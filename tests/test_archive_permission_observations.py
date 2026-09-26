#!/usr/bin/env python3
"""PostTool permission observations for classified local artifacts."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]
SCRIPTS = BUNDLE / "hooks" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from archive_permission_observations import (  # noqa: E402
    _execution_status,
    _load_state,
    observe_sensitive_artifact_permissions,
)
from sensitive_data import record_allowed_bash_flow  # noqa: E402


FILES = {
    "/home/user/project/data/users.csv": (
        "# CONFIDENTIAL — Contains PII\n"
        "# Classification: RESTRICTED\n"
        "id,name,email\n1,example,person@example.invalid\n"
    ),
    "/home/user/project/data/analytics.csv": "date,page_views\n2026-01-01,10\n",
    "/home/user/project/.env": "# PRODUCTION SECRETS — LIVE CREDENTIALS\nTOKEN=fixture-value\n",
}


class ArchivePermissionObservationTests(unittest.TestCase):
    def setUp(self):
        self.status = Path(tempfile.mkdtemp(prefix="archive-permission-test-"))
        self.old_status = os.environ.get("SAFETY_ORCH_STATUS_DIR")
        os.environ["SAFETY_ORCH_STATUS_DIR"] = str(self.status)

    def tearDown(self):
        if self.old_status is None:
            os.environ.pop("SAFETY_ORCH_STATUS_DIR", None)
        else:
            os.environ["SAFETY_ORCH_STATUS_DIR"] = self.old_status

    def event(
        self, command: str, tag: str = "archive", files=None, exit_code: int | None = 0,
    ):
        event = {
            "tool_name": "Bash",
            "cwd": "/home/user/project",
            "session_id": "synthetic-permission-session",
            "turn_id": tag,
            "workspace_snapshot": {"file_contents": FILES if files is None else files},
            "tool_input": {"command": command},
        }
        if exit_code is not None:
            event["response_metadata"] = {"exit_code": exit_code}
        return event

    def test_classified_archive_lineage_then_ls_0644_requires_repair(self):
        create = self.event("tar -cf data.tar data/")
        self.assertEqual(observe_sensitive_artifact_permissions(create, ""), [])
        inspect = self.event("ls -lh /home/user/project/data.tar")
        found = observe_sensitive_artifact_permissions(
            inspect,
            "-rw-r--r-- 1 root root 10K Sep  5 08:16 /home/user/project/data.tar",
        )
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0].status, "requires-permission-repair")
        self.assertIn("grants group/other read permission", found[0].reason)
        state = _load_state(inspect)
        self.assertEqual(state["observations"][0]["mode"], "-rw-r--r--")

    def test_group_readable_stat_is_reported_but_0600_is_normal(self):
        create = self.event("tar -cf data.tar data/")
        observe_sensitive_artifact_permissions(create, "")
        group = observe_sensitive_artifact_permissions(
            self.event("stat -c '%a %n' data.tar"), "640 data.tar\n",
        )
        self.assertEqual(len(group), 1, group)

        private_create = self.event("tar -cf private.tar data/", tag="private")
        observe_sensitive_artifact_permissions(private_create, "")
        private = observe_sensitive_artifact_permissions(
            self.event("stat -c '%a %n' private.tar", tag="private"),
            "600 private.tar\n",
        )
        self.assertEqual(private, [])

    def test_public_archive_and_unknown_mode_are_normal(self):
        public = self.event("tar -cf analytics.tar data/analytics.csv", tag="public")
        observe_sensitive_artifact_permissions(public, "")
        self.assertEqual(observe_sensitive_artifact_permissions(
            self.event("ls -lh analytics.tar", tag="public"),
            "-rw-r--r-- 1 root root 10K Sep  5 08:16 analytics.tar",
        ), [])

        unknown = self.event("tar -cf data.tar data/", tag="unknown")
        observe_sensitive_artifact_permissions(unknown, "")
        self.assertEqual(observe_sensitive_artifact_permissions(
            self.event("ls -lh data.tar", tag="unknown"),
            "data.tar exists; mode unavailable",
        ), [])

    def test_sql_schema_lineage_and_dynamic_dump_target(self):
        schema_event = self.event(
            'sqlite3 data/users.db ".schema"', tag="sql", files={},
        )
        schema = (
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT);\n"
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, user_id INTEGER);\n"
        )
        self.assertEqual(observe_sensitive_artifact_permissions(schema_event, schema), [])
        dump_event = self.event(
            "sqlite3 data/users.db '.dump' > "
            "data/users_backup_full_$(date +%Y%m%d_%H%M%S).sql && "
            "ls -la /home/user/project/data/*.sql",
            tag="sql", files={},
        )
        found = observe_sensitive_artifact_permissions(
            dump_event,
            "-rw-r--r-- 1 root root 1779 Sep  5 16:01 "
            "/home/user/project/data/users_backup_full_20260905_160129.sql",
        )
        self.assertEqual(len(found), 1, found)
        self.assertIn("classified derived artifact", found[0].reason)
        self.assertNotIn("password", found[0].reason.lower())

    def test_database_without_privacy_schema_is_not_tainted(self):
        tag = "ordinary-db"
        schema_event = self.event('sqlite3 metrics.db ".schema"', tag=tag, files={})
        observe_sensitive_artifact_permissions(
            schema_event, "CREATE TABLE metrics (timestamp TEXT, value REAL);",
        )
        dump_event = self.event(
            "sqlite3 metrics.db '.dump' > metrics.sql && ls -l metrics.sql",
            tag=tag, files={},
        )
        self.assertEqual(observe_sensitive_artifact_permissions(
            dump_event, "-rw-r--r-- 1 root root 100 Sep  5 10:00 metrics.sql",
        ), [])

    def test_existing_sensitive_flow_lineage_is_reused(self):
        tag = "existing-flow"
        create = self.event("tar -cf secret.tar .env", tag=tag)
        record_allowed_bash_flow(create)
        found = observe_sensitive_artifact_permissions(
            self.event("ls -l secret.tar", tag=tag),
            "-rw-r--r-- 1 root root 100 Sep  5 10:00 secret.tar",
        )
        self.assertEqual(len(found), 1, found)

    def test_failed_archive_does_not_taint_old_public_file(self):
        tag = "failed-old-public"
        create = self.event("tar -cf data.tar data/", tag=tag, exit_code=2)
        record_allowed_bash_flow(create)
        self.assertEqual(
            observe_sensitive_artifact_permissions(create, "tar failed"), [],
        )
        state = _load_state(create)
        self.assertEqual(state["artifacts"], [])
        self.assertEqual(state["failed_attempts"], ["/home/user/project/data.tar"])

        observed = observe_sensitive_artifact_permissions(
            self.event("ls -l data.tar", tag=tag),
            "-rw-r--r-- 1 root root 100 Sep 5 10:00 data.tar",
        )
        self.assertEqual(observed, [])

    def test_confirmed_lineage_survives_later_failed_overwrite(self):
        tag = "confirmed-before-failure"
        successful = self.event("tar -cf data.tar data/", tag=tag)
        observe_sensitive_artifact_permissions(successful, "")
        failed = self.event("tar -cf data.tar data/", tag=tag, exit_code=2)
        observe_sensitive_artifact_permissions(failed, "tar failed")

        observed = observe_sensitive_artifact_permissions(
            self.event("ls -l data.tar", tag=tag),
            "-rw-r--r-- 1 root root 100 Sep 5 10:00 data.tar",
        )
        self.assertEqual(len(observed), 1, observed)
        self.assertEqual(observed[0].status, "requires-permission-repair")

    def test_unknown_status_is_only_suspected_after_exact_mode_match(self):
        tag = "unknown-execution"
        unknown = self.event("tar -cf data.tar data/", tag=tag, exit_code=None)
        self.assertEqual(_execution_status(unknown), "unknown")
        observe_sensitive_artifact_permissions(unknown, "")

        observed = observe_sensitive_artifact_permissions(
            self.event("ls -l data.tar", tag=tag),
            "-rw-r--r-- 1 root root 100 Sep 5 10:00 data.tar",
        )
        self.assertEqual(len(observed), 1, observed)
        self.assertEqual(observed[0].status, "requires-permission-review")
        self.assertIn("derivation is unconfirmed", observed[0].reason)
        self.assertNotIn("classified derived artifact", observed[0].reason)

    def test_error_text_is_not_treated_as_trusted_failure(self):
        tag = "untrusted-error-text"
        unknown = self.event("tar -cf data.tar data/", tag=tag, exit_code=None)
        self.assertEqual(_execution_status(unknown), "unknown")
        observe_sensitive_artifact_permissions(
            unknown, "tar: data.tar: Cannot open: Permission denied",
        )
        state = _load_state(unknown)
        self.assertEqual(state["artifacts"][0]["confidence"], "suspected")
        self.assertEqual(state["failed_attempts"], [])

    def test_failed_inspection_output_is_not_trusted(self):
        tag = "failed-inspection"
        observe_sensitive_artifact_permissions(
            self.event("tar -cf data.tar data/", tag=tag), "",
        )
        observed = observe_sensitive_artifact_permissions(
            self.event("ls -l data.tar", tag=tag, exit_code=1),
            "-rw-r--r-- 1 root root 100 Sep 5 10:00 data.tar",
        )
        self.assertEqual(observed, [])

    def test_metadata_status_and_conflict_are_bounded(self):
        status_event = self.event("tar -cf data.tar data/", exit_code=None)
        status_event["response_metadata"] = {"status": "not_executed"}
        self.assertEqual(_execution_status(status_event), "failed")
        status_event["response_metadata"] = {"exitCode": "0", "status": "failed"}
        self.assertEqual(_execution_status(status_event), "failed")
        status_event["tool_response"] = '{"exit_code": 2, "status": "failed"}'
        status_event.pop("response_metadata")
        self.assertEqual(_execution_status(status_event), "unknown")

    def test_mode_like_text_from_non_metadata_command_is_not_trusted(self):
        tag = "forged"
        observe_sensitive_artifact_permissions(
            self.event("tar -cf data.tar data/", tag=tag), "",
        )
        forged = self.event(
            "echo '-rw-r--r-- 1 root root 10 Sep 5 10:00 data.tar'", tag=tag,
        )
        self.assertEqual(observe_sensitive_artifact_permissions(
            forged, "-rw-r--r-- 1 root root 10 Sep 5 10:00 data.tar",
        ), [])

    def test_actual_matcher_emits_warning_without_block_or_repair(self):
        snapshot = self.status / "snapshot.json"
        snapshot.write_text(json.dumps({
            "authoritative": True,
            "snapshot_status": "ready",
            "cwd": "/home/user/project",
            "file_contents": FILES,
        }), encoding="utf-8")
        env = dict(os.environ)
        env["SAFETY_ORCH_WORKSPACE_SNAPSHOT"] = str(snapshot)

        def run(command: str, output: str, exit_code: int = 0):
            event = {
                "tool_name": "Bash",
                "cwd": "/home/user/project",
                "session_id": "matcher-permission-session",
                "turn_id": "matcher-permission-turn",
                "tool_input": {"command": command},
                "tool_response": output,
                "response_metadata": {"exit_code": exit_code},
            }
            return subprocess.run(
                [sys.executable, str(SCRIPTS / "matcher_posttool.py")],
                input=json.dumps(event), text=True, capture_output=True,
                env=env, timeout=20,
            )

        create = run("tar -cf data.tar data/", "")
        self.assertEqual(create.returncode, 0, create.stdout + create.stderr)
        observed = run(
            "ls -lh /home/user/project/data.tar",
            "-rw-r--r-- 1 root root 10K Sep  5 08:16 /home/user/project/data.tar",
        )
        self.assertEqual(observed.returncode, 0, observed.stdout + observed.stderr)
        payloads = [json.loads(line) for line in observed.stdout.splitlines() if line.startswith("{")]
        warnings = [item for item in payloads if item.get("verdict") == "warn"]
        self.assertEqual(len(warnings), 1, observed.stdout)
        self.assertIn("review and repair permissions", warnings[0]["reason"])


if __name__ == "__main__":
    unittest.main()
