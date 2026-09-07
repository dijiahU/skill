"""Replay failed pilot records with stream evidence; never advances scoring gates."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import run_saber_v10 as control
from saber_v10_model_specs import MODEL_SPECS
from saber_v10_audit import validate_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=['gptoss', 'minimax'], required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--revision', type=int, required=True)
    args = parser.parse_args()
    if args.revision < 100:
        raise ValueError('Diagnostic scope revisions start at 100')
    source = control.ROOT / 'jobs/saber-v10-paired-20260907-r3/frozen'
    manifest = json.loads((source / 'manifest.json').read_text())
    old_spec = next(s for s in manifest['models'] if s['key'] == args.model)
    spec = deepcopy(next(s for s in MODEL_SPECS if s['key'] == args.model))
    spec.update({k: old_spec[k] for k in ('slug', 'result_slugs', 'endpoints')})
    if os.environ.get('CUDA_VISIBLE_DEVICES') != ','.join(map(str, spec['gpus'])):
        raise RuntimeError('Exact GPU reservation required')
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    control.BATCH = f'v10-paired-20260907-r{args.revision}'
    control.LOG = directory / 'logs'
    control.DATA = directory / 'results'
    control.FROZEN = directory / 'frozen'
    (control.FROZEN / 'jobs').mkdir(parents=True)
    for name in ('saber', 'bundle'):
        shutil.copytree(source / name, control.FROZEN / name)
    shutil.copy2(source / 'jobs/saber_v10_container_entry.py', control.FROZEN / 'jobs/saber_v10_container_entry.py')
    subset_dir = control.FROZEN / 'subsets/pilot'
    subset_dir.mkdir(parents=True)
    (control.DATA / 'pilot/raw').mkdir(parents=True)
    terminal = json.loads((control.ROOT / 'reports/v10-fixes-20260906/20260907_r3_terminal_summary.json').read_text())
    selected = {c: [r['task_id'] for r in v['failures']]
                for c, v in terminal['models'][args.model].items() if v['failures']}
    for condition, ids in selected.items():
        (subset_dir / (condition + '.json')).write_text(json.dumps(ids))
    capture_dir = directory / 'stream-captures'
    for service in spec['services']:
        if any('vllm_responses_compat_proxy' in a for a in service['argv']):
            service.setdefault('env', {})['SABER_RESPONSES_STREAM_CAPTURE_DIR'] = str(capture_dir)
    report = {'diagnostic_only': True, 'scoring_authorized': False, 'model': args.model,
              'source_batch': 'v10-paired-20260907-r3', 'selected': selected,
              'status': 'starting', 'conditions': {}, 'cleanup_safe': False,
              'proxy_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (control.ROOT / 'bin').glob('vllm_responses_compat_proxy*.py')}}
    def save():
        control.save(directory / 'status.json', report)
    save()
    run_id = 'pilot-' + args.model
    scopes = {control.resource_scope('pilot', args.model, c) for c in selected}
    control.ensure_fresh_container_scope(run_id, scopes)
    life = control.Lifecycle(run_id)
    try:
        control.services_start(life, spec)
        report['status'] = 'running'
        save()
        print(json.dumps({'status': 'running', 'model': args.model}), flush=True)
        for condition, ids in selected.items():
            worker = control.docker_runner(life, spec, 'pilot', condition, condition + '-diagnostic',
                    spec['endpoints'][0], ['--skip-preflight', '--trace', '--subset',
                                          '/run/saber-subsets/' + condition + '.json'])
            code = worker.wait()
            validation = validate_model(control.DATA / 'pilot/raw' / spec['result_slugs'][condition],
                                        control.FROZEN / 'saber/tasks', ids, require_full=False, condition=condition)
            report['conditions'][condition] = {'worker_exit_code': code, 'validation': validation}
            save()
            if code:
                raise RuntimeError('Diagnostic worker failed: ' + str(code))
        report['status'] = 'complete'
    except BaseException as exc:
        report.update(status='error', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        try:
            life.close()
            report['cleanup_safe'] = True
        finally:
            save()
    print(json.dumps({'status': report['status'], 'model': args.model,
                      'cleanup_safe': report['cleanup_safe']}), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
