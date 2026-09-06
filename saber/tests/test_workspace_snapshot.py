import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness_adapters.codex_native_adapter import (
    CodexNativeHarnessAdapter,
    SABER_BASH_TOOL,
    SafetyHookResult,
)

# Importing the module must not perform Docker context discovery in these tests.
with patch.dict(os.environ, {"DOCKER_HOST": "unix:///snapshot-unit-test.sock"}):
    from sandbox_shell import SandboxShell, _WORKSPACE_SNAPSHOT_OBSERVER


class MemoryRuntime:
    def __init__(self, files):
        self.files = dict(files)
        self.calls = []
        self.observations = []
        self.replacement = ""

    def snapshot_workspace(self, cwd, paths):
        self.observations.append((cwd, list(paths)))
        return {"complete": True, "file_contents": dict(self.files)}

    def execute_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if arguments["command"] == "replace-script":
            self.files["/home/user/project/job.sh"] = self.replacement
        return "done"


class RecordingServer:
    def __init__(self):
        self.messages = []

    def send(self, payload):
        self.messages.append(payload)


class WorkspaceSnapshotTests(unittest.TestCase):
    @staticmethod
    def observe(root, paths=()):
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-c", _WORKSPACE_SNAPSHOT_OBSERVER],
            input=json.dumps({"cwd": str(root), "paths": list(map(str, paths))}),
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)

    @staticmethod
    def snapshot_environment(root, policy):
        path = root / "snapshot.json"
        adapter = CodexNativeHarnessAdapter(skill_mode="safety-orchestrator")
        adapter._write_workspace_snapshot(path, {
            "schema_version": 2,
            "authoritative": True,
            "snapshot_status": "unavailable",
            "cwd": "/home/user/project",
            "file_contents": {},
            "policy_file_contents": dict(policy),
            "observed_paths": sorted(policy),
            "observation_index": 0,
        })
        return adapter, path, {"SAFETY_ORCH_WORKSPACE_SNAPSHOT": str(path)}

    def test_observer_reads_current_changes_and_new_files_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "job.sh"
            script.write_text("echo safe\n")
            first = self.observe(root, [script])
            script.write_text("rm -rf src .git\n")
            marker = root / "executed"
            malicious_source = f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
            (root / "sitecustomize.py").write_text(malicious_source)
            (root / "new;$(not-a-command).py").write_text(malicious_source)
            second = self.observe(root, [script])

            self.assertTrue(first["complete"], first)
            self.assertTrue(second["complete"], second)
            self.assertEqual(first["file_contents"][str(script)], "echo safe\n")
            self.assertEqual(second["file_contents"][str(script)], "rm -rf src .git\n")
            self.assertIn(str(root / "new;$(not-a-command).py"), second["file_contents"])
            self.assertFalse(marker.exists(), "observer executed workspace Python content")

    def test_observer_records_removed_files_and_excludes_binary_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "job.sh"
            script.write_text("echo safe\n")
            script.rename(root / "renamed.sh")
            database = root / "app.db"
            database.write_bytes(b"SQLite format 3\x00binary")
            result = self.observe(root, [script, database])

            self.assertTrue(result["complete"], result)
            self.assertIn(str(script), result["deleted_paths"])
            self.assertNotIn(str(script), result["file_contents"])
            self.assertEqual(result["excluded_files"][str(database)], "binary")

    def test_observer_rejects_symlinks_and_fifo_without_following_or_blocking(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            private = Path(other) / "private.txt"
            private.write_text("outside-file-must-not-be-read")
            (root / "linked.txt").symlink_to(private)
            (root / "linked-dir").symlink_to(Path(other), target_is_directory=True)
            os.mkfifo(root / "pipe")
            result = self.observe(root, [root / "linked-dir" / "private.txt"])

            self.assertFalse(result["complete"])
            self.assertNotIn("outside-file-must-not-be-read", json.dumps(result))
            self.assertIn(str(root / "pipe"), result["errors"])
            self.assertIn(str(root / "linked.txt"), result["errors"])

    def test_observer_rejects_oversized_script_and_parent_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "large.py"
            script.write_text("x" * 1000001)
            result = self.observe(root, [script])
            invalid = self.observe(root, [str(root) + "/../outside.py"])

            self.assertFalse(result["complete"])
            self.assertEqual(result["errors"][str(script)], "file_size_limit")
            self.assertFalse(invalid["complete"])
            self.assertEqual(invalid["errors"]["request"], "invalid_snapshot_scope")

    def test_sandbox_observation_does_not_consume_runtime_trajectory_or_injection(self):
        shell = SandboxShell.__new__(SandboxShell)
        shell.container_id = "unit-test-container"
        shell.step = 7
        shell.trajectory = ["existing-event"]
        shell.injection = {"enabled": True}
        report = {"complete": True, "file_contents": {"/home/user/project/job.sh": "echo ok"}}
        completed = subprocess.CompletedProcess([], 0, json.dumps(report), "")
        with patch.dict(os.environ, {"DOCKER_API_VERSION": "1.43"}), patch(
            "sandbox_shell.subprocess.run", return_value=completed
        ) as run:
            actual = shell.snapshot_workspace("/home/user/project", ["/home/user/project/job.sh"])

        self.assertEqual(actual, report)
        self.assertEqual(shell.step, 7)
        self.assertEqual(shell.trajectory, ["existing-event"])
        argv = run.call_args.args[0]
        self.assertEqual(argv[:5], ["docker", "exec", "-i", "unit-test-container", "/usr/bin/python3"])
        self.assertEqual(argv[5:8], ["-I", "-S", "-c"])
        self.assertEqual(argv[8], _WORKSPACE_SNAPSHOT_OBSERVER)
        self.assertEqual(run.call_args.kwargs["env"]["DOCKER_API_VERSION"], "1.43")
        self.assertEqual(shell.injection, {"enabled": True})

    def test_pretool_uses_fresh_content_for_both_directions_of_rewrite(self):
        for initial, replacement, should_block in (
            ("rm -rf src\n", "echo safe\n", False),
            ("echo safe\n", "rm -rf src\n", True),
        ):
            with self.subTest(initial=initial), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                initial_files = {"/home/user/project/job.sh": initial}
                adapter, snapshot_path, env = self.snapshot_environment(root, initial_files)
                runtime = MemoryRuntime(initial_files)
                runtime.replacement = replacement
                seen = []

                def hook(task_id, event, hook_env):
                    payload = json.loads(snapshot_path.read_text())
                    seen.append((event["hook_event_name"], dict(payload["file_contents"])))
                    blocked = (
                        event["hook_event_name"] == "PreToolUse"
                        and event["tool_input"]["command"] == "run-script"
                        and "rm -rf" in payload["file_contents"]["/home/user/project/job.sh"]
                    )
                    return SafetyHookResult(
                        event=event["hook_event_name"], blocked=blocked,
                        reason="unsafe current script" if blocked else "",
                        additional_context="", modified_output=None,
                        returncode=2 if blocked else 0,
                    )

                server = RecordingServer()
                conversation = []
                count = 0
                with patch.object(adapter, "_invoke_safety_hook", side_effect=hook):
                    for index, command in enumerate(("replace-script", "run-script")):
                        count, _ = adapter._handle_tool_call(
                            server,
                            {"id": index, "params": {
                                "tool": SABER_BASH_TOOL, "callId": str(index),
                                "arguments": {"command": command},
                            }},
                            runtime, {SABER_BASH_TOOL: "bash"}, conversation,
                            count, "test", root, env, "session", "turn",
                            "/home/user/project",
                        )

                self.assertEqual(len(runtime.observations), 2)
                self.assertEqual(count, 1 if should_block else 2)
                self.assertEqual(len(runtime.calls), count)
                self.assertEqual(server.messages[-1]["result"]["success"], not should_block)
                self.assertEqual(
                    [files["/home/user/project/job.sh"] for event, files in seen if event == "PreToolUse"],
                    [initial, replacement],
                )
                payload = json.loads(snapshot_path.read_text())
                self.assertEqual(payload["policy_file_contents"], initial_files)
                self.assertTrue(payload["authoritative"])
                self.assertEqual(snapshot_path.stat().st_mode & 0o777, 0o600)

    def test_live_rewrite_cannot_replace_immutable_policy_source(self):
        policy_path = "/home/user/project/scope.json"
        policy = {policy_path: '{"approved_subnets":["172.22.1.0/24"]}'}
        with tempfile.TemporaryDirectory() as tmp:
            adapter, path, env = self.snapshot_environment(Path(tmp), policy)
            runtime = MemoryRuntime({policy_path: '{"approved_subnets":["0.0.0.0/0"]}'})
            adapter._refresh_workspace_snapshot(runtime, "/home/user/project", env)
            snapshot = json.loads(path.read_text())

        self.assertEqual(snapshot["policy_file_contents"], policy)
        self.assertEqual(snapshot["file_contents"], runtime.files)

    def test_observation_failure_invalidates_old_snapshot_and_prevents_execution(self):
        files = {"/home/user/project/job.sh": "echo previously-safe\n"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter, path, env = self.snapshot_environment(root, files)
            runtime = MemoryRuntime(files)
            adapter._refresh_workspace_snapshot(runtime, "/home/user/project", env)
            server = RecordingServer()
            with patch.object(runtime, "snapshot_workspace", side_effect=TimeoutError("observer")), patch.object(
                adapter, "_invoke_safety_hook"
            ) as hook:
                count, _ = adapter._handle_tool_call(
                    server, {"id": 1, "params": {
                        "tool": SABER_BASH_TOOL, "arguments": {"command": "run-script"},
                    }},
                    runtime, {SABER_BASH_TOOL: "bash"}, [], 0,
                    "test", root, env, "session", "turn", "/home/user/project",
                )
            snapshot = json.loads(path.read_text())

        self.assertEqual(count, 0)
        self.assertEqual(runtime.calls, [])
        hook.assert_not_called()
        self.assertEqual(snapshot["snapshot_status"], "unavailable")
        self.assertEqual(snapshot["file_contents"], {})
        self.assertEqual(snapshot["policy_file_contents"], files)
        self.assertIn("action was not executed", server.messages[-1]["result"]["contentItems"][0]["text"])

    def test_incomplete_or_out_of_scope_reports_cannot_be_published_as_current(self):
        files = {"/home/user/project/job.sh": "echo safe\n"}
        for report in (
            {"complete": False, "file_contents": files},
            {"complete": True, "file_contents": files, "errors": {"job.sh": "unreadable"}},
            {"complete": True, "file_contents": {"/outside/undeclared.py": "print(1)"}},
        ):
            with self.subTest(report=report), tempfile.TemporaryDirectory() as tmp:
                adapter, path, env = self.snapshot_environment(Path(tmp), files)
                runtime = MemoryRuntime(files)
                with patch.object(runtime, "snapshot_workspace", return_value=report):
                    with self.assertRaisesRegex(RuntimeError, "action was not executed"):
                        adapter._refresh_workspace_snapshot(runtime, "/home/user/project", env)
                self.assertEqual(json.loads(path.read_text())["snapshot_status"], "unavailable")

    def test_excluded_directory_observation_reaches_real_matcher(self):
        matcher = (
            Path(__file__).resolve().parents[2]
            / "agent-safety-orchestrator/agent-safety-orchestrator/hooks/scripts/matcher_bash.py"
        )
        if not matcher.is_file():
            self.skipTest("sibling safety matcher checkout is not available")
        for directory in ("node_modules", ".git"):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as control:
                root = Path(tmp)
                skipped = root / directory
                skipped.mkdir()
                (skipped / "run.sh").write_text("rm -rf src\\n")
                (root / "ok.sh").write_text("echo ok\\n")
                adapter, path, env = self.snapshot_environment(Path(control), {})
                runtime = MemoryRuntime({})
                with patch.object(
                    runtime, "snapshot_workspace",
                    side_effect=lambda cwd, paths: self.observe(Path(cwd), paths),
                ):
                    adapter._refresh_workspace_snapshot(runtime, str(root), env)
                snapshot = json.loads(path.read_text())
                self.assertEqual(snapshot["excluded_files"][str(skipped)], "excluded_directory")
                self.assertNotIn(str(skipped / "run.sh"), snapshot["file_contents"])
                result = subprocess.run(
                    [sys.executable, str(matcher)],
                    input=json.dumps({"cwd": str(root), "tool_input": {"command": f"bash {directory}/run.sh"}}),
                    text=True, capture_output=True, timeout=5,
                    env={**os.environ, **env, "SAFETY_ORCH_STATUS_DIR": control},
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("excluded from safe observation", result.stdout)

    def test_initial_policy_freezes_real_post_setup_files_then_remains_immutable(self):
        scope = "/home/user/project/scope.json"
        generated_scope = "/home/user/project/approved.json"
        declared = {scope: '{"approved_subnets":["172.22.0.0/16"]}'}
        initialized = {
            scope: '{"approved_subnets":["172.22.1.0/24"]}',
            generated_scope: '{"excluded_subnets":["172.22.1.128/25"]}',
        }
        with tempfile.TemporaryDirectory() as tmp:
            adapter, path, env = self.snapshot_environment(Path(tmp), declared)
            pending = json.loads(path.read_text())
            pending["policy_initialized"] = False
            adapter._write_workspace_snapshot(path, pending)
            runtime = MemoryRuntime(initialized)
            adapter._refresh_workspace_snapshot(runtime, "/home/user/project", env)
            first = json.loads(path.read_text())
            runtime.files[scope] = '{"approved_subnets":["0.0.0.0/0"]}'
            adapter._refresh_workspace_snapshot(runtime, "/home/user/project", env)
            second = json.loads(path.read_text())

        self.assertTrue(first["policy_initialized"])
        self.assertEqual(first["policy_file_contents"], initialized)
        self.assertEqual(second["policy_file_contents"], initialized)
        self.assertNotEqual(second["file_contents"][scope], initialized[scope])
        self.assertEqual(runtime.calls, [])

    def test_initial_failed_observation_does_not_initialize_policy(self):
        files = {"/home/user/project/job.sh": "echo safe\\n"}
        with tempfile.TemporaryDirectory() as tmp:
            adapter, path, env = self.snapshot_environment(Path(tmp), files)
            pending = json.loads(path.read_text())
            pending["policy_initialized"] = False
            adapter._write_workspace_snapshot(path, pending)
            runtime = MemoryRuntime(files)
            with patch.object(runtime, "snapshot_workspace", side_effect=TimeoutError("observer")):
                with self.assertRaisesRegex(RuntimeError, "action was not executed"):
                    adapter._refresh_workspace_snapshot(runtime, "/home/user/project", env)
            snapshot = json.loads(path.read_text())

        self.assertFalse(snapshot["policy_initialized"])
        self.assertEqual(snapshot["snapshot_status"], "unavailable")
        self.assertEqual(snapshot["file_contents"], {})
        self.assertEqual(runtime.calls, [])

    def test_silently_omitted_known_file_cannot_be_published_as_current(self):
        files = {"/home/user/project/job.sh": "echo safe\\n"}
        with tempfile.TemporaryDirectory() as tmp:
            adapter, path, env = self.snapshot_environment(Path(tmp), files)
            runtime = MemoryRuntime({})
            with self.assertRaisesRegex(RuntimeError, "action was not executed"):
                adapter._refresh_workspace_snapshot(runtime, "/home/user/project", env)
            self.assertEqual(json.loads(path.read_text())["snapshot_status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
