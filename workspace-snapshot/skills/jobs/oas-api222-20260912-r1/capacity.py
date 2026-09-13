"""Progress through disjoint OAS tasks with measured, bounded concurrency."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from monitor import snapshot

JOB = Path(__file__).resolve().parent
RESULTS = Path('/srv/benchmark/skills/results/oas-api222-20260912-r1')


def results(model, stage):
    rows = []
    for path in (RESULTS / model / stage).rglob('output.jsonl'):
        for line in path.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def summary(model, stage, ids, workers, elapsed, returncode, peak):
    rows = results(model, stage)
    by_id = {r['instance_id']: r for r in rows}
    valid = []
    errors = []
    for task in ids:
        row = by_id.get(task)
        if row is None:
            errors.append({'task': task, 'error': 'missing output'})
            continue
        test = row.get('test_result') or {}
        score = test.get('final_score') or {}
        partial = (test.get('skilldistill') or {}).get('graded_from_partial_trajectory')
        if row.get('error') or 'result' not in score or 'total' not in score or partial:
            errors.append({'task': task, 'error': str(row.get('error') or test.get('error') or 'missing/partial grading')[:350]})
        else:
            valid.append(task)
    latency = [item['latency'] for r in rows for item in (r.get('metrics') or {}).get('response_latencies', []) if isinstance(item.get('latency'), (int, float))]
    return {'model': model, 'stage': stage, 'workers': workers, 'task_count': len(ids),
            'valid_count': len(valid), 'valid_task_ids': valid, 'errors': errors,
            'elapsed_seconds': round(elapsed, 2), 'returncode': returncode,
            'tasks_per_minute': round(len(valid) * 60 / max(elapsed, 1), 3),
            'peak_owned_containers': peak,
            'mean_llm_response_seconds': round(sum(latency) / len(latency), 3) if latency else None,
            'ok': returncode == 0 and len(valid) == len(ids)}


def run_stage(model, workers, ids, stage):
    selection = JOB / (model + '-' + stage + '.txt')
    selection.write_text('\n'.join(ids) + '\n')
    start = time.monotonic()
    with (JOB / (model + '-' + stage + '.log')).open('a') as log:
        process = subprocess.Popen([str(JOB / 'run_stage.sh'), '--model', model,
                                    '--workers', str(workers), '--select', str(selection),
                                    '--stage', stage], stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        (JOB / 'active-stage.json').write_text(json.dumps({'model': model, 'stage': stage, 'workers': workers, 'pid': process.pid, 'tasks': ids, 'started': time.time()}, indent=2))
        peak = 0
        while process.poll() is None:
            row = snapshot(stage=stage)
            peak = max(peak, row.get('running_containers', 0))
            # This ceiling bounds the whole stage, including startup and grading.
            if time.monotonic() - start > 1200 * max(1, (len(ids) + workers - 1) // workers):
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(10)
        process.wait()
    outcome = summary(model, stage, ids, workers, time.monotonic() - start, process.returncode, peak)
    (JOB / (model + '-' + stage + '-summary.json')).write_text(json.dumps(outcome, indent=2))
    return outcome


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['glm5','deepseek-flash','qwen'], required=True)
    args = parser.parse_args()
    model = args.model
    order = (JOB / 'capacity-order.txt').read_text().splitlines()
    smoke = (JOB / 'smoke.txt').read_text().splitlines()
    complete = set()
    stages = []
    prior_smoke = results(model, 'smoke-w2')
    if prior_smoke:
        check = summary(model, 'smoke-w2', smoke, 2, 0, 0, 2)
        if not check['ok']:
            raise RuntimeError('Existing smoke did not pass')
        complete.update(smoke)
    else:
        check = run_stage(model, 2, smoke, 'smoke-w2')
        stages.append(check)
        if not check['ok']:
            (JOB / (model + '-capacity.json')).write_text(json.dumps({'model':model,'stages':stages,'status':'smoke failed'},indent=2))
            return
        complete.update(smoke)
    stable = 2
    for workers in [4,8,16,24,32,48]:
        candidates = [i for i in order if i not in complete][:workers]
        outcome = run_stage(model, workers, candidates, 'capacity-w' + str(workers))
        stages.append(outcome)
        complete.update(outcome['valid_task_ids'])
        state = {'model':model,'highest_passed_workers':stable,'stages':stages,'completed_distinct_tasks':len(complete),'status':'running'}
        if outcome['ok']:
            stable = workers
            state['highest_passed_workers'] = stable
        else:
            state['status'] = 'stopped at failed stage; inspect before resuming'
        (JOB / (model + '-capacity.json')).write_text(json.dumps(state,indent=2))
        print(json.dumps({k:v for k,v in outcome.items() if k not in ['valid_task_ids','errors']}),flush=True)
        if not outcome['ok']:
            return
    remaining = [i for i in (JOB / 'tasks222.txt').read_text().splitlines() if i not in complete]
    outcome = run_stage(model, stable, remaining, 'remaining-w' + str(stable))
    stages.append(outcome)
    complete.update(outcome['valid_task_ids'])
    (JOB / (model + '-capacity.json')).write_text(json.dumps({'model':model,'highest_passed_workers':stable,'stages':stages,'completed_distinct_tasks':len(complete),'status':'finished all scheduled tasks; review known invalid tasks separately'},indent=2))


if __name__ == '__main__':
    main()
