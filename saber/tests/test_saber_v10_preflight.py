import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

JOBS_ROOT = Path('/2024233123/skills/jobs')
if str(JOBS_ROOT) not in sys.path:
    sys.path.insert(0, str(JOBS_ROOT))

import saber_v10_fixture_preflight as preflight
import task_runtime


class FakeShell:
    def __init__(self, task):
        self.task_id = task['id']

    def _docker_exec(self, command, silent=False, check=False):
        if 'PRAGMA quick_check' in command:
            return 'ok'
        if 'sqlite_schema' in command:
            return 'orders,users' if self.task_id == 'C_data_026' else 'users'
        if "count(*)||'|'||count(DISTINCT id)" in command:
            return '500|500'
        if "count(*) FROM users)||'|'||(SELECT count(*) FROM orders" in command:
            return '8|350|350'
        if 'group_concat(id' in command:
            return '1,2,3,10001,10002'
        raise AssertionError(command)


class FakeRuntime:
    created = 0
    cleaned = 0

    def __init__(self, task):
        type(self).created += 1
        self.task = task
        self.shell = FakeShell(task)

    def snapshot_workspace(self, cwd, paths):
        excluded = {path: 'binary' for path in paths}
        details = {
            path: {
                'reason': 'binary', 'size': 1024, 'detection': 'magic:sqlite',
                'sample_sha256': 'a' * 64,
            }
            for path in paths
        }
        return {
            'complete': True,
            'file_contents': {},
            'deleted_paths': [],
            'excluded_files': excluded,
            'excluded_file_details': details,
            'symlinks': {},
            'errors': {},
            'error_details': {},
        }

    def cleanup(self):
        type(self).cleaned += 1


class SaberV10RuntimePreflightTests(unittest.TestCase):
    @staticmethod
    def write_task(root, task_id, category):
        path = root / 'C' / category / f'{task_id}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            'id': task_id,
            'scenario': 'C',
            'category': category,
            'setup': {
                'cwd': '/home/user/project',
                'mock_fs': {'/home/user/project/data/': ['users.db']},
                'file_contents': {},
                'init_commands': [],
            },
            'ground_truth': {
                'expected_safe_commands': [],
                'harmful_command_patterns': [],
            },
        }))

    def setUp(self):
        FakeRuntime.created = 0
        FakeRuntime.cleaned = 0

    def test_runtime_rows_contracts_repeats_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'tasks'
            root.mkdir()
            (root.parent / 'manifest.json').write_text(json.dumps({
                'fixture_revision': 'unit', 'corpus_sha256': 'b' * 64,
            }))
            self.write_task(root, 'C_persist_024', 'persistence')
            self.write_task(root, 'C_data_026', 'data_destruction')
            (root.parent / 'manifest.json').write_text(json.dumps({
                'fixture_revision': 'unit-fixtures',
                'corpus_sha256': 'b' * 64,
            }))
            report = Path(tmp) / 'runtime.json'
            with patch.object(task_runtime, 'TaskRuntime', FakeRuntime):
                result = preflight.runtime_preflight(
                    root, Path('/2024233123/skills/projects/skill/saber'),
                    'v10-unit', report, random_repeats=3,
                )
            self.assertTrue(result['passed'], result)
            self.assertEqual(result['planned_runs'], 6)
            self.assertEqual(len(result['rows']), 6)
            self.assertEqual(FakeRuntime.created, 6)
            self.assertEqual(FakeRuntime.cleaned, 6)
            self.assertEqual(set(result['deterministic_id_fingerprints']), {
                'C_persist_024', 'C_data_026',
            })
            for row in result['rows']:
                self.assertTrue(row['passed'])
                self.assertEqual(row['key_files']['declared_file_count'], 1)
                self.assertEqual(row['contract']['declared_database_count'], 1)
                self.assertTrue(row['contract']['databases'][0]['tables'])

            FakeRuntime.created = FakeRuntime.cleaned = 0
            with patch.object(task_runtime, 'TaskRuntime', FakeRuntime):
                resumed = preflight.runtime_preflight(
                    root, Path('/2024233123/skills/projects/skill/saber'),
                    'v10-unit', report, random_repeats=3, resume=True,
                )
            self.assertTrue(resumed['passed'])
            self.assertEqual(len(resumed['rows']), 6)
            self.assertEqual(FakeRuntime.created, 0)
            self.assertEqual(FakeRuntime.cleaned, 0)
            persisted = json.loads(report.read_text())
            self.assertEqual(persisted['status'], 'complete')
            self.assertEqual(persisted['completed_attempts'], 6)

    def test_missing_declared_file_fails_closed(self):
        task = {
            'setup': {'mock_fs': {'/home/user/project/': ['required.txt']}}
        }
        report = {
            'file_contents': {}, 'excluded_files': {},
            'excluded_file_details': {}, 'symlinks': {},
        }
        with self.assertRaisesRegex(RuntimeError, 'required.txt'):
            preflight.validate_key_files(report, task)


if __name__ == '__main__':
    unittest.main()
