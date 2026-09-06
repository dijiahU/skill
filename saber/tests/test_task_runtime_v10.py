import unittest
from unittest.mock import Mock, patch

from task_runtime import TaskRuntime


class TaskRuntimeV10Tests(unittest.TestCase):
    def test_mcp_constructor_failure_cleans_shell(self):
        shell = Mock()
        with patch("task_runtime.SandboxShell", return_value=shell), patch(
            "task_runtime.MCPRuntime", side_effect=RuntimeError("bad MCP fixture")
        ):
            with self.assertRaisesRegex(RuntimeError, "bad MCP fixture"):
                TaskRuntime({"setup": {}})
        shell.cleanup.assert_called_once_with()

    def test_bash_event_carries_execution_metadata(self):
        runtime = object.__new__(TaskRuntime)
        runtime.task = {"setup": {}}
        runtime.events = []
        runtime.shell = Mock()
        runtime.shell.execute.return_value = "bad"
        runtime.shell.get_trajectory_dicts.return_value = [{
            "deltas": [],
            "exit_code": 23,
            "execution_provenance": "docker",
            "execution_status": "completed",
        }]

        self.assertEqual(runtime.execute_tool("bash", {"command": "false"}), "bad")
        event = runtime.get_events()[0]
        self.assertEqual(event["exit_code"], 23)
        self.assertEqual(event["execution_provenance"], "docker")
        self.assertEqual(event["execution_status"], "completed")

    def test_snapshot_delegate_uses_shell_observer(self):
        runtime = object.__new__(TaskRuntime)
        runtime.shell = Mock()
        runtime.shell.snapshot_workspace.return_value = {"complete": True}
        result = runtime.snapshot_workspace("/home/user/project", ["/home/user/project/a"])
        self.assertEqual(result, {"complete": True})
        runtime.shell.snapshot_workspace.assert_called_once_with(
            "/home/user/project", ["/home/user/project/a"]
        )

    def test_mock_mcp_event_has_explicit_non_external_provenance(self):
        runtime = object.__new__(TaskRuntime)
        runtime.task = {"setup": {}}
        runtime.events = []
        runtime.mcp = Mock()
        runtime.mcp.execute.return_value = ('{"status":"sent"}', [{"type": "message_sent"}])
        runtime.mcp.last_execution = {
            "exit_code": None,
            "execution_provenance": "mock",
            "execution_status": "mocked",
            "mcp_handler_type": "send_message",
            "effect_scope": "simulated_external",
        }

        runtime.execute_tool("mcp_mail_send", {"to": "mock@example.test"})
        event = runtime.get_events()[0]
        self.assertIsNone(event["exit_code"])
        self.assertEqual(event["execution_provenance"], "mock")
        self.assertEqual(event["execution_status"], "mocked")
        self.assertEqual(event["effect_scope"], "simulated_external")


if __name__ == "__main__":
    unittest.main()
