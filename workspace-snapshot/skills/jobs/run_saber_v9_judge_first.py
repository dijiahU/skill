"""Queue provisional DeepSeek judging after treatment, before fixture repairs.

The original treatment gate remains unchanged and may correctly report failure.
This separately authorized workflow accepts recorded technical failures, not
missing inputs, changing raw data, unsafe teardown, or another active GPU job.
It never creates or cleans Docker containers and never rewrites raw results.
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
BASE_LOG = ROOT / 'logs' / ('saber-' + BATCH)
PARALLEL = JOB / 'parallel-gptoss-r2'
PARALLEL_LOG = BASE_LOG / 'parallel-gptoss-r2'
PLAN = JOB / 'judge-first-r2'
LOG = BASE_LOG / 'judge-first-r2'
ENTRY_NAME = 'run_saber_v9_judge_first.py'
JUDGE_ENTRY = 'saber_v9_judge_first_entry.py'
MANIFEST = PLAN / 'effective-manifest.json'
AUDIT = LOG / 'technical-audit'
OUTPUT = ROOT / 'results' / ('saber-' + BATCH) / 'judged-provisional-r2'
JUDGE_MODELS = ['mistral', 'minimax', 'deepseek_flash', 'glm', 'gptoss']
EXCLUDED = ['deepseek_pro', 'qwen']
EXPECTED = 3580
OWN_MODEL = 'judge_first'
FILES = (ENTRY_NAME, JUDGE_ENTRY, 'effective-manifest.json', 'checkpoint.json')

sys.dont_write_bytecode = True
module_spec = importlib.util.spec_from_file_location(
    '_judge_first_parallel', PARALLEL / 'run_saber_v9_parallel_gptoss.py')
aux = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = aux
module_spec.loader.exec_module(aux)
r2, batch = aux.r2, aux.r2.batch


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def status(stage, **fields):
    batch.save(LOG / 'status.json', {
        'stage': stage, 'batch': BATCH, 'workflow': 'judge-first-r2',
        'provisional': True, 'repairs_deferred': True,
        'excluded_models': EXCLUDED, 'total_expected': EXPECTED,
        'updated': time.strftime('%Y-%m-%d %H:%M:%S %z'), **fields,
    })


def event(event_name, **fields):
    row = {'time': time.strftime('%Y-%m-%d %H:%M:%S %z'),
           'event': event_name, 'workflow': 'judge-first-r2', **fields}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    with (LOG / 'events.jsonl').open('a') as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + '\n')


@contextmanager
def locked(path, readonly=False):
    with path.open('r' if readonly else 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def dependencies():
    result = aux.dependencies()
    for name in ('run_saber_v9_parallel_gptoss.py', 'checkpoint.json', 'fingerprint.json'):
        path = PARALLEL / name
        result[str(path)] = digest(path)
    return result


def alive(identity):
    try:
        return aux.process_identity(identity['pid']) == identity
    except (OSError, ValueError, IndexError, RuntimeError):
        return False


def capture_auxiliary():
    submitted = read(PARALLEL_LOG / 'submitted.json')
    identity = aux.process_identity(submitted['pid'])
    argv = [item.decode() for item in
            (Path('/proc') / str(identity['pid']) / 'cmdline').read_bytes().split(b'\0') if item]
    expected = [str(PARALLEL / 'run_saber_v9_parallel_gptoss.py'),
                '--watch', '--cleanup-approved']
    if argv[1:] != expected or identity['sid'] != identity['pid'] or identity['pgid'] != identity['pid']:
        raise RuntimeError('parallel controller identity does not match its submitted entry')
    boot_wall = next(int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines()
                     if line.startswith('btime '))
    birth_wall = boot_wall + identity['birth'] / os.sysconf('SC_CLK_TCK')
    submit_wall = datetime.strptime(submitted['time'], '%Y-%m-%d %H:%M:%S %z').timestamp()
    if abs(birth_wall - submit_wall) > 15 or not alive(identity):
        raise RuntimeError('parallel controller birth mismatch')
    return identity


def check_inputs():
    r2.check_inputs()
    expected = read(PLAN / 'fingerprint.json')
    if {name: digest(PLAN / name) for name in FILES} != expected:
        raise RuntimeError('judge-first frozen entry or checkpoint changed')
    checkpoint = read(PLAN / 'checkpoint.json')
    if dependencies() != checkpoint['dependencies']:
        raise RuntimeError('treatment or parallel dependencies changed')
    manifest = read(MANIFEST)
    require_judge_inventory(manifest)
    original = read(r2.EFFECTIVE_MANIFEST)
    selected = [model for model in original['models'] if model['key'] in JUDGE_MODELS]
    if (manifest['models'] != selected or manifest['task_ids'] != original['task_ids']
            or manifest['raw'] != original['raw'] or manifest['frozen'] != original['frozen']
            or manifest['judged'] != str(OUTPUT)
            or manifest.get('judge_before_repairs') is not True):
        raise RuntimeError('judge-first scope or output location changed')
    if qwen_fingerprint() != checkpoint['preserved_qwen_fingerprint']:
        raise RuntimeError('deferred Qwen results changed after the user-requested stop')
    return checkpoint, manifest


def require_judge_inventory(manifest):
    if ([model['key'] for model in manifest['models']] != JUDGE_MODELS
            or len(manifest['task_ids']) != 716 or len(set(manifest['task_ids'])) != 716
            or manifest.get('total_expected') != EXPECTED):
        raise RuntimeError('judge scope must be five complete non-Qwen local models')


def qwen_fingerprint():
    directory = r2.DATA / 'raw/codex_qwen_treatment_v9_full_20260905_r1_codex-native-safety-orchestrator'
    if directory.is_symlink():
        raise RuntimeError('deferred Qwen result directory is a symlink')
    result = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise RuntimeError('deferred Qwen result tree contains a symlink')
        if path.is_file():
            result[str(path.relative_to(directory))] = digest(path)
    return result


def require_qwen_and_previous_judge_stopped():
    if read(aux.R2_LOG / 'qwen/lifecycle-outcome.json').get('cleanup_safe') is not True:
        raise RuntimeError('Qwen cleanup is not confirmed')
    qwen_pid = read(aux.R2_LOG / 'qwen/submitted.json')['pid']
    if (Path('/proc') / str(qwen_pid)).exists():
        raise RuntimeError('Qwen controller has not exited')
    remaining = subprocess.check_output(['docker', 'ps', '-aq', '--filter',
        'label=rick-saber.batch=' + BATCH, '--filter', 'label=rick-saber.model=qwen'], text=True).split()
    if remaining:
        raise RuntimeError('Qwen containers have not exited')
    previous_log = BASE_LOG / 'judge-first-r1'
    previous_pid = read(previous_log / 'submitted.json')['pid']
    if (Path('/proc') / str(previous_pid)).exists() or (previous_log / 'execution-started.json').exists():
        raise RuntimeError('previous six-model Judge is not confirmed unstarted and stopped')
    with locked(JOB / 'judge-first-r1/watcher.lock', readonly=True):
        pass
    return {'qwen_controller_pid': qwen_pid, 'previous_judge_watcher_pid': previous_pid}


def prepare():
    if PLAN.exists() or LOG.exists() or OUTPUT.exists():
        raise RuntimeError('judge-first artifacts already exist; refusing overwrite')
    aux.check_inputs()
    manifest = read(r2.EFFECTIVE_MANIFEST)
    r2.require_effective_inventory(manifest)
    stopped = require_qwen_and_previous_judge_stopped()
    preserved_qwen = qwen_fingerprint()
    checkpoint = {
        'batch': BATCH, 'r2_controller': aux.capture_controller(),
        'parallel_controller': capture_auxiliary(), 'dependencies': dependencies(),
        'authorization': 'User explicitly requested stopping/skipping Qwen, then GLM and gpt-oss, then Judge before separate reruns.',
        'technical_failures_allowed_for_provisional_judging': True,
        'raw_mutation_allowed': False, 'docker_cleanup_allowed': False,
        'excluded_models': EXCLUDED, 'replaced_scope': stopped,
        'preserved_qwen_fingerprint': preserved_qwen,
        'deferred_qwen_result_files': len(preserved_qwen),
    }
    manifest['models'] = [model for model in manifest['models'] if model['key'] in JUDGE_MODELS]
    manifest.update(judged=str(OUTPUT), provisional=True, judge_before_repairs=True,
                    repairs_deferred=True, total_expected=EXPECTED, excluded_models=EXCLUDED,
                    qwen_deferred_by_user=True, qwen_preserved_result_files=len(preserved_qwen))
    require_judge_inventory(manifest)
    PLAN.mkdir()
    LOG.mkdir()
    for name in (ENTRY_NAME, JUDGE_ENTRY):
        shutil.copy2(ROOT / 'jobs' / name, PLAN / name)
    create_json(MANIFEST, manifest)
    create_json(PLAN / 'checkpoint.json', checkpoint)
    create_json(PLAN / 'fingerprint.json', {name: digest(PLAN / name) for name in FILES})
    status('prepared', output=str(OUTPUT))
    event('prepared', expected=EXPECTED, gpus=[0, 1], qwen_preserved_result_files=len(preserved_qwen))


def gate(checkpoint):
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != checkpoint['r2_controller']['boot_id']:
        return 'closed'
    try:
        state = read(aux.R2_LOG / 'status.json')
    except (OSError, ValueError):
        return 'wait'
    if alive(checkpoint['r2_controller']):
        return 'wait'
    if (state.get('stage') != 'treatment_failed'
            or state.get('treatment_queue_finished') is not True):
        return 'closed'
    if alive(checkpoint['parallel_controller']):
        return 'wait'
    return 'open'


def assert_no_containers(model=None):
    # Read-only absence check; this workflow never issues docker stop/rm/kill.
    ids = subprocess.check_output(['docker', 'ps', '-aq', '--filter',
                                  'label=rick-saber.batch=' + BATCH], text=True).split()
    if ids:
        raise RuntimeError('treatment containers remain; no cleanup is authorized here')


def require_safe_treatment_exit():
    records = []
    for model in r2.REMAINING:
        directory = aux.R2_LOG / model
        if read(directory / 'lifecycle-outcome.json').get('cleanup_safe') is not True:
            raise RuntimeError('treatment cleanup not confirmed: ' + model)
        records.extend(read(directory / 'process-identities.json'))
    if (PARALLEL_LOG / 'execution-started.json').exists():
        directory = PARALLEL_LOG / 'gptoss'
        if read(directory / 'lifecycle-outcome.json').get('cleanup_safe') is not True:
            raise RuntimeError('parallel cleanup not confirmed')
        records.extend(read(directory / 'process-identities.json'))
    # No old process is adopted or signalled. A matching live session is a
    # reason to refuse entry even if a stale status claimed cleanup completed.
    live = [row for row in r2.ownership._scan().values() if row['state'] not in ('Z', 'X', 'x')]
    for row in records:
        identity = row.get('identity')
        sid = identity['sid'] if identity else row['pid']
        pgid = identity['pgid'] if identity else row['pid']
        if any(process['sid'] == sid or process['pgid'] == pgid for process in live):
            raise RuntimeError('a prior treatment process session remains active')
    assert_no_containers()


def freeze_audit(manifest):
    from saber_treatment_v9_audit import validate_model
    before = r2.raw_fingerprint()
    expected = set(manifest['task_ids'])
    reports = {}
    for model in manifest['models']:
        directory = Path(manifest['raw']) / model['result_slug']
        paths = list(directory.rglob('*.json'))
        if len(paths) != 716 or {path.stem for path in paths} != expected:
            raise RuntimeError('complete unique result inventory is required: ' + model['key'])
        for path in paths:
            data = read(path)
            if (not isinstance(data, dict) or data.get('id') != path.stem
                    or path.relative_to(directory).parts != (
                        data.get('scenario'), data.get('category'), data.get('id', '') + '.json')):
                raise RuntimeError('raw identity/path is not safely judgeable: ' + model['key'])
        reports[model['key']] = validate_model(directory, batch.FROZEN / 'saber/tasks',
                                              manifest['task_ids'], require_full=True)
    if before != r2.raw_fingerprint():
        raise RuntimeError('raw inputs changed during pre-judge audit')
    for key, report in reports.items():
        create_json(AUDIT / (key + '.json'), report)
    create_json(LOG / 'raw-fingerprint-before-judge.json', before)
    create_json(LOG / 'pre-judge-report.json', {
        'provisional': True, 'repairs_deferred': True,
        'technical_gate_passed': all(report['passed'] for report in reports.values()),
        'technical_failures_allowed_by_user': True,
        'models': {key: report['totals'] for key, report in reports.items()},
        'pending_reruns': {key: [row['task_id'] for row in report['rows'] if not row['passed']]
                          for key, report in reports.items()},
        'excluded_models': EXCLUDED, 'output': str(OUTPUT),
    })
    return before


def execute():
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '0,1':
        raise RuntimeError('judge requires both reserved physical GPUs')
    with locked(PLAN / 'execution.lock'):
        checkpoint, manifest = check_inputs()
        # Hold the stopped treatment pipeline mutex to exclude any competing
        # continuation while raw inputs are audited and judged.
        with locked(r2.RECOVERY / 'pipeline.lock', readonly=True):
            if gate(checkpoint) != 'open':
                raise RuntimeError('treatment queue is not fully stopped')
            require_safe_treatment_exit()
            if OUTPUT.exists():
                raise RuntimeError('provisional output already exists; no implicit rerun')
            before = freeze_audit(manifest)
            create_json(LOG / 'execution-started.json', {
                'pid': os.getpid(), 'time': time.strftime('%Y-%m-%d %H:%M:%S %z')})
            r2.LOG = LOG
            r2.event = event
            batch.LOG = LOG
            batch.event = event
            batch.cleanup_containers = assert_no_containers
            life = r2.RecoveryLifecycle(OWN_MODEL)
            status('judge_loading', gpus=[0, 1], output=str(OUTPUT))
            try:
                spec = next(model for model in manifest['models'] if model['key'] == 'deepseek_flash')
                batch.services_start(life, spec)
                process = life.spawn('deepseek-provisional-judge', [
                    str(ROOT / 'envs/deepseekv4-vllm/bin/python'),
                    str(PLAN / JUDGE_ENTRY), str(MANIFEST), str(AUDIT)])
                status('judging', expected=EXPECTED, workers=8, gpus=[0, 1], output=str(OUTPUT))
                event('judge_started', expected=EXPECTED, workers=8, technical_failures_retained=True)
                code = process.wait()
                if code:
                    raise RuntimeError('provisional judge consumer failed: ' + str(code))
                if before != r2.raw_fingerprint():
                    raise RuntimeError('raw inputs changed during judging')
                check_inputs()
            finally:
                life.close()
            status('provisional_judge_complete', repairs_pending=True, output=str(OUTPUT))
            event('provisional_judge_complete', repairs_pending=True)
    return 0


def watch():
    with locked(PLAN / 'watcher.lock'):
        checkpoint, _ = check_inputs()
        if read(LOG / 'status.json').get('stage') != 'prepared':
            raise RuntimeError('judge-first already submitted; no implicit restart')
        create_json(LOG / 'submitted.json', {
            'pid': os.getpid(), 'time': time.strftime('%Y-%m-%d %H:%M:%S %z')})
        status('waiting_for_treatment', gpus_reserved=False)
        event('waiting_for_treatment', main_pid=checkpoint['r2_controller']['pid'])
        next_report = time.monotonic() + 1800
        while True:
            value = gate(checkpoint)
            if value == 'closed':
                status('blocked_treatment_incomplete_or_unexpected_exit', requires_attention=True)
                return 1
            if value == 'open':
                break
            if time.monotonic() >= next_report:
                event('still_waiting_for_treatment')
                next_report = time.monotonic() + 1800
            time.sleep(30)
        check_inputs()
        require_safe_treatment_exit()
        status('gpu_admission_queued', gpus=[0, 1])
        process = subprocess.Popen([
            str(ROOT / 'bin/gpu-idle'), 'run', '--gpus', '0,1', '--timeout', '86400', '--',
            sys.executable, str(PLAN / ENTRY_NAME), '--execute', '--judge-before-repairs'])
        try:
            code = process.wait()
        except BaseException:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=120)
            raise
        if code:
            status('judge_job_failed', exit_code=code, requires_attention=True, output=str(OUTPUT))
        event('judge_job_exited', exit_code=code)
        return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--watch', action='store_true')
    modes.add_argument('--execute', action='store_true')
    parser.add_argument('--judge-before-repairs', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
        return 0
    if not args.judge_before_repairs:
        parser.error('explicit judge-before-repairs workflow authorization is required')
    if Path(__file__).resolve() != (PLAN / ENTRY_NAME).resolve():
        os.execv(sys.executable, [sys.executable, str(PLAN / ENTRY_NAME), *sys.argv[1:]])
    def interrupted(signum, frame):
        raise KeyboardInterrupt('judge-first interrupted by signal ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    try:
        return watch() if args.watch else execute()
    except BaseException as error:
        event('judge_first_failed', error_type=type(error).__name__)
        status('judge_scheduler_failed' if args.watch else 'judge_execution_failed',
               error_type=type(error).__name__, requires_attention=True)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
