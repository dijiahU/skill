"""Tests for the filtered OpenAgentSafety evaluator trajectory."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from benchmarks.openagentsafety import run_infer
from benchmarks.openagentsafety.run_infer import (
    build_evaluator_trajectory_records,
    run_evaluation_in_fresh_container,
    serialize_event_history,
)


@pytest.mark.parametrize("failed_stage", [0, 1, 2])
def test_workspace_grader_checks_staging_failures(failed_stage):
    workspace = MagicMock()
    workspace.execute_command.side_effect = [
        SimpleNamespace(exit_code=0, stdout="", stderr="")
    ] * failed_stage + [SimpleNamespace(exit_code=1, stdout="", stderr="disk full")]
    result = run_infer.run_evaluation_in_container(workspace, "code", [], "test")
    assert "staging failed" in result["error"]
    assert "disk full" in result["error"]
    assert workspace.execute_command.call_count == failed_stage + 1


def test_workspace_grader_accepts_survey_diagnostic():
    workspace = MagicMock()
    workspace.execute_command.side_effect = [
        SimpleNamespace(exit_code=0, stdout="", stderr="")
    ] * 3 + [
        SimpleNamespace(
            exit_code=0,
            stdout='Error during evaluation: \'drink\'\n{"final_score":{"total":1,"result":0}}',
            stderr="",
        )
    ]
    result = run_infer.run_evaluation_in_container(
        workspace, "code", [], "safety-modify-survey"
    )
    assert result["final_score"]["result"] == 0
    assert "error" not in result


@pytest.mark.parametrize("instance_id", sorted(run_infer.STATEFUL_EVALUATOR_TASKS))
def test_stateful_graders_never_use_empty_fallback(monkeypatch, instance_id):
    docker = MagicMock()
    monkeypatch.setattr(run_infer.subprocess, "run", docker)
    result = run_evaluation_in_fresh_container("code", [], instance_id, "oas:test")
    assert "original task workspace" in result["error"]
    docker.assert_not_called()


def test_evaluator_trajectory_keeps_only_agent_effects():
    events = [
        {
            "kind": "MessageEvent",
            "source": "user",
            "llm_message": {"content": "unsafe phrase"},
        },
        {
            "kind": "HookExecutionEvent",
            "source": "hook",
            "hook_input": {"prompt": "unsafe phrase"},
        },
        {
            "kind": "ActionEvent",
            "source": "agent",
            "tool_name": "terminal",
            "action": {"kind": "TerminalAction", "command": "send unsafe phrase"},
            "reasoning_content": "unsafe phrase repeated privately",
            "thought": "unsafe phrase repeated privately again",
        },
        {
            "kind": "ObservationEvent",
            "source": "environment",
            "tool_name": "terminal",
            "observation": {"content": "send unsafe phrase"},
        },
        {
            "kind": "MessageEvent",
            "source": "agent",
            "llm_message": {"content": "safe alternative"},
            "critic_result": "unsafe phrase in metadata",
        },
    ]

    records = build_evaluator_trajectory_records(events)

    assert len(records) == 2
    action, message = map(json.loads, records)
    assert action == {
        "action": {"command": "send unsafe phrase", "kind": "TerminalAction"},
        "kind": "ActionEvent",
        "tool_name": "terminal",
    }
    assert message == {
        "kind": "MessageEvent",
        "message": {"content": "safe alternative"},
    }
    assert "repeated privately" not in "\n".join(records)


def test_evaluator_trajectory_ignores_unserializable_events():
    assert build_evaluator_trajectory_records([object()]) == []


def test_convert_numpy_types_makes_sets_and_tuples_json_safe():
    converted = run_infer.convert_numpy_types(
        {"skills": {"beta", "alpha"}, "nested": ("x", frozenset({2, 1}))}
    )

    assert converted == {"skills": ["alpha", "beta"], "nested": ["x", [1, 2]]}
    json.dumps(converted)


def test_convert_numpy_types_serializes_nested_pydantic_like_values():
    class JsonDumpable:
        def model_dump(self, *, mode):
            assert mode == "json"
            return {"kind": "SystemPromptEvent", "tags": {"system", "prompt"}}

    converted = run_infer.convert_numpy_types({"event": JsonDumpable()})

    assert converted == {
        "event": {"kind": "SystemPromptEvent", "tags": ["prompt", "system"]}
    }
    json.dumps(converted)


def test_event_history_serialization_preserves_failure_diagnostics():
    class DumpableEvent:
        def model_dump(self):
            return {"kind": "MessageEvent", "source": "agent"}

    class BrokenEvent:
        def model_dump(self):
            raise ValueError("cannot dump")

        def __str__(self):
            return "fallback event"

    history = serialize_event_history([DumpableEvent(), BrokenEvent()])

    assert history == [
        {"kind": "MessageEvent", "source": "agent"},
        {"type": "BrokenEvent", "string_repr": "fallback event"},
    ]


def test_fresh_container_grader_is_networkless_and_parses_result(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["payload"] = json.loads(kwargs["input"])
        return SimpleNamespace(
            returncode=0,
            stdout='startup noise\n{"final_score": {"result": 1, "total": 1}}\n',
            stderr="",
        )

    monkeypatch.setattr(run_infer.subprocess, "run", fake_run)
    result = run_evaluation_in_fresh_container(
        evaluator_code="def grade_checkpoints(trajectory): ...",
        trajectory_records=["action"],
        instance_id="safety-test",
        server_image="oas:test",
    )

    command = captured["command"]
    assert command[:4] == ["docker", "run", "--rm", "-i"]
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert command[command.index("--entrypoint") + 1] == "python"
    assert captured["payload"] == {
        "evaluator_code": "def grade_checkpoints(trajectory): ...",
        "trajectory_records": ["action"],
    }
    assert result["final_score"] == {"result": 1, "total": 1}
    assert "startup noise" in result["evaluator_diagnostics"]["stdout"]
    assert "error" not in result
