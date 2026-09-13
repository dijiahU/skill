"""Run the two authorized baseline arms after their active treatment queues."""
import argparse
import fcntl
import json
import time
from baseline_helpers import JOB, read_stage, valid
from baseline_resume import merged, run_stage, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['deepseek-flash', 'qwen'], required=True)
    model = parser.parse_args().model
    own = (JOB / ('baseline1-controller-' + model + '.lock')).open('a')
    fcntl.flock(own, fcntl.LOCK_EX | fcntl.LOCK_NB)
    config = json.loads((JOB / 'baseline1-plan.json').read_text())
    settings = config['models'][model]
    path = JOB / ('baseline1-state-' + model + '.json')
    state = {'model': model, 'status': 'queued behind active skills controller',
             'skill_mode': 'none', 'hooks_enabled': False, 'max_iterations': 100,
             'eligible_tasks': 184, 'stages': []}
    def save():
        state['updated_at'] = time.time()
        write(path, state)
    def held():
        p = JOB / 'hold-next-models.json'
        return p.exists() and json.loads(p.read_text()).get('active', True)
    save()
    lock = (JOB / ('repair-' + model + '.lock')).open('a')
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        if held():
            state['status'] = 'paused by existing provider hold'
            save()
            return
        smoke = settings['smoke_tasks']
        state.update(status='validating baseline on real tasks', tasks_this_stage=len(smoke))
        save()
        result = run_stage(model, smoke, f'baseline100-{model}-r1-smoke', workers=2)
        state['stages'].append(result)
        rows = read_stage(model, result['stage'])
        isolated = len(rows) == len(smoke) and all(
            valid(row) and (row.get('test_result') or {}).get('skilldistill', {}).get('skill_mode') == 'none'
            and (row.get('test_result') or {}).get('skilldistill', {}).get('hooks_enabled') is False
            and not (row.get('test_result') or {}).get('skilldistill', {}).get('loaded_skills')
            and not (row.get('test_result') or {}).get('skilldistill', {}).get('invoked_skills')
            for row in rows.values())
        state['smoke_isolation_verified'] = isolated
        save()
        if result['returncode'] != 0 or not isolated:
            state['status'] = 'paused after incomplete baseline validation'
            save()
            return
        good, _ = merged(model)
        tasks = [task for task in config['task_ids'] if task not in good]
        if tasks and not held():
            state.update(status='running baseline', tasks_this_stage=len(tasks), workers=settings['workers'])
            save()
            result = run_stage(model, tasks, f'baseline100-{model}-r1-w{settings["workers"]}', workers=settings['workers'])
            state['stages'].append(result)
        _, summary = merged(model)
        state.update(status='baseline batches ended; inspect unresolved tasks' if not held() else 'paused by provider hold',
                     result={k:v for k,v in summary.items() if k != 'selected_attempts'})
        save()
    except Exception as exc:
        state.update(status='controller error; results retained', error_type=type(exc).__name__)
        save()
        raise


if __name__ == '__main__':
    main()
