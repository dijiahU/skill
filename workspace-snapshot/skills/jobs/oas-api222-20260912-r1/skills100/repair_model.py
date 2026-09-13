"""Validate each model, then recover unresolved tasks with bounded concurrency."""
import argparse
import fcntl
import json
import time
from resume_helpers import JOB, RESULTS, read_stage, valid
from scoring_repairs import REPAIRABLE
from resume_after_recharge import merged, run_stage, write

MODELS = ['glm5', 'deepseek-flash', 'qwen']
TRANSIENT = ('TPM limit reached', 'RateLimitError', 'Connection error', 'Connection refused',
             'Remote conversation ended with error', 'timed out', 'Timeout',
             'no available IPv4 addresses', 'OAS run guard:', 'remote conversation',
             'Failed to run docker container', 'account balance is insufficient')


def pending(model, retry_only=False):
    good, summary = merged(model)
    stages = {s: read_stage(model, s) for s in set(summary['selected_attempts'].values())}
    all_tasks = (JOB / 'tasks222.txt').read_text().splitlines()
    excluded_path = JOB / 'unscorable-tasks.json'
    excluded = set(json.loads(excluded_path.read_text())['task_ids']) if excluded_path.exists() else set()
    todo, held = [], []
    for task in all_tasks:
        if task in good or task in excluded:
            continue
        stage = summary['selected_attempts'].get(task)
        row = stages.get(stage, {}).get(task)
        if row is None:
            todo.append(task)
            continue
        test = row.get('test_result') or {}
        detail = test.get('skilldistill') or {}
        error = str(row.get('error') or test.get('error') or '')
        transport = error + ' ' + str(detail.get('conversation_error') or '')
        transient = any(token in transport for token in TRANSIENT)
        if not transient and retry_only and stage:
            for log in (RESULTS / model / stage).rglob('instance_' + task + '.output.log'):
                if any(token in log.read_text(errors='replace') for token in TRANSIENT):
                    transient = True
                    break
        # Preserve genuine full-trajectory evaluator defects separately. Guard
        # failures, timeouts and partial traces are eligible for recovery.
        grader_defect = (task not in REPAIRABLE and not detail.get('graded_from_partial_trajectory') and not transient
                         and ('Evaluator' in error or 'Evaluation failed' in error))
        if grader_defect or (retry_only and not transient):
            held.append(task)
        else:
            todo.append(task)
    assert not set(todo).intersection(good)
    return todo, held


def smoke_ids(model, todo):
    candidates = {}
    for other in MODELS:
        if other == model:
            continue
        good, _ = merged(other)
        for task, value in good.items():
            if task in todo:
                # Prefer short tasks with a working evaluator in another model.
                size = len(json.dumps(value['row'].get('history') or []))
                candidates[task] = min(size, candidates.get(task, size))
    ordered = sorted(candidates, key=lambda task: (candidates[task], task))
    return (ordered + [task for task in todo if task not in candidates])[:2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=MODELS, required=True)
    model = parser.parse_args().model
    lock = (JOB / ('repair-' + model + '.lock')).open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state_path = JOB / ('repair-state-' + model + '.json')
    state = {'model': model, 'status': 'preparing verification', 'stages': [],
             'workers': [32, 16, 8], 'max_iterations': 100, 'skill_mode': 'safety-orchestrator',
             'npc_model': 'deepseek-flash', 'global_agent_limit': 96}
    def save():
        state['updated_at'] = time.time()
        write(state_path, state)
    save()
    try:
        todo, held = pending(model)
        state['evaluator_tasks_held'] = held
        state['valid_preserved_at_restart'] = len(merged(model)[0])
        if todo:
            smoke = smoke_ids(model, todo)
            state.update(status='verifying real tasks', smoke_tasks=smoke)
            save()
            result = run_stage(model, smoke, 'skills100-' + model + '-repair2-smoke', workers=2)
            state['stages'].append(result)
            if result['returncode'] != 0 or result.get('valid_count') != len(smoke):
                state['status'] = 'verification incomplete; broad recovery held'
                save()
                return
        for index, workers in enumerate([32, 16, 8]):
            todo, held = pending(model, retry_only=index > 0)
            state['evaluator_or_nontransient_tasks_held'] = held
            if not todo:
                break
            state.update(status='recovering unresolved tasks', current_workers=workers, tasks_this_stage=len(todo))
            save()
            result = run_stage(model, todo, f'skills100-{model}-repair2-w{workers}', workers=workers)
            state['stages'].append(result)
            if result['returncode'] != 0:
                state['status'] = 'paused after runner or provider error'
                save()
                return
        _, summary = merged(model)
        state.update(status='recovery finished; retained invalid tasks require review',
                     result={k:v for k,v in summary.items() if k != 'selected_attempts'})
        save()
    except Exception as exc:
        state.update(status='controller error; results retained', error_type=type(exc).__name__)
        save()
        raise


if __name__ == '__main__':
    main()
