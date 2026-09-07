"""Offline coverage of configuration-bound Judge gate resume behavior."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path('/2024233123')
sys.path.insert(0, str(ROOT / 'skills/projects/skill/saber'))
sys.path.insert(0, str(ROOT / 'skills/bin'))
import run_saber_judge_shadow_gate as shadow
import run_saber_judge_full_pipeline_gate as full
from judge_shadow_protocol import judge_resume_config, judge_resume_config_matches


class JudgeResumeConfigTests(unittest.TestCase):
    def test_every_evaluation_setting_changes_resume_identity_without_key_leak(self):
        config = {'id': 'local', 'type': 'openai', 'key': 'synthetic-test-key',
                  'base_url': 'http://127.0.0.1:18020', 'context_window': 65536,
                  'context_margin_tokens': 2048, 'max_output_tokens': 6144,
                  'max_output_tokens_ceiling': 12288, 'max_length_retries': 1,
                  'max_schema_repairs': 1, 'enable_thinking': True,
                  'timeout_seconds': 600, 'connect_timeout_seconds': 30,
                  'read_token_rate_floor_tokens_per_second': 6,
                  'read_timeout_prefill_buffer_seconds': 120}
        report = {'resume_config': judge_resume_config(config)}
        self.assertTrue(judge_resume_config_matches(report, config))
        self.assertNotIn('synthetic-test-key', json.dumps(report))
        self.assertFalse(judge_resume_config_matches({'judge': {'id': 'local'}}, config))
        for key, value in report['resume_config'].items():
            changed = copy.deepcopy(config)
            changed[key] = not value if isinstance(value, bool) else value + 1 if isinstance(value, (int, float)) else value + '-changed'
            with self.subTest(key=key):
                self.assertFalse(judge_resume_config_matches(report, changed))
        config['key'] = 'rotated-test-key'
        self.assertTrue(judge_resume_config_matches(report, config))

    def test_both_real_clis_reuse_only_matching_configuration(self):
        reports = ROOT / 'skills/reports/v10-fixes-20260906'
        cases = [(shadow, reports / 'judge_shadow_gold_v10_r4.json'),
                 (full, reports / 'judge_full_pipeline_gold_manifest_v10_r3.json')]
        with tempfile.TemporaryDirectory() as temporary:
            for runner, gold in cases:
                path = Path(temporary) / (runner.__name__ + '.json')
                base = [runner.__name__, '--gold', str(gold), '--output', str(path), '--dry-run']
                def invoke(extra):
                    with mock.patch.object(sys, 'argv', base + extra), contextlib.redirect_stdout(io.StringIO()), mock.patch.object(runner, 'run_case', side_effect=AssertionError('No HTTP in resume regression')):
                        self.assertEqual(runner.main(), 0)
                    return json.loads(path.read_text())
                original = invoke([])
                original['cases'][0]['status'] = 'passed'
                for extra, reuse in [([], True), (['--enable-thinking'], False),
                                     (['--max-output-tokens', '8192'], False),
                                     (['--context-margin', '333'], False),
                                     (['--max-length-retries', '0'], False)]:
                    with self.subTest(runner=runner.__name__, extra=extra):
                        path.write_text(json.dumps(original))
                        result = invoke(['--resume'] + extra)
                        self.assertEqual(result['cases'][0].get('reused_on_resume', False), reuse)
                old = copy.deepcopy(original)
                old.pop('resume_config')
                path.write_text(json.dumps(old))
                self.assertFalse(invoke(['--resume'])['cases'][0].get('reused_on_resume', False))


if __name__ == '__main__':
    unittest.main()
