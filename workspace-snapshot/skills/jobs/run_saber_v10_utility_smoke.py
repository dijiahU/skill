"""Small diagnostic for utility classification; never a full Judge gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


CANDIDATE = Path(__file__).with_name('judge-v10-r10-candidate')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gold', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--base-url', default='http://127.0.0.1:18020')
    parser.add_argument('--model', default='deepseek-ai/DeepSeek-V4-Flash-0731')
    parser.add_argument('--enable-thinking', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('Refusing to overwrite an existing smoke report')
    gold = json.loads(args.gold.read_text())
    if gold.get('schema') != 'saber-utility-smoke-cases-v10.0':
        raise ValueError('Unexpected utility smoke corpus')
    cases = gold['cases']
    if not cases or len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Missing or duplicate smoke cases')
    paths = [Path(__file__).resolve(), args.gold.resolve(), *(
        CANDIDATE / name for name in ('judge_osbench.py', 'judge_protocol.py', 'judge_shadow_protocol.py')
    )]
    before = {str(path): digest(path) for path in paths}
    os.environ.setdefault('OSBENCH_JUDGE_KEY', 'local-smoke')
    sys.path.insert(0, str(CANDIDATE))
    import judge_osbench as judge
    from judge_protocol import build_evidence_ledger
    judge.JUDGE_CFG = {
        'id': args.model, 'type': 'openai', 'key': 'local-smoke', 'base_url': args.base_url,
        'enable_thinking': args.enable_thinking, 'context_window': 65536,
        'context_margin_tokens': 2048, 'max_output_tokens': 2048,
        'max_output_tokens_ceiling': 4096, 'max_length_retries': 1,
        'max_schema_repairs': 0, 'timeout_seconds': 600, 'connect_timeout_seconds': 30,
        'read_token_rate_floor_tokens_per_second': 6, 'read_timeout_prefill_buffer_seconds': 120,
    }
    report = {
        'schema': 'saber-judge-utility-smoke-v10.0', 'status': 'running',
        'passed': False, 'dry_run': args.dry_run, 'attribution_tested': False,
        'scoring_authorized': False, 'source_sha256_start': before,
        'expected_cases': len(cases), 'cases': [],
    }

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(args.output)

    save()
    for case in cases:
        row = {'id': case['id'], 'expected': case['expected_category'], 'passed': False}
        try:
            ledger = build_evidence_ledger(case['result'])
            if args.dry_run:
                row.update(status='dry_run', confirmed_model_messages=len(ledger['model_messages']))
            else:
                assessment = judge.run_zero_event_utility_judge(case['task'], case['result'], ledger)
                row.update(status='complete', assessment=assessment,
                           passed=assessment['category'] == case['expected_category'])
        except Exception as exc:
            row.update(status='error', error_type=type(exc).__name__, error=str(exc))
            if hasattr(exc, 'response_meta'):
                row['failure_metadata'] = exc.response_meta
        report['cases'].append(row)
        save()
        print(json.dumps({'case_id': row['id'], 'passed': row['passed'], 'status': row['status']}), flush=True)
        if not args.dry_run and not row['passed']:
            break
    report['source_sha256_end'] = {str(path): digest(path) for path in paths}
    report['sources_unchanged'] = report['source_sha256_end'] == before
    report['passed'] = (not args.dry_run and report['sources_unchanged']
                        and len(report['cases']) == len(cases)
                        and all(row['passed'] for row in report['cases']))
    report['status'] = 'dry_run' if args.dry_run else ('passed' if report['passed'] else 'failed')
    save()
    return 0 if report['passed'] or args.dry_run else 1


if __name__ == '__main__':
    raise SystemExit(main())
