#!/usr/bin/env python3
"""Aggregate technically valid, usable SABER v9 harmful judgments.

This script is evidence generation only. It reads frozen result JSON and writes
compact summaries in the same report directory; it never executes trajectories.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path("/2024233123")
RUN = ROOT / "skills/results/saber-v9-full-20260905-r1"
JUDGED = RUN / "judged-provisional-r2"
RAW = RUN / "raw"
OUT = ROOT / "skills/reports/v9-root-cause-20260906"
MODELS = ["mistral", "minimax", "deepseek_flash", "glm", "gptoss"]
SLUG = "codex_{model}_treatment_v9_full_20260905_r1_codex-native-safety-orchestrator"


def bump_nested(table: dict, keys: tuple[str, ...]) -> None:
    cursor = table
    for key in keys[:-1]:
        cursor = cursor.setdefault(key, {})
    cursor[keys[-1]] = cursor.get(keys[-1], 0) + 1


def failed_output(text: str) -> bool:
    lowered = text.lower()
    needles = (
        "command not found", "no such file", "permission denied", "operation not permitted",
        "not installed", "failed", "failure", "error:", "cannot ", "could not ",
        "timed out", "unable to", "拒绝", "失败", "不存在", "未找到",
    )
    return any(needle in lowered for needle in needles)


summary: dict = {
    "scope": {
        "models": MODELS,
        "filter": "technical_validity.passed == true and judge_status == usable",
        "judged_glob": "[ABC]/*/*.json (excluding _attempts)",
    },
    "models": {},
    "all_harmful": {},
    "cross_model": {},
}
rows: list[dict] = []
task_models: dict[str, dict[str, bool]] = defaultdict(dict)

all_counts = Counter()
all_categories = Counter()
all_scenarios = Counter()
all_difficulty = Counter()
all_causes = Counter()
all_terminations = Counter()
all_atoms = Counter()
all_patterns = Counter()
all_match_kinds = Counter()
all_evidence_sources = Counter()
all_category_models: dict[str, Counter] = defaultdict(Counter)

for model in MODELS:
    slug = SLUG.format(model=model)
    model_judged = JUDGED / slug
    official_summary = json.loads((model_judged / "summary.json").read_text())
    files = sorted(path for scenario in "ABC" for path in (model_judged / scenario).glob("*/*.json"))
    model_counts = Counter(total_files=len(files))
    categories = Counter()
    scenarios = Counter()
    difficulties = Counter()
    causes = Counter()
    terminations = Counter()
    atoms = Counter()
    patterns = Counter()
    match_kinds = Counter()
    evidence_sources = Counter()

    for judged_path in files:
        judged = json.loads(judged_path.read_text())
        valid = bool(judged.get("technical_validity", {}).get("passed"))
        usable = judged.get("judge_status") == "usable"
        if not (valid and usable):
            model_counts["excluded"] += 1
            continue

        model_counts["eligible"] += 1
        harmful = bool(judged.get("harmful"))
        task_id = judged["id"]
        task_models[task_id][model] = harmful
        if not harmful:
            continue

        model_counts["harmful"] += 1
        category = judged.get("category") or "unknown"
        scenario = judged.get("scenario") or "unknown"
        difficulty = judged.get("difficulty") or "unknown"
        cause = judged.get("cause") or "unknown"
        termination = judged.get("termination") or "unknown"
        categories[category] += 1
        scenarios[scenario] += 1
        difficulties[difficulty] += 1
        causes[cause] += 1
        terminations[termination] += 1
        all_categories[category] += 1
        all_scenarios[scenario] += 1
        all_difficulty[difficulty] += 1
        all_causes[cause] += 1
        all_terminations[termination] += 1
        all_category_models[category][model] += 1

        source_raw = RAW / slug / scenario / category / f"{task_id}.json"
        raw = json.loads(source_raw.read_text())
        meta = raw.get("harness_meta") or {}
        usage = meta.get("safety_usage") or {}
        hook_calls = usage.get("hook_calls") or []
        triggered = sorted({atom for call in hook_calls for atom in (call.get("triggered_atoms") or [])})
        block_count = sum(bool(call.get("blocked")) for call in hook_calls)
        warning_count = sum(bool(call.get("warned")) for call in hook_calls)
        for atom in triggered:
            atoms[atom] += 1
            all_atoms[atom] += 1

        harmful_commands = judged.get("harmful_commands") or []
        candidate_commands = judged.get("candidate_harmful_commands") or []
        trajectory_by_step = {entry.get("step"): entry for entry in raw.get("trajectory", [])}
        outputs = []
        delta_count = 0
        apparent_failed_count = 0
        for command in harmful_commands:
            step = command.get("step")
            trajectory = trajectory_by_step.get(step, {})
            output = str(trajectory.get("output") or "")
            outputs.append(output)
            delta_count += len(trajectory.get("deltas") or [])
            apparent_failed_count += failed_output(output)
            pattern = command.get("pattern") or "unknown"
            match_kind = command.get("match_kind") or "unknown"
            evidence_source = command.get("evidence_source") or "unknown"
            patterns[pattern] += 1
            match_kinds[match_kind] += 1
            evidence_sources[evidence_source] += 1
            all_patterns[pattern] += 1
            all_match_kinds[match_kind] += 1
            all_evidence_sources[evidence_source] += 1

        has_commands = bool(harmful_commands)
        has_candidates = bool(candidate_commands)
        model_counts["harmful_with_executed_command_evidence" if has_commands else "harmful_without_executed_command_evidence"] += 1
        model_counts["harmful_with_candidate_evidence"] += int(has_candidates)
        model_counts["harmful_with_any_hook_block"] += int(block_count > 0)
        model_counts["harmful_with_any_hook_warning"] += int(warning_count > 0)
        model_counts["harmful_with_triggered_hook_atom"] += int(bool(triggered))
        model_counts["harmful_with_skill_read"] += int(bool(usage.get("skill_reads")))
        model_counts["harmful_command_no_delta"] += int(has_commands and delta_count == 0)
        model_counts["harmful_command_apparent_failure"] += int(apparent_failed_count > 0)
        all_counts.update({
            "harmful": 1,
            "with_executed_command_evidence": int(has_commands),
            "without_executed_command_evidence": int(not has_commands),
            "with_candidate_evidence": int(has_candidates),
            "with_any_hook_block": int(block_count > 0),
            "with_any_hook_warning": int(warning_count > 0),
            "with_triggered_hook_atom": int(bool(triggered)),
            "with_skill_read": int(bool(usage.get("skill_reads"))),
            "harmful_command_no_delta": int(has_commands and delta_count == 0),
            "harmful_command_apparent_failure": int(apparent_failed_count > 0),
        })

        rows.append({
            "model": model,
            "task_id": task_id,
            "scenario": scenario,
            "category": category,
            "difficulty": difficulty,
            "cause": cause,
            "termination": termination,
            "harmful_command_count": len(harmful_commands),
            "candidate_command_count": len(candidate_commands),
            "harmful_command_delta_count": delta_count,
            "apparent_failed_harmful_command_count": apparent_failed_count,
            "hook_block_count": block_count,
            "hook_warning_count": warning_count,
            "triggered_atoms": ";".join(triggered),
            "skill_read_count": len(usage.get("skill_reads") or []),
            "turn_status": meta.get("turn_status"),
            "judged_path": str(judged_path),
            "raw_path": str(source_raw),
            "harmful_patterns": ";".join(str(x.get("pattern") or "unknown") for x in harmful_commands),
            "harmful_steps": ";".join(str(x.get("step")) for x in harmful_commands),
        })

    summary["models"][model] = {
        "counts": dict(model_counts),
        "harmful_over_primary": (
            model_counts["harmful"] / model_counts["eligible"] if model_counts["eligible"] else None
        ),
        "official_hsr_effective": official_summary["summary"]["HSR"],
        "official_effective_denominator": official_summary["primary_effective_denominator"],
        "categories": dict(categories.most_common()),
        "scenarios": dict(scenarios.most_common()),
        "difficulties": dict(difficulties.most_common()),
        "causes": dict(causes.most_common()),
        "terminations": dict(terminations.most_common()),
        "triggered_atoms": dict(atoms.most_common()),
        "harmful_patterns": dict(patterns.most_common()),
        "match_kinds": dict(match_kinds.most_common()),
        "evidence_sources": dict(evidence_sources.most_common()),
    }

summary["all_harmful"] = {
    "counts": dict(all_counts),
    "categories": dict(all_categories.most_common()),
    "scenarios": dict(all_scenarios.most_common()),
    "difficulties": dict(all_difficulty.most_common()),
    "causes": dict(all_causes.most_common()),
    "terminations": dict(all_terminations.most_common()),
    "triggered_atoms": dict(all_atoms.most_common()),
    "harmful_patterns": dict(all_patterns.most_common()),
    "match_kinds": dict(all_match_kinds.most_common()),
    "evidence_sources": dict(all_evidence_sources.most_common()),
    "category_by_model": {key: dict(value) for key, value in sorted(all_category_models.items())},
}

agreement = Counter()
task_details = {}
for task_id, verdicts in sorted(task_models.items()):
    harmful_models = sorted(model for model, harmful in verdicts.items() if harmful)
    usable_models = sorted(verdicts)
    agreement[f"{len(harmful_models)}_harmful_of_{len(usable_models)}_usable"] += 1
    if harmful_models:
        task_details[task_id] = {"harmful_models": harmful_models, "usable_models": usable_models}
summary["cross_model"] = {
    "agreement_histogram": dict(sorted(agreement.items())),
    "harmful_task_count": len(task_details),
    "tasks": task_details,
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "harmful_aggregate.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
with (OUT / "harmful_records.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

print(json.dumps({
    "output_json": str(OUT / "harmful_aggregate.json"),
    "output_csv": str(OUT / "harmful_records.csv"),
    "model_counts": {model: summary["models"][model]["counts"] for model in MODELS},
    "all_harmful_counts": summary["all_harmful"]["counts"],
}, ensure_ascii=False, indent=2))
