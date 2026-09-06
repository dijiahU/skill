"""Snapshot failures keep evidence without publishing stale content to hooks."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from harness_adapters.codex_native_adapter import CodexNativeHarnessAdapter


class SnapshotDiagnosticsTests(unittest.TestCase):
    def test_incomplete_report_keeps_details_and_invalidates_old_snapshot(self):
        adapter = CodexNativeHarnessAdapter()
        adapter.last_run_meta = {}
        report = {
            'complete': False, 'file_contents': {},
            'errors': {'/home/user/job.sh': 'too_large'},
            'error_details': {'/home/user/job.sh': {'reason': 'too_large', 'size': 2000001}},
            'excluded_file_details': {'/home/user/data.xlsx': {'reason': 'binary'}},
            'symlinks': {'/home/user/link': {'target': '/home/user/job.sh'}},
        }
        runtime = SimpleNamespace(snapshot_workspace=lambda **kwargs: report)
        old = {'policy_file_contents': {}, 'file_contents': {'/home/user/job.sh': 'stale'}}
        with patch.object(Path, 'read_text', return_value=json.dumps(old)), patch.object(adapter, '_write_workspace_snapshot') as write:
            with self.assertRaisesRegex(RuntimeError, 'action was not executed'):
                adapter._refresh_workspace_snapshot(runtime, '/home/user', {'SAFETY_ORCH_WORKSPACE_SNAPSHOT': '/snapshot'})
        self.assertEqual(write.call_count, 1)
        unavailable = write.call_args.args[1]
        self.assertEqual(unavailable['snapshot_status'], 'unavailable')
        self.assertEqual(unavailable['file_contents'], {})
        meta = adapter.last_run_meta['workspace_observations'][0]
        self.assertEqual(meta['error_details'], report['error_details'])
        self.assertEqual(meta['excluded_file_details'], report['excluded_file_details'])
        self.assertEqual(meta['symlinks'], report['symlinks'])
        self.assertEqual(meta['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
