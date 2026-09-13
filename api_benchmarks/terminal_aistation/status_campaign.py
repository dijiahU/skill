"""Read-only progress and score report for the repaired campaign."""
import json
from pathlib import Path

ROOT=Path('/srv/benchmark/skills/jobs/terminal-bench-repair-20260910-r1/campaign-v5')


def read(path):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return {}


request=read(ROOT/'request.json');state=read(ROOT/'status.json');ready=read(ROOT/'environment-readiness.json')
passed=set(ready.get('passed',[]));last_errors={}
for path in sorted(ROOT.glob('build-round-*/result.json')):
    for task,item in read(path).items():
        if item.get('passed'):passed.add(task);last_errors.pop(task,None)
        elif task not in passed:last_errors[task]=item.get('error','')
report={'campaign':str(ROOT),'state':state,'environment_tasks_ready':len(passed),'environment_tasks_total':len(request.get('tasks',[])),
    'environment_failures':last_errors,'models':{}}
for model,spec in request.get('models',{}).items():
    config=read(Path(spec['config']));result=read(Path(config['jobs_dir'])/config['job_name']/'result.json');stats=result.get('stats',{})
    report['models'][model]={'completed':stats.get('n_completed_trials',0),'errors':stats.get('n_errored_trials',0),
        'running':stats.get('n_running_trials',0),'finished_at':result.get('finished_at'),
        'scores':{key:{'n_scored':value.get('n_trials'),'errors':value.get('n_errors'),
            'reward_counts':{reward:len(names) for reward,names in value.get('reward_stats',{}).get('reward',{}).items()}}
            for key,value in stats.get('evals',{}).items()}}
print(json.dumps(report,indent=2))
