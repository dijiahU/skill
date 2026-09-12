"""Summarize native Harbor trial results without treating pending tasks as zero."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re


def read_jsonl(path: Path) -> list[dict]:
    """Ignore non-JSON console lines; source files remain unchanged."""
    rows = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def audit_summary(trial: Path) -> dict:
    """Count observed reads and audit verdicts without claiming enforcement."""
    commands = [
        row["item"].get("command", "")
        for row in read_jsonl(trial / "agent/codex.txt")
        if row.get("type") == "item.completed"
        and row.get("item", {}).get("type") == "command_execution"
        and row["item"].get("exit_code") == 0
    ]
    reads = [
        command
        for command in commands
        if re.search(r"\b(cat|sed|head|tail)\b", command)
    ]
    root = trial / "agent/safety-audit"
    verdicts = read_jsonl(root / "verdict-log.jsonl")
    return {
        "router_read": any(
            "safety-router-skill/SKILL.md" in command for command in reads
        ),
        "archetype_files_read": sorted(
            set(re.findall(r"references/archetypes/([a-z0-9-]+\.md)", "\n".join(reads)))
        ),
        "tool_invocation_records": len(read_jsonl(root / "tool-invocations.jsonl")),
        "controller_decisions": dict(
            Counter(
                row.get("decision")
                for row in read_jsonl(root / "controller-decision-trace.jsonl")
            )
        ),
        "verdict_counts": dict(Counter(row.get("verdict") for row in verdicts)),
        "block_atoms": dict(
            Counter(
                row.get("atom_id") for row in verdicts if row.get("verdict") == "block"
            )
        ),
        "fail_open_records": len(read_jsonl(root / "fail-open-log.jsonl")),
    }


def summarize(root: Path) -> dict:
    """Keep task rewards, test counts, exceptions and usage separately visible."""
    manifest = json.loads((root / "manifest.json").read_text())
    expected = manifest["limit"] * manifest.get("attempts", 1)
    groups = {}
    for mode in ("none", "safety-orchestrator"):
        trials = []
        for path in sorted((root / mode).glob("*/*/result.json")):
            result = json.loads(path.read_text())
            tests = path.parent / "verifier/ctrf.json"
            tests_summary = None
            if tests.exists():
                tests_summary = (
                    json.loads(tests.read_text()).get("results", {}).get("summary")
                )
            trials.append(
                {
                    "task": result["task_name"],
                    "task_ref": result["task_id"].get("ref"),
                    "trial": result["trial_name"],
                    "finished_at": result.get("finished_at"),
                    "reward": (result.get("verifier_result") or {})
                    .get("rewards", {})
                    .get("reward"),
                    "exception": result.get("exception_info"),
                    "tests": tests_summary,
                    "usage": result.get("agent_result"),
                    "agent_execution": result.get("agent_execution"),
                    "audit": audit_summary(path.parent),
                    "result_path": str(path.resolve()),
                }
            )
        finished = [row for row in trials if row["finished_at"]]
        valid = [
            row
            for row in finished
            if row["reward"] is not None and row["exception"] is None
        ]
        all_valid = len(valid) == expected and len(trials) == expected
        groups[mode] = {
            "expected": expected,
            "finished": len(finished),
            "valid_scored": len(valid),
            "passed": sum(row["reward"] == 1 for row in valid),
            "complete_without_errors": all_valid,
            "mean_reward": sum(row["reward"] for row in valid) / expected
            if all_valid
            else None,
            "trials": trials,
        }
    return {
        "model": manifest["config"]["model"],
        "dataset": manifest["dataset"],
        "concurrency": manifest.get("concurrency", 1),
        "groups": groups,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="The run's terminalbench directory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarize(args.root)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    for mode, group in result["groups"].items():
        print(
            f"{mode}: finished={group['finished']}/{group['expected']}, "
            f"valid={group['valid_scored']}, passed={group['passed']}, "
            f"mean_reward={group['mean_reward']}"
        )
