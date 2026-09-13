import argparse,fcntl,importlib.util,json,os,signal,subprocess,sys,time
from pathlib import Path
from terminal_common import JOB,PLAN,run_terminal
from lifecycle import save
OJ=Path('/srv/benchmark/skills/jobs/oas-api222-20260912-r1/skills100')
GJ=Path('/srv/benchmark/skills/jobs/gptoss-oas-terminal-20260913-r1')
sys.path.insert(0,str(OJ))
from resume_helpers import read_stage,valid,balance_error
from stage_cleanup import cleanup_stage

def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['oas','terminal'],required=True);arm=p.parse_args().arm
    spec=importlib.util.spec_from_file_location('prior_arm_probe',GJ/'arm_runner.py');probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe);probe.JOB=JOB
    probe.protocol_probe(arm)
    if arm=='terminal':return run_terminal('gptoss',os.environ['GPTOSS_BASE_URL'],'EMPTY')
    lock=(OJ/'repair-gptoss.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    from resume_after_recharge import merged
    cfg=PLAN['oas']['skills100-gptoss'];good,_=merged('gptoss');tasks=[t for t in cfg['tasks'] if t not in good]
    stage='skills100-gptoss-local-20260913-r1-resume2';path=JOB/'state-oas-skills100-gptoss.json';selection=JOB/'oas-gptoss-resume2.txt'
    if path.exists() or selection.exists() or (Path(PLAN['local_oas_plan']['results_root'])/stage).exists():raise RuntimeError('Duplicate local OAS retry')
    if json.loads((OJ/'hold-next-models.json').read_text()).get('active'):raise RuntimeError('Provider hold active')
    selection.write_text('\n'.join(tasks)+'\n')
    state={'model':'gptoss','condition':'skills100','status':'running supplemental tasks','planned_tasks':len(tasks),'current_stage':stage,'workers':cfg['workers'],'controller_pid':os.getpid()}
    def persist():state['updated_at']=time.time();save(path,state)
    def stop(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    process=None
    try:
        with (JOB/'logs'/'oas-gptoss-resume2.log').open('x') as log:
            process=subprocess.Popen([str(GJ/'oas-run.sh'),'--model','gptoss','--workers',str(cfg['workers']),'--select',str(selection),'--stage',stage],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        state['runner_pid']=process.pid
        save(OJ/'active-stage-gptoss.json',{'model':'gptoss','pid':process.pid,'stage':stage,'tasks':tasks,'workers':cfg['workers'],'started':time.time()});persist()
        while process.poll() is None:
            rows=read_stage('gptoss',stage);valid_rows=[r for r in rows.values() if valid(r)]
            state['progress']={'returned':len(rows),'valid':len(valid_rows),'points':sum(r['test_result']['final_score']['result'] for r in valid_rows)};persist()
            if any(balance_error(r) for r in rows.values()):raise RuntimeError('NPC balance exhausted')
            time.sleep(10)
        state.update(status='supplemental batch ended; inspect unresolved tasks',returncode=process.returncode);persist()
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=40)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=15)
            cleanup_stage(stage)
if __name__=='__main__':main()
