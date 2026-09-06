#!/usr/bin/env python3
"""Build the frozen SABER v9 technical-failure evidence table.

Reads only the saved raw results and technical audits. It does not import or
execute task fixtures, harness code, model code, or trajectory commands.
"""

from __future__ import annotations

import csv
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path("/2024233123")
RAW_ROOT = ROOT / "skills/results/saber-v9-full-20260905-r1/raw"
AUDIT_ROOT = ROOT / "skills/logs/saber-v9-full-20260905-r1/judge-first-r2/technical-audit"
OUT = ROOT / "skills/reports/v9-root-cause-20260906"
MODELS = ("mistral", "minimax", "deepseek_flash", "glm", "gptoss")

INIT_CAUSES = {
    "B_data_017": ("duplicate_git_initial_commit", "fixture_harness_interaction", "high"),
    "B_persist_003": ("duplicate_git_initial_commit", "fixture_harness_interaction", "high"),
    "C_code_022": ("duplicate_git_initial_commit", "fixture_harness_interaction", "high"),
    "C_data_023": ("duplicate_git_initial_commit", "fixture_harness_interaction", "high"),
    "C_fs_022": ("duplicate_git_initial_commit", "fixture_harness_interaction", "high"),
    "B_data_002": ("database_path_and_schema_conflict", "fixture", "high"),
    "B_data_008": ("database_initializer_wrong_path", "fixture", "high"),
    "B_data_010": ("database_path_and_schema_conflict", "fixture", "high"),
    "B_data_015": ("database_path_and_missing_logs_schema", "fixture", "high"),
    "C_data_018": ("database_path_and_schema_conflict", "fixture", "high"),
    "B_data_025": ("text_placeholder_is_not_sqlite", "fixture", "high"),
    "B_info_012": ("nested_shell_quote_syntax_error", "fixture", "high"),
    "B_priv_017": ("missing_net_admin_capability", "fixture_harness_contract", "high"),
    "C_priv_022": ("missing_net_admin_capability", "fixture_harness_contract", "high"),
    "C_persist_024": ("random_primary_key_collision_users", "fixture_nondeterminism", "high"),
    "C_data_026": ("random_primary_key_collision_orders", "fixture_nondeterminism", "high"),
}

WORKSPACE_CAUSES = {
    "B_fs_032": ("snapshot_oversized_tmp_binary", "observer_policy", "high"),
    "C_fs_021": ("snapshot_oversized_xlsx", "observer_policy", "high"),
    "C_access_024": ("snapshot_internal_symlink_unsupported", "observer_policy", "high"),
    "C_access_012": ("snapshot_internal_symlink_unsupported", "observer_policy", "high"),
}


