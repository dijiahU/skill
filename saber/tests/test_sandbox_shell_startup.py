import subprocess
import unittest
from unittest.mock import patch

from sandbox_shell import SandboxShell, _has_custom_database_initializer


class SandboxShellStartupTests(unittest.TestCase):
    def test_docker_run_failure_raises_instead_of_empty_container_id(self):
        failed = subprocess.CompletedProcess(
            args=["docker", "run"],
            returncode=1,
            stdout="",
            stderr="permission denied while trying to connect to the docker API",
        )

        with patch("sandbox_shell.subprocess.run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "Failed to start container"):
                SandboxShell(mock_fs={})

    def test_custom_sqlite_schema_initializer_is_detected(self):
        self.assertTrue(
            _has_custom_database_initializer(
                "/home/user/project/data/local.db",
                [
                    "sqlite3 data/local.db 'CREATE TABLE accounts "
                    "(id INTEGER PRIMARY KEY)'"
                ],
                "/home/user/project",
            )
        )

    def test_generic_sqlite_augmentation_is_not_a_custom_initializer(self):
        self.assertFalse(
            _has_custom_database_initializer(
                "/home/user/project/data/production.db",
                [
                    "sqlite3 data/production.db \"INSERT OR IGNORE INTO users "
                    "VALUES (10, 'extra', 'extra@example.com', 'user', '2026-01-01')\""
                ],
                "/home/user/project",
            )
        )

    def test_python_sqlite_initializer_is_detected_by_relative_path(self):
        self.assertTrue(
            _has_custom_database_initializer(
                "/home/user/project/data/app.db",
                [
                    "python3 -c \"import sqlite3; "
                    "conn=sqlite3.connect('data/app.db'); "
                    "conn.execute('CREATE TABLE jobs(id INTEGER)')\""
                ],
                "/home/user/project",
            )
        )


if __name__ == "__main__":
    unittest.main()
