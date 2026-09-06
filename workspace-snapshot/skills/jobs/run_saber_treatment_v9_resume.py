"""Resume only the six unstarted models using an immutable lifecycle overlay.

The original frozen benchmark, inputs, audit and Mistral results are not edited.
Only host process ownership, recovery bookkeeping and queue continuation change.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


ROOT = Path('/2024233123/skills')
BATCH = 'v9-full-20260905-r1'
JOB = ROOT / 'jobs' / ('saber-' + BATCH)
FROZEN = JOB / 'frozen'
RECOVERY = JOB / 'recovery-r1'
BASE_LOG = ROOT / 'logs' / ('saber-' + BATCH)
LOG = BASE_LOG / 'recovery-r1'
DATA = ROOT / 'results' / ('saber-' + BATCH)
REMAINING = ['minimax', 'deepseek_flash', 'qwen', 'glm', 'gptoss', 'deepseek_pro']
OVERLAY_FILES = ['run_saber_treatment_v9_resume.py', 'saber_treatment_v9_process_ownership.py']
sys.path.insert(0, str(FROZEN / 'jobs'))
spec = importlib.util.spec_from_file_location('_v9_frozen_batch', FROZEN / 'jobs/run_saber_treatment_v9_full_batch.py')
batch = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = batch
spec.loader.exec_module(batch)
import saber_treatment_v9_process_ownership as ownership


def read(path):
    return json.loads(path.read_text())


def create_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def status(stage, **fields):
    payload = {'stage': stage, 'batch': BATCH, 'recovery': 'r1',
               'updated': time.strftime('%Y-%m-%d %H:%M:%S %z'), **fields}
    batch.save(LOG / 'status.json', payload)
    batch.save(BASE_LOG / 'status.json', payload)


_original_event = batch.event


def event(message, **fields):
    _original_event(message, recovery='r1', **fields)
    row = {'time': time.strftime('%Y-%m-%d %H:%M:%S %z'),
           'event': message, 'recovery': 'r1', **fields}
    with (BASE_LOG / 'events.jsonl').open('a') as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def check_inputs():
    batch.check_frozen()
    expected = read(RECOVERY / 'overlay-fingerprint.json')
    actual = {name: hashlib.sha256((RECOVERY / name).read_bytes()).hexdigest()
              for name in OVERLAY_FILES + ['checkpoint.json']}
    if actual != expected:
        raise RuntimeError('recovery overlay or checkpoint changed')
    checkpoint = read(RECOVERY / 'checkpoint.json')
    mistral = DATA / 'raw' / checkpoint['mistral_result_slug']
    if batch.fingerprint(mistral) != checkpoint['mistral_fingerprint']:
        raise RuntimeError('preserved Mistral results changed')


def check_images():
    for image, digest in batch.IMAGE_IDS.items():
        actual = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', image], text=True).strip()
        if actual != digest:
            raise RuntimeError('runtime image changed')


def require_unstarted(manifest):
    if [s['key'] for s in manifest['models']] != ['mistral', *REMAINING]:
        raise RuntimeError('unexpected model inventory or order')
    for item in manifest['models'][1:]:
        if any((DATA / 'raw' / item['result_slug']).rglob('*')):
            raise RuntimeError('remaining model already has artifacts: ' + item['key'])
    ids = subprocess.check_output(['docker', 'ps', '-aq', '--filter',
                                  'label=rick-saber.batch=' + BATCH], text=True).split()
    if ids:
        raise RuntimeError('batch containers still exist; inspect exact targets first')


def prepare():
    batch.check_frozen()
    check_images()
    manifest = read(batch.MANIFEST)
    previous = read(BASE_LOG / 'status.json')
    if previous.get('stage') != 'pipeline_failed':
        raise RuntimeError('recovery requires the recorded failed pipeline')
    require_unstarted(manifest)
    mistral = manifest['models'][0]
    from saber_treatment_v9_audit import validate_model
    report = validate_model(DATA / 'raw' / mistral['result_slug'], FROZEN / 'saber/tasks', manifest['task_ids'])
    if report['totals']['unique_result_ids'] != 716 or report['totals']['result_files'] != 716:
        raise RuntimeError('Mistral must have all 716 retained records')
    rows = read(BASE_LOG / 'mistral/processes.json')
    server = next(row for row in rows if row['name'] == 'mistral-vllm')
    pid = server['pid']
    # The old ledger has no birth field. Require exact argv, original start event,
    # current leader tags and matching boot-relative creation time before adoption.
    argv = [a.decode() for a in (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0') if a]
    expected_argv = mistral['services'][0]['argv']
    shebang = Path(expected_argv[0]).read_bytes().split(b'\n', 1)[0]
    interpreter = shebang[2:].decode().strip() if shebang.startswith(b'#!/') else ''
    shebang_match = (interpreter and not any(c.isspace() for c in interpreter)
                     and argv == [interpreter, *expected_argv])
    if argv != expected_argv and not shebang_match:
        raise RuntimeError('legacy Mistral leader argv mismatch')
    identity = ownership.capture(pid, BATCH, 'mistral')
    starts = [json.loads(line) for line in (BASE_LOG / 'events.jsonl').read_text().splitlines()]
    started = next(row for row in starts if row.get('event') == 'process_started'
                   and row.get('model') == 'mistral' and row.get('name') == 'mistral-vllm' and row.get('pid') == pid)
    fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
    boot = next(int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines() if line.startswith('btime '))
    birth_wall = boot + int(fields[19]) / os.sysconf('SC_CLK_TCK')
    if abs(birth_wall - datetime.strptime(started['time'], '%Y-%m-%d %H:%M:%S %z').timestamp()) > 5:
        raise RuntimeError('legacy leader creation time differs from original launch')
    RECOVERY.mkdir()
    LOG.mkdir()
    for name in OVERLAY_FILES:
        shutil.copy2(ROOT / 'jobs' / name, RECOVERY / name)
    checkpoint = {'batch': BATCH, 'remaining': REMAINING,
                  'previous_status': previous, 'previous_exit_audit': read(BASE_LOG / 'exit-audit.json'),
                  'mistral_result_slug': mistral['result_slug'],
                  'mistral_fingerprint': batch.fingerprint(DATA / 'raw' / mistral['result_slug']),
                  'mistral_validation': report['totals'], 'legacy_processes': [identity],
                  'legacy_process_start_event': started,
                  'change_scope': 'host lifecycle and six-model continuation only; original frozen inputs unchanged'}
    create_json(RECOVERY / 'checkpoint.json', checkpoint)
    create_json(RECOVERY / 'overlay-fingerprint.json', {
        name: hashlib.sha256((RECOVERY / name).read_bytes()).hexdigest()
        for name in OVERLAY_FILES + ['checkpoint.json']})
    create_json(LOG / 'status.json', {'stage': 'recovery_prepared', 'remaining': REMAINING})
    print(json.dumps({'prepared': str(RECOVERY), 'legacy_identity': identity,
                      'mistral': report['totals'], 'remaining': REMAINING}), flush=True)


@contextmanager
def exclusive_lock(name):
    with (RECOVERY / (name + '.lock')).open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def cleanup_model(model):
    path = LOG / model / 'process-identities.json'
    if path.exists():
        rows = read(path)
        for row in rows:
            if row.get('identity'):
                continue
            active = [p for p in ownership._scan().values()
                      if (p['pgid'] == row['pid'] or p['sid'] == row['pid'])
                      and p['state'] not in ('Z', 'X', 'x')]
            if active:
                raise RuntimeError('uncaptured process session still has live members')
        records = [row['identity'] for row in rows if row.get('identity')]
        ownership.cleanup(records, BATCH, model)


_original_container_cleanup = batch.cleanup_containers


def cleanup_containers(model):
    _original_container_cleanup(model)
    remaining = subprocess.check_output(['docker', 'ps', '-aq', '--filter',
        'label=rick-saber.batch=' + BATCH, '--filter',
        'label=rick-saber.model=' + model], text=True).split()
    if remaining:
        raise RuntimeError('scoped containers remain after cleanup')


class RecoveryLifecycle:
    def __init__(self, model):
        self.model = model
        self.directory = LOG / model
        self.directory.mkdir(parents=True, exist_ok=True)
        self.processes = []
        self.records = []

    def spawn(self, name, argv, extra_env=None):
        env = dict(os.environ, SABER_BATCH_ID=BATCH, SABER_BATCH_MODEL=self.model,
                   PYTHONDONTWRITEBYTECODE='1')
        env.pop('SABER_IDLE_SESSION', None)
        env.pop('SABER_DISCARD_RESULTS', None)
        env.update(extra_env or {})
        with (self.directory / (name + '.log')).open('x') as output:
            process = subprocess.Popen(argv, env=env, stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        self.processes.append((name, process))
        record = {'name': name, 'pid': process.pid, 'identity': None}
        self.records.append(record)
        try:
            record['identity'] = ownership.capture(process.pid, BATCH, self.model)
        except Exception:
            if process.poll() is None:
                # This is our newly spawned, unreaped direct child, not an old PID.
                process.terminate()
                process.wait(timeout=10)
                raise
        finally:
            batch.save(self.directory / 'process-identities.json', self.records)
        event('process_started', model=self.model, name=name, pid=process.pid)
        return process

    def close(self):
        errors = []
        try:
            cleanup_model(self.model)
            for _, process in self.processes:
                process.wait(timeout=5)
        except Exception as error:
            errors.append(error)
        try:
            batch.cleanup_containers(self.model)
        except Exception as error:
            errors.append(error)
        batch.save(self.directory / 'process-exits.json', [
            {'name': name, 'pid': process.pid, 'returncode': process.poll()}
            for name, process in self.processes])
        if errors:
            event('lifecycle_cleanup_failed', model=self.model, error_types=[type(e).__name__ for e in errors])
            raise RuntimeError('recovery lifecycle cleanup failed') from errors[0]
        event('lifecycle_closed', model=self.model)


def managed_command(arguments, gpus):
    command = [sys.executable, str(RECOVERY / Path(__file__).name), *arguments, '--cleanup-approved']
    if gpus:
        command = [str(ROOT / 'bin/gpu-idle'), 'run', '--gpus', ','.join(map(str, gpus)),
                   '--timeout', '86400', '--', *command]
    return command


def launch(arguments, gpus):
    process = subprocess.Popen(managed_command(arguments, gpus))
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


def run_remaining(manifest, checkpoint):
    failures = [{'model': 'mistral', 'reason': 'preserved_previous_technical_failure',
                 'technical_fail': checkpoint['mistral_validation']['technical_fail']}]
    for item in manifest['models'][1:]:
        key = item['key']
        check_inputs()
        status('treatment', current_model=key, failures=failures, preserved_models=['mistral'])
        event('model_queued', model=key, gpus=item['gpus'])
        code = launch(['--run-model', key], item['gpus'])
        # Only a genuinely unsafe/incomplete resource teardown blocks the queue.
        cleanup_model(key)
        batch.cleanup_containers(key)
        report = batch.validate(item, manifest['task_ids'])
        if code or not report['passed']:
            failures.append({'model': key, 'exit_code': code,
                             'technical_fail': report['totals']['technical_fail']})
        event('model_exited', model=key, exit_code=code, totals=report['totals'])
    check_inputs()
    reports = [batch.validate(item, manifest['task_ids']) for item in manifest['models']]
    passed = not failures and all(report['passed'] for report in reports)
    gate = {'passed': passed, 'failures': failures,
            'models': {item['key']: report['totals'] for item, report in zip(manifest['models'], reports)}}
    batch.save(LOG / 'treatment-batch-validation.json', gate)
    batch.save(BASE_LOG / 'treatment-batch-validation.json', gate)
    if not passed:
        status('treatment_failed', treatment_queue_finished=True, judge_started=False, failures=failures)
        event('paused_before_judge', reason='all remaining models attempted; technical gate retained')
        return 1
    status('judge_queued', treatment_validated=True)
    code = launch(['--run-judge'], [0, 1])
    cleanup_model('judge')
    batch.cleanup_containers('judge')
    status('complete' if code == 0 else 'judge_failed', treatment_validated=True, judge_exit_code=code)
    event('batch_complete' if code == 0 else 'judge_failed', exit_code=code)
    return code


def run_recovery(manifest):
    with exclusive_lock('pipeline'):
        check_inputs()
        check_images()
        require_unstarted(manifest)
        if read(LOG / 'status.json').get('stage') != 'recovery_prepared':
            raise RuntimeError('recovery already submitted; refusing duplicate or implicit restart')
        create_json(LOG / 'submitted.json', {'pid': os.getpid(), 'time': time.strftime('%Y-%m-%d %H:%M:%S %z')})
        checkpoint = read(RECOVERY / 'checkpoint.json')
        try:
            status('recovery_cleanup', current_model='mistral', preserved_models=['mistral'])
            preview = ownership.inspect(checkpoint['legacy_processes'], BATCH, 'mistral')
            create_json(LOG / 'legacy-cleanup-preview.json', preview)
            ownership.cleanup(preview['records'], BATCH, 'mistral')
            batch.cleanup_containers('mistral')
            event('preserved_model_cleanup_complete', model='mistral', preserved_results=716)
            check_inputs()
            return run_remaining(manifest, checkpoint)
        except BaseException as error:
            cleanup_errors = []
            for key in [*REMAINING, 'judge']:
                for cleanup in (cleanup_model, batch.cleanup_containers):
                    try:
                        cleanup(key)
                    except Exception as cleanup_error:
                        cleanup_errors.append({'model': key, 'type': type(cleanup_error).__name__})
            batch.save(LOG / 'exit-audit.json', {'failure_type': type(error).__name__, 'cleanup_errors': cleanup_errors})
            status('pipeline_failed', failure_type=type(error).__name__, automatic_judge_continuation=False)
            event('pipeline_failed', failure_type=type(error).__name__)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--run', action='store_true')
    modes.add_argument('--run-model', choices=REMAINING)
    modes.add_argument('--run-judge', action='store_true')
    parser.add_argument('--cleanup-approved', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
        return 0
    if not args.cleanup_approved:
        parser.error('scoped cleanup approval is required')
    if Path(__file__).resolve() != (RECOVERY / Path(__file__).name).resolve():
        os.execv(sys.executable, [sys.executable, str(RECOVERY / Path(__file__).name), *sys.argv[1:]])
    check_inputs()
    batch.LOG = LOG
    batch.event = event
    batch.Lifecycle = RecoveryLifecycle
    batch.cleanup_processes = cleanup_model
    batch.cleanup_containers = cleanup_containers
    batch.launch_managed = launch
    def interrupted(signum, frame):
        raise KeyboardInterrupt('recovery interrupted by signal ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    manifest = read(batch.MANIFEST)
    if args.run_model:
        with exclusive_lock(args.run_model):
            state = read(LOG / 'status.json')
            if state.get('stage') != 'treatment' or state.get('current_model') != args.run_model:
                raise RuntimeError('model is not the queued recovery stage')
            create_json(LOG / args.run_model / 'submitted.json', {'pid': os.getpid()})
            batch.run_model(manifest, args.run_model)
        return 0
    if args.run_judge:
        with exclusive_lock('judge'):
            batch.run_judge(manifest)
        return 0
    return run_recovery(manifest)


if __name__ == '__main__':
    raise SystemExit(main())
