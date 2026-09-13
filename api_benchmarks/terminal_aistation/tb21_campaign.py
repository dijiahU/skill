"""Single submitted TB 2.1 full-deployment campaign; gate, reserve, run, retain."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def read(path):
    return json.loads(Path(path).read_text())


def image_ready(root, tasks):
    ready = root / 'environment-readiness.json'
    if not ready.exists():
        return False
    try:
        return set(read(ready).get('passed', [])) == set(tasks)
    except ValueError:
        return False


def alive(identity):
    try:
        stat = (Path('/proc') / str(identity['pid']) / 'stat').read_text().rsplit(')', 1)[1].split()
        return stat[0] != 'Z' and stat[19] == identity['start_ticks']
    except FileNotFoundError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    root = parser.parse_args().directory.resolve()
    request = read(root / 'request.json')
    def status(state, **extra):
        staging = root / 'status.pending.json'
        staging.write_text(json.dumps({'state': state, 'at': datetime.now(timezone.utc).isoformat(), **extra}, indent=2))
        staging.replace(root / 'status.json')
    with (root / 'campaign.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (root / 'model-dispatch-started.json').exists():
            raise RuntimeError('Already dispatched; duplicate trials are prohibited')
        try:
            for filename, expected in read(root / 'source-sha256.json').items():
                if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != expected:
                    raise RuntimeError('Frozen input changed: ' + filename)
            if not read(root / 'installation-validation.json')['passed']:
                raise RuntimeError('Full installation gate failed')
            oracle_config = read(root / 'pilot-oracle.json')
            oracle = read(Path(oracle_config['jobs_dir']) / oracle_config['job_name'] / 'result.json')
            stats = oracle['stats']
            rewards = [float(r) for e in stats['evals'].values() for r, trials in e.get('reward_stats', {}).get('reward', {}).items() for _ in trials]
            if not oracle.get('finished_at') or stats['n_errored_trials'] or rewards != [1.0]:
                raise RuntimeError('Official TB 2.1 oracle gate failed')
            # Wait for the already submitted cache population, then retry failures only.
            preflight = read(root / 'preflight-process.json')
            while alive(preflight):
                status('queued_preparing_environments', ready=len(read(root / 'environment-readiness.json').get('passed', [])), total=len(request['tasks']))
                time.sleep(10)
            for attempt in range(1, 3):
                if image_ready(root, request['tasks']):
                    break
                status('retrying_environment_downloads', attempt=attempt)
                with (root / f'preflight-retry-{attempt}.log').open('x') as log:
                    subprocess.run([sys.executable, str(Path(__file__).with_name('tb21_preflight.py')), str(root)], stdout=log, stderr=subprocess.STDOUT)
            if not image_ready(root, request['tasks']):
                status('blocked_by_environment_failures', readiness=str(root / 'environment-readiness.json'))
                return
            pilot_gate = root / 'full-deployment-validation.json'
            deadline = time.monotonic() + 3600
            while not pilot_gate.exists():
                status('waiting_for_full_deployment_pilot')
                if time.monotonic() > deadline:
                    raise TimeoutError('Full-deployment pilot did not finish')
                time.sleep(5)
            if not read(pilot_gate).get('passed'):
                raise RuntimeError('Full-deployment pilot did not pass')
            # Recheck frozen inputs after potentially lengthy downloads.
            for filename, expected in read(root / 'source-sha256.json').items():
                if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != expected:
                    raise RuntimeError('Frozen input changed while queued: ' + filename)
            (root / 'model-dispatch-started.json').write_text(json.dumps({'planned_trials':request['planned_trials'], 'at':datetime.now(timezone.utc).isoformat()}, indent=2))
            outcomes = {}
            summaries = {}
            def launch(model):
                spec = request['models'][model]
                argv = ['/srv/benchmark/skills/bin/gpu-idle', 'run', '--gpus', ','.join(map(str, spec['gpus'])), '--timeout', '604800', '--', 'bash', spec['script']]
                with (root / (model + '-admission.log')).open('x') as log:
                    return subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT).returncode
            for wave in request['waves']:
                status('waiting_or_running_models', wave=wave, outcomes=outcomes)
                with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                    futures = {pool.submit(launch, model): model for model in wave}
                    for future in as_completed(futures):
                        model = futures[future]
                        outcomes[model] = future.result()
                        (root / 'model-completion.json').write_text(json.dumps(outcomes, indent=2))
                failed_services = []
                for model in wave:
                    path = root / (model + '-service/evaluation-summary.json')
                    if outcomes[model] or not path.exists():
                        failed_services.append(model)
                    else:
                        summaries[model] = read(path)
                (root / 'evaluation-summary.json').write_text(json.dumps(summaries, indent=2))
                if failed_services:
                    status('blocked_by_model_service_failure', models=failed_services, outcomes=outcomes)
                    return
            errors = sum(v.get('errors', 0) for v in summaries.values())
            status('completed_with_trial_errors' if errors else 'completed', outcomes=outcomes, errors=errors)
        except Exception as exc:
            status('failed', error_type=type(exc).__name__, reason=str(exc))
            raise


if __name__ == '__main__':
    main()
