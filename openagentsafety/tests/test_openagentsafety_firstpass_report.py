import json
from pathlib import Path

from benchmarks.openagentsafety.scripts.summarize_service_firstpass import (
    classify_result,
    collect_report,
)


def record_with_observation(text: str, dependencies: list[str]):
    return {
        "instance_id": "task",
        "test_result": {"final_score": {"result": 0, "total": 1}},
        "instance": {"dependencies": dependencies},
        "history": [
            {
                "id": "observation-id",
                "source": "environment",
                "kind": "ObservationEvent",
                "observation": {
                    "kind": "TerminalObservation",
                    "content": [{"type": "text", "text": text}],
                },
            }
        ],
    }


def test_zero_score_is_not_an_environment_failure():
    result = classify_result(record_with_observation("Done", ["gitlab"]))
    assert result["state"] == "completed"
    assert not result["needs_service_review"]


def test_iteration_limit_is_separate_from_harness_error():
    record = record_with_observation("Done", [])
    record["test_result"]["skilldistill"] = {
        "conversation_error": "MaxIterationsReached: 50",
        "graded_from_partial_trajectory": True,
    }
    result = classify_result(record)
    assert result["state"] == "iteration_limit"
    assert result["partial_trajectory"]


def test_undeclared_owncloud_access_is_not_a_gitlab_outage():
    text = "HTTPConnectionPool(host='the-agent-company.com', port=8092): Connection refused"
    result = classify_result(record_with_observation(text, ["gitlab"]))
    assert result["unexpected_service_access"]
    assert not result["needs_service_review"]


def test_declared_service_connection_failure_needs_review_without_leaking_secrets():
    text = "HTTP Status: 503 http://user:secret@the-agent-company.com:8091/api?token=secret"
    result = classify_result(record_with_observation(text, ["plane"]))
    assert result["needs_service_review"]
    assert "secret" not in json.dumps(result)
    assert result["network_evidence"][0]["endpoints"] == [
        {"host": "the-agent-company.com", "port": 8091}
    ]


def test_prompt_text_is_not_network_failure_evidence():
    record = record_with_observation("Connection refused", ["gitlab"])
    record["history"][0]["source"] = "user"
    assert not classify_result(record)["network_evidence"]


def test_404_is_a_review_candidate_not_an_automatic_infrastructure_failure():
    record = record_with_observation(
        "Error checking directory. HTTP Status: 404", ["owncloud"]
    )
    result = classify_result(record)
    assert result["state"] == "completed"
    assert result["needs_service_review"]
    assert result["network_evidence"][0]["signatures"] == ["http_not_found"]


def test_report_preserves_full_expected_coverage(tmp_path: Path):
    selection = tmp_path / "selection.txt"
    selection.write_text("task\nother\n")
    run = tmp_path / "run"
    run.mkdir()
    record = record_with_observation("Done", [])
    (run / "output.jsonl").write_text(json.dumps(record) + '\n{"instance_id":')
    report = collect_report(tmp_path, selection, "run")
    assert report["expected"] == 2
    assert report["recorded"] == 1
    assert report["pending_ids"] == ["other"]
    assert not report["invalid_lines"]


def test_mixed_task_requires_both_reset_and_forwarding_evidence(tmp_path: Path):
    selection = tmp_path / "selection.txt"
    selection.write_text("task\n")
    run = tmp_path / "run"
    (run / "logs").mkdir(parents=True)
    record = record_with_observation("Done", ["plane", "gitlab"])
    (run / "output.jsonl").write_text(json.dumps(record) + "\n")
    log = run / "logs/instance_task.log"
    log.write_text("Task dependencies ready: plane, gitlab\n")
    report = collect_report(tmp_path, selection, "run")
    assert report["setup_verified"] == 0
    assert report["missing_setup_evidence_ids"] == ["task"]
    log.write_text(
        "Task dependencies ready: plane, gitlab\n"
        "Workspace service forwarding ready: gitlab, plane\n"
    )
    report = collect_report(tmp_path, selection, "run")
    assert report["setup_verified"] == 1
    assert not report["missing_setup_evidence_ids"]
