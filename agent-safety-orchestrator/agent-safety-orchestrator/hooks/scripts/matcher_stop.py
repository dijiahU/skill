#!/usr/bin/env python3
"""Stop matcher — runs when the agent finishes a turn / completes a task.

Atoms covered (3):
- record-decision-trace
- snapshot-agent-state
- log-human-decision-outcome
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_common import (
    read_event, _state_dir, aggregate, check, soft_check, log_audit,
    PII_PATTERNS, SECRET_PATTERNS,
)
from matcher_posttool import (
    MARKDOWN_IMAGE_BEACON, BASE64_PAYLOAD, DNS_EXFIL_PATTERNS,
    SYSTEM_PROMPT_FRAGMENTS, INTERNAL_INFRA_PATTERNS,
)
from ported_atom_checks import (
    disallowed_content_rule_findings,
    review_generated_code_output_findings,
)


# Shared resolver: honors SAFETY_ORCH_STATUS_DIR so all audit streams
# (decision-trace, tool-invocations, verdict-log) stay in one dir.
_STATE_DIR = _state_dir()


def main() -> int:
    event = read_event()
    ts = int(time.time())
    final_message = event.get("final_message") or event.get("last_assistant_message") or ""

    verdicts = []
    verdicts.extend(_check_final_output(final_message))

    # record-decision-trace — append-only structured log
    trace = _STATE_DIR / "decision-trace.jsonl"
    with trace.open("a") as f:
        f.write(json.dumps({
            "ts": ts,
            "event": "stop",
            "turn_id": event.get("turn_id"),
            "final_message_truncated": final_message[:500],
        }) + "\n")

    # snapshot-agent-state — minimal: timestamp + last counters
    state_file = _STATE_DIR / "session-counters.json"
    if state_file.exists():
        snapshot = _STATE_DIR / f"snapshot-{ts}.json"
        snapshot.write_text(state_file.read_text())

    # log-human-decision-outcome — if event carries a human decision marker
    if event.get("human_decision"):
        hd_log = _STATE_DIR / "human-decisions.jsonl"
        with hd_log.open("a") as f:
            f.write(json.dumps({
                "ts": ts,
                "decision": event["human_decision"],
                "context": event.get("decision_context", {}),
            }) + "\n")

    _check_incident_stop(event, ts)
    return aggregate(verdicts) if verdicts else 0


def _check_final_output(text: str) -> list[dict]:
    """Deterministic output-generation checks for the final assistant message."""
    if not text or not isinstance(text, str):
        return []
    verdicts = []

    pii_hits = [name for name, rx in PII_PATTERNS.items() if rx.search(text)]
    if pii_hits:
        verdicts.append(soft_check(
            "redact-output-pii", True,
            f"Final output contains PII: {', '.join(pii_hits)}",
        ))
    secret_hits = [name for name, rx in SECRET_PATTERNS.items() if rx.search(text)]
    if secret_hits:
        verdicts.append(soft_check(
            "redact-output-secret", True,
            f"Final output contains secrets: {', '.join(secret_hits)}",
        ))
    if SYSTEM_PROMPT_FRAGMENTS.search(text):
        verdicts.append(soft_check(
            "redact-output-system-prompt", True,
            "Final output may contain system-prompt fragments",
        ))
    if INTERNAL_INFRA_PATTERNS.search(text):
        verdicts.append(soft_check(
            "redact-output-internal-infra", True,
            "Final output may contain internal infrastructure details",
        ))
    if MARKDOWN_IMAGE_BEACON.search(text):
        verdicts.append(check(
            "detect-markdown-image-beacon", True,
            "Final output contains a markdown image beacon",
        ))
    if BASE64_PAYLOAD.search(text):
        verdicts.append(soft_check(
            "detect-base64-payload-in-output", True,
            "Final output contains a large base64-looking block",
        ))
    if DNS_EXFIL_PATTERNS.search(text):
        verdicts.append(soft_check(
            "detect-dns-exfiltration-pattern", True,
            "Final output contains a possible DNS exfil pattern",
        ))

    findings = review_generated_code_output_findings(text)
    if findings:
        verdicts.append(check(
            "review-generated-code-output", True,
            f"Dangerous generated code in final output: {findings[0]}",
        ))

    rules_json = os.environ.get("SAFETY_ORCH_OUTPUT_CONTENT_RULES_JSON", "").strip()
    rules_path = os.environ.get("SAFETY_ORCH_OUTPUT_CONTENT_RULES_FILE", "").strip()
    try:
        if rules_path:
            path = Path(rules_path)
            if path.stat().st_size > 1_000_000:
                raise ValueError("output content rule file exceeds 1 MB")
            rules_json = path.read_text(encoding="utf-8")
        if rules_json:
            findings = disallowed_content_rule_findings(text, rules_json)
            if findings:
                verdicts.append(check(
                    "enforce-disallowed-content-rule", True,
                    f"Output content rule(s) matched: {', '.join(findings[:5])}",
                ))
    except (OSError, ValueError) as exc:
        log_audit("enforce-disallowed-content-rule", "config-error", {"err": str(exc)})
        verdicts.append(check(
            "enforce-disallowed-content-rule", True,
            f"Configured output content rule pack is invalid: {exc}",
        ))
    return verdicts


def _check_incident_stop(event: dict, ts: int) -> None:
    """Handle incident-response stop-side actions (ticket + playbook run)."""
    incident_file = _STATE_DIR / "incident-state.json"
    if not incident_file.exists():
        return
    try:
        incident = json.loads(incident_file.read_text())
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(incident, dict):
        return

    if incident.get("notify_pending"):
        ticket_log = _STATE_DIR / "incident-tickets.jsonl"
        with ticket_log.open("a") as f:
            f.write(json.dumps({
                "ts": ts,
                "incident_id": incident.get("incident_id", ""),
                "severity": incident.get("severity", "high"),
                "summary": str(incident.get("summary", ""))[:300],
            }) + "\n")
        log_audit("notify-oncall-and-open-ticket", "ticket-opened",
                  {"incident_id": incident.get("incident_id", "")})

    if incident.get("playbook_pending") and os.environ.get(
        "SAFETY_ORCH_RECOVERY_PLAYBOOK_JSON", ""
    ).strip():
        playbook_log = _STATE_DIR / "recovery-playbook-runs.jsonl"
        with playbook_log.open("a") as f:
            f.write(json.dumps({
                "ts": ts,
                "incident_id": incident.get("incident_id", ""),
                "playbook": os.environ["SAFETY_ORCH_RECOVERY_PLAYBOOK_JSON"][:500],
            }) + "\n")
        log_audit("execute-recovery-playbook", "playbook-run",
                  {"incident_id": incident.get("incident_id", "")})


if __name__ == "__main__":
    sys.exit(main())
