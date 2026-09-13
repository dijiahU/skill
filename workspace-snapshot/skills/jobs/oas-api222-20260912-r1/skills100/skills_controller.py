"""Run skills treatment with a common budget and distinct per-model results."""
import fcntl
import json
from pathlib import Path
from capacity import run_stage, results

JOB = Path(__file__).resolve().parent


def main():
    lock = (JOB / 'queue.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    ids = (JOB / 'tasks222.txt').read_text().splitlines()
    smoke = (JOB / 'smoke.txt').read_text().splitlines()
    state = {'status': 'running integration check', 'models': ['glm5', 'deepseek-flash', 'qwen'],
             'workers': 128, 'max_iterations': 100, 'npc_model': 'deepseek-flash',
             'skill_mode': 'safety-orchestrator', 'stages': []}
    def save():
        (JOB / 'queue-state.json').write_text(json.dumps(state, indent=2) + '\n')
    save()
    stage = 'skills100-glm5-check'
    if (JOB / ('glm5-' + stage + '.txt')).exists():
        raise RuntimeError('Refusing duplicate integration stage')
    check = run_stage('glm5', 2, smoke, stage)
    state['stages'].append(check)
    rows = results('glm5', stage)
    evidence = []
    for row in rows:
        skill = (row.get('test_result') or {}).get('skilldistill') or {}
        evidence.append({'task': row['instance_id'], 'loaded': skill.get('loaded_skills'),
                         'invoked': skill.get('invoked_skills'), 'hooks_enabled': skill.get('hooks_enabled'),
                         'audit': skill.get('audit')})
    state['integration_evidence'] = evidence
    ready = check['ok'] and len(evidence) == 2 and all(
        e['loaded'] == ['safety-router-skill'] and e['hooks_enabled']
        and 'safety-router-skill' in (e['invoked'] or [])
        and (e['audit'] or {}).get('jsonl_files', 0) > 0 for e in evidence)
    if not ready:
        state['status'] = 'integration check needs diagnosis; large queue not started'
        save()
        return
    for model in state['models']:
        selected = [task for task in ids if model != 'glm5' or task not in smoke]
        assert len(set(selected)) == len(selected)
        stage = 'skills100-' + model + '-w128'
        if (JOB / (model + '-' + stage + '.txt')).exists():
            raise RuntimeError('Refusing duplicate model stage')
        state['status'] = 'running ' + model
        save()
        outcome = run_stage(model, 128, selected, stage)
        state['stages'].append(outcome)
        save()
        if outcome['returncode'] != 0 or len(outcome['valid_task_ids']) == 0:
            state['status'] = 'runner failure needs diagnosis; subsequent models remain queued'
            save()
            return
    state['status'] = 'all three models finished; inspect incomplete and evaluator errors separately'
    save()


if __name__ == '__main__':
    main()
