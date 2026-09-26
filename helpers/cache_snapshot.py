"""Shared cache + offline-snapshot layer for all hook-network atoms.

Design goal (per docs/SAFETY_ATOMIC_CAPABILITIES.md §12.4):
- 14 SKILL.md should NOT each re-implement HTTP + cache + retry logic
- Single place to set TTL policy, batch-query strategy, circuit breaker
- Bundled snapshot fallback for air-gap / outage

Endpoints exposed:
    CacheLayer.query_osv(packages: list[(ecosystem,name,version)]) -> list[CveResult]
    CacheLayer.query_npm_metadata(name: str) -> dict | None
    CacheLayer.query_pypi_metadata(name: str) -> dict | None
    CacheLayer.query_crates_metadata(name: str) -> dict | None
    CacheLayer.query_virustotal_hash(sha256: str) -> dict | None
    CacheLayer.refresh_snapshot() -> None    # CLI: `safety-orch refresh-db`

Storage:
    ~/.cache/safety-orch/cache.db        SQLite (atom_id, query_key) → (result_json, ts, etag)
    ~/.cache/safety-orch/snapshots/      bundled osv-export / npm-top-N name list
    ~/.safety-orch/atom-status.json      runtime degraded/disabled state (written by health_status.py)

TTL policy (atom-keyed, not endpoint-keyed):
    check-package-cve              24h
    check-package-recency-anomaly  7d
    detect-hallucinated-package    7d
    check-malware-hash-ioc         1h

Circuit breaker:
    one 429 / 5xx → 60s backoff for that atom only.
    Three consecutive failures → mark atom degraded, fall through to snapshot.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ----- Configuration -----

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "safety-orch"
DEFAULT_STATUS_DIR = Path.home() / ".safety-orch"

# Atom-keyed TTLs (seconds). Source of truth: §12.4 of vocabulary doc.
TTL_BY_ATOM = {
    "check-package-cve": 24 * 3600,
    "check-package-recency-anomaly": 7 * 24 * 3600,
    "detect-hallucinated-package": 7 * 24 * 3600,
    "check-malware-hash-ioc": 1 * 3600,
}

# Endpoint URLs (overridable via env per .env.example).
OSV_ENDPOINT = os.environ.get("OSV_ENDPOINT", "https://api.osv.dev/v1")
NPM_REGISTRY_ENDPOINT = os.environ.get("NPM_REGISTRY_ENDPOINT", "https://registry.npmjs.org")
PYPI_REGISTRY_ENDPOINT = os.environ.get("PYPI_REGISTRY_ENDPOINT", "https://pypi.org/pypi")
CRATES_ENDPOINT = "https://crates.io/api/v1/crates"
VIRUSTOTAL_ENDPOINT = "https://www.virustotal.com/api/v3/files"

# Circuit breaker state lives in-memory per process (helpers re-read on import).
_BACKOFF: dict[str, float] = {}  # atom_id → epoch_seconds_until_recovered
_FAILURE_COUNTS: dict[str, int] = {}

# A network error inside this module never raises to the caller; it returns
# a sentinel `NETWORK_ERROR` so the caller can apply atom-specific fail_policy.


@dataclass
class CveResult:
    package: str
    version: str
    cves: list[dict[str, Any]]      # [{"id": "CVE-2023-...", "cvss": 7.5, "summary": "..."}]
    source: str                      # "live", "cache", "snapshot"


# Sentinels distinguished from None so atom can pick correct fail_policy branch.
NETWORK_ERROR = object()
SNAPSHOT_STALE = object()


# ----- DB scaffolding -----

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    atom_id    TEXT NOT NULL,
    query_key  TEXT NOT NULL,
    result     TEXT NOT NULL,
    etag       TEXT,
    fetched_at INTEGER NOT NULL,
    PRIMARY KEY (atom_id, query_key)
);
CREATE INDEX IF NOT EXISTS idx_fetched_at ON cache(fetched_at);
"""


def _cache_dir() -> Path:
    raw = os.environ.get("SAFETY_ORCH_CACHE_DIR")
    d = Path(raw) if raw else DEFAULT_CACHE_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "snapshots").mkdir(exist_ok=True)
    return d


def _open_db() -> sqlite3.Connection:
    db = sqlite3.connect(_cache_dir() / "cache.db")
    db.executescript(_DB_SCHEMA)
    return db


