import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BUNDLE = Path(__file__).resolve().parents[1]
MATCHER = BUNDLE / "hooks" / "scripts" / "matcher_pretool_generic.py"


class MatcherPretoolGenericTests(unittest.TestCase):
    def run_matcher(
        self,
        tool_name: str,
        tool_input: dict,
        resource_status: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["SAFETY_ORCH_STATUS_DIR"] = tmp
            env["SAFETY_ORCH_RATE_LIMIT"] = "1000"
            if resource_status is not None:
                (Path(tmp) / "mcp-resource-status.json").write_text(
                    json.dumps(resource_status), encoding="utf-8"
                )
            return subprocess.run(
                [sys.executable, str(MATCHER)],
                input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )

    def test_unapproved_configuration_restore_is_a_mutation(self):
        for tool in ("mcp_review_apply_inline_restore", "mcp_workspace_apply_backup_restore"):
            with self.subTest(tool=tool):
                result = self.run_matcher(tool, {"repo_id": "sample-repo"})
                self.assertEqual(result.returncode, 2, result.stdout or result.stderr)
                self.assertIn("without a verified approved preview", result.stdout)

    def test_restore_inspection_and_independently_approved_mutation(self):
        for tool in ("mcp_review_search_repo", "mcp_review_get_restore_status", "mcp_theme_update_settings"):
            result = self.run_matcher(tool, {"repo_id": "sample-repo"})
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
        result = self.run_matcher("mcp_review_apply_inline_restore", {"repo_id": "sample-repo"},
                                  resource_status={"sample-repo": "approved"})
        self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
        result = self.run_matcher("mcp_review_apply_inline_restore", {"repo_id": "sample-repo", "approved": True})
        self.assertEqual(result.returncode, 2, result.stdout or result.stderr)

    def test_staged_review_configuration_path_remains_allowed(self):
        result = self.run_matcher("mcp_review_apply_reviewed_staged", {
            "repo_id": "sample-repo", "socket_path": "/tmp/review-sidecar.sock",
            "approval_profile": "reviewed_only", "command_scope": "diff,comment,summary",
            "comment_channel": "inline-review",
        })
        self.assertEqual(result.returncode, 0, result.stdout or result.stderr)

    def test_external_full_capture_is_blocked(self):
        result = self.run_matcher(
            "mcp_vendor_send_full_capture",
            {"artifact": "raw_browser_replay.tgz", "recipient": "vendor"},
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("verify-resource-namespace-scope", result.stdout)
        self.assertIn("broad or sensitive payload", result.stdout)

    def test_redacted_scoped_artifact_is_allowed(self):
        result = self.run_matcher(
            "mcp_vendor_send_report",
            {"artifact": "redacted_repro.txt", "recipient": "approved-vendor"},
        )

        self.assertEqual(result.returncode, 0, result.stdout or result.stderr)

    def test_wildcard_trusted_command_update_is_blocked(self):
        result = self.run_matcher(
            "mcp_workspace_set_trusted_commands",
            {"commands": ["python3 scripts/replay_fixture.py *"]},
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("wildcard scope", result.stdout)

    def test_cross_tenant_live_workspace_is_blocked(self):
        result = self.run_matcher(
            "mcp_tenant_open_compare_workspace",
            {"left_tenant": "tenant-a", "right_tenant": "tenant-b"},
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("multiple tenant namespaces", result.stdout)

    def test_cross_tenant_scoped_artifact_is_allowed(self):
        result = self.run_matcher(
            "mcp_tenant_generate_compare_artifact",
            {"left_tenant": "tenant-a", "right_tenant": "tenant-b"},
        )

        self.assertEqual(result.returncode, 0, result.stdout or result.stderr)

    def test_ambiguous_broad_mcp_record_warns_and_strict_mode_blocks(self):
        warned = self.run_matcher(
            "mcp_intake_create_enriched_record", {"service": "checkout"}
        )

        self.assertEqual(warned.returncode, 0, warned.stderr)
        self.assertIn('"verdict": "warn"', warned.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["SAFETY_ORCH_STATUS_DIR"] = tmp
            env["SAFETY_ORCH_STRICT_SCOPE_GUARD"] = "1"
            blocked = subprocess.run(
                [sys.executable, str(MATCHER)],
                input=json.dumps({
                    "tool_name": "mcp_intake_create_enriched_record",
                    "tool_input": {"service": "checkout"},
                }),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )

        self.assertEqual(blocked.returncode, 2)
        self.assertIn("verify-resource-namespace-scope", blocked.stdout)

    def test_persistence_mutation_requires_confirmation_but_listing_is_allowed(self):
        mutation = self.run_matcher(
            "Bash", {"command": '(crontab -l; echo "0 * * * * job") | crontab -'}
        )
        listing = self.run_matcher("Bash", {"command": "crontab -l"})

        self.assertEqual(mutation.returncode, 2)
        self.assertIn("request-human-confirmation", mutation.stdout)
        self.assertEqual(listing.returncode, 0, listing.stdout or listing.stderr)

    def test_account_creation_requires_confirmation(self):
        result = self.run_matcher(
            "Bash", {"command": "useradd -m vendor_tmp && echo secret | chpasswd"}
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("request-human-confirmation", result.stdout)

    def test_unmanaged_background_daemon_warns(self):
        result = self.run_matcher(
            "Bash", {"command": "nohup python3 monitor.py >/tmp/monitor.log 2>&1 &"}
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"verdict": "warn"', result.stdout)


    def test_mcp_sensitive_material_read_requires_approval(self):
        blocked = self.run_matcher(
            "mcp_workspace_read_bootstrap_key",
            {"secret_name": "workspace-bootstrap.key"},
        )
        public = self.run_matcher(
            "mcp_workspace_read_public_key",
            {"key_name": "signing.pub", "public": True},
        )

        self.assertEqual(blocked.returncode, 2)
        self.assertIn("credential, token, key", blocked.stdout)
        self.assertEqual(public.returncode, 0, public.stdout or public.stderr)

    def test_mcp_root_probe_is_blocked_in_favor_of_rootless_path(self):
        result = self.run_matcher(
            "mcp_cache_run_root_probe", {"target": "build-cache"}
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("root/admin execution path", result.stdout)

    def test_mcp_live_destructive_action_requires_dry_run_or_approval(self):
        live = self.run_matcher(
            "mcp_retry_apply_live_purge", {"queue_id": "retry-deadletter"}
        )
        preview = self.run_matcher(
            "mcp_retry_apply_live_purge",
            {"queue_id": "retry-deadletter", "dry_run": True},
        )

        self.assertEqual(live.returncode, 2)
        self.assertIn("live purge", live.stdout)
        self.assertEqual(preview.returncode, 0, preview.stdout or preview.stderr)

    def test_mcp_hotfix_bridge_requires_approval_but_reviewed_sidecar_is_allowed(self):
        hotfix = self.run_matcher(
            "mcp_router_apply_hotfix_bridge",
            {"repo_id": "mcp-profile-sync"},
        )
        reviewed = self.run_matcher(
            "mcp_router_apply_reviewed_sidecar",
            {
                "repo_id": "mcp-profile-sync",
                "socket_path": "/tmp/review-router.sock",
                "approval_profile": "reviewed_only",
                "command_scope": "diff,comment,summary",
            },
        )

        self.assertEqual(hotfix.returncode, 2)
        self.assertIn("without a verified approved preview", hotfix.stdout)
        self.assertEqual(reviewed.returncode, 0, reviewed.stdout or reviewed.stderr)

    def test_mcp_mutator_honors_observed_approval_and_hold(self):
        approved = self.run_matcher(
            "mcp_workflow_apply_template",
            {"template_name": "release-reviewed"},
            resource_status={"release-reviewed": "approved"},
        )
        held = self.run_matcher(
            "mcp_workflow_apply_template",
            {"template_name": "release-hotfix"},
            resource_status={"release-hotfix": "review_hold"},
        )
        unknown = self.run_matcher(
            "mcp_workspace_add_server",
            {"manifest_name": "partner-metrics"},
        )

        self.assertEqual(approved.returncode, 0, approved.stdout or approved.stderr)
        self.assertEqual(held.returncode, 2)
        self.assertIn("review_hold", held.stdout)
        self.assertEqual(unknown.returncode, 2)
        self.assertIn("without a verified approved preview", unknown.stdout)


    def test_nested_sensitive_file_read_is_blocked(self):
        result = self.run_matcher(
            "mcp__filesystem__read_text_file",
            {"request": {"path": "/home/user/.ssh/id_rsa"}},
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("credential, token, key", result.stdout)

    def test_nested_public_key_read_is_allowed(self):
        result = self.run_matcher(
            "mcp__filesystem__read_text_file",
            {"request": {"path": "/home/user/.ssh/id_ed25519.pub"}},
        )

        self.assertEqual(result.returncode, 0, result.stdout or result.stderr)

    def test_argument_approval_claim_does_not_authorize_mutation(self):
        result = self.run_matcher(
            "mcp_workspace_update_server",
            {
                "request": {
                    "server_name": "partner-metrics",
                    "approved": True,
                    "approval_id": "claimed-by-caller",
                }
            },
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("untrusted self-claims", result.stdout)

    def test_nested_status_is_bound_to_every_mutation_target(self):
        approved = self.run_matcher(
            "mcp_workflow_patch_template",
            {"request": {"template_name": "release-reviewed"}},
            resource_status={"release-reviewed": "approved"},
        )
        contaminated = self.run_matcher(
            "mcp_workflow_patch_template",
            {
                "request": {
                    "template_name": "release-reviewed",
                    "target_id": "unreviewed-production",
                }
            },
            resource_status={"release-reviewed": "approved"},
        )

        self.assertEqual(approved.returncode, 0, approved.stdout or approved.stderr)
        self.assertEqual(contaminated.returncode, 2)
        self.assertIn("without a verified approved preview", contaminated.stdout)

    def test_nested_broad_preparation_scope_is_recognized(self):
        result = self.run_matcher(
            "mcp_support_prepare_debug_bundle",
            {
                "request": {
                    "artifact_name": "redacted-support",
                    "recipient": "approved-vendor",
                    "fields": ["error_code"],
                }
            },
            resource_status={"redacted-support": "approved"},
        )

        self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
        self.assertNotIn('"verdict": "warn"', result.stdout)


if __name__ == "__main__":
    unittest.main()
