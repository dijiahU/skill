"""Read-only progress observer for the authorized r4 Judge continuation."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('/2024233123/skills')
BASE = ROOT / 'logs/saber-v9-full-20260905-r1'
JUDGE = BASE / 'judge-resume-r4'
MONITOR = BASE / 'judge-monitor-r4'
spec = importlib.util.spec_from_file_location(
    '_judge_observer', ROOT / 'jobs/watch_saber_v9_judge_r2.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
observer.JUDGE = JUDGE
observer.TERMINAL = {'provisional_judge_complete', 'nothing_to_retry',
                     'recovery_failed', 'scheduler_failed', 'execution_failed'}


def main():
    MONITOR.mkdir(exist_ok=True)
    with (MONITOR / 'monitor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        submitted = observer.read(JUDGE / 'submitted.json')
        watcher = submitted['identity']
        checkpoint = observer.read(observer.PLAN / 'checkpoint.json')
        cache = {}
        while True:
            try:
                row = observer.snapshot(checkpoint, watcher, cache)
                row['workflow'] = 'judge-resume-r4'
                if row['stage'] not in observer.TERMINAL:
                    row['issues'] = [issue for issue in row['issues']
                                     if issue != 'judge_records_with_unusable_verdicts_present']
                row['remaining_to_retry'] = row['failed']
                row['requires_attention'] = bool(row['issues'])
            except Exception as error:
                row = {'time': time.strftime('%Y-%m-%d %H:%M:%S %z'),
                       'requires_attention': True, 'observation_error': type(error).__name__}
            row['monitor_pid'] = os.getpid()
            temporary = MONITOR / 'status.pending'
            temporary.write_text(json.dumps(row, ensure_ascii=False, indent=2))
            os.replace(temporary, MONITOR / 'status.json')
            with (MONITOR / 'events.jsonl').open('a') as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps(row, ensure_ascii=False), flush=True)
            if row.get('stage') in observer.TERMINAL:
                return
            time.sleep(60)


if __name__ == '__main__':
    main()
