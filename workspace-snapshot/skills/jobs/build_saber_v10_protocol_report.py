#!/usr/bin/env python3
"""Build the fail-closed v10 protocol gate from real and controlled evidence.

The controlled fault report proves adapter/proxy behavior only. Every combined
case also requires evidence from that model's completed real service probe.
This script reads JSON/SSE evidence and never starts a model, GPU, or container.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import run_saber_v10 as controller
from saber_v10_model_specs import MODEL_SPECS, PROTOCOL_VERSION

ROOT = Path("/2024233123/skills")
REPORT_ROOT = ROOT / "reports/v10-fixes-20260906"
CORPUS_SHA256 = "3dbba088b71153d5af02ef081376d83017f87da8cf1142c81764e19a0ac56167"
REAL_REPORTS = {
    "mistral": REPORT_ROOT / "protocol-mistral-r2",
    "minimax": REPORT_ROOT / "protocol-minimax-r1",
    "deepseek_flash": REPORT_ROOT / "protocol-deepseek-flash-r1",
    "glm": REPORT_ROOT / "protocol-glm-r3",
    "gptoss": REPORT_ROOT / "protocol-gptoss-r3",
}
CONTROLLED_REPORT = (
    REPORT_ROOT / "protocol-failure-validation-local/protocol-failure-validation.json"
)
DEFAULT_OUTPUT = REPORT_ROOT / "protocol_probe_report.json"
COMMON_PROBES = tuple(
    name for name in controller.PROTOCOL_REQUIRED_CHECKS
    if name != "mistral_incremental_decode_matches_batch_decode"
)
MISTRAL_PROBE = "mistral_incremental_decode_matches_batch_decode"


class EvidenceError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise EvidenceError(f"unreadable JSON {path}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"JSON root is not an object: {path}")
    return value


def absolute(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(REPORT_ROOT.resolve()) or not resolved.is_file():
        raise EvidenceError(f"evidence missing or out of scope: {resolved}")
    return str(resolved)


def response_body(path: Path) -> dict[str, Any]:
    wrapper = load_json(path)
    if wrapper.get("status_code") != 200 or not isinstance(wrapper.get("body"), str):
        raise EvidenceError(f"unsuccessful response evidence: {path}")
    try:
        value = json.loads(wrapper["body"])
    except ValueError as exc:
        raise EvidenceError(f"response body is not JSON: {path}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"response body root is not an object: {path}")
    return value


def nonempty_model_text(response: dict[str, Any]) -> bool:
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip():
                return True
    return False


def validate_controlled() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    report = load_json(CONTROLLED_REPORT)
    cases = report.get("cases")
    expected_names = set(COMMON_PROBES[2:])
    if (report.get("schema_version") != 1 or report.get("status") != "complete"
            or report.get("passed") is not True
            or report.get("scope") != "controlled_local_fault_injection"
            or report.get("protocol_version") != PROTOCOL_VERSION
            or report.get("fixture_corpus_sha256") != CORPUS_SHA256
            or report.get("real_model_service_invoked") is not False
            or report.get("proxy_host_dependency_shims") != []
            or not isinstance(cases, list) or report.get("case_count") != 3
            or {case.get("probe_name") for case in cases if isinstance(case, dict)}
            != expected_names):
        raise EvidenceError("controlled fault report header or exact case inventory failed")
    case_map = {}
    all_paths = set()
    all_sources = {}
    for case in cases:
        name = case["probe_name"]
        checks = case.get("checks")
        required = controller.PROTOCOL_REQUIRED_CHECKS[name]
        if (case.get("passed") is not True or not isinstance(checks, dict)
                or any(checks.get(key) is not True for key in required)
                or not isinstance(case.get("evidence_paths"), list)
                or not case["evidence_paths"]
                or not isinstance(case.get("source_sha256"), dict)
                or not case["source_sha256"]):
            raise EvidenceError(f"controlled case incomplete: {name}")
        for value, digest in case["source_sha256"].items():
            path = Path(value).resolve()
            if not path.is_file() or sha256_file(path) != digest:
                raise EvidenceError(f"controlled case source stale: {path}")
            prior = all_sources.setdefault(str(path), digest)
            if prior != digest:
                raise EvidenceError(f"controlled case source hash conflict: {path}")
        for value in case["evidence_paths"]:
            all_paths.add(absolute(Path(value)))
        case_map[name] = case
    if set(report.get("evidence_paths", [])) != all_paths:
        raise EvidenceError("controlled top evidence path inventory differs from cases")
    if report.get("evidence_sha256") != {
        value: sha256_file(Path(value)) for value in sorted(all_paths)
    }:
        raise EvidenceError("controlled evidence hashes changed")
    if report.get("source_sha256") != all_sources:
        raise EvidenceError("controlled top source inventory differs from cases")
    return case_map, all_sources


def real_source_requirements(model: str, spec: dict[str, Any]) -> set[Path]:
    names = {
        "run_saber_v10_protocol_probe.py", "saber_v10_protocol_cases.py",
        "saber_v10_stream_probe.py", "run_saber_v10_protocol_failure_validation.py",
        "codex_native_adapter.py", "vllm_responses_compat_proxy.py",
    }
    for service in spec["services"]:
        argv = [str(value) for value in service.get("argv", [])]
        if "--middleware" in argv:
            names.add("saber_vllm_token_count.py")
        for value in argv + [str(item) for item in service.get("prestart_argv", [])]:
            if Path(value).suffix == ".py":
                names.add(Path(value).name)
        if service.get("env", {}).get("SABER_RESPONSES_CONTEXT_GUARD") == "1":
            names.add("saber_responses_budget.py")
    roots = [ROOT / "jobs", ROOT / "bin", ROOT / "projects/skill/saber/harness_adapters"]
    paths = {path.resolve() for root in roots for path in root.glob("*") if path.name in names}
    if model == "mistral":
        paths.update((ROOT / relative).resolve() for relative in (
            "compat/mistral_utf8_v10/sitecustomize.py",
            "compat/mistral_utf8_v10/mistral_utf8_compat.py",
            "compat/mistral_utf8_v10/mistral_tool_strict_compat.py",
            "compat/mistral_utf8_v10/verify_activation.py",
            "compat/mistral_developer_role/sitecustomize.py",
        ))
    missing = names - {path.name for path in paths}
    if missing:
        raise EvidenceError(f"{model} required source missing: {sorted(missing)}")
    return paths


def merge_source_evidence(
    model: str, status: dict[str, Any], controlled_sources: dict[str, str],
    spec: dict[str, Any],
) -> dict[str, str]:
    merged = dict(status.get("source_sha256") or {})
    merged[str(Path(__file__).resolve())] = sha256_file(Path(__file__).resolve())
    for path, digest in controlled_sources.items():
        prior = merged.setdefault(path, digest)
        if prior != digest:
            raise EvidenceError(f"{model} source reports disagree: {path}")
    for path in real_source_requirements(model, spec):
        expected = sha256_file(path)
        if merged.get(str(path)) != expected:
            raise EvidenceError(f"{model} loaded or controlled source is stale: {path}")
    return merged


def build_model(
    model: str, controlled: dict[str, dict[str, Any]],
    controlled_sources: dict[str, str],
) -> dict[str, Any]:
    directory = REAL_REPORTS[model]
    status_path = directory / "status.json"
    status = load_json(status_path)
    spec = next(item for item in MODEL_SPECS if item["key"] == model)
    if (status.get("model") != model or status.get("status") != "probe_passed"
            or status.get("cleanup_safe") is not True
            or not isinstance(status.get("service_spec"), dict)):
        raise EvidenceError(f"{model} real service probe or cleanup did not pass")
    if (controller.canonical_hash(controller.service_spec_contract(status["service_spec"]))
            != controller.canonical_hash(controller.service_spec_contract(spec))):
        raise EvidenceError(f"{model} recorded service spec differs from current per-model config")
    base_rows = {row.get("name"): row for row in status.get("cases", [])}
    extended = {row.get("name"): row for row in status.get("extended_cases", [])}
    if set(base_rows) != {"ascii", "unicode"} or any(
        row.get("count_matches") is not True or row.get("response_status") != "completed"
        or row.get("counted") != (row.get("usage") or {}).get("input_tokens")
        for row in base_rows.values()
    ):
        raise EvidenceError(f"{model} exact render/usage checks failed")
    for name in ("multibyte_tool_roundtrip", "long_context_budget", "unicode_sse"):
        if extended.get(name, {}).get("passed") is not True:
            raise EvidenceError(f"{model} missing successful real case: {name}")

    common = [absolute(status_path), absolute(directory / "cleanup.json")]
    ascii_response = response_body(directory / "ascii-response.json")
    unicode_response = response_body(directory / "unicode-response.json")
    if not nonempty_model_text(ascii_response) or not nonempty_model_text(unicode_response):
        raise EvidenceError(f"{model} completed response lacked nonempty model text")
    count_paths = common + [absolute(directory / name) for name in (
        "ascii-count.json", "ascii-response.json", "unicode-count.json", "unicode-response.json",
    )]
    cases = [{
        "probe_name": COMMON_PROBES[0], "passed": True,
        "checks": {"short_count_matches_usage": True, "multibyte_count_matches_usage": True},
        "evidence_paths": sorted(set(count_paths)), "evidence_kind": "real_model_service",
    }]

    long_row = extended["long_context_budget"]
    long_response = response_body(directory / "long-boundary-proxy-response.json")
    usage_input = (long_response.get("usage") or {}).get("input_tokens")
    within = all(type(long_row.get(key)) is int for key in (
        "input_tokens", "allocated_output_tokens", "context_limit",
    )) and long_row["input_tokens"] + long_row["allocated_output_tokens"] + 128 <= long_row["context_limit"]
    if (not within or long_row["allocated_output_tokens"] <= 0
            or usage_input != long_row["input_tokens"]
            or long_response.get("max_output_tokens") != long_row["allocated_output_tokens"]):
        raise EvidenceError(f"{model} long-context invariant failed")
    long_paths = common + [absolute(directory / name) for name in (
        "long-boundary-count.json", "long-boundary-proxy-response.json",
    )]
    cases.append({
        "probe_name": COMMON_PROBES[1], "passed": True,
        "checks": {"within_context": True, "input_not_truncated": True,
                   "output_reserve_positive": True},
        "evidence_paths": sorted(set(long_paths)), "evidence_kind": "real_model_service",
    })

    actual_by_fault = {
        COMMON_PROBES[2]: ["tool-first-count.json", "tool-first-response.json",
                           "tool-second-count.json", "tool-second-response.json"],
        COMMON_PROBES[3]: ["unicode-stream.sse", "unicode-stream-validation.json"],
        COMMON_PROBES[4]: ["ascii-response.json", "unicode-response.json"],
    }
    for name in COMMON_PROBES[2:]:
        controlled_case = controlled[name]
        evidence = common + [absolute(directory / item) for item in actual_by_fault[name]]
        evidence.extend(absolute(Path(item)) for item in controlled_case["evidence_paths"])
        cases.append({
            "probe_name": name, "passed": True,
            "checks": {key: True for key in controller.PROTOCOL_REQUIRED_CHECKS[name]},
            "evidence_paths": sorted(set(evidence)),
            "evidence_kind": "real_model_service_plus_controlled_local_fault",
            "controlled_scope": "does_not_prove_model_encountered_fault",
        })

    if model == "mistral":
        stream = extended["unicode_sse"]
        if (stream.get("delta_matches_final") is not True
                or stream.get("replacement_count") != 0
                or extended["multibyte_tool_roundtrip"].get("passed") is not True):
            raise EvidenceError("Mistral live decode or strict-tool evidence failed")
        evidence = common + [absolute(directory / item) for item in (
            "unicode-stream.sse", "unicode-stream-validation.json", "tool-first-response.json",
        )] + [absolute(REPORT_ROOT / "mistral_utf8_regression.json"),
              absolute(REPORT_ROOT / "mistral_tool_strict_regression.json")]
        cases.append({
            "probe_name": MISTRAL_PROBE, "passed": True,
            "checks": {"incremental_matches_batch": True, "replacement_count_zero": True,
                       "strict_null_removed": True},
            "evidence_paths": sorted(set(evidence)),
            "evidence_kind": "real_model_service_plus_cpu_regression",
        })

    names = [case["probe_name"] for case in cases]
    evidence = sorted({path for case in cases for path in case["evidence_paths"]})
    sources = merge_source_evidence(model, status, controlled_sources, spec)
    return {
        "passed": True, "cleanup_safe": True, "protocol_version": PROTOCOL_VERSION,
        "probe_names": names, "case_count": len(cases), "cases": cases,
        "evidence_paths": evidence, "source_sha256": sources,
        "service_spec": status["service_spec"],
        "service_spec_sha256": controller.canonical_hash(
            controller.service_spec_contract(status["service_spec"])
        ),
        "real_probe_status_path": absolute(status_path),
    }


def build() -> dict[str, Any]:
    errors = []
    models = {}
    try:
        controlled, controlled_sources = validate_controlled()
    except Exception as exc:
        controlled, controlled_sources = {}, {}
        errors.append(f"controlled: {type(exc).__name__}: {exc}")
    for model in controller.EXPECTED_MODELS:
        try:
            models[model] = build_model(model, controlled, controlled_sources)
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}: {exc}")
    probes = {}
    for name in controller.PROTOCOL_REQUIRED_CHECKS:
        applicable = [item for model, item in models.items()
                      if name in item.get("probe_names", [])]
        evidence = sorted({path for item in applicable for case in item["cases"]
                           if case["probe_name"] == name for path in case["evidence_paths"]})
        probes[name] = {
            "passed": len(applicable) == (1 if name == MISTRAL_PROBE else 5),
            "case_count": len(applicable), "evidence_paths": evidence,
        }
    all_evidence = sorted({path for item in models.values() for path in item["evidence_paths"]})
    passed = (not errors and set(models) == set(controller.EXPECTED_MODELS)
              and all(item["passed"] for item in probes.values()))
    return {
        "schema_version": 1, "status": "complete", "passed": passed,
        "fixture_corpus_sha256": CORPUS_SHA256,
        "probes": probes, "models": models,
        "evidence_sha256": {path: sha256_file(Path(path)) for path in all_evidence},
        "errors": errors,
        "evidence_separation": {
            "real_service": "Each model supplied its own count, tool roundtrip, context, completion, SSE and cleanup evidence.",
            "controlled_fault": "Local fault injection proves shared adapter/proxy behavior and does not claim a model encountered the injected fault.",
        },
    }


def save(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    pending.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build()
    save(args.output.resolve(), report)
    print(json.dumps({"output": str(args.output.resolve()), "passed": report["passed"],
                      "models": sorted(report["models"]), "errors": report["errors"]},
                     ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
