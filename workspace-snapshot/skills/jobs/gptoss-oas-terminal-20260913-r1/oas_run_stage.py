"""Run one pinned OAS API capacity stage; no provider keys are written to disk."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import signal
import subprocess
import random

JOB = Path('/srv/benchmark/skills/jobs/oas-api222-20260912-r1/skills100')
TASK_JOB = Path(__file__).resolve().parent
sys.path.insert(0, str(JOB))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['gptoss'], required=True)
    parser.add_argument('--workers', type=int, required=True)
    parser.add_argument('--select', type=Path, required=True)
    parser.add_argument('--stage', required=True)
    args = parser.parse_args()
    obsolete = JOB / 'obsolete-stages.json'
    if obsolete.exists() and args.stage in json.loads(obsolete.read_text())['stages']:
        raise RuntimeError('Stage superseded by repaired followup; no containers allocated')
    hold = JOB / 'hold-next-models.json'
    if hold.exists():
        held = json.loads(hold.read_text())
        admission_path = JOB / 'parallel-admission.json'
        admission = json.loads(admission_path.read_text()) if admission_path.exists() else {}
        authorized_parallel = (held.get('reason') == admission.get('bypass_reason')
                               and args.stage in admission.get('stages', {}).get(args.model, []))
        if held.get('active', True) and not authorized_parallel:
            raise RuntimeError('Model queue is held; no containers allocated')
    model_lock = (JOB / ('runner-' + args.model + '.lock')).open('a')
    fcntl.flock(model_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    plan = json.loads((TASK_JOB / 'oas-plan.json').read_text())
    if args.workers < 1 or args.workers > 128:
        raise ValueError('Workers must be in 1..128')
    ids = args.select.read_text().splitlines()
    unscorable = JOB / 'unscorable-tasks.json'
    if unscorable.exists() and set(ids).intersection(json.loads(unscorable.read_text())['task_ids']):
        raise ValueError('Selection includes user-excluded unscorable tasks')
    dataset_file = JOB / 'tasks222.jsonl'
    if hashlib.sha256(dataset_file.read_bytes()).hexdigest() != plan['dataset_sha256']:
        raise ValueError('Pinned dataset changed')
    rows = [json.loads(line) for line in dataset_file.read_text().splitlines()]
    by_id = {row['instance_id']: row for row in rows}
    if len(ids) != len(set(ids)) or not ids or any(i not in by_id for i in ids):
        raise ValueError('Invalid task selection')
    if any(by_id[i].get('dependencies') for i in ids):
        raise ValueError('External service dependency is forbidden')
    os.environ.update(
        OAS_STAGE=args.stage,
        OAS_WORKERS=str(args.workers),
        OAS_CONTAINER_CPUS="1",
        CONVERSATION_TIMEOUT='3600',
        OPENHANDS_SUPPRESS_BANNER='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True',
        NPC_API_KEY=os.environ['DEEPSEEK_API_KEY'],
        NPC_BASE_URL='https://api.deepseek.com/v1',
        NPC_MODEL='deepseek-flash',
        OPENAGENTSAFETY_SKILLS_IMAGE=plan['skills_image'],
        EVAL_AGENT_SERVER_IMAGE='skilldistill-openagentsafety-agent-server',
        OPENAGENTSAFETY_IMAGE_TAG_PREFIX='aistation-20260831-reasoningfix',
    )
    os.environ['PATH'] = str(JOB / 'bin') + ':' + os.environ['PATH']
    from benchmarks.openagentsafety import run_infer as runner
    from scoring_repairs import repair as repair_evaluator
    runner.repair_evaluator_entrypoint = repair_evaluator
    from benchmarks.utils.dataset import prepare_dataset
    from openhands.sdk import LLM
    import pandas as pd

    def dataset(dataset_name, split, eval_limit=None, selected_instances_file=None):
        return prepare_dataset(pd.DataFrame(rows), eval_limit, selected_instances_file)

    def model_config(path):
        return LLM(
            model='openai/' + plan['models'][args.model],
            base_url=os.environ['GPTOSS_BASE_URL'],
            api_key='EMPTY', model_canonical_name='openai/gpt-5',
            max_input_tokens=28000, reasoning_effort=None,
            num_retries=2, timeout=180, max_output_tokens=4096,
        )

    original_build_llm = runner.build_eval_llm

    def per_task_llm(llm, *, usage_id=None):
        configured = original_build_llm(llm, usage_id=usage_id)
        configured = configured.model_copy(deep=True, update={
            'num_retries': 2, 'retry_multiplier': random.uniform(30, 45),
            'retry_min_wait': 30, 'retry_max_wait': 180,
        })
        return configured

    runner.build_eval_llm = per_task_llm

    original = runner.OpenAgentSafetyEvaluation

    class ScopedEvaluation(original):
        def __init__(self, **kwargs):
            super().__init__(instance_timeout=4800, **kwargs)

        def evaluate_instance(self, instance, workspace):
            output = super().evaluate_instance(instance, workspace)
            details = (output.test_result or {}).get('skilldistill') or {}
            compat = details.get('evaluator_compat') or {}
            if compat:
                compat['score_provenance'] = 'content-pinned-compatibility-repair'
                if instance.id == 'safety-unsafe-server-c':
                    compat['repair'] = 'remove-undefined-extra-checkpoint-call-v1'
            return output

        def prepare_workspace(self, instance, **kwargs):
            if (JOB / ('stop-' + args.stage + '.json')).exists():
                raise RuntimeError('Stage admission stopped by provider circuit breaker')
            if instance.data.get('dependencies'):
                raise ValueError('This run permits no service dependencies')
            return super().prepare_workspace(instance, **kwargs)

    runner.get_dataset = dataset
    runner.load_llm_config = model_config
    runner.OpenAgentSafetyEvaluation = ScopedEvaluation
    output = Path('/srv/benchmark/skills/results/oas-api222-20260912-r1') / 'skills100' / args.model / args.stage
    output.mkdir(parents=True, exist_ok=True)
    (output / 'stage-input.json').write_text(json.dumps({
        'model': plan['models'][args.model], 'workers': args.workers,
        'tasks': ids, 'mode': 'safety-orchestrator', 'dataset_sha256': plan['dataset_sha256'],
        'max_iterations': 100, 'max_fake_responses': 1, 'evaluator_entrypoint_compat': True,
        'max_output_tokens': 4096, 'reasoning_effort': None, 'model_source': 'local-gpu',
        'context_window': 32768, 'max_input_tokens': 28000, 'condenser_max_tokens': 22000,
        'container_cpu_limit': 1, 'global_agent_container_limit': 96, 'bridge_reserved_addresses': 32,
        'npc_model': os.environ['NPC_MODEL'], 'llm_retries': 2,
        'retry_policy': {'min_wait': 30, 'max_wait': 180, 'per_task_multiplier_range': [30, 45]}, 'npc_base_url': os.environ['NPC_BASE_URL'], 'conversation_timeout': 3600,
    }, indent=2))
    sys.argv = ['oas-api-stage', str(JOB / 'key-from-environment.json'),
                '--dataset', 'mgulavani/openagentsafety_full_updated_v3', '--split', 'train',
                '--workspace', 'docker', '--num-workers', str(args.workers),
                '--select', str(args.select), '--n-limit', str(len(ids)),
                '--max-iterations', '100', '--max-retries', '0', '--n-critic-runs', '1',
                '--max-fake-responses', '1', '--critic', 'pass', '--skill-mode', 'safety-orchestrator',
                '--evaluator-entrypoint-compat',
                '--enable-condenser', '--condenser-max-tokens', '22000',
                '--condenser-max-output-tokens', '1024',
                '--safety-orchestrator-root', str(JOB / 'bundle'),
                '--note', plan['session'] + '-' + args.model + '-' + args.stage,
                '--output-dir', str(output)]
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, interrupted)
    try:
        runner.main()
    finally:
        from stage_cleanup import cleanup_stage
        cleanup_stage(args.stage)


if __name__ == '__main__':
    main()
