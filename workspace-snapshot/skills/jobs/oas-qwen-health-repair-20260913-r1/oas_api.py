"""Resume Qwen after an exact-host proxy bypass fix, gated by real tasks."""
import fcntl
import json
import os
from pathlib import Path
import sys
import time

JOB=Path(__file__).resolve().parent
OJ=Path('/srv/benchmark/skills/jobs/oas-api222-20260912-r1/skills100')
RJ=Path('/srv/benchmark/skills/jobs/eval-retry-20260913-r2')
sys.path.insert(0,str(OJ))
import resume_after_recharge as skills
import baseline_resume as baseline
from resume_helpers import valid

def save(path,data):
    tmp=path.with_name(path.name+'.writing');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,path)

def main():
    lock=(OJ/'repair-qwen.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (JOB/'plan.json').exists():raise RuntimeError('Already submitted; refusing duplicate repair run')
    excluded=set(json.loads((OJ/'unscorable-tasks.json').read_text())['task_ids'])
    ids=[t for t in (OJ/'tasks222.txt').read_text().splitlines() if t not in excluded]
    plan={'model':'qwen','model_id':'Qwen/Qwen3.8-27B','max_iterations':100,'npc_model':'deepseek-flash','workers':2,'conditions':{}}
    for condition,helper in [('skills100',skills),('baseline100',baseline)]:
        good,_=helper.merged('qwen');todo=[t for t in ids if t not in good]
        plan['conditions'][condition]={'tasks':todo,'smoke':todo[:2],'prior_valid_preserved':len(good)}
    save(JOB/'plan.json',plan)
    def persist(condition,state):
        state['updated_at']=time.time();save(JOB/f'state-{condition}.json',state);save(RJ/f'state-oas-{condition}-qwen.json',state)
    queued={'model':'qwen','condition':'baseline100','status':'queued pending repaired skills run','controller_pid':os.getpid(),'planned_tasks':len(plan['conditions']['baseline100']['tasks']),'repair_job':str(JOB)}
    persist('baseline100',queued)
    state={'model':'qwen','condition':'skills100','status':'waiting for old stage cleanup','controller_pid':os.getpid(),'planned_tasks':len(plan['conditions']['skills100']['tasks']),'repair_job':str(JOB),'stages':[]}
    persist('skills100',state)
    deadline=time.monotonic()+900
    while Path('/proc/13356/stat').exists():
        raw=Path('/proc/13356/stat').read_text().rsplit(')',1)[1].split()
        if raw[0]=='Z':break
        if time.monotonic()>deadline:
            state['status']='paused: old stage cleanup still active';persist('skills100',state);return
        time.sleep(3)
    for condition,helper in [('skills100',skills),('baseline100',baseline)]:
        cfg=plan['conditions'][condition]
        state={'model':'qwen','condition':condition,'status':'checking repaired stage','controller_pid':os.getpid(),'planned_tasks':len(cfg['tasks']),'repair_job':str(JOB),'workers':2,'stages':[]}
        persist(condition,state)
        for phase,selection in [('smoke',cfg['smoke']),('full',cfg['tasks'][len(cfg['smoke']):])]:
            good,_=helper.merged('qwen');selection=[t for t in selection if t not in good]
            if not selection:continue
            stage=f'{condition}-qwen-healthfix-20260913-r1-{phase}'
            state.update(status='running '+phase,current_stage=stage,tasks_this_stage=len(selection));persist(condition,state)
            result=helper.run_stage('qwen',selection,stage,workers=min(2,len(selection)))
            state['stages'].append(result);persist(condition,state)
            rows=helper.read_stage('qwen',stage)
            good_rows=[r for r in rows.values() if valid(r)]
            if result['returncode'] or not good_rows or (phase=='smoke' and len(good_rows)!=len(selection)):
                state['status']='paused: repaired task validation incomplete';persist(condition,state)
                queued['status']='paused pending skills validation' if condition=='skills100' else state['status']
                if condition=='skills100':persist('baseline100',queued)
                return
            if condition=='baseline100' and phase=='smoke':
                isolated=all((r.get('test_result')or{}).get('skilldistill',{}).get('skill_mode')=='none' and (r.get('test_result')or{}).get('skilldistill',{}).get('hooks_enabled') is False for r in good_rows)
                state['baseline_isolation_verified']=isolated;persist(condition,state)
                if not isolated:state['status']='paused: baseline isolation check failed';persist(condition,state);return
        _,summary=helper.merged('qwen');state.update(status='health repair batch ended; inspect remaining tasks',summary={k:v for k,v in summary.items() if k!='selected_attempts'});persist(condition,state)

if __name__=='__main__':main()