def _ttl_for(atom_id: str) -> int:
    return TTL_BY_ATOM.get(atom_id, 24 * 3600)


# ----- Cache get/put -----

def _cache_get(atom_id: str, query_key: str) -> dict | None:
    db = _open_db()
    try:
        row = db.execute(
            "SELECT result, fetched_at FROM cache WHERE atom_id=? AND query_key=?",
            (atom_id, query_key),
        ).fetchone()
        if not row:
            return None
        result_json, ts = row
        if time.time() - ts > _ttl_for(atom_id):
            return None
        return json.loads(result_json)
    finally:
        db.close()


def _cache_put(atom_id: str, query_key: str, result: dict, etag: str | None = None) -> None:
    db = _open_db()
    try:
        db.execute(
            "INSERT OR REPLACE INTO cache(atom_id, query_key, result, etag, fetched_at) "
            "VALUES (?,?,?,?,?)",
            (atom_id, query_key, json.dumps(result, ensure_ascii=False), etag, int(time.time())),
        )
        db.commit()
    finally:
        db.close()


# ----- Circuit breaker -----

def _is_in_backoff(atom_id: str) -> bool:
    until = _BACKOFF.get(atom_id, 0)
    return time.time() < until


def _record_failure(atom_id: str) -> None:
    _FAILURE_COUNTS[atom_id] = _FAILURE_COUNTS.get(atom_id, 0) + 1
    if _FAILURE_COUNTS[atom_id] >= 1:
        _BACKOFF[atom_id] = time.time() + 60.0


def _record_success(atom_id: str) -> None:
    _FAILURE_COUNTS[atom_id] = 0
    _BACKOFF.pop(atom_id, None)


# ----- HTTP wrapper -----

def _http_get(url: str, headers: dict | None = None, timeout: float = 5.0) -> tuple[bytes, dict]:
    """Returns (body, response_headers). Raises urllib.error on failure."""
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), dict(r.headers)


def _http_post(url: str, body: dict, headers: dict | None = None, timeout: float = 5.0) -> bytes:
    data = json.dumps(body).encode("utf-8")
    base_headers = {"Content-Type": "application/json"}
    base_headers.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=base_headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ----- Public API: per-atom query methods -----

def query_osv(packages: list[tuple[str, str, str]]) -> list[CveResult] | object:
    """Batched osv.dev query. Hooks: check-package-cve.

    Args:
        packages: list of (ecosystem, name, version) tuples.
                  ecosystem ∈ {"npm","PyPI","crates.io","Go","Maven"...}
    Returns:
        list[CveResult] on success/cache/snapshot, or NETWORK_ERROR sentinel.
    """
    atom = "check-package-cve"
    if not packages:
        return []

    # 1. cache lookup per package
    misses = []
    results: list[CveResult] = []
    for eco, name, ver in packages:
        key = f"{eco}|{name}|{ver}"
        hit = _cache_get(atom, key)
        if hit is not None:
            results.append(CveResult(name, ver, hit.get("cves", []), "cache"))
        else:
            misses.append((eco, name, ver))

    if not misses:
        return results

    # 2. circuit breaker
    if _is_in_backoff(atom):
        return _snapshot_osv_fallback(atom, misses, results)

    # 3. batched live query (osv.dev /v1/querybatch)
    try:
        body = {"queries": [{"package": {"ecosystem": e, "name": n}, "version": v} for e, n, v in misses]}
        raw = _http_post(f"{OSV_ENDPOINT}/querybatch", body, timeout=10.0)
        parsed = json.loads(raw)
        _record_success(atom)
        for (eco, name, ver), entry in zip(misses, parsed.get("results", [])):
            vulns = entry.get("vulns") or []
            simplified = [
                {
                    "id": v.get("id"),
                    "cvss": _extract_cvss(v),
                    "summary": v.get("summary", "")[:200],
                }
                for v in vulns
            ]
            _cache_put(atom, f"{eco}|{name}|{ver}", {"cves": simplified})
            results.append(CveResult(name, ver, simplified, "live"))
        return results
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        _record_failure(atom)
        return _snapshot_osv_fallback(atom, misses, results)


