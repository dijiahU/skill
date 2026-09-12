"""Offline tests for configuration isolation, bounded runs and secret handling."""

import json
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from api_benchmarks import bench


class WorkflowTests(unittest.TestCase):
    def test_terminal_parallelism_and_attempts_are_explicit_and_positive(self):
        env = dict(self.env, TERMINALBENCH_CONCURRENCY="4", TERMINALBENCH_ATTEMPTS="2")
        _, command = bench.commands(
            "terminalbench", "none", env, 4, None, Path("temp.json")
        )
        self.assertEqual(command[command.index("--n-concurrent") + 1], "4")
        self.assertEqual(command[command.index("--n-attempts") + 1], "2")
        for value in ("0", "-1", "invalid"):
            with self.assertRaises(ValueError):
                bench.positive_setting(
                    {"TERMINALBENCH_CONCURRENCY": value}, "TERMINALBENCH_CONCURRENCY", 1
                )

    def test_oas_rejects_partial_or_missing_scores_but_accepts_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output.jsonl"
            valid = {
                "instance_id": "test",
                "error": None,
                "test_result": {"final_score": {"total": 1, "result": 0}},
            }
            output.write_text(json.dumps(valid) + "\n")
            bench.check_oas_results([output])
            valid["test_result"]["skilldistill"] = {
                "graded_from_partial_trajectory": True
            }
            output.write_text(json.dumps(valid) + "\n")
            with self.assertRaisesRegex(ValueError, "failed or lacks"):
                bench.check_oas_results([output])
            output.write_text("")
            with self.assertRaisesRegex(ValueError, "no task results"):
                bench.check_oas_results([output])

    def setUp(self) -> None:
        self.env = {
            "BENCH_MODEL": "org/chat-model",
            "BENCH_BASE_URL": "https://example.org/v1",
            "BENCH_API_KEY": "agent-secret",
            "RESPONSES_MODEL": "org/responses-model",
            "RESPONSES_BASE_URL": "https://example.org/v1",
            "RESPONSES_API_KEY": "responses-secret",
            "JUDGE_MODEL": "judge",
            "JUDGE_BASE_URL": "https://judge.example.org/v1",
            "JUDGE_API_KEY": "judge-secret",
            "NPC_MODEL": "npc",
            "NPC_BASE_URL": "https://npc.example.org/v1",
            "NPC_API_KEY": "npc-secret",
        }

    def test_all_command_lines_and_plans_exclude_keys(self) -> None:
        for name in bench.BENCHMARKS:
            cfg = bench.config_data(name, self.env, False)
            for mode in bench.MODES:
                _, cmd = bench.commands(
                    name, mode, self.env, 1, None, Path("temp.json")
                )
                serialized = json.dumps([cfg, cmd])
                for secret in (
                    "agent-secret",
                    "responses-secret",
                    "judge-secret",
                    "npc-secret",
                ):
                    self.assertNotIn(secret, serialized)
                self.assertIn(
                    mode if name != "terminalbench" else f"skill_mode={mode}", cmd
                )
                self.assertIn("1", cmd)

    def test_saber_uses_env_credentials_and_no_login(self) -> None:
        model = bench.config_data("saber", self.env, True)["models"]["api-smoke-001"]
        self.assertNotIn("key", model)
        self.assertEqual(model["key_env"], "RESPONSES_API_KEY")
        self.assertFalse(model["copy_codex_auth"])
        self.assertFalse(model["preload_skill_references"])

    def test_oas_provider_prefix_preserves_model_namespace(self) -> None:
        self.assertEqual(
            bench.config_data("oas", self.env, True)["model"], "openai/org/chat-model"
        )

    def test_saber_legacy_judge_gets_single_version_prefix(self) -> None:
        for url, kind, expected in (
            ("https://example.org/v1", "openai", "https://example.org"),
            ("https://example.org/api/v1", "openai", "https://example.org/api"),
            ("https://example.org", "openai", "https://example.org"),
            ("https://example.org/v1", "anthropic", "https://example.org/v1"),
        ):
            with self.subTest(url=url, kind=kind):
                self.assertEqual(
                    bench.saber_judge_base_url({"base_url": url, "type": kind}),
                    expected,
                )

    def test_incomplete_credentials_fail(self) -> None:
        for role in ("agent", "responses", "judge", "npc"):
            with self.assertRaises(ValueError):
                bench.role_config({}, role, True)

    def test_responses_probe_stops_at_completed_event(self) -> None:
        stream = io.BytesIO(
            b'data: {"type":"response.completed","response":{"status":"completed"}}\n\n'
            b"data: invalid trailing gateway data\n"
        )
        bench.check_responses_stream(stream)

    def test_responses_probe_rejects_incomplete_and_false_completion(self) -> None:
        for payload in (
            b'data: {"type":"response.created"}\n\n',
            b'data: {"type":"response.failed"}\n\n',
            b'data: {"type":"response.completed","response":{"status":"incomplete"}}\n\n',
            b'data: {"type":"response.output_text.delta","delta":"response.completed"}\n\n',
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                bench.check_responses_stream(io.BytesIO(payload))

    def test_provider_key_alias_uses_rotated_canonical_key(self) -> None:
        env = dict(
            self.env,
            RESPONSES_API_KEY_ENV="APINEBULA_API_KEY",
            APINEBULA_API_KEY="new-key",
        )
        self.assertEqual(bench.role_config(env, "responses", True)["key"], "new-key")
        del env["APINEBULA_API_KEY"]
        with self.assertRaisesRegex(ValueError, "APINEBULA_API_KEY"):
            bench.role_config(env, "responses", True)

    def test_invalid_endpoint_rejected(self) -> None:
        for url in (
            "https://key@example.org/v1",
            "https://example.org?key=secret",
            "https://example.org/v1/responses",
            "file:///tmp/key",
        ):
            with self.assertRaises(ValueError):
                bench.validate_url(url)

    def test_launch_resolves_provider_alias_for_each_harness(self) -> None:
        env = dict(
            self.env,
            RESPONSES_API_KEY_ENV="FOREIGN_KEY",
            NPC_API_KEY_ENV="DOMESTIC_KEY",
            FOREIGN_KEY="rotated-foreign-key",
            DOMESTIC_KEY="rotated-domestic-key",
        )
        for name, variable, expected in (
            ("saber", "RESPONSES_API_KEY", "rotated-foreign-key"),
            ("terminalbench", "OPENAI_API_KEY", "rotated-foreign-key"),
            ("oas", "NPC_API_KEY", "rotated-domestic-key"),
        ):
            with self.subTest(benchmark=name), tempfile.TemporaryDirectory() as temp:
                with (
                    patch.object(bench, "REPORTS", Path(temp)),
                    patch.object(bench.subprocess, "run") as run,
                    patch.object(bench, "check_harbor_results"),
                    patch.object(bench, "check_oas_results"),
                ):
                    bench.launch(name, ("none",), env, 1, None)
                    self.assertEqual(run.call_args.kwargs["env"][variable], expected)

    def test_harbor_environment_failure_is_not_zero_reward_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp) / "result.json"
            result.write_text(
                json.dumps({"stats": {"n_completed_trials": 1, "n_errored_trials": 1}})
            )
            with self.assertRaisesRegex(ValueError, "failed or unfinished"):
                bench.check_harbor_results({result})
            result.write_text(
                json.dumps({"stats": {"n_completed_trials": 1, "n_errored_trials": 0}})
            )
            bench.check_harbor_results({result})
            with self.assertRaisesRegex(ValueError, "no new job result"):
                bench.check_harbor_results(set())

    def test_dotenv_is_literal_and_shell_wins(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / ".env"
            path.write_text(
                "BENCH_MODEL='$(touch should-never-exist)'\nBENCH_API_KEY=file-value\n"
            )
            with patch.dict(os.environ, {"BENCH_API_KEY": "shell-value"}, clear=True):
                env = bench.environment(path)
            self.assertEqual(env["BENCH_MODEL"], "$(touch should-never-exist)")
            self.assertEqual(env["BENCH_API_KEY"], "shell-value")

    def test_private_file_and_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "model.json"
            bench.private_json(path, {"api_key": "secret"})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                bench.private_json(path, {})

    def test_limits_and_run_id_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            bench.commands("oas", "none", self.env, 0, None, Path("temp.json"))
        with self.assertRaises(ValueError):
            bench.run_id({"BENCH_RUN_ID": "../../other"})

    def test_run_config_change_cannot_reuse_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch.object(bench, "REPORTS", Path(temporary)),
                patch.object(bench.subprocess, "run") as run,
            ):
                bench.launch("saber", ("none",), self.env, 1, None)
                self.assertEqual(run.call_count, 1)
                changed = dict(self.env, RESPONSES_MODEL="different-model")
                with self.assertRaisesRegex(ValueError, "configuration changed"):
                    bench.launch("saber", ("safety-orchestrator",), changed, 1, None)
                self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
