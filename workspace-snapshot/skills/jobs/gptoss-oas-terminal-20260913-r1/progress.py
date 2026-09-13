"""Read-only progress, with numeric scores separated from incomplete trials."""
import json
from pathlib import Path
import sys
import time

JOB = Path(__file__).resolve().parent
sys.path.insert(0, '/srv/benchmark/skills/jobs/oas-api222-20260912-r1/skills100')
from resume_helpers import read_stage, valid


def main():
    results = {'checked_at': time.time()}
    for arm in ['oas', 'terminal']:
        plan = json.loads((JOB / f'{arm}-plan.json').read_text())
        path = JOB / f'state-{arm}.json'
        state = json.loads(path.read_text()) if path.exists() else {}
        life = JOB / f'lifecycle-{arm}.json'
        lifecycle = json.loads(life.read_text()) if life.exists() else {}
        selected = {}
        for directory in sorted(Path(plan['results_root']).glob('*')):
            if not directory.is_dir():
                continue
            if arm == 'oas':
                for task, row in read_stage('gptoss', directory.name).items():
                    good = valid(row)
                    score = (row.get('test_result') or {}).get('final_score') or {}
                    if task not in selected or not selected[task]['valid']:
                        selected[task] = {'valid': good, 'points': score.get('result', 0) if good else 0,
                                          'total': score.get('total', 0) if good else 0}
            else:
                for p in directory.glob('*/result.json'):
                    try:
                        row = json.loads(p.read_text())
                    except json.JSONDecodeError:
                        continue
                    score = ((row.get('verifier_result') or {}).get('rewards') or {}).get('reward')
                    good = not row.get('exception_info') and isinstance(score, (int, float))
                    selected[row['task_name']] = {'valid': good, 'points': score if good else 0, 'total': 1 if good else 0}
        vals = list(selected.values())
        results[arm] = {'status': state.get('status', lifecycle.get('status', 'queued')),
                        'planned': 184 if arm == 'oas' else 89, 'returned': len(vals),
                        'valid': sum(r['valid'] for r in vals), 'points': sum(r['points'] for r in vals),
                        'graded_total': sum(r['total'] for r in vals),
                        'errors': sum(not r['valid'] for r in vals), 'current_workers': state.get('workers'),
                        'gpu': lifecycle.get('gpu'), 'lifecycle_status': lifecycle.get('status')}
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
