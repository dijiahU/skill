from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SABER_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = Path("/2024233123/skills/bin/run_saber_parallel_judge.py")
sys.path.insert(0, str(SABER_ROOT))
spec = importlib.util.spec_from_file_location("judge_runner_v10_under_test", RUNNER_PATH)
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


def pairs(count):
    return [
        (
            {"id": f"T_{i}", "scenario": "A", "category": "test"},
            {"id": f"T_{i}", "events": [], "conversation": []},
        )
        for i in range(count)
    ]


class ResumeContractTests(unittest.TestCase):
    def test_usable_requires_v10_protocol_schema_model_and_source_hash(self):
        source = {"id": "T", "events": [], "conversation": []}
        existing = {
            "_judge_model": runner.JUDGE_MODEL,
            "_judge_protocol": runner.PROTOCOL_VERSION,
            "_schema_version": runner.OUTPUT_SCHEMA_VERSION,
            "_source_result_sha256": runner._source_fingerprint(source),
            "judge_status": "usable",
            "judge_err": None,
            "harmful": False,
            "termination": "Safe Completion",
        }
        self.assertTrue(runner._is_usable(existing, source))
        for key in (
            "_judge_model", "_judge_protocol", "_schema_version",
            "_source_result_sha256", "judge_status",
        ):
            broken = dict(existing)
            broken[key] = "wrong"
            self.assertFalse(runner._is_usable(broken, source), key)
        broken = dict(existing, harmful=None)
        self.assertFalse(runner._is_usable(broken, source))

    def test_source_errors_are_excluded_not_made_safe(self):
        task = {"id": "T", "scenario": "A", "category": "test"}
        source = {"id": "T", "error": {"type": "upstream_turn_error"}}
        self.assertEqual(runner._pending("model", [(task, source)]), [])


class ControllerTests(unittest.TestCase):
    def test_transport_failure_pauses_globally_before_later_batch_and_resumes_pending(self):
        source_pairs = pairs(5)
        completed = set()
        calls, control_events = [], []
        first_transport = {"value": True}

        def pending(_model, all_pairs):
            return [pair for pair in all_pairs if pair[0]["id"] not in completed]

        def judge_one(_model, task, _result):
            task_id = task["id"]
            calls.append(task_id)
            if task_id == "T_0" and first_transport["value"]:
                first_transport["value"] = False
                return runner.JudgeOutcome(
                    task_id, "failed", "transport", "connection down"
                )
            completed.add(task_id)
            return runner.JudgeOutcome(task_id, "usable")

        def probe():
            control_events.append(("probe", tuple(calls)))
            self.assertNotIn("T_2", calls)
            self.assertNotIn("T_3", calls)
            self.assertNotIn("T_4", calls)

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(runner, "_pairs", return_value=source_pairs),                  mock.patch.object(runner, "_pending", side_effect=pending),                  mock.patch.object(runner, "_judge_one", side_effect=judge_one),                  mock.patch.object(runner, "_write_summary"),                  mock.patch.object(runner.judge, "JUDGED_DIR", Path(tmp)):
                controller = runner.JudgeController(
                    workers=2, batch_size=2, max_schema_attempts=2,
                    max_transport_pauses=2, pause_seconds=0,
                    probe_fn=probe, sleep_fn=lambda _seconds: None,
                )
                state = controller.run_model("model")
        self.assertEqual(state.status, "complete")
        self.assertEqual(state.transport_pauses, 1)
        self.assertEqual(len(control_events), 1)
        self.assertEqual(completed, {f"T_{i}" for i in range(5)})
        self.assertEqual(calls.count("T_0"), 2)

    def test_invalid_schema_is_bounded_and_never_saved_as_usable(self):
        source_pairs = pairs(1)
        attempts = {"count": 0}

        def judge_one(_model, task, _result):
            attempts["count"] += 1
            return runner.JudgeOutcome(
                task["id"], "failed", "schema", "invalid JSON"
            )

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(runner, "_pairs", return_value=source_pairs),                  mock.patch.object(runner, "_judge_one", side_effect=judge_one),                  mock.patch.object(runner, "_write_summary"),                  mock.patch.object(runner.judge, "JUDGED_DIR", Path(tmp)),                  mock.patch.object(runner, "_pending", return_value=source_pairs):
                controller = runner.JudgeController(
                    workers=1, batch_size=1, max_schema_attempts=2,
                    pause_seconds=0, sleep_fn=lambda _seconds: None,
                )
                state = controller.run_model("model")
        self.assertEqual(attempts["count"], 2)
        self.assertEqual(state.status, "complete_with_exclusions")
        self.assertEqual(state.pending, 1)
        self.assertEqual(state.exclusions[0]["failure_class"], "retryable_schema")

    def test_failed_recovery_probe_remains_paused_and_retries_before_resume(self):
        source_pairs = pairs(1)
        completed = set()
        first = {"value": True}
        probes = {"count": 0}

        def pending(_model, all_pairs):
            return [pair for pair in all_pairs if pair[0]["id"] not in completed]

        def judge_one(_model, task, _result):
            if first["value"]:
                first["value"] = False
                return runner.JudgeOutcome(
                    task["id"], "failed", "transport", "disconnect"
                )
            completed.add(task["id"])
            return runner.JudgeOutcome(task["id"], "usable")

        def probe():
            probes["count"] += 1
            if probes["count"] == 1:
                raise runner.JudgeTransportError("still down")

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(runner, "_pairs", return_value=source_pairs),                  mock.patch.object(runner, "_pending", side_effect=pending),                  mock.patch.object(runner, "_judge_one", side_effect=judge_one),                  mock.patch.object(runner, "_write_summary"),                  mock.patch.object(runner.judge, "JUDGED_DIR", Path(tmp)):
                state = runner.JudgeController(
                    workers=1, batch_size=1, max_transport_pauses=3,
                    pause_seconds=0, probe_fn=probe,
                    sleep_fn=lambda _seconds: None,
                ).run_model("model")
        self.assertEqual(state.status, "complete")
        self.assertEqual(probes["count"], 2)
        self.assertEqual(state.transport_pauses, 2)


if __name__ == "__main__":
    unittest.main()
