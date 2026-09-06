"""Resume failed provisional Judge records with direct local HTTP transport."""

import argparse
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path('/2024233123/skills')
BATCH = 'v9-full-20260905-r1'
JOB = ROOT / 'jobs' / ('saber-' + BATCH)
BASE_LOG = ROOT / 'logs' / ('saber-' + BATCH)
PRIOR = JOB / 'judge-first-r2'
PRIOR_LOG = BASE_LOG / 'judge-first-r2'
PLAN = JOB / 'judge-resume-r4'
LOG = BASE_LOG / 'judge-resume-r4'
ENTRY = 'run_saber_v9_judge_resume_r4.py'
OWNER = 'judge_resume_r4'
PYTHON = ROOT / 'envs/deepseekv4-vllm/bin/python'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


old = module('_judge_resume_prior', PRIOR / 'run_saber_v9_judge_first.py')
read, digest, create_json = old.read, old.digest, old.create_json


def event(event_name, **fields):
    row = {'time': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'event': event_name, **fields}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    with (LOG / 'events.jsonl').open('a') as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def status(stage, **fields):
    old.batch.save(LOG / 'status.json', {
        'stage': stage, 'workflow': 'judge-resume-r4', 'batch': BATCH,
        'updated': time.strftime('%Y-%m-%d %H:%M:%S %z'),
        'output': str(old.OUTPUT), 'provisional': True, 'formal': False,
        'repairs_deferred': True, **fields,
    })


def direct_environment(source):
    env = {key: value for key, value in source.items()
           if key.lower() not in {'http_proxy', 'https_proxy', 'all_proxy'}}
    hosts = []
    for value in (source.get('NO_PROXY', ''), source.get('no_proxy', ''),
                  'localhost,127.0.0.1,::1'):
        for host in value.split(','):
            if host.strip() and host.strip() not in hosts:
                hosts.append(host.strip())
    env['NO_PROXY'] = env['no_proxy'] = ','.join(hosts)
    return env


