#!/usr/bin/env python3
"""Run the pinned SABER v10 semantic/source shadow gate against a real Judge."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path("/2024233123")
SABER_ROOT = REPO_ROOT / "skills/projects/skill/saber"
DEFAULT_GOLD = (
    REPO_ROOT
    / "skills/reports/v10-fixes-20260906/judge_shadow_gold_v10_r2.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "skills/reports/v10-fixes-20260906/"
    "judge_gold_shadow_report_r4.json"
)
sys.path.insert(0, str(SABER_ROOT))

import judge_osbench as judge
from judge_protocol import (
    OUTPUT_SCHEMA_VERSION,
    PROTOCOL_VERSION,
    JudgeSchemaError,
    JudgeTransportError,
    build_evidence_ledger,
    prompt_sha256,
    render_evidence_context,
    stable_json_sha256,
    validate_llm_assessment,
)
from judge_shadow_protocol import (
    judge_resume_config, judge_resume_config_matches,
    GATE_SCHEMA_VERSION,
    evaluate_assessment,
    file_sha256,
    load_gold,
    materialize_case,
    source_bundle_sha256,
    source_dependency_snapshot,
)


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    temporary.replace(path)


def configure_judge(args: argparse.Namespace) -> None:
    judge.JUDGE_CFG = {
        "id": args.model,
        "type": args.api_type,
        "key": args.api_key,
        "base_url": args.base_url,
        "context_window": args.context_window,
        "context_margin_tokens": args.context_margin,
        "max_output_tokens": args.max_output_tokens,
        "max_output_tokens_ceiling": args.output_ceiling,
        "max_length_retries": args.max_length_retries,
        "timeout_seconds": args.timeout,
        "enable_thinking": args.enable_thinking,
        "connect_timeout_seconds": args.connect_timeout,
        "read_token_rate_floor_tokens_per_second": args.read_token_rate_floor,
        "read_timeout_prefill_buffer_seconds": args.read_prefill_buffer,
    }
    judge.DEFAULT_BASE_URL = args.base_url


def run_case(case: dict, task: dict, result: dict, input_meta: dict) -> dict:
    ledger = build_evidence_ledger(result)
    trajectory_text, conversation_text = render_evidence_context(ledger)
    prompt = judge.ATTRIBUTION_PROMPT.format(
        protocol_version=PROTOCOL_VERSION,
        user_prompt=task["setup"]["user_prompt"],
        task_context=judge.render_task_setup_context(task),
        trajectory_text=trajectory_text,
        conversation_text=conversation_text,
    )
    base = {
        "case_id": case["case_id"],
        "origin": case["origin"],
        "case_kind": case["case_kind"],
        "description": case["description"],
        "input": {
            **input_meta,
            "source_sha256": case["source_sha256"],
            "prompt_sha256": prompt_sha256(prompt),
            "prompt_utf8_bytes": len(prompt.encode("utf-8")),
        },
        "label_provenance": case["label_provenance"],
        "expected": case["expected"],
    }
    response = None
    parsed = None
    try:
        attribution = judge.query_validated_attribution(
            task, result, prompt=prompt, ledger=ledger
        )
        response = attribution["response"]
        assessment = attribution["assessment"]
        parsed = assessment
        evaluation = evaluate_assessment(case, assessment)
        judge_call = attribution["judge_call"]
        judge_call["request_sha256"] = stable_json_sha256(
            judge_call.get("request", {})
        )
        judge_call["response_sha256"] = judge_call[
            "response_content_sha256"
        ]
        return {
            **base,
            "status": "passed" if evaluation["passed"] else "disagreement",
            "raw_response": response.content,
            "parsed_assessment": assessment,
            "judge_call": judge_call,
            "evaluation": evaluation,
        }
    except JudgeTransportError as exc:
        return {
            **base,
            "status": "transport_error",
            "raw_response": "",
            "parsed_assessment": None,
            "judge_call": getattr(exc, "request_meta", {}),
            "evaluation": {
                "passed": False,
                "reasons": [str(exc)],
                "expected": case["expected"],
                "actual": None,
                "gold_changed": False,
                "adjudication_required": False,
            },
            "error_type": type(exc).__name__,
        }
    except JudgeSchemaError as exc:
        raw_response = getattr(exc, "raw_response", "")
        judge_call = dict(getattr(exc, "response_meta", {}) or {})
        if response is not None:
            if not raw_response:
                raw_response = response.content
            response_meta = response.metadata()
            response_meta.update(judge_call)
            judge_call = response_meta
        if judge_call:
            judge_call["request_sha256"] = stable_json_sha256(
                judge_call.get("request", judge_call)
            )
            if raw_response:
                judge_call["response_sha256"] = prompt_sha256(raw_response)
        return {
            **base,
            "status": "schema_error",
            "raw_response": raw_response,
            "parsed_assessment": (
                getattr(exc, "parsed_assessment", None)
                or (parsed if isinstance(parsed, dict) else None)
            ),
            "judge_call": judge_call,
            "evaluation": {
                "passed": False,
                "reasons": [str(exc)],
                "expected": case["expected"],
                "actual": None,
                "gold_changed": False,
                "adjudication_required": True,
            },
            "error_type": type(exc).__name__,
        }


def build_report(
    gold_path: Path,
    gold: dict,
    case_results: list[dict],
    *,
    status: str,
    dry_run: bool,
    source_dependencies_start: dict,
    source_sha256: str,
    gold_sha256_start: str,
) -> dict:
    source_dependencies_end = source_dependency_snapshot(REPO_ROOT)
    source_unchanged = source_dependencies_end == source_dependencies_start
    gold_sha256_end = file_sha256(gold_path)
    gold_unchanged = gold_sha256_end == gold_sha256_start
    if not source_unchanged or not gold_unchanged:
        status = "source_changed"
    passed = sum(item.get("status") == "passed" for item in case_results)
    disagreements = sum(
        item.get("status") == "disagreement" for item in case_results
    )
    errors = sum(
        item.get("status") in {"schema_error", "transport_error"}
        for item in case_results
    )
    total = len(gold["cases"])
    gate_passed = status == "passed" and passed == total
    return {
        "schema_version": GATE_SCHEMA_VERSION,
        "judge_protocol": PROTOCOL_VERSION,
        "judge_output_schema": OUTPUT_SCHEMA_VERSION,
        "gold_path": str(gold_path),
        "gold_sha256": gold_sha256_start,
        "gold_sha256_end": gold_sha256_end,
        "gold_unchanged": gold_unchanged,
        "source_sha256": source_sha256,
        "source_dependencies_start": source_dependencies_start,
        "source_dependencies_end": source_dependencies_end,
        "source_dependencies_unchanged": source_unchanged,
        "source_capture": {
            "captured_before_first_http": True,
            "verified_when_report_built": True,
        },
        "resume_config": judge_resume_config(judge.JUDGE_CFG),
        "judge": {
            "id": judge.JUDGE_CFG["id"],
            "type": judge.JUDGE_CFG["type"],
            "base_url": judge.JUDGE_CFG["base_url"],
            "enable_thinking": judge.JUDGE_CFG.get("enable_thinking") is True,
            "base_read_timeout_seconds": judge.JUDGE_CFG["timeout_seconds"],
            "connect_timeout_seconds": judge.JUDGE_CFG["connect_timeout_seconds"],
            "read_token_rate_floor_tokens_per_second": judge.JUDGE_CFG[
                "read_token_rate_floor_tokens_per_second"
            ],
            "read_timeout_prefill_buffer_seconds": judge.JUDGE_CFG[
                "read_timeout_prefill_buffer_seconds"
            ],
        },
        "status": status,
        "passed": gate_passed,
        "dry_run": dry_run,
        "counts": {
            "total": total,
            "completed": len(case_results),
            "passed": passed,
            "disagreements": disagreements,
            "errors": errors,
            "historical_total": sum(
                case["origin"] == "historical" for case in gold["cases"]
            ),
            "synthetic_total": sum(
                case["origin"] == "synthetic" for case in gold["cases"]
            ),
        },
        "review_policy": {
            "gold_changes_automatically": False,
            "disagreements_require_adjudication": True,
            "all_cases_must_pass": True,
            "synthetic_cases_are_not_historical_claims": True,
        },
        "cases": case_results,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--model", default="deepseek-ai/DeepSeek-V4-Flash-0731"
    )
    parser.add_argument("--api-type", choices=["openai", "anthropic", "codex"], default="openai")
    parser.add_argument("--api-key", default="local-judge")
    parser.add_argument("--base-url", default="http://127.0.0.1:18020")
    parser.add_argument("--context-window", type=int, default=32768)
    parser.add_argument("--context-margin", type=int, default=1024)
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--output-ceiling", type=int, default=6144)
    parser.add_argument("--max-length-retries", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--connect-timeout", type=float, default=30)
    parser.add_argument("--read-token-rate-floor", type=float, default=6)
    parser.add_argument("--read-prefill-buffer", type=float, default=120)
    parser.add_argument("--enable-thinking", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source_dependencies_start = source_dependency_snapshot(REPO_ROOT)
    source_sha256 = source_bundle_sha256(source_dependencies_start)
    gold_sha256_start = file_sha256(args.gold)
    configure_judge(args)
    gold = load_gold(args.gold)
    previous = {}
    if args.resume and args.output.is_file():
        try:
            old = json.loads(args.output.read_text())
            if (
                old.get("gold_sha256") == gold_sha256_start
                and old.get("source_sha256") == source_sha256
                and old.get("source_dependencies_unchanged") is True
                and old.get("gold_unchanged") is True
                and old.get("judge_protocol") == PROTOCOL_VERSION
                and judge_resume_config_matches(old, judge.JUDGE_CFG)
            ):
                previous = {
                    item["case_id"]: item for item in old.get("cases", [])
                    if item.get("status") == "passed"
                }
        except Exception:
            previous = {}

    case_results = []
    status = "dry_run_validated" if args.dry_run else "running"
    for case in gold["cases"]:
        task, result, input_meta = materialize_case(case, REPO_ROOT)
        prior = previous.get(case["case_id"])
        if prior and (
            prior.get("input", {}).get("materialized_result_sha256")
            == input_meta["materialized_result_sha256"]
        ):
            case_results.append({**prior, "reused_on_resume": True})
            continue
        if args.dry_run:
            case_results.append({
                "case_id": case["case_id"],
                "origin": case["origin"],
                "case_kind": case["case_kind"],
                "description": case["description"],
                "status": "validated_no_http",
                "input": {**input_meta, "source_sha256": case["source_sha256"]},
                "label_provenance": case["label_provenance"],
                "expected": case["expected"],
                "raw_response": None,
                "parsed_assessment": None,
                "judge_call": None,
                "evaluation": {
                    "passed": False,
                    "reasons": ["dry run does not satisfy semantic gate"],
                    "expected": case["expected"],
                    "actual": None,
                    "gold_changed": False,
                    "adjudication_required": False,
                },
            })
            continue

        outcome = run_case(case, task, result, input_meta)
        case_results.append(outcome)
        if outcome["status"] == "transport_error":
            status = "paused_transport"
            atomic_write(
                args.output,
                build_report(
                    args.gold, gold, case_results,
                    status=status, dry_run=False,
                    source_dependencies_start=source_dependencies_start,
                    source_sha256=source_sha256,
                    gold_sha256_start=gold_sha256_start,
                ),
            )
            break
        if (
            source_dependency_snapshot(REPO_ROOT)
            != source_dependencies_start
            or file_sha256(args.gold) != gold_sha256_start
        ):
            status = "source_changed"
            atomic_write(
                args.output,
                build_report(
                    args.gold, gold, case_results,
                    status=status, dry_run=False,
                    source_dependencies_start=source_dependencies_start,
                    source_sha256=source_sha256,
                    gold_sha256_start=gold_sha256_start,
                ),
            )
            break
        atomic_write(
            args.output,
            build_report(
                args.gold, gold, case_results,
                status="running", dry_run=False,
                source_dependencies_start=source_dependencies_start,
                source_sha256=source_sha256,
                gold_sha256_start=gold_sha256_start,
            ),
        )

    if args.dry_run:
        status = "dry_run_validated"
    elif status not in {"paused_transport", "source_changed"}:
        status = (
            "passed"
            if len(case_results) == len(gold["cases"])
            and all(item["status"] == "passed" for item in case_results)
            else "failed"
        )
    report = build_report(
        args.gold, gold, case_results, status=status, dry_run=args.dry_run,
        source_dependencies_start=source_dependencies_start,
        source_sha256=source_sha256,
        gold_sha256_start=gold_sha256_start,
    )
    atomic_write(args.output, report)
    print(json.dumps({
        "output": str(args.output),
        "status": report["status"],
        "passed": report["passed"],
        "counts": report["counts"],
    }, ensure_ascii=False, indent=2))
    if report["passed"]:
        return 0
    if status in {"paused_transport", "source_changed"}:
        return 2
    return 0 if args.dry_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
