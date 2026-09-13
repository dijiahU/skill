"""Validate all official shared-verifier images without GPU or cleanup."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import uuid
from harbor.models.task.task import Task
from harbor.models.task.verifier_mode import resolve_effective_verifier_env_config
from tb21_docker import project_image
from batch_docker import cache_image, direct_download_env
from aistation import host_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    root = args.directory
    request = json.loads((root / 'request.json').read_text())
    output = root / 'preflight'
    output.mkdir(exist_ok=True)
    outcomes = {}
    def check(name):
        path = Path(request['dataset']) / name
        log_path = output / (name + '.json')
        if log_path.exists():
            prior = json.loads(log_path.read_text())
            if prior.get('passed') and subprocess.run(['docker','image','inspect',prior['main']['image']],capture_output=True).returncode == 0:
                return prior
        item = {'task': name, 'at': datetime.now(timezone.utc).isoformat()}
        try:
            task = Task(path)
            assert resolve_effective_verifier_env_config(task.config, None) is None, 'Unexpected separate verifier'
            assert not task.config.environment.gpus, 'Task requires additional GPU'
            reference = task.config.environment.docker_image
            image = cache_image(reference)
            assert image == project_image(reference)
            container = 'rick-saber-tb21-probe-' + uuid.uuid4().hex[:12]
            probe = subprocess.run([
                'docker', 'run', '--runtime=runc', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                '--name', container, '--label', 'skilldistill.benchmark=terminal-bench-2.1',
                '--mount', 'type=bind,src=' + host_path('/srv/benchmark/skills/envs/uv-python/cpython-3.12.14-linux-x86_64-gnu') + ',dst=/opt/terminal-bench-observer-python,readonly',
                '--entrypoint', '/bin/sh', image, '-c',
                'command -v bash && /opt/terminal-bench-observer-python/bin/python3 -I -S -c "import json, pathlib, stat, os"'
            ], capture_output=True, text=True, timeout=60, env=direct_download_env())
            item['main'] = {'image':image, 'upstream':reference, 'container':container,
                            'exit_code':probe.returncode, 'stdout':probe.stdout, 'stderr':probe.stderr}
            if probe.returncode:
                raise RuntimeError('Bash/observer probe failed')
            item.update(passed=True, verifier_mode='shared', official_agent_timeout=task.config.agent.timeout_sec)
        except Exception as exc:
            item.update(passed=False, error_type=type(exc).__name__, error=str(exc))
        (output / (name + '-attempt-' + uuid.uuid4().hex[:8] + '.json')).write_text(json.dumps(item, indent=2))
        log_path.write_text(json.dumps(item, indent=2))
        return item
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(check, name):name for name in request['tasks']}
        for future in as_completed(futures):
            name = futures[future]
            item = future.result()
            outcomes[name] = item
            passed = sorted(k for k,v in outcomes.items() if v.get('passed'))
            pending = sorted(set(request['tasks']) - set(passed))
            (root / 'environment-readiness.json').write_text(json.dumps({'passed':passed,'pending':pending,'evidence':outcomes}, indent=2))
            print(name, 'PASS' if item['passed'] else item.get('error'), len(passed), '/', len(request['tasks']), flush=True)
    (output / 'result.json').write_text(json.dumps(outcomes, indent=2))
    return 0 if all(v['passed'] for v in outcomes.values()) else 1

if __name__ == '__main__':
    raise SystemExit(main())
