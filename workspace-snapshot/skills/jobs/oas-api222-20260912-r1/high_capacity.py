"""Continue the same 222-task run directly at 64 and 128 workers."""
import json
from pathlib import Path
from capacity import run_stage, results

JOB = Path(__file__).resolve().parent


def main():
    model = 'glm5'
    assigned = set((JOB / 'smoke.txt').read_text().splitlines())
    for stage in ['capacity-w4','capacity-w8']:
        assigned.update((JOB / (model + '-' + stage + '.txt')).read_text().splitlines())
    order = (JOB / 'capacity-order.txt').read_text().splitlines()
    state = {'model':model,'requested_worker_levels':[64,128],'low_stage_handoff':json.loads((JOB/'controller-handoff.json').read_text()),'stages':[],'status':'running'}
    for workers in [64,128]:
        selected = [i for i in order if i not in assigned][:workers]
        if len(selected)!=workers:
            raise ValueError('Not enough fresh tasks for requested worker count')
        stage='capacity-w'+str(workers)
        outcome=run_stage(model,workers,selected,stage)
        assigned.update(selected)
        state['stages'].append(outcome)
        state['highest_fully_passed_high_workers']=max([s['workers'] for s in state['stages'] if s['ok']],default=None)
        if not outcome['ok']:
            state['status']='high stage finished with errors; paused for diagnosis before increasing load'
        (JOB/'glm5-high-capacity.json').write_text(json.dumps(state,indent=2))
        print(json.dumps({k:v for k,v in outcome.items() if k not in ['valid_task_ids','errors']}),flush=True)
        if not outcome['ok']:
            return
    remaining=[i for i in (JOB/'tasks222.txt').read_text().splitlines() if i not in assigned]
    if remaining:
        outcome=run_stage(model,min(128,len(remaining)),remaining,'remaining-after-high')
        state['stages'].append(outcome)
    state['status']='all 222 task IDs scheduled; inspect low-stage and known-invalid outputs separately'
    (JOB/'glm5-high-capacity.json').write_text(json.dumps(state,indent=2))


if __name__=='__main__':
    main()
