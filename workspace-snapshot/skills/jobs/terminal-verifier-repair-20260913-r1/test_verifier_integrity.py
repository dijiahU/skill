import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, '/srv/benchmark/skills/projects/terminal-bench-aistation')
from verifier_integrity import assess_verifier, assess_trial

ROOT = Path(__file__).parent / 'test-artifacts'
ROOT.mkdir(exist_ok=True)

class IntegrityTests(unittest.TestCase):
    def fixture(self, statuses):
        p = Path(tempfile.mkdtemp(prefix='case-', dir=ROOT))
        summary = {'tests': len(statuses), **{s: statuses.count(s) for s in ['passed','failed','skipped','pending','other']}}
        (p/'ctrf.json').write_text(json.dumps({'results': {'summary': summary, 'tests': [{'name': str(i), 'status': s} for i,s in enumerate(statuses)]}}))
        return p

    def test_real_pass_and_real_assertion_failure(self):
        self.assertTrue(assess_verifier(self.fixture(['passed']), 1)['valid'])
        self.assertTrue(assess_verifier(self.fixture(['passed','failed']), 0)['valid'])

    def test_dependency_download_failure_is_not_zero_score(self):
        p = Path(tempfile.mkdtemp(prefix='missing-', dir=ROOT))
        (p/'test-stdout.txt').write_text('error: Failed to fetch pytest; dns error')
        self.assertFalse(assess_verifier(p, 0)['valid'])

    def test_empty_or_incomplete_report(self):
        self.assertFalse(assess_verifier(self.fixture([]), 0)['valid'])
        p = self.fixture(['passed']);r=json.loads((p/'ctrf.json').read_text());r['results']['summary']['tests']=2
        (p/'ctrf.json').write_text(json.dumps(r))
        self.assertFalse(assess_verifier(p, 1)['valid'])

    def test_reward_mismatch_and_boolean(self):
        p=self.fixture(['failed'])
        self.assertFalse(assess_verifier(p, 1)['valid'])
        self.assertFalse(assess_verifier(p, False)['valid'])

    def test_collection_failure_and_all_skipped(self):
        p=self.fixture(['passed']);(p/'test-stdout.txt').write_text('ERROR collecting /tests/another_test.py')
        self.assertFalse(assess_verifier(p, 1)['valid'])
        self.assertFalse(assess_verifier(self.fixture(['skipped']), 1)['valid'])

    def test_real_claude_regressions(self):
        root=Path('/srv/benchmark/skills/results/terminal-api-foreign-20260913-r1/rick-saber-tbapi-claude-20260913-r1-smoke')
        self.assertFalse(assess_verifier(root/'fix-git__LFvVWTy/verifier', 0)['valid'])
        repaired=assess_trial(root/'fix-git__LFvVWTy/result.json')
        self.assertTrue(repaired['valid'])
        self.assertEqual(repaired['reward'], 1)
        self.assertIn('verifier_replay', repaired)
        # Test assertions really ran for this task; its failure must remain zero.
        self.assertTrue(assess_trial(root/'openssl-selfsigned-cert__mpouG8h/result.json')['valid'])

if __name__ == '__main__': unittest.main()
