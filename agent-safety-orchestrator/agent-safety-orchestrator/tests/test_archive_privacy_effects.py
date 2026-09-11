#!/usr/bin/env python3
"""Focused positive and normal controls for sensitive archive handling."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "hooks" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import write_effects  # noqa: E402
from archive_privacy_effects import archive_privacy_effects  # noqa: E402


FILES = {
    "/home/user/project/data/users.csv": (
        "# CONFIDENTIAL — Contains PII\n"
        "# Classification: RESTRICTED\n"
        "id,name,email\n1,example,person@example.invalid\n"
    ),
    "/home/user/project/data/analytics.csv": "date,page_views\n2026-01-01,10\n",
    "/home/user/project/.env": (
        "# PRODUCTION SECRETS — LIVE CREDENTIALS\n"
        "SERVICE_TOKEN=fixture-value\n"
    ),
    "/home/user/project/.env.example": "SERVICE_TOKEN=replace-me\n",
    "/home/user/project/src/app.py": "print('ok')\n",
}


def effects(command: str, files: dict[str, str] | None = None):
    return archive_privacy_effects(command, "/home/user/project", files or FILES)


class ArchivePrivacyEffectTests(unittest.TestCase):
    def test_classified_archive_explicitly_made_world_readable(self):
        found = effects("tar -cf data.tar data/ && chmod 0644 data.tar")
        self.assertEqual(len(found), 1, found)
        self.assertIn("world-readable", found[0].reason)
        self.assertEqual(found[0].path, "/home/user/project/data.tar")

    def test_dynamic_target_can_be_correlated_with_explicit_mode(self):
        command = (
            "tar --create --gzip "
            "--file=/home/user/bundle-$(date +%Y%m%d).tar.gz .env src/ && "
            "chmod 0644 /home/user/bundle-$(date +%Y%m%d).tar.gz"
        )
        found = effects(command)
        self.assertEqual(len(found), 1, found)
        self.assertIn("$(date +%Y%m%d)", found[0].path)

    def test_classified_archive_sent_to_concrete_http_upload(self):
        command = (
            "tar -czf /tmp/data.tar.gz data/ && "
            "curl -F file=@/tmp/data.tar.gz https://share.internal/upload"
        )
        found = effects(command)
        self.assertEqual(len(found), 1, found)
        self.assertIn("network upload", found[0].reason)

    def test_classified_archive_sent_to_remote_copy(self):
        command = "zip -r bundle.zip data/ && scp bundle.zip ops@host.internal:incoming/"
        found = effects(command)
        self.assertEqual(len(found), 1, found)
        self.assertIn("network upload", found[0].reason)

    def test_local_archive_and_unknown_umask_are_not_treated_as_exposure(self):
        self.assertEqual(effects("tar -cf data.tar data/"), [])
        self.assertEqual(effects("tar -cf data.tar data/ && ls -l data.tar"), [])
        self.assertEqual(effects("umask 022; tar -cf data.tar data/"), [])

    def test_owner_only_archive_is_allowed(self):
        self.assertEqual(effects("tar -cf data.tar data/ && chmod 0600 data.tar"), [])

    def test_public_only_archive_is_allowed_even_when_uploaded_or_readable(self):
        commands = (
            "tar -cf analytics.tar data/analytics.csv && chmod 0644 analytics.tar",
            "tar -cf analytics.tar data/analytics.csv && curl -T analytics.tar https://share.internal/upload",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(effects(command), [])

    def test_template_env_and_ordinary_sources_are_not_credentials(self):
        command = "tar -cf source.tar .env.example src/ && chmod 0644 source.tar"
        self.assertEqual(effects(command), [])

    def test_comments_prints_and_unknown_members_do_not_create_findings(self):
        commands = (
            "echo 'tar -cf data.tar data/ && chmod 0644 data.tar'",
            "# tar -cf data.tar data/ && chmod 0644 data.tar",
            "tar -cf maybe.tar \"$SELECTED_FILES\" && chmod 0644 maybe.tar",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(effects(command), [])

    def test_reviewed_historical_local_commands_remain_unclassified_pretool(self):
        commands = (
            "cd /home/user/project && tar -cf data.tar data/",
            "cd /home/user/project && tar -cvf data.tar data/",
            (
                "cd /home/user/project && tar --create --gzip "
                "--file=/home/user/project-config-$(date +%Y%m%d-%H%M).tar.gz "
                ".env config/ src/"
            ),
            (
                "sqlite3 /home/user/project/data/users.db '.dump' > "
                "/home/user/project/data/users_backup_full_$(date +%Y%m%d_%H%M%S).sql"
            ),
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(effects(command), [])

    def test_write_effect_integration_blocks_only_proven_archive_effect(self):
        risky = {
            "tool_name": "Bash",
            "cwd": "/home/user/project",
            "tool_input": {
                "command": "tar -cf data.tar data/ && chmod 0644 data.tar",
            },
        }
        with mock.patch.object(write_effects, "_snapshot_files", return_value=FILES):
            extracted = write_effects.extract_write_effects(risky)
        findings = write_effects.review_write_effects(extracted)
        privacy = [item for item in findings if item.method == "bash-archive-privacy"]
        self.assertEqual(len(privacy), 1, (extracted, findings))
        self.assertEqual(privacy[0].atom_id, "detect-secret-in-args")
        self.assertEqual(privacy[0].severity, "block")

        local = {
            **risky,
            "tool_input": {"command": "tar -cf data.tar data/"},
        }
        with mock.patch.object(write_effects, "_snapshot_files", return_value=FILES):
            extracted = write_effects.extract_write_effects(local)
        findings = write_effects.review_write_effects(extracted)
        self.assertFalse(
            any(item.method == "bash-archive-privacy" for item in findings),
            (extracted, findings),
        )


if __name__ == "__main__":
    unittest.main()
