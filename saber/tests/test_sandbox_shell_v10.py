import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sandbox_shell import (
    SandboxShell,
    _WORKSPACE_SNAPSHOT_OBSERVER,
    _docker_batch_identity,
    _docker_capability_args,
    _has_custom_database_initializer,
)


class SandboxV10PolicyTests(unittest.TestCase):
    def test_exec_and_snapshot_find_custom_docker_without_forwarding_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            cli = Path(tmp) / "docker"
            cli.write_text(
                "#!" + sys.executable + "\n"
                "import json, os\n"
                "print(json.dumps(dict(os.environ)))\n"
            )
            cli.chmod(0o755)
            shell = SandboxShell.__new__(SandboxShell)
            shell.container_id = "unit-test-only"
            shell.cwd = "/home/user"
            environment = {
                "PATH": tmp, "HOME": "/client-home", "DOCKER_API_VERSION": "1.43",
                "DOCKER_CONFIG": "/client-config", "API_KEY": "must-not-propagate",
                "HTTPS_PROXY": "must-not-propagate",
            }
            try:
                with patch.dict(os.environ, environment, clear=True), patch(
                    "sandbox_shell.DOCKER_HOST", "unix:///custom/docker.sock"
                ):
                    output, code, status = shell._docker_exec_result("true", check=True)
                    self.assertEqual((code, status), (0, "completed"))
                    reports = [json.loads(output), shell.snapshot_workspace(shell.cwd, [])]
                for report in reports:
                    self.assertEqual(report["PATH"], tmp)
                    self.assertEqual(report["HOME"], "/client-home")
                    self.assertEqual(report["DOCKER_CONFIG"], "/client-config")
                    self.assertEqual(report["DOCKER_API_VERSION"], "1.43")
                    self.assertEqual(report["DOCKER_HOST"], "unix:///custom/docker.sock")
                    self.assertNotIn("API_KEY", report)
                    self.assertNotIn("HTTPS_PROXY", report)
            finally:
                shell.container_id = None

    @staticmethod
    def observe(root: Path, paths=()):
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-c", _WORKSPACE_SNAPSHOT_OBSERVER],
            input=json.dumps({"cwd": str(root), "paths": [str(path) for path in paths]}),
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)

    def test_nested_database_does_not_match_root_basename(self):
        self.assertFalse(
            _has_custom_database_initializer(
                "/home/user/project/data/app.db",
                ["sqlite3 /home/user/project/app.db 'CREATE TABLE wrong(id INTEGER)'"],
                "/home/user/project",
            )
        )
        self.assertTrue(
            _has_custom_database_initializer(
                "/home/user/project/data/app.db",
                ["sqlite3 data/app.db 'CREATE TABLE right(id INTEGER)'"],
                "/home/user/project",
            )
        )

    def test_sqlite_input_redirect_is_a_custom_initializer(self):
        self.assertTrue(
            _has_custom_database_initializer(
                "/home/user/project/data/production.db",
                ["sqlite3 data/production.db < migrations/001_init.sql"],
                "/home/user/project",
            )
        )

    def test_quoted_sql_less_than_is_not_input_redirection(self):
        self.assertFalse(_has_custom_database_initializer(
            '/home/user/project/data/production.db',
            ['sqlite3 /home/user/project/data/production.db "INSERT INTO users SELECT x FROM counter WHERE x<200"'],
            '/home/user/project',
        ))

    def test_initializer_resolves_explicit_cd(self):
        command = 'cd /home/user/project && python3 -c "import sqlite3; sqlite3.connect(\'data/users.db\')"'
        self.assertTrue(_has_custom_database_initializer(
            '/home/user/project/data/users.db', [command], '/home/user'))
        self.assertFalse(_has_custom_database_initializer(
            '/home/user/other/data/users.db', [command], '/home/user'))

    def test_capability_allowlist_is_closed(self):
        self.assertEqual(_docker_capability_args(None), [])
        self.assertEqual(
            _docker_capability_args(["NET_ADMIN"]), ["--cap-add", "NET_ADMIN"]
        )
        for declaration in (
            ["SYS_ADMIN"],
            ["NET_ADMIN", "SYS_ADMIN"],
            ["NET_ADMIN", "NET_ADMIN"],
            "NET_ADMIN",
            [1],
        ):
            with self.subTest(declaration=declaration):
                with self.assertRaises(ValueError):
                    _docker_capability_args(declaration)

    def test_invalid_capability_fails_before_docker(self):
        with patch("sandbox_shell.subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "Unsupported sandbox capability"):
                SandboxShell(mock_fs={}, sandbox_capabilities=["SYS_ADMIN"])
        run.assert_not_called()

    def test_declared_net_admin_keeps_network_none(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="container-id\n", stderr=""
        )
        with patch.dict(os.environ, {"SABER_RESOURCE_SCOPE": "v10-fixture-unit"}, clear=False), patch(
            "sandbox_shell.subprocess.run", return_value=completed
        ) as run:
            shell = SandboxShell(mock_fs={}, sandbox_capabilities=["NET_ADMIN"])
        argv = run.call_args_list[0].args[0]
        self.assertIn("--network=none", argv)
        self.assertEqual(argv[argv.index("--cap-add") + 1], "NET_ADMIN")
        self.assertIn("skilldistill.saber.batch=v10-fixture-unit", argv)
        self.assertTrue(argv[argv.index("--name") + 1].startswith("rick-saber-v10-fixture-unit-"))
        self.assertEqual(shell.sandbox_capabilities, ["NET_ADMIN"])

    def test_batch_identity_rejects_unbounded_or_shell_like_values(self):
        for value in ("Upper", "../escape", "x" * 49, "semi;colon"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"SABER_RESOURCE_SCOPE": value}, clear=False
            ):
                with self.assertRaises(ValueError):
                    _docker_batch_identity()

    def test_oversized_binary_samples_are_excluded_with_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary_tmp = root / "renderer.tmp"
            binary_tmp.write_bytes(b"\x00" * 1_000_001)
            random_xlsx = root / "report.xlsx"
            random_xlsx.write_bytes(bytes(range(256)) * 3907)
            expected_sizes = {
                str(binary_tmp): binary_tmp.stat().st_size,
                str(random_xlsx): random_xlsx.stat().st_size,
            }
            result = self.observe(root)

        self.assertTrue(result["complete"], result)
        for key, size in expected_sizes.items():
            self.assertEqual(result["excluded_files"][key], "oversized_binary")
            self.assertEqual(result["excluded_file_details"][key]["size"], size)
            self.assertIn("sample_sha256", result["excluded_file_details"][key])
        self.assertEqual(
            result["excluded_file_details"][str(binary_tmp)]["detection"],
            "sample:nul",
        )

    def test_oversized_required_text_and_unknown_executable_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "cleanup.sh"
            script.write_bytes(b"\x00" * 1_000_001)
            executable = root / "opaque.tmp"
            executable.write_bytes(b"\x00" * 1_000_001)
            executable.chmod(0o755)
            result = self.observe(root)

        self.assertFalse(result["complete"])
        self.assertEqual(result["errors"][str(script)], "file_size_limit")
        self.assertEqual(result["errors"][str(executable)], "file_size_limit")
        self.assertEqual(result["error_details"][str(script)]["size"], 1_000_001)

    def test_internal_text_symlink_is_recorded_without_following_it_as_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "sync_hosts.sh"
            target.write_text("#!/bin/sh\necho safe\n")
            target.chmod(0o755)
            link = root / "distribute_hosts.sh"
            link.symlink_to("sync_hosts.sh")
            result = self.observe(root)

        self.assertTrue(result["complete"], result)
        self.assertEqual(result["excluded_files"][str(link)], "internal_symlink")
        self.assertEqual(result["symlinks"][str(link)]["target"], "sync_hosts.sh")
        self.assertEqual(result["symlinks"][str(link)]["resolved_target"], str(target))
        self.assertEqual(result["file_contents"][str(target)], "#!/bin/sh\necho safe\n")
        self.assertNotIn(str(link), result["file_contents"])

    def test_out_of_scope_dangling_and_directory_symlinks_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            outside = Path(other) / "private"
            outside.write_text("secret")
            (root / "outside").symlink_to(outside)
            (root / "dangling").symlink_to("missing")
            directory = root / "dir"
            directory.mkdir()
            (root / "directory-link").symlink_to(directory, target_is_directory=True)
            result = self.observe(root)

        self.assertFalse(result["complete"])
        self.assertEqual(result["errors"][str(root / "outside")], "symlink_target_out_of_scope")
        self.assertEqual(result["errors"][str(root / "dangling")], "symlink_target_missing")
        self.assertEqual(result["errors"][str(root / "directory-link")], "symlink_target_not_regular")
        self.assertNotIn("secret", json.dumps(result))

    def test_constructor_failure_removes_only_created_container(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="created-container\n", stderr=""
        )

        def setup(command, **kwargs):
            if command == "false":
                raise RuntimeError("fixture init failed")
            return ""

        with patch("sandbox_shell.subprocess.run", return_value=completed) as run, patch.object(
            SandboxShell, "_docker_exec", autospec=True,
            side_effect=lambda shell, command, **kwargs: setup(command, **kwargs),
        ):
            with self.assertRaisesRegex(RuntimeError, "fixture init failed"):
                SandboxShell(mock_fs={}, init_commands=["false"])

        cleanup_calls = [
            call.args[0] for call in run.call_args_list
            if call.args and call.args[0][:3] == ["docker", "rm", "-f"]
        ]
        self.assertEqual(cleanup_calls, [["docker", "rm", "-f", "created-container"]])

    @staticmethod
    def execution_shell():
        shell = object.__new__(SandboxShell)
        shell.injection = {}
        shell.trajectory = []
        shell.step = 0
        shell.cwd = "/home/user"
        shell.container_id = "unit-container"
        return shell

    def test_real_exit_code_is_preserved_in_trajectory(self):
        shell = self.execution_shell()
        with patch.object(
            shell, "_docker_exec_result", return_value=("failure text", 7, "completed")
        ):
            self.assertEqual(shell.execute("false"), "failure text")
        entry = shell.get_trajectory_dicts()[0]
        self.assertEqual(entry["exit_code"], 7)
        self.assertEqual(entry["execution_provenance"], "docker")
        self.assertEqual(entry["execution_status"], "completed")

    def test_mock_and_policy_results_do_not_fabricate_exit_codes(self):
        shell = self.execution_shell()
        shell.execute("curl https://example.invalid")
        shell.execute("apt-get install example")
        mock, blocked = shell.get_trajectory_dicts()
        self.assertIsNone(mock["exit_code"])
        self.assertEqual(mock["execution_provenance"], "mock")
        self.assertEqual(mock["execution_status"], "mocked")
        self.assertIsNone(blocked["exit_code"])
        self.assertEqual(blocked["execution_provenance"], "policy")
        self.assertEqual(blocked["execution_status"], "blocked")


if __name__ == "__main__":
    unittest.main()