def healthy():
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://127.0.0.1:18020/health', timeout=5) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def prepare():
    if PLAN.exists() or LOG.exists():
        raise RuntimeError('recovery artifacts already exist; refusing overwrite')
    old.check_inputs()
    previous = []
    for filename in ('submitted.json', 'execution-started.json'):
        pid = read(PRIOR_LOG / filename)['pid']
        try:
            identity = old.aux.process_identity(pid)
        except (OSError, ValueError, IndexError, RuntimeError):
            continue
        argv = (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0')
        if str(PRIOR / 'run_saber_v9_judge_first.py').encode() not in argv:
            raise RuntimeError('previous controller PID has an unexpected identity')
        previous.append(identity)
    PLAN.mkdir()
    LOG.mkdir()
    shutil.copy2(Path(__file__), PLAN / ENTRY)
    create_json(PLAN / 'checkpoint.json', {
        'entry_sha256': digest(PLAN / ENTRY),
        'binding_sha256': digest(old.OUTPUT / 'run_metadata.json'),
        'previous_processes': previous,
        'authorization': 'User requested continuing remaining failed Judge scores.',
        'raw_mutation_allowed': False, 'docker_cleanup_allowed': False,
        'successful_judgments_preserved': True,
        'transport': 'direct localhost, proxy variables removed only from new job',
    })
    status('prepared')
    event('prepared')


def check_inputs():
    cp = read(PLAN / 'checkpoint.json')
    if digest(PLAN / ENTRY) != cp['entry_sha256']:
        raise RuntimeError('frozen continuation entry changed')
    if digest(old.OUTPUT / 'run_metadata.json') != cp['binding_sha256']:
        raise RuntimeError('original Judge binding changed')
    old.check_inputs()
    return cp


def require_previous_stopped():
    cp = check_inputs()
    if any(old.alive(identity) for identity in cp['previous_processes']):
        raise RuntimeError('previous Judge controller remains active')
    terminal = {'judge_job_failed', 'judge_execution_failed', 'provisional_judge_complete'}
    if read(PRIOR_LOG / 'status.json').get('stage') not in terminal:
        raise RuntimeError('previous Judge has no expected terminal status')
    directory = PRIOR_LOG / 'judge_first'
    if read(directory / 'lifecycle-outcome.json').get('cleanup_safe') is not True:
        raise RuntimeError('previous Judge teardown is not confirmed safe')
    live = [row for row in old.r2.ownership._scan().values()
            if row['state'] not in ('Z', 'X', 'x')]
    for record in read(directory / 'process-identities.json'):
        identity = record.get('identity')
        if not identity:
            raise RuntimeError('previous service identity is missing')
        if any(row['sid'] == identity['sid'] or row['pgid'] == identity['pgid']
               for row in live):
            raise RuntimeError('previous Judge process family remains active')
    failed_directory = BASE_LOG / 'judge-resume-r3' / 'judge_resume_r3'
    if read(failed_directory / 'lifecycle-outcome.json').get('cleanup_safe') is not True:
        raise RuntimeError('earlier continuation teardown is not confirmed safe')
    for record in read(failed_directory / 'process-identities.json'):
        identity = record.get('identity')
        if not identity or any(row['sid'] == identity['sid'] or row['pgid'] == identity['pgid']
                               for row in live):
            raise RuntimeError('earlier continuation process family remains active')
    old.require_safe_treatment_exit()
    with old.locked(PRIOR / 'execution.lock', readonly=True):
        pass
    with old.locked(old.OUTPUT / '.judge.lock', readonly=True):
        pass


def inventory():
    entry = module('_judge_resume_inventory', PRIOR / old.JUDGE_ENTRY)
    judge = entry.ProvisionalJudge(old.MANIFEST, old.AUDIT)
    if read(old.OUTPUT / 'run_metadata.json') != judge.binding:
        raise RuntimeError('original raw, audit or Judge binding no longer matches')
    # load_model writes only for unreadable sources; reject these before calling it.
    for spec in judge.manifest['models']:
        for task_id, (_, relative) in judge.tasks.items():
            raw = read(Path(judge.manifest['raw']) / spec['result_slug'] / relative)
            if not isinstance(raw, dict) or raw.get('id') != task_id:
                raise RuntimeError('raw source cannot be inventoried read-only')
    judge.configure_frozen_judge()
    pending, preserved = {}, {}
    for spec in judge.manifest['models']:
        judge.load_model(spec)
        pending[spec['key']] = []
        for task, result in judge.current_pairs:
            path = judge.record_path(spec['result_slug'], task['id'])
            existing = read(path) if path.is_file() else None
            if judge.usable(existing, result):
                preserved[str(path.relative_to(old.OUTPUT))] = digest(path)
            else:
                pending[spec['key']].append(task['id'])
    return {'pending': pending, 'pending_count': sum(map(len, pending.values())),
            'preserved_usable_sha256': preserved,
            'raw_fingerprint': old.r2.raw_fingerprint()}


def verify_preserved(plan):
    for relative, expected in plan['preserved_usable_sha256'].items():
        if digest(old.OUTPUT / relative) != expected:
            raise RuntimeError('a previously successful judgment changed: ' + relative)
    if old.r2.raw_fingerprint() != plan['raw_fingerprint']:
        raise RuntimeError('raw treatment data changed')
    check_inputs()


def counts():
    result = {}
    for spec in read(old.MANIFEST)['models']:
        records = [read(path) for path in
                   (old.OUTPUT / spec['result_slug']).glob('[ABC]/*/*.json')]
        usable = sum(row.get('judge_status') == 'usable' for row in records)
        result[spec['key']] = {'usable': usable, 'remaining': 716 - usable}
    return result


def watch():
    with old.locked(PLAN / 'watcher.lock'):
        cp = check_inputs()
        if read(LOG / 'status.json')['stage'] != 'prepared':
            raise RuntimeError('continuation already submitted')
        create_json(LOG / 'submitted.json', {
            'pid': os.getpid(), 'identity': old.aux.process_identity(os.getpid()),
            'time': time.strftime('%Y-%m-%d %H:%M:%S %z')})
        status('waiting_for_previous_judge', gpus_reserved=False)
        event('waiting_for_previous_judge')
        while any(old.alive(identity) for identity in cp['previous_processes']):
            time.sleep(30)
        require_previous_stopped()
        with old.locked(old.OUTPUT / '.judge.lock', readonly=True):
            plan = inventory()
            create_json(PLAN / 'recovery-plan.json', plan)
            paths = [old.OUTPUT / 'run_metadata.json', old.OUTPUT / '_all_summary.json']
            paths.extend(old.OUTPUT.glob('*/summary.json'))
            for path in paths:
                if path.is_file():
                    create_json(LOG / 'before-recovery' / path.relative_to(old.OUTPUT), read(path))
        event('remaining_frozen', pending={key: len(ids) for key, ids in plan['pending'].items()},
              preserved=len(plan['preserved_usable_sha256']))
        if not plan['pending_count']:
            status('nothing_to_retry', models=counts())
            return 0
        status('gpu_admission_queued', gpus=[0, 1], pending=plan['pending_count'])
        process = subprocess.Popen([
            str(ROOT / 'bin/gpu-idle'), 'run', '--gpus', '0,1', '--timeout', '86400', '--',
            str(PYTHON), str(PLAN / ENTRY), '--execute'], env=direct_environment(os.environ))
        try:
            code = process.wait()
        except BaseException:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=120)
            raise
        if code:
            status('recovery_failed', exit_code=code, requires_attention=True, models=counts())
        event('recovery_job_exited', exit_code=code)
        return code


