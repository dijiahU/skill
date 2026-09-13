"""Reuse completed trajectories; never regrade partial or stateful runs here."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
from typing import Any
from resume_helpers import JOB, RESULTS, read_stage, valid
from resume_after_recharge import merged, write
from scoring_repairs import repair, REPAIRABLE, STATEFUL, SOURCE

TREE = ast.parse((SOURCE / 'run_infer.py').read_text())
RUNNER = next(ast.literal_eval(n.value) for n in TREE.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == '_GRADER_RUNNER' for t in n.targets))
NODE = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'build_evaluator_trajectory_records')
NAMESPACE = {'json': json, 'Any': Any}
exec(compile(ast.Module(body=[NODE], type_ignores=[]), '<original-trajectory-converter>', 'exec'), NAMESPACE)
RECORDS = NAMESPACE['build_evaluator_trajectory_records']
PARSE = runpy.run_path(str(SOURCE / 'evaluator_output.py'))['parse_evaluator_output']


def regrade(model):
    good, _ = merged(model)
    selected = {}
    for stage in sorted((RESULTS / model).iterdir(), key=lambda p:p.stat().st_mtime):
        if not stage.is_dir():
            continue
        for task, row in read_stage(model, stage.name).items():
            test = row.get('test_result') or {}
            detail = test.get('skilldistill') or {}
            if (task in REPAIRABLE - STATEFUL and task not in good and row.get('history')
                    and not detail.get('graded_from_partial_trajectory') and not detail.get('conversation_error')
                    and (row.get('error') or test.get('error'))
                    and detail.get('skill_mode') == 'safety-orchestrator'):
                selected[task] = (stage.name, row)
    outcomes = []
    data = {r['instance_id']:r for r in map(json.loads, (JOB / 'tasks222.jsonl').read_text().splitlines())}
    for task, (source_stage, row) in selected.items():
        stage = f'skills100-{model}-entrypoint-regrade-r3-{task}'
        root = RESULTS / model / stage
        if root.exists():
            continue
        root.mkdir(parents=True)
        original = data[task]['evaluator_code']; patched = repair(original, task)
        assert patched != original
        records = RECORDS(row['history'])
        args = [str(JOB / 'bin/docker'), 'run', '--rm', '-i', '--network', 'none', '--runtime', 'runc',
                '--read-only', '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m', '--memory', '512m', '--cpus', '1',
                '--pids-limit', '128', '--name', 'skilldistill-oas-grader-' + model + '-' + task + '-r3',
                '--label', 'skilldistill.openagentsafety.grader=true', '--entrypoint', 'python',
                'skilldistill-openagentsafety-agent-server:aistation-20260831-reasoningfix-openagentsafety', '-c', RUNNER]
        result = subprocess.run(args, input=json.dumps({'evaluator_code':patched, 'trajectory_records':records}),
                                capture_output=True, text=True, env=dict(os.environ, OAS_STAGE=stage), timeout=180)
        graded = PARSE(result.stdout, result.stderr, result.returncode)
        output = copy.deepcopy(row)
        detail = copy.deepcopy((row.get('test_result') or {}).get('skilldistill') or {})
        detail['evaluator_compat'] = {'repair':'missing-single-checkpoint-entrypoint-v1',
            'original_sha256':hashlib.sha256(original.encode()).hexdigest(),
            'repaired_sha256':hashlib.sha256(patched.encode()).hexdigest(),
            'score_provenance':'content-pinned-compatibility-repair', 'reused_complete_trajectory':True,
            'source_stage':source_stage}
        graded['skilldistill'] = detail
        output.update(test_result=graded, error=graded.get('error'), metrics=None,
                      regrade_source={'stage':source_stage,'instance_id':task,'inference_reused':True})
        (root / 'output.critic_attempt_1.jsonl').write_text(json.dumps(output) + '\n')
        outcomes.append({'task':task,'source_stage':source_stage,'valid':valid(output),'score':graded.get('final_score')})
    summary_path = JOB / ('entrypoint-regrade-' + model + '-summary.json')
    previous = json.loads(summary_path.read_text()).get('outcomes', []) if summary_path.exists() else []
    combined = {item['task']:item for item in previous + outcomes}
    write(summary_path, {'model':model,'outcomes':list(combined.values())})
    merged(model)
    return outcomes


if __name__ == '__main__':
    import sys
    print(json.dumps(regrade(sys.argv[1])))
