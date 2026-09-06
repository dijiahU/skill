"""Paired audit regressions using in-memory records, no containers."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ROOT = Path(__file__).resolve().parents[1]
AUDIT = load('v10_audit_test', ROOT / 'saber_v10_audit.py')
FIXTURES = load('v9_audit_fixtures', ROOT / 'tests/test_saber_treatment_v9_audit.py')


class PairedAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = FIXTURES.AuditTests()
        fixture.setUp()
        cls.template = fixture.files[fixture.first]
        cls.task = fixture.files[FIXTURES.TASKS / 'A/info_leak' / (fixture.ids[0] + '.json')]

    def record(self, condition='safety-orchestrator'):
        record = deepcopy(self.template)
        record['harness'] = 'codex-native-' + condition
        record['conversation'][-1]['source'] = 'model'
        record['events'][0].update(exit_code=0, execution_provenance='docker', execution_status='completed')
        meta = record['harness_meta']
        meta['condition'] = condition
        if condition == 'none':
            record['harness_meta'] = {key: meta[key] for key in (
                'condition', 'task_tool_attempts', 'support_tool_attempts', 'task_tool_attempt_limit',
                'support_tool_attempt_limit', 'tool_calls', 'turn_status')}
            record['harness_meta'].update(skills=[], manual_hook_runs=0, safety_usage={'hook_calls': []})
        return record

    def validate(self, record, condition='safety-orchestrator'):
        return AUDIT._validate_record(record, self.task, 30, condition)[0]

    def test_both_conditions_pass_their_actual_contract(self):
        for condition in ('none', 'safety-orchestrator'):
            self.assertEqual(self.validate(self.record(condition), condition), [])

    def test_baseline_rejects_skill_contamination_and_wrong_condition(self):
        record = self.record('none')
        record['harness_meta']['skills'] = ['safety-router-skill']
        self.assertIn('baseline_skill_isolation_failed', self.validate(record, 'none'))
        self.assertIn('wrong_condition', self.validate(self.record(), 'none'))

    def test_treatment_still_requires_observed_hook_and_snapshot(self):
        record = self.record()
        record['harness_meta']['safety_usage']['hook_calls'] = []
        self.assertIn('observed_hook_calls_missing', self.validate(record))
        record = self.record()
        record['harness_meta']['stop_workspace_snapshot'] = False
        self.assertIn('stop_workspace_snapshot_not_true', self.validate(record))

    def test_mock_exit_code_and_unknown_execution_are_rejected(self):
        record = self.record('none')
        record['events'][0]['execution_provenance'] = 'mock'
        record['events'][0]['execution_status'] = 'mocked'
        self.assertIn('nonexecution_exit_code_misrepresented', self.validate(record, 'none'))
        record['events'][0]['exit_code'] = None
        self.assertEqual(self.validate(record, 'none'), [])
        record['events'][0].pop('execution_provenance')
        self.assertIn('execution_provenance_missing_or_invalid', self.validate(record, 'none'))

    def test_stop_replacement_requires_original_and_observed_block(self):
        record = self.record()
        record['conversation'][-1].update(source='harness', content=AUDIT.STOP_REPLACEMENT + ' unsafe final')
        record['harness_meta']['safety_usage']['hook_calls'][-1]['blocked'] = True
        record['harness_meta']['manual_hook_blocks'] = 1
        self.assertIn('stop_replacement_missing_original_evidence', self.validate(record))
        record['harness_meta']['withheld_model_messages'] = [{'text': 'unsafe advice', 'phase': 'final_answer'}]
        self.assertEqual(self.validate(record), [])

    def test_observed_pre_model_veto_is_valid_without_executed_tools(self):
        record = self.record()
        record['events'] = []
        record['trajectory'] = []
        record['conversation'] = [{'role': 'assistant', 'source': 'harness', 'phase': 'final_answer', 'content': 'Request blocked before model execution.'}]
        meta = record['harness_meta']
        meta.update(turn_status='blocked_by_user_prompt_hook', task_tool_attempts=0, tool_calls=0,
                    manual_hook_runs=1, hook_runs=1, manual_hook_blocks=1,
                    stop_workspace_snapshot=False, workspace_observations=[])
        meta['safety_usage']['hook_calls'] = [FIXTURES.hook('UserPromptSubmit', blocked=True)]
        self.assertEqual(self.validate(record), [])
        meta['safety_usage']['hook_calls'][0]['blocked'] = False
        self.assertIn('user_prompt_veto_missing_hook_evidence', self.validate(record))

    def test_model_audit_excludes_archived_attempts(self):
        task_id = self.task['id']
        relative = Path(self.task['scenario']) / self.task['category'] / (task_id + '.json')
        tasks_root, results_root = Path('/memory/tasks'), Path('/memory/results')
        source, official = tasks_root / relative, results_root / relative
        archived = results_root / '_attempts' / 'retry1' / relative
        files = {source: self.task, official: self.record('none'), archived: self.record('none')}
        def recursive(path, pattern):
            return [source] if path == tasks_root else [official, archived]
        def canonical(path, pattern):
            self.assertEqual(path, results_root)
            self.assertEqual(pattern, '[ABC]/*/*.json')
            return [official]
        with patch.object(Path, 'rglob', recursive), patch.object(Path, 'glob', canonical), patch.object(
                AUDIT, '_load', side_effect=lambda path: (deepcopy(files[path]), None)):
            report = AUDIT.validate_model(results_root, tasks_root, [task_id], require_full=False, condition='none')
        self.assertTrue(report['passed'], report['issues'])
        self.assertEqual(report['totals']['result_files'], 1)
        self.assertEqual(report['totals']['technical_pass'], 1)

    def test_commentary_alone_is_not_model_final(self):
        record = self.record('none')
        record['conversation'][-1]['phase'] = 'commentary'
        self.assertIn('missing_model_final', self.validate(record, 'none'))


if __name__ == '__main__': unittest.main()
