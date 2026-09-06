"""Audit task coverage and collect diagnostic candidates without changing scores."""

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


SERVICE_PORTS = {"gitlab": 8929, "owncloud": 8092, "plane": 8091}
SIGNATURES = {
    "http_not_found": re.compile(
        r"(?:HTTP Status:|HTTP Error|Error code:|Error:)\s*404", re.I
    ),
    "http_bad_request": re.compile(
        r"(?:HTTP Status:|HTTP Error|Error code:)\s*(?:400|422)", re.I
    ),
    "connection_refused": re.compile(r"connection refused", re.I),
    "dns_failure": re.compile(r"name or service not known|failed to resolve", re.I),
    "network_timeout": re.compile(r"ReadTimeout|ConnectTimeout|read timed out", re.I),
    "http_auth_error": re.compile(
        r"(?:HTTP Status:|HTTP Error|Error code:)\s*40[13]", re.I
    ),
    "http_server_error": re.compile(
        r"(?:HTTP Status:|HTTP Error|Error code:)\s*5\d\d", re.I
    ),
    "npc_empty_response": re.compile(r"NPC returned no visible response", re.I),
}
POOL_ENDPOINT = re.compile(r"ConnectionPool\(host=['\"]([^'\"]+)['\"], port=(\d+)")


def _endpoints(text: str) -> list[tuple[str, int]]:
    """Keep only host/port pairs, never URL credentials, paths, or query tokens."""
    endpoints = {(host, int(port)) for host, port in POOL_ENDPOINT.findall(text)}
    for url in re.findall(r"https?://[^\s'\"<>]+", text):
        try:
            parts = urlsplit(url)
            if parts.hostname:
                endpoints.add(
                    (
                        parts.hostname,
                        parts.port or (443 if parts.scheme == "https" else 80),
                    )
                )
        except ValueError:
            continue
    return sorted(endpoints)


def classify_result(record: dict[str, Any]) -> dict[str, Any]:
    """Distinguish harness errors, model limits, and ordinary graded outcomes."""
    result = record.get("test_result") or {}
    details = result.get("skilldistill") or {}
    error = record.get("error") or result.get("error")
    conversation_error = str(details.get("conversation_error") or "")
    if error or not result.get("final_score"):
        state = "harness_error"
    elif "MaxIterationsReached" in conversation_error:
        state = "iteration_limit"
    elif "stuck" in conversation_error.lower():
        state = "agent_stuck"
    elif conversation_error:
        state = "conversation_error"
    else:
        state = "completed"

    instance = record.get("instance") or {}
    dependencies = sorted(set(instance.get("dependencies") or []))
    expected_ports = {SERVICE_PORTS[d] for d in dependencies if d in SERVICE_PORTS}
    evidence = []
    for event in record.get("history") or []:
        if not isinstance(event, dict):
            continue
        if (
            event.get("source") != "environment"
            or event.get("kind") != "ObservationEvent"
        ):
            continue
        observation = event.get("observation") or {}
        if observation.get("kind") != "TerminalObservation":
            continue
        content = observation.get("content") or []
        if not isinstance(content, list):
            continue
        text = "\n".join(
            str(part.get("text", "")) for part in content if isinstance(part, dict)
        )
        signatures = [
            name for name, pattern in SIGNATURES.items() if pattern.search(text)
        ]
        if not signatures:
            continue
        endpoints = _endpoints(text)
        undeclared_only = bool(endpoints) and all(
            host == "the-agent-company.com"
            and port in SERVICE_PORTS.values()
            and port not in expected_ports
            for host, port in endpoints
        )
        evidence.append(
            {
                "event_id": event.get("id"),
                "signatures": signatures,
                "endpoints": [{"host": host, "port": port} for host, port in endpoints],
                "undeclared_service_only": undeclared_only,
            }
        )
    return {
        "instance_id": record.get("instance_id"),
        "state": state,
        "dependencies": dependencies,
        "score": result.get("final_score"),
        "partial_trajectory": bool(details.get("graded_from_partial_trajectory")),
        "network_evidence": evidence,
        # These are review candidates, NOT automatic diagnoses or score changes.
        "needs_service_review": any(not e["undeclared_service_only"] for e in evidence),
        "unexpected_service_access": any(
            e["undeclared_service_only"] for e in evidence
        ),
    }


def collect_report(results_root: Path, selection: Path, pattern: str) -> dict[str, Any]:
    expected = set(selection.read_text().split())
    records: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    unexpected: set[str] = set()
    invalid_lines: list[dict[str, Any]] = []
    for directory in sorted(results_root.glob(pattern)):
        output = directory / "output.jsonl"
        if not output.is_file():
            continue
        with output.open() as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    if line.endswith("\n"):
                        invalid_lines.append({"file": str(output), "line": number})
                    continue  # A non-newline-terminated record may still be writing.
                instance_id = str(record.get("instance_id", ""))
                if instance_id not in expected:
                    unexpected.add(instance_id)
                    continue
                if instance_id in records:
                    duplicates.add(instance_id)
                classified = classify_result(record)
                required = set(classified["dependencies"])
                ready: set[str] = set()
                forwarded: set[str] = set()
                log_path = directory / "logs" / f"instance_{instance_id}.log"
                if log_path.is_file():
                    for log_line in log_path.read_text(errors="replace").splitlines():
                        marker = "Task dependencies ready: "
                        if marker in log_line:
                            ready = set(log_line.split(marker, 1)[1].split(", "))
                        marker = "Workspace service forwarding ready: "
                        if marker in log_line:
                            forwarded = set(log_line.split(marker, 1)[1].split(", "))
                records[instance_id] = {
                    **classified,
                    "service_setup_confirmed": required <= ready
                    and required <= forwarded,
                    "result_dir": str(directory),
                }
    states = Counter(str(r["state"]) for r in records.values())
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expected": len(expected),
        "recorded": len(records),
        "pending_ids": sorted(expected - records.keys()),
        "states": dict(states),
        "setup_verified": sum(
            bool(v["service_setup_confirmed"]) for v in records.values()
        ),
        "missing_setup_evidence_ids": sorted(
            k for k, v in records.items() if not v["service_setup_confirmed"]
        ),
        "harness_error_ids": sorted(
            k for k, v in records.items() if v["state"] == "harness_error"
        ),
        "service_review_ids": sorted(
            k for k, v in records.items() if v["needs_service_review"]
        ),
        "unexpected_service_access_ids": sorted(
            k for k, v in records.items() if v["unexpected_service_access"]
        ),
        "duplicate_ids": sorted(duplicates),
        "unexpected_ids": sorted(unexpected),
        "invalid_lines": invalid_lines,
        "tasks": [records[k] for k in sorted(records)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = collect_report(args.results_root, args.selection, args.pattern)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"tasks", "pending_ids"}}
        )
    )


if __name__ == "__main__":
    main()
