"""Run the one-case model lifecycle under gpu-idle, without Docker cleanup."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit

ROOT = Path('/srv/benchmark/skills')
sys.path.insert(0, str(ROOT / 'jobs'))
from saber_v10_model_specs import MODEL_SPECS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='gptoss', choices=[s['key'] for s in MODEL_SPECS])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--spec-file', type=Path)
    parser.add_argument('--harbor-launcher', type=Path, default=ROOT / 'projects/terminal-bench-aistation/harbor.sh')
    parser.add_argument('--formal', action='store_true', help='Score reward=0 and preserve per-trial infrastructure errors')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--pilot-config', type=Path)
    parser.add_argument('--deployment-gate', type=Path)
    args = parser.parse_args()
    specs = json.loads(args.spec_file.read_text()) if args.spec_file else MODEL_SPECS
    spec = deepcopy(next(s for s in specs if s['key'] == args.model))
    if os.environ.get('CUDA_VISIBLE_DEVICES') != ','.join(map(str, spec['gpus'])):
        raise RuntimeError('Exact gpu-idle reservation required')
    args.directory.mkdir(parents=True, exist_ok=False)
    procs = []
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for index, service in enumerate(spec['services']):
            # Dedicated terminal-bench ports; never adopt an existing model server.
            replacements = {'18004':'18104', '18005':'18105'} if args.model == 'gptoss' else {}
            argv = [a for a in service['argv']]
            for old, new in replacements.items():
                argv = [a.replace(old, new) for a in argv]
                service['health_url'] = service['health_url'].replace(old, new)
            port = urlsplit(service['health_url']).port
            with socket.socket() as sock:
                sock.bind(('0.0.0.0', port))
            env = dict(os.environ, **service.get('env', {}))
            env['SABER_RESPONSES_ERROR_DIR'] = str(args.directory / 'count-rejections')
            if service.get('prestart_argv'):
                subprocess.run(service['prestart_argv'], env=env, check=True, timeout=120)
            with (args.directory / (service['name'] + '.log')).open('x') as log:
                process = subprocess.Popen(argv, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            procs.append(process)
            print('Starting ' + service['name'], flush=True)
            deadline = time.monotonic() + service.get('ready_timeout', 900)
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Service exited: ' + service['name'])
                try:
                    with http.open(service['health_url'], timeout=3) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                time.sleep(2)
            else:
                raise TimeoutError(service['name'])
            print('Ready ' + service['name'], flush=True)
        if args.pilot_config:
            from validate_run import validate
            try:
                pilot_return = subprocess.run([str(args.harbor_launcher), 'run', '-c', str(args.pilot_config.resolve())]).returncode
                pilot = json.loads(args.pilot_config.read_text())
                report = validate(Path(pilot['jobs_dir']) / pilot['job_name'])
                report['harbor_returncode'] = pilot_return
                report['passed'] = report['passed'] and pilot_return == 0
            except Exception as exc:
                report = {'passed':False, 'reason':str(exc)}
            args.deployment_gate.write_text(json.dumps(report, indent=2))
        if args.deployment_gate:
            deadline = time.monotonic() + 2400
            while not args.deployment_gate.exists():
                if any(process.poll() is not None for process in procs):
                    raise RuntimeError('Service exited while waiting for full deployment pilot')
                if time.monotonic() > deadline:
                    raise TimeoutError('Waiting for GLM full-deployment pilot')
                time.sleep(2)
            if not json.loads(args.deployment_gate.read_text()).get('passed'):
                raise RuntimeError('Full-deployment pilot validation failed')
        result = subprocess.run([str(args.harbor_launcher),
            'run', '-c', str(args.config.resolve())])
        if result.returncode:
            raise RuntimeError('Harbor exited ' + str(result.returncode))
        config = json.loads(args.config.read_text())
        outcome_path = Path(config['jobs_dir']) / config['job_name'] / 'result.json'
        outcome = json.loads(outcome_path.read_text())
        stats = outcome['stats']
        if args.formal:
            (args.directory / 'evaluation-summary.json').write_text(json.dumps({
                'result':str(outcome_path), 'total':outcome['n_total_trials'],
                'completed':stats['n_completed_trials'], 'errors':stats['n_errored_trials'],
                'stats':stats, 'reward_zero_is_valid':True}, indent=2))
            if not outcome.get('finished_at') or stats.get('n_running_trials') or stats.get('n_pending_trials'):
                raise RuntimeError('Formal evaluation did not reach terminal state')
            return
        if stats['n_errored_trials'] or stats['n_completed_trials'] != outcome['n_total_trials']:
            raise RuntimeError('Harbor recorded an incomplete or errored trial')
        rewards = [float(value) for evaluation in stats['evals'].values()
                   for value, trials in evaluation.get('reward_stats', {}).get('reward', {}).items()
                   for _ in trials]
        if len(rewards) != outcome['n_total_trials'] or any(value != 1 for value in rewards):
            raise RuntimeError('Single-case validation did not pass all official tests; preserve results')

    finally:
        # Only process groups created by this exact lifecycle; no host Docker calls.
        for process in reversed(procs):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=15)
        (args.directory / 'lifecycle.json').write_text(json.dumps({
            'processes': [{'pid':p.pid,'returncode':p.returncode} for p in procs],
            'docker_resources_retained':True}, indent=2))


if __name__ == '__main__':
    main()
