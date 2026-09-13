#!/usr/bin/env python3
"""Restrict this OAS experiment to its labelled containers and pinned image."""
import json
import runpy
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/srv/benchmark/skills/jobs/oas-api222-20260912-r1')
REAL = '/srv/benchmark/skills/bin/docker'
SESSION = 'oas-api222-20260912-r1'
PREFIX = 'rick-' + SESSION + '-'
LABEL = 'skilldistill.oas.api_run'
IMAGE = 'skilldistill-openagentsafety-agent-server:aistation-20260831-reasoningfix-openagentsafety-oas-hooks-v1'
DIGEST = 'sha256:7504b5ce81b340aff74fdc945c385c838b43f70e2d7612d115ce03f9b479c2ac'
BASE_IMAGE = 'skilldistill-openagentsafety-agent-server:aistation-20260831-reasoningfix-openagentsafety'


def reject(message):
    print('OAS run guard: ' + message, file=sys.stderr)
    raise SystemExit(2)


def inspect(target):
    p = subprocess.run([REAL, 'inspect', target], capture_output=True, text=True)
    if p.returncode:
        reject('Cannot inspect target for ownership')
    return json.loads(p.stdout)[0]


def approved():
    p = ROOT / 'lifecycle-approval.json'
    if not p.exists() or json.loads(p.read_text()).get('session') != SESSION:
        reject('This session requires explicit container lifecycle authorization')


def main():
    args = sys.argv[1:]
    if not args:
        reject('Missing Docker operation')
    op = args[0]
    if op == 'run':
        approved()
        stage = os.environ.get('OAS_STAGE', 'unknown')
        if (Path(__file__).resolve().parents[1] / ('stop-' + stage + '.json')).exists():
            reject('Stage admission stopped by provider circuit breaker')
        if '--name' not in args:
            reject('Only named OAS containers are permitted')
        name_index = args.index('--name') + 1
        name = args[name_index]
        grader = name.startswith('skilldistill-oas-grader-')
        if grader:
            required = {'--network': 'none', '--runtime': 'runc', '--entrypoint': 'python'}
            if any(flag not in args or args[args.index(flag) + 1] != value
                   for flag, value in required.items()) or '--read-only' not in args or '--rm' not in args:
                reject('Fallback grader must remain read-only, disposable, and offline')
            if BASE_IMAGE in args:
                args[args.index(BASE_IMAGE)] = IMAGE
        elif '-d' not in args and '--detach' not in args:
            reject('Agent admission requires detached Docker startup')
        if IMAGE not in args:
            reject('Only the pinned OAS image is permitted')
        if not name.startswith(('skilldistill-oas-agent-', 'skilldistill-oas-grader-')):
            reject('Unexpected container name')
        info = inspect(IMAGE)
        if info['Id'] != DIGEST:
            reject('Pinned image tag changed')
        args[name_index] = PREFIX + name
        extra = ['--label', LABEL + '=' + SESSION,
                 '--label', 'skilldistill.oas.stage=' + os.environ.get('OAS_STAGE', 'unknown')]
        extra += ['-e', 'LITELLM_LOCAL_MODEL_COST_MAP=True']
        if '--memory' not in args:
            cpu = os.environ.get('OAS_CONTAINER_CPUS', '1')
            if cpu not in ('0.25', '1'):
                reject('Unexpected CPU limit')
            extra += ['--memory', '2g', '--cpus', cpu, '--pids-limit', '512']
        args[1:1] = extra
        capacity_module = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'capacity_admission.py'))
        raise SystemExit(capacity_module['run_bounded'](args, grader=grader))
    elif op in ('stop', 'rm'):
        approved()
        if op == 'stop' and (len(args) != 4 or args[1:3] != ['--time', '10']):
            reject('Only bounded single-container stop is permitted')
        if op == 'rm' and len(args) != 2:
            reject('Only non-forced single-container removal is permitted')
        obj = inspect(args[-1])
        if op == 'rm' and obj.get('State', {}).get('Running'):
            reject('Stop an owned container before removing it')
        if not obj['Name'].lstrip('/').startswith(PREFIX) or obj.get('Config', {}).get('Labels', {}).get(LABEL) != SESSION:
            reject('Refusing stop of container outside this exact session')
    elif op == 'image' and len(args) >= 2 and args[1] == 'inspect':
        pass
    elif op in ('exec', 'cp', 'logs', 'inspect', 'images', 'ps', 'stats', 'version', 'info', 'port'):
        pass
    else:
        reject('Operation not permitted: ' + op)
    os.execv(REAL, [REAL, *args])


if __name__ == '__main__':
    main()
