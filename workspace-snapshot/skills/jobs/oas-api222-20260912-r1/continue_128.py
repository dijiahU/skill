"""Run the user-approved disjoint 128-task stage after the 64-task stage."""
import fcntl
import json
import time
from pathlib import Path
from capacity import run_stage

JOB = Path(__file__).resolve().parent
RESULTS = Path('/srv/benchmark/skills/results/oas-api222-20260912-r1/glm5')

def save(state):
    (JOB / 'continuation-128.json').write_text(json.dumps(state, indent=2) + '\n')

def main():
    lock = (JOB / 'continuation-128.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    allocation = json.loads((JOB / 'disjoint-task-allocation.json').read_text())
    batches = allocation['batches']
    flat = [task for ids in batches.values() for task in ids]
    assert len(flat) == len(set(flat)) == 222
    state = {'model': 'glm5', 'status': 'waiting for 64 stage', 'stages': [],
             'authorization': 'User explicitly requested continuing 128 on new tasks',
             'grading_policy': 'Preserve invalid and partial results; do not treat them as valid capacity evidence.'}
    save(state)
    while not (JOB / 'glm5-capacity-w64-summary.json').exists():
        time.sleep(10)
    # The prior controller records its strict scoring gate before exiting.
    while not (JOB / 'glm5-high-capacity.json').exists():
        time.sleep(2)
    prior = json.loads((JOB / 'glm5-high-capacity.json').read_text())
    if prior['stages'][0]['ok']:
        state['status'] = 'existing controller owns continuation'
        save(state)
        return
    for stage, workers in [('capacity-w128', 128), ('remaining-after-high', 16)]:
        if (RESULTS / stage).exists():
            raise RuntimeError('Refusing duplicate stage: ' + stage)
        state['status'] = 'running ' + stage
        save(state)
        outcome = run_stage('glm5', workers, batches[stage], stage)
        state['stages'].append(outcome)
        save(state)
        if outcome['returncode'] != 0:
            state['status'] = 'stage process failed; preserved results for diagnosis'
            save(state)
            return
    state['status'] = 'all 222 unique task IDs scheduled; inspect invalid outputs separately'
    save(state)

if __name__ == '__main__':
    main()
