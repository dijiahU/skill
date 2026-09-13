"""Write a paired baseline/full hooks+skills plan (no model calls)."""
import argparse
import hashlib
import json
from pathlib import Path

from harbor.models.job.config import JobConfig

ROOT = Path('/srv/benchmark/skills')


def digest_tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '.git' not in p.parts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True, help='Complete Safety Orchestrator bundle')
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--attempts', type=int, default=1)
    args = parser.parse_args()
    dataset, skill = args.dataset.resolve(), args.bundle.resolve()
    if not (skill / 'skills/safety-router-skill/SKILL.md').is_file() or not (skill/'adapters/codex/codex_hook.py').is_file():
        parser.error('--bundle must contain the complete hooks and skills deployment')
    tasks = sorted(dataset.glob('*/task.toml'))
    if not tasks or args.attempts < 1:
        parser.error('Need a local dataset with tasks and positive attempts')
    if not args.name.replace('-', '').replace('_', '').isalnum():
        parser.error('Name must contain only letters, digits, hyphens or underscores')
    output = ROOT / 'jobs' / ('terminal-bench-' + args.name)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'condition_scope': 'full_hooks_and_skills', 'model': args.model,
                'tasks': [str(t.parent) for t in tasks], 'dataset_sha256': digest_tree(dataset),
                'skills_path': str(skill), 'skills_sha256': digest_tree(skill),
                'formal_run_ready': False, 'pending': ['oracle validation', 'model endpoint validation',
                    'skills load evidence', 'task compatibility audit']}
    for condition in ('baseline', 'full'):
        config = JobConfig.model_validate({
            'job_name': f'rick-saber-terminal-{args.name}-{condition}',
            'jobs_dir': str(ROOT / 'results' / 'terminal-bench'),
            'n_attempts': args.attempts, 'n_concurrent_trials': 1,
            'environment': {'import_path': 'aistation:AIStationDocker', 'delete': False},
            'agents': [{'import_path': 'full_agent:FullSafetyCodex', 'model_name': args.model,
                        'kwargs': {'base_url': args.base_url, 'safety_bundle': str(skill),
                                   'treatment': condition == 'full'}}],
            'datasets': [{'path': str(dataset)}],
        })
        (output / f'{condition}.json').write_text(config.model_dump_json(indent=2))
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(output)


if __name__ == '__main__':
    main()
