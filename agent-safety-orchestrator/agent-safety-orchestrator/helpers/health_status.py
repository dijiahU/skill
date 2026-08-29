"""Runtime health-status + banner for Safety Orchestrator.

Design goal (per docs/SAFETY_ATOMIC_CAPABILITIES.md §12.4):
- Session-start banner shows which atoms are active / degraded / disabled
- fail-open events get persistent audit log entries (never silent)
- Other helpers/hook-scripts call `mark_degraded` / `mark_disabled` / `log_fail_open`

Public API:
    init_banner(atoms_json_path: str) -> str
        Pings hook-network atoms, returns multi-line human-readable banner.
        Side effect: writes ~/.safety-orch/atom-status.json.

    mark_degraded(atom_id: str, reason: str) -> None
    mark_disabled(atom_id: str, reason: str) -> None
    log_fail_open(atom_id: str, ctx: dict) -> None
        Append-only JSONL audit log at ~/.safety-orch/fail-open-log.jsonl
        Wired into `record-decision-trace` archetype downstream.

    get_atom_state(atom_id: str) -> dict
        Returns {"state": "active|degraded|disabled", "reason": str, "since": ts}.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_STATUS_DIR = Path.home() / ".safety-orch"
STATUS_FILE = "atom-status.json"
FAIL_OPEN_LOG = "fail-open-log.jsonl"

# Atoms that need a live endpoint at session start to verify connectivity.
# Pulled from requires_network=true atoms in §12.3 of vocab doc.
NETWORK_ATOMS = {
    "check-package-cve": "https://api.osv.dev/v1",
    "detect-hallucinated-package": "https://registry.npmjs.org",
    "check-package-recency-anomaly": "https://registry.npmjs.org",
    "check-dependency-confusion": "https://registry.npmjs.org",
    "check-malware-hash-ioc": "https://www.virustotal.com/api/v3",
}

# Atoms gated by API keys. Key absent → atom disabled.
API_KEY_GATED = {
    "check-malware-hash-ioc": "VIRUSTOTAL_API_KEY",
}


def _status_dir() -> Path:
    raw = os.environ.get("SAFETY_ORCH_STATUS_DIR")
    d = Path(raw) if raw else DEFAULT_STATUS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_dir() -> Path:
    """Return the cache directory shared with helpers.cache_snapshot."""
    raw = os.environ.get("SAFETY_ORCH_CACHE_DIR")
    return Path(raw) if raw else Path.home() / ".cache" / "safety-orch"


def _snapshot_advisory_count(path: Path) -> int:
    """Count indexed package entries in an offline OSV snapshot."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return 0
    if not isinstance(data, dict):
        return 0
    return sum(
        1
        for key, advisories in data.items()
        if key != "_meta" and "|" in key and isinstance(advisories, list)
    )


def _read_status() -> dict[str, dict]:
    p = _status_dir() / STATUS_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_status(state: dict[str, dict]) -> None:
    p = _status_dir() / STATUS_FILE
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _set_state(atom_id: str, state: str, reason: str) -> None:
    cur = _read_status()
    cur[atom_id] = {"state": state, "reason": reason, "since": int(time.time())}
    _write_status(cur)


def mark_degraded(atom_id: str, reason: str) -> None:
    _set_state(atom_id, "degraded", reason)


def mark_disabled(atom_id: str, reason: str) -> None:
    _set_state(atom_id, "disabled", reason)


def mark_active(atom_id: str) -> None:
    _set_state(atom_id, "active", "")


def get_atom_state(atom_id: str) -> dict:
    cur = _read_status()
    return cur.get(atom_id, {"state": "active", "reason": "", "since": 0})


def log_fail_open(atom_id: str, ctx: dict[str, Any]) -> None:
    """Append a fail-open event to the audit log.

    `record-decision-trace` archetype consumes this stream downstream.
    """
    log = _status_dir() / FAIL_OPEN_LOG
    entry = {
        "ts": int(time.time()),
        "atom_id": atom_id,
        "event": "fail-open",
        "ctx": ctx,
    }
    with log.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ----- session-start banner -----

def _ping(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    """Lightweight HEAD-like probe. Returns (ok, reason)."""
    try:
        host = urlparse(url).hostname
        if host:
            socket.gethostbyname(host)    # DNS resolves
    except (socket.gaierror, OSError) as e:
        return False, f"DNS: {e}"
    try:
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=timeout).close()
        return True, ""
    except urllib.error.HTTPError as e:
        # 4xx still indicates the endpoint is reachable.
        if 400 <= e.code < 500:
            return True, ""
        return False, f"HTTP {e.code}"
    except (urllib.error.URLError, OSError) as e:
        return False, str(e)


def init_banner(atoms_json_path: str | None = None) -> str:
    """Run health checks and produce a session-start banner.

    Called by safety-router-skill at the start of a session (via Bash tool, since
    the meta-skill cannot run Python directly — install.sh wires this up).
    """
    atoms_path = atoms_json_path or str(Path(__file__).resolve().parent.parent / "atoms.json")
    try:
        atoms = json.loads(Path(atoms_path).read_text())
    except (OSError, json.JSONDecodeError):
        return "Safety Orchestrator: ❌ failed to load atoms.json"

    total = len(atoms)
    degraded: dict[str, str] = {}
    disabled: dict[str, str] = {}

    def note_degraded(atom_id: str, reason: str) -> None:
        previous = degraded.get(atom_id)
        combined = f"{previous}; {reason}" if previous else reason
        degraded[atom_id] = combined
        mark_degraded(atom_id, combined)

    # 1. API-key gates
    for atom_id, env_key in API_KEY_GATED.items():
        if not os.environ.get(env_key):
            mark_disabled(atom_id, f"{env_key} missing")
            disabled[atom_id] = f"{env_key} missing"

    # 2. Network pings
    for atom_id, endpoint in NETWORK_ATOMS.items():
        if atom_id in disabled:
            continue
        ok, reason = _ping(endpoint)
        if ok:
            mark_active(atom_id)
        else:
            note_degraded(atom_id, f"endpoint unreachable: {reason}")

    # 3. Snapshot freshness
    snap = _cache_dir() / "snapshots" / "osv-export.json"
    if snap.exists():
        advisory_count = _snapshot_advisory_count(snap)
        if advisory_count == 0:
            note_degraded(
                "check-package-cve",
                "offline CVE snapshot has no indexed advisory entries",
            )
        else:
            age_days = (time.time() - snap.stat().st_mtime) / 86400
            max_age = float(os.environ.get("SAFETY_ORCH_SNAPSHOT_MAX_AGE_DAYS", "14"))
            if age_days > max_age:
                note_degraded(
                    "check-package-cve",
                    f"offline snapshot stale ({age_days:.0f}d > {max_age:.0f}d)",
                )
    else:
        note_degraded(
            "check-package-cve",
            "offline CVE snapshot missing; protection is online-only when OSV is reachable",
        )

    active = total - len(degraded) - len(disabled)
    lines = [
        f"Safety Orchestrator: {active}/{total} fully active "
        f"({len(degraded)} degraded, {len(disabled)} disabled)"
    ]
    for atom_id, reason in degraded.items():
        lines.append(f"  ⚠️ Degraded: {atom_id} ({reason})")
    for atom_id, reason in disabled.items():
        lines.append(f"  ⚠️ Disabled: {atom_id} ({reason})")
    if not degraded and not disabled:
        lines.append("  ✓ All atoms active.")
    return "\n".join(lines)


def _main() -> int:
    """CLI: `python -m helpers.health_status` → prints banner to stdout."""
    print(init_banner())
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
