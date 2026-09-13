"""Continue repaired, scoreable tasks after each model's active wave."""
import argparse
import fcntl
import json
import time
from resume_helpers import JOB, read_stage, valid
from resume_after_recharge import merged, run_stage, write
from repair_model import pending
from regrade_entrypoints import regrade


def select(model, retry_only=False):
    todo, held = pending(model, retry_only=retry_only)
    _, summary = merged(model)
    stages = {s:read_stage(model,s) for s in set(summary['selected_attempts'].values())}
    selected, budget_or_stuck = [], []
    for task in todo:
        row = stages.get(summary['selected_attempts'].get(task),{}).get(task) or {}
        test = row.get('test_result') or {}
        reason = str((test.get('skilldistill') or {}).get('conversation_error') or '')
        if 'MaxIterationsReached' in reason or 'Remote conversation got stuck' in reason:
            budget_or_stuck.append(task)
        else:
            selected.append(task)
    return selected, held, budget_or_stuck


def main():
    p = argparse.ArgumentParser(); p.add_argument('--model', choices=['glm5','deepseek-flash','qwen'], required=True)
    model = p.parse_args().model
    own = (JOB / ('repair3-controller-' + model + '.lock')).open('a')
    fcntl.flock(own, fcntl.LOCK_EX | fcntl.LOCK_NB)
    path = JOB / ('repair3-state-' + model + '.json')
    levels = [8,4,2] if model == 'qwen' else [32,16,8]
    state = {'model':model, 'status':'waiting for active model wave', 'stages':[],
             'worker_levels':levels, 'max_iterations':100, 'excluded_unscorable':38,
             'evaluator_compat':True, 'cpu_per_agent':1}
    def save():
        state['updated_at'] = time.time(); write(path,state)
    save()
    lock = (JOB / ('repair-' + model + '.lock')).open('a')
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        state['regraded'] = regrade(model)
        for index, workers in enumerate(levels):
            todo, held, budget = select(model, retry_only=index > 0)
            state.update(held_other_errors=held, held_budget_or_stuck=budget)
            if not todo:
                break
            state.update(status='running repaired scoreable tasks', current_workers=workers, tasks_this_stage=len(todo))
            save()
            result = run_stage(model,todo,f'skills100-{model}-repair3-w{workers}',workers=workers)
            state['stages'].append(result)
            if result['returncode'] != 0:
                state['status'] = 'paused after provider or runner error';save();return
        state['regraded_after_wave'] = regrade(model)
        _, summary = merged(model)
        state.update(status='repair3 finished; see held tasks', result={k:v for k,v in summary.items() if k != 'selected_attempts'})
        save()
    except Exception as exc:
        state.update(status='controller error; results retained',error_type=type(exc).__name__);save();raise


if __name__ == '__main__':
    main()
