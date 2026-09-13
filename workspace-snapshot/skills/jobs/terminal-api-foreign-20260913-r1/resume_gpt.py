"""Continue GPT after accepting a fully graded safety-blocked smoke result."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
from controller import JOB, PLAN, config, records, save, summarize


def main():
    lock = (JOB / 'gpt.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state_path = JOB / 'state-gpt.json'
    state = json.loads(state_path.read_text())
    assert state['status'] == 'paused: smoke integration incomplete; artifacts retained'
    root = Path(state['current_results'])
    rows = records(root)
    assert len(rows) == 2
    evidence = []
    for path, row in rows:
        meta = json.loads((path.parent / 'agent/native-metadata.json').read_text())
        rewards = (row.get('verifier_result') or {}).get('rewards')
        assert not row.get('exception_info') and isinstance(rewards, dict) and rewards
        assert meta.get('router_preloaded') is True and meta.get('hooks_listed') is True
        assert meta.get('auth_copied') is False and meta.get('hook_runs', 0) > 0
        assert not meta.get('upstream_turn_error') and meta.get('model_final_present') is True
        assert meta.get('turn_status') == 'completed'
        assert meta.get('tool_calls', 0) > 0 or meta.get('manual_hook_blocks', 0) > 0
        evidence.append({'task': row['task_name'], 'rewards': rewards,
                         'tool_calls': meta.get('tool_calls'), 'hook_blocks': meta.get('manual_hook_blocks'),
                         'integration_valid': True})
    # One trial verifies real tool execution. A different, fully graded trial
    # may legitimately score zero because the unchanged safety hooks deny it.
    assert any(x['tool_calls'] > 0 for x in evidence)
    backup = JOB / 'state-gpt-before-smoke-review.json'
    assert not backup.exists()
    save(backup, state)
    save(JOB / 'preflight/gpt-smoke-reviewed.json', {
        'reason': 'Startup gate incorrectly required successful task tools in every trial',
        'scoring_and_hooks_unchanged': True, 'zero_reward_preserved': True, 'evidence': evidence})
    env = dict(os.environ, RESPONSES_API_KEY=os.environ['APINEBULA_GPT_API_KEY'])
    tasks = [t for t in PLAN['tasks'] if t not in PLAN['smoke_tasks']]
    cfg, directory = config('gpt', PLAN['models']['gpt'], PLAN['base_url'], 'full', tasks)
    state.update(status='running full', current_tasks=len(tasks), current_results=str(directory),
                 smoke_review='Valid safety-blocked zero score retained; batch tool integration verified')
    def persist():
        state['updated_at'] = time.time()
        save(state_path, state)
    with (JOB / 'logs/gpt-full.log').open('a') as log:
        process = subprocess.Popen([str(JOB / 'harbor.sh'), 'run', '--config', str(cfg)],
                                   env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        state['runner_pid'] = process.pid
        persist()
        while process.poll() is None:
            state['progress'] = summarize(directory)
            persist()
            time.sleep(15)
        state['phases'].append({'phase': 'full', 'returncode': process.returncode, **summarize(directory)})
    state['status'] = 'all 89 tasks attempted; inspect scores and errors' if process.returncode == 0 else 'batch ended with runner errors; artifacts retained'
    persist()


if __name__ == '__main__':
    main()
