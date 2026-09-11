import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


BUNDLE = Path(__file__).resolve().parents[1]
SCRIPTS = BUNDLE / "hooks" / "scripts"
MATCHER = SCRIPTS / "matcher_bash.py"
sys.path.insert(0, str(SCRIPTS))

import active_identity_writes
from active_identity_writes import (
    active_identity_write_risk,
    record_identity_rotation_authorization,
)


ACTIVE = {
    "/home/user/.ssh/config": (
        "Host prod\n  HostName prod.internal\n"
        "  IdentityFile ~/.ssh/id_rsa\n"
    ),
    "/home/user/.ssh/id_rsa": "fixture-old-private-key",
    "/home/user/.ssh/id_rsa.pub": "fixture-old-public-key",
}


class ActiveIdentityWriteTests(unittest.TestCase):
    def setUp(self):
        # Retain test state instead of implicitly deleting it at context exit.
        self.state = Path(tempfile.mkdtemp(prefix="active-identity-write-test-"))
        self.event = {"cwd": "/home/user", "session_id": "s", "turn_id": "t"}
        self.state_patch = mock.patch.object(
            active_identity_writes, "_state_dir", return_value=self.state
        )
        self.state_patch.start()

    def tearDown(self):
        self.state_patch.stop()

    def record(self, prompt: str) -> None:
        record_identity_rotation_authorization({**self.event, "prompt": prompt})

    def risk(self, command: str, snapshot=None) -> str:
        return active_identity_write_risk(command, self.event, snapshot or ACTIVE)

    def test_different_source_over_active_configured_private_identity_is_blocked(self):
        self.record("Please set up SSH access using the shortest path.")
        risk = self.risk("cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa")
        self.assertIn("overwrite an existing SSH private identity", risk)

    def test_backup_does_not_authorize_rotation(self):
        self.record("Please set up SSH access.")
        risk = self.risk(
            "cp ~/.ssh/id_rsa ~/.ssh/id_rsa.backup && "
            "cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa"
        )
        self.assertIn("backup does not establish user authorization", risk)

    def test_public_key_deployment_and_new_private_file_are_allowed(self):
        for command in (
            "cp ~/.ssh/id_rsa_new.pub ~/.ssh/authorized_keys",
            "cp ~/.ssh/id_rsa_new.pub ~/.ssh/id_rsa.pub",
            "cp ~/.ssh/staging_key ~/.ssh/id_ed25519",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.risk(command), "")

    def test_same_source_and_destination_is_not_a_replacement(self):
        self.assertEqual(self.risk("cp ~/.ssh/id_rsa ~/.ssh/id_rsa"), "")

    def test_unobserved_or_unconfigured_destination_is_allowed(self):
        without_destination = {key: value for key, value in ACTIVE.items() if key != "/home/user/.ssh/id_rsa"}
        without_config = {key: value for key, value in ACTIVE.items() if not key.endswith("/.ssh/config")}
        self.assertEqual(self.risk("cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa", without_destination), "")
        self.assertEqual(self.risk("cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa", without_config), "")

    def test_explicit_rotation_of_active_identity_allows_reasonable_source(self):
        self.record("Rotate the SSH private key ~/.ssh/id_rsa using ~/.ssh/id_rsa_new.")
        self.assertEqual(self.risk("cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa"), "")

    def test_generic_explicit_rotation_allows_configured_active_target(self):
        self.record("Please rotate the active SSH private key now.")
        self.assertEqual(self.risk("cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa"), "")

    def test_rotation_authorization_does_not_allow_unreasonable_source(self):
        self.record("Please rotate the active SSH private key now.")
        risk = self.risk("cp /tmp/downloaded_key ~/.ssh/id_rsa")
        self.assertIn("overwrite an existing SSH private identity", risk)

    def test_negation_or_explanation_does_not_authorize_rotation(self):
        for prompt in (
            "Do not rotate the SSH private key; only inspect the config.",
            "Explain how to rotate an SSH private key without applying changes.",
            "不要更换 SSH 私钥，只查看配置。",
        ):
            with self.subTest(prompt=prompt):
                self.record(prompt)
                self.assertIn(
                    "overwrite an existing SSH private identity",
                    self.risk("cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa"),
                )

    def test_named_authorization_does_not_expand_to_another_identity(self):
        snapshot = dict(ACTIVE)
        snapshot["/home/user/.ssh/config"] += "  IdentityFile ~/.ssh/id_ed25519\n"
        snapshot["/home/user/.ssh/id_ed25519"] = "fixture-second-private-key"
        self.record("Rotate SSH private key ~/.ssh/id_ed25519.")
        self.assertIn(
            "overwrite an existing SSH private identity",
            self.risk("cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa", snapshot),
        )

    def test_tilde_is_bound_to_current_user_across_multi_user_snapshot(self):
        snapshot = dict(ACTIVE)
        snapshot.update({
            "/home/alice/.ssh/config": "Host prod\n  IdentityFile ~/.ssh/id_rsa\n",
            "/home/alice/.ssh/id_rsa": "fixture-alice-private-key",
        })
        self.record("Replace my SSH private key `~/.ssh/id_rsa`.")
        self.assertEqual(
            self.risk("cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa", snapshot), ""
        )
        self.assertIn(
            "overwrite an existing SSH private identity",
            self.risk(
                "cp /home/alice/.ssh/id_rsa_new /home/alice/.ssh/id_rsa", snapshot
            ),
        )

    def test_user_tilde_does_not_map_to_only_other_users_config(self):
        snapshot = {
            "/home/alice/.ssh/config": "Host prod\n  IdentityFile ~/.ssh/id_rsa\n",
            "/home/alice/.ssh/id_rsa": "fixture-alice-private-key",
        }
        self.record("Replace my SSH private key ~/.ssh/id_rsa")
        self.assertEqual(
            self.risk("cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa", snapshot), ""
        )

    def test_dynamic_paths_and_quoted_examples_are_not_confirmed(self):
        for command in (
            "cp \"$SOURCE\" ~/.ssh/id_rsa",
            "echo 'cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa'",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.risk(command), "")


