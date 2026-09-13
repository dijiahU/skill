"""Invoke the pinned SABER runner while retaining its temporary workspaces."""
import argparse
from pathlib import Path
import tempfile
import run_harness

JOB = Path(__file__).resolve().parent
OriginalTemporaryDirectory = tempfile.TemporaryDirectory

class RetainedTemporaryDirectory(OriginalTemporaryDirectory):
    def __init__(self, *args, **kwargs):
        kwargs['dir'] = str(JOB / 'retained')
        super().__init__(*args, **kwargs)
        self._finalizer.detach()

    def cleanup(self):
        self._finalizer.detach()

tempfile.TemporaryDirectory = RetainedTemporaryDirectory
run_harness.TASKS_DIR = JOB / 'tasks'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--shard')
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    argv = ['--harness', 'codex-native', '--model', args.model, '--config', args.config,
            '--skill-mode', 'safety-orchestrator', '--safety-orchestrator', str(JOB / 'bundle')]
    if args.preflight:
        argv += ['--preflight-only', '--limit', '1']
    else:
        if not args.shard:
            raise ValueError('Shard is required')
        argv += ['--subset', args.shard, '--skip-preflight']
    raise SystemExit(run_harness.main(argv))
