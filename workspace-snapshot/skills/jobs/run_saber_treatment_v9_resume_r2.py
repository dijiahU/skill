"""Resume five incomplete local models without overwriting existing raw results.

R2 changes host lifecycle capture only. Frozen benchmark code and configuration
stay unchanged. DeepSeek Pro is excluded from execution and judging; its old raw
record is retained. Preparation and execution are explicit, separate actions.
"""

import argparse
from contextlib import contextmanager
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
PREVIOUS_RECOVERY = JOB / 'recovery-r1'
RECOVERY = JOB / 'recovery-r2'
BASE_LOG = ROOT / 'logs' / ('saber-' + BATCH)
PREVIOUS_LOG = BASE_LOG / 'recovery-r1'
LOG = BASE_LOG / 'recovery-r2'
EFFECTIVE_MANIFEST = RECOVERY / 'effective-manifest.json'
DATA = ROOT / 'results' / ('saber-' + BATCH)
REMAINING = ['minimax', 'deepseek_flash', 'qwen', 'glm', 'gptoss']
EFFECTIVE_MODELS = ['mistral', *REMAINING]
EXCLUDED = ['deepseek_pro']
OVERLAY_FILES = ['run_saber_treatment_v9_resume_r2.py',
                 'saber_treatment_v9_process_ownership.py',
                 'saber_treatment_v9_spawn_capture.py']
FINGERPRINTED_FILES = [*OVERLAY_FILES, 'checkpoint.json', 'effective-manifest.json']
sys.path.insert(0, str(FROZEN / 'jobs'))
spec = importlib.util.spec_from_file_location('_v9_frozen_batch', FROZEN / 'jobs/run_saber_treatment_v9_full_batch.py')
batch = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = batch
spec.loader.exec_module(batch)
ORIGINAL_MANIFEST = batch.MANIFEST
ownership_path = (RECOVERY if Path(__file__).resolve().parent == RECOVERY.resolve()
                  else PREVIOUS_RECOVERY) / 'saber_treatment_v9_process_ownership.py'
ownership_spec = importlib.util.spec_from_file_location('saber_treatment_v9_process_ownership', ownership_path)
ownership = importlib.util.module_from_spec(ownership_spec)
sys.modules[ownership_spec.name] = ownership
ownership_spec.loader.exec_module(ownership)


def read(path):
    return json.loads(path.read_text())


def create_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def status(stage, **fields):
    payload = {'stage': stage, 'batch': BATCH, 'recovery': 'r2',
               'excluded_models': EXCLUDED, 'effective_manifest': str(EFFECTIVE_MANIFEST),
               'total_expected': 4296,
               'updated': time.strftime('%Y-%m-%d %H:%M:%S %z'), **fields}
    batch.save(LOG / 'status.json', payload)
    batch.save(BASE_LOG / 'status.json', payload)


_original_event = batch.event


def event(message, **fields):
    if message == 'judge_started':
        fields['expected'] = 4296
    _original_event(message, recovery='r2', **fields)