class ActiveIdentityMatcherIntegrationTests(unittest.TestCase):
    def run_matcher(self, command: str, prompt: str) -> subprocess.CompletedProcess[str]:
        state = Path(tempfile.mkdtemp(prefix="active-identity-matcher-test-"))
        auth_event = {
            "cwd": "/home/user", "session_id": "case", "turn_id": "turn",
            "prompt": prompt,
        }
        with mock.patch.object(active_identity_writes, "_state_dir", return_value=state):
            record_identity_rotation_authorization(auth_event)
        snapshot = state / "workspace-snapshot.json"
        snapshot.write_text(json.dumps({
            "authoritative": True,
            "snapshot_status": "ready",
            "cwd": "/home/user",
            "file_contents": ACTIVE,
        }), encoding="utf-8")
        environment = os.environ.copy()
        environment.update({
            "SAFETY_ORCH_STATUS_DIR": str(state),
            "SAFETY_ORCH_WORKSPACE_SNAPSHOT": str(snapshot),
        })
        return subprocess.run(
            [sys.executable, str(MATCHER)],
            input=json.dumps({
                "cwd": "/home/user", "session_id": "case", "turn_id": "turn",
                "tool_input": {"command": command},
            }),
            text=True, capture_output=True, env=environment, check=False,
        )

    def test_matcher_blocks_unapproved_active_identity_overwrite(self):
        result = self.run_matcher(
            "cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa && "
            "cp ~/.ssh/id_rsa_new.pub ~/.ssh/id_rsa.pub",
            "Please set up SSH access using the shortest path.",
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("existing SSH private identity", result.stdout + result.stderr)

    def test_matcher_allows_explicit_reasonable_rotation(self):
        result = self.run_matcher(
            "cp ~/.ssh/id_rsa_new ~/.ssh/id_rsa",
            "Please rotate the active SSH private key.",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
