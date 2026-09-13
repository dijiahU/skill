import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

JOB = Path(__file__).resolve().parent
SCRIPTS = JOB / 'frozen/safety-bundle/hooks/scripts'
sys.path.insert(0, str(SCRIPTS))
from workspace_snapshot_cache import read_snapshot


class RepairTests(unittest.TestCase):
    def test_snapshot_cache_reuses_parse_and_invalidates_atomic_replacement(self):
        directory = Path(tempfile.mkdtemp(dir=JOB / 'preflight', prefix='cache-test-'))
        path = directory / 'snapshot.json'
        path.write_text('{"snapshot_status":"ready","file_contents":{"/app/policy":"old"}}')
        first = read_snapshot(str(path))
        self.assertIs(first, read_snapshot(str(path)))
        pending = directory / 'pending.json'
        pending.write_text('{"snapshot_status":"unavailable","file_contents":{}}')
        os.replace(pending, path)
        self.assertEqual(read_snapshot(str(path))['snapshot_status'], 'unavailable')
        path.write_text('broken')
        with self.assertRaises(json.JSONDecodeError):
            read_snapshot(str(path))

    def test_matcher_timeout_blocks_when_fail_closed(self):
        path = JOB / 'frozen/safety-bundle/adapters/codex/codex_hook.py'
        spec = importlib.util.spec_from_file_location('repair_hook', path)
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        with mock.patch.object(bridge, 'FAIL_CLOSED', True), mock.patch.object(
            bridge.subprocess, 'run', side_effect=subprocess.TimeoutExpired('matcher', 25)
        ):
            result = bridge._run_matcher('matcher_bash.py', {})
        self.assertTrue(result[0])
        self.assertIn('unavailable', result[2][0])

    def test_streamed_observer_reports_error_after_emitting_valid_text(self):
        directory = Path(tempfile.mkdtemp(dir=JOB / 'preflight', prefix='scope-test-'))
        (directory / 'allowed.txt').write_text('complete content')
        (directory / 'escape').symlink_to('/etc/passwd')
        tree = ast.parse((JOB / 'frozen/saber/sandbox_shell.py').read_text())
        observer = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == '_WORKSPACE_SNAPSHOT_OBSERVER' for t in n.targets))
        result = subprocess.run([sys.executable, '-I', '-S', '-c', observer],
                                input=json.dumps({'cwd': str(directory), 'paths': []}),
                                capture_output=True, text=True, check=True)
        payload = json.loads(result.stdout)
        self.assertFalse(payload['complete'])
        self.assertEqual(payload['file_contents'][str(directory / 'allowed.txt')], 'complete content')
        self.assertEqual(payload['errors'][str(directory / 'escape')], 'symlink_target_out_of_scope')
        with self.assertRaises(json.JSONDecodeError):
            json.loads(result.stdout[:-10])

    def test_validator_invalidates_snapshot_on_silent_omission(self):
        sys.path.insert(0, str(JOB / 'frozen/saber'))
        from harness_adapters.codex_native_adapter import CodexNativeHarnessAdapter
        directory = Path(tempfile.mkdtemp(dir=JOB / 'preflight', prefix='omission-test-'))
        path = directory / 'snapshot.json'
        path.write_text(json.dumps({'file_contents': {'/app/policy': 'initial'},
                                    'policy_file_contents': {'/app/policy': 'initial'},
                                    'policy_initialized': True, 'snapshot_status': 'ready'}))
        runtime = mock.Mock()
        runtime.snapshot_workspace.return_value = {'complete': True, 'file_contents': {}}
        adapter = CodexNativeHarnessAdapter()
        with self.assertRaisesRegex(RuntimeError, 'action was not executed'):
            adapter._refresh_workspace_snapshot(runtime, '/app', {'SAFETY_ORCH_WORKSPACE_SNAPSHOT': str(path)})
        self.assertEqual(json.loads(path.read_text())['snapshot_status'], 'unavailable')


if __name__ == '__main__':
    unittest.main(verbosity=2)
