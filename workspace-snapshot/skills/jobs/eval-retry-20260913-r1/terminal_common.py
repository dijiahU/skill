import json,os,subprocess,time
from pathlib import Path
from lifecycle import save
JOB=Path(__file__).resolve().parent
PLAN=json.loads((JOB/'plan.json').read_text())

def run_terminal(model,url,key):
    cfg=PLAN['terminal'][model]; local=model=='gptoss'; base=PLAN['local_terminal_plan'] if local else PLAN['terminal_plan']
    model_id='OpenAI-Mirror/gpt-oss-120b' if local else base['models'][model]['id']
    name='rick-saber-tbgptoss-20260913-r1-retry1' if local else f'rick-saber-tbapi-{model}-20260913-r1-retry1'
    path=JOB/f'state-terminal-{model}.json';config=JOB/'configs'/f'{model}-retry1.json';directory=Path(base['results_root'])/name
    if config.exists() or directory.exists():raise RuntimeError('Duplicate Terminal retry')
    # Recheck first-valid preservation at dispatch, in case another run finished.
    good=set();pattern='rick-saber-tbgptoss-*' if local else f'rick-saber-tbapi-{model}-*'
    for p in Path(base['results_root']).glob(pattern+'/*/result.json'):
        r=json.loads(p.read_text());score=((r.get('verifier_result')or{}).get('rewards')or{}).get('reward')
        if not r.get('exception_info') and isinstance(score,(int,float)):good.add(r['task_name'].removeprefix('terminal-bench/'))
    tasks=[t for t in cfg['tasks'] if t not in good]
    state={'model':model_id,'condition':'skills','status':'running supplemental tasks','planned_tasks':len(tasks),'prior_valid':len(good),'current_results':str(directory),'controller_pid':os.getpid(),'workers':cfg['workers']}
    def persist():state['updated_at']=time.time();save(path,state)
    if not tasks:state['status']='nothing unresolved';persist();return
    data={'job_name':name,'jobs_dir':base['results_root'],'n_attempts':1,'n_concurrent_trials':cfg['workers'],'retry':{'max_retries':0},'environment_build_timeout_multiplier':3,'environment':{'import_path':'tb21_docker:TB21Docker','delete':False},'datasets':[{'path':base['dataset'],'task_names':tasks}],'agents':[{'import_path':'full_agent:FullSafetyCodex','model_name':model_id,'kwargs':{'base_url':url,'safety_bundle':str(JOB/'frozen/safety-bundle'),'treatment':True,'max_steps':1000,'timeout_seconds':12000,'require_deployment_activity':False,'context_window':32768 if local else 65536}}]}
    save(config,data)
    env=dict(os.environ,RESPONSES_API_KEY=key)
    with (JOB/'logs'/f'terminal-{model}-retry1.log').open('x') as log:
        process=subprocess.Popen([str(JOB/'harbor.sh'),'run','--config',str(config)],env=env,stdout=log,stderr=subprocess.STDOUT)
        state['runner_pid']=process.pid;persist()
        while process.poll() is None:
            rows=[json.loads(p.read_text()) for p in directory.glob('*/result.json')]
            state['progress']={'returned':len(rows),'valid':sum(not r.get('exception_info') and isinstance(((r.get('verifier_result')or{}).get('rewards')or{}).get('reward'),(int,float)) for r in rows)};persist();time.sleep(10)
    state.update(status='supplemental batch ended; inspect unresolved tasks',returncode=process.returncode);persist()
