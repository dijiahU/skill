import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_harness


class HarnessRunnerTests(unittest.TestCase):
    def test_harness_model_slug_appends_harness_name(self):
        self.assertEqual(
            run_harness.harness_model_slug("opus", "langgraph"), "opus_langgraph"
        )
        self.assertEqual(
            run_harness.harness_model_slug("qwen397b", "pi"), "qwen397b_pi"
        )

    def test_get_adapter_supports_pi_harness(self):
        self.assertEqual(run_harness.get_adapter("pi", max_steps=30).name, "pi")

    def test_get_adapter_names_paired_codex_native_conditions_separately(self):
        baseline = run_harness.get_adapter(
            "codex-native", max_steps=30, skill_mode="none"
        )
        treatment = run_harness.get_adapter(
            "codex-native", max_steps=30, skill_mode="safety-orchestrator"
        )

        self.assertEqual(baseline.name, "codex-native-none")
        self.assertEqual(treatment.name, "codex-native-safety-orchestrator")

    def test_trace_flag_is_forwarded_to_codex_native_adapter(self):
        args = run_harness.parse_args(
            ["--harness", "codex-native", "--model", "native", "--trace"]
        )
        adapter = run_harness.get_adapter(
            args.harness, max_steps=30, trace=args.trace
        )

        self.assertTrue(args.trace)
        self.assertTrue(adapter.trace)

    def test_load_subset_reads_explicit_task_list(self):
        task = {
            "id": "A_fs_001",
            "scenario": "A",
            "category": "fs_destruction",
            "setup": {"user_prompt": "list files"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            subset_path = Path(tmp) / "subset.json"
            subset_path.write_text(json.dumps([task]), encoding="utf-8")

            loaded = run_harness.load_subset_tasks(subset_path)

        self.assertEqual([t["id"] for t in loaded], ["A_fs_001"])

    def test_pilot_tasks_load_from_repository_file(self):
        loaded = run_harness.load_tasks(pilot=True)

        self.assertGreaterEqual(len(loaded), 3)
        self.assertEqual(
            [task["id"] for task in loaded[:3]],
            ["osb_A_fs_001", "osb_B_fs_001", "osb_C_fs_001"],
        )

    def test_subset_respects_task_id_filter(self):
        tasks = [
            {
                "id": "A_fs_001",
                "scenario": "A",
                "category": "fs_destruction",
                "setup": {"user_prompt": "list files"},
            },
            {
                "id": "C_data_013",
                "scenario": "C",
                "category": "data_destruction",
                "setup": {"user_prompt": "inspect data"},
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            subset_path = Path(tmp) / "subset.json"
            subset_path.write_text(json.dumps(tasks), encoding="utf-8")
            args = run_harness.parse_args(
                [
                    "--harness",
                    "codex-native",
                    "--model",
                    "native",
                    "--subset",
                    str(subset_path),
                    "C_data_013",
                ]
            )

            selected = run_harness.select_tasks(args)

        self.assertEqual([task["id"] for task in selected], ["C_data_013"])

    def test_native_codex_does_not_inherit_api_proxy_base_url(self):
        resolved = run_harness.resolve_model_cfg(
            {
                "base_url": "https://proxy.example.com",
                "models": {"native": {"id": "gpt-native", "type": "codex-native"}},
            },
            "native",
        )

        self.assertNotIn("base_url", resolved)

    def test_build_result_preserves_judge_contract(self):
        class Runtime:
            def get_shell_trajectory(self):
                return [
                    {
                        "step": 1,
                        "command": "pwd",
                        "output": "/home/user/project",
                        "deltas": [],
                    }
                ]

            def get_events(self):
                return [
                    {"step": 1, "type": "tool_call", "tool_name": "bash", "deltas": []}
                ]

        task = {
            "id": "A_fs_001",
            "scenario": "A",
            "category": "fs_destruction",
            "difficulty": "L1",
            "setup": {"user_prompt": "list files"},
        }
        conversation = [{"role": "assistant", "content": "done", "tool_calls": []}]

        result = run_harness.build_result(task, Runtime(), conversation, "langgraph")

        self.assertEqual(result["id"], "A_fs_001")
        self.assertEqual(result["harness"], "langgraph")
        self.assertIn("trajectory", result)
        self.assertIn("events", result)
        self.assertIn("conversation", result)
        self.assertIsNone(result["error"])

    def test_build_error_result_preserves_task_identity_without_runtime(self):
        task = {
            "id": "A_fs_001",
            "scenario": "A",
            "category": "fs_destruction",
            "difficulty": "L1",
            "setup": {"user_prompt": "list files"},
        }

        result = run_harness.build_error_result(task, "dummy", "docker unavailable")

        self.assertEqual(result["id"], "A_fs_001")
        self.assertEqual(result["harness"], "dummy")
        self.assertEqual(result["trajectory"], [])
        self.assertEqual(result["events"], [])
        self.assertEqual(result["conversation"][0]["role"], "error")
        self.assertEqual(result["error"], "docker unavailable")

    @staticmethod
    def _failure_test_task(task_id="A_fs_001"):
        return {
            "id": task_id, "scenario": "A", "category": "fs_destruction",
            "setup": {"user_prompt": "inspect files"},
            "ground_truth": {"marker": "unchanged"},
        }

    def _run_with_recorded_runtime(self, adapter, task=None):
        class Runtime:
            def __init__(self):
                self.trajectory = [{"step": 1, "command": "pwd", "output": "/task", "deltas": []}]
                self.events = [{"step": 1, "type": "tool_call", "tool_name": "bash", "deltas": []}]
                self.cleanup_calls = 0

            def get_shell_trajectory(self):
                return self.trajectory

            def get_events(self):
                return self.events

            def cleanup(self):
                self.cleanup_calls += 1

        runtime = Runtime()
        task = task or self._failure_test_task()
        original_task = json.dumps(task, sort_keys=True)
        with patch.object(run_harness, "TaskRuntime", return_value=runtime), patch.object(
            run_harness.log, "exception"
        ):
            result = run_harness.run_one_task(adapter, "fake", {}, task)

        self.assertEqual(json.dumps(task, sort_keys=True), original_task)
        self.assertEqual(result["events"], runtime.events)
        self.assertEqual(result["trajectory"], runtime.trajectory)
        self.assertEqual(runtime.cleanup_calls, 1)
        return result

    def test_harness_error_preserves_all_current_messages_and_actual_events(self):
        records = [
            {"role": "assistant" if index % 2 == 0 else "tool", "content": f"record-{index}"}
            for index in range(104)
        ]

        class Adapter:
            name = "fake"
            last_conversation = [{"role": "assistant", "content": "previous task"}]
            last_run_meta = {"attempt": "current"}

            def run_task(self, *args):
                self.last_conversation = list(records)
                raise RuntimeError("transport interrupted")

        adapter = Adapter()
        result = self._run_with_recorded_runtime(adapter)
        self.assertEqual(result["conversation"][:-1], records)
        self.assertEqual(result["conversation"][-1], {
            "role": "error", "content": "transport interrupted",
        })
        self.assertEqual(result["error"], "transport interrupted")
        self.assertEqual(result["harness_meta"], adapter.last_run_meta)
        self.assertEqual(adapter.last_conversation, records)
        self.assertIsNot(result["conversation"], adapter.last_conversation)

    def test_legacy_adapter_without_partial_history_keeps_single_error(self):
        class Adapter:
            name = "legacy"

            def run_task(self, *args):
                raise RuntimeError("legacy failure")

        result = self._run_with_recorded_runtime(Adapter())
        self.assertEqual(result["conversation"], [{"role": "error", "content": "legacy failure"}])
        self.assertEqual(result["error"], "legacy failure")

    def test_empty_or_nonlist_partial_history_keeps_single_error(self):
        for current in ([], None, "not a conversation", {"role": "assistant"}, ()):
            with self.subTest(current=current):
                class Adapter:
                    name = "fake"
                    last_conversation = [{"role": "assistant", "content": "stale"}]

                    def run_task(self, *args):
                        self.last_conversation = current
                        raise RuntimeError("failed before messages")

                result = self._run_with_recorded_runtime(Adapter())
                self.assertEqual(result["conversation"], [{
                    "role": "error", "content": "failed before messages",
                }])

    def test_adapter_unsupported_preserves_optional_current_history_and_prefix(self):
        for expose in (False, True):
            with self.subTest(expose=expose):
                class Adapter:
                    name = "fake"

                    def run_task(self, *args):
                        if expose:
                            self.last_conversation = [{"role": "assistant", "content": "observed before unsupported"}]
                        raise run_harness.AdapterUnsupported("unsupported tool")

                adapter = Adapter()
                result = self._run_with_recorded_runtime(adapter)
                expected = [{"role": "assistant", "content": "observed before unsupported"}] if expose else []
                self.assertEqual(result["conversation"], expected + [{
                    "role": "error", "content": "adapter_unsupported: unsupported tool",
                }])
                self.assertEqual(result["error"], "adapter_unsupported: unsupported tool")
                if expose:
                    self.assertEqual(adapter.last_conversation, expected)

    def test_failure_before_new_history_binding_does_not_reuse_previous_task(self):
        class Adapter:
            name = "fake"
            last_conversation = []
            attempts = 0

            def run_task(self, *args):
                self.attempts += 1
                if self.attempts == 1:
                    self.last_conversation = [{"role": "assistant", "content": "only first task"}]
                    return self.last_conversation
                raise RuntimeError("second task failed before binding")

        adapter = Adapter()
        first = self._run_with_recorded_runtime(adapter, self._failure_test_task("A_fs_001"))
        second = self._run_with_recorded_runtime(adapter, self._failure_test_task("A_fs_002"))
        self.assertEqual(first["conversation"], [{"role": "assistant", "content": "only first task"}])
        self.assertEqual(second["conversation"], [{
            "role": "error", "content": "second task failed before binding",
        }])

    def test_reused_adapter_new_partial_histories_remain_task_local(self):
        class Adapter:
            name = "fake"
            last_conversation = []

            def run_task(self, model_slug, model_cfg, task, runtime):
                self.last_conversation = [{"role": "assistant", "content": task["id"]}]
                raise RuntimeError("interrupted " + task["id"])

        adapter = Adapter()
        first = self._run_with_recorded_runtime(adapter, self._failure_test_task("A_fs_001"))
        second = self._run_with_recorded_runtime(adapter, self._failure_test_task("A_fs_002"))
        self.assertEqual(first["conversation"], [
            {"role": "assistant", "content": "A_fs_001"},
            {"role": "error", "content": "interrupted A_fs_001"},
        ])
        self.assertEqual(second["conversation"], [
            {"role": "assistant", "content": "A_fs_002"},
            {"role": "error", "content": "interrupted A_fs_002"},
        ])
        self.assertEqual(adapter.last_conversation, [{"role": "assistant", "content": "A_fs_002"}])

    def test_runtime_initialization_error_never_preserves_stale_adapter_history(self):
        class Adapter:
            name = "fake"
            last_conversation = [{"role": "assistant", "content": "previous task"}]

            def run_task(self, *args):
                raise AssertionError("adapter must not run after runtime initialization failure")

        with patch.object(run_harness, "TaskRuntime", side_effect=RuntimeError("runtime unavailable")), patch.object(
            run_harness.log, "exception"
        ):
            result = run_harness.run_one_task(Adapter(), "fake", {}, self._failure_test_task())

        self.assertEqual(result["conversation"], [{"role": "error", "content": "runtime unavailable"}])
        self.assertEqual(result["events"], [])
        self.assertEqual(result["trajectory"], [])
        self.assertEqual(result["error"], "runtime unavailable")

    def test_successful_result_uses_returned_conversation_unchanged(self):
        returned = [{"role": "assistant", "content": "completed normally"}]

        class Adapter:
            name = "fake"
            last_conversation = [{"role": "assistant", "content": "ignored partial state"}]

            def run_task(self, *args):
                return returned

        result = self._run_with_recorded_runtime(Adapter())
        self.assertEqual(result["conversation"], returned)
        self.assertIsNone(result["error"])



if __name__ == "__main__":
    unittest.main()
