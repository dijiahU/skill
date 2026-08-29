"""Shared utilities for matcher_*.py hook scripts.

Hook scripts get a JSON event from Claude Code on stdin (or via env var,
depending on host adapter); they emit a verdict JSON to stdout. Exit code 0
= proceed, exit code 2 = block + reason in stderr (Claude Code convention).

Each matcher script:
  1. Reads event from stdin
  2. Iterates atoms it owns, running their fast-path checks
  3. Aggregates verdicts (block > warn > pass)
  4. Writes audit log entry via cache_snapshot/health_status helpers
  5. Exits with appropriate code
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

# Add project root to path so helpers/ is importable
_BUNDLE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BUNDLE_ROOT))

try:
    from helpers import health_status
except ImportError:
    health_status = None    # graceful — tests may mock this


def read_event() -> dict[str, Any]:
    """Read the hook event JSON from stdin. Returns {} if no input."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return {}


def emit_pass() -> int:
    """Exit code 0 = proceed."""
    return 0


def emit_warn(reason: str, atom_id: str = "") -> int:
    """Exit code 0 + warn JSON — host shows to user, action proceeds."""
    print(json.dumps({"verdict": "warn", "atom_id": atom_id, "reason": reason}))
    return 0


def emit_block(reason: str, atom_id: str = "") -> int:
    """Exit code 2 = block. Reason goes to stderr per Claude Code convention."""
    print(reason, file=sys.stderr)
    print(json.dumps({"verdict": "block", "atom_id": atom_id, "reason": reason}))
    return 2


def _state_dir() -> Path:
    """Resolve the audit/state dir. Mirrors health_status._status_dir():
    honor SAFETY_ORCH_STATUS_DIR, else ~/.safety-orch (the host-mounted
    .audit-<mode>/ dir under the pilot container)."""
    raw = os.environ.get("SAFETY_ORCH_STATUS_DIR")
    d = Path(raw) if raw else (Path.home() / ".safety-orch")
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def _phase() -> str:
    """Which matcher emitted this verdict, derived from the running script name.
    matcher_bash.py -> 'bash', matcher_user_prompt.py -> 'user_prompt'."""
    name = Path(sys.argv[0]).stem if sys.argv and sys.argv[0] else "unknown"
    return name[len("matcher_"):] if name.startswith("matcher_") else name


def log_verdict(verdicts: list[dict]) -> None:
    """Append every block/warn verdict to verdict-log.jsonl — the durable
    'blocked/warned by THE BUNDLE' ledger used for pilot attribution.

    `source: "bundle"` tags these as OUR hook's deterministic decision. By
    contrast, anything Claude Code stops on its own (built-in policy or model
    alignment refusal) leaves NO entry here — it shows up only in the session
    transcript. So: in a bundle-mode run, a blocked scenario WITH a matching
    verdict-log entry == attributable to us; blocked WITHOUT one == Claude Code.

    Logging is best-effort and must never crash a hook."""
    actionable = [v for v in verdicts if v.get("verdict") in ("block", "warn")]
    if not actionable:
        return
    try:
        ts = int(time.time())
        phase = _phase()
        log = _state_dir() / "verdict-log.jsonl"
        with log.open("a") as f:
            for v in actionable:
                f.write(json.dumps({
                    "ts": ts,
                    "source": "bundle",
                    "phase": phase,
                    "atom_id": v.get("atom_id", ""),
                    "verdict": v.get("verdict", ""),
                    "reason": v.get("reason", ""),
                }) + "\n")
    except Exception:    # noqa: BLE001 — never let logging crash a hook
        pass


def aggregate(verdicts: list[dict]) -> int:
    """block wins, then warn, else pass. Returns exit code."""
    log_verdict(verdicts)
    blocks = [v for v in verdicts if v.get("verdict") == "block"]
    if blocks:
        reasons = "; ".join(f"[{v['atom_id']}] {v['reason']}" for v in blocks)
        return emit_block(reasons)
    warns = [v for v in verdicts if v.get("verdict") == "warn"]
    if warns:
        reasons = "; ".join(f"[{v['atom_id']}] {v['reason']}" for v in warns)
        return emit_warn(reasons)
    return emit_pass()


def check(atom_id: str, condition: bool, reason: str) -> dict:
    """Convenience: produce a verdict dict for one atom."""
    return {
        "atom_id": atom_id,
        "verdict": "block" if condition else "pass",
        "reason": reason if condition else "",
    }


def soft_check(atom_id: str, condition: bool, reason: str) -> dict:
    """Same as check() but returns 'warn' instead of 'block'."""
    return {
        "atom_id": atom_id,
        "verdict": "warn" if condition else "pass",
        "reason": reason if condition else "",
    }


# --- shared regex library (used by multiple matchers) ---

PII_PATTERNS = {
    "ssn":            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card":    re.compile(
        r"\b(?:\d{13,19}|(?:\d{4}[ -]){3}\d{1,4}|\d{4}[ -]\d{6}[ -]\d{5})\b"
    ),
    "iban":           re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    "email":          re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "us_phone":       re.compile(r"\b\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b"),
}

SECRET_PATTERNS = {
    "aws_access_key":     re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "aws_secret":         re.compile(r"\b[A-Za-z0-9/+=]{40}\b"),    # heuristic
    "github_token":       re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    "openai_key":         re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "anthropic_key":      re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "deepseek_key":       re.compile(r"\bsk-[a-f0-9]{32}\b"),
    "private_key_header": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "slack_webhook":      re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"),
}

DESTRUCTIVE_KEYWORDS = re.compile(
    r"(?:^|\b)(?:(?:sudo|doas)\s+)?(?:\S*/)?rm\s+"
    r"(?=[^;&|\n]*(?:--recursive\b|-[A-Za-z]*[rR][A-Za-z]*\b))|"
    r"\b(drop\s+(table|database)|truncate\s+table|"
    r"force[\s-]push|--no-verify|chmod\s+777|"
    r"DELETE\s+FROM|UPDATE\s+\w+\s+SET\s+(?!.*WHERE))",
    re.IGNORECASE,
)

PATH_TRAVERSAL_PATTERNS = re.compile(r"(\.\./|\.\.\\|/etc/passwd|/etc/shadow|~/\.ssh/id_)")

SHELL_INJECTION_PATTERNS = re.compile(
    r"(\$\(\s*(?:curl|wget|nc|ncat|sh|bash|python|node)\b[^)]*\)|"
    r"`\s*(?:curl|wget|nc|ncat|sh|bash|python|node)\b[^`]*`|"
    r";\s*(rm|curl|wget|nc|sh|bash)\b|"
    r"\|\s*(sh|bash|python|nc)\b|>\s*/dev/(tcp|udp))",
    re.IGNORECASE,
)

UNSAFE_URL_PATTERNS = re.compile(
    r"^(file://|chrome://|javascript:|data:text/html|"
    r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|169\.254\.169\.254|"
    r"\[::1\]|metadata\.google|metadata\.azure))",
    re.IGNORECASE,
)


def log_audit(atom_id: str, event: str, ctx: dict) -> None:
    """Write to fail-open log if helpers are available."""
    if health_status is None:
        return
    try:
        health_status.log_fail_open(atom_id, {"event": event, **ctx})
    except Exception:    # noqa: BLE001 — never let logging crash a hook
        pass
