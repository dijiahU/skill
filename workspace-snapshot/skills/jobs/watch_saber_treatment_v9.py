"""Read-only job checks every 30 minutes; emit earlier when the parent exits.

This observer never kills, restarts, judges, or changes experiment artifacts.
The active agent goal handles diagnosis and authorized recovery from its output.
"""

import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import time


ROOT = Path('/2024233123/skills')
BATCH = 'v9-full-20260905-r1'
LOG = ROOT / 'logs' / ('saber-' + BATCH)
MANIFEST = ROOT / 'jobs' / ('saber-' + BATCH) / 'frozen/manifest.json'
TERMINAL = {'pipeline_failed', 'treatment_failed', 'judge_failed', 'complete'}


def read(path):
    return json.loads(path.read_text())


def parent_state():
    state = read(LOG / 'status.json')
    recovery = state.get('recovery')
    record = LOG / ('recovery-' + recovery) / 'submitted.json' if recovery else None
    pid = read(record)['pid'] if record is not None and record.exists() else 2012296
    path = Path('/proc') / str(pid)
    try:
        fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
        argv = (path / 'cmdline').read_bytes().split(b'\0')
        matches = any(BATCH.encode() in arg and b'run_saber_treatment_v9_' in arg for arg in argv)
        alive = matches and fields[0] not in ('Z', 'X', 'x')
        birth = int(fields[19])
    except (FileNotFoundError, ProcessLookupError):
        alive, birth = False, None
    return state, {'pid': pid, 'birth': birth, 'alive': alive}


def snapshot(reason, interval):
    state, parent = parent_state()
    effective = ROOT / 'jobs' / ('saber-' + BATCH) / 'recovery-r2/effective-manifest.json'
    manifest = read(effective if state.get('recovery') == 'r2' else MANIFEST)
    models = []
    for spec in manifest['models']:
        paths = list((Path(manifest['raw']) / spec['result_slug']).rglob('*.json'))
        errors, unreadable = 0, 0
        for path in paths:
            try:
                errors += bool(read(path).get('error'))
            except (OSError, ValueError):
                unreadable += 1
        models.append({'model': spec['key'], 'written': len(paths), 'expected': 716,
                       'raw_errors': errors, 'unreadable_now': unreadable,
                       'latest_mtime': max((p.stat().st_mtime for p in paths), default=None)})
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.used,utilization.gpu',
                          '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=15)
    now = time.time()
    row = {'time': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'epoch': now,
           'reason': reason, 'status': state, 'parent': parent, 'models': models,
           'gpu_query_ok': gpu.returncode == 0, 'gpus': gpu.stdout.strip().splitlines(),
           'next_scheduled_epoch': now + interval,
           'requires_attention': not parent['alive'] or state.get('stage') in TERMINAL}
    (LOG / 'watch-status.json').write_text(json.dumps(row, ensure_ascii=False, indent=2))
    with (LOG / 'watch-events.jsonl').open('a') as output:
        output.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps(row, ensure_ascii=False), flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interval', type=int, default=1800)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.interval < 30:
        parser.error('interval must be at least 30 seconds')
    with (LOG / 'watch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = None
        next_check = 0
        while True:
            try:
                state, parent = parent_state()
                signature = (state.get('stage'), state.get('current_model'), parent['pid'], parent['alive'])
                changed = signature != previous
                if changed or time.time() >= next_check:
                    row = snapshot('state_change' if changed else 'scheduled_30min', args.interval)
                    previous = signature
                    next_check = row['next_scheduled_epoch']
                    if args.once:
                        return
            except Exception as error:
                # A failed observation is not evidence that the job terminated.
                print(json.dumps({'time': time.strftime('%Y-%m-%d %H:%M:%S %z'),
                                  'observation_error': type(error).__name__,
                                  'job_terminal_not_inferred': True}), flush=True)
                if args.once:
                    raise
            time.sleep(min(30, max(1, next_check - time.time())))


if __name__ == '__main__':
    main()
