"""Observe the authorized five-model Judge workflow without controlling jobs.

Reads evaluation artifacts and process identities. Writes only its own monitor
directory. Never starts/stops GPU work, edits results, or cleans resources.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import time


ROOT = Path('/2024233123/skills')
BATCH = 'saber-v9-full-20260905-r1'
BASE = ROOT / 'logs' / BATCH
PLAN = ROOT / 'jobs' / BATCH / 'judge-first-r2'
JUDGE = BASE / 'judge-first-r2'
OUT = ROOT / 'results' / BATCH / 'judged-provisional-r2'
MONITOR = BASE / 'judge-monitor-r2'
MODELS = ['mistral', 'minimax', 'deepseek_flash', 'glm', 'gptoss']
TERMINAL = {'provisional_judge_complete', 'judge_job_failed',
            'judge_scheduler_failed', 'judge_execution_failed',
            'blocked_treatment_incomplete_or_unexpected_exit'}


def read(path):
    return json.loads(path.read_text())


def identity(pid):
    root = Path('/proc') / str(pid)
    fields = (root / 'stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': pid, 'birth': int(fields[19]), 'pgid': int(fields[2]),
            'sid': int(fields[3]), 'state': fields[0],
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def alive(expected):
    try:
        actual = identity(expected['pid'])
        return (actual['state'] not in ('Z', 'X', 'x')
                and all(actual[key] == expected[key]
                        for key in ('pid', 'birth', 'pgid', 'sid', 'boot_id')))
    except (OSError, ValueError, IndexError):
        return False


def slug(key):
    return f'codex_{key}_treatment_v9_full_20260905_r1_codex-native-safety-orchestrator'


def snapshot(checkpoint, watcher, cache):
    now = time.time()
    state = read(JUDGE / 'status.json')
    stage = state['stage']
    raw = ROOT / 'results' / BATCH / 'raw'
    treatment = {}
    for key in ('glm', 'gptoss'):
        stamps = [path.stat().st_mtime for path in (raw / slug(key)).glob('[ABC]/*/*.json')]
        treatment[key] = {'written': len(stamps), 'expected': 716,
                          'new_last_5m': sum(stamp >= now - 300 for stamp in stamps),
                          'latest_age_s': round(now - max(stamps), 1) if stamps else None}
    judged = {}
    for key in MODELS:
        # Exclude _attempts/task/0001.json; only A/B/C files are task verdicts.
        paths = list((OUT / slug(key)).glob('[ABC]/*/*.json'))
        usable = failed = unreadable = 0
        latest = None
        for path in paths:
            stat = path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            latest = max(latest or 0, stat.st_mtime)
            prior = cache.get(str(path))
            if prior and prior[0] == signature:
                outcome = prior[1]
            else:
                try:
                    data = read(path)
                    outcome = ('usable' if data.get('judge_status') == 'usable'
                               else 'failed')
                    cache[str(path)] = (signature, outcome)
                except (OSError, ValueError):
                    outcome = 'unreadable'
            usable += outcome == 'usable'
            failed += outcome == 'failed'
            unreadable += outcome == 'unreadable'
        summary = OUT / slug(key) / 'summary.json'
        judged[key] = {'written': len(paths), 'usable': usable, 'failed': failed,
                       'unreadable_now': unreadable, 'summary_exists': summary.exists(),
                       'latest_mtime': latest}
    watcher_alive = alive(watcher)
    issues = []
    if stage in TERMINAL and stage != 'provisional_judge_complete':
        issues.append('judge_workflow_reported_failure')
    if not watcher_alive and stage not in TERMINAL:
        issues.append('judge_watcher_exited_before_terminal_status')
    written = sum(value['written'] for value in judged.values())
    usable = sum(value['usable'] for value in judged.values())
    failed = sum(value['failed'] for value in judged.values())
    latest = max((value['latest_mtime'] or 0 for value in judged.values()), default=0)
    started = JUDGE / 'execution-started.json'
    if stage == 'judging':
        since = latest or (started.stat().st_mtime if started.exists() else now)
        if now - since > 900:
            issues.append('no_new_judge_records_for_15_minutes')
    if failed:
        issues.append('judge_records_with_unusable_verdicts_present')
    if stage == 'provisional_judge_complete':
        if written != 3580 or usable != 3580 or not (OUT / '_all_summary.json').exists():
            issues.append('completion_artifacts_need_review')
    row = {'time': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'epoch': now,
           'stage': stage, 'watcher': {'pid': watcher['pid'], 'alive': watcher_alive},
           'main_alive': alive(checkpoint['r2_controller']),
           'parallel_alive': alive(checkpoint['parallel_controller']),
           'treatment': treatment, 'judged': judged, 'written': written,
           'usable': usable, 'failed': failed,
           'execution_started': started.exists(),
           'requires_attention': bool(issues), 'issues': issues,
           'provisional': True, 'formal': False}
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    MONITOR.mkdir(parents=True, exist_ok=True)
    with (MONITOR / 'monitor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        checkpoint = read(PLAN / 'checkpoint.json')
        watcher_pid = read(JUDGE / 'submitted.json')['pid']
        watcher = identity(watcher_pid)
        argv = (Path('/proc') / str(watcher_pid) / 'cmdline').read_bytes().split(b'\0')
        if str(PLAN / 'run_saber_v9_judge_first.py').encode() not in argv or b'--watch' not in argv:
            raise RuntimeError('submitted Judge watcher identity does not match')
        cache = {}
        while True:
            try:
                row = snapshot(checkpoint, watcher, cache)
            except Exception as error:
                row = {'time': time.strftime('%Y-%m-%d %H:%M:%S %z'),
                       'epoch': time.time(), 'requires_attention': True,
                       'observation_error': type(error).__name__,
                       'job_terminal_not_inferred': True}
            row['monitor_pid'] = os.getpid()
            (MONITOR / 'status.json').write_text(json.dumps(row, ensure_ascii=False, indent=2))
            with (MONITOR / 'events.jsonl').open('a') as output:
                output.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps(row, ensure_ascii=False), flush=True)
            if args.once or row.get('stage') in TERMINAL:
                return
            time.sleep(60)


if __name__ == '__main__':
    main()
