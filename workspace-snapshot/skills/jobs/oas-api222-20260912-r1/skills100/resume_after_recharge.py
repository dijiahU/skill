"""Resume only unresolved skills tasks, with a balance circuit breaker."""
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import threading

from monitor import snapshot
from resume_helpers import JOB, RESULTS, valid, read_stage, balance_error, probe

PLAN = json.loads((JOB / 'plan.json').read_text())
SESSION_LABEL = 'skilldistill.oas.api_run=oas-api222-20260912-r1'
DOCKER = '/srv/benchmark/skills/bin/docker'
GUARD = str(JOB / 'bin/docker')


def write(path, data):
    temporary = path.with_name(path.name + f'.{os.getpid()}.{threading.get_ident()}.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    os.replace(temporary, path)


def merged(model):
    selected = {}
    stages = sorted((RESULTS / model).iterdir(), key=lambda p: p.stat().st_mtime) if (RESULTS / model).exists() else []
    for stage in stages:
        if not stage.is_dir():
            continue
        for task, row in read_stage(model, stage.name).items():
            if task not in selected or (not valid(selected[task]['row'])):
                selected[task] = {'stage': stage.name, 'row': row}
    good = {task: value for task, value in selected.items() if valid(value['row'])}
    summary = {'model': model, 'unique_tasks_with_output': len(selected), 'valid_tasks': len(good),
               'points': sum(v['row']['test_result']['final_score']['result'] for v in good.values()),
               'total': sum(v['row']['test_result']['final_score']['total'] for v in good.values()),
               'invalid_tasks': len(selected) - len(good),
               'selected_attempts': {task: v['stage'] for task, v in selected.items()}}
    write(JOB / ('consolidated-' + model + '.json'), summary)
    return good, summary


def stop_owned_stage(process, stage, reason):
    marker = {'stage': stage, 'reason': reason, 'time': time.time()}
    write(JOB / ('stop-' + stage + '.json'), marker)
    write(JOB / 'hold-next-models.json', {'active': True, **marker})
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
    except ProcessLookupError:
        pass
    # Reuse the stage cleanup that verifies prefix, session and stage labels,
    # then retries removal of stopped as well as running owned containers.
    from stage_cleanup import cleanup_stage
    cleanup_stage(stage)


def run_stage(model, ids, stage, workers=128):
    selection = JOB / (model + '-' + stage + '.txt')
    if selection.exists() or (RESULTS / model / stage).exists():
        raise RuntimeError('Refusing duplicate recharge attempt: ' + stage)
    write(JOB / ('health-' + stage + '.json'), health := probe(PLAN['models'][model]))
    if not health['ok']:
        return {'model': model, 'stage': stage, 'status': 'provider preflight failed', 'health': health, 'returncode': 2}
    selection.write_text('\n'.join(ids) + '\n')
    start = time.monotonic()
    with (JOB / (model + '-' + stage + '.log')).open('a') as log:
        process = subprocess.Popen([str(JOB / 'run_stage.sh'), '--model', model, '--workers', str(workers),
            '--select', str(selection), '--stage', stage], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        write(JOB / ('active-stage-' + model + '.json'), {'model': model, 'stage': stage, 'workers': workers, 'pid': process.pid, 'tasks': ids, 'started': time.time()})
        last_check = time.monotonic()
        peak = 0
        stopped = None
        while process.poll() is None:
            rows = read_stage(model, stage)
            if any(balance_error(row) for row in rows.values()):
                stopped = 'structured provider error: insufficient account balance'
            if not stopped and time.monotonic() - last_check >= 60:
                health = probe(PLAN['models'][model])
                with (JOB / 'provider-health-history.jsonl').open('a') as stream:
                    stream.write(json.dumps({'stage': stage, **health}) + '\n')
                last_check = time.monotonic()
                if health['balance_exhausted']:
                    stopped = 'provider health check: HTTP 402 / insufficient balance'
            if time.monotonic() - start > 7200 * max(1, (len(ids) + workers - 1) // workers):
                stopped = 'stage wall time exceeded'
            if stopped:
                stop_owned_stage(process, stage, stopped)
                break
            resource = snapshot(stage=stage)
            peak = max(peak, resource.get('running_containers', 0))
            merged(model)
            time.sleep(5)
        process.wait()
    rows = read_stage(model, stage)
    valid_count = sum(valid(row) for row in rows.values())
    result = {'model': model, 'stage': stage, 'task_count': len(ids), 'returned': len(rows),
              'valid_count': valid_count, 'workers': workers, 'peak_containers': peak,
              'returncode': process.returncode, 'elapsed_seconds': round(time.monotonic() - start, 2),
              'status': stopped or 'stage finished'}
    write(JOB / (model + '-' + stage + '-summary.json'), result)
    return result


def main():
    lock = (JOB / 'queue.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    all_ids = (JOB / 'tasks222.txt').read_text().splitlines()
    state = {'status': 'resuming after recharge', 'models': ['glm5', 'deepseek-flash', 'qwen'],
             'workers': 128, 'max_iterations': 100, 'skill_mode': 'safety-orchestrator',
             'npc_model': 'deepseek-flash', 'stages': [], 'prior_valid_preserved': {}}
    for model in state['models']:
        good, _ = merged(model)
        state['prior_valid_preserved'][model] = len(good)
        todo = [task for task in all_ids if task not in good]
        if not todo:
            continue
        assert not set(todo).intersection(good)
        state['status'] = 'running ' + model + ' recharge retry'
        write(JOB / 'queue-state.json', state)
        result = run_stage(model, todo, 'skills100-' + model + '-recharge1-w128')
        state['stages'].append(result)
        _, state['latest_consolidated'] = merged(model)
        write(JOB / 'queue-state.json', state)
        if result['returncode'] != 0 or result.get('valid_count', 0) == 0 or result.get('returned', 0) != len(todo):
            state['status'] = 'paused after stage error; results preserved'
            write(JOB / 'queue-state.json', state)
            return
    state['status'] = 'recharge queue finished; inspect consolidated per-model results'
    write(JOB / 'queue-state.json', state)


if __name__ == '__main__':
    main()