def raw_fingerprint():
    raw = DATA / 'raw'
    result = {}
    for path in sorted(raw.rglob('*')):
        if path.is_symlink():
            raise RuntimeError('raw result tree contains a symlink')
        if path.is_file():
            result[str(path.relative_to(raw))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def require_effective_inventory(manifest):
    if ([item['key'] for item in manifest['models']] != EFFECTIVE_MODELS
            or len(manifest['task_ids']) != 716
            or len(set(manifest['task_ids'])) != 716
            or manifest.get('total_expected') != 4296):
        raise RuntimeError('effective scope must be six local models and 4296 records')


def check_inputs():
    batch.check_frozen()
    expected = read(RECOVERY / 'overlay-fingerprint.json')
    actual = {name: hashlib.sha256((RECOVERY / name).read_bytes()).hexdigest()
              for name in FINGERPRINTED_FILES}
    if actual != expected:
        raise RuntimeError('R2 overlay, effective scope, or checkpoint changed')
    checkpoint = read(RECOVERY / 'checkpoint.json')
    preserved = checkpoint['preserved_raw_fingerprint']
    current = raw_fingerprint()
    if any(current.get(path) != digest for path, digest in preserved.items()):
        raise RuntimeError('an existing raw result was changed or removed')
    allowed = set(checkpoint['append_only_result_slugs'])
    if any(Path(path).parts[0] not in allowed for path in current.keys() - preserved.keys()):
        raise RuntimeError('new raw artifact is outside the five-model append-only scope')
    require_effective_inventory(read(EFFECTIVE_MANIFEST))


def check_images():
    for image, digest in batch.IMAGE_IDS.items():
        actual = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', image], text=True).strip()
        if actual != digest:
            raise RuntimeError('runtime image changed')


def require_previous_stopped():
    previous = read(PREVIOUS_LOG / 'status.json')
    if previous.get('stage') not in {'treatment_failed', 'pipeline_failed'}:
        raise RuntimeError('R1 has not reached a recorded terminal state')
    submitted = read(PREVIOUS_LOG / 'submitted.json')
    pid = submitted.get('pid')
    if type(pid) is not int or pid <= 1 or (Path('/proc') / str(pid)).exists():
        raise RuntimeError('R1 controller exit is not confirmed')
    # Do not alter the old lock file or adopt/stop old services.
    with (PREVIOUS_RECOVERY / 'pipeline.lock').open('r') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    ids = subprocess.check_output(['docker', 'ps', '-aq', '--filter',
                                  'label=rick-saber.batch=' + BATCH], text=True).split()
    if ids:
        raise RuntimeError('batch containers still exist; inspect exact targets first')
    return previous


def prepare():
    batch.check_frozen()
    check_images()
    previous_r1 = require_previous_stopped()
    original = read(ORIGINAL_MANIFEST)
    if [item['key'] for item in original['models']] != [*EFFECTIVE_MODELS, 'deepseek_pro']:
        raise RuntimeError('unexpected original model inventory')
    if RECOVERY.exists() or LOG.exists():
        raise RuntimeError('R2 preparation already exists; refusing overwrite')
    preserved = raw_fingerprint()
    from saber_treatment_v9_audit import validate_model
    mistral = original['models'][0]
    report = validate_model(DATA / 'raw' / mistral['result_slug'],
                            FROZEN / 'saber/tasks', original['task_ids'])
    if report['totals']['unique_result_ids'] != 716 or report['totals']['result_files'] != 716:
        raise RuntimeError('all 716 Mistral records must remain present')
    inventory = {}
    for item in original['models']:
        prefix = item['result_slug'] + '/'
        files = sorted(path[len(prefix):] for path in preserved if path.startswith(prefix))
        inventory[item['key']] = {'result_slug': item['result_slug'], 'files': files}
        if item['key'] != 'mistral' and files != ['A/fs_destruction/A_fs_001.json']:
            raise RuntimeError('R2 expects only the preserved first task for ' + item['key'])
    effective = dict(original)
    effective['models'] = [item for item in original['models'] if item['key'] in EFFECTIVE_MODELS]
    effective['excluded_models'] = EXCLUDED
    effective['total_expected'] = 4296
    effective['scope'] = 'six local-model treatments and judge only; DeepSeek Pro excluded; old raw records preserved'
    require_effective_inventory(effective)
    sources = {
        name: (PREVIOUS_RECOVERY if name == 'saber_treatment_v9_process_ownership.py'
               else ROOT / 'jobs') / name
        for name in OVERLAY_FILES
    }
    if any(not path.is_file() for path in sources.values()):
        raise RuntimeError('an R2 lifecycle source file is unavailable')
    RECOVERY.mkdir()
    LOG.mkdir()
    for name, path in sources.items():
        shutil.copy2(path, RECOVERY / name)
    create_json(EFFECTIVE_MANIFEST, effective)
    checkpoint = {
        'batch': BATCH, 'recovery': 'r2', 'remaining': REMAINING, 'excluded': EXCLUDED,
        'previous_status': read(BASE_LOG / 'status.json'),
        'previous_r1_status': previous_r1,
        'previous_r1_submitted': read(PREVIOUS_LOG / 'submitted.json'),
        'previous_r1_gate': read(PREVIOUS_LOG / 'treatment-batch-validation.json'),
        'preserved_raw_fingerprint': preserved, 'preserved_inventory': inventory,
        'mistral_validation': report['totals'],
        'append_only_result_slugs': [item['result_slug'] for item in effective['models'][1:]],
        'change_scope': 'bounded fixed-birth spawn capture; five-model append-only continuation; no Pro execution or judge',
    }
    create_json(RECOVERY / 'checkpoint.json', checkpoint)
    create_json(RECOVERY / 'overlay-fingerprint.json', {
        name: hashlib.sha256((RECOVERY / name).read_bytes()).hexdigest()
        for name in FINGERPRINTED_FILES})
    create_json(LOG / 'status.json', {'stage': 'recovery_prepared', 'remaining': REMAINING,
                                      'excluded_models': EXCLUDED, 'total_expected': 4296,
                                      'effective_manifest': str(EFFECTIVE_MANIFEST)})
    print(json.dumps({'prepared': str(RECOVERY), 'preserved_records': len(preserved),
                      'remaining': REMAINING, 'excluded_models': EXCLUDED,
                      'total_expected': 4296}), flush=True)


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
            from saber_treatment_v9_spawn_capture import capture_spawn
            record['identity'] = capture_spawn(process, BATCH, self.model)
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
        primary_error = sys.exc_info()[1]
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
        batch.save(self.directory / 'lifecycle-outcome.json', {
            'primary_error_type': type(primary_error).__name__ if primary_error else None,
            'cleanup_error_types': [type(error).__name__ for error in errors],
            'cleanup_safe': not errors,
        })
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
    require_effective_inventory(manifest)
    failures = []
    if checkpoint['mistral_validation']['technical_fail']:
        failures.append({'model': 'mistral', 'reason': 'preserved_previous_technical_failure',
                         'technical_fail': checkpoint['mistral_validation']['technical_fail']})
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
            'excluded_models': EXCLUDED, 'effective_manifest': str(EFFECTIVE_MANIFEST),
            'total_expected': 4296,
            'models': {item['key']: report['totals'] for item, report in zip(manifest['models'], reports)}}
    batch.save(LOG / 'treatment-batch-validation.json', gate)
    if not passed:
        status('treatment_failed', treatment_queue_finished=True, judge_started=False, failures=failures)
        event('paused_before_judge', reason='five local models attempted; six-model technical gate retained; Pro excluded')
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
        require_previous_stopped()
        if read(LOG / 'status.json').get('stage') != 'recovery_prepared':
            raise RuntimeError('R2 already submitted; refusing duplicate or implicit restart')
        checkpoint = read(RECOVERY / 'checkpoint.json')
        if raw_fingerprint() != checkpoint['preserved_raw_fingerprint']:
            raise RuntimeError('raw inputs changed between R2 preparation and submission')
        create_json(LOG / 'submitted.json', {'pid': os.getpid(), 'time': time.strftime('%Y-%m-%d %H:%M:%S %z')})
        try:
            status('recovery_started', preserved_models=['mistral'], excluded_models=EXCLUDED,
                   total_expected=4296)
            return run_remaining(manifest, checkpoint)
        except BaseException as error:
            cleanup_errors = []
            for key in [*REMAINING, 'judge']:
                for cleanup in (cleanup_model, batch.cleanup_containers):
                    try:
                        cleanup(key)
                    except Exception as cleanup_error:
                        cleanup_errors.append({'model': key, 'type': type(cleanup_error).__name__})
            batch.save(LOG / 'exit-audit.json', {'failure_type': type(error).__name__,
                                               'cleanup_errors': cleanup_errors,
                                               'excluded_models': EXCLUDED})
            status('pipeline_failed', failure_type=type(error).__name__,
                   automatic_judge_continuation=False, excluded_models=EXCLUDED)
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
    batch.MANIFEST = EFFECTIVE_MANIFEST
    batch.event = event
    batch.Lifecycle = RecoveryLifecycle
    batch.cleanup_processes = cleanup_model
    batch.cleanup_containers = cleanup_containers
    batch.launch_managed = launch
    def interrupted(signum, frame):
        raise KeyboardInterrupt('recovery interrupted by signal ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    manifest = read(EFFECTIVE_MANIFEST)
    require_effective_inventory(manifest)
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
