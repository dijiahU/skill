"""Verify skills integration on scored tasks, then consume the remaining tasks."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from openai import OpenAI
import httpx

JOB = Path(__file__).resolve().parent
OJ = Path('/srv/benchmark/skills/jobs/oas-api222-20260912-r1/skills100')
sys.path.insert(0, str(OJ))
from resume_helpers import valid, read_stage, balance_error
from stage_cleanup import cleanup_stage
from lifecycle import save


def protocol_probe(arm):
    client = OpenAI(api_key='EMPTY', base_url=os.environ['GPTOSS_BASE_URL'], timeout=240, max_retries=0, http_client=httpx.Client(trust_env=False))
    tool = {'type': 'function', 'name': 'probe_echo', 'description': 'Echo a probe value.',
            'parameters': {'type': 'object', 'properties': {'value': {'type': 'string'}},
                           'required': ['value'], 'additionalProperties': False}}
    history = [{'role': 'user', 'content': 'Call probe_echo once with value OK.'}]
    def complete(**kwargs):
        with client.responses.create(model='OpenAI-Mirror/gpt-oss-120b', max_output_tokens=2048,
                                     stream=True, **kwargs) as stream:
            for event in stream:
                if event.type in ['error', 'response.failed']:
                    raise RuntimeError('Responses protocol error')
                if event.type == 'response.completed':
                    return event.response
        raise RuntimeError('No completed Responses event')
    first = complete(input=history, tools=[tool], tool_choice='auto')
    calls = [x for x in first.output if x.type == 'function_call']
    assert len(calls) == 1 and calls[0].name == 'probe_echo'
    assert json.loads(calls[0].arguments)['value'] == 'OK'
    followup = history + [x.model_dump(exclude_none=True) for x in first.output]
    followup += [{'type': 'function_call_output', 'call_id': calls[0].call_id, 'output': 'OK'}]
    second = complete(input=followup, tools=[], tool_choice='auto')
    assert second.output_text.strip()
    save(JOB / 'preflight' / f'{arm}-protocol.json', {
        'passed': True, 'streaming_completed': True, 'tool_roundtrip': True,
        'usage': [x.usage.model_dump() if x.usage else None for x in [first, second]],
        'checked_at': time.time()})


def terminal_rows(directory):
    found = []
    for p in directory.glob('*/result.json'):
        try:
            row = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        meta = p.parent / 'agent/native-metadata.json'
        found.append((row, json.loads(meta.read_text()) if meta.exists() else {}))
    return found


def terminal_summary(directory):
    rows = terminal_rows(directory)
    good = [r for r, _ in rows if not r.get('exception_info') and
            isinstance(((r.get('verifier_result') or {}).get('rewards') or {}).get('reward'), (int, float))]
    return {'returned': len(rows), 'valid': len(good), 'passed': sum(r['verifier_result']['rewards']['reward'] == 1 for r in good),
            'errors': len(rows) - len(good)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--arm', choices=['oas', 'terminal'], required=True)
    arm = parser.parse_args().arm
    plan = json.loads((JOB / f'{arm}-plan.json').read_text())
    path = JOB / f'state-{arm}.json'
    if path.exists():
        old = json.loads(path.read_text())
        if os.environ.get('GPTOSS_RETRY_SETUP') != '1' or old.get('stages') or old.get('current_stage'):
            raise RuntimeError('Duplicate controller submission')
        save(JOB / f'state-{arm}-setup-failure-{int(time.time())}.json', old)
    lock = (JOB / f'controller-{arm}.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    model_lock = None
    if arm == 'oas':
        model_lock = (OJ / 'repair-gptoss.lock').open('a')
        fcntl.flock(model_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = {'arm': arm, 'model': 'OpenAI-Mirror/gpt-oss-120b', 'condition': 'skills',
             'status': 'checking local Responses protocol', 'stages': [], 'planned_tasks': 184 if arm == 'oas' else 89}
    child = None
    current_stage = None
    def persist():
        state['updated_at'] = time.time()
        save(path, state)
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    persist()
    try:
        protocol_probe(arm)
        tasks = plan['task_ids'] if arm == 'oas' else plan['tasks']
        smoke = plan['smoke_tasks']
        for phase, selection in [('smoke', smoke), ('full', [t for t in tasks if t not in smoke])]:
            workers = 2 if phase == 'smoke' else 8 if arm == 'oas' else 4
            if arm == 'oas':
                hold = json.loads((OJ / 'hold-next-models.json').read_text())
                if hold.get('active', True):
                    state['status'] = 'paused by provider hold; NPC needs balance'
                    persist()
                    return
                current_stage = f'skills100-gptoss-local-20260913-r1-{phase}'
                directory = Path(plan['results_root']) / current_stage
                selected_path = JOB / f'oas-{phase}.txt'
                if selected_path.exists() or directory.exists():
                    raise RuntimeError('Refusing duplicate OAS stage')
                selected_path.write_text('\n'.join(selection) + '\n')
                argv = [str(JOB / 'oas-run.sh'), '--model', 'gptoss', '--workers', str(workers),
                        '--select', str(selected_path), '--stage', current_stage]
            else:
                current_stage = f'rick-saber-tbgptoss-20260913-r1-{phase}'
                directory = Path(plan['results_root']) / current_stage
                cfg = JOB / 'configs' / f'terminal-{phase}.json'
                if directory.exists() or cfg.exists():
                    raise RuntimeError('Refusing duplicate Terminal phase')
                save(cfg, {'job_name': current_stage, 'jobs_dir': plan['results_root'], 'n_attempts': 1,
                    'n_concurrent_trials': workers, 'retry': {'max_retries': 0}, 'environment_build_timeout_multiplier': 3,
                    'environment': {'import_path': 'tb21_docker:TB21Docker', 'delete': False},
                    'datasets': [{'path': plan['dataset'], 'task_names': selection}],
                    'agents': [{'import_path': 'full_agent:FullSafetyCodex', 'model_name': state['model'],
                        'kwargs': {'base_url': os.environ['GPTOSS_BASE_URL'], 'safety_bundle': str(JOB / 'frozen/safety-bundle'),
                                   'treatment': True, 'max_steps': 1000, 'timeout_seconds': 12000,
                                   'require_deployment_activity': False, 'context_window': 32768}}]})
                argv = [str(JOB / 'harbor.sh'), 'run', '--config', str(cfg)]
            state.update(status='running ' + phase, current_stage=current_stage, current_results=str(directory),
                         tasks_this_stage=len(selection), workers=workers)
            with (JOB / 'logs' / f'{arm}-{phase}.log').open('x') as log:
                child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            state['runner_pid'] = child.pid
            if arm == 'oas':
                save(OJ / 'active-stage-gptoss.json', {'model': 'gptoss', 'pid': child.pid,
                    'stage': current_stage, 'workers': workers, 'tasks': selection, 'started': time.time()})
            persist()
            while child.poll() is None:
                if arm == 'oas':
                    rows = read_stage('gptoss', current_stage)
                    good = [r for r in rows.values() if valid(r)]
                    state['progress'] = {'returned': len(rows), 'valid': len(good),
                        'points': sum(r['test_result']['final_score']['result'] for r in good)}
                    if any(balance_error(r) for r in rows.values()):
                        raise RuntimeError('NPC provider balance exhausted')
                else:
                    state['progress'] = terminal_summary(directory)
                persist()
                time.sleep(10)
            rc = child.returncode
            if arm == 'oas':
                rows = read_stage('gptoss', current_stage)
                good = [r for r in rows.values() if valid(r)]
                summary = {'returned': len(rows), 'valid': len(good),
                           'points': sum(r['test_result']['final_score']['result'] for r in good)}
            else:
                summary = terminal_summary(directory)
            state['stages'].append({'stage': current_stage, 'returncode': rc, **summary})
            if phase == 'smoke':
                evidence = []
                if arm == 'oas':
                    for r in rows.values():
                        sk = (r.get('test_result') or {}).get('skilldistill') or {}
                        ok = valid(r) and sk.get('hooks_enabled') is True and 'safety-router-skill' in (sk.get('loaded_skills') or []) and 'safety-router-skill' in (sk.get('invoked_skills') or []) and (sk.get('audit') or {}).get('jsonl_files', 0) > 0
                        evidence.append({'task': r['instance_id'], 'passed': ok,
                                         'score': (r.get('test_result') or {}).get('final_score'), 'audit': sk.get('audit')})
                    batch_ok = len(evidence) == 2 and all(e['passed'] for e in evidence)
                else:
                    for r, meta in terminal_rows(directory):
                        score = ((r.get('verifier_result') or {}).get('rewards') or {}).get('reward')
                        ok = not r.get('exception_info') and isinstance(score, (int, float)) and meta.get('router_preloaded') is True and meta.get('hooks_listed') is True and meta.get('auth_copied') is False and meta.get('hook_runs', 0) > 0 and not meta.get('upstream_turn_error') and meta.get('turn_status') == 'completed' and meta.get('model_final_present') is True and (meta.get('tool_calls', 0) > 0 or meta.get('manual_hook_blocks', 0) > 0)
                        evidence.append({'task': r['task_name'], 'passed': ok, 'score': score,
                                         'tool_calls': meta.get('tool_calls', 0), 'hook_runs': meta.get('hook_runs', 0)})
                    batch_ok = len(evidence) == 2 and all(e['passed'] for e in evidence) and any(e['tool_calls'] > 0 for e in evidence)
                save(JOB / 'preflight' / f'{arm}-smoke.json', {'passed': batch_ok, 'evidence': evidence})
                if rc != 0 or not batch_ok:
                    state['status'] = 'paused: incomplete skills integration; results retained'
                    persist()
                    return
            elif rc != 0:
                state['status'] = 'batch ended with runner errors; inspect results'
                persist()
                return
            persist()
        state['status'] = 'all tasks attempted; inspect scores and unresolved tasks'
        persist()
    except Exception as exc:
        state.update(status='controller error; artifacts retained', error_type=type(exc).__name__, error=str(exc))
        persist()
        raise
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=40)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=15)
            if arm == 'oas' and current_stage:
                cleanup_stage(current_stage)


if __name__ == '__main__':
    main()
