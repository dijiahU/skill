"""Attach formal-batch ownership without changing benchmark safety semantics."""

import os
import re
import sys


def tag_sandbox_command(command, batch, model):
    """Only rewrite the benchmark's disposable docker-run name and labels."""
    if not isinstance(command, list) or command[:2] != ['docker', 'run']:
        return command
    if not re.fullmatch(r'v9-full-20260905-r1', batch):
        raise ValueError('unexpected batch identity')
    if not re.fullmatch(r'[a-z0-9_]+', model):
        raise ValueError('invalid model identity')
    result = list(command)
    index = result.index('--name') + 1
    original = result[index]
    if not re.fullmatch(r'osbench-[a-f0-9]{8}', original):
        raise ValueError('refuse to relabel a non-benchmark sandbox')
    result[index] = f'rick-saber-{batch}-{model.replace("_", "-")}-{original}'
    result[2:2] = ['--label', f'rick-saber.batch={batch}',
                   '--label', f'rick-saber.model={model}',
                   '--label', 'rick-saber.role=sandbox']
    return result


def main():
    if os.environ.get('SABER_IDLE_SESSION'):
        raise RuntimeError('formal results must not use an idle session')
    sys.path.insert(0, '/workspace/saber')
    import sandbox_shell
    real_subprocess = sandbox_shell.subprocess

    class ScopedSubprocess:
        def __getattr__(self, name):
            return getattr(real_subprocess, name)

        def run(self, command, *args, **kwargs):
            return real_subprocess.run(tag_sandbox_command(
                command, os.environ['SABER_BATCH_ID'], os.environ['SABER_BATCH_MODEL']),
                *args, **kwargs)

    sandbox_shell.subprocess = ScopedSubprocess()
    import run_harness
    return run_harness.main()


if __name__ == '__main__':
    raise SystemExit(main())
