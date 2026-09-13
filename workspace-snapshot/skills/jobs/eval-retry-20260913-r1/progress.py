"""Read-only progress for the supplemental queue and merged first-valid scores."""
import json,time
from pathlib import Path
JOB=Path(__file__).resolve().parent
plan=json.loads((JOB/'plan.json').read_text())
report=Path('/srv/benchmark/skills/reports/api-evaluation-snapshot-20260913/build_report.py')
g={'__file__':str(report),'__name__':'read_progress'}
exec(compile(report.read_text().split('history=[];history_trials=[];regrade_inventory=[]')[0],str(report),'exec'),g)
states={}
for p in sorted(JOB.glob('state-*.json'))+sorted(JOB.glob('lifecycle-*.json')):
    d=json.loads(p.read_text());states[p.stem]={k:v for k,v in d.items() if k in ['status','planned_tasks','progress','runner_pid','controller_pid','summary','processes']}
launch=json.loads((JOB/'launch.json').read_text())
for name,p in launch['processes'].items():
    proc=Path('/proc')/str(p['pid'])/'cmdline'
    states.setdefault(name,{})['launcher_alive']=proc.exists() and str(JOB).encode() in proc.read_bytes()
print(json.dumps({'checked_at':time.time(),'states':states,'oas':g['oas'],'terminal':g['terminal']},ensure_ascii=False,indent=2))