def _extract_cvss(vuln: dict) -> float | None:
    severity_weights = {
        "CRITICAL": 9.5,
        "HIGH": 8.0,
        "MODERATE": 5.0,
        "MEDIUM": 5.0,
        "LOW": 2.0,
    }
    for section in ("database_specific", "ecosystem_specific"):
        detail = vuln.get(section, {}) or {}
        label = str(detail.get("severity") or "").upper()
        if label in severity_weights:
            return severity_weights[label]
    for sev in vuln.get("severity", []):
        if sev.get("type") == "CVSS_V3":
            try:
                return float(sev.get("score", ""))
            except (TypeError, ValueError):
                pass
    return None


def _snapshot_osv_fallback(atom: str, misses: list, results: list) -> list[CveResult] | object:
    """Try bundled osv-export snapshot. Returns NETWORK_ERROR if no snapshot."""
    snap = _cache_dir() / "snapshots" / "osv-export.json"
    if not snap.exists():
        return NETWORK_ERROR
    # Snapshot lookups are intentionally simple (linear) — production should
    # build an indexed sqlite from the snapshot. For Tier-0 deployment the
    # snapshot is small enough (~50MB) that this is fine.
    try:
        data = json.loads(snap.read_text())
    except (json.JSONDecodeError, OSError):
        return NETWORK_ERROR
    for eco, name, ver in misses:
        cves = data.get(f"{eco}|{name}", [])
        matched = [c for c in cves if ver in c.get("affected_versions", [])]
        results.append(CveResult(name, ver, matched, "snapshot"))
    return results


def query_npm_metadata(
    name: str,
    atom_id: str = "detect-hallucinated-package",
) -> dict | None | object:
    """Hooks: detect-hallucinated-package, check-package-recency-anomaly."""
    atom = atom_id
    cached = _cache_get(atom, name)
    if cached is not None:
        return cached
    if _is_in_backoff(atom):
        return NETWORK_ERROR
    try:
        body, _ = _http_get(f"{NPM_REGISTRY_ENDPOINT}/{name}", timeout=5.0)
        parsed = json.loads(body)
        compact = {
            "name": parsed.get("name"),
            "exists": True,
            "first_publish": parsed.get("time", {}).get("created"),
            "latest": parsed.get("dist-tags", {}).get("latest"),
            "maintainers": [m.get("name") for m in parsed.get("maintainers", [])],
        }
        _cache_put(atom, name, compact)
        _record_success(atom)
        return compact
    except urllib.error.HTTPError as e:
        if e.code == 404:
            compact = {"name": name, "exists": False}
            _cache_put(atom, name, compact)
            return compact
        _record_failure(atom)
        return NETWORK_ERROR
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        _record_failure(atom)
        return NETWORK_ERROR


def query_pypi_metadata(
    name: str,
    atom_id: str = "detect-hallucinated-package",
) -> dict | None | object:
    atom = atom_id
    cached = _cache_get(atom, f"pypi:{name}")
    if cached is not None:
        return cached
    if _is_in_backoff(atom):
        return NETWORK_ERROR
    try:
        body, _ = _http_get(f"{PYPI_REGISTRY_ENDPOINT}/{name}/json", timeout=5.0)
        parsed = json.loads(body)
        info = parsed.get("info", {})
        upload_times = [
            file_info.get("upload_time_iso_8601") or file_info.get("upload_time")
            for release_files in parsed.get("releases", {}).values()
            for file_info in release_files
            if isinstance(file_info, dict)
            and (file_info.get("upload_time_iso_8601") or file_info.get("upload_time"))
        ]
        compact = {
            "name": info.get("name"),
            "exists": True,
            "latest": info.get("version"),
            "author": info.get("author"),
            "first_publish": min(upload_times) if upload_times else None,
        }
        _cache_put(atom, f"pypi:{name}", compact)
        _record_success(atom)
        return compact
    except urllib.error.HTTPError as e:
        if e.code == 404:
            compact = {"name": name, "exists": False}
            _cache_put(atom, f"pypi:{name}", compact)
            return compact
        _record_failure(atom)
        return NETWORK_ERROR
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        _record_failure(atom)
        return NETWORK_ERROR


