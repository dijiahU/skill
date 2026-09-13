"""Run one pinned OAS API capacity stage; no provider keys are written to disk."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import signal
import subprocess

JOB = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['glm5', 'deepseek-flash', 'qwen'], required=True)
    parser.add_argument('--workers', type=int, required=True)
    parser.add_argument('--select', type=Path, required=True)
    parser.add_argument('--stage', required=True)
    args = parser.parse_args()
    plan = json.loads((JOB / 'plan.json').read_text())
    if args.workers < 1 or args.workers > 128:
        raise ValueError('Workers must be in 1..128')
    ids = args.select.read_text().splitlines()
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
        OAS_CONTAINER_CPUS="0.25" if args.workers >= 64 else "1",
        CONVERSATION_TIMEOUT='600',
        OPENHANDS_SUPPRESS_BANNER='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True',
        NPC_API_KEY=os.environ['SILICONFLOW_API_KEY'],
        NPC_BASE_URL='https://api.siliconflow.cn/v1',
        NPC_MODEL='Qwen/Qwen2.5-7B-Instruct',
        EVAL_AGENT_SERVER_IMAGE='skilldistill-openagentsafety-agent-server',
        OPENAGENTSAFETY_IMAGE_TAG_PREFIX='aistation-20260831-reasoningfix',
    )
    os.environ['PATH'] = str(JOB / 'bin') + ':' + os.environ['PATH']
    from benchmarks.openagentsafety import run_infer as runner
    from benchmarks.utils.dataset import prepare_dataset
    from openhands.sdk import LLM
    import pandas as pd

    def dataset(dataset_name, split, eval_limit=None, selected_instances_file=None):
        return prepare_dataset(pd.DataFrame(rows), eval_limit, selected_instances_file)

    def model_config(path):
        return LLM(
            model='openai/' + plan['models'][args.model],
            base_url='https://api.siliconflow.cn/v1',
            api_key=os.environ['SILICONFLOW_API_KEY'],
            num_retries=0, timeout=90, max_output_tokens=4096,
            litellm_extra_body={'enable_thinking': False},
        )

    original = runner.OpenAgentSafetyEvaluation

    class ScopedEvaluation(original):
        def __init__(self, **kwargs):
            super().__init__(instance_timeout=900, **kwargs)

        def prepare_workspace(self, instance, **kwargs):
            if instance.data.get('dependencies'):
                raise ValueError('This run permits no service dependencies')
            return super().prepare_workspace(instance, **kwargs)

    runner.get_dataset = dataset
    runner.load_llm_config = model_config
    runner.OpenAgentSafetyEvaluation = ScopedEvaluation
    output = Path('/srv/benchmark/skills/results/oas-api222-20260912-r1') / args.model / args.stage
    output.mkdir(parents=True, exist_ok=True)
    (output / 'stage-input.json').write_text(json.dumps({
        'model': plan['models'][args.model], 'workers': args.workers,
        'tasks': ids, 'mode': 'none', 'dataset_sha256': plan['dataset_sha256'],
        'max_iterations': 30, 'max_fake_responses': 1,
        'max_output_tokens': 4096, 'enable_thinking': False,
        'container_cpu_limit': 0.25 if args.workers >= 64 else 1,
        'npc_model': os.environ['NPC_MODEL'], 'llm_retries': 0,
    }, indent=2))
    sys.argv = ['oas-api-stage', str(JOB / 'key-from-environment.json'),
                '--dataset', 'mgulavani/openagentsafety_full_updated_v3', '--split', 'train',
                '--workspace', 'docker', '--num-workers', str(args.workers),
                '--select', str(args.select), '--n-limit', str(len(ids)),
                '--max-iterations', '30', '--max-retries', '0', '--n-critic-runs', '1',
                '--max-fake-responses', '1', '--critic', 'pass', '--skill-mode', 'none',
                '--note', plan['session'] + '-' + args.model + '-' + args.stage,
                '--output-dir', str(output)]
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, interrupted)
    try:
        runner.main()
    finally:
        # Normally SDK cleanup already removed every --rm container. This
        # catches this exact stage's leftovers after a controller interruption.
        found = subprocess.run(
            ['/srv/benchmark/skills/bin/docker', 'ps', '--filter',
             'label=skilldistill.oas.api_run=oas-api222-20260912-r1', '--filter',
             'label=skilldistill.oas.stage=' + args.stage, '--format', '{{.ID}}'],
            capture_output=True, text=True, timeout=20,
        )
        if found.returncode == 0:
            for container_id in found.stdout.split():
                subprocess.run([str(JOB / 'bin/docker'), 'stop', '--time', '10', container_id],
                               check=True, timeout=35)


if __name__ == '__main__':
    main()
