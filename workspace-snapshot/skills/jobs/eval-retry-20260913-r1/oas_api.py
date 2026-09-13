"""One user-authorized supplemental attempt; preserve baseline isolation."""
import argparse,fcntl,json,os,sys,time
from pathlib import Path
JOB=Path(__file__).resolve().parent
OJ=Path('/srv/benchmark/skills/jobs/oas-api222-20260912-r1/skills100')
sys.path.insert(0,str(OJ))
import resume_after_recharge as skills
import baseline_resume as baseline
from resume_helpers import valid
from lifecycle import save
PLAN=json.loads((JOB/'plan.json').read_text())

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True,choices=['glm5','deepseek-flash','qwen']);model=p.parse_args().model
    lock=(OJ/f'repair-{model}.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for condition,helper in [('skills100',skills),('baseline100',baseline)]:
        key=condition+'-'+model
        if key not in PLAN['oas']:continue
        cfg=PLAN['oas'][key];path=JOB/f'state-oas-{key}.json'
        if path.exists():raise RuntimeError('Duplicate supplemental submission')
        state={'model':model,'condition':condition,'status':'checking provider','planned_tasks':len(cfg['tasks']),'stages':[],'controller_pid':os.getpid()}
        def persist():state['updated_at']=time.time();save(path,state)
        persist()
        good,_=helper.merged(model);tasks=[t for t in cfg['tasks'] if t not in good]
        if condition=='baseline100' and model=='qwen':
            smoke=json.loads((OJ/'baseline1-plan.json').read_text())['models'][model]['smoke_tasks']
            stages=[('smoke',[t for t in smoke if t in tasks]),('full',[t for t in tasks if t not in smoke])]
        else:stages=[('full',tasks)]
        for phase,selection in stages:
            if not selection:continue
            hold=json.loads((OJ/'hold-next-models.json').read_text())
            if hold.get('active'):
                state['status']='paused by provider hold';persist();return
            name=f'{condition}-{model}-supplement-20260913-r1-{phase}'
            state.update(status='running '+phase,tasks_this_stage=len(selection),current_stage=name,workers=min(cfg['workers'],len(selection)));persist()
            result=helper.run_stage(model,selection,name,workers=state['workers'])
            state['stages'].append(result);persist()
            if result['returncode']:
                state['status']='paused after provider or runner error';persist();return
            if phase=='smoke':
                rows=helper.read_stage(model,name)
                isolated=len(rows)==len(selection) and all(valid(r) and (r.get('test_result') or {}).get('skilldistill',{}).get('skill_mode')=='none' and (r.get('test_result') or {}).get('skilldistill',{}).get('hooks_enabled') is False and not (r.get('test_result') or {}).get('skilldistill',{}).get('loaded_skills') and not (r.get('test_result') or {}).get('skilldistill',{}).get('invoked_skills') for r in rows.values())
                state['baseline_isolation_verified']=isolated;persist()
                if not isolated:state['status']='paused: baseline isolation validation incomplete';persist();return
        _,state['summary']=helper.merged(model);state['status']='supplemental batch ended; inspect unresolved tasks';persist()
if __name__=='__main__':main()