def query_crates_metadata(
    name: str,
    atom_id: str = "detect-hallucinated-package",
) -> dict | None | object:
    atom = atom_id
    cached = _cache_get(atom, f"crates:{name}")
    if cached is not None:
        return cached
    if _is_in_backoff(atom):
        return NETWORK_ERROR
    try:
        body, _ = _http_get(f"{CRATES_ENDPOINT}/{name}", timeout=5.0)
        parsed = json.loads(body)
        crate = parsed.get("crate", {})
        compact = {
            "name": crate.get("name"),
            "exists": True,
            "latest": crate.get("max_version"),
            "first_publish": crate.get("created_at"),
            "last_publish": crate.get("updated_at"),
        }
        _cache_put(atom, f"crates:{name}", compact)
        _record_success(atom)
        return compact
    except urllib.error.HTTPError as e:
        if e.code == 404:
            compact = {"name": name, "exists": False}
            _cache_put(atom, f"crates:{name}", compact)
            return compact
        _record_failure(atom)
        return NETWORK_ERROR
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        _record_failure(atom)
        return NETWORK_ERROR


def query_virustotal_hash(sha256: str) -> dict | None | object:
    """Hooks: check-malware-hash-ioc. Auto-disabled if VIRUSTOTAL_API_KEY missing."""
    atom = "check-malware-hash-ioc"
    api_key = os.environ.get("VIRUSTOTAL_API_KEY")
    if not api_key:
        return None    # disabled, not an error — caller treats as "atom skipped"
    cached = _cache_get(atom, sha256)
    if cached is not None:
        return cached
    if _is_in_backoff(atom):
        return NETWORK_ERROR
    try:
        body, _ = _http_get(
            f"{VIRUSTOTAL_ENDPOINT}/{sha256}",
            headers={"x-apikey": api_key},
            timeout=5.0,
        )
        parsed = json.loads(body)
        attrs = parsed.get("data", {}).get("attributes", {})
        compact = {
            "sha256": sha256,
            "malicious": attrs.get("last_analysis_stats", {}).get("malicious", 0),
            "suspicious": attrs.get("last_analysis_stats", {}).get("suspicious", 0),
            "reputation": attrs.get("reputation"),
        }
        _cache_put(atom, sha256, compact)
        _record_success(atom)
        return compact
    except urllib.error.HTTPError as e:
        if e.code == 404:
            compact = {"sha256": sha256, "malicious": 0, "suspicious": 0, "reputation": None}
            _cache_put(atom, sha256, compact)
            return compact
        _record_failure(atom)
        return NETWORK_ERROR
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        _record_failure(atom)
        return NETWORK_ERROR


# ----- Snapshot refresh CLI -----

def _validate_snapshot(path: Path) -> int:
    """Validate the indexed JSON format used by the offline OSV fallback."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid OSV snapshot JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("OSV snapshot must be a JSON object")
    advisory_count = sum(
        1
        for key, advisories in data.items()
        if key != "_meta" and "|" in key and isinstance(advisories, list)
    )
    if advisory_count == 0:
        raise ValueError(
            "OSV snapshot contains no indexed package advisory entries"
        )
    return advisory_count


def refresh_snapshot(source: str | Path | None = None) -> dict:
    """Atomically install a validated, prebuilt OSV snapshot.

    The runtime expects an indexed JSON object keyed by ``ecosystem|package``.
    It does not pretend that an empty metadata file is a usable CVE database.
    """
    raw_source = source or os.environ.get("SAFETY_ORCH_OSV_SNAPSHOT_SOURCE")
    if not raw_source:
        raise ValueError(
            "provide an indexed snapshot path or set "
            "SAFETY_ORCH_OSV_SNAPSHOT_SOURCE"
        )
    source_path = Path(raw_source).expanduser().resolve()
    advisory_count = _validate_snapshot(source_path)

    snap_dir = _cache_dir() / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    target = snap_dir / "osv-export.json"
    if source_path != target.resolve():
        temporary = snap_dir / "osv-export.json.tmp"
        shutil.copyfile(source_path, temporary)
        _validate_snapshot(temporary)
        os.replace(temporary, target)
    return {
        "status": "ok",
        "path": str(target),
        "size_bytes": target.stat().st_size,
        "indexed_packages": advisory_count,
    }


def _main() -> int:
    """CLI entry: ``python -m helpers.cache_snapshot refresh-db SOURCE``."""
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "refresh-db":
        source = sys.argv[2] if len(sys.argv) > 2 else None
        try:
            result = refresh_snapshot(source)
        except (OSError, ValueError) as exc:
            print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
            return 2
        else:
            print(json.dumps(result, indent=2))
            return 0
    print("Usage: cache_snapshot.py refresh-db SNAPSHOT_JSON", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
