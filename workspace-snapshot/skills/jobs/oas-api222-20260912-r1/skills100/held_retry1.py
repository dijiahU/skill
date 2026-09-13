"""Retry the six user-authorized held tasks once after the active model queue."""
import argparse
import fcntl
import json
import time
from resume_helpers import JOB
from resume_after_recharge import merged, run_stage, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['glm5', 'deepseek-flash'], required=True)
    model = parser.parse_args().model
    own = (JOB / ('held-retry1-controller-' + model + '.lock')).open('a')
    fcntl.flock(own, fcntl.LOCK_EX | fcntl.LOCK_NB)
    plan = json.loads((JOB / 'held-retry1-plan.json').read_text())['models'][model]
    path = JOB / ('held-retry1-state-' + model + '.json')
    state = {'model': model, 'status': 'queued behind active model controller',
             'tasks': plan['tasks'], 'stage': plan['stage'], 'max_iterations': 100,
             'attempts_per_task': 1}
    def save():
        state['updated_at'] = time.time()
        write(path, state)
    save()
    lock = (JOB / ('repair-' + model + '.lock')).open('a')
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        hold = JOB / 'hold-next-models.json'
        if hold.exists() and json.loads(hold.read_text()).get('active', True):
            state['status'] = 'paused by existing provider or runner hold'
            save()
            return
        good, _ = merged(model)
        excluded = set(json.loads((JOB / 'unscorable-tasks.json').read_text())['task_ids'])
        tasks = [task for task in plan['tasks'] if task not in good and task not in excluded]
        state.update(tasks_to_run=tasks, skipped_already_valid=[t for t in plan['tasks'] if t in good])
        if not tasks:
            state['status'] = 'finished; no unresolved eligible tasks'
            save()
            return
        state['status'] = 'running held tasks once'
        save()
        result = run_stage(model, tasks, plan['stage'], workers=min(plan['workers'], len(tasks)))
        _, summary = merged(model)
        state.update(status='finished' if result['returncode'] == 0 else 'paused after provider or runner error',
                     result=result, valid_tasks=summary['valid_tasks'])
        save()
    except Exception as exc:
        state.update(status='controller error; results retained', error_type=type(exc).__name__)
        save()
        raise


if __name__ == '__main__':
    main()