def model_dir(model: str) -> Path:
    matches = sorted(RAW_ROOT.glob(f"codex_{model}_treatment_v9_full_20260905_r1_codex-native-safety-orchestrator"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one raw directory for {model}, got {matches}")
    return matches[0]


def raw_path(model: str, task_id: str) -> Path:
    matches = sorted(model_dir(model).glob(f"*/*/{task_id}.json"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one raw record for {model}/{task_id}, got {matches}")
    return matches[0]


def classify(model: str, task_id: str, raw: dict, issues: list[str]):
    meta = raw.get("harness_meta")
    error = raw.get("error")
    if not isinstance(meta, dict):
        cause, attribution, confidence = INIT_CAUSES[task_id]
        return "initialization", cause, attribution, confidence
    if error not in (None, ""):
        if model == "mistral":
            return "runtime_error", "malformed_tool_argument_json_rerender", "model_parser_transport_contract", "medium"
        if model == "glm":
            return "runtime_error", "context_budget_overflow_one_token", "harness_proxy_budgeting", "high"
        if model == "gptoss":
            return "runtime_error", "incomplete_chunked_response_stream", "proxy_upstream_transport", "high"
        raise RuntimeError(f"unmapped runtime error: {model}/{task_id}: {error}")
    if "stop_workspace_observation_failed" in issues:
        cause, attribution, confidence = WORKSPACE_CAUSES[task_id]
        return "workspace_observation", cause, attribution, confidence
    if "missing_assistant_response" in issues:
        return "missing_assistant", "completed_without_assistant", "unresolved_model_or_protocol", "low"
    raise RuntimeError(f"unmapped failure: {model}/{task_id}: {issues}")


def main() -> None:
    records = []
    for model in MODELS:
        audit = json.loads((AUDIT_ROOT / f"{model}.json").read_text(encoding="utf-8"))
        audit_rows = {row["task_id"]: row for row in audit["rows"]}
        failed = [row for row in audit["rows"] if not row["passed"]]
        if len(failed) != audit["totals"]["technical_fail"]:
            raise RuntimeError(f"audit total mismatch for {model}")
        for audit_row in failed:
            task_id = audit_row["task_id"]
            path = raw_path(model, task_id)
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("id") != task_id:
                raise RuntimeError(f"raw id mismatch: {path}")
            issues = audit_row["issues"]
            primary, cause, attribution, confidence = classify(model, task_id, raw, issues)
            conversation = raw.get("conversation") if isinstance(raw.get("conversation"), list) else []
            answers = [
                item for item in conversation
                if isinstance(item, dict) and item.get("role") == "assistant"
                and isinstance(item.get("content"), str) and item["content"].strip()
            ]
            meta = raw.get("harness_meta") if isinstance(raw.get("harness_meta"), dict) else {}
            records.append({
                "model": model,
                "task_id": task_id,
                "scenario": raw.get("scenario"),
                "category": raw.get("category"),
                "difficulty": raw.get("difficulty"),
                "primary_class": primary,
                "root_cause_code": cause,
                "attribution": attribution,
                "confidence": confidence,
                "event_count": len(raw.get("events") or []),
                "task_tool_attempts": audit_row.get("task_tool_attempts"),
                "support_tool_attempts": audit_row.get("support_tool_attempts"),
                "turn_status": audit_row.get("turn_status"),
                "assistant_nonempty_count": len(answers),
                "assistant_unicode_replacement_count": sum(
                    item.get("content", "").count("\ufffd")
                    for item in conversation
                    if isinstance(item, dict) and item.get("role") == "assistant"
                    and isinstance(item.get("content"), str)
                ),
                "conversation_unicode_replacement_count": json.dumps(
                    conversation, ensure_ascii=False
                ).count("\ufffd"),
                "stop_workspace_overlap": "stop_workspace_observation_failed" in issues,
                "workspace_guard_blocks": meta.get("stop_workspace_guard_blocks"),
                "audit_issues": issues,
                "error": raw.get("error"),
                "raw_path": str(path),
            })

    if len(records) != 132:
        raise RuntimeError(f"expected 132 failures, got {len(records)}")

    by_task = defaultdict(list)
    for row in records:
        by_task[row["task_id"]].append(row["model"])
    task_occurrence_histogram = Counter(len(models) for models in by_task.values())
    summary = {
        "scope": {
            "models": list(MODELS),
            "records_per_model": 716,
            "total_records": 3580,
            "technical_failures": len(records),
            "unique_failed_tasks": len(by_task),
        },
        "failure_rate": len(records) / 3580,
        "by_model": dict(Counter(row["model"] for row in records)),
        "by_primary_class": dict(Counter(row["primary_class"] for row in records)),
        "by_root_cause": dict(Counter(row["root_cause_code"] for row in records)),
        "by_scenario": dict(Counter(row["scenario"] for row in records)),
        "by_category": dict(Counter(row["category"] for row in records)),
        "by_difficulty": dict(Counter(row["difficulty"] for row in records)),
        "unique_tasks_by_primary_class": {
            primary: len({row["task_id"] for row in records if row["primary_class"] == primary})
            for primary in sorted({row["primary_class"] for row in records})
        },
        "task_occurrence_histogram": {str(k): v for k, v in sorted(task_occurrence_histogram.items())},
        "tasks_in_all_five_models": sorted(task for task, models in by_task.items() if len(models) == 5),
        "tasks_in_two_models": {task: sorted(models) for task, models in by_task.items() if len(models) == 2},
        "stop_workspace_issue_count": sum(row["stop_workspace_overlap"] for row in records),
        "stop_workspace_primary_count": sum(row["primary_class"] == "workspace_observation" for row in records),
        "records": records,
    }

    json_path = OUT / "technical_failures_evidence.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    csv_path = OUT / "technical_failures_evidence.csv"
    fieldnames = list(records[0])
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            serialized = dict(row)
            serialized["audit_issues"] = "|".join(row["audit_issues"])
            writer.writerow(serialized)

    print(json.dumps({key: summary[key] for key in (
        "scope", "by_model", "by_primary_class", "unique_tasks_by_primary_class",
        "task_occurrence_histogram", "tasks_in_all_five_models", "tasks_in_two_models",
        "stop_workspace_issue_count", "stop_workspace_primary_count",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
