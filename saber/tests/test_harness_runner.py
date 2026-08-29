import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
