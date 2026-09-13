"""Finish the active wave, then recover rate-limited tasks at lower concurrency."""
import fcntl
import json
from pathlib import Path
import time

from resume_helpers import JOB, RESULTS, read_stage, valid, probe
from resume_after_recharge import PLAN, merged, run_stage, write


def unresolved(model, only_rate=False):
    _, summary = merged(model)
    stages = {stage: read_stage(model, stage) for stage in set(summary['selected_attempts'].values())}
    todo, blocked_evaluators = [], []
    for task in (JOB / 'tasks222.txt').read_text().splitlines():
        stage = summary['selected_attempts'].get(task)
        row = stages.get(stage, {}).get(task)
        if row is None:
            if not only_rate:
                todo.append(task)
            continue
        if valid(row):
            continue
        test = row.get('test_result') or {}
        skill = test.get('skilldistill') or {}
        error = str(row.get('error') or test.get('error') or '')
        if not skill.get('graded_from_partial_trajectory') and ('Evaluator' in error or 'Evaluation failed' in error):
            blocked_evaluators.append(task)
            continue
        if only_rate:
            reason = str(skill.get('conversation_error') or '')
            rate = 'RateLimitError' in reason or 'TPM limit reached' in reason
            if not rate and stage:
                for log in (RESULTS / model / stage).rglob('instance_' + task + '.output.log'):
                    text = log.read_text(errors='replace')
                    if 'LLMRateLimitError' in text or 'TPM limit reached' in text:
                        rate = True
                        break
            if not rate:
                continue
        todo.append(task)
    return todo, blocked_evaluators


def main():
    own = (JOB / 'rate-recovery.lock').open('a')
    fcntl.flock(own, fcntl.LOCK_EX | fcntl.LOCK_NB)
    lock = (JOB / 'queue.lock').open('a')
    state = {'status': 'waiting for active GLM128 wave to finish', 'max_iterations': 100,
             'skill_mode': 'safety-orchestrator', 'npc_model': 'deepseek-flash', 'stages': [],
             'worker_levels': {'glm5': [32, 16, 8]}}
    write(JOB / 'rate-recovery-state.json', state)
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            time.sleep(10)
    health = probe(PLAN['models']['glm5'])
    if health.get('balance_exhausted'):
        state['status'] = 'balance exhausted; queue remains held'
        write(JOB / 'rate-recovery-state.json', state)
        return
    hold_path = JOB / 'hold-next-models.json'
    hold = json.loads(hold_path.read_text())
    hold.update(active=False, resolved_by='rate recovery controller now owns queue; lower-concurrency retries enabled')
    write(hold_path, hold)
    def save():
        write(JOB / 'rate-recovery-state.json', state)
        write(JOB / 'queue-state.json', state)
    for model, levels in state['worker_levels'].items():
        for index, workers in enumerate(levels):
            todo, blocked = unresolved(model, only_rate=index > 0)
            state['evaluator_tasks_held_' + model] = blocked
            if not todo:
                break
            state['status'] = 'running ' + model + ' rate recovery at ' + str(workers)
            save()
            stage = 'skills100-' + model + '-rate1-w' + str(workers)
            result = run_stage(model, todo, stage, workers=workers)
            state['stages'].append(result)
            save()
            if result['returncode'] != 0:
                state['status'] = 'paused after runner/provider error; valid results retained'
                save()
                return
        _, summary = merged(model)
        state['result_' + model] = {k: v for k, v in summary.items() if k != 'selected_attempts'}
        save()
    state['status'] = 'bounded rate recovery finished; review unresolved non-rate errors separately'
    save()


if __name__ == '__main__':
    main()
