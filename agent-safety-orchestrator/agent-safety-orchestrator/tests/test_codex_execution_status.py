"""Execution failure metadata survives Codex routing without trusting output."""
import runpy
import sys
import unittest
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE / "hooks/scripts"))
from archive_permission_observations import _execution_status

JOBS = runpy.run_path(str(BUNDLE / "adapters/codex/codex_hook.py"))["_jobs_for"]


class ExecutionStatusTests(unittest.TestCase):
    def status(self, **extra):
        event = {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                 "tool_input": {"command": "tar -cf archive.tar files"}, **extra}
        return _execution_status(JOBS(event)[0][1])

    def test_top_level_status_survives(self):
        self.assertEqual(self.status(exit_code=1), "failed")
        self.assertEqual(self.status(exit_code=0), "success")
        self.assertEqual(self.status(executed=False), "failed")

    def test_conflicting_metadata_retains_failure(self):
        self.assertEqual(self.status(response_metadata={"exit_code": 0},
                                     tool_response_metadata={"exit_code": 1}), "failed")
        self.assertEqual(self.status(response_metadata={"exit_code": 0},
                                     exit_code=1), "failed")

    def test_output_and_requested_arguments_do_not_supply_status(self):
        self.assertEqual(self.status(tool_response={"exit_code": 0}), "unknown")
        self.assertEqual(self.status(tool_response="error: failed"), "unknown")
        self.assertEqual(self.status(tool_input={"exit_code": 0}), "unknown")


if __name__ == "__main__":
    unittest.main()
