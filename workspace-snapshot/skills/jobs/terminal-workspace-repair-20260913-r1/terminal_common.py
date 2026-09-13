"""One smoke gate and one remaining batch; preserve every prior valid result."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, '/srv/benchmark/skills/projects/terminal-bench-aistation')
from verifier_integrity import assess_trial
from lifecycle import save

JOB = Path(__file__).resolve().parent
PLAN = json.loads((JOB / 'plan.json').read_text())


def run_terminal(model, url, key):
    local = model == 'gptoss'
    base = PLAN['local_terminal_plan'] if local else PLAN['terminal_plan']
    model_id = 'OpenAI-Mirror/gpt-oss-120b' if local else base['models'][model]['id']
    prefix = 'rick-saber-tbgptoss-20260913-r1' if local else f'rick-saber-tbapi-{model}-20260913-r1'
    state_path = JOB / f'state-terminal-{model}.json'
    state = {'model': model_id, 'condition': 'skills', 'controller_pid': os.getpid(),
             'repair': 'workspace streaming, stdin manifest, shared snapshot parse, fail-closed transport',
             'official_task_budgets_changed': False, 'stages': []}

    def persist():
        state['updated_at'] = time.time()
        save(state_path, state)

    def unresolved():
        good = set()
        pattern = 'rick-saber-tbgptoss-*' if local else f'rick-saber-tbapi-{model}-*'
        for path in Path(base['results_root']).glob(pattern + '/*/result.json'):
            row = json.loads(path.read_text())
            if assess_trial(path, row)['valid']:
                good.add(row['task_name'].removeprefix('terminal-bench/'))
        return [task for task in PLAN['terminal'][model]['tasks'] if task not in good]

    for phase in ['smoke', 'full']:
        tasks = unresolved()
        if not tasks:
            state['status'] = 'all targeted tasks valid; no more inference needed'
            persist()
            return
        if phase == 'smoke':
            tasks = tasks[:1]
        name = prefix + '-wsrepair1-' + phase
        directory = Path(base['results_root']) / name
        config = JOB / 'configs' / f'{model}-{phase}.json'
        if config.exists() or directory.exists():
            raise RuntimeError('Duplicate repair stage; explicit review required')
        data = {'job_name': name, 'jobs_dir': base['results_root'], 'n_attempts': 1,
                'n_concurrent_trials': 1 if phase == 'smoke' else 2, 'retry': {'max_retries': 0},
                'environment_build_timeout_multiplier': 3,
                'environment': {'import_path': 'tb21_docker:TB21Docker', 'delete': False},
                'datasets': [{'path': base['dataset'], 'task_names': tasks}],
                'agents': [{'import_path': 'full_agent:FullSafetyCodex', 'model_name': model_id,
                            'kwargs': {'base_url': url, 'safety_bundle': str(JOB / 'frozen/safety-bundle'),
                                       'treatment': True, 'max_steps': 1000, 'timeout_seconds': 12000,
                                       'require_deployment_activity': False,
                                       'context_window': 32768 if local else 65536}}]}
        save(config, data)
        stage = {'name': name, 'tasks': tasks, 'results': str(directory)}
        state['stages'].append(stage)
        state.update(status='running ' + phase, current_results=str(directory), planned_tasks=len(tasks))
        env = dict(os.environ, RESPONSES_API_KEY=key)
        with (JOB / 'logs' / f'terminal-{model}-{phase}.log').open('x') as log:
            process = subprocess.Popen([str(JOB / 'harbor.sh'), 'run', '--config', str(config)],
                                       env=env, stdout=log, stderr=subprocess.STDOUT)
            stage['runner_pid'] = process.pid
            while process.poll() is None:
                rows = list(directory.glob('*/result.json'))
                stage['returned'] = len(rows)
                stage['valid'] = sum(assess_trial(path)['valid'] for path in rows)
                persist()
                time.sleep(10)
        rows = list(directory.glob('*/result.json'))
        stage.update(returncode=process.returncode, returned=len(rows),
                     valid=sum(assess_trial(path)['valid'] for path in rows))
        persist()
        if stage['valid'] != len(tasks):
            state['status'] = phase + ' contains infrastructure-invalid results; automatic continuation stopped'
            persist()
            return
    state.update(status='targeted repair completed', unresolved=unresolved())
    persist()
