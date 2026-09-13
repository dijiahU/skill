"""Bounded verifier-only replay of the 39 user-authorized pending attempts."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

JOB=Path(__file__).resolve().parent
BATCH=JOB/'batch-39-r1'
PYTHON='/srv/benchmark/skills/envs/terminal-bench/bin/python'
REPORT=Path('/srv/benchmark/skills/reports/api-evaluation-snapshot-20260913')
sys.path.insert(0,'/srv/benchmark/skills/projects/terminal-bench-aistation')
from verifier_integrity import assess_trial

def now():return datetime.now(timezone.utc).isoformat()
def save(path,data):
    temporary=path.with_name(path.name+'.writing')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    os.replace(temporary,path)

def main():
    BATCH.mkdir(exist_ok=True)
    lock=(BATCH/'batch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (BATCH/'state.json').exists():raise RuntimeError('Batch already submitted; refusing duplicate dispatch')
    rows=list(csv.DictReader((REPORT/'terminal-verifier-pending.csv').open(encoding='utf-8-sig')))
    if len(rows)!=39:raise RuntimeError('Expected the approved 39-task snapshot')
    for i,r in enumerate(rows):
        r['index']=i;r['source_result_sha256']=hashlib.sha256(Path(r['source']).read_bytes()).hexdigest()
    save(BATCH/'plan.json',{'created_at_utc':now(),'tasks':rows,'workers':4,'scope':'official verifier only on retained completed artifacts','model_api_calls':0,'claude_inference':'remains paused','docker_lifecycle_operations':False})
    state={'status':'running','started_at_utc':now(),'controller_pid':os.getpid(),'planned':len(rows),'workers':4,'completed':0,'active':0,'results':[]}
    save(BATCH/'state.json',state)
    def grade(r):
        p=Path(r['source']);log=BATCH/(f"{r['index']:02d}-"+p.parent.name+'.log')
        if hashlib.sha256(p.read_bytes()).hexdigest()!=r['source_result_sha256']:
            return {**r,'status':'source_changed','model_api_calls':0}
        prior=assess_trial(p)
        if prior['valid']:return {**r,'status':'already_valid','integrity':prior,'model_api_calls':0}
        save(BATCH/f"task-{r['index']:02d}.json",{'status':'running','started_at_utc':now(),**r})
        with log.open('x') as stream:
            process=subprocess.Popen([PYTHON,str(JOB/'regrade_retained.py'),'--source',str(p.parent)],stdout=stream,stderr=subprocess.STDOUT)
            rc=process.wait()
        verdict=assess_trial(p)
        item={**r,'status':'scored' if verdict['valid'] else 'needs_review','finished_at_utc':now(),'returncode':rc,'integrity':verdict,'log':str(log),'model_api_calls':0}
        save(BATCH/f"task-{r['index']:02d}.json",item)
        return item
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(grade,r) for r in rows]
        for future in as_completed(futures):
            try:item=future.result()
            except Exception as exc:item={'status':'controller_error','error_type':type(exc).__name__,'error':str(exc)}
            state['results'].append(item);state['completed']=len(state['results'])
            state['counts']=dict(Counter(x['status'] for x in state['results']));state['updated_at_utc']=now()
            save(BATCH/'state.json',state)
            print(json.dumps({k:v for k,v in item.items() if k in ['model','task','status','integrity']},ensure_ascii=False),flush=True)
    state['status']='completed';state['finished_at_utc']=now();save(BATCH/'state.json',state)
    # Archive the previous static snapshot before refreshing the report.
    archive=BATCH/'report-before';archive.mkdir()
    for p in REPORT.iterdir():
        if p.is_file() and p.suffix in ['.json','.csv','.md']:(archive/p.name).write_bytes(p.read_bytes())
    with (BATCH/'report-refresh.log').open('w') as stream:
        rc=subprocess.run([PYTHON,str(REPORT/'build_report.py')],stdout=stream,stderr=subprocess.STDOUT).returncode
    state['report_refresh_returncode']=rc;save(BATCH/'state.json',state)

if __name__=='__main__':main()
