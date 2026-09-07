#!/usr/bin/env python3
"""Prepare and run the gated SABER v10 paired pilot/full evaluation.

Importing this module is side-effect free. ``--prepare`` only creates a new,
versioned freeze/result/log tree. All workload actions require execution from
that freeze plus explicit scoped lifecycle approval.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
import re
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from typing import Any


ROOT = Path("/2024233123/skills")
SABER = ROOT / "projects/skill/saber"
BUNDLE = ROOT / "projects/skill/agent-safety-orchestrator/agent-safety-orchestrator"
FIXTURE_REVISION = ROOT / "jobs/saber-v10-fixtures-20260906-r2"
PILOT_PLAN = ROOT / "jobs/saber_v10_expanded_pilot_plan.json"
DEFAULT_BATCH = "v10-paired-20260906-r1"
BATCH_PATTERN = re.compile(r"v10-paired-[0-9]{8}-r[1-9][0-9]*")


def _validate_batch_id(value: str) -> str:
    if BATCH_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "batch ID must match v10-paired-YYYYMMDD-rN with N >= 1"
        )
    return value


def _batch_from_location(path: Path) -> str | None:
    for parent in path.resolve().parents:
        if parent.name.startswith("saber-v10-paired-"):
            candidate = parent.name.removeprefix("saber-")
            return _validate_batch_id(candidate)
    return None


def _select_batch(value: str) -> None:
    global BATCH, JOB, FROZEN, DATA, LOG, MANIFEST
    BATCH = _validate_batch_id(value)
    JOB = ROOT / "jobs" / ("saber-" + BATCH)
    FROZEN = JOB / "frozen"
    DATA = ROOT / "results" / ("saber-" + BATCH)
    LOG = ROOT / "logs" / ("saber-" + BATCH)
    MANIFEST = FROZEN / "manifest.json"


BATCH = _validate_batch_id(
    os.environ.get("SABER_V10_BATCH_ID")
    or _batch_from_location(Path(__file__))
    or DEFAULT_BATCH
)
_select_batch(BATCH)
IMAGE = "saber-codex-runner:0.149.1"
IMAGE_IDS = {
    IMAGE: "sha256:3749667060d25e3b6503c74521a13556e618d308803e9774e754ea64ab6401a1",
    "osbench-sandbox:latest": "sha256:439dd2c1803d6f9cd223fcae4fbb6e859ce3bddaea33eaca5e50f83d93949044",
}
EXPECTED_MODELS = ("mistral", "minimax", "deepseek_flash", "glm", "gptoss")
CONDITIONS = ("none", "safety-orchestrator")
PROTOCOL_REPORT = ROOT / "reports/v10-fixes-20260906/protocol_probe_report_r5.json"
FIXTURE_REPORT = ROOT / "reports/v10-fixes-20260906/fixture_runtime_preflight_r4.json"
JUDGE_SHADOW_REPORT = ROOT / "reports/v10-fixes-20260906/judge-shadow-deepseek-r3/shadow-report.json"
JUDGE_SHADOW_GOLD = ROOT / "reports/v10-fixes-20260906/judge_shadow_gold_v10_r4.json"
JUDGE_FULL_PIPELINE_REPORT = ROOT / "reports/v10-fixes-20260906/judge-full-pipeline-r12/shadow-report.json"
JUDGE_FULL_PIPELINE_GOLD = ROOT / "reports/v10-fixes-20260906/judge_full_pipeline_gold_manifest_v10_r3.json"
JUDGE_SHADOW_MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731"
JUDGE_FULL_PIPELINE_BUDGET = {
    "context_window": 65536,
    "context_margin_tokens": 2048,
    "max_output_tokens": 6144,
    "max_output_tokens_ceiling": 12288,
}
JUDGE_FULL_PIPELINE_TIMEOUT_POLICY = {
    "base_read_timeout_seconds": 600.0,
    "connect_timeout_seconds": 30.0,
    "read_token_rate_floor_tokens_per_second": 6.0,
    "read_timeout_prefill_buffer_seconds": 120.0,
}
JUDGE_TIMEOUT_FORMULA = (
    "max(base_read, prefill_buffer + actual_max_output_tokens / token_rate_floor)"
)
PILOT_SEMANTICS_REPORT = ROOT / "reports/v10-fixes-20260906/pilot_semantics_report.json"
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()


def stable_canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _sha256_string(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


def load_judge_gold_contract(path: Path = JUDGE_SHADOW_GOLD) -> dict[str, Any]:
    data = json.loads(path.read_text())
    cases = data.get("cases")
    if (data.get("schema_version") != "saber-judge-shadow-gold-v10.0"
            or data.get("judge_protocol") != "saber-judge-v10.0"
            or not isinstance(cases, list) or len(cases) < 4
            or len({case.get("case_id") for case in cases if isinstance(case, dict)}) != len(cases)):
        raise RuntimeError("Judge shadow gold schema or case inventory is invalid")
    expectations = {}
    origins = {"historical": 0, "synthetic": 0}
    harm = {True: 0, False: 0}
    coverage = {(origin, harmful): 0 for origin in origins for harmful in harm}
    for case in cases:
        case_id = case.get("case_id")
        expected = case.get("expected")
        provenance = case.get("label_provenance")
        origin = case.get("origin")
        if (not isinstance(case_id, str) or not case_id
                or origin not in origins
                or not isinstance(expected, dict) or type(expected.get("harmful")) is not bool
                or not isinstance(provenance, dict)
                or provenance.get("selection_independent_of_shadow_output") is not True
                or not all(isinstance(case.get(key), str) and len(case[key]) == 64
                           for key in ("source_sha256", "materialized_task_sha256",
                                       "materialized_result_sha256"))):
            raise RuntimeError(f"Judge shadow gold case contract is invalid: {case_id!r}")
        if origin == "synthetic" and provenance.get("synthetic") is not True:
            raise RuntimeError(f"synthetic Judge gold lacks explicit provenance: {case_id}")
        if origin == "historical" and "raw_ref" not in case:
            raise RuntimeError(f"historical Judge gold lacks raw reference: {case_id}")
        if origin == "historical":
            label_path = provenance.get("source_artifact")
            label_sha = provenance.get("source_artifact_sha256")
            resolved_label = ROOT.parent / label_path if isinstance(label_path, str) else None
            if (resolved_label is None or not resolved_label.is_file()
                    or sha256_file(resolved_label) != label_sha):
                raise RuntimeError(f"historical Judge gold label source is missing or stale: {case_id}")
        for ref_name in ("task_ref",) + (("raw_ref",) if origin == "historical" else ()):
            ref = case.get(ref_name)
            if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
                raise RuntimeError(f"Judge gold {case_id} has invalid {ref_name}")
            source_path = ROOT.parent / ref["path"]
            if not source_path.is_file() or sha256_file(source_path) != ref.get("sha256"):
                raise RuntimeError(f"Judge gold {case_id} {ref_name} is missing or stale")
        expectations[case_id] = {
            "origin": origin,
            "harmful": expected["harmful"],
            "source_sha256": case["source_sha256"],
            "materialized_task_sha256": case["materialized_task_sha256"],
            "materialized_result_sha256": case["materialized_result_sha256"],
            "label_provenance": provenance,
            "expected": expected,
        }
        origins[origin] += 1
        harm[expected["harmful"]] += 1
        coverage[(origin, expected["harmful"])] += 1
    if any(count < 1 for count in coverage.values()):
        raise RuntimeError(
            "Judge shadow gold requires historical/synthetic positive and negative coverage"
        )
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "schema_version": data["schema_version"],
        "judge_protocol": data["judge_protocol"],
        "judge_output_schema": "saber-judge-output-v10.0",
        "case_count": len(cases),
        "origin_counts": origins,
        "harmful_counts": {str(key).lower(): value for key, value in harm.items()},
        "coverage_counts": {
            f"{origin}_{str(harmful).lower()}": count
            for (origin, harmful), count in coverage.items()
        },
        "case_expectations": expectations,
    }



def load_full_pipeline_gold_contract(
    path: Path = JUDGE_FULL_PIPELINE_GOLD,
) -> dict[str, Any]:
    manifest = json.loads(path.read_text())
    sources = manifest.get("gold_sources")
    acceptance = manifest.get("acceptance")
    required_branches = {
        "attribution", "rule_evaluation", "zero_event_utility", "abort_validity",
    }
    if (manifest.get("schema_version")
            != "saber-judge-full-pipeline-gold-manifest-v10.0"
            or manifest.get("judge_protocol") != "saber-judge-v10.0"
            or manifest.get("status") != "gold_ready_not_executed"
            or not isinstance(sources, list) or len(sources) != 2
            or not isinstance(acceptance, dict)
            or acceptance.get("all_cases_must_pass") is not True
            or acceptance.get("disagreement_changes_gold_automatically") is not False
            or set(acceptance.get("required_branches", [])) != required_branches):
        raise RuntimeError("full-pipeline Judge gold manifest contract is invalid")
    source_contracts = {}
    cases = {}
    origin_counts = {"historical": 0, "synthetic": 0}
    for source in sources:
        role = source.get("role") if isinstance(source, dict) else None
        if role in source_contracts or role not in {
            "primary_attribution_gold", "utility_source_supplement",
        }:
            raise RuntimeError("full-pipeline Judge gold source roles are invalid")
        relative = source.get("path")
        resolved = ROOT.parent / relative if isinstance(relative, str) else None
        if (resolved is None or not resolved.is_file()
                or not _sha256_string(source.get("sha256"))
                or sha256_file(resolved) != source["sha256"]):
            raise RuntimeError(f"full-pipeline Judge gold source is missing or stale: {role}")
        value = json.loads(resolved.read_text())
        source_cases = value.get("cases")
        if (value.get("schema_version") != source.get("schema_version")
                or not isinstance(source_cases, list)
                or len(source_cases) != source.get("case_count")):
            raise RuntimeError(f"full-pipeline Judge gold source schema/count failed: {role}")
        source_contracts[role] = {
            "path": relative, "sha256": source["sha256"],
            "schema_version": source["schema_version"],
            "case_count": source["case_count"],
        }
        for case in source_cases:
            case_id = case.get("case_id") if isinstance(case, dict) else None
            origin = case.get("origin") if isinstance(case, dict) else None
            expected = case.get("expected_full") or case.get("expected") if isinstance(case, dict) else None
            provenance = case.get("label_provenance") if isinstance(case, dict) else None
            if (not isinstance(case_id, str) or not case_id or case_id in cases
                    or origin not in origin_counts
                    or not isinstance(expected, dict)
                    or not isinstance(provenance, dict)
                    or provenance.get("selection_independent_of_shadow_output") is not True
                    or not isinstance(case.get("case_kind"), str)
                    or not isinstance(case.get("description"), str)
                    or not all(_sha256_string(case.get(key)) for key in (
                        "source_sha256", "materialized_task_sha256",
                        "materialized_result_sha256",
                    ))):
                raise RuntimeError(f"full-pipeline Judge gold case is invalid: {case_id!r}")
            if origin == "synthetic" and provenance.get("synthetic") is not True:
                raise RuntimeError(f"full-pipeline synthetic provenance failed: {case_id}")
            cases[case_id] = {
                "origin": origin, "case_kind": case["case_kind"],
                "description": case["description"], "expected": expected,
                "label_provenance": provenance,
                "source_sha256": case["source_sha256"],
                "materialized_task_sha256": case["materialized_task_sha256"],
                "materialized_result_sha256": case["materialized_result_sha256"],
            }
            origin_counts[origin] += 1
    primary = source_contracts.get("primary_attribution_gold")
    supplement = source_contracts.get("utility_source_supplement")
    primary_contract = load_judge_gold_contract()
    if (primary is None or supplement is None
            or Path(ROOT.parent / primary["path"]).resolve() != JUDGE_SHADOW_GOLD.resolve()
            or primary["sha256"] != primary_contract["sha256"]
            or primary["case_count"] != primary_contract["case_count"]
            or supplement["schema_version"]
            != "saber-judge-utility-source-supplement-v10.2"
            or supplement["case_count"] != 4
            or acceptance.get("case_count") != len(cases)
            or set(acceptance.get("required_case_ids", [])) != set(cases)):
        raise RuntimeError("full-pipeline Judge primary/supplement composition is invalid")
    return {
        "path": str(path.resolve()), "sha256": sha256_file(path),
        "schema_version": manifest["schema_version"],
        "judge_protocol": manifest["judge_protocol"],
        "judge_output_schema": "saber-judge-output-v10.0",
        "case_count": len(cases), "origin_counts": origin_counts,
        "required_branches": sorted(required_branches),
        "gold_sources": source_contracts,
        "gold_source_sha256": {
            item["path"]: item["sha256"] for item in source_contracts.values()
        },
        "case_expectations": cases,
    }


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.replace(pending, path)


def event(message: str, **fields: Any) -> None:
    row = {"time": time.strftime("%Y-%m-%d %H:%M:%S %z"), "event": message, **fields}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    LOG.mkdir(parents=True, exist_ok=True)
    with (LOG / "events.jsonl").open("a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def fingerprint(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): sha256_file(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def check_frozen() -> None:
    expected = json.loads((JOB / "frozen-fingerprint.json").read_text())
    if fingerprint(FROZEN) != expected:
        raise RuntimeError("frozen experiment inputs changed; refusing mixed-version run")


def host_path(path: Path) -> str:
    relative = path.resolve().relative_to(Path(os.environ["POD_USER_ROOT"]).resolve())
    return str(Path(os.environ["HOST_USER_ROOT"]) / relative)


def load_plan(path: Path = PILOT_PLAN) -> dict[str, Any]:
    plan = json.loads(path.read_text())
    if plan.get("status") != "planned_not_executed":
        raise ValueError("expanded pilot plan status must remain planned_not_executed")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 52 or len(set(tasks)) != 52:
        raise ValueError("expanded pilot must contain 52 unique task IDs")
    if tuple(plan.get("models", ())) != EXPECTED_MODELS:
        raise ValueError("expanded pilot model inventory/order changed")
    if tuple(plan.get("conditions", ())) != CONDITIONS:
        raise ValueError("expanded pilot conditions changed")
    if plan.get("fixture_revision") != "saber-v10-fixtures-20260906-r2":
        raise ValueError("expanded pilot fixture revision changed")
    if plan.get("task_root") != str(FIXTURE_REVISION / "tasks"):
        raise ValueError("expanded pilot task root changed")
    if set(plan.get("protocol_probes", [])) != set(PROTOCOL_REQUIRED_CHECKS):
        raise ValueError("expanded pilot protocol probe inventory changed")
    if plan.get("no_full_run_before_all_gates") is not True:
        raise ValueError("expanded pilot must prohibit ungated full execution")
    return plan


def build_schedule(specs: list[dict[str, Any]]) -> list[list[str]]:
    by_key = {spec["key"]: spec for spec in specs}
    if set(by_key) != set(EXPECTED_MODELS):
        raise ValueError("model specs do not contain the exact formal five")
    waves = [["mistral"], ["minimax"], ["deepseek_flash"], ["glm", "gptoss"]]
    for wave in waves:
        used: set[int] = set()
        for key in wave:
            gpus = set(by_key[key]["gpus"])
            if used & gpus:
                raise ValueError(f"GPU overlap inside concurrent wave: {wave}")
            used |= gpus
    if by_key["glm"]["gpus"] != [1] or by_key["gptoss"]["gpus"] != [0]:
        raise ValueError("GLM/GPT-oss physical GPU pairing changed")
    if any(by_key[key]["gpus"] != [0, 1] for key in waves[0] + waves[1] + waves[2]):
        raise ValueError("dual-GPU model reservation changed")
    return waves


def _copytree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source, destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
    )


def _task_index(task_root: Path) -> tuple[list[str], dict[str, Path]]:
    paths = sorted(task_root.glob("[ABC]/*/*.json"))
    rows = [(json.loads(path.read_text())["id"], path) for path in paths]
    by_id = dict(rows)
    if len(rows) != len(by_id) or len(rows) != 716:
        raise ValueError("fixture tree must contain 716 unique tasks")
    return [task_id for task_id, _ in rows], by_id


def _write_subsets(directory: Path, task_ids: list[str], workers: int = 8) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    parts = [[] for _ in range(workers)]
    for index, task_id in enumerate(task_ids):
        parts[index % workers].append(task_id)
    flattened = [task for part in parts for task in part]
    if sorted(flattened) != sorted(task_ids) or len(flattened) != len(set(flattened)):
        raise AssertionError("subset partition changed task identity")
    for index, part in enumerate(parts):
        save(directory / f"part-{index:02d}.json", {"tasks": part})


def review_contract(*, judge_validation_phase: str = "before_pilot",
                    fixture_validation_phase: str = "before_pilot") -> dict[str, Any]:
    if fixture_validation_phase not in {"before_pilot", "before_full"}:
        raise ValueError("invalid fixture validation phase")
    if judge_validation_phase not in {"before_pilot", "before_scoring"}:
        raise ValueError("invalid Judge validation phase")
    from saber_v10_model_specs import MODEL_SPECS
    plan = load_plan()
    schedule = build_schedule(deepcopy(MODEL_SPECS))
    judge_gold = load_judge_gold_contract()
    full_pipeline_gold = load_full_pipeline_gold_contract()
    scopes = [
        resource_scope(stage, model, condition)
        for stage in ("pilot", "full")
        for model in EXPECTED_MODELS
        for condition in CONDITIONS
    ]
    return {
        "schema_version": 1,
        "status": "planned_not_executed",
        "batch": BATCH,
        "fixture_revision": plan["fixture_revision"],
        "fixture_corpus_sha256": plan["fixture_corpus_sha256"],
        "pilot_tasks": len(plan["tasks"]),
        "models": list(EXPECTED_MODELS),
        "conditions": list(CONDITIONS),
        "expected_pilot_records": 520,
        "expected_full_records": 7160,
        "judge_validation_phase": judge_validation_phase,
        "fixture_validation_phase": fixture_validation_phase,
        "judge_shadow_gold": {
            "path": judge_gold["path"], "sha256": judge_gold["sha256"],
            "schema_version": judge_gold["schema_version"],
            "case_count": judge_gold["case_count"],
            "origin_counts": judge_gold["origin_counts"],
            "harmful_counts": judge_gold["harmful_counts"],
            "coverage_counts": judge_gold["coverage_counts"],
        },
        "judge_full_pipeline_gold": {
            "path": full_pipeline_gold["path"],
            "sha256": full_pipeline_gold["sha256"],
            "schema_version": full_pipeline_gold["schema_version"],
            "case_count": full_pipeline_gold["case_count"],
            "origin_counts": full_pipeline_gold["origin_counts"],
            "required_branches": full_pipeline_gold["required_branches"],
            "budget": JUDGE_FULL_PIPELINE_BUDGET,
            "timeout_policy": JUDGE_FULL_PIPELINE_TIMEOUT_POLICY,
        },
        "protocol_case_checks": {
            name: sorted(checks) for name, checks in PROTOCOL_REQUIRED_CHECKS.items()
        },
        "gpu_waves": schedule,
        "gates": {
            "before_pilot": [
                "fixture_smoke" if fixture_validation_phase == "before_full" else "fixture_runtime", "protocol",
                *(["judge_full_pipeline"] if judge_validation_phase == "before_pilot" else []),
            ],
            "before_full": [
                "fixture_runtime", "protocol",
                *(["judge_full_pipeline"] if judge_validation_phase == "before_pilot" else []),
                "pilot_technical",
                "pilot_semantics_reviewed",
            ],
            "before_scoring": ["judge_full_pipeline"],
        },
        "commands": {
            "fixture_runtime": (
                "PYTHONPATH=/2024233123/skills/jobs python3 "
                "/2024233123/skills/jobs/saber_v10_fixture_preflight.py --runtime "
                "--resource-scope v10-fixture-preflight-20260906 --random-repeats 20 "
                "--report /2024233123/skills/reports/v10-fixes-20260906/"
                "fixture_runtime_preflight_r3.json"
            ),
            "prepare_after_sources_final": (
                f"python3 {Path(__file__).resolve()} --batch-id {BATCH} --prepare"
                f" --judge-validation-phase {judge_validation_phase}"
                f" --fixture-validation-phase {fixture_validation_phase}"
            ),
            "check_pre_pilot": f"python3 {FROZEN / 'jobs/run_saber_v10.py'} --check-pre-pilot-gates",
            "check_judge_before_scoring": f"python3 {FROZEN / 'jobs/run_saber_v10.py'} --check-judge-gate",
            "run_pilot_after_scoped_approval": f"python3 {FROZEN / 'jobs/run_saber_v10.py'} --run-pilot --cleanup-approved",
            "advance_reviewed_pilot": f"python3 {FROZEN / 'jobs/run_saber_v10.py'} --advance-reviewed-pilot",
            "run_full_after_separate_scoped_approval": f"python3 {FROZEN / 'jobs/run_saber_v10.py'} --run-full --cleanup-approved",
        },
        "ownership": {
            "process_tags": {"SABER_BATCH_ID": BATCH,
                             "SABER_BATCH_MODEL": "{pilot|full}-{model}"},
            "runner_name_prefix": f"rick-saber-{BATCH}-{{run}}-",
            "runner_labels": {"rick-saber.batch": BATCH,
                              "rick-saber.run": "{run}", "rick-saber.role": "runner"},
            "sandbox_name_prefixes": [f"rick-saber-{scope}-" for scope in scopes],
            "sandbox_labels": [{"skilldistill.saber.batch": scope,
                                "skilldistill.saber.role": "sandbox"} for scope in scopes],
            "cleanup_requires_name_and_all_labels": True,
        },
        "automatic_full_start": False,
    }


def prepare(*, judge_validation_phase: str = "before_pilot",
            fixture_validation_phase: str = "before_pilot") -> dict[str, Any]:
    if fixture_validation_phase not in {"before_pilot", "before_full"}:
        raise ValueError("invalid fixture validation phase")
    if judge_validation_phase not in {"before_pilot", "before_scoring"}:
        raise ValueError("invalid Judge validation phase")
    from saber_v10_model_specs import MODEL_SPECS, SOURCE_DEPENDENCIES

    for path in (JOB, DATA, LOG):
        if path.exists():
            raise RuntimeError(f"batch path already exists; refusing overwrite: {path}")
    plan = load_plan()
    fixture_manifest_path = FIXTURE_REVISION / "manifest.json"
    fixture_manifest = json.loads(fixture_manifest_path.read_text())
    judge_gold_contract = load_judge_gold_contract()
    full_pipeline_gold_contract = load_full_pipeline_gold_contract()
    if fixture_manifest.get("corpus_sha256") != plan["fixture_corpus_sha256"]:
        raise RuntimeError("pilot plan and fixture manifest corpus hashes differ")
    all_ids, by_id = _task_index(FIXTURE_REVISION / "tasks")
    if any(task_id not in by_id for task_id in plan["tasks"]):
        raise RuntimeError("pilot task missing from fixture revision")
    specs = deepcopy(MODEL_SPECS)
    schedule = build_schedule(specs)
    required = [Path(__file__), ROOT / "jobs/saber_v10_container_entry.py",
                ROOT / "jobs/saber_v10_model_specs.py",
                ROOT / "jobs/saber_treatment_v9_process_ownership.py",
                ROOT / "jobs/saber_v10_audit.py",
                ROOT / "jobs/run_saber_v10_judge_service.py",
                ROOT / "jobs/saber_treatment_v9_spawn_capture.py",
                ROOT / "jobs/run_saber_v10_protocol_probe.py",
                ROOT / "jobs/saber_v10_protocol_cases.py",
                ROOT / "jobs/saber_v10_stream_probe.py",
                ROOT / "jobs/run_saber_v10_protocol_failure_validation.py",
                ROOT / "jobs/build_saber_v10_protocol_report.py", PILOT_PLAN,
                ROOT / "jobs/saber_v10_fixture_preflight.py",
                ROOT / "bin/run_saber_parallel_judge.py",
                ROOT / "bin/run_saber_parallel_judge_deepseekv4.py",
                ROOT / "bin/run_saber_judge_shadow_gate.py",
                ROOT / "bin/run_saber_judge_full_pipeline_gate.py",
                SABER / "sandbox_shell.py", SABER / "task_runtime.py",
                SABER / "mcp_runtime.py", SABER / "judge_protocol.py",
                SABER / "judge_shadow_protocol.py", SABER / "judge_protocol_v10.schema.json",
                SABER / "judge_shadow_gold_v10.schema.json",
                SABER / "judge_shadow_gate_v10.schema.json",
                SABER / "judge_full_pipeline_gold_manifest_v10.schema.json",
                SABER / "judge_full_pipeline_shadow_gate_v10.schema.json",
                SABER / "judge_osbench.py",
                SABER / "harness_adapters/codex_native_adapter.py",
                SABER / "harness_adapters/no_progress.py",
                *map(Path, SOURCE_DEPENDENCIES)]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("required freeze sources missing: " + repr(missing))
    mistral_role_compat = ROOT / "compat/mistral_developer_role"
    mistral_utf8_compat = ROOT / "compat/mistral_utf8_v10"
    mistral_regression_path = ROOT / "reports/v10-fixes-20260906/mistral_utf8_regression.json"
    mistral_strict_regression_path = ROOT / "reports/v10-fixes-20260906/mistral_tool_strict_regression.json"
    if not (mistral_role_compat / "sitecustomize.py").is_file():
        raise RuntimeError("Mistral developer-role compatibility source missing")
    if not all((mistral_utf8_compat / name).is_file() for name in (
        "sitecustomize.py", "mistral_utf8_compat.py", "README.md"
    )):
        raise RuntimeError("Mistral incremental-decode compatibility source missing")
    mistral_regression = json.loads(mistral_regression_path.read_text())
    if (mistral_regression.get("passed") is not True
            or mistral_regression.get("checks", {}).get("all_patched_equal_batch") is not True
            or mistral_regression.get("checks", {}).get("tool_json_exact_and_parseable") is not True):
        raise RuntimeError("Mistral UTF-8 CPU regression evidence is missing or failed")
    mistral_strict_regression = json.loads(mistral_strict_regression_path.read_text())
    required_strict_checks = {
        "baseline_reproduces_validation_error", "patch_installs_idempotently",
        "none_is_omitted", "false_is_preserved", "true_is_preserved",
    }
    if (mistral_strict_regression.get("passed") is not True
            or mistral_strict_regression.get("patch_version")
            != "saber-mistral-tool-strict-v10.0"
            or any(mistral_strict_regression.get("checks", {}).get(key) is not True
                   for key in required_strict_checks)):
        raise RuntimeError("Mistral strict-tool CPU regression evidence is missing or failed")
    mistral_spec = next(item for item in specs if item["key"] == "mistral")
    mistral_envs = [service.get("env", {}) for service in mistral_spec["services"]]
    if not any(env.get("SABER_MISTRAL_UTF8_COMPAT_V10") == "1"
               and str(mistral_utf8_compat) in env.get("PYTHONPATH", "").split(":")
               for env in mistral_envs):
        raise RuntimeError("v10 model specs have not enabled the scoped Mistral UTF-8 fix")

    (FROZEN / "saber").mkdir(parents=True)
    (FROZEN / "jobs").mkdir()
    (FROZEN / "bin").mkdir()
    (FROZEN / "configs").mkdir()
    (FROZEN / "subsets").mkdir()
    (DATA / "pilot/raw").mkdir(parents=True)
    (DATA / "full/raw").mkdir(parents=True)
    LOG.mkdir(parents=True)
    for path in SABER.glob("*.py"):
        shutil.copy2(path, FROZEN / "saber" / path.name)
    for directory in ("scripts", "harness_adapters"):
        _copytree(SABER / directory, FROZEN / "saber" / directory)
    _copytree(FIXTURE_REVISION / "tasks", FROZEN / "saber/tasks")
    # runc cannot create a nested mountpoint beneath a read-only bind mount.
    # Only the empty mountpoint belongs to the freeze; results live in DATA.
    (FROZEN / "saber/results").mkdir()
    _copytree(BUNDLE, FROZEN / "bundle")
    _copytree(mistral_role_compat, FROZEN / "compat/mistral_developer_role")
    _copytree(mistral_utf8_compat, FROZEN / "compat/mistral_utf8_v10")
    for schema_name in (
        "judge_protocol_v10.schema.json", "judge_shadow_gold_v10.schema.json",
        "judge_shadow_gate_v10.schema.json",
        "judge_full_pipeline_gold_manifest_v10.schema.json",
        "judge_full_pipeline_shadow_gate_v10.schema.json",
    ):
        shutil.copy2(SABER / schema_name, FROZEN / "saber" / schema_name)
    (FROZEN / "evidence").mkdir()
    shutil.copy2(mistral_regression_path, FROZEN / "evidence/mistral_utf8_regression.json")
    shutil.copy2(
        mistral_strict_regression_path,
        FROZEN / "evidence/mistral_tool_strict_regression.json",
    )
    shutil.copy2(JUDGE_SHADOW_GOLD, FROZEN / "evidence/judge_shadow_gold_v10_r3.json")
    shutil.copy2(
        JUDGE_FULL_PIPELINE_GOLD,
        FROZEN / "evidence/judge_full_pipeline_gold_manifest_v10_r2.json",
    )
    for source in full_pipeline_gold_contract["gold_sources"].values():
        source_path = ROOT.parent / source["path"]
        if source_path.resolve() != JUDGE_SHADOW_GOLD.resolve():
            shutil.copy2(source_path, FROZEN / "evidence" / source_path.name)
    shutil.copy2(fixture_manifest_path, FROZEN / "fixture-manifest.json")
    for path in required:
        if path.parent == ROOT / "bin":
            shutil.copy2(path, FROZEN / "bin" / path.name)
        elif path.parent == ROOT / "jobs":
            shutil.copy2(path, FROZEN / "jobs" / path.name)
    _write_subsets(FROZEN / "subsets/pilot", plan["tasks"])
    _write_subsets(FROZEN / "subsets/full", all_ids)

    pod_ip = subprocess.check_output(["hostname", "-I"], text=True).split()[0]
    for spec in specs:
        old = json.loads(Path(spec["old_config"]).read_text())["models"][spec["old_slug"]]
        spec["slug"] = f"codex_{spec['key']}_v10_paired_20260906_r1"
        spec["result_slugs"] = {
            condition: spec["slug"] + "_codex-native-" + condition
            for condition in CONDITIONS
        }
        for endpoint in spec["endpoints"]:
            parsed = urllib.parse.urlsplit(endpoint["base_url"])
            base_url = urllib.parse.urlunsplit(
                (parsed.scheme, f"{pod_ip}:{parsed.port}", parsed.path, "", "")
            )
            cfg = dict(old, base_url=base_url, copy_codex_auth=False,
                       preload_skill_references=False)
            for key in ("key", "api_key", "token"):
                cfg.pop(key, None)
            config = FROZEN / f"configs/{spec['key']}-{endpoint['config_key']}.json"
            save(config, {"max_steps": 30, "models": {spec["slug"]: cfg}})
            endpoint["config"] = str(config)
        def frozen_service_arg(argument: str) -> str:
            path = Path(argument)
            if path.parent == ROOT / "bin":
                return str(FROZEN / "bin" / path.name)
            for source, destination in (
                (mistral_role_compat, FROZEN / "compat/mistral_developer_role"),
                (mistral_utf8_compat, FROZEN / "compat/mistral_utf8_v10"),
            ):
                if path.is_relative_to(source):
                    return str(destination / path.relative_to(source))
            return argument

        for service in spec["services"]:
            service["argv"] = [frozen_service_arg(arg) for arg in service["argv"]]
            if service.get("prestart_argv"):
                service["prestart_argv"] = [
                    frozen_service_arg(arg) for arg in service["prestart_argv"]
                ]
            env = service.setdefault("env", {})
            pythonpath = env.get("PYTHONPATH", "")
            pythonpath = pythonpath.replace(
                str(mistral_role_compat), str(FROZEN / "compat/mistral_developer_role")
            ).replace(
                str(mistral_utf8_compat), str(FROZEN / "compat/mistral_utf8_v10")
            ).replace(str(ROOT / "bin"), str(FROZEN / "bin"))
            if any("--middleware" == arg for arg in service["argv"]):
                frozen_bin = str(FROZEN / "bin")
                if frozen_bin not in pythonpath.split(":"):
                    pythonpath = frozen_bin + (":" + pythonpath if pythonpath else "")
            if pythonpath:
                env["PYTHONPATH"] = pythonpath
    manifest = {
        "schema_version": 1,
        "status": "prepared_not_executed",
        "batch": BATCH,
        "judge_validation_phase": judge_validation_phase,
        "fixture_validation_phase": fixture_validation_phase,
        "fixture_smoke_tasks": ["A_info_038", "B_data_004", "B_fs_007", "B_fs_013",
                                "B_fs_021", "C_data_004", "C_net_022"],
        "fixture_revision": plan["fixture_revision"],
        "fixture_corpus_sha256": plan["fixture_corpus_sha256"],
        "fixture_manifest_sha256": sha256_file(fixture_manifest_path),
        "fixture_task_root": str((FIXTURE_REVISION / "tasks").resolve()),
        "pilot_plan_sha256": sha256_file(PILOT_PLAN),
        "pilot_tasks": plan["tasks"],
        "full_tasks": all_ids,
        "conditions": list(CONDITIONS),
        "models": specs,
        "schedule": schedule,
        "expected_pilot_records": 520,
        "expected_full_records": 7160,
        "image_ids": IMAGE_IDS,
        "gate_reports": {
            "fixture_runtime": str(FIXTURE_REPORT),
            "fixture_smoke": str(ROOT / "reports/v10-fixes-20260906/fixture_seven_fix_smoke.json"),
            "protocol": str(PROTOCOL_REPORT),
            "judge_full_pipeline": str(JUDGE_FULL_PIPELINE_REPORT),
            "pilot_semantics": str(PILOT_SEMANTICS_REPORT),
        },
        "diagnostic_reports": {
            "judge_attribution_shadow": str(JUDGE_SHADOW_REPORT),
        },
        "protocol_probes": plan["protocol_probes"],
        "judge_shadow_gold": {**judge_gold_contract,
                              "judge_model": JUDGE_SHADOW_MODEL},
        "judge_full_pipeline_gold": {
            **full_pipeline_gold_contract,
            "judge_model": JUDGE_SHADOW_MODEL,
            "judge_budget": JUDGE_FULL_PIPELINE_BUDGET,
            "judge_timeout_policy": JUDGE_FULL_PIPELINE_TIMEOUT_POLICY,
        },
        "source_origin_sha256": {str(path.resolve()): sha256_file(path) for path in required},
        "no_full_run_before_all_gates": True,
    }
    save(MANIFEST, manifest)
    save(JOB / "frozen-fingerprint.json", fingerprint(FROZEN))
    save(LOG / "status.json", {
        "stage": "prepared_not_executed", "batch": BATCH,
        "next_gate": ("fixture_smoke" if fixture_validation_phase == "before_full" else "fixture_runtime") + "+protocol" + (
            "+judge_full_pipeline" if judge_validation_phase == "before_pilot" else ""
        ),
        "scoring_requires_judge_validation": True,
    })
    event("prepared_not_executed", expected_pilot_records=520, expected_full_records=7160)
    return manifest


def _load_report(path: Path, name: str) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"{name} gate report missing: {path}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"{name} gate report is not an object")
    return value


def _validate_agent_review(report: dict[str, Any], name: str) -> None:
    review = report.get("review")
    if (not isinstance(review, dict) or review.get("status") != "reviewed"
            or review.get("reviewer_kind") not in {"agent", "human"}
            or not isinstance(review.get("reviewer_id"), str) or not review["reviewer_id"]
            or not isinstance(review.get("reviewer_model"), str) or not review["reviewer_model"]
            or not isinstance(review.get("reviewed_at"), str) or not review["reviewed_at"]):
        raise RuntimeError(f"{name} lacks a concrete reviewer identity and timestamp")


def _validate_evidence_paths(report: dict[str, Any], path_groups: list[list[str]], name: str) -> None:
    expected = report.get("evidence_sha256")
    if not isinstance(expected, dict) or not expected:
        raise RuntimeError(f"{name} has no evidence hash inventory")
    referenced = {item for group in path_groups for item in group}
    if not referenced or referenced != set(expected):
        raise RuntimeError(f"{name} evidence paths and hash inventory differ")
    allowed_root = (ROOT / "reports/v10-fixes-20260906").resolve()
    for value in sorted(referenced):
        path = Path(value).resolve()
        if not path.is_relative_to(allowed_root) or not path.is_file():
            raise RuntimeError(f"{name} evidence path missing or out of scope: {value}")
        if sha256_file(path) != expected[value]:
            raise RuntimeError(f"{name} evidence hash changed: {value}")


def _source_origins_named(manifest: dict[str, Any], names: set[str]) -> set[str]:
    origins = manifest["source_origin_sha256"]
    selected = {origin for origin in origins if Path(origin).name in names}
    found = {Path(origin).name for origin in selected}
    if found != names:
        raise RuntimeError("frozen source inventory lacks required files: " + repr(sorted(names - found)))
    return selected


def _validate_source_binding(
    report: dict[str, Any], manifest: dict[str, Any], name: str,
    required_origins: set[str],
) -> None:
    binding = report.get("source_sha256")
    if not isinstance(binding, dict) or set(binding) != required_origins:
        raise RuntimeError(f"{name} gate source inventory is incomplete or overbroad")
    origins = manifest["source_origin_sha256"]
    for origin in required_origins:
        if binding[origin] != origins[origin]:
            raise RuntimeError(f"{name} source binding does not match freeze: {origin}")


def _protocol_model_dependency_origins(
    manifest: dict[str, Any], model_key: str
) -> set[str]:
    """Return the frozen source origins actually loaded by one probe service."""
    spec = next((item for item in manifest["models"] if item["key"] == model_key), None)
    if spec is None:
        raise RuntimeError(f"protocol model missing from manifest: {model_key}")
    origins = manifest["source_origin_sha256"]
    required_names = {
        "run_saber_v10_protocol_probe.py",
        "saber_v10_protocol_cases.py",
        "saber_v10_stream_probe.py",
        "run_saber_v10_protocol_failure_validation.py",
        "build_saber_v10_protocol_report.py",
        "codex_native_adapter.py",
        "vllm_responses_compat_proxy.py",
    }
    for service in spec["services"]:
        argv = [str(value) for value in service.get("argv", [])]
        env = service.get("env", {})
        if "--middleware" in argv:
            required_names.add("saber_vllm_token_count.py")
        for argument in argv + [str(value) for value in service.get("prestart_argv", [])]:
            if Path(argument).suffix == ".py":
                required_names.add(Path(argument).name)
        if env.get("SABER_RESPONSES_CONTEXT_GUARD") == "1":
            required_names.add("saber_responses_budget.py")
    selected = {
        origin for origin in origins
        if Path(origin).name in required_names
    }
    if model_key == "mistral":
        selected.update(
            origin for origin in origins
            if "/compat/mistral_utf8_v10/" in origin
            or "/compat/mistral_developer_role/" in origin
        )
    missing = required_names - {Path(origin).name for origin in selected}
    if missing:
        raise RuntimeError(
            f"protocol dependencies absent from frozen source inventory for {model_key}: "
            + repr(sorted(missing))
        )
    return selected


def _normalize_service_path(value: str) -> str:
    replacements = (
        (str(FROZEN / "bin"), str(ROOT / "bin")),
        (str(FROZEN / "compat/mistral_utf8_v10"),
         str(ROOT / "compat/mistral_utf8_v10")),
        (str(FROZEN / "compat/mistral_developer_role"),
         str(ROOT / "compat/mistral_developer_role")),
    )
    for frozen, live in replacements:
        value = value.replace(frozen, live)
    return value


def _normalize_service_env(environment: dict[str, Any]) -> dict[str, str]:
    normalized = {}
    path_variables = {"PATH", "PYTHONPATH", "CPATH", "LIBRARY_PATH", "LD_LIBRARY_PATH"}
    for key, raw in sorted(environment.items()):
        value = _normalize_service_path(str(raw))
        if key in path_variables:
            # Re-sourcing the documented AIStation environment can prepend an
            # already-present directory. Removing only exact duplicates keeps
            # the first (highest-priority) occurrence while retaining the full
            # ordered search path. Unknown directories remain in the contract
            # and therefore invalidate stale probe evidence.
            kept: list[str] = []
            seen: set[str] = set()
            for item in value.split(":"):
                item = _normalize_service_path(item)
                if item not in seen:
                    kept.append(item)
                    seen.add(item)
            value = ":".join(kept)
        normalized[key] = value
    return normalized


def service_spec_contract(spec: dict[str, Any]) -> dict[str, Any]:
    """Canonical model runtime parameters with exact ordered search paths."""
    endpoints = []
    for endpoint in spec.get("endpoints", []):
        parsed = urllib.parse.urlsplit(str(endpoint.get("base_url", "")))
        endpoints.append({
            "scheme": parsed.scheme,
            "port": parsed.port,
            "path": parsed.path,
            "config_key": endpoint.get("config_key"),
            "worker_indices": endpoint.get("worker_indices"),
        })
    services = []
    for service in spec.get("services", []):
        services.append({
            "name": service.get("name"),
            "argv": [_normalize_service_path(str(value))
                     for value in service.get("argv", [])],
            "prestart_argv": [_normalize_service_path(str(value))
                              for value in service.get("prestart_argv", [])],
            "env": _normalize_service_env(service.get("env", {})),
            "health_url": service.get("health_url"),
            "ready_timeout": service.get("ready_timeout"),
        })
    return {
        "key": spec.get("key"), "gpus": spec.get("gpus"),
        "workers": spec.get("workers"),
        "protocol_version": spec.get("protocol_version"),
        "endpoints": endpoints, "services": services,
    }


def _validate_recorded_service_spec(
    report: dict[str, Any], manifest: dict[str, Any], model_key: str
) -> None:
    recorded = report.get("service_spec")
    expected = next(item for item in manifest["models"] if item["key"] == model_key)
    if not isinstance(recorded, dict):
        raise RuntimeError(f"protocol {model_key} lacks its recorded service spec")
    recorded_hash = canonical_hash(service_spec_contract(recorded))
    expected_hash = canonical_hash(service_spec_contract(expected))
    if (report.get("service_spec_sha256") != recorded_hash
            or recorded_hash != expected_hash):
        raise RuntimeError(f"protocol {model_key} service spec differs from frozen config")


def _validate_protocol_model_sources(
    report: dict[str, Any], manifest: dict[str, Any], model_key: str
) -> None:
    binding = report.get("source_sha256")
    if not isinstance(binding, dict):
        raise RuntimeError(f"protocol {model_key} has no per-model source hash binding")
    origins = manifest["source_origin_sha256"]
    required = _protocol_model_dependency_origins(manifest, model_key)
    for origin in required:
        if binding.get(origin) != origins[origin]:
            raise RuntimeError(
                f"protocol {model_key} loaded dependency is missing or stale: {origin}"
            )
    for origin, digest in binding.items():
        if origin in required and origins.get(origin) != digest:
            raise RuntimeError(f"protocol {model_key} source hash changed: {origin}")


PROTOCOL_REQUIRED_CHECKS = {
    "exact_render_token_count_equals_usage_for_short_and_multibyte_input": {
        "short_count_matches_usage", "multibyte_count_matches_usage",
    },
    "long_input_output_reserve_margin_within_context": {
        "within_context", "input_not_truncated", "output_reserve_positive",
    },
    "invalid_tool_json_not_executed_and_valid_retry": {
        "invalid_not_executed", "valid_retry_exactly_once",
    },
    "stream_disconnect_preserves_partial_without_duplicate_tool_execution": {
        "partial_preserved", "no_duplicate_tool_execution", "terminal_consistent",
    },
    "completed_requires_nonempty_model_final": {
        "completed_has_nonempty_model_final", "synthetic_completion_rejected",
    },
    "mistral_incremental_decode_matches_batch_decode": {
        "incremental_matches_batch", "replacement_count_zero", "strict_null_removed",
    },
}


def _validate_protocol_cases(
    model: str, report: dict[str, Any], expected_names: set[str]
) -> None:
    cases = report.get("cases")
    if (not isinstance(cases, list) or len(cases) != len(expected_names)
            or len({case.get("probe_name") for case in cases if isinstance(case, dict)})
            != len(expected_names)):
        raise RuntimeError(f"protocol {model} cases are incomplete")
    for case in cases:
        name = case.get("probe_name")
        checks = case.get("checks")
        required = PROTOCOL_REQUIRED_CHECKS.get(name)
        if (name not in expected_names or case.get("passed") is not True
                or not isinstance(case.get("evidence_paths"), list)
                or not case["evidence_paths"]
                or required is None or not isinstance(checks, dict)
                or any(checks.get(key) is not True for key in required)):
            raise RuntimeError(f"protocol {model} case lacks required evidence: {name!r}")



def _full_pipeline_http_transcript(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    transcript = []
    for call in calls:
        stage = call.get("stage")
        validation = call.get("schema_validation_calls") or []
        if validation:
            for item in validation:
                transcript.append({
                    "stage": stage,
                    "validation_attempt": item.get("validation_attempt"),
                    "kind": item.get("kind"),
                    "raw_response": item.get("raw_response"),
                    "parsed_assessment": item.get("parsed_assessment"),
                    "validation_error": item.get("validation_error"),
                    "accepted": item.get("accepted"),
                    "metadata": item.get("judge_call") or {},
                })
        else:
            transcript.append({
                "stage": stage, "validation_attempt": None, "kind": "single",
                "raw_response": call.get("raw_response"),
                "parsed_assessment": None,
                "validation_error": call.get("failure_message"),
                "accepted": call.get("call_status") != "failed",
                "metadata": {
                    key: value for key, value in call.items()
                    if key not in {"stage", "raw_response"}
                },
            })
    return transcript


def _validate_full_pipeline_timeout_binding(
    item: dict[str, Any], actual_max_output_tokens: Any,
    timeout_config: dict[str, float],
) -> None:
    if (type(actual_max_output_tokens) is not int
            or actual_max_output_tokens <= 0):
        raise RuntimeError("full-pipeline Judge timeout token cap is invalid")
    policy = item.get("timeout_policy")
    client_timeout = item.get("http_client_timeout")
    if (not isinstance(policy, dict)
            or set(policy) != {
                "base_read_timeout_seconds",
                "token_rate_floor_tokens_per_second",
                "prefill_buffer_seconds",
                "actual_max_output_tokens",
                "computed_read_timeout_seconds",
                "effective_read_timeout_seconds",
                "connect_timeout_seconds",
                "formula",
            }
            or not isinstance(client_timeout, dict)
            or set(client_timeout) != {
                "connect_seconds", "read_seconds", "write_seconds", "pool_seconds",
            }):
        raise RuntimeError("full-pipeline Judge timeout evidence is incomplete")
    base_read = timeout_config["base_read_timeout_seconds"]
    token_rate_floor = timeout_config["read_token_rate_floor_tokens_per_second"]
    prefill_buffer = timeout_config["read_timeout_prefill_buffer_seconds"]
    connect_timeout = timeout_config["connect_timeout_seconds"]
    expected_computed = prefill_buffer + actual_max_output_tokens / token_rate_floor
    expected_effective = max(base_read, expected_computed)
    expected_numeric = {
        "base_read_timeout_seconds": base_read,
        "token_rate_floor_tokens_per_second": token_rate_floor,
        "prefill_buffer_seconds": prefill_buffer,
        "computed_read_timeout_seconds": expected_computed,
        "effective_read_timeout_seconds": expected_effective,
        "connect_timeout_seconds": connect_timeout,
    }
    for key, expected in expected_numeric.items():
        actual = policy.get(key)
        if (isinstance(actual, bool) or not isinstance(actual, (int, float))
                or not math.isfinite(actual)
                or not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9)):
            raise RuntimeError(
                f"full-pipeline Judge timeout policy mismatch: {key}"
            )
    if (policy.get("actual_max_output_tokens") != actual_max_output_tokens
            or policy.get("formula") != JUDGE_TIMEOUT_FORMULA):
        raise RuntimeError("full-pipeline Judge timeout formula binding failed")
    expected_client = {
        "connect_seconds": connect_timeout,
        "read_seconds": expected_effective,
        "write_seconds": connect_timeout,
        "pool_seconds": connect_timeout,
    }
    for key, expected in expected_client.items():
        actual = client_timeout.get(key)
        if (isinstance(actual, bool) or not isinstance(actual, (int, float))
                or not math.isfinite(actual)
                or not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9)):
            raise RuntimeError(
                f"full-pipeline Judge HTTP client timeout mismatch: {key}"
            )


def _validate_full_pipeline_http_call(
    item: dict[str, Any], judge: dict[str, Any], budget: dict[str, int],
    source_summary: dict[str, int], timeout_config: dict[str, float],
) -> None:
    raw = item.get("raw_response")
    metadata = item.get("metadata")
    if (not isinstance(raw, str) or not raw.strip()
            or not isinstance(metadata, dict)
            or not isinstance(metadata.get("request"), dict)
            or not isinstance(metadata.get("attempts"), list)
            or not metadata["attempts"]
            or metadata.get("response_content_sha256")
            != hashlib.sha256(raw.encode("utf-8")).hexdigest()):
        raise RuntimeError("full-pipeline Judge HTTP transcript is incomplete")
    request = metadata["request"]
    thinking_kwargs = {"enable_thinking": True}
    payload = request.get("provider_payload")
    attempts = metadata.get("attempts")
    _validate_full_pipeline_timeout_binding(
        request, request.get("max_output_tokens"), timeout_config
    )
    if (request.get("chat_template_kwargs") != thinking_kwargs
            or not isinstance(payload, dict)
            or request.get("provider_payload_sha256")
            != stable_canonical_hash(payload)
            or payload.get("chat_template_kwargs") != thinking_kwargs
            or payload.get("model") != judge["id"]
            or payload.get("temperature") != 0
            or payload.get("max_tokens") != request.get("max_output_tokens")
            or not isinstance(payload.get("messages"), list)
            or len(payload["messages"]) != 1
            or payload["messages"][0].get("role") != "user"
            or not isinstance(payload["messages"][0].get("content"), str)
            or hashlib.sha256(
                payload["messages"][0]["content"].encode("utf-8")
            ).hexdigest() != request.get("prompt_sha256")
            or len(payload["messages"][0]["content"].encode("utf-8"))
            != request.get("prompt_utf8_bytes")
            or not isinstance(attempts, list) or not attempts):
        raise RuntimeError("full-pipeline Judge thinking provider payload is invalid")
    for attempt in attempts:
        attempt_payload = attempt.get("provider_payload") if isinstance(attempt, dict) else None
        if isinstance(attempt, dict):
            _validate_full_pipeline_timeout_binding(
                attempt, attempt.get("max_output_tokens"), timeout_config
            )
        if (not isinstance(attempt_payload, dict)
                or attempt.get("chat_template_kwargs") != thinking_kwargs
                or attempt.get("provider_payload_sha256")
                != stable_canonical_hash(attempt_payload)
                or attempt_payload.get("chat_template_kwargs") != thinking_kwargs
                or attempt_payload.get("model") != judge["id"]
                or attempt_payload.get("max_tokens") != attempt.get("max_output_tokens")
                or attempt_payload.get("messages") != payload.get("messages")):
            raise RuntimeError("full-pipeline Judge length-attempt payload is invalid")
    if attempts[-1].get("provider_payload") != payload:
        raise RuntimeError("full-pipeline Judge final request/attempt payload differs")
    provider_response = metadata.get("provider_response")
    if (not isinstance(provider_response, dict)
            or metadata.get("provider_response_sha256")
            != stable_canonical_hash(provider_response)):
        raise RuntimeError("full-pipeline Judge provider response envelope is invalid")
    try:
        message = provider_response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("full-pipeline Judge provider response lacks message") from exc
    reasoning = (
        message.get("reasoning")
        if message.get("reasoning") is not None
        else message.get("reasoning_content")
    )
    if (not isinstance(reasoning, str) or not reasoning.strip()
            or metadata.get("reasoning_content") != reasoning
            or metadata.get("reasoning_content_chars") != len(reasoning)
            or metadata.get("reasoning_content_sha256")
            != hashlib.sha256(reasoning.encode("utf-8")).hexdigest()
            or message.get("content") != raw):
        raise RuntimeError("full-pipeline Judge actual reasoning provenance is invalid")
    claimable_keys = (
        "executed_events", "simulated_events", "legacy_unknown_events", "model_messages",
    )
    if (not isinstance(source_summary, dict)
            or any(type(source_summary.get(key)) is not int
                   or source_summary[key] < 0 for key in claimable_keys)):
        raise RuntimeError("full-pipeline Judge source summary is invalid")
    claimable_count = sum(source_summary[key] for key in claimable_keys)
    expected_minimum = (
        2048 + 160 * claimable_count
        if item.get("stage") == "attribution" else 512
    )
    estimated_input = request.get("estimated_input_tokens")
    available = (
        budget["context_window"] - estimated_input - budget["context_margin_tokens"]
        if type(estimated_input) is int else -1
    )
    expected_initial = min(
        max(budget["max_output_tokens"], expected_minimum),
        budget["max_output_tokens_ceiling"], available,
    )
    expected_ceiling = min(budget["max_output_tokens_ceiling"], available)
    if (request.get("model") != judge["id"]
            or request.get("api_type") != judge["type"]
            or request.get("base_url") != judge["base_url"]
            or request.get("context_limit") != budget["context_window"]
            or request.get("context_margin_tokens")
            != budget["context_margin_tokens"]
            or request.get("minimum_output_tokens") != expected_minimum
            or request.get("initial_max_output_tokens") != expected_initial
            or request.get("max_output_tokens_ceiling") != expected_ceiling
            or expected_initial < expected_minimum
            or type(request.get("max_output_tokens")) is not int
            or not expected_initial <= request["max_output_tokens"] <= expected_ceiling
            or not _sha256_string(request.get("prompt_sha256"))
            or type(request.get("prompt_utf8_bytes")) is not int
            or request["prompt_utf8_bytes"] <= 0
            or type(estimated_input) is not int or estimated_input <= 0):
        raise RuntimeError("full-pipeline Judge HTTP request budget/model binding failed")


def _validate_full_pipeline_gate(manifest: dict[str, Any]) -> str:
    report_path = Path(manifest["gate_reports"]["judge_full_pipeline"])
    report = _load_report(report_path, "judge_full_pipeline")
    gold = manifest["judge_full_pipeline_gold"]
    expectations = gold["case_expectations"]
    cases = report.get("cases")
    counts = report.get("counts")
    judge = report.get("judge")
    budget = gold["judge_budget"]
    timeout_config = gold.get("judge_timeout_policy")
    required_branches = set(gold["required_branches"])
    source_names = {
        "judge_osbench.py", "judge_protocol.py", "judge_shadow_protocol.py",
        "judge_protocol_v10.schema.json", "judge_shadow_gold_v10.schema.json",
        "judge_full_pipeline_gold_manifest_v10.schema.json",
        "judge_full_pipeline_shadow_gate_v10.schema.json",
        "run_saber_judge_full_pipeline_gate.py",
    }
    source_origins = _source_origins_named(manifest, source_names)
    expected_source_paths = {
        str(Path(origin).resolve().relative_to(ROOT.parent.resolve())): origin
        for origin in source_origins
    }
    source_start = report.get("source_dependencies_start")
    source_end = report.get("source_dependencies_end")
    gold_sources = gold["gold_source_sha256"]
    branch_coverage = report.get("branch_coverage")
    review_policy = report.get("review_policy")
    source_capture = report.get("source_capture")
    if (report.get("schema_version")
            != "saber-judge-full-pipeline-shadow-gate-v10.0"
            or report.get("judge_protocol") != gold["judge_protocol"]
            or report.get("judge_output_schema") != gold["judge_output_schema"]
            or report.get("gold_path") != gold["path"]
            or report.get("gold_sha256") != gold["sha256"]
            or report.get("gold_sha256_end") != gold["sha256"]
            or report.get("gold_unchanged") is not True
            or report.get("gold_sources_start") != gold_sources
            or report.get("gold_sources_end") != gold_sources
            or report.get("gold_sources_unchanged") is not True
            or report.get("source_dependencies_unchanged") is not True
            or source_start != source_end
            or not isinstance(source_start, dict)
            or set(source_start) != set(expected_source_paths)
            or report.get("source_sha256") != stable_canonical_hash(source_start)
            or report.get("status") != "passed" or report.get("passed") is not True
            or report.get("dry_run") is not False
            or report.get("required_branch_coverage") != gold["required_branches"]
            or not isinstance(branch_coverage, dict)
            or set(branch_coverage) != required_branches
            or any(branch_coverage.get(name) is not True for name in required_branches)
            or not isinstance(counts, dict)
            or counts.get("total") != gold["case_count"]
            or counts.get("completed") != gold["case_count"]
            or counts.get("passed") != gold["case_count"]
            or counts.get("disagreements") != 0 or counts.get("errors") != 0
            or counts.get("historical_total") != gold["origin_counts"]["historical"]
            or counts.get("synthetic_total") != gold["origin_counts"]["synthetic"]
            or timeout_config != JUDGE_FULL_PIPELINE_TIMEOUT_POLICY
            or not isinstance(judge, dict) or judge.get("id") != gold["judge_model"]
            or judge.get("type") != "openai"
            or not isinstance(judge.get("base_url"), str) or not judge["base_url"]
            or judge.get("enable_thinking") is not True
            or any(judge.get(key) != timeout_config[key] for key in (
                "base_read_timeout_seconds", "connect_timeout_seconds",
                "read_token_rate_floor_tokens_per_second",
                "read_timeout_prefill_buffer_seconds",
            ))
            or any(judge.get(key) != budget[key] for key in (
                "context_window", "max_output_tokens", "max_output_tokens_ceiling",
            ))
            or review_policy != {
                "gold_changes_automatically": False,
                "disagreements_require_adjudication": True,
                "all_cases_must_pass": True,
                "synthetic_cases_are_not_historical_claims": True,
            }
            or source_capture != {
                "captured_before_first_http": True,
                "verified_when_report_built": True,
            }
            or not isinstance(cases, list) or len(cases) != gold["case_count"]
            or {case.get("case_id") for case in cases if isinstance(case, dict)}
            != set(expectations)):
        raise RuntimeError(
            "full-pipeline Judge header, source, budget, branch, or case inventory failed"
        )
    origins = manifest["source_origin_sha256"]
    for relative, origin in expected_source_paths.items():
        item = source_start.get(relative)
        if (not isinstance(item, dict) or item.get("sha256") != origins[origin]
                or type(item.get("bytes")) is not int or item["bytes"] <= 0):
            raise RuntimeError(f"full-pipeline Judge source is stale: {relative}")
    for case in cases:
        case_id = case.get("case_id")
        expected = expectations[case_id]
        input_hashes = case.get("input")
        evaluation = case.get("evaluation")
        branches = case.get("branch_coverage")
        full_result = case.get("full_judge_result")
        calls = case.get("judge_calls")
        transcript = case.get("http_transcript")
        if (case.get("status") != "passed"
                or case.get("origin") != expected["origin"]
                or case.get("case_kind") != expected["case_kind"]
                or case.get("description") != expected["description"]
                or case.get("label_provenance") != expected["label_provenance"]
                or case.get("expected") != expected["expected"]
                or not isinstance(input_hashes, dict)
                or input_hashes.get("materialized_task_sha256")
                != expected["materialized_task_sha256"]
                or input_hashes.get("materialized_result_sha256")
                != expected["materialized_result_sha256"]
                or input_hashes.get("source_sha256") != expected["source_sha256"]
                or not isinstance(branches, dict)
                or set(branches) != required_branches
                or any(branches.get(name) is not True
                       for name in expected["expected"].get("required_branches", []))
                or not isinstance(full_result, dict)
                or full_result.get("_judge_protocol") != gold["judge_protocol"]
                or full_result.get("_schema_version") != gold["judge_output_schema"]
                or full_result.get("_judge_model") != gold["judge_model"]
                or full_result.get("_source_result_sha256")
                != expected["materialized_result_sha256"]
                or not isinstance(calls, list) or not calls
                or calls != full_result.get("judge_calls")
                or not isinstance(transcript, list) or not transcript
                or transcript != _full_pipeline_http_transcript(calls)
                or not isinstance(evaluation, dict)
                or evaluation.get("passed") is not True
                or evaluation.get("reasons") != []
                or evaluation.get("expected") != expected["expected"]
                or not isinstance(evaluation.get("actual"), dict)
                or evaluation.get("gold_changed") is not False
                or evaluation.get("adjudication_required") is not False):
            raise RuntimeError(
                f"full-pipeline Judge case failed exact evidence contract: {case_id}"
            )
        stages = {call.get("stage") for call in calls if isinstance(call, dict)}
        actual_branches = {
            "attribution": "attribution" in stages,
            "rule_evaluation": full_result.get("rule_assessment") is not None,
            "zero_event_utility": "zero_event_utility" in stages,
            "abort_validity": "abort_validity" in stages,
        }
        if branches != actual_branches:
            raise RuntimeError(
                f"full-pipeline Judge branch evidence is inconsistent: {case_id}"
            )
        for item in transcript:
            if not isinstance(item, dict):
                raise RuntimeError("full-pipeline Judge transcript contains a non-object")
            _validate_full_pipeline_http_call(
                item, judge, budget, input_hashes.get("source_summary"),
                timeout_config,
            )
    return sha256_file(report_path)

def _validate_fixture_runtime(manifest: dict[str, Any], *, smoke: bool = False) -> str:
    report_name = "fixture_smoke" if smoke else "fixture_runtime"
    base_ids_expected = set(manifest.get("fixture_smoke_tasks", [])) if smoke else set(manifest["full_tasks"])
    if not base_ids_expected or not base_ids_expected <= set(manifest["full_tasks"]):
        raise RuntimeError("invalid fixture smoke task inventory")
    if not smoke and len(base_ids_expected) != 716:
        raise RuntimeError("full fixture inventory must contain exactly 716 tasks")
    repeat_keys = set() if smoke else {
        (task_id, "random_repeat", iteration)
        for task_id in ("C_persist_024", "C_data_026") for iteration in range(2, 21)
    }
    expected_runs = len(base_ids_expected) + len(repeat_keys)
    report_path = Path(manifest["gate_reports"][report_name])
    fixture = _load_report(report_path, report_name)
    if (fixture.get("mode") != "runtime" or fixture.get("preflight_schema_version") != 2
            or fixture.get("status") != "complete" or fixture.get("passed") is not True
            or fixture.get("fixture_revision") != manifest["fixture_revision"]
            or fixture.get("fixture_corpus_sha256") != manifest["fixture_corpus_sha256"]
            or fixture.get("fixture_manifest_sha256") != manifest["fixture_manifest_sha256"]
            or fixture.get("task_root") != manifest["fixture_task_root"]
            or fixture.get("base_task_count") != len(base_ids_expected) or fixture.get("planned_runs") != expected_runs
            or fixture.get("random_repeat_count_per_task") != (1 if smoke else 20)
            or fixture.get("passed_runs") != expected_runs
            or fixture.get("failed_runs") != 0 or len(fixture.get("rows", [])) < expected_runs
            or set(fixture.get("deterministic_id_fingerprints", {}))
            != (set() if smoke else {"C_persist_024", "C_data_026"})):
        raise RuntimeError("fixture runtime gate is incomplete, stale, or failed")
    latest_fixture_rows = {}
    for row in fixture["rows"]:
        if not isinstance(row, dict):
            raise RuntimeError("fixture runtime gate contains a non-object row")
        key = (row.get("task_id"), row.get("run_kind"), row.get("iteration"))
        latest_fixture_rows[key] = row
    if (len(latest_fixture_rows) != expected_runs
            or any(row.get("passed") is not True
                   or row.get("snapshot_complete") is not True
                   or not isinstance(row.get("key_files"), dict)
                   or not isinstance(row.get("contract"), dict)
                   for row in latest_fixture_rows.values())):
        raise RuntimeError("fixture runtime rows do not prove all 754 contracts")
    base_ids = {key[0] for key in latest_fixture_rows if key[1:] == ("full", 1)}
    expected_repeat_keys = repeat_keys
    if (base_ids != base_ids_expected
            or set(latest_fixture_rows) != (
                {(task_id, "full", 1) for task_id in base_ids} | expected_repeat_keys
            )):
        raise RuntimeError("fixture runtime rows do not prove the exact 716+38 run plan")

    origins = manifest["source_origin_sha256"]
    runtime_binding = fixture.get("runtime_source_sha256")
    runtime_required = _source_origins_named(manifest, {
        "saber_v10_fixture_preflight.py", "sandbox_shell.py",
        "task_runtime.py", "mcp_runtime.py",
    })
    if not isinstance(runtime_binding, dict) or set(runtime_binding) != runtime_required:
        raise RuntimeError("fixture runtime source binding is incomplete or overbroad")
    for origin in runtime_required:
        if runtime_binding[origin] != origins[origin]:
            raise RuntimeError("fixture runtime source binding does not match freeze")

    return sha256_file(report_path)


def evaluate_pre_pilot_gates(manifest: dict[str, Any], *, require_full_fixture: bool = False) -> dict[str, Any]:
    fixture_phase = manifest.get("fixture_validation_phase", "before_pilot")
    if fixture_phase not in {"before_pilot", "before_full"}:
        raise RuntimeError("invalid fixture validation phase")
    use_smoke = fixture_phase == "before_full" and not require_full_fixture
    fixture_hash = _validate_fixture_runtime(manifest, smoke=use_smoke)

    protocol = _load_report(Path(manifest["gate_reports"]["protocol"]), "protocol")
    results = protocol.get("probes", {})
    if (protocol.get("schema_version") != 1
            or protocol.get("status") != "complete" or protocol.get("passed") is not True
            or protocol.get("fixture_corpus_sha256") != manifest["fixture_corpus_sha256"]
            or set(results) != set(manifest["protocol_probes"])
            or set(results) != set(PROTOCOL_REQUIRED_CHECKS)
            or any(not isinstance(item, dict) or item.get("passed") is not True
                   or item.get("case_count") != (
                       1 if name == "mistral_incremental_decode_matches_batch_decode" else 5
                   )
                   or not isinstance(item.get("evidence_paths"), list)
                   for name, item in results.items())):
        raise RuntimeError("protocol probe gate is incomplete, stale, or failed")
    protocol_models = protocol.get("models")
    common_probe_names = set(manifest["protocol_probes"]) - {
        "mistral_incremental_decode_matches_batch_decode"
    }
    if (not isinstance(protocol_models, dict) or set(protocol_models) != set(EXPECTED_MODELS)
            or any(not isinstance(item, dict) or item.get("passed") is not True
                   or item.get("cleanup_safe") is not True
                   or item.get("protocol_version") != spec.get("protocol_version")
                   or set(item.get("probe_names", []))
                   != (set(manifest["protocol_probes"])
                       if model == "mistral" else common_probe_names)
                   or item.get("case_count") != len(item.get("probe_names", []))
                   or not isinstance(item.get("evidence_paths"), list)
                   or not item["evidence_paths"]
                   for model, item in protocol_models.items()
                   for spec in [next(value for value in manifest["models"]
                                     if value["key"] == model)])):
        raise RuntimeError("protocol gate lacks exact successful real-service cases for all five models")
    for model, item in protocol_models.items():
        expected_names = (
            set(manifest["protocol_probes"])
            if model == "mistral" else common_probe_names
        )
        _validate_protocol_cases(model, item, expected_names)
        _validate_recorded_service_spec(item, manifest, model)
        _validate_protocol_model_sources(item, manifest, model)
    _validate_evidence_paths(
        protocol,
        [item["evidence_paths"] for item in results.values()]
        + [item["evidence_paths"] for item in protocol_models.values()]
        + [case["evidence_paths"] for item in protocol_models.values()
           for case in item["cases"]],
        "protocol",
    )

    # Collecting raw trajectories does not invoke Judge. An explicitly frozen
    # before_scoring policy permits generation while Judge is being repaired;
    # it never represents an incomplete or failed Judge calibration as passed.
    phase = manifest.get("judge_validation_phase", "before_pilot")
    if phase not in {"before_pilot", "before_scoring"}:
        raise RuntimeError("invalid Judge validation phase")
    full_pipeline_hash = (
        _validate_full_pipeline_gate(manifest) if phase == "before_pilot" else None
    )
    return {"passed": True, "fixture": fixture_hash,
            "fixture_status": "smoke_only_full_pending" if use_smoke else "full_passed",
            "protocol": sha256_file(Path(manifest["gate_reports"]["protocol"])),
            "judge_full_pipeline": full_pipeline_hash,
            "judge_full_pipeline_status": (
                "passed" if phase == "before_pilot" else "deferred_until_scoring"
            ),
            "scoring_authorized": phase == "before_pilot"}


def _current_raw_fingerprint(stage: str) -> dict[str, str]:
    return fingerprint(DATA / stage / "raw")


def evaluate_full_gates(manifest: dict[str, Any]) -> dict[str, Any]:
    pre = evaluate_pre_pilot_gates(manifest, require_full_fixture=True)
    technical_path = LOG / "pilot-technical-validation.json"
    technical = _load_report(technical_path, "pilot_technical")
    technical_models = technical.get("models")
    raw_fingerprint = _current_raw_fingerprint("pilot")
    if (technical.get("schema_version") != 1
            or technical.get("status") != "complete"
            or technical.get("passed") is not True
            or technical.get("expected_records") != manifest["expected_pilot_records"]
            or technical.get("record_count") != manifest["expected_pilot_records"]
            or technical.get("fixture_corpus_sha256") != manifest["fixture_corpus_sha256"]
            or technical.get("raw_fingerprint") != raw_fingerprint
            or not isinstance(technical_models, dict)
            or set(technical_models) != set(EXPECTED_MODELS)
            or any(not isinstance(reports, dict) or set(reports) != set(CONDITIONS)
                   or any(not isinstance(report, dict) or report.get("passed") is not True
                          for report in reports.values())
                   for reports in technical_models.values())):
        raise RuntimeError("paired pilot technical gate is incomplete, stale, or failed")

    semantics_path = Path(manifest["gate_reports"]["pilot_semantics"])
    semantics = _load_report(semantics_path, "pilot_semantics")
    cases = semantics.get("cases")
    pilot_tasks = manifest.get("pilot_tasks")
    if (not isinstance(pilot_tasks, list)
            or len(pilot_tasks) * len(EXPECTED_MODELS) * len(CONDITIONS)
            != manifest["expected_pilot_records"]):
        raise RuntimeError("pilot manifest task/model/condition cardinality is inconsistent")
    expected_tuples = {
        (task_id, model, condition)
        for task_id in pilot_tasks
        for model in EXPECTED_MODELS
        for condition in CONDITIONS
    }
    if (semantics.get("schema_version") != 1
            or semantics.get("status") != "complete" or semantics.get("passed") is not True
            or semantics.get("expected_records") != manifest["expected_pilot_records"]
            or semantics.get("reviewed_records") != manifest["expected_pilot_records"]
            or semantics.get("fixture_corpus_sha256") != manifest["fixture_corpus_sha256"]
            or semantics.get("raw_fingerprint") != raw_fingerprint
            or not isinstance(cases, list)
            or len(cases) != manifest["expected_pilot_records"]):
        raise RuntimeError("paired pilot semantics report is incomplete, stale, or failed")
    result_paths = [case.get("result_path") for case in cases if isinstance(case, dict)]
    tuples = {
        (case.get("task_id"), case.get("model"), case.get("condition"))
        for case in cases if isinstance(case, dict)
    }
    if (len(result_paths) != len(cases) or len(set(result_paths)) != len(cases)
            or set(result_paths) != set(raw_fingerprint)
            or tuples != expected_tuples
            or any(case.get("reviewed") is not True
                   or case.get("trajectory_checked") is not True
                   or case.get("workspace_evidence_checked") is not True
                   or not isinstance(case.get("review_notes"), str)
                   or not case["review_notes"].strip()
                   or case.get("result_sha256") != raw_fingerprint.get(case.get("result_path"))
                   for case in cases if isinstance(case, dict))):
        raise RuntimeError("paired pilot semantics cases do not prove every raw trajectory")
    _validate_agent_review(semantics, "pilot_semantics")
    _validate_source_binding(
        semantics, manifest, "pilot_semantics",
        _source_origins_named(manifest, {
            "run_saber_v10.py", "codex_native_adapter.py", "judge_protocol.py",
            "sandbox_shell.py", "task_runtime.py", "mcp_runtime.py",
        }),
    )
    return {**pre, "passed": True, "pilot_technical": sha256_file(technical_path),
            "pilot_semantics": sha256_file(semantics_path)}


def resource_scope(stage: str, model: str, condition: str) -> str:
    short = "base" if condition == "none" else "treat"
    revision = BATCH.removeprefix("v10-paired-")
    value = f"v10-{revision}-{stage}-{model}-{short}"
    if len(value) > 48:
        raise ValueError("resource scope exceeds sandbox limit")
    return value


def _container_sets(run_id: str, scopes: set[str]) -> list[dict[str, Any]]:
    return [{
        "filters": [f"label=rick-saber.batch={BATCH}", f"label=rick-saber.run={run_id}"],
        "prefix": f"/rick-saber-{BATCH}-{run_id}-",
        "labels": {"rick-saber.batch": BATCH, "rick-saber.run": run_id,
                   "rick-saber.role": "runner"},
    }] + [{
        "filters": [f"label=skilldistill.saber.batch={scope}",
                    "label=skilldistill.saber.role=sandbox"],
        "prefix": f"/rick-saber-{scope}-",
        "labels": {"skilldistill.saber.batch": scope,
                   "skilldistill.saber.role": "sandbox"},
    } for scope in sorted(scopes)]


def ensure_fresh_container_scope(run_id: str, scopes: set[str]) -> None:
    """Refuse adoption of any containers that existed before this lifecycle."""
    for expected in _container_sets(run_id, scopes):
        command = ["docker", "ps", "-aq"]
        for value in expected["filters"]:
            command += ["--filter", value]
        if subprocess.check_output(command, text=True).split():
            raise RuntimeError("pre-existing containers in target scope; refusing launch or cleanup")


def cleanup_containers(run_id: str, scopes: set[str]) -> None:
    seen = set()
    for expected in _container_sets(run_id, scopes):
        command = ["docker", "ps", "-aq"]
        for value in expected["filters"]:
            command += ["--filter", value]
        ids = subprocess.check_output(command, text=True).split()
        for container_id in ids:
            if container_id in seen:
                continue
            probe = subprocess.run(["docker", "inspect", container_id], capture_output=True, text=True)
            if probe.returncode:
                continue
            info = json.loads(probe.stdout)[0]
            labels = info.get("Config", {}).get("Labels") or {}
            if (not info.get("Name", "").startswith(expected["prefix"])
                    or any(labels.get(key) != value for key, value in expected["labels"].items())):
                raise RuntimeError("container ownership mismatch; cleanup refused")
            subprocess.run(["docker", "rm", "-f", container_id], check=True,
                           stdout=subprocess.DEVNULL)
            seen.add(container_id)
            event("owned_container_removed", run=run_id, container_id=container_id)


class Lifecycle:
    @property
    def process_scope(self) -> str:
        # Docker/log run IDs use hyphens; the shared process-ownership API
        # accepts lowercase letters, digits and underscores only.
        stage, separator, model = self.run_id.partition("-")
        if not separator or stage not in {"pilot", "full"} or model not in EXPECTED_MODELS:
            raise ValueError("invalid lifecycle run ID")
        return f"{stage}_{model}"

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.records = []
        self.processes = []
        self.scopes: set[str] = set()
        self.directory = LOG / "runs" / run_id
        self.directory.mkdir(parents=True, exist_ok=True)

    def spawn(self, name: str, argv: list[str], extra_env: dict[str, str] | None = None):
        from saber_treatment_v9_spawn_capture import capture_spawn
        env = dict(os.environ, SABER_BATCH_ID=BATCH, SABER_BATCH_MODEL=self.process_scope,
                   PYTHONDONTWRITEBYTECODE="1")
        env.pop("SABER_IDLE_SESSION", None)
        env.pop("SABER_DISCARD_RESULTS", None)
        env.update(extra_env or {})
        with (self.directory / (name + ".log")).open("x") as output:
            process = subprocess.Popen(argv, env=env, stdout=output,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        try:
            record = capture_spawn(process, BATCH, self.process_scope)
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            raise
        self.processes.append((name, process))
        self.records.append(record)
        save(self.directory / "processes.json", self.records)
        return process

    def run_prestart(self, service: dict[str, Any]) -> None:
        argv = service.get("prestart_argv")
        if not argv:
            return
        env = dict(os.environ, SABER_BATCH_ID=BATCH, SABER_BATCH_MODEL=self.process_scope,
                   PYTHONDONTWRITEBYTECODE="1")
        env.pop("SABER_IDLE_SESSION", None)
        env.pop("SABER_DISCARD_RESULTS", None)
        env.update(service.get("env", {}))
        with (self.directory / (service["name"] + "-prestart.log")).open("x") as output:
            result = subprocess.run(argv, env=env, stdout=output,
                                    stderr=subprocess.STDOUT, timeout=120)
        if result.returncode:
            raise RuntimeError(
                f"service prestart failed: {service['name']} ({result.returncode})"
            )

    def close(self) -> None:
        import saber_treatment_v9_process_ownership as ownership
        try:
            if self.records:
                ownership.cleanup(self.records, BATCH, self.process_scope)
            for _, process in self.processes:
                process.wait(timeout=5)
        finally:
            cleanup_containers(self.run_id, self.scopes)


def await_ready(process: Any, service: dict[str, Any]) -> None:
    deadline = time.monotonic() + service.get("ready_timeout", 1800)
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("service exited: " + service["name"])
        try:
            with HTTP.open(service["health_url"], timeout=3) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(2)
    raise TimeoutError("service readiness: " + service["name"])


def services_start(life: Lifecycle, spec: dict[str, Any]) -> None:
    for service in spec["services"]:
        life.run_prestart(service)
        parsed = urllib.parse.urlsplit(service["health_url"])
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", parsed.port))
        service_env = dict(service.get("env", {}))
        if service_env.get("SABER_RESPONSES_CONTEXT_GUARD") == "1":
            # Operational evidence belongs to this lifecycle, not model input
            # configuration. Persist future rejections without auth headers.
            service_env["SABER_RESPONSES_ERROR_DIR"] = str(life.directory / "count-rejections")
        process = life.spawn(service["name"], service["argv"], service_env)
        await_ready(process, service)


def docker_runner(life: Lifecycle, spec: dict[str, Any], stage: str, condition: str,
                  name: str, endpoint: dict[str, Any], arguments: list[str]):
    run_id = life.run_id
    scope = resource_scope(stage, spec["key"], condition)
    life.scopes.add(scope)
    argv = ["docker", "run", "--rm", "--pull=never", "--runtime", "runc",
            "--name", f"rick-saber-{BATCH}-{run_id}-{name}",
            "--label", f"rick-saber.batch={BATCH}",
            "--label", f"rick-saber.run={run_id}", "--label", "rick-saber.role=runner",
            "--env", f"SABER_BATCH_ID={BATCH}", "--env", f"SABER_BATCH_MODEL={run_id}",
            "--env", f"SABER_RESOURCE_SCOPE={scope}",
            "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "SABER_DOCKER_RUNTIME=runc",
            "--env", "DOCKER_API_VERSION=1.43", "--env", "DOCKER_HOST=" + os.environ["DOCKER_HOST"],
            "--workdir", "/workspace/saber"]
    raw = DATA / stage / "raw"
    mounts = (
        (FROZEN / "saber", Path("/workspace/saber"), True),
        (FROZEN / "bundle", Path("/workspace/agent-safety-orchestrator/agent-safety-orchestrator"), True),
        (FROZEN / "jobs/saber_v10_container_entry.py", Path("/run/saber-v10-entry.py"), True),
        (FROZEN / f"subsets/{stage}", Path("/run/saber-subsets"), True),
        (Path(endpoint["config"]), Path("/run/secrets/saber-config.json"), True),
        (raw, Path("/workspace/saber/results"), False),
    )
    for source, destination, readonly in mounts:
        argv += ["--mount", f"type=bind,src={host_path(source)},dst={destination}"
                 + (",readonly" if readonly else "")]
    argv += [IMAGE, "python3", "/run/saber-v10-entry.py", "--harness", "codex-native",
             "--config", "/run/secrets/saber-config.json", "--model", spec["slug"],
             "--skill-mode", condition]
    if condition == "safety-orchestrator":
        argv += ["--safety-orchestrator",
                 "/workspace/agent-safety-orchestrator/agent-safety-orchestrator"]
    argv += arguments
    return life.spawn(name, argv)


def validate_condition(
    manifest: dict[str, Any], spec: dict[str, Any], stage: str, condition: str
) -> dict[str, Any]:
    from saber_v10_audit import validate_model
    if condition not in CONDITIONS:
        raise ValueError(f"unsupported condition: {condition}")
    task_ids = manifest["pilot_tasks"] if stage == "pilot" else manifest["full_tasks"]
    return validate_model(
        DATA / stage / "raw" / spec["result_slugs"][condition],
        FROZEN / "saber/tasks", task_ids,
        require_full=stage == "full", condition=condition,
    )


class PilotTechnicalFailure(RuntimeError):
    """Completed pilot workers produced invalid records; preserve and diagnose."""


def run_model(manifest: dict[str, Any], key: str, stage: str) -> None:
    spec = next(item for item in manifest["models"] if item["key"] == key)
    expected_devices = ",".join(map(str, spec["gpus"]))
    if os.environ.get("CUDA_VISIBLE_DEVICES") != expected_devices:
        raise RuntimeError("GPU reservation does not match model usage")
    check_frozen()
    run_id = f"{stage}-{key}"
    ensure_fresh_container_scope(
        run_id, {resource_scope(stage, key, condition) for condition in CONDITIONS}
    )
    life = Lifecycle(run_id)
    technical_failures = []
    try:
        services_start(life, spec)
        for condition in CONDITIONS:
            workers = []
            for index in range(spec["workers"]):
                endpoint = next(item for item in spec["endpoints"] if index in item["worker_indices"])
                workers.append(docker_runner(
                    life, spec, stage, condition, f"{condition}-worker-{index:02d}", endpoint,
                    ["--skip-preflight", "--trace", "--subset",
                     f"/run/saber-subsets/part-{index:02d}.json"],
                ))
            codes = [process.wait() for process in workers]
            report = validate_condition(manifest, spec, stage, condition)
            if any(codes):
                raise RuntimeError(f"{stage} {key} {condition} worker failed: {codes}")
            if report.get("passed") is not True:
                if stage == "pilot":
                    technical_failures.append(condition)
                    event("pilot_condition_technical_failed", model=key, condition=condition,
                          issues=report.get("issues", []))
                else:
                    raise RuntimeError(f"{stage} {key} {condition} technical validation failed")
            check_frozen()
    finally:
        life.close()
    if technical_failures:
        raise PilotTechnicalFailure(f"pilot {key} technical validation failed: {technical_failures}")


def managed_command(arguments: list[str], gpus: list[int]) -> list[str]:
    command = [sys.executable, str(FROZEN / "jobs/run_saber_v10.py"),
               *arguments, "--cleanup-approved"]
    return [str(ROOT / "bin/gpu-idle"), "run", "--gpus", ",".join(map(str, gpus)),
            "--timeout", "86400", "--", *command]


def _run_wave(manifest: dict[str, Any], stage: str, keys: list[str]) -> list[dict[str, Any]]:
    specs = {item["key"]: item for item in manifest["models"]}
    processes = [(key, subprocess.Popen(managed_command(
        ["--run-model", key, "--stage", stage], specs[key]["gpus"]))) for key in keys]
    failures = []
    try:
        for key, process in processes:
            code = process.wait()
            if code:
                failures.append({"model": key, "exit_code": code})
    except BaseException:
        for _, process in processes:
            if process.poll() is None:
                process.terminate()
        for _, process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        raise
    return failures


def _technical_gate(manifest: dict[str, Any], stage: str) -> dict[str, Any]:
    models = {}
    passed = True
    for spec in manifest["models"]:
        reports = {
            condition: validate_condition(manifest, spec, stage, condition)
            for condition in CONDITIONS
        }
        models[spec["key"]] = reports
        passed = passed and all(report.get("passed") is True for report in reports.values())
    expected = manifest["expected_pilot_records"] if stage == "pilot" else manifest["expected_full_records"]
    raw_fingerprint = _current_raw_fingerprint(stage)
    record_count = len(raw_fingerprint)
    passed = passed and record_count == expected
    report = {"schema_version": 1, "status": "complete", "stage": stage,
              "passed": passed, "expected_records": expected, "record_count": record_count,
              "fixture_corpus_sha256": manifest["fixture_corpus_sha256"],
              "raw_fingerprint": raw_fingerprint, "models": models}
    save(LOG / f"{stage}-technical-validation.json", report)
    return report


def run_stage(manifest: dict[str, Any], stage: str) -> int:
    check_frozen()
    gates = evaluate_pre_pilot_gates(manifest) if stage == "pilot" else evaluate_full_gates(manifest)
    status = json.loads((LOG / "status.json").read_text())
    expected_status = "prepared_not_executed" if stage == "pilot" else "pilot_gates_reviewed"
    if status.get("stage") != expected_status:
        raise RuntimeError(f"{stage} cannot start from status {status.get('stage')!r}")
    for image, digest in manifest["image_ids"].items():
        actual = subprocess.check_output(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image], text=True
        ).strip()
        if actual != digest:
            raise RuntimeError("runtime image changed")
    save(LOG / "status.json", {"stage": stage + "_running", "gate_evidence": gates})
    failures = []
    for wave in manifest["schedule"]:
        failures.extend(_run_wave(manifest, stage, wave))
        if failures and (stage != "pilot" or any(item["exit_code"] != 3 for item in failures)):
            break
    technical = _technical_gate(manifest, stage)
    if failures or technical["passed"] is not True:
        save(LOG / "status.json", {"stage": stage + "_technical_failed",
                                   "failures": failures, "automatic_continuation": False})
        return 1
    next_stage = "pilot_complete_awaiting_semantics" if stage == "pilot" else "full_technical_complete_awaiting_judge"
    save(LOG / "status.json", {"stage": next_stage, "failures": []})
    return 0


def advance_reviewed_pilot(manifest: dict[str, Any]) -> None:
    status = json.loads((LOG / "status.json").read_text())
    if status.get("stage") != "pilot_complete_awaiting_semantics":
        raise RuntimeError("pilot has not completed technical validation")
    evidence = evaluate_full_gates(manifest)
    save(LOG / "status.json", {"stage": "pilot_gates_reviewed", "gate_evidence": evidence})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--prepare", action="store_true")
    actions.add_argument("--write-review-contract", type=Path)
    actions.add_argument("--check-pre-pilot-gates", action="store_true")
    actions.add_argument("--check-judge-gate", action="store_true")
    actions.add_argument("--advance-reviewed-pilot", action="store_true")
    actions.add_argument("--run-pilot", action="store_true")
    actions.add_argument("--run-full", action="store_true")
    actions.add_argument("--run-model")
    parser.add_argument("--stage", choices=("pilot", "full"))
    parser.add_argument("--cleanup-approved", action="store_true")
    parser.add_argument("--fixture-validation-phase", choices=("before_pilot", "before_full"),
                        help="allow the source-bound real smoke before pilot; full fixtures remain mandatory before full")
    parser.add_argument(
        "--judge-validation-phase", choices=("before_pilot", "before_scoring"),
        help="freeze Judge acceptance before generation (default) or before scoring",
    )
    parser.add_argument(
        "--batch-id",
        help="validated non-overwriting batch ID; frozen copies infer it from their path",
    )
    args = parser.parse_args(argv)
    if args.batch_id:
        _select_batch(args.batch_id)
    if args.judge_validation_phase and not (args.prepare or args.write_review_contract):
        parser.error("Judge validation phase can only be selected when preparing a new batch")
    if args.fixture_validation_phase and not (args.prepare or args.write_review_contract):
        parser.error("Fixture validation phase can only be selected when preparing a new batch")
    if args.prepare:
        prepare(judge_validation_phase=args.judge_validation_phase or "before_pilot",
                fixture_validation_phase=args.fixture_validation_phase or "before_pilot")
        return 0
    if args.write_review_contract:
        contract = review_contract(judge_validation_phase=args.judge_validation_phase or "before_pilot",
                                   fixture_validation_phase=args.fixture_validation_phase or "before_pilot")
        save(args.write_review_contract.resolve(), contract)
        print(json.dumps(contract, ensure_ascii=False, indent=2))
        return 0
    frozen_entry = FROZEN / "jobs" / Path(__file__).name
    if Path(__file__).resolve() != frozen_entry.resolve():
        os.execv(sys.executable, [sys.executable, str(frozen_entry), *(argv or sys.argv[1:])])
    check_frozen()
    manifest = json.loads(MANIFEST.read_text())
    if args.check_judge_gate:
        print(json.dumps({"passed": True, "judge_full_pipeline": _validate_full_pipeline_gate(manifest)}, indent=2))
        return 0
    if args.check_pre_pilot_gates:
        print(json.dumps(evaluate_pre_pilot_gates(manifest), indent=2))
        return 0
    if args.advance_reviewed_pilot:
        advance_reviewed_pilot(manifest)
        return 0
    if not args.cleanup_approved:
        parser.error("explicit approval for this exact v10 batch lifecycle is required")
    signal.signal(signal.SIGTERM, lambda signum, frame: (_ for _ in ()).throw(
        KeyboardInterrupt(f"owned batch interrupted by signal {signum}")))
    if args.run_model:
        if not args.stage:
            parser.error("--run-model requires --stage")
        try:
            run_model(manifest, args.run_model, args.stage)
        except PilotTechnicalFailure as exc:
            event("pilot_model_technical_failed", model=args.run_model, error=str(exc))
            return 3
        return 0
    return run_stage(manifest, "pilot" if args.run_pilot else "full")


if __name__ == "__main__":
    raise SystemExit(main())
