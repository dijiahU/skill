"""Read-only technical audit before judging a complete SABER treatment run.

``passed`` means the experiment record is technically complete, not that the
agent was safe or finished the user's task. Empty trajectories, intercepted
answers and correctly attributed harness stops remain eligible for judging.
Reports contain identifiers and fixed diagnostic codes, never task contents.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any


EXPECTED_TASK_COUNT = 716
STOP_REPLACEMENT = "Final response blocked by Safety Orchestrator:"
CONTROLLED_REASONS = {
    "consecutive_safety_blocks", "task_attempt_limit", "support_attempt_limit",
    "runtime_step_limit",
}
TASK_ID = re.compile(r"[ABC]_[a-z][a-z0-9_]*_[0-9]{3,}\Z")


def _safe_id(value: Any) -> str:
    return value if isinstance(value, str) and TASK_ID.fullmatch(value) else "<invalid-id>"


def _integer(value: Any) -> bool:
    return type(value) is int and value >= 0


def _load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None, "unreadable_or_invalid_json"
    return (value, None) if isinstance(value, dict) else (None, "json_root_not_object")


def _conversation_valid(entries: list[Any]) -> bool:
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("role"), str) or entry.get("role") not in {
            "assistant", "tool", "user", "system", "developer",
        }:
            return False
        if "content" in entry and not isinstance(entry["content"], str):
            return False
        if entry.get("phase") is not None and not isinstance(entry["phase"], str):
            return False
        calls = entry.get("tool_calls", [])
        if not isinstance(calls, list) or any(
            not isinstance(call, dict)
            or not isinstance(call.get("id"), str)
            or not isinstance(call.get("name"), str)
            or not isinstance(call.get("input"), dict)
            for call in calls
        ):
            return False
        if entry["role"] == "tool" and not (
            isinstance(entry.get("tool_name"), str)
            and isinstance(entry.get("tool_input"), dict)
            and isinstance(entry.get("output"), str)
        ):
            return False
    return True


def _runtime_entries_valid(entries: list[Any], *, events: bool) -> bool:
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or type(entry.get("step")) is not int or entry["step"] != index:
            return False
        if not isinstance(entry.get("output"), str) or not isinstance(entry.get("deltas"), list):
            return False
        if any(not isinstance(delta, dict) for delta in entry["deltas"]):
            return False
        if events:
            if not (
                entry.get("type") == "tool_call"
                and isinstance(entry.get("tool_name"), str)
                and isinstance(entry.get("input"), dict)
            ):
                return False
            if entry["tool_name"] == "bash" and not isinstance(entry.get("command"), str):
                return False
        elif not isinstance(entry.get("command"), str):
            return False
    return True


def _validate_record(data: dict[str, Any], task: dict[str, Any], max_steps: int) -> tuple[list[str], list[str], dict[str, Any]]:
    issues: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    for field in ("id", "scenario", "category", "difficulty"):
        if field not in data or data[field] != task.get(field):
            issues.append("task_" + field + "_mismatch")
    setup = task.get("setup")
    if not isinstance(setup, dict) or not isinstance(setup.get("user_prompt"), str):
        issues.append("source_task_prompt_invalid")
    elif data.get("prompt") != setup["user_prompt"]:
        issues.append("task_prompt_mismatch")
    if "error" not in data or data["error"] not in (None, ""):
        issues.append("result_error_present_or_missing_field")
    if data.get("harness") != "codex-native-safety-orchestrator":
        issues.append("unexpected_harness")

    collections: dict[str, list[Any]] = {}
    for name in ("conversation", "events", "trajectory"):
        value = data.get(name)
        if not isinstance(value, list):
            issues.append(name + "_not_list")
            value = []
        collections[name] = value
    conversation, events, trajectory = (collections[name] for name in ("conversation", "events", "trajectory"))
    if not _conversation_valid(conversation):
        issues.append("conversation_entry_invalid")
    if not _runtime_entries_valid(events, events=True):
        issues.append("event_entry_invalid")
    if not _runtime_entries_valid(trajectory, events=False):
        issues.append("trajectory_entry_invalid")
    # MCP shell handlers can legitimately add shell trajectory entries too;
    # trajectory length must not be equated to the number of bash events.
    if not events:
        warnings.append("empty_events_requires_judgment")
    assistants = [entry for entry in conversation if isinstance(entry, dict) and entry.get("role") == "assistant"]
    answers = [entry for entry in assistants if isinstance(entry.get("content"), str) and entry["content"].strip()]
    if not answers:
        issues.append("missing_assistant_response")
    stop_replaced = any(entry["content"].startswith(STOP_REPLACEMENT) for entry in answers)
    if stop_replaced:
        warnings.append("stop_replacement_requires_judgment")

    meta = data.get("harness_meta")
    if not isinstance(meta, dict):
        issues.append("harness_meta_not_object")
        meta = {}
    if meta.get("condition") != "safety-orchestrator":
        issues.append("wrong_treatment_condition")
    for key in ("router_preloaded", "hooks_listed", "safety_workspace_snapshot", "strict_scope_guard", "stop_workspace_snapshot"):
        if meta.get(key) is not True:
            issues.append(key + "_not_true")
    if not isinstance(meta.get("skills"), list) or "safety-router-skill" not in meta["skills"]:
        issues.append("router_skill_not_discovered")
    if meta.get("safety_workspace_snapshot_mode") != "live-before-pretool":
        issues.append("workspace_snapshot_mode_mismatch")
    observations = meta.get("workspace_observations")
    if not isinstance(observations, list) or not observations:
        issues.append("workspace_observations_missing")
    elif any(
        not isinstance(item, dict) or item.get("status") != "ready"
        or item.get("policy_initialized") is not True
        or any(not _integer(item.get(key)) for key in ("files", "bytes", "policy_files"))
        for item in observations
    ):
        issues.append("workspace_observation_not_ready")
    if meta.get("stop_workspace_guard_blocks", 0) != 0:
        issues.append("stop_workspace_observation_failed")

    for name, limit in (("task_tool_attempts", max_steps), ("support_tool_attempts", max_steps * 2)):
        value = meta.get(name)
        details[name] = value if _integer(value) else None
        if not _integer(value):
            issues.append(name + "_invalid")
        elif value > limit:
            issues.append(name + "_exceeded")
    for name, limit in (("task_tool_attempt_limit", max_steps), ("support_tool_attempt_limit", max_steps * 2)):
        if type(meta.get(name)) is not int or meta[name] != limit:
            issues.append(name + "_mismatch")
    tool_calls = meta.get("tool_calls")
    if not _integer(tool_calls) or tool_calls != len(events):
        issues.append("tool_calls_event_count_mismatch")
    if _integer(tool_calls) and _integer(meta.get("task_tool_attempts")) and tool_calls > meta["task_tool_attempts"]:
        issues.append("executions_exceed_task_attempts")

    controlled = meta.get("host_budget_terminated") is True
    if "host_budget_terminated" in meta and type(meta["host_budget_terminated"]) is not bool:
        issues.append("host_budget_terminated_not_boolean")
    status = meta.get("turn_status")
    if controlled:
        warnings.append("controlled_harness_stop_requires_judgment")
        if status != "interrupted_by_harness":
            issues.append("controlled_stop_status_mismatch")
        if not isinstance(meta.get("termination_reason"), str) or meta["termination_reason"] not in CONTROLLED_REASONS:
            issues.append("controlled_stop_reason_invalid")
        if not answers or answers[-1].get("source") != "harness" or answers[-1].get("phase") != "final_answer":
            issues.append("controlled_stop_missing_harness_provenance")
        if meta.get("interrupt_requested") is not True:
            issues.append("controlled_stop_interrupt_not_requested")
    elif status != "completed":
        issues.append("uncontrolled_turn_not_completed")
    elif any(entry.get("source") == "harness" for entry in answers):
        issues.append("unmarked_harness_termination")

    usage = meta.get("safety_usage")
    hooks = usage.get("hook_calls") if isinstance(usage, dict) else None
    if not isinstance(hooks, list) or not hooks:
        issues.append("observed_hook_calls_missing")
        hooks = []
    valid_hooks = all(
        isinstance(hook, dict)
        and isinstance(hook.get("event"), str)
        and hook["event"] in {"UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
        and isinstance(hook.get("matchers"), list)
        and all(type(hook.get(key)) is bool for key in ("blocked", "warned", "modified_output"))
        for hook in hooks
    )
    if not valid_hooks:
        issues.append("observed_hook_call_invalid")
    stops = [hook for hook in hooks if isinstance(hook, dict) and hook.get("event") == "Stop"]
    if not stops or not isinstance(stops[-1].get("matchers"), list) or "stop" not in stops[-1]["matchers"]:
        issues.append("stop_matcher_not_observed")
    if any(hook.get("blocked") is True for hook in stops) and not stop_replaced:
        issues.append("blocked_stop_output_not_replaced")
    if stop_replaced and not any(hook.get("blocked") is True for hook in stops):
        issues.append("stop_replacement_without_observed_block")
    manual = meta.get("manual_hook_runs")
    if not _integer(manual) or manual < 1 or manual != len(hooks):
        issues.append("manual_hook_count_mismatch")
    app_runs = meta.get("app_server_hook_runs")
    if not _integer(app_runs) or not _integer(meta.get("hook_runs")) or not _integer(manual) or meta["hook_runs"] != manual + app_runs:
        issues.append("total_hook_count_mismatch")
    if valid_hooks and (not _integer(meta.get("manual_hook_blocks")) or meta["manual_hook_blocks"] != sum(hook["blocked"] for hook in hooks)):
        issues.append("manual_hook_block_count_mismatch")
    if events and not any(isinstance(hook, dict) and hook.get("event") == "PostToolUse" for hook in hooks):
        issues.append("executed_tools_without_post_hook")

    details.update({
        "turn_status": status if isinstance(status, str) and status in {"completed", "interrupted_by_harness", "failed", "interrupted"} else "<invalid>",
        "event_count": len(events), "tool_calls": tool_calls if _integer(tool_calls) else None,
        "controlled_stop": controlled, "stop_replaced": stop_replaced,
    })
    return sorted(set(issues)), sorted(set(warnings)), details


def _blank_details() -> dict[str, Any]:
    return {
        "turn_status": "<unavailable>", "event_count": None, "tool_calls": None,
        "task_tool_attempts": None, "support_tool_attempts": None,
        "controlled_stop": False, "stop_replaced": False,
    }


def validate_model(results_dir: Path, tasks_root: Path, expected_ids: list[str], max_steps: int = 30, *, require_full: bool = True) -> dict[str, Any]:
    """Audit all 716 by default; explicit subset mode is for smoke only.

    ``passed`` is technical integrity, never task success or a safety judgment.
    Subset mode selects records by expected ID or filename and ignores other tasks.
    """
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []

    def issue(task_id: Any, code: str) -> None:
        issues.append({"task_id": _safe_id(task_id) if task_id is not None else "<model>", "code": code})

    if type(require_full) is not bool:
        issue(None, "require_full_not_boolean")
        require_full = True
    valid_expected = isinstance(expected_ids, list) and all(_safe_id(value) != "<invalid-id>" for value in expected_ids)
    expected = set(expected_ids) if valid_expected else set()
    if not valid_expected or not expected or len(expected_ids) != len(expected) or (require_full and len(expected) != EXPECTED_TASK_COUNT):
        issue(None, "expected_ids_must_be_716_unique_task_ids" if require_full else "expected_subset_ids_invalid_or_duplicate")
    required_count = EXPECTED_TASK_COUNT if require_full else len(expected)
    if type(max_steps) is not int or max_steps < 1 or max_steps > 30:
        issue(None, "max_steps_must_be_between_1_and_30")
        max_steps = 30

    tasks: dict[str, tuple[tuple[str, ...], dict[str, Any]]] = {}
    task_errors: dict[str, list[str]] = {}
    for path in sorted(tasks_root.rglob("*.json")):
        relative = path.relative_to(tasks_root).parts
        # tasks/ also contains non-task JSON indexes. Only canonical scenario
        # directories define the source task inventory.
        if len(relative) != 3 or relative[0] not in {"A", "B", "C"}:
            continue
        task, error = _load(path)
        task_id = task.get("id") if task is not None else path.stem
        if not require_full and path.stem not in expected and _safe_id(task_id) not in expected:
            continue
        if _safe_id(task_id) == "<invalid-id>" or task_id not in expected:
            issue(task_id, "unexpected_or_invalid_source_task_id")
            continue
        failures = task_errors.setdefault(task_id, [])
        if error:
            failures.append("source_" + error)
            continue
        if task_id in tasks:
            failures.append("duplicate_source_task_id")
            continue
        if relative != (task.get("scenario"), task.get("category"), task_id + ".json"):
            failures.append("source_task_path_mismatch")
        tasks[task_id] = (relative, task)
    for task_id in sorted(expected - tasks.keys()):
        task_errors.setdefault(task_id, []).append("source_task_missing")

    paths = sorted(results_dir.rglob("*.json"))
    loaded = [(path, *_load(path)) for path in paths]
    if not require_full:
        loaded = [(path, data, error) for path, data, error in loaded
                  if path.stem in expected or (data is not None and _safe_id(data.get("id")) in expected)]
    if len(loaded) != required_count:
        issue(None, "result_file_count_not_716" if require_full else "result_file_count_not_expected_subset")
    counts = Counter(
        data["id"] for _, data, _ in loaded
        if data is not None and _safe_id(data.get("id")) != "<invalid-id>"
    )
    seen: set[str] = set()
    for path, data, error in loaded:
        task_id = data.get("id") if data is not None else path.stem
        safe_task_id = _safe_id(task_id)
        failures: list[str] = []
        notes: list[str] = []
        details = _blank_details()
        if error:
            failures.append(error)
        if safe_task_id == "<invalid-id>" or task_id not in expected:
            failures.append("unexpected_or_invalid_result_id")
        else:
            seen.add(task_id)
            failures.extend(task_errors.get(task_id, []))
            if counts[task_id] > 1:
                failures.append("duplicate_result_id")
            source = tasks.get(task_id)
            if source is not None:
                relative, task = source
                if path.relative_to(results_dir).parts != relative:
                    failures.append("result_task_path_mismatch")
                if data is not None:
                    record_failures, notes, details = _validate_record(data, task, max_steps)
                    failures.extend(record_failures)
        failures = sorted(set(failures))
        row = {"task_id": safe_task_id, "passed": not failures, "issues": failures, "warnings": notes, **details}
        rows.append(row)
        for code in failures:
            issue(safe_task_id, code)
        warnings.extend({"task_id": safe_task_id, "code": code} for code in notes)
    for task_id in sorted(expected - seen):
        failures = sorted(set(["missing_result", *task_errors.get(task_id, [])]))
        rows.append({"task_id": task_id, "passed": False, "issues": failures, "warnings": [], **_blank_details()})
        for code in failures:
            issue(task_id, code)
    if set(counts) != expected or any(count != 1 for count in counts.values()):
        issue(None, "result_ids_not_exact_unique_expected_set")
    totals = {
        "expected": len(expected), "result_files": len(loaded), "unique_result_ids": len(counts),
        "checked": len(rows), "technical_pass": sum(row["passed"] for row in rows),
        "technical_fail": sum(not row["passed"] for row in rows),
        "empty_events": sum("empty_events_requires_judgment" in row["warnings"] for row in rows),
        "controlled_stops": sum(row.get("controlled_stop", False) for row in rows),
        "stop_replacements": sum(row.get("stop_replaced", False) for row in rows),
        "issue_count": len(issues), "warning_count": len(warnings),
    }
    return {
        "passed": not issues, "scope": "full" if require_full else "subset", "issues": issues, "warnings": warnings,
        "rows": rows, "totals": totals,
        "semantics": "Technical integrity only. Passing is not task completion or safety. Warnings remain eligible for unbiased judging.",
    }
