"""No Docker, network, or model: replay attempted calls through a fake server."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harness_adapters.codex_native_adapter import (
    CodexNativeHarnessAdapter,
    SafetyHookResult,
    SABER_BASH_TOOL,
    SABER_SKILL_READ_TOOL,
    _ToolCallBudget,
    AppServerProtocolError,
)


class BudgetRuntime:
    def __init__(self):
        self.calls = []
        self.observations = []

    def get_tools(self, provider):
        return [{"name": "bash", "parameters": {"type": "object"}}]

    def snapshot_workspace(self, cwd, paths):
        self.observations.append((cwd, list(paths)))
        return {"complete": True, "file_contents": {}}

    def execute_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if arguments.get("command") == "runtime-error":
            raise RuntimeError("fixture runtime failed")
        return "observed"


class BudgetServer:
    def __init__(self, calls, *, protocol_failure=False, interrupt_failure=False, empty_final=False):
        self.empty_final = empty_final
        self.final_sent = False
        self.calls = list(calls)
        self.messages = []
        self.read_count = 0
        self.closed = False
        self.interruptions = []
        self.protocol_failure = protocol_failure
        self.interrupt_failure = interrupt_failure

    def request(self, method, params, deadline):
        if method == "skills/list":
            return {"data": [{"skills": [{"name": "safety-router-skill"}]}]}
        if method == "thread/start":
            return {"thread": {"id": "thread-budget"}}
        if method == "turn/start":
            return {"turn": {"id": "turn-budget"}}
        return {}

    def request_start(self, method, params):
        self.interruptions.append((method, params))
        if self.interrupt_failure:
            raise RuntimeError("fixture interrupt was not acknowledged")
        return 99

    def read(self, deadline):
        self.read_count += 1
        if self.calls:
            tool, arguments = self.calls.pop(0)
            return {"id": self.read_count, "method": "item/tool/call", "params": {
                "tool": tool, "arguments": arguments, "callId": str(self.read_count),
            }}
        if self.protocol_failure:
            raise TimeoutError("fixture transport failed")
        if not self.empty_final and not self.final_sent:
            self.final_sent = True
            return {"method": "item/completed", "params": {"item": {
                "type": "agentMessage", "phase": "final_answer", "text": "Inspection finished.",
            }}}
        return {"method": "turn/completed", "params": {"turn": {"status": "completed"}}}

    def send(self, payload):
        self.messages.append(payload)

    def close(self):
        self.closed = True


class CodexCallBudgetTests(unittest.TestCase):
    @staticmethod
    def bash(command):
        return SABER_BASH_TOOL, {"command": command}

    @staticmethod
    def support():
        return SABER_SKILL_READ_TOOL, {"path": "references/archetypes/review.md"}

    def run_case(self, calls, *, max_steps=30, protocol_failure=False,
                 interrupt_failure=False, adapter=None, expect_error=False, empty_final=False):
        adapter = adapter or CodexNativeHarnessAdapter(skill_mode="safety-orchestrator", max_steps=max_steps)
        server = BudgetServer(calls, protocol_failure=protocol_failure, interrupt_failure=interrupt_failure, empty_final=empty_final)
        runtime = BudgetRuntime()
        hook_events = []

        def hook(task_id, event, env):
            hook_events.append(dict(event))
            command = (event.get("tool_input") or {}).get("command", "")
            blocked = (event["hook_event_name"] == "PreToolUse" and command.startswith("denied"))
            blocked |= (event["hook_event_name"] == "PostToolUse" and command.startswith("post-blocked"))
            return SafetyHookResult(event["hook_event_name"], blocked, "fixture safety block" if blocked else "", "", None, 2 if blocked else 0)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(adapter, "_prepare_environment", return_value=({}, root, root, False)), \
                    patch.object(adapter, "_read_skill_file", return_value="# Safety reference"), \
                    patch.object(adapter, "_run_skill_health", return_value="Health preflight complete"), \
                    patch.object(adapter, "_invoke_safety_hook", side_effect=hook), \
                    patch("harness_adapters.codex_native_adapter.AppServerProcess", return_value=server):
                if expect_error:
                    with self.assertRaises(AppServerProtocolError if empty_final else TimeoutError):
                        adapter.run_task("fake", {"id": "fake-model"}, {"id": "budget-fixture", "setup": {
                            "cwd": "/home/user/project", "user_prompt": "Inspect the workspace.",
                        }}, runtime)
                    conversation = adapter.last_conversation
                else:
                    conversation = adapter.run_task("fake", {"id": "fake-model"}, {"id": "budget-fixture", "setup": {
                        "cwd": "/home/user/project", "user_prompt": "Inspect the workspace.",
                    }}, runtime)
        self.assertTrue(server.closed)
        return adapter, server, runtime, conversation, hook_events

    def test_three_host_blocks_stop_a_42_request_loop_without_runtime_execution(self):
        adapter, server, runtime, conversation, hooks = self.run_case([self.bash("denied-read")] * 42)
        self.assertEqual(server.read_count, 3)
        self.assertEqual(runtime.calls, [])
        self.assertEqual(adapter.last_run_meta["tool_calls"], 0)
        self.assertEqual(adapter.last_run_meta["task_tool_attempts"], 3)
        self.assertEqual(adapter.last_run_meta["termination_reason"], "consecutive_safety_blocks")
        self.assertEqual(len(server.interruptions), 1)
        self.assertEqual([event["hook_event_name"] for event in hooks].count("Stop"), 1)
        self.assertEqual(len(runtime.observations), 4)
        self.assertEqual(conversation[-1]["source"], "harness")
        self.assertIn("not a claim of task completion", conversation[-1]["content"])
        self.assertEqual(sum(row.get("role") == "tool" for row in conversation), 3)

    def test_support_reads_and_changed_arguments_do_not_reset_host_denials(self):
        calls = [self.bash("denied-one"), self.support(), self.bash("denied-two"), self.support(), self.bash("denied-three"), self.bash("must-not-run")]
        adapter, server, runtime, conversation, hooks = self.run_case(calls)
        self.assertEqual(server.read_count, 5)
        self.assertEqual(runtime.calls, [])
        self.assertEqual(adapter.last_run_meta["task_tool_attempts"], 3)
        self.assertEqual(adapter.last_run_meta["support_tool_attempts"], 2)
        self.assertEqual(adapter.last_run_meta["consecutive_safety_blocks"], 3)

    def test_real_progress_resets_consecutive_blocks_without_weakening_hooks(self):
        calls = [self.bash("denied-one"), self.bash("denied-two"), self.bash("safe-inspection"), self.bash("denied-three"), self.bash("denied-four")]
        adapter, server, runtime, conversation, hooks = self.run_case(calls)
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(adapter.last_run_meta["tool_calls"], 1)
        self.assertEqual(adapter.last_run_meta["consecutive_safety_blocks"], 2)
        self.assertEqual(server.interruptions, [])
        self.assertNotIn("host_budget_terminated", adapter.last_run_meta)

    def test_unknown_and_failed_requests_spend_attempt_budget(self):
        for call in (("unknown-tool", {}), self.bash("runtime-error")):
            with self.subTest(call=call):
                adapter, server, runtime, conversation, hooks = self.run_case([call] * 42, max_steps=2)
                self.assertEqual(server.read_count, 3)
                self.assertEqual(adapter.last_run_meta["task_tool_attempts"], 2)
                self.assertEqual(adapter.last_run_meta["budget_rejected_calls"], 1)
                self.assertEqual(adapter.last_run_meta["termination_reason"], "task_attempt_limit")
                self.assertLessEqual(len(runtime.calls), 2)

    def test_support_only_loop_is_finite_and_does_not_spend_task_steps(self):
        adapter, server, runtime, conversation, hooks = self.run_case([self.support()] * 42, max_steps=1)
        self.assertEqual(server.read_count, 17)
        self.assertEqual(adapter.last_run_meta["support_tool_attempts"], 16)
        self.assertEqual(adapter.last_run_meta["task_tool_attempts"], 0)
        self.assertEqual(adapter.last_run_meta["tool_calls"], 0)
        self.assertEqual(adapter.last_run_meta["termination_reason"], "support_attempt_limit")
        self.assertEqual(runtime.calls, [])

    def test_posttool_blocks_still_count_real_runtime_calls(self):
        adapter, server, runtime, conversation, hooks = self.run_case([self.bash("post-blocked")] * 42)
        self.assertEqual(len(runtime.calls), 3)
        self.assertEqual(adapter.last_run_meta["tool_calls"], 3)
        self.assertEqual(adapter.last_run_meta["termination_reason"], "consecutive_safety_blocks")

    def test_unacknowledged_interrupt_still_closes_the_owned_server(self):
        adapter, server, runtime, conversation, hooks = self.run_case([self.bash("denied")] * 42, interrupt_failure=True)
        self.assertEqual(server.read_count, 3)
        self.assertTrue(server.closed)
        self.assertEqual(adapter.last_run_meta["interrupt_request_error"], "RuntimeError")
        self.assertEqual(conversation[-1]["source"], "harness")

    def test_last_conversation_survives_failure_and_resets_on_next_task(self):
        adapter, server, runtime, conversation, hooks = self.run_case([self.bash("safe-inspection")], protocol_failure=True, expect_error=True)
        self.assertIs(adapter.last_conversation, conversation)
        self.assertEqual(sum(row.get("role") == "tool" for row in conversation), 1)
        old = conversation
        adapter, server, runtime, conversation, hooks = self.run_case([], adapter=adapter)
        self.assertIsNot(old, adapter.last_conversation)
        self.assertEqual(len(conversation), 1)
        self.assertEqual(conversation[0]["source"], "model")
        self.assertEqual(adapter.last_run_meta["task_tool_attempts"], 0)
        self.assertEqual(sum(row.get("role") == "tool" for row in old), 1)

    def test_early_environment_failure_does_not_reuse_old_conversation(self):
        adapter = CodexNativeHarnessAdapter()
        old = [{"role": "assistant", "content": "prior-task"}]
        adapter.last_conversation = old
        with patch.object(adapter, "_prepare_environment", side_effect=RuntimeError("fixture environment failed")):
            with self.assertRaises(RuntimeError):
                adapter.run_task("fake", {"id": "fake-model"}, {"id": "next", "setup": {}}, BudgetRuntime())
        self.assertIsNot(adapter.last_conversation, old)
        self.assertEqual(adapter.last_conversation, [])

    def test_exact_budget_does_not_interrupt_a_completed_response(self):
        adapter, server, runtime, conversation, hooks = self.run_case([self.bash("safe-inspection")], max_steps=1)
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(server.interruptions, [])
        self.assertEqual(adapter.last_run_meta["turn_status"], "completed")

    def test_empty_final_is_technical_failure_with_partial_history_preserved(self):
        adapter, server, runtime, conversation, _ = self.run_case(
            [self.bash("safe-inspection")], empty_final=True, expect_error=True)
        self.assertEqual(adapter.last_run_meta["technical_failure_stage"], "empty_model_final")
        self.assertFalse(adapter.last_run_meta["model_final_present"])
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(sum(row.get("role") == "tool" for row in conversation), 1)

    def test_invalid_json_is_not_executed_and_valid_retry_can_progress(self):
        malformed = '{"command":"echo 中文",}'
        for invalid in (malformed, '[]', 'null', None):
            with self.subTest(invalid=invalid):
                adapter, server, runtime, conversation, hooks = self.run_case(
                    [(SABER_BASH_TOOL, invalid), self.bash("safe-inspection")])
                self.assertEqual(runtime.calls, [("bash", {"command": "safe-inspection"})])
                self.assertEqual(adapter.last_run_meta["task_tool_attempts"], 2)
                self.assertEqual(adapter.last_run_meta["tool_argument_errors"][0]["raw_arguments"], invalid)
                self.assertFalse(server.messages[1]["result"]["success"])
                self.assertEqual(sum(e["hook_event_name"] == "PreToolUse" for e in hooks), 1)

    def test_safe_recovery_does_not_erase_total_risk_budget(self):
        budget = _ToolCallBudget(30, 60)
        for _ in range(5):
            budget.observe(support=False, blocked=True, progress=False, decision_kind="high_risk_block")
            budget.observe(support=False, blocked=False, progress=True, decision_kind="low_risk_recovery_allow")
            self.assertEqual(budget.reason, "")
        self.assertEqual(budget.successful_recovery_actions, 5)
        budget.observe(support=False, blocked=True, progress=False, decision_kind="high_risk_block")
        self.assertEqual(budget.reason, "total_high_risk_block_limit")
        self.assertFalse(budget.admit(False))

    def test_delivered_filtered_view_does_not_count_as_dangerous_retry(self):
        budget = _ToolCallBudget(30, 60)
        for _ in range(10):
            budget.observe(support=False, blocked=False, progress=True, decision_kind="posttool_isolation")
        self.assertEqual(budget.total_high_risk_blocks, 0)
        self.assertEqual(budget.reason, "")
        budget.observe(support=False, blocked=True, progress=False, decision_kind="posttool_isolation")
        self.assertEqual(budget.total_high_risk_blocks, 1, "an actual block cannot be bypassed by metadata")

    def test_runtime_failure_loop_stops_without_increasing_total_step_budget(self):
        def execute(runtime, name, arguments):
            runtime.calls.append((name, arguments))
            if not hasattr(runtime, "events"):
                runtime.events = []
            runtime.events.append({"exit_code": 1, "execution_provenance": "docker", "deltas": [], "output": "same failure"})
            return "same failure"
        with patch.object(BudgetRuntime, "execute_tool", execute):
            adapter, server, runtime, conversation, hooks = self.run_case(
                [self.bash("git status --short")] * 10)
        self.assertEqual(len(runtime.calls), 4)
        self.assertEqual(adapter.last_run_meta["termination_reason"], "repeated_no_progress")
        self.assertEqual(adapter.last_run_meta["task_tool_attempt_limit"], 30)
        self.assertEqual(conversation[-1]["source"], "harness")
        self.assertEqual(len(server.interruptions), 1)
        self.assertTrue(adapter.last_run_meta["no_progress_observations"][-1]["terminal"])

    def test_budget_terminal_reason_cannot_be_reset_by_a_later_support_read(self):
        budget = _ToolCallBudget(30, 60)
        for _ in range(3):
            self.assertTrue(budget.admit(False))
            budget.observe(support=False, blocked=True, progress=False)
        self.assertFalse(budget.admit(True))
        budget.observe(support=True, blocked=False, progress=True)
        self.assertEqual(budget.reason, "consecutive_safety_blocks")


if __name__ == "__main__":
    unittest.main()
