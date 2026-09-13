"""Prepare pinned dependencies, then replay official tests without model calls."""
import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys
import time

JOB = Path(__file__).resolve().parent
ROOT = Path('/srv/benchmark/skills/results/terminal-api-foreign-20260913-r1')
SOURCES = [
    'rick-saber-tbapi-gpt-20260913-r1-retry1/torch-pipeline-parallelism__unvMwEs',
    'rick-saber-tbapi-gemini-20260913-r1-full/torch-pipeline-parallelism__ZJSfB8E',
    'rick-saber-tbapi-gpt-20260913-r1-resume2/crack-7z-hash__MtBym95',
    'rick-saber-tbapi-gemini-20260913-r1-resume2/path-tracing-reverse__iSgzYrp',
]


def repair(rel):
    source = ROOT / rel
    name = source.parent.name.split('-')[3] + '-' + source.name
    state = {'source': str(source), 'model_api_calls': 0, 'started_at': time.time()}
    if source.name.startswith('torch-pipeline-parallelism__'):
        runtime, = (source / 'aistation').glob('*/runtime.json')
        session = runtime.parent.name
        ids = subprocess.check_output(['docker', 'ps', '-q', '--filter', 'label=skilldistill.session=' + session,
                                       '--filter', 'label=com.docker.compose.service=main'], text=True).split()
        container, = ids
        info = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
        assert info['Config']['Labels']['skilldistill.benchmark'] == 'terminal-bench'
        assert info['Config']['Labels']['skilldistill.session'] == session
        assert info['Name'].lstrip('/').startswith(session + '-')
        assert session.startswith(('rick-saber-tbapi-', 'rick-saber-tbretry-'))
        env = {k: 'http://private-host-fb6337b4cc5a.invalid:7899' for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']}
        env.update(ALL_PROXY='', all_proxy='', NO_PROXY='localhost,127.0.0.1', no_proxy='localhost,127.0.0.1',
                   UV_DEFAULT_INDEX='https://pypi.org/simple', UV_INDEX_URL='https://pypi.org/simple',
                   UV_FIND_LINKS='/opt/tb21-verifier-bootstrap/wheels', UV_HTTP_TIMEOUT='300')
        argv = ['docker', 'exec']
        for key, value in env.items():
            argv.extend(['-e', key + '=' + value])
        argv.extend([container, 'timeout', '--signal=TERM', '--kill-after=5s', '3600s',
                     '/opt/tb21-verifier-bootstrap/uvx', '-p', '3.13', '-w', 'pytest==8.4.1',
                     '-w', 'torch==2.7.0', '-w', 'transformers==4.55.0', '-w', 'pytest-json-ctrf==0.3.5',
                     'pytest', '--version'])
        with (JOB / 'logs' / (name + '-dependencies.log')).open('x') as log:
            ready = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=3630)
        state['dependency_returncode'] = ready.returncode
        if ready.returncode:
            state['status'] = 'dependency preparation failed; verifier not run'
            (JOB / 'preflight' / (name + '-verifier.json')).write_text(json.dumps(state, indent=2))
            return state
    with (JOB / 'logs' / (name + '-regrade.log')).open('x') as log:
        replay = subprocess.run([sys.executable, '/srv/benchmark/skills/jobs/terminal-verifier-repair-20260913-r1/regrade_retained.py',
                                 '--source', str(source)], stdout=log, stderr=subprocess.STDOUT)
    state.update(returncode=replay.returncode, status='replay ended', finished_at=time.time())
    (JOB / 'preflight' / (name + '-verifier.json')).write_text(json.dumps(state, indent=2))
    return state


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for state in pool.map(repair, SOURCES):
            print(json.dumps(state), flush=True)
