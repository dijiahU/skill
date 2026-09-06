"""Single-GPU, resumable engineering first pass of the 137 OAS service tasks."""

import fcntl
import json
import subprocess
import time
from pathlib import Path

import requests


ROOT = Path('/2024233123/skills')
JOBS = ROOT / 'jobs'
LOG = ROOT / 'logs/openagentsafety-services-firstpass-20260905'
RESULTS = ROOT / ('results/openagentsafety/'
                  'mgulavani__openagentsafety_full_updated_v3-train/openai/ZhipuAI')
GROUPS = [('owncloud-only', 86), ('gitlab-only', 42), ('plane-only', 2),
          ('plane-gitlab', 6), ('gitlab-owncloud', 1)]


def launch(group, count):
    note = f'glm47-services-{group}-firstpass-20260905'
    selection = JOBS / f'openagentsafety-{group}-{count}.txt'
    output = (LOG / f'{group}.log').open('a')
    process = subprocess.Popen(
        ['bash', str(JOBS / 'run_openagentsafety_service_probe.sh'), str(selection), note],
        stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
    )
    output.close()
    return {'group': group, 'count': count, 'note': note, 'process': process}


def summarize(job):
    completed = 0
    partial = 0
    grading_errors = 0
    for directory in RESULTS.glob('*_' + job['note']):
        for file in directory.glob('eval_*.json'):
            try:
                result = json.loads(file.read_text())
            except (OSError, ValueError):
                continue
            completed += 1
            partial += bool(result.get('skilldistill', {}).get('conversation_error'))
            grading_errors += bool(result.get('error'))
    return {'group': job['group'], 'selected': job['count'],
            'graded': completed, 'partial': partial, 'grading_errors': grading_errors,
            'pid': job['process'].pid, 'exit_code': job['process'].poll()}


def main():
    selected = []
    for group, count in GROUPS:
        ids = (JOBS / f'openagentsafety-{group}-{count}.txt').read_text().split()
        assert len(ids) == count, (group, len(ids), count)
        selected.extend(ids)
    expected = set((JOBS / 'openagentsafety-services-137.txt').read_text().split())
    assert len(selected) == len(set(selected)) == 137 and set(selected) == expected
    session = requests.Session()
    session.trust_env = False
    response = session.get('http://127.0.0.1:18010/v1/models', timeout=5)
    response.raise_for_status()
    assert 'ZhipuAI/GLM-4.7-Flash' in {m['id'] for m in response.json()['data']}
    LOG.mkdir(parents=True, exist_ok=True)
    supervisor_lock = (LOG / 'supervisor.lock').open('a')
    fcntl.flock(supervisor_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    jobs = [launch(group, count) for group, count in GROUPS[:3]]
    print('Started 130 single-service tasks on GPU 0; mixed tasks follow.', flush=True)
    while any(job['process'].poll() is None for job in jobs):
        status = [summarize(job) for job in jobs]
        (LOG / 'progress.json').write_text(json.dumps(status, indent=2) + '\n')
        print(json.dumps(status), flush=True)
        time.sleep(30)
    for group, count in GROUPS[3:]:
        job = launch(group, count)
        jobs.append(job)
        while job['process'].poll() is None:
            status = [summarize(item) for item in jobs]
            (LOG / 'progress.json').write_text(json.dumps(status, indent=2) + '\n')
            print(json.dumps(status), flush=True)
            time.sleep(30)
    status = [summarize(job) for job in jobs]
    (LOG / 'progress.json').write_text(json.dumps(status, indent=2) + '\n')
    print(json.dumps(status), flush=True)
    return any(job['process'].returncode != 0 for job in jobs)


if __name__ == '__main__':
    raise SystemExit(main())
