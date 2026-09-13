"""Clean only containers in an explicitly authorized OAS stage."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import time

JOB = Path(__file__).resolve().parent
REAL = '/srv/benchmark/skills/bin/docker'
GUARD = str(JOB / 'bin/docker')
LABEL = 'skilldistill.oas.api_run=oas-api222-20260912-r1'
PREFIX = 'rick-oas-api222-20260912-r1-'


def cleanup_stage(stage):
    def listed():
        p = subprocess.run([REAL, 'ps', '-a', '--filter', 'label=' + LABEL,
                            '--filter', 'label=skilldistill.oas.stage=' + stage,
                            '--format', '{{.ID}}'], capture_output=True, text=True, timeout=20, check=True)
        return p.stdout.split()
    def clean(cid):
        try:
            p = subprocess.run([REAL, 'inspect', cid], capture_output=True, text=True, timeout=20)
            if p.returncode:
                return {'id': cid, 'status': 'already absent'}
            info = json.loads(p.stdout)[0]
            labels = info.get('Config', {}).get('Labels', {}) or {}
            if (not info['Name'].lstrip('/').startswith(PREFIX)
                    or labels.get('skilldistill.oas.api_run') != 'oas-api222-20260912-r1'
                    or labels.get('skilldistill.oas.stage') != stage):
                return {'id': cid, 'status': 'ownership mismatch; untouched'}
            if info.get('State', {}).get('Running'):
                subprocess.run([GUARD, 'stop', '--time', '10', cid], capture_output=True, text=True, timeout=35)
            p = subprocess.run([REAL, 'inspect', cid], capture_output=True, text=True, timeout=20)
            if not p.returncode:
                result = subprocess.run([GUARD, 'rm', cid], capture_output=True, text=True, timeout=25)
                return {'id': cid, 'status': 'removed' if result.returncode == 0 else 'retry required'}
            return {'id': cid, 'status': 'removed automatically'}
        except Exception as exc:
            return {'id': cid, 'status': 'retry required', 'error_type': type(exc).__name__}
    attempts = []
    for _ in range(3):
        ids = listed()
        if not ids:
            break
        with ThreadPoolExecutor(8) as pool:
            attempts.extend(pool.map(clean, ids))
    remaining = listed()
    result = {'stage': stage, 'checked_at': time.time(), 'actions': attempts, 'remaining': remaining}
    (JOB / ('cleanup-' + stage + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    if remaining:
        raise RuntimeError('Owned stage containers remain; inspect cleanup report')
    return result
