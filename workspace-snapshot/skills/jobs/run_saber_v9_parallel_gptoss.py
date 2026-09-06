"""Run gpt-oss on GPU0 only inside the live R2 GLM/GPU1 admission window.

Prepare an immutable auxiliary checkpoint, then watch without reserving GPUs.
The admitted child rechecks the window and holds R2's gptoss.lock throughout
the complete frozen model lifecycle. No R2 code, status or log is rewritten.
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
R2_DIR = JOB / 'recovery-r2'
R2_ENTRY = R2_DIR / 'run_saber_treatment_v9_resume_r2.py'
BASE_LOG = ROOT / 'logs' / ('saber-' + BATCH)
R2_LOG = BASE_LOG / 'recovery-r2'
AUX = JOB / 'parallel-gptoss-r2'
LOG = BASE_LOG / 'parallel-gptoss-r2'
ENTRY_NAME = 'run_saber_v9_parallel_gptoss.py'
MODEL = 'gptoss'

sys.dont_write_bytecode = True
sys.path.insert(0, str(R2_DIR))
module_spec = importlib.util.spec_from_file_location('_v9_parallel_r2', R2_ENTRY)
r2 = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = r2
module_spec.loader.exec_module(r2)
batch = r2.batch


def read(path):
    return json.loads(path.read_text())


def create_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def status(stage, **fields):
    batch.save(LOG / 'status.json', {
        'stage': stage, 'batch': BATCH, 'auxiliary': 'parallel-gptoss-r2',
        'model': MODEL, 'gpus': [0], 'excluded_models': ['deepseek_pro'],
        'updated': time.strftime('%Y-%m-%d %H:%M:%S %z'), **fields,
    })


def event(event_name, **fields):
    row = {'time': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'event': event_name,
           'auxiliary': 'parallel-gptoss-r2', **fields}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    with (LOG / 'events.jsonl').open('a') as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + '\n')


@contextmanager
def locked(path):
    # The only R2 filesystem object this helper creates/opens for writing is
    # its explicitly shared mutex; flock does not change its contents.
    with path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def process_identity(pid):
    if type(pid) is not int or pid <= 1:
        raise RuntimeError('invalid R2 controller PID')
    fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
    if fields[0] in {'Z', 'X', 'x'}:
        raise RuntimeError('R2 controller is no longer alive')
    return {'pid': pid, 'birth': int(fields[19]), 'pgid': int(fields[2]),
            'sid': int(fields[3]),
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def capture_controller():
    submitted = read(R2_LOG / 'submitted.json')
    identity = process_identity(submitted.get('pid'))
    argv = [part.decode() for part in
            (Path('/proc') / str(identity['pid']) / 'cmdline').read_bytes().split(b'\0') if part]
    script_index = 1
    while script_index < len(argv) and argv[script_index] in {'-u', '-B'}:
        script_index += 1
    if (len(argv) != script_index + 3
            or Path(argv[script_index]).resolve() != R2_ENTRY.resolve()
            or set(argv[script_index + 1:]) != {'--run', '--cleanup-approved'}):
        raise RuntimeError('R2 controller command does not match its submitted run')
    boot_wall = next(int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines()
                     if line.startswith('btime '))
    birth_wall = boot_wall + identity['birth'] / os.sysconf('SC_CLK_TCK')
    submitted_wall = datetime.strptime(submitted['time'], '%Y-%m-%d %H:%M:%S %z').timestamp()
    if abs(submitted_wall - birth_wall) > 15 or process_identity(identity['pid']) != identity:
        raise RuntimeError('R2 controller birth does not match its original submission')
    return identity


def controller_alive(checkpoint):
    try:
        identity = checkpoint['r2_controller']
        return process_identity(identity['pid']) == identity
    except (OSError, ValueError, IndexError, RuntimeError):
        return False


def inventory():
    manifest = read(r2.EFFECTIVE_MANIFEST)
    r2.require_effective_inventory(manifest)
    if any(item['key'] == 'deepseek_pro' for item in manifest['models']):
        raise RuntimeError('DeepSeek Pro must remain excluded')
    gptoss = next(item for item in manifest['models'] if item['key'] == MODEL)
    glm = next(item for item in manifest['models'] if item['key'] == 'glm')
    if gptoss['gpus'] != [0] or glm['gpus'] != [1] or gptoss['workers'] != 8:
        raise RuntimeError('unexpected GLM/gpt-oss GPU or worker mapping')
    return manifest, gptoss


def gptoss_fingerprint(spec):
    directory = r2.DATA / 'raw' / spec['result_slug']
    if directory.is_symlink():
        raise RuntimeError('gpt-oss result directory is a symlink')
    result = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise RuntimeError('gpt-oss result tree contains a symlink')
        if path.is_file():
            result[str(path.relative_to(directory))] = digest(path)
    return result


def dependencies():
    paths = [R2_DIR / name for name in r2.FINGERPRINTED_FILES]
    paths += [R2_DIR / 'overlay-fingerprint.json', JOB / 'frozen-fingerprint.json']
    return {str(path): digest(path) for path in paths}


def check_inputs():
    r2.check_inputs()
    expected = read(AUX / 'fingerprint.json')
    actual = {name: digest(AUX / name) for name in (ENTRY_NAME, 'checkpoint.json')}
    if actual != expected:
        raise RuntimeError('auxiliary code or checkpoint changed')
    checkpoint = read(AUX / 'checkpoint.json')
    if dependencies() != checkpoint['r2_dependencies']:
        raise RuntimeError('immutable R2 dependencies changed')
    manifest, spec = inventory()
    current = gptoss_fingerprint(spec)
    if any(current.get(path) != value for path, value in checkpoint['preserved_gptoss'].items()):
        raise RuntimeError('an existing gpt-oss raw result was overwritten or removed')
    return checkpoint, manifest, spec


def glm_ready():
    path = R2_LOG / 'events.jsonl'
    if not path.is_file():
        return False
    text = path.read_text()
    lines = text.splitlines()
    if text and not text.endswith('\n'):
        lines = lines[:-1]  # Do not mistake an in-progress append for evidence.
    rows = [json.loads(line) for line in lines if line.strip()]
    queued = [index for index, row in enumerate(rows)
              if row.get('event') == 'model_queued' and row.get('model') == 'glm']
    if not queued:
        return False
    rows = rows[queued[-1] + 1:]
    started = {row.get('name') for row in rows if row.get('event') == 'process_started'
               and row.get('model') == 'glm' and type(row.get('pid')) is int}
    ready = {row.get('name') for row in rows if row.get('event') == 'service_ready'
             and row.get('model') == 'glm'}
    return {'glm-vllm', 'glm-proxy'} <= started & ready


def window(checkpoint):
    if not controller_alive(checkpoint):
        return 'closed'
    try:
        state = read(R2_LOG / 'status.json')
    except (OSError, ValueError):
        return 'wait'  # R2 writes its mutable status in place; retry a torn read.
    stage, model = state.get('stage'), state.get('current_model')
    if stage == 'recovery_started':
        return 'wait'
    if stage != 'treatment':
        return 'closed'
    if model in {'minimax', 'deepseek_flash', 'qwen'}:
        return 'wait'
    if model != 'glm':
        return 'closed'
    if not glm_ready():
        return 'wait'
    # Require the same live window after reading readiness evidence.
    try:
        final = read(R2_LOG / 'status.json')
    except (OSError, ValueError):
        return 'wait'
    return ('open' if controller_alive(checkpoint) and final.get('stage') == 'treatment'
            and final.get('current_model') == 'glm' else 'closed')


def prepare():
    if AUX.exists() or LOG.exists():
        raise RuntimeError('auxiliary artifacts already exist; refusing overwrite')
    r2.check_inputs()
    manifest, spec = inventory()
    identity = capture_controller()
    checkpoint = {'batch': BATCH, 'r2_controller': identity,
                  'r2_dependencies': dependencies(),
                  'preserved_gptoss': gptoss_fingerprint(spec),
                  'result_slug': spec['result_slug'], 'excluded_models': ['deepseek_pro'],
                  'r2_effective_manifest': str(r2.EFFECTIVE_MANIFEST)}
    if checkpoint['preserved_gptoss'].keys() != {'A/fs_destruction/A_fs_001.json'}:
        raise RuntimeError('auxiliary admission requires only the preserved gpt-oss first task')
    if window(checkpoint) == 'closed':
        raise RuntimeError('R2 GLM admission window has already been missed')
    AUX.mkdir()
    LOG.mkdir()
    shutil.copy2(ROOT / 'jobs' / ENTRY_NAME, AUX / ENTRY_NAME)
    create_json(AUX / 'checkpoint.json', checkpoint)
    create_json(AUX / 'fingerprint.json', {
        name: digest(AUX / name) for name in (ENTRY_NAME, 'checkpoint.json')})
    status('prepared', r2_controller=identity, result_slug=spec['result_slug'])
    event('prepared', model=MODEL, r2_controller_pid=identity['pid'])


def stop_admission(process):
    if process.poll() is None:
        process.terminate()
        # Let gpu-idle and the admitted child finish their own safe teardown.
        # Do not SIGKILL the admission wrapper and orphan its reservation.
        process.wait(timeout=120)


def watch():
    with locked(AUX / 'watcher.lock'):
        checkpoint, _, _ = check_inputs()
        if read(LOG / 'status.json').get('stage') != 'prepared':
            raise RuntimeError('auxiliary already submitted; no implicit restart')
        create_json(LOG / 'submitted.json', {'pid': os.getpid(),
                    'time': time.strftime('%Y-%m-%d %H:%M:%S %z')})
        status('waiting_for_glm')
        while True:
            gate = window(checkpoint)
            if gate == 'closed':
                status('missed_window', gpu_requested=False)
                return 0
            if gate == 'open':
                break
            time.sleep(10)
        check_inputs()
        if window(checkpoint) != 'open':
            status('missed_window', gpu_requested=False)
            return 0
        status('gpu0_admission_requested')
        command = [str(ROOT / 'bin/gpu-idle'), 'run', '--gpus', '0', '--timeout', '300', '--',
                   sys.executable, str(AUX / ENTRY_NAME), '--execute', '--cleanup-approved']
        process = subprocess.Popen(command)
        try:
            while process.poll() is None:
                # Once committed, GLM may finish normally and R2 may queue its
                # own gpt-oss admission behind us. Finish the owned lifecycle.
                if not (LOG / 'execution-started.json').exists() and window(checkpoint) == 'closed':
                    stop_admission(process)
                    status('missed_window', gpu_requested=True)
                    return 0
                time.sleep(1)
            code = process.wait()
            if not (LOG / 'execution-started.json').exists():
                status('admission_finished_without_execution', exit_code=code)
            event('auxiliary_exited', model=MODEL, exit_code=code)
            return code
        except BaseException:
            stop_admission(process)
            raise


def configure_lifecycle():
    # This mutates only this auxiliary process's imported module objects, not
    # the live R2 process or any file in its immutable recovery directory.
    r2.LOG = LOG
    r2.event = event
    batch.LOG = LOG
    batch.MANIFEST = r2.EFFECTIVE_MANIFEST
    batch.event = event
    batch.Lifecycle = r2.RecoveryLifecycle
    batch.cleanup_processes = r2.cleanup_model
    batch.cleanup_containers = r2.cleanup_containers


def execute():
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '0':
        raise RuntimeError('auxiliary execution requires the GPU0 admission reservation')
    with locked(AUX / 'execution.lock'):
        # Taken inside the GPU reservation; released only after all owned
        # services and containers are closed, before gpu-idle releases GPU0.
        with locked(R2_DIR / 'gptoss.lock'):
            checkpoint, manifest, spec = check_inputs()
            r2.check_images()
            if window(checkpoint) != 'open':
                status('missed_window', gpu_requested=True)
                return 0
            if gptoss_fingerprint(spec) != checkpoint['preserved_gptoss']:
                raise RuntimeError('gpt-oss acquired new results before auxiliary admission')
            existing = subprocess.check_output(['docker', 'ps', '-aq', '--filter',
                'label=rick-saber.batch=' + BATCH, '--filter',
                'label=rick-saber.model=' + MODEL], text=True).split()
            if existing:
                raise RuntimeError('gpt-oss containers already exist; refusing duplicate execution')
            if window(checkpoint) != 'open':
                status('missed_window', gpu_requested=True)
                return 0
            create_json(LOG / 'execution-started.json', {'pid': os.getpid(),
                        'time': time.strftime('%Y-%m-%d %H:%M:%S %z')})
            configure_lifecycle()
            status('running', model=MODEL)
            failure = None
            try:
                batch.run_model(manifest, MODEL)
            except BaseException as error:
                failure = error
            finally:
                cleanup_errors = []
                for cleanup in (r2.cleanup_model, r2.cleanup_containers):
                    try:
                        cleanup(MODEL)
                    except Exception as error:
                        cleanup_errors.append(type(error).__name__)
                check_inputs()
                if cleanup_errors:
                    status('cleanup_failed', cleanup_error_types=cleanup_errors,
                           primary_error_type=type(failure).__name__ if failure else None)
                    raise RuntimeError('auxiliary gpt-oss cleanup is not confirmed safe') from failure
            if failure:
                status('technical_failed', failure_type=type(failure).__name__, cleanup_safe=True)
                raise failure
            status('completed', cleanup_safe=True)
            return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--watch', action='store_true')
    modes.add_argument('--execute', action='store_true')
    parser.add_argument('--cleanup-approved', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
        return 0
    if not args.cleanup_approved:
        parser.error('scoped cleanup approval is required')
    if Path(__file__).resolve() != (AUX / ENTRY_NAME).resolve():
        os.execv(sys.executable, [sys.executable, str(AUX / ENTRY_NAME), *sys.argv[1:]])
    def interrupted(signum, frame):
        raise KeyboardInterrupt('auxiliary interrupted by signal ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    return watch() if args.watch else execute()


if __name__ == '__main__':
    raise SystemExit(main())
