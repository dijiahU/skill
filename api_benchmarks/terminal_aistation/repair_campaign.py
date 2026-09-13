"""Repair campaign: verify all environments before model dispatch, retain every attempt."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def read(path):
    return json.loads(path.read_text())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args();root=args.directory.resolve();request=read(root/'request.json')
    def status(state,**extra):
        (root/'status.json').write_text(json.dumps({'state':state,'at':datetime.now(timezone.utc).isoformat(),**extra},indent=2))
    with (root/'campaign.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (root/'model-dispatch-started.json').exists():raise RuntimeError('Already dispatched')
        try:
            for name,sha in read(root/'source-sha256.json').items():
                if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise RuntimeError('Frozen input changed: '+name)
            validation=read(Path(request['pilot_validation']))
            if not all(validation[m]['passed'] for m in ['gptoss','glm']):raise RuntimeError('Paired model gate failed')
            oracle=read(Path(request['network_oracle'])/'result.json')
            if oracle['stats']['n_errored_trials'] or oracle['stats']['n_completed_trials']!=4:raise RuntimeError('Network gate failed')
            results={}
            if request.get('validated_environments'):
                evidence=read(Path(request['validated_environments']))
                results={task:item for task,item in evidence.items() if task in request['tasks'] and item.get('passed')}
                images=sorted({item[phase]['image'] for item in results.values() for phase in ('main','verifier')})
                if images:subprocess.run(['docker','image','inspect',*images],check=True,stdout=subprocess.DEVNULL)
            pending=[task for task in request['tasks'] if task not in results]
            (root/'environment-readiness.json').write_text(json.dumps({'passed':sorted(results),'pending':pending,'evidence':results},indent=2))
            for attempt in range(1,4):
                if not pending:break
                status('prebuilding_environments',attempt=attempt,remaining=len(pending),passed=len(results))
                output=root/('build-round-'+str(attempt))
                argv=[sys.executable,str(Path(__file__).with_name('environment_preflight.py')),
                    '--dataset',request['dataset'],'--output',str(output),'--workers','4','--tasks',*pending]
                with (root/('build-round-'+str(attempt)+'.log')).open('x') as log:
                    subprocess.run(argv,check=True,env=dict(os.environ,TERMINAL_BENCH_DOWNLOAD_PROXY=request['download_proxy']),stdout=log,stderr=subprocess.STDOUT)
                outcomes=read(output/'result.json')
                results.update({task:item for task,item in outcomes.items() if item['passed']})
                pending=[task for task in request['tasks'] if task not in results]
                (root/'environment-readiness.json').write_text(json.dumps({'passed':sorted(results),'pending':pending,'evidence':results},indent=2))
                if not pending:break
            if pending:
                status('blocked_by_environment_failures',tasks=pending,passed=len(results))
                return
            with (root/'model-dispatch-started.json').open('x') as stream:json.dump({'planned_trials':request['planned_trials']},stream)
            outcomes={}
            trial_error_models=[]
            def launch(model):
                spec=request['models'][model]
                argv=['/srv/benchmark/skills/bin/gpu-idle','run','--gpus',','.join(map(str,spec['gpus'])),'--timeout','604800','--','bash',spec['script']]
                with (root/(model+'-admission.log')).open('x') as log:return subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT).returncode
            for wave in request['waves']:
                status('waiting_or_running_models',wave=wave,outcomes=outcomes)
                with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                    futures={pool.submit(launch,model):model for model in wave}
                    for future in as_completed(futures):
                        outcomes[futures[future]]=future.result()
                        (root/'model-completion.json').write_text(json.dumps(outcomes,indent=2))
                infrastructure_errors=[]
                for model in wave:
                    p=root/(model+'-service/evaluation-summary.json')
                    if outcomes[model] or not p.exists():
                        infrastructure_errors.append(model)
                    elif read(p).get('errors',0):
                        trial_error_models.append(model)
                        if not request.get('continue_on_trial_errors', False):
                            infrastructure_errors.append(model)
                (root/'trial-error-models.json').write_text(json.dumps(trial_error_models))
                if infrastructure_errors:
                    status('blocked_by_model_infrastructure_errors',models=infrastructure_errors,outcomes=outcomes)
                    return
            status('completed_with_trial_errors' if trial_error_models else 'completed',outcomes=outcomes,trial_error_models=trial_error_models)
        except Exception as exc:
            status('failed',reason=str(exc));raise


if __name__=='__main__':main()