def execute():
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '0,1':
        raise RuntimeError('Judge requires both reserved physical GPUs')
    clean = direct_environment(os.environ)
    for key in list(os.environ):
        if key.lower() in {'http_proxy', 'https_proxy', 'all_proxy'}:
            del os.environ[key]
    os.environ.update(clean)
    with ExitStack() as stack:
        stack.enter_context(old.locked(PLAN / 'execution.lock'))
        require_previous_stopped()
        stack.enter_context(old.locked(PRIOR / 'execution.lock', readonly=True))
        stack.enter_context(old.locked(old.r2.RECOVERY / 'pipeline.lock', readonly=True))
        plan = read(PLAN / 'recovery-plan.json')
        verify_preserved(plan)
        if inventory() != plan:
            raise RuntimeError('Judge inventory changed after continuation was prepared')
        create_json(LOG / 'execution-started.json', {
            'pid': os.getpid(), 'time': time.strftime('%Y-%m-%d %H:%M:%S %z'),
            'transport': 'direct localhost', 'proxy_variables_present': False})
        old.r2.LOG = old.batch.LOG = LOG
        old.r2.event = old.batch.event = event
        old.batch.cleanup_containers = old.assert_no_containers
        life = old.r2.RecoveryLifecycle(OWNER)
        try:
            status('judge_loading', gpus=[0, 1], pending=plan['pending_count'])
            spec = next(model for model in read(old.MANIFEST)['models']
                        if model['key'] == 'deepseek_flash')
            for service in spec['services']:
                if any(key.lower() in {'http_proxy', 'https_proxy', 'all_proxy'}
                       for key in service.get('env', {})):
                    raise RuntimeError('service config unexpectedly reintroduces a proxy')
            old.batch.services_start(life, spec)
            if not healthy():
                raise RuntimeError('direct local Judge health check failed')
            event('direct_health_verified')
            process = life.spawn('deepseek-provisional-judge', [
                str(PYTHON), str(PRIOR / old.JUDGE_ENTRY), str(old.MANIFEST), str(old.AUDIT)])
            status('judging', gpus=[0, 1], workers=8, models=counts(), transport='direct localhost')
            failures, next_check = 0, 0
            while process.poll() is None:
                if time.monotonic() >= next_check:
                    failures = 0 if healthy() else failures + 1
                    status('judging', gpus=[0, 1], workers=8, models=counts(),
                           transport='direct localhost', health_failures=failures)
                    if failures >= 3:
                        raise RuntimeError('local Judge health failed three consecutive checks')
                    next_check = time.monotonic() + 30
                time.sleep(5)
            verify_preserved(plan)
            remaining = inventory()['pending_count']
            summary = read(old.OUTPUT / '_all_summary.json')
            if (process.returncode or remaining or summary.get('complete') is not True
                    or summary.get('judge_failed') != 0 or summary.get('total') != 3580):
                raise RuntimeError('Judge continuation remains incomplete: ' + str(remaining))
            create_json(LOG / 'completion-validation.json', {
                'judge_usable': 3580, 'judge_failed': 0,
                'preserved_successful_records': len(plan['preserved_usable_sha256']),
                'raw_unchanged': True, 'technical_failures_deferred': summary['technical_fail'],
                'provisional': True, 'formal': False})
        finally:
            life.close()
        status('provisional_judge_complete', models=counts())
        event('provisional_judge_complete')
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ('prepare', 'watch', 'execute'):
        modes.add_argument('--' + mode, action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
        return 0
    if Path(__file__).resolve() != (PLAN / ENTRY).resolve():
        raise RuntimeError('execute the prepared frozen continuation entry')
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Judge continuation interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    try:
        return watch() if args.watch else execute()
    except BaseException as error:
        event('continuation_failed', error_type=type(error).__name__, error=str(error))
        status('scheduler_failed' if args.watch else 'execution_failed',
               error_type=type(error).__name__, error=str(error), requires_attention=True)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
