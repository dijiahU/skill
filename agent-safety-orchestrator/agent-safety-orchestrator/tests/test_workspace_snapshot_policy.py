"""Current implementation changes cannot rewrite original scope constraints."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


MATCHER = Path(__file__).resolve().parents[1] / "hooks/scripts/matcher_bash.py"


class WorkspaceSnapshotPolicyTests(unittest.TestCase):
    def run_matcher(self, command, current, policy, status="ready", excluded=None):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "snapshot.json"
            snapshot.write_text(json.dumps({
                "schema_version": 2, "authoritative": True,
                "cwd": "/home/user/project",
                "snapshot_status": status, "file_contents": current,
                "policy_file_contents": policy, "excluded_files": excluded or {},
            }))
            return subprocess.run(
                [sys.executable, str(MATCHER)], text=True, capture_output=True,
                input=json.dumps({"cwd": "/home/user/project",
                                  "tool_input": {"command": command}}),
                env={**os.environ, "SAFETY_ORCH_STATUS_DIR": directory,
                     "SAFETY_ORCH_WORKSPACE_SNAPSHOT": str(snapshot)},
            )

    def test_current_safe_repair_does_not_execute_original_dangerous_code(self):
        path = "/home/user/project/maintain.sh"
        result = self.run_matcher(
            "bash maintain.sh", {path: "sqlite3 data/store.db 'VACUUM;'"},
            {path: "sqlite3 data/store.db 'DROP TABLE users;'"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_new_dangerous_code_is_not_hidden_by_original_safe_snapshot(self):
        path = "/home/user/project/maintain.sh"
        result = self.run_matcher(
            "bash maintain.sh", {path: "sqlite3 data/store.db 'DROP TABLE users;'"},
            {path: "sqlite3 data/store.db 'VACUUM;'"},
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_modified_policy_cannot_expand_original_scope(self):
        scope = "/home/user/project/scope.json"
        result = self.run_matcher(
            "nc -z 172.27.9.2 443",
            {scope: json.dumps({"approved_subnets": ["172.27.0.0/16"]})},
            {scope: json.dumps({"approved_subnets": ["172.27.1.0/24"]})},
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("approved", result.stdout)

    def test_original_scope_still_permits_current_narrow_target(self):
        scope = "/home/user/project/scope.json"
        result = self.run_matcher(
            "nc -z 172.27.1.2 443", {},
            {scope: json.dumps({"approved_subnets": ["172.27.1.0/24"]})},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_entering_subdirectory_does_not_discard_parent_policy(self):
        current = {"/home/user/project/tools/probe.sh": "nc -z 172.27.9.2 443"}
        policy = {"/home/user/project/scope.json": json.dumps({"approved_subnets": ["172.27.1.0/24"]})}
        for command in ("bash tools/probe.sh", "cd tools && bash probe.sh"):
            result = self.run_matcher(command, current, policy)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("approved", result.stdout)

    def test_required_unobserved_script_cannot_run_outside_snapshot_scope(self):
        for command in ("bash /tmp/new-helper.sh", "/tmp/new-helper.sh", "python3 /tmp/new-helper.py", "node /tmp/new-helper.js"):
            result = self.run_matcher(command, {}, {})
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("required automation content was not observed", result.stdout)

    def test_excluded_automation_is_not_assumed_safe(self):
        for command, excluded in (
            ("bash node_modules/vendor/run.sh", {"/home/user/project/node_modules": "excluded_directory"}),
            ("./helper.bin", {"/home/user/project/helper.bin": "binary"}),
        ):
            result = self.run_matcher(command, {}, {}, excluded=excluded)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("excluded from safe observation", result.stdout)

    def test_unavailable_observation_is_never_treated_as_fresh_empty_workspace(self):
        result = self.run_matcher("bash maintain.sh", {}, {}, status="unavailable")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("observation is unavailable", result.stdout)


if __name__ == "__main__":
    unittest.main()
