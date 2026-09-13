"""Execute frozen evaluation waves after evidence-backed integration gates."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time


def write(path, value):
    path.write_text(json.dumps(value, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    request = json.loads((directory / 'formal-request.json').read_text())
    with (directory / 'formal.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (directory / 'formal-dispatch-started.json').exists():
            raise RuntimeError('Already dispatched; no automatic duplicate trials')
        def status(state, **details):
            write(directory / 'formal-status.json', {
                'state':state, 'updated_at':datetime.now(timezone.utc).isoformat(), **details})
        try:
            deadline = time.monotonic() + 3600
            while True:
                outcome_path = Path(request['oracle_job']) / 'result.json'
                outcome = json.loads(outcome_path.read_text()) if outcome_path.exists() else {}
                if outcome.get('finished_at'):
                    stats = outcome['stats']
                    rewards = [float(value) for item in stats['evals'].values()
                               for value in item.get('reward_stats', {}).get('reward', {})]
                    if stats['n_errored_trials'] or stats['n_completed_trials'] != 1 or rewards != [1.0]:
                        raise RuntimeError('Native oracle gate failed: ' + str(outcome_path))
                    break
                status('validating_native_oracle', oracle=str(outcome_path))
                if time.monotonic() > deadline:
                    raise TimeoutError('Native oracle validation')
                time.sleep(15)
            from validate_run import validate
            deployment = validate(Path(request['deployment_job']))
            write(directory / 'formal-deployment-validation.json', deployment)
            if not deployment['passed']:
                raise RuntimeError('Full hooks and skills gate failed')
            for name, expected in json.loads((directory / 'frozen-sha256.json').read_text()).items():
                if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
                    raise RuntimeError('Frozen input changed: ' + name)
            with (directory / 'formal-dispatch-started.json').open('x') as stream:
                json.dump({'at':datetime.now(timezone.utc).isoformat(), 'planned_trials':630}, stream)
            outcomes = {}
            def launch(model):
                spec = request['models'][model]
                argv = ['/srv/benchmark/skills/bin/gpu-idle','run','--gpus',
                        ','.join(map(str,spec['gpus'])),'--timeout','604800','--',
                        'bash',spec['script']]
                with (directory / ('formal-' + model + '-admission.log')).open('x') as log:
                    return subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT).returncode
            for wave in request['waves']:
                status('waiting_or_running_formal_wave', wave=wave, outcomes=outcomes)
                with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                    futures = {pool.submit(launch, model):model for model in wave}
                    for future in as_completed(futures):
                        outcomes[futures[future]] = future.result()
                        write(directory / 'model-completion.json', outcomes)
                        status('waiting_or_running_formal_wave', wave=wave, outcomes=outcomes)
            summaries = {}
            for model in request['models']:
                path = directory / ('formal-' + model + '-service') / 'evaluation-summary.json'
                summaries[model] = json.loads(path.read_text()) if path.exists() else {'missing_summary':True}
            errors = any(outcomes.values()) or any(s.get('errors',0) or s.get('missing_summary') for s in summaries.values())
            write(directory / 'formal-summary.json', summaries)
            status('completed_with_errors' if errors else 'completed', outcomes=outcomes)
        except Exception as exc:
            status('failed', reason=str(exc))
            raise


if __name__ == '__main__':
    main()
