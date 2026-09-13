"""Build main/sidecar/verifier images before spending model time; retain evidence."""
import argparse
import asyncio
import json
import subprocess
import uuid
from pathlib import Path
from harbor.models.task.task import Task
from harbor.models.task.verifier_mode import resolve_effective_verifier_env_config
from harbor.models.trial.paths import TrialPaths
from batch_docker import BatchDocker
from aistation import host_path


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--tasks',nargs='*')
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    semaphore=asyncio.Semaphore(args.workers)
    outcomes={}
    async def check(path):
        async with semaphore:
            item={}
            try:
                task=Task(path)
                for phase,envdir,cfg in [('main',path/'environment',task.config.environment),('verifier',path/'tests',resolve_effective_verifier_env_config(task.config,None))]:
                    trial=TrialPaths(args.output/path.name/phase);trial.mkdir()
                    env=BatchDocker(environment_dir=envdir,environment_name=path.name+'-'+phase,
                        session_id='repair-prebuild-'+path.name+'-'+phase,trial_paths=trial,task_env_config=cfg)
                    await asyncio.to_thread(env._build)
                    item[phase]={'built':True,'image':env._env_vars.main_image_name}
                    if phase == 'main':
                        name='rick-saber-terminal-prereq-'+uuid.uuid4().hex[:12]
                        probe=await asyncio.to_thread(subprocess.run, ['docker','run','--runtime=runc','--network','none','--read-only','--cap-drop','ALL','--name',name,'--label','skilldistill.benchmark=terminal-bench','--mount','type=bind,src='+host_path('/srv/benchmark/skills/envs/uv-python/cpython-3.12.14-linux-x86_64-gnu')+',dst=/opt/terminal-bench-observer-python,readonly','--entrypoint','/bin/sh',env._env_vars.main_image_name,'-c','command -v bash && (command -v python3 || /opt/terminal-bench-observer-python/bin/python3 -I -S -c "import json, pathlib")'], capture_output=True,text=True,timeout=60)
                        item[phase]['prerequisite_probe']={'container':name,'exit_code':probe.returncode,'stdout':probe.stdout,'stderr':probe.stderr}
                        if probe.returncode:
                            raise RuntimeError('Task image lacks required bash/Python observer runtime')
                item['passed']=True
            except Exception as exc:
                item.update(passed=False,error_type=type(exc).__name__,error=str(exc))
            outcomes[path.name]=item
            (args.output/'result.json').write_text(json.dumps(outcomes,indent=2))
            print(path.name, 'PASS' if item['passed'] else item['error_type'],flush=True)
    paths=[p for p in sorted(args.dataset.iterdir()) if (p/'task.toml').exists() and (not args.tasks or p.name in args.tasks)]
    await asyncio.gather(*(check(p) for p in paths))
    (args.output/'completion.json').write_text(json.dumps({'total':len(paths),'passed':sum(v['passed'] for v in outcomes.values()),'failed':[k for k,v in outcomes.items() if not v['passed']]},indent=2))


if __name__=='__main__':asyncio.run(main())
