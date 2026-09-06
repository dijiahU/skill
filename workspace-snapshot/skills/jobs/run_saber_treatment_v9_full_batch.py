"""Fresh seven-model treatment batch, followed by gated local DeepSeek judging.

Preparation is non-GPU. Running requires explicit scoped cleanup approval.
All model-server/consumer lifecycles are foreground children of gpu-idle run.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.parse


ROOT = Path('/2024233123/skills')
SABER = ROOT / 'projects/skill/saber'
BUNDLE = ROOT / 'projects/skill/agent-safety-orchestrator/agent-safety-orchestrator'
BATCH = 'v9-full-20260905-r1'
JOB = ROOT / 'jobs' / ('saber-' + BATCH)
FROZEN = JOB / 'frozen'
DATA = ROOT / 'results' / ('saber-' + BATCH)
LOG = ROOT / 'logs' / ('saber-' + BATCH)
MANIFEST = FROZEN / 'manifest.json'
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
IMAGE = 'saber-codex-runner:0.149.1'
IMAGE_IDS = {
    IMAGE: 'sha256:3749667060d25e3b6503c74521a13556e618d308803e9774e754ea64ab6401a1',
    'osbench-sandbox:latest': 'sha256:439dd2c1803d6f9cd223fcae4fbb6e859ce3bddaea33eaca5e50f83d93949044',
}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def event(message, **fields):
    row = {'time': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'event': message, **fields}
    text = json.dumps(row, ensure_ascii=False)
    print(text, flush=True)
    LOG.mkdir(parents=True, exist_ok=True)
    with (LOG / 'events.jsonl').open('a') as handle:
        handle.write(text + '\n')


def fingerprint(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.rglob('*'))
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'}


def check_frozen():
    expected = json.loads((JOB / 'frozen-fingerprint.json').read_text())
    if fingerprint(FROZEN) != expected:
        raise RuntimeError('frozen experiment inputs changed; refusing mixed-version run')


def host_path(path):
    relative = Path(path).relative_to(os.environ['POD_USER_ROOT'])
    return str(Path(os.environ['HOST_USER_ROOT']) / relative)


def prepare():
    from saber_treatment_v9_model_specs import MODEL_SPECS
    for path in (JOB, DATA, LOG):
        if path.exists():
            raise RuntimeError(f'batch path already exists; not overwriting: {path}')
    task_ids = []
    for scenario in ('A', 'B', 'C'):
        for path in sorted((SABER / 'tasks' / scenario).glob('*/*.json')):
            task_ids.append(json.loads(path.read_text())['id'])
    assert len(task_ids) == len(set(task_ids)) == 716
    JOB.mkdir(parents=True)
    (FROZEN / 'saber').mkdir(parents=True)
    (FROZEN / 'saber/results').mkdir()
    (FROZEN / 'bin').mkdir()
    (FROZEN / 'jobs').mkdir()
    (DATA / 'raw').mkdir(parents=True)
    (DATA / 'judged').mkdir()
    LOG.mkdir(parents=True)
    ignored = shutil.ignore_patterns('__pycache__', '*.pyc', '.git')
    for path in SABER.glob('*.py'):
        shutil.copy2(path, FROZEN / 'saber' / path.name)
    for directory in ('tasks', 'scripts', 'harness_adapters'):
        shutil.copytree(SABER / directory, FROZEN / 'saber' / directory, ignore=ignored)
    shutil.copytree(BUNDLE, FROZEN / 'bundle', ignore=ignored)
    for path in (ROOT / 'bin').glob('vllm_responses_compat_proxy*.py'):
        shutil.copy2(path, FROZEN / 'bin' / path.name)
    for name in ('run_saber_parallel_judge.py', 'run_saber_parallel_judge_deepseekv4.py'):
        shutil.copy2(ROOT / 'bin' / name, FROZEN / 'bin' / name)
    for name in ('run_saber_treatment_v9_full_batch.py', 'saber_treatment_v9_model_specs.py',
                 'saber_treatment_v9_audit.py', 'saber_treatment_v9_container_entry.py',
                 'saber_treatment_v9_judge_entry.py'):
        shutil.copy2(ROOT / 'jobs' / name, FROZEN / 'jobs' / name)
    save(FROZEN / 'saber/config.json', {'max_steps': 30, 'models': {}, 'judge': {
        'id': 'deepseek-ai/DeepSeek-V4-Flash-0731', 'type': 'openai',
        'key': 'local-judge', 'base_url': 'http://127.0.0.1:18020'}})
    # Preserve the exact established partition, not merely the total count.
    subset_source = ROOT / 'jobs/saber_glm47_baseline_716_subsets'
    shutil.copytree(subset_source, FROZEN / 'subsets', ignore=ignored)
    partition = []
    for index in range(8):
        payload = json.loads((FROZEN / f'subsets/part-{index:02d}.json').read_text())
        partition.extend(item if isinstance(item, str) else item['id']
                         for item in (payload['tasks'] if isinstance(payload, dict) else payload))
    assert sorted(partition) == sorted(task_ids), 'subset partition mismatch'
    models = json.loads(json.dumps(MODEL_SPECS))
    pod_ip = subprocess.check_output(['hostname', '-I'], text=True).split()[0]
    for spec in models:
        old = json.loads(Path(spec['old_config']).read_text())['models'][spec['old_slug']]
        spec['slug'] = f'codex_{spec["key"]}_treatment_v9_full_20260905_r1'
        spec['result_slug'] = spec['slug'] + '_codex-native-safety-orchestrator'
        for endpoint in spec['endpoints']:
            base_url = endpoint['base_url']
            if base_url.startswith('http://'):
                parsed = urllib.parse.urlsplit(base_url)
                base_url = urllib.parse.urlunsplit((parsed.scheme, f'{pod_ip}:{parsed.port}',
                                                   parsed.path, '', ''))
            cfg = dict(old, base_url=base_url, copy_codex_auth=False,
                       preload_skill_references=False)
            # Provider secrets remain in the existing credential file/env, never snapshots.
            for key in ('key', 'api_key', 'token'):
                cfg.pop(key, None)
            path = FROZEN / f'configs/{spec["key"]}-{endpoint["config_key"]}.json'
            save(path, {'max_steps': 30, 'models': {spec['slug']: cfg}})
            endpoint['config'] = str(path)
        for service in spec['services']:
            service['argv'] = [str(FROZEN / 'bin' / Path(arg).name)
                               if arg.startswith(str(ROOT / 'bin/vllm_responses_compat_proxy'))
                               else arg for arg in service['argv']]
            if not Path(service['argv'][0]).is_file():
                raise RuntimeError('service executable missing: ' + service['name'])
    manifest = {'batch': BATCH, 'frozen': str(FROZEN), 'raw': str(DATA / 'raw'),
                'judged': str(DATA / 'judged'), 'task_ids': task_ids,
                'models': models, 'image_ids': IMAGE_IDS,
                'scope': 'treatment only; all seven models; new results; automatic gated DeepSeek judge',
                'known_limitations': ['semantic task incompletion is judged, not filtered out',
                                      'controlled harness stops are not model safety success']}
    save(MANIFEST, manifest)
    save(JOB / 'frozen-fingerprint.json', fingerprint(FROZEN))
    save(LOG / 'status.json', {'stage': 'prepared', 'batch': BATCH, 'models': len(models),
                             'tasks_per_model': 716, 'total_expected': len(models) * 716})
    event('prepared', models=[s['key'] for s in models], total=len(models) * 716)


def cleanup_containers(model):
    ids = subprocess.check_output(['docker', 'ps', '-aq',
        '--filter', f'label=rick-saber.batch={BATCH}',
        '--filter', f'label=rick-saber.model={model}'], text=True).split()
    for container_id in ids:
        probe = subprocess.run(['docker', 'inspect', container_id], capture_output=True, text=True)
        if probe.returncode:
            continue  # --rm may have already completed its own cleanup.
        info = json.loads(probe.stdout)[0]
        labels = info.get('Config', {}).get('Labels') or {}
        prefix = f'/rick-saber-{BATCH}-{model.replace("_", "-")}-'
        if (labels.get('rick-saber.batch') != BATCH or labels.get('rick-saber.model') != model
                or not info.get('Name', '').startswith(prefix)):
            raise RuntimeError('container ownership mismatch; cleanup refused')
        subprocess.run(['docker', 'rm', '-f', container_id], check=True,
                       stdout=subprocess.DEVNULL)
        event('owned_container_removed', model=model, container_id=container_id)



def group_members(pgid, model):
    """Resolve current members and verify inherited batch identity before signals."""
    members = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(fields[2]) != pgid or fields[0] == 'Z':
                continue
            environment = (path / 'environ').read_bytes().split(b'\0')
            if (f'SABER_BATCH_ID={BATCH}'.encode() not in environment
                    or f'SABER_BATCH_MODEL={model}'.encode() not in environment):
                raise RuntimeError('process-group identity mismatch; refusing signal')
            members.append(int(path.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return members


def cleanup_processes(model):
    record = LOG / model / 'processes.json'
    if not record.exists():
        return
    groups = [row['pid'] for row in json.loads(record.read_text())]
    for pgid in groups:
        if group_members(pgid, model):
            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline and any(group_members(p, model) for p in groups):
        time.sleep(1)
    for pgid in groups:
        if group_members(pgid, model):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and any(group_members(p, model) for p in groups):
        time.sleep(0.5)
    if any(group_members(p, model) for p in groups):
        raise RuntimeError('owned process groups did not exit; reservation must not advance')


class Lifecycle:
    def __init__(self, model):
        self.model = model
        self.processes = []
        self.directory = LOG / model
        self.directory.mkdir(parents=True, exist_ok=True)

    def spawn(self, name, argv, extra_env=None):
        env = dict(os.environ, SABER_BATCH_ID=BATCH, SABER_BATCH_MODEL=self.model,
                   PYTHONDONTWRITEBYTECODE='1')
        env.pop('SABER_IDLE_SESSION', None)
        env.pop('SABER_DISCARD_RESULTS', None)
        env.update(extra_env or {})
        with (self.directory / (name + '.log')).open('x') as output:
            process = subprocess.Popen(argv, env=env, stdout=output,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        self.processes.append((name, process))
        save(self.directory / 'processes.json', [
            {'name': label, 'pid': p.pid, 'returncode': p.poll()} for label, p in self.processes])
        event('process_started', model=self.model, name=name, pid=process.pid)
        return process

    def close(self):
        try:
            cleanup_processes(self.model)
            for _, process in self.processes:
                process.wait(timeout=5)
        finally:
            cleanup_containers(self.model)
        event('lifecycle_closed', model=self.model)


def await_ready(process, service):
    deadline = time.monotonic() + service.get('ready_timeout', 1800)
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('service exited: ' + service['name'])
        try:
            with HTTP.open(service['health_url'], timeout=3) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(2)
    raise TimeoutError('service readiness: ' + service['name'])


def services_start(life, spec):
    for service in spec['services']:
        parsed = urllib.parse.urlsplit(service['health_url'])
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', parsed.port))
        process = life.spawn(service['name'], service['argv'], service.get('env'))
        await_ready(process, service)
        event('service_ready', model=spec['key'], name=service['name'])


def docker_runner(life, spec, name, endpoint, arguments):
    key = spec['key']
    argv = ['docker', 'run', '--rm', '--pull=never', '--runtime', 'runc',
            '--name', f'rick-saber-{BATCH}-{key.replace("_", "-")}-{name}',
            '--label', f'rick-saber.batch={BATCH}', '--label', f'rick-saber.model={key}',
            '--label', 'rick-saber.role=runner',
            '--env', f'SABER_BATCH_ID={BATCH}', '--env', f'SABER_BATCH_MODEL={key}',
            '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'SABER_DOCKER_RUNTIME=runc',
            '--env', 'DOCKER_API_VERSION=1.43', '--env', 'DOCKER_HOST=' + os.environ['DOCKER_HOST'],
            '--workdir', '/workspace/saber']
    for source, destination, readonly in (
        (FROZEN / 'saber', '/workspace/saber', True),
        (FROZEN / 'bundle', '/workspace/agent-safety-orchestrator/agent-safety-orchestrator', True),
        (FROZEN / 'jobs/saber_treatment_v9_container_entry.py', '/run/saber-batch-entry.py', True),
        (FROZEN / 'subsets', '/run/saber-subsets', True),
        (Path(endpoint['config']), '/run/secrets/saber-config.json', True),
        (DATA / 'raw', '/workspace/saber/results', False),
    ):
        argv += ['--mount', f'type=bind,src={host_path(source)},dst={destination}'
                 + (',readonly' if readonly else '')]
    extra_env = {}
    credentials = spec.get('provider_credentials_path')
    if credentials:
        key_value = json.loads(Path(credentials).read_text()).get('api_key')
        if not key_value:
            raise RuntimeError('provider credential is unavailable')
        extra_env['SABER_CODEX_PROVIDER_API_KEY'] = key_value
        argv += ['--env', 'SABER_CODEX_PROVIDER_API_KEY']
    argv += [IMAGE, 'python3', '/run/saber-batch-entry.py',
             '--harness', 'codex-native', '--config', '/run/secrets/saber-config.json',
             '--model', spec['slug'], '--skill-mode', 'safety-orchestrator',
             '--safety-orchestrator', '/workspace/agent-safety-orchestrator/agent-safety-orchestrator',
             *arguments]
    return life.spawn(name, argv, extra_env)


def validate(spec, task_ids):
    from saber_treatment_v9_audit import validate_model
    report = validate_model(DATA / 'raw' / spec['result_slug'], FROZEN / 'saber/tasks', task_ids,
                            require_full=len(task_ids) == 716)
    save(LOG / spec['key'] / 'validation.json', report)
    return report


def run_model(manifest, key):
    spec = next(s for s in manifest['models'] if s['key'] == key)
    check_frozen()
    if spec['gpus'] and os.environ.get('CUDA_VISIBLE_DEVICES') != ','.join(map(str, spec['gpus'])):
        raise RuntimeError('GPU reservation does not match model usage')
    life = Lifecycle(key)
    try:
        services_start(life, spec)
        endpoint = spec['endpoints'][0]
        process = docker_runner(life, spec, 'preflight', endpoint, ['--preflight-only', 'A_fs_001'])
        if process.wait() != 0:
            raise RuntimeError('preflight failed')
        process = docker_runner(life, spec, 'smoke', endpoint, ['--skip-preflight', '--trace', 'A_fs_001'])
        if process.wait() != 0 or not validate(spec, ['A_fs_001'])['passed']:
            raise RuntimeError('smoke technical validation failed')
        check_frozen()
        workers = []
        for index in range(spec['workers']):
            endpoint = next(e for e in spec['endpoints'] if index in e['worker_indices'])
            workers.append(docker_runner(life, spec, f'worker-{index:02d}', endpoint,
                ['--skip-preflight', '--trace', '--subset', f'/run/saber-subsets/part-{index:02d}.json']))
        event('treatment_started', model=key, workers=len(workers), tasks=716)
        codes = [p.wait() for p in workers]
        report = validate(spec, manifest['task_ids'])
        check_frozen()
        if any(codes) or not report['passed']:
            raise RuntimeError('treatment technical validation failed; retained all raw results')
        event('treatment_validated', model=key, totals=report['totals'])
    finally:
        life.close()


def run_judge(manifest):
    check_frozen()
    gate = json.loads((LOG / 'treatment-batch-validation.json').read_text())
    status = json.loads((LOG / 'status.json').read_text())
    if (gate.get('passed') is not True or gate.get('failures')
            or status.get('stage') != 'judge_queued'
            or os.environ.get('CUDA_VISIBLE_DEVICES') != '0,1'):
        raise RuntimeError('judge requires validated batch exit and both reserved GPUs')
    if not all(validate(s, manifest['task_ids'])['passed'] for s in manifest['models']):
        raise RuntimeError('judge gate rejected incomplete or invalid treatment results')
    source_fingerprint = fingerprint(DATA / 'raw')
    save(LOG / 'raw-fingerprint-before-judge.json', source_fingerprint)
    spec = next(s for s in manifest['models'] if s['key'] == 'deepseek_flash')
    life = Lifecycle('judge')
    try:
        services_start(life, spec)
        process = life.spawn('deepseek-judge', [str(ROOT / 'envs/deepseekv4-vllm/bin/python'),
            str(FROZEN / 'jobs/saber_treatment_v9_judge_entry.py'), str(MANIFEST)])
        event('judge_started', models=len(manifest['models']), expected=5012)
        if process.wait() != 0:
            raise RuntimeError('DeepSeek judge failed; partial judged results retained')
        if source_fingerprint != fingerprint(DATA / 'raw'):
            raise RuntimeError('raw treatment results changed during judging')
        check_frozen()
        event('judge_complete', models=len(manifest['models']))
    finally:
        life.close()


def launch_managed(arguments, gpus):
    command = [sys.executable, str(FROZEN / 'jobs' / Path(__file__).name),
               *arguments, '--cleanup-approved']
    if gpus:
        command = [str(ROOT / 'bin/gpu-idle'), 'run', '--gpus', ','.join(map(str, gpus)),
                   '--timeout', '86400', '--', *command]
    process = subprocess.Popen(command)
    try:
        return process.wait()
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        raise


def run_batch(manifest):
    stage = json.loads((LOG / 'status.json').read_text()).get('stage')
    if stage != 'prepared':
        raise RuntimeError('batch already submitted; no implicit restart or overwrite')
    check_frozen()
    for image, digest in IMAGE_IDS.items():
        actual = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', image], text=True).strip()
        if actual != digest:
            raise RuntimeError('runtime image changed')
    failures = []
    for spec in manifest['models']:
        save(LOG / 'status.json', {'stage': 'treatment', 'current_model': spec['key'], 'failures': failures})
        event('model_queued', model=spec['key'], gpus=spec['gpus'])
        code = launch_managed(['--run-model', spec['key']], spec['gpus'])
        # Backstop for an admission wrapper interrupted before child cleanup finished.
        cleanup_processes(spec['key'])
        cleanup_containers(spec['key'])
        if code:
            failures.append({'model': spec['key'], 'exit_code': code})
        event('model_exited', model=spec['key'], exit_code=code)
    reports = [validate(s, manifest['task_ids']) for s in manifest['models']]
    check_frozen()
    passed = not failures and all(r['passed'] for r in reports)
    save(LOG / 'treatment-batch-validation.json', {'passed': passed, 'failures': failures,
        'models': {s['key']: r['totals'] for s, r in zip(manifest['models'], reports)}})
    if not passed:
        save(LOG / 'status.json', {'stage': 'treatment_failed', 'judge_started': False, 'failures': failures})
        event('paused_before_judge', reason='technical validation failed; manual review required')
        return 1
    save(LOG / 'status.json', {'stage': 'judge_queued', 'treatment_validated': True})
    code = launch_managed(['--run-judge'], [0, 1])
    cleanup_processes('judge')
    cleanup_containers('judge')
    save(LOG / 'status.json', {'stage': 'complete' if code == 0 else 'judge_failed',
                             'treatment_validated': True, 'judge_exit_code': code})
    event('batch_complete' if code == 0 else 'judge_failed', exit_code=code)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--prepare', action='store_true')
    actions.add_argument('--run-batch', action='store_true')
    actions.add_argument('--run-model')
    actions.add_argument('--run-judge', action='store_true')
    parser.add_argument('--cleanup-approved', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
        return 0
    frozen_entry = FROZEN / 'jobs' / Path(__file__).name
    if Path(__file__).resolve() != frozen_entry.resolve():
        os.execv(sys.executable, [sys.executable, str(frozen_entry), *sys.argv[1:]])
    if not args.cleanup_approved:
        parser.error('explicit scoped cleanup approval is required before running')
    manifest = json.loads(MANIFEST.read_text())
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'owned batch interrupted by signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    if args.run_model:
        run_model(manifest, args.run_model)
    elif args.run_judge:
        run_judge(manifest)
    else:
        try:
            return run_batch(manifest)
        except BaseException as exc:
            # An early infrastructure failure must also leave an explicit gate decision.
            cleanup_errors = []
            for model in [s['key'] for s in manifest['models']] + ['judge']:
                try:
                    cleanup_processes(model)
                    cleanup_containers(model)
                except Exception as cleanup_error:
                    cleanup_errors.append({'model': model, 'type': type(cleanup_error).__name__})
            partial = {}
            for spec in manifest['models']:
                try:
                    partial[spec['key']] = validate(spec, manifest['task_ids'])['totals']
                except Exception as audit_error:
                    partial[spec['key']] = {'audit_error_type': type(audit_error).__name__}
            save(LOG / 'exit-audit.json', {'passed': False, 'failure_type': type(exc).__name__,
                                         'cleanup_errors': cleanup_errors, 'models': partial})
            save(LOG / 'status.json', {'stage': 'pipeline_failed', 'failure_type': type(exc).__name__,
                                     'automatic_judge_continuation': False})
            event('pipeline_failed', failure_type=type(exc).__name__)
            raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())



