"""Preflight or run three API-backed SABER models concurrently."""
import argparse
import concurrent.futures
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
from openai import OpenAI
from api_benchmarks.bridge_process import chat_bridge

JOB = Path(__file__).resolve().parent
ROOT = Path('/srv/benchmark/skills/projects/skill-api-20260912')
PYTHON = '/srv/benchmark/skills/envs/api-saber-20260912/bin/python'
PLAN = json.loads((JOB / 'plan.json').read_text())


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')
    path.chmod(0o600)


def run_model(name, definition, preflight):
    output = JOB / 'logs' / name
    output.mkdir(exist_ok=True)
    state = {'model': definition['id'], 'status': 'preflight', 'shards': []}
    state_path = output / ('preflight.json' if preflight else 'state.json')
    save(state_path, state)
    env = dict(os.environ)
    slug = 'saber-foreign-' + name + '-20260912-r1'
    with ExitStack() as stack:
        key = os.environ[definition['key_env']]
        url = PLAN['base_url']
        if definition['bridge']:
            bridge_env = dict(env, BRIDGE_MAX_OUTPUT_TOKENS='8192', BRIDGE_ADVERTISE_HOST='127.0.0.1')
            bridge = stack.enter_context(chat_bridge(
                bridge_env, {'id': definition['id'], 'base_url': url, 'key': key},
                '/srv/benchmark/skills/envs/api-harbor-20260912/bin/python', ROOT, output))
            key = bridge['OPENAI_API_KEY']
            url = bridge['BRIDGE_LOCAL_BASE_URL']
        env['RESPONSES_API_KEY'] = key
        cfg = {'max_steps': 100, 'models': {slug: {
            'id': definition['id'], 'type': 'codex-native', 'base_url': url,
            'key_env': 'RESPONSES_API_KEY', 'copy_codex_auth': False,
            'preload_skill_references': False, 'timeout_seconds': 3600}}}
        config = JOB / 'configs' / (name + ('-preflight' if preflight else '-run') + '.json')
        save(config, cfg)
        started = time.monotonic()
        client = OpenAI(api_key=key, base_url=url, timeout=120, max_retries=0)
        event_types = set()
        with client.responses.create(model=definition['id'], input=[{'role': 'user', 'content': 'Reply OK.'}], max_output_tokens=512, stream=True) as events:
            for event in events:
                event_types.add(event.type)
                if event.type in ('response.failed', 'error'):
                    raise RuntimeError('Responses API returned failure event')
        if 'response.completed' not in event_types:
            raise RuntimeError('Responses stream did not complete')
        state['api_probe'] = {'completed': True, 'seconds': round(time.monotonic() - started, 2), 'event_types': sorted(event_types)}
        save(state_path, state)
        base = [PYTHON, str(JOB / 'worker.py'), '--model', slug, '--config', str(config)]
        with (output / 'preflight.log').open('a') as log:
            check = subprocess.run(base + ['--preflight'], env=env, cwd=ROOT / 'saber', stdout=log, stderr=subprocess.STDOUT, timeout=180)
        state['preflight_returncode'] = check.returncode
        if check.returncode != 0:
            state['status'] = 'preflight failed; inspect preflight.log'
            save(state_path, state)
            return state
        if preflight:
            state['status'] = 'preflight passed; no task containers created'
            save(state_path, state)
            return state
        state['status'] = 'running 8 shards'
        save(state_path, state)
        processes = []
        for shard in range(8):
            log = stack.enter_context((output / ('shard-%02d.log' % shard)).open('a'))
            process = subprocess.Popen(base + ['--shard', str(JOB / 'shards' / ('%02d.json' % shard))], env=env, cwd=ROOT / 'saber', stdout=log, stderr=subprocess.STDOUT)
            processes.append((shard, process))
        for shard, process in processes:
            state['shards'].append({'shard': shard, 'returncode': process.wait()})
            save(state_path, state)
        if not all(shard['returncode'] == 0 for shard in state['shards']):
            state['status'] = 'some shards failed; preserve results'
            save(state_path, state)
            return state
        state['status'] = 'judging'
        save(state_path, state)
        judge = PLAN['judge']
        judge_env = dict(env, OSBENCH_JUDGE_MODEL=judge['model'], OSBENCH_JUDGE_TYPE=judge['provider'],
                         OSBENCH_JUDGE_BASE_URL=judge['base_url'], OSBENCH_JUDGE_KEY=os.environ[judge['key_env']],
                         SABER_JUDGED_OUTPUT_ROOT=PLAN['results_root'] + '/judged')
        with (output / 'judge.log').open('a') as log:
            judged = subprocess.run([PYTHON, str(JOB / 'judge_worker.py'), slug + '_codex-native-safety-orchestrator'],
                                    cwd=ROOT / 'saber', env=judge_env, stdout=log, stderr=subprocess.STDOUT)
        state['judge_returncode'] = judged.returncode
        state['status'] = 'inference and judging finished' if judged.returncode == 0 else 'judge failed; inference results retained'
        save(state_path, state)
        return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    lock = (JOB / ('preflight.lock' if args.preflight else 'run.lock')).open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if not args.preflight:
        approval = JOB / 'lifecycle-approval.json'
        if not approval.exists():
            raise RuntimeError('Awaiting explicit approval for the new SABER container lifecycle')
        identity = json.loads(approval.read_text())
        if any(identity.get(k) != PLAN[k] for k in ('container_prefix', 'container_labels')):
            raise RuntimeError('Lifecycle approval does not match this batch')
    result = {}
    with concurrent.futures.ThreadPoolExecutor(3) as pool:
        futures = {pool.submit(run_model, name, definition, args.preflight): name for name, definition in PLAN['models'].items()}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                result[name] = future.result()
            except Exception as exc:
                result[name] = {'status': 'failed', 'error_type': type(exc).__name__, 'status_code': getattr(exc, 'status_code', None)}
            save(JOB / ('preflight-summary.json' if args.preflight else 'run-summary.json'), result)
            print(json.dumps({name: result[name]}), flush=True)

if __name__ == '__main__':
    main()
