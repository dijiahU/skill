"""Persistent dependency queue: hold full evaluation until its launch plan is validated.

The preparation process supplies readiness.json and a source-bound launch plan.
Missing preparation never triggers a smoke run or a partial dataset evaluation.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def predecessor_reasons(directory):
    path = directory / 'predecessor.json'
    if not path.exists():
        return []
    dependency = json.loads(path.read_text())
    pid = dependency['pid']
    stat = Path(f'/proc/{pid}/stat')
    if stat.exists():
        fields = stat.read_text().rsplit(')', 1)[1].split()
        if fields[19] == dependency['birth'] and fields[0] != 'Z':
            return ['predecessor_running:' + dependency['job_id']]
    completion = Path(dependency['completion_file'])
    if not completion.is_file():
        return ['predecessor_missing_completion:' + dependency['job_id']]
    result = json.loads(completion.read_text())
    if set(result) != set(dependency['models']) or any(type(v) is not int for v in result.values()):
        return ['predecessor_incomplete_model_statuses']
    return []


def readiness(directory, request):
    dependency_reasons = predecessor_reasons(directory)
    if dependency_reasons:
        return dependency_reasons, None
    path = directory / 'readiness.json'
    if not path.is_file():
        return ['full_dataset_preparation', 'task_environment_compatibility',
                'source_bound_oracle_validation', 'full_deployment_validation',
                'full_evaluation_launcher'], None
    report = json.loads(path.read_text())
    reasons = []
    if report.get('request_sha256') != sha256(directory / 'request.json'):
        reasons.append('readiness_request_mismatch')
    for name in ('dataset_complete', 'environment_compatible', 'oracle_validated',
                 'full_deployment_validated', 'launcher_validated'):
        if report.get(name) is not True:
            reasons.append(name)
    if report.get('task_names') != request['task_names']:
        reasons.append('task_list_mismatch')
    bindings = report.get('validated_files_sha256', {})
    plan_path = directory / 'launch-plan.json'
    if str(plan_path) not in bindings:
        reasons.append('launch_plan_not_bound')
    for name, expected in bindings.items():
        p = Path(name)
        if not p.is_file() or sha256(p) != expected:
            reasons.append('validation_stale:' + name)
    if reasons:
        return reasons, None
    plan = json.loads(plan_path.read_text())
    if plan.get('waves') != request['waves']:
        reasons.append('gpu_pairing_mismatch')
    if set(plan.get('models', {})) != set(request['models']):
        reasons.append('model_list_mismatch')
    for model, item in plan.get('models', {}).items():
        if item.get('gpus') != request['models'][model]['gpus']:
            reasons.append('gpu_reservation_mismatch:' + model)
        script = item.get('script', '')
        if script not in bindings or not Path(script).is_file():
            reasons.append('launcher_not_bound:' + model)
    return reasons, plan


def status(directory, state, reasons=None, **extra):
    value = {'state':state, 'updated_at':datetime.now(timezone.utc).isoformat(),
             'pending':reasons or [], **extra}
    (directory/'status.json').write_text(json.dumps(value,indent=2))
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    directory=args.directory.resolve()
    with (directory/'queue.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        request=json.loads((directory/'request.json').read_text())
        if (directory/'dispatch-started.json').exists():
            raise RuntimeError('Already dispatched; inspect persisted results before any retry')
        while True:
            try:
                reasons,plan=readiness(directory,request)
            except (ValueError,OSError,KeyError,TypeError) as exc:
                reasons,plan=['invalid_readiness:'+str(exc)],None
            if reasons:
                state = 'waiting_predecessor' if any(x.startswith('predecessor_') for x in reasons) else 'waiting_preparation'
                status(directory,state,reasons)
                if args.once:
                    print(json.dumps({'state':state,'pending':reasons}))
                    return
                time.sleep(30)
                continue
            if args.once:
                print(json.dumps({'state':'ready','launch_performed':False}))
                return
            with (directory/'dispatch-started.json').open('x') as marker:
                json.dump({'request_sha256':sha256(directory/'request.json'),
                           'readiness_sha256':sha256(directory/'readiness.json')},marker)
            def launch(model):
                item=plan['models'][model]
                command=['/srv/benchmark/skills/bin/gpu-idle','run','--gpus',
                         ','.join(map(str,item['gpus'])),'--timeout','604800','--',
                         'bash',item['script']]
                with (directory/(model+'-admission.log')).open('x') as log:
                    return subprocess.run(command,stdout=log,stderr=subprocess.STDOUT).returncode
            results={}
            for wave in plan['waves']:
                status(directory,'waiting_or_running_gpu_jobs',wave=wave,results=results)
                with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                    futures={m:pool.submit(launch,m) for m in wave}
                    results.update({m:f.result() for m,f in futures.items()})
                if any(results[m] for m in wave):
                    status(directory,'failed',results=results)
                    return
            status(directory,'completed',results=results)
            return


if __name__=='__main__':
    main()
