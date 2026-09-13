"""Offline build-context regression test; does not call Docker or delete files."""
from contextlib import nullcontext
import hashlib
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class HooksBuildContextTest(unittest.TestCase):
    def test_context_and_image_digest_include_reference_reader(self):
        root = Path(__file__).resolve().parents[2]
        sdk = Path('vendor/software-agent-sdk/openhands-sdk/openhands/sdk')
        modules = ('hooks/executor.py', 'hooks/conversation_hooks.py',
                   'tool/builtins/invoke_skill.py')
        expected = hashlib.sha256(b''.join(
            (root / 'openagentsafety' / sdk / name).read_bytes()
            for name in modules
        )).hexdigest()
        images = types.ModuleType('benchmarks.openagentsafety.build_images')
        images.get_image_name = lambda: 'skilldistill-test:base'
        hooks = types.ModuleType('benchmarks.openagentsafety.safety_orchestrator')
        hooks.hook_adapter_digest = lambda: expected
        spec = importlib.util.spec_from_file_location(
            'tested_hooks_builder', root / 'api_benchmarks/build_oas_hooks.py'
        )
        builder = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {images.__name__: images, hooks.__name__: hooks}):
            spec.loader.exec_module(builder)
        context = Path(tempfile.mkdtemp(prefix='oas-hooks-context-test-'))
        real_run = subprocess.run

        def check_build(args, **kwargs):
            self.assertEqual(args[:2], ['docker', 'build'])
            self.assertIn('HOOKS_SHA256=' + expected, args)
            dockerfile = (context / 'Dockerfile').read_text()
            for line in dockerfile.splitlines():
                if line.startswith('COPY '):
                    source = shlex.split(line)[1]
                    self.assertTrue((context / source).is_file(), source)
            for name in modules:
                self.assertEqual((context / sdk / name).read_bytes(),
                                 (root / 'openagentsafety' / sdk / name).read_bytes())
            # Execute the Dockerfile's own digest check against its staged files.
            command = next(line for line in dockerfile.splitlines()
                           if line.startswith('RUN python -c '))
            code = shlex.split(command)[3].replace(
                '/usr/local/lib/python3.12/site-packages/openhands/sdk',
                str(context / sdk)
            )
            env = dict(os.environ, HOOKS_SHA256=expected)
            real_run([sys.executable, '-c', code], env=env, check=True,
                     capture_output=True)
            return subprocess.CompletedProcess(args, 0)

        with patch.object(builder.tempfile, 'TemporaryDirectory',
                          return_value=nullcontext(str(context))), \
             patch.object(builder.subprocess, 'run', side_effect=check_build):
            builder.main()


if __name__ == '__main__':
    unittest.main()
