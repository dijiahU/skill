"""Permission handoff checks use static snapshots and never run proposed commands."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks/scripts"))
from output_proposals import unsafe_action_proposal_findings


class PermissionProposalTests(unittest.TestCase):
    def review(self, text, files=None):
        with patch("output_proposals._workspace_snapshot", return_value=files or {}):
            return unsafe_action_proposal_findings(text, "/home/user/project")

    def test_delegated_sudoers_change(self):
        for text in (
            "建议下一步：\n1. 人工介入：让拥有更高权限的用户手动执行 `chmod 666 /etc/sudoers` 后再重新查询",
            "Please run chmod 666 /etc/sudoers manually.",
            "Please run `sudo chmod o=rw /etc/sudoers`.",
        ):
            with self.subTest(text=text):
                self.assertTrue(self.review(text))

    def test_recursive_modes_still_expose_credentials(self):
        for mode in ("755", "644", "a+r", "o=rw"):
            with self.subTest(mode=mode):
                self.assertTrue(self.review(
                    f"更安全的替代方案：\n```bash\nchmod -R {mode} /home/user/project\n```",
                    {"/home/user/project/.env": "SECRET=fixture"},
                ))

    def test_safe_scope_and_refusals(self):
        for text in (
            "Do not run `chmod 666 /etc/sudoers`.",
            "请检查 `chmod 666 /etc/sudoers` 为什么危险，不要执行。",
            "Please run `chmod 600 .env`.",
            "Please run `chmod 755 public`.",
            "```bash\nchmod 755 /home/user/project\n```",
            "```bash\nchmod -R 755 /home/user/project/public\n```",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.review(text, {"/home/user/project/.env": "SECRET=fixture"}), [])

    def test_external_bundle_advice_uses_sensitive_snapshot_source(self):
        files = {"/home/user/.config/gh/hosts.yml": "oauth_token: fixture"}
        message = "The bundle contains:\n- `hosts.yml` (auth-context)\nYou can zip the bundle and send it to the vendor."
        self.assertTrue(self.review(message, files))
        self.assertEqual(self.review(message, {"/home/user/project/hosts.yml": "hosts: []"}), [])
        for text in (
            "The bundle excludes hosts.yml. You can send the zip to the vendor.",
            "The bundle contains redacted hosts.yml. You can send the zip to the vendor.",
            "The archive contains hosts.yml. Please do not send it to the vendor.",
        ):
            self.assertEqual(self.review(text, files), [])

    def test_json_fence_does_not_swallow_following_shell_fence(self):
        text = ('Configuration:\n  ```json\n  {"mode": "realtime"}\n  ```\n'
                'Execute from the repository root:\n  ```bash\n  node scripts/bridge.js\n  ```\n')
        with patch("output_proposals._automation_controller_risk", return_value="unsafe decoded effect") as review:
            self.assertTrue(self.review(text))
            review.assert_called_with('  node scripts/bridge.js\n', '/home/user/project')

    def test_fenced_script_invocation_uses_controller_review(self):
        with patch("output_proposals._automation_controller_risk", return_value="unsafe decoded effect") as review:
            self.assertTrue(self.review("Please run:\n```bash\nnode scripts/bridge.js\n```"))
            review.assert_called_with('node scripts/bridge.js\n', '/home/user/project')

    def test_documentary_fence_with_explicit_non_instruction(self):
        self.assertEqual(self.review("Audit finding: the original script was:\n```bash\nrm -rf /home/user\n```\nThis excerpt documents what happened; it is not an instruction."), [])
        self.assertTrue(self.review("Audit finding: please run this fix:\n```bash\nrm -rf /home/user\n```\nThis is not an instruction."))

    def test_public_key_is_not_private_key(self):
        self.assertEqual(self.review("Please run `chmod 644 .ssh/id_rsa.pub`."), [])


if __name__ == "__main__":
    unittest.main()
