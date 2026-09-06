import unittest
from harness_adapters.no_progress import NoProgressGuard


class NoProgressTests(unittest.TestCase):
    def observe(self, guard, command='git status', output='not a repository', failed=True, deltas=None):
        return guard.observe(tool='bash', arguments={'command': command}, output=output,
                             failed=failed, deltas=[] if deltas is None else deltas)

    def test_same_failed_target_with_whitespace_and_flag_changes_is_bounded(self):
        guard = NoProgressGuard()
        for i, command in enumerate(('git status', 'git   status', 'git status --short', 'git status --porcelain')):
            result = self.observe(guard, command)
            self.assertEqual(result['terminal'], i == 3)

    def test_new_output_and_actual_state_change_allow_normal_debugging(self):
        guard = NoProgressGuard()
        for _ in range(3): self.observe(guard)
        self.assertEqual(self.observe(guard, output='a different error')['count'], 1)
        self.observe(guard, deltas=[{'operation': 'write'}], failed=False)
        self.assertEqual(self.observe(guard)['count'], 1)

    def test_same_intent_success_clears_its_failure_streak(self):
        guard = NoProgressGuard()
        for _ in range(3): self.observe(guard)
        self.observe(guard, failed=False, output='success')
        self.assertEqual(self.observe(guard)['count'], 1)

    def test_successful_repeated_reads_do_not_trigger_failure_budget(self):
        guard = NoProgressGuard()
        for _ in range(20):
            self.assertIsNone(self.observe(guard, failed=False, output='stable status'))
        self.assertEqual(guard.failures, {})

    def test_different_operands_are_not_merged_and_unknown_effect_resets(self):
        guard = NoProgressGuard()
        for _ in range(3): self.observe(guard, command='cat missing-a')
        self.assertEqual(self.observe(guard, command='cat missing-b')['count'], 1)
        guard.observe(tool='bash', arguments={}, output='', failed=True, deltas=None)
        self.assertEqual(guard.failures, {})


if __name__ == '__main__': unittest.main()
