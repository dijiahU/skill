"""Run two authorized API Terminal-Bench arms with retained Docker resources."""
import argparse
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
import sys
sys.path.insert(0, '/srv/benchmark/skills/projects/terminal-bench-aistation')
from verifier_integrity import assess_trial
from openai import OpenAI
from api_benchmarks.bridge_process import chat_bridge

JOB = Path(__file__).resolve().parent
PLAN = json.loads((JOB / 'plan.json').read_text())
RESULTS = Path(PLAN['results_root'])


def save(path, data):
    temporary = path.with_name(path.name + '.writing')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    os.replace(temporary, path)


def records(directory):
    rows = []
    for path in directory.glob('*/result.json'):
        try:
            rows.append((path, json.loads(path.read_text())))
        except json.JSONDecodeError:
            pass
    return rows


def summarize(directory):
    rows = records(directory)
    return {'returned': len(rows),
            'errors': sum(not assess_trial(path, row)['valid'] for path, row in rows),
            'scored': sum(assess_trial(path, row)['valid'] for path, row in rows)}


def config(model, definition, url, phase, tasks):
    name = f'rick-saber-tbapi-{model}-20260913-r1-{phase}'
    data = {'job_name': name, 'jobs_dir': str(RESULTS), 'n_attempts': 1,
            'n_concurrent_trials': 2 if phase == 'smoke' else PLAN['workers_per_model'],
            'retry': {'max_retries': 0}, 'environment_build_timeout_multiplier': 3,
            'environment': {'import_path': 'tb21_docker:TB21Docker', 'delete': False},
            'datasets': [{'path': PLAN['dataset'], 'task_names': tasks}],
            'agents': [{'import_path': 'full_agent:FullSafetyCodex', 'model_name': definition['id'],
                        'kwargs': {'base_url': url, 'safety_bundle': str(JOB / 'frozen/safety-bundle'),
                                   'treatment': True, 'max_steps': PLAN['max_task_tool_attempts'],
                                   'timeout_seconds': 12000, 'require_deployment_activity': False,
                                   'context_window': PLAN['context_window']}}]}
    path = JOB / 'configs' / f'{model}-{phase}.json'
    if path.exists() or (RESULTS / name).exists():
        raise RuntimeError('Refusing duplicate benchmark phase')
    save(path, data)
    return path, RESULTS / name


def smoke_evidence(directory):
    evidence = []
    for path, row in records(directory):
        meta_path = path.parent / 'agent/native-metadata.json'
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        rewards = (row.get('verifier_result') or {}).get('rewards')
        ok = (assess_trial(path, row)['valid']
              and meta.get('router_preloaded') is True and meta.get('hooks_listed') is True
              and meta.get('auth_copied') is False and meta.get('hook_runs', 0) > 0
              and (meta.get('tool_calls', 0) > 0 or meta.get('manual_hook_blocks', 0) > 0)
              and meta.get('turn_status') == 'completed' and meta.get('model_final_present') is True
              and not meta.get('upstream_turn_error'))
        evidence.append({'task': row['task_name'], 'passed_integration': ok,
                         'rewards': rewards, 'router_preloaded': meta.get('router_preloaded'),
                         'hook_runs': meta.get('hook_runs'), 'tool_calls': meta.get('tool_calls'),
                         'exception_type': (row.get('exception_info') or {}).get('exception_type')})
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['claude'], required=True)
    model = parser.parse_args().model
    lock = (JOB / f'{model}.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state_path = JOB / f'state-{model}.json'
    if state_path.exists():
        raise RuntimeError('Controller already submitted; use a new revision for retries')
    definition = PLAN['models'][model]
    state = {'model': definition['id'], 'status': 'checking API', 'phases': [],
             'planned_tasks': 89, 'condition': 'full_skills_and_hooks', 'controller_pid': os.getpid()}
    def persist():
        state['updated_at'] = time.time()
        save(state_path, state)
    persist()
    try:
        with ExitStack() as stack:
            env = dict(os.environ)
            key, url = env[definition['key_env']], PLAN['base_url']
            if definition['bridge']:
                bridge = stack.enter_context(chat_bridge(
                    dict(env, BRIDGE_MAX_OUTPUT_TOKENS='8192', BRIDGE_ADVERTISE_HOST='127.0.0.1'),
                    {'id': definition['id'], 'base_url': url, 'key': key},
                    '/srv/benchmark/skills/envs/api-harbor-20260912/bin/python', JOB / 'frozen', JOB / 'logs' / model))
                key, url = bridge['OPENAI_API_KEY'], bridge['BRIDGE_LOCAL_BASE_URL']
            env['RESPONSES_API_KEY'] = key
            client = OpenAI(api_key=key, base_url=url, timeout=120, max_retries=0)
            completed = False
            with client.responses.create(model=definition['id'], input=[{'role': 'user', 'content': 'Reply OK.'}],
                                         max_output_tokens=512, stream=True) as stream:
                for event in stream:
                    if event.type in ('response.failed', 'error'):
                        raise RuntimeError('API returned failed response')
                    if event.type == 'response.completed':
                        completed = True
                        usage = getattr(event.response, 'usage', None)
                        state['preflight_usage'] = usage.model_dump() if usage else None
                        break
            if not completed:
                raise RuntimeError('API did not complete')
            state['api_preflight_passed'] = True
            persist()
            for phase, tasks in [('smoke', PLAN['smoke_tasks']),
                                 ('full', [t for t in PLAN['tasks'] if t not in PLAN['smoke_tasks']])]:
                cfg, directory = config(model, definition, url, phase, tasks)
                state.update(status='running ' + phase, current_tasks=len(tasks), current_results=str(directory))
                persist()
                with (JOB / 'logs' / f'{model}-{phase}.log').open('a') as log:
                    process = subprocess.Popen([str(JOB / 'harbor.sh'), 'run', '--config', str(cfg)],
                                               env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    state['runner_pid'] = process.pid
                    persist()
                    while process.poll() is None:
                        state['progress'] = summarize(directory)
                        persist()
                        time.sleep(15)
                    state['phases'].append({'phase': phase, 'returncode': process.returncode, **summarize(directory)})
                if phase == 'smoke':
                    evidence = smoke_evidence(directory)
                    save(JOB / 'preflight' / f'{model}-smoke.json', evidence)
                    if (process.returncode != 0 or len(evidence) != 2
                            or not all(row['passed_integration'] for row in evidence)
                            or not any(row['tool_calls'] > 0 for row in evidence)):
                        state['status'] = 'paused: smoke integration incomplete; artifacts retained'
                        persist()
                        return
                elif process.returncode != 0:
                    state['status'] = 'batch ended with runner errors; artifacts retained'
                    persist()
                    return
            state['status'] = 'all 89 tasks attempted; inspect scores and errors'
            persist()
    except Exception as exc:
        state.update(status='paused after setup or provider error', error_type=type(exc).__name__,
                     http_status=getattr(exc, 'status_code', None))
        persist()
        raise


if __name__ == '__main__':
    main()
