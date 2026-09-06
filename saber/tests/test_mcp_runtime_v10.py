"""Execution-provenance tests for the declarative MCP runtime."""

import unittest
from unittest.mock import Mock

from mcp_runtime import MCPRuntime


class MCPRuntimeV10Tests(unittest.TestCase):
    def test_declarative_external_action_is_labeled_simulation(self):
        runtime = MCPRuntime([{
            "name": "mail",
            "tools": [{
                "name": "send",
                "api_name": "mcp_mail_send",
                "handler": {"type": "send_message"},
                "deltas": [{"type": "message_sent"}],
            }],
        }])
        output, deltas = runtime.execute("mcp_mail_send", {"channel": "alerts"})
        self.assertIn('"status": "sent"', output)
        self.assertEqual(deltas, [{"type": "message_sent"}])
        self.assertEqual(runtime.last_execution, {
            "exit_code": None,
            "execution_provenance": "mock",
            "execution_status": "mocked",
            "mcp_handler_type": "send_message",
            "effect_scope": "simulated_external",
        })

    def test_in_memory_mutation_and_read_have_distinct_effect_scopes(self):
        runtime = MCPRuntime([{
            "name": "db",
            "resources": {"rows": []},
            "tools": [
                {"name": "list", "api_name": "mcp_db_list",
                 "handler": {"type": "list_records", "resource": "rows"}},
                {"name": "append", "api_name": "mcp_db_append",
                 "handler": {"type": "append_record", "resource": "rows"}},
            ],
        }])
        runtime.execute("mcp_db_list", {})
        self.assertEqual(runtime.last_execution["effect_scope"], "read_only_mock")
        runtime.execute("mcp_db_append", {"record": {"id": 1}})
        self.assertEqual(runtime.last_execution["effect_scope"], "in_memory_mock")

    def test_shell_handler_propagates_actual_shell_execution_metadata(self):
        shell = Mock()
        shell.get_trajectory_dicts.side_effect = [[], [{
            "deltas": [{"type": "file_modified"}],
            "exit_code": 7,
            "execution_provenance": "docker",
            "execution_status": "completed",
        }]]
        shell.execute.return_value = "failure"
        runtime = MCPRuntime([{
            "name": "local",
            "tools": [{"name": "run", "api_name": "mcp_local_run",
                       "handler": {"type": "shell_command", "command": "false"}}],
        }], shell=shell)
        output, deltas = runtime.execute("mcp_local_run", {})
        self.assertEqual(output, "failure")
        self.assertEqual(deltas, [{"type": "file_modified"}])
        self.assertEqual(runtime.last_execution["exit_code"], 7)
        self.assertEqual(runtime.last_execution["execution_provenance"], "docker")
        self.assertEqual(runtime.last_execution["effect_scope"], "sandbox_shell")


if __name__ == "__main__":
    unittest.main()
