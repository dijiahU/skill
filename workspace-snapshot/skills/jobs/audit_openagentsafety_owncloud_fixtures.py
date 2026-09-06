"""Read-only official-image catalog and task-path candidates, never task scores."""

import json
import os
import re
import subprocess
from pathlib import Path

from datasets import load_dataset


ROOT = Path('/2024233123/skills')
IMAGE = 'ghcr.io/theagentcompany/servers-owncloud:1.0.0'
CATALOG = ROOT / 'logs/openagentsafety-owncloud-baseline-fixtures-20260905.json'
REPORT = ROOT / 'logs/openagentsafety-owncloud-fixture-candidates-20260905.json'
SUFFIXES = r'pdf|csv|xlsx|docx|txt|json|odt|pptx|zip|pem|jpg|png'


def catalog():
    image_id = subprocess.check_output(
        ['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], text=True,
    ).strip()
    if CATALOG.is_file():
        saved = json.loads(CATALOG.read_text())
        if saved['image_id'] == image_id:
            return saved
        raise RuntimeError('Existing catalog belongs to a different image')
    result = subprocess.run(
        ['docker', 'run', '--rm', '--pull', 'never', '--network', 'none',
         '--runtime', 'runc', '--read-only', '--memory', '256m', '--cpus', '1',
         '--pids-limit', '64', '--name', 'skilldistill-oas-owncloud-fixture-audit-20260905',
         '--label', 'skilldistill.openagentsafety.fixture-audit=true',
         '--entrypoint', 'find', IMAGE,
         '/var/www/html/data/theagentcompany/files/Documents',
         '-type', 'f', '-printf', '%P\\0'],
        capture_output=True, check=True, timeout=120,
    )
    if len(result.stdout) > 4 * 1024 * 1024:
        raise RuntimeError('Catalog exceeds 4 MiB diagnostic limit')
    paths = sorted('Documents/' + p for p in result.stdout.decode().split('\0') if p)
    if not paths or any('\n' in p for p in paths):
        raise RuntimeError('Invalid fixture catalog')
    saved = {'image': IMAGE, 'image_id': image_id, 'file_count': len(paths), 'paths': paths}
    with CATALOG.open('x') as stream:
        json.dump(saved, stream, indent=2)
    return saved


def main():
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_DATASETS_OFFLINE'] = '1'
    baseline = catalog()
    paths = set(baseline['paths'])
    ids = set((ROOT / 'jobs/openagentsafety-services-137.txt').read_text().split())
    dataset = load_dataset('mgulavani/openagentsafety_full_updated_v3', split='train')
    tasks = []
    for row in dataset:
        if row['instance_id'] not in ids or 'owncloud' not in row['dependencies']:
            continue
        prompt = row['problem_statement']
        explicit = set(re.findall(r'Documents/[^\n`"<>]*?\.(?:' + SUFFIXES + r')\b', prompt))
        for quoted in re.findall(r'[`"]([^`"\n]+)[`"]', prompt):
            if quoted.lstrip('/').startswith('Documents/'):
                explicit.add(quoted.lstrip('/').rstrip('/'))
        names = set(re.findall(r'\b[\w.-]+\.(?:' + SUFFIXES + r')\b', prompt))
        tasks.append({
            'instance_id': row['instance_id'],
            'explicit_paths': [
                {'path': p, 'exists': p in paths or any(q.startswith(p + '/') for q in paths),
                 'same_basename': sorted(q for q in paths if q.rsplit('/', 1)[-1] == p.rsplit('/', 1)[-1])}
                for p in sorted(explicit)
            ],
            'named_files': {name: sorted(p for p in paths if p.rsplit('/', 1)[-1] == name)
                            for name in sorted(names)},
        })
    report = {
        'image_id': baseline['image_id'], 'baseline_files': baseline['file_count'],
        'selected_owncloud_tasks': len(tasks),
        'warning': 'Mentions include output paths. Missing paths need manual review, not automatic repair.',
        'tasks': tasks,
    }
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'tasks'}))
    for task in tasks:
        missing = [p for p in task['explicit_paths'] if not p['exists']]
        if missing:
            print(json.dumps({'instance_id': task['instance_id'], 'missing_mentions': missing}))


if __name__ == '__main__':
    main()
