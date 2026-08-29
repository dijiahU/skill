#!/usr/bin/env python3
"""UserPromptSubmit matcher — runs on every user message before the agent sees it.

Atoms covered (6):
- detect-pii-in-input
- detect-payment-card-data
- detect-credential-in-input
- detect-private-key-input
- detect-destructive-action-keyword
- detect-jailbreak-template
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_common import (
    read_event, aggregate, soft_check, check, log_audit, _state_dir,
    PII_PATTERNS, SECRET_PATTERNS, DESTRUCTIVE_KEYWORDS,
)
from ported_atom_checks import jailbreak_template_matches


def main() -> int:
    event = read_event()
    text = event.get("prompt") or event.get("user_message") or ""
    if not text:
        return 0

    verdicts = []

    # detect-pii-in-input — warn (not block) for general PII
    pii_hits = [name for name, rx in PII_PATTERNS.items() if rx.search(text)]
    if pii_hits:
        verdicts.append(soft_check(
            "detect-pii-in-input", True,
            f"PII detected: {', '.join(pii_hits)}",
        ))

    # redact-input-pii — hook fast path surfaces a redaction warning; full host
    # prompt rewriting is adapter-specific.
    if pii_hits:
        verdicts.append(soft_check(
            "redact-input-pii", True,
            f"Input PII should be redacted before downstream processing: {', '.join(pii_hits)}",
        ))

    # detect-payment-card-data — block if credit card matches Luhn check
    cc_matches = PII_PATTERNS["credit_card"].findall(text)
    for m in cc_matches:
        digits = [int(c) for c in m if c.isdigit()]
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            verdicts.append(check(
                "detect-payment-card-data", True,
                "Credit card number detected in user input",
            ))
            break

    # detect-credential-in-input — block on AWS key, GitHub token, etc.
    cred_hits = [name for name, rx in SECRET_PATTERNS.items()
                 if name != "private_key_header" and rx.search(text)]
    if cred_hits:
        verdicts.append(check(
            "detect-credential-in-input", True,
            f"Credential pattern matched: {', '.join(cred_hits)}",
        ))

    # detect-private-key-input — block on PEM header
    if SECRET_PATTERNS["private_key_header"].search(text):
        verdicts.append(check(
            "detect-private-key-input", True,
            "Private key PEM header detected in user input",
        ))

    # detect-destructive-action-keyword — warn (user will be re-confirmed by intent skill)
    if DESTRUCTIVE_KEYWORDS.search(text):
        match = DESTRUCTIVE_KEYWORDS.search(text)
        verdicts.append(soft_check(
            "detect-destructive-action-keyword", True,
            f"Destructive keyword detected: '{match.group()}'",
        ))

    # Known-template fast path; broader semantic detection remains the hybrid
    # fallback in the prompt-injection archetype reference.
    jailbreak_matches = jailbreak_template_matches(text)
    if jailbreak_matches:
        verdicts.append(check(
            "detect-jailbreak-template", True,
            f"Known jailbreak template matched: '{jailbreak_matches[0]}'",
        ))

    _record_prompt_snapshot(text)
    return aggregate(verdicts) if verdicts else 0


def _record_prompt_snapshot(text: str) -> None:
    """Append a bounded prompt snapshot for audit-trail-recording."""
    snapshot = _state_dir() / "prompt-snapshots.jsonl"
    with snapshot.open("a") as f:
        f.write(json.dumps({
            "ts": int(time.time()),
            "prompt_chars": len(text),
            "prompt_truncated": text[:500],
        }) + "\n")
    log_audit("record-prompt-and-context-snapshot", "snapshot",
              {"prompt_chars": len(text)})


def _luhn_ok(digits: list[int]) -> bool:
    s, alt = 0, False
    for d in reversed(digits):
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        s += d
        alt = not alt
    return s % 10 == 0


if __name__ == "__main__":
    sys.exit(main())
