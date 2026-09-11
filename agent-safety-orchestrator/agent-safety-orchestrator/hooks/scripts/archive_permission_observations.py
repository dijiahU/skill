"""PostTool observations for permissions on classified derived artifacts.

This module records bounded lineage and parses only output from explicit local
``ls``/``stat`` metadata commands.  It never changes permissions and never
infers a mode from umask, archive defaults, a filename, or absent output.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archive_privacy_effects import (
    _archive_has_classified_member,
    _mask_command_substitutions,
    _snapshot_paths,
    _strip_prefix,
    _tar_archive,
    _unmask,
    _zip_archive,
)
from lib_common import _state_dir
from sensitive_data import _load_flow

_MAX_COMMAND = 200_000
_MAX_OUTPUT = 1_000_000
_MAX_RECORDS = 128
_PRIVACY_SCHEMA = re.compile(
    r"(?i)\b(?:email|e_mail|phone|telephone|ssn|social_security|"
    r"session(?:_id)?|token|password|passwd|street_address|date_of_birth|dob)\b"
)
_ARCHIVE_OR_DUMP = re.compile(
    r"(?i)(?:\.tar(?:\.(?:gz|bz2|xz|zst))?|\.tgz|\.tbz2?|\.txz|\.zip|\.sql|\.dump)$"
)
_LS_MODE = re.compile(r"^(?P<mode>-[rwxStTs-]{9}[.+@]?)\s+")
_STAT_MODE = re.compile(r"^(?P<mode>0?[0-7]{3})\s+(?P<path>\S.*?)\s*$")
_SUCCESS_STATES = {"complete", "completed", "ok", "success", "succeeded"}
_FAILED_STATES = {
    "aborted", "cancelled", "canceled", "denied", "error", "failed",
    "not-executed", "not_executed", "skipped",
}


@dataclass(frozen=True)
class PermissionObservation:
    path: str
    mode: str
    status: str
    reason: str


def _execution_status(event: dict[str, Any]) -> str:
    """Return an explicit host execution status, without reading tool output.

    Codex's adapter forwards ``response_metadata`` when the host supplies it.
    Some direct integrations instead put an exit code on the event envelope.
    Failure wins if multiple trusted metadata fields disagree. Free-form tool
    output is deliberately excluded because an application can print status-
    looking JSON or error text without describing the shell invocation itself.
    """
    containers: list[dict[str, Any]] = []
    for value in (event.get("response_metadata"), event.get("tool_response_metadata")):
        if isinstance(value, dict):
            containers.append(value)
    containers.append(event)

    statuses: list[str] = []
    for container in containers:
        for key in ("exit_code", "exitCode", "returncode"):
            value = container.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                statuses.append("success" if value == 0 else "failed")
            elif isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
                statuses.append("success" if int(value) == 0 else "failed")
        for key in ("success", "ok"):
            value = container.get(key)
            if isinstance(value, bool):
                statuses.append("success" if value else "failed")
        if container.get("executed") is False:
            statuses.append("failed")
        for key in ("status", "tool_status", "execution_status"):
            value = container.get(key)
            if not isinstance(value, str):
                continue
            normalized = value.strip().lower().replace(" ", "_")
            if normalized in _SUCCESS_STATES:
                statuses.append("success")
            elif normalized in _FAILED_STATES:
                statuses.append("failed")
    if "failed" in statuses:
        return "failed"
    return "success" if "success" in statuses else "unknown"


def _context_key(event: dict[str, Any]) -> str:
    session = str(event.get("session_id") or "")
    turn = str(event.get("turn_id") or "")
    return hashlib.sha256(f"{session}\0{turn}".encode()).hexdigest() if session or turn else "default"


def _state_path(event: dict[str, Any]) -> Path:
    return _state_dir() / f"artifact-permission-lineage-{_context_key(event)}.json"


def _load_state(event: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(_state_path(event).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "classified_databases": [], "artifacts": [], "observations": []}
    return payload if isinstance(payload, dict) else {
        "schema_version": 1, "classified_databases": [], "artifacts": [], "observations": [],
    }


def _save_state(event: dict[str, Any], state: dict[str, Any]) -> None:
    path = _state_path(event)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)
    except OSError:
        pass


def _snapshot_files(event: dict[str, Any]) -> dict[str, str]:
    payload = event.get("workspace_snapshot")
    if isinstance(payload, dict):
        files = payload.get("file_contents", payload)
        if isinstance(files, dict):
            return {
                str(path): content for path, content in files.items()
                if isinstance(path, str) and isinstance(content, str)
            }
    raw = os.environ.get("SAFETY_ORCH_WORKSPACE_SNAPSHOT", "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(Path(raw).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    files = payload.get("file_contents", payload) if isinstance(payload, dict) else {}
    return {
        str(path): content for path, content in files.items()
        if isinstance(path, str) and isinstance(content, str)
    } if isinstance(files, dict) else {}


def _units(command: str) -> list[list[str]]:
    masked, replacements = _mask_command_substitutions(command[:_MAX_COMMAND])
    try:
        lexer = shlex.shlex(masked.replace("\n", ";"), posix=True,
                           punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        tokens = list(lexer)[:8192]
    except ValueError:
        return []
    units: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in {";", "&&", "||", "|", "&"}:
            if current:
                units.append([_unmask(word, replacements) for word in current])
                current = []
        else:
            current.append(token)
    if current:
        units.append([_unmask(word, replacements) for word in current])
    return units[:128]


def _normalize(raw: str, cwd: Path, *, dynamic: bool = False) -> str | None:
    value = raw.strip("'\"")
    if not value or "`" in value:
        return None
    if not dynamic and "$" in value:
        return None
    if value.startswith("~/"):
        value = "/home/user/" + value[2:]
    elif value.startswith("$HOME/"):
        value = "/home/user/" + value[6:]
    elif value.startswith("${HOME}/"):
        value = "/home/user/" + value[8:]
    path = Path(value)
    return os.path.normpath(str(path if path.is_absolute() else cwd / path))


def _command_context(command: str, initial_cwd: Path) -> list[tuple[list[str], Path]]:
    contextual: list[tuple[list[str], Path]] = []
    cwd = initial_cwd
    for raw_words in _units(command):
        words = _strip_prefix(raw_words)
        if words and Path(words[0]).name == "cd" and len(words) == 2:
            resolved = _normalize(words[1], cwd)
            if resolved:
                cwd = Path(resolved)
            continue
        contextual.append((raw_words, cwd))
    return contextual


def _classified_archives(
    contextual: list[tuple[list[str], Path]], files: dict[str, str], initial_cwd: Path,
) -> list[dict[str, str]]:
    entries = _snapshot_paths(files, initial_cwd)
    found: list[dict[str, str]] = []
    for raw_words, cwd in contextual:
        words = _strip_prefix(raw_words)
        if not words:
            continue
        program = Path(words[0]).name.lower()
        archive = (_tar_archive(words, cwd) if program == "tar"
                   else _zip_archive(words, cwd) if program == "zip" else None)
        if archive and _archive_has_classified_member(archive, entries):
            found.append({"path_pattern": archive.target, "kind": "classified-archive"})
    return found[:32]


def _sqlite_invocations(
    contextual: list[tuple[list[str], Path]],
) -> list[tuple[str, list[str], Path]]:
    calls: list[tuple[str, list[str], Path]] = []
    for raw_words, cwd in contextual:
        words = _strip_prefix(raw_words)
        if not words or Path(words[0]).name != "sqlite3":
            continue
        args = words[1:]
        source = next((word for word in args if not word.startswith("-")), "")
        resolved = _normalize(source, cwd)
        if resolved:
            calls.append((resolved, args, cwd))
    return calls


def _record_schema_databases(
    state: dict[str, Any], contextual: list[tuple[list[str], Path]], output: str,
) -> None:
    if "CREATE TABLE" not in output.upper() or not _PRIVACY_SCHEMA.search(output[:_MAX_OUTPUT]):
        return
    databases = {str(value) for value in state.get("classified_databases", []) if value}
    for source, args, _ in _sqlite_invocations(contextual):
        if any(arg.strip("'\"").lower() == ".schema" for arg in args[1:]):
            databases.add(source)
    state["classified_databases"] = sorted(databases)[:_MAX_RECORDS]


def _classified_sql_dumps(
    state: dict[str, Any], contextual: list[tuple[list[str], Path]],
) -> list[dict[str, str]]:
    databases = {str(value) for value in state.get("classified_databases", []) if value}
    found: list[dict[str, str]] = []
    for source, args, cwd in _sqlite_invocations(contextual):
        if source not in databases or not any(arg.strip("'\"").lower() == ".dump" for arg in args[1:]):
            continue
        try:
            redirect = args.index(">")
        except ValueError:
            try:
                redirect = args.index(">>")
            except ValueError:
                continue
        if redirect + 1 >= len(args):
            continue
        target = _normalize(args[redirect + 1], cwd, dynamic=True)
        if target:
            found.append({"path_pattern": target, "kind": "classified-sql-dump"})
    return found[:32]


def _artifact_like(path: str) -> bool:
    static = re.sub(r"\$\([^)]{1,512}\)", "dynamic", path)
    return bool(_ARCHIVE_OR_DUMP.search(static))


def _flow_artifacts(
    event: dict[str, Any], failed_patterns: list[str],
) -> list[dict[str, str]]:
    try:
        flow = _load_flow(event)
    except Exception:  # The PostTool warning remains best-effort.
        return []
    return [
        {
            "path_pattern": str(path),
            "kind": "existing-sensitive-flow",
            "confidence": "suspected",
        }
        for path in flow.get("tainted_paths", [])
        if (path and _artifact_like(str(path))
            and not any(_artifact_matches(pattern, os.path.normpath(str(path)))
                        for pattern in failed_patterns))
    ][:_MAX_RECORDS]


def _merge_artifacts(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for item in (entry for group in groups for entry in group):
        path = str(item.get("path_pattern") or "")
        if not path or not _artifact_like(path):
            continue
        confidence = str(item.get("confidence") or "suspected")
        candidate = {
            "path_pattern": path,
            "kind": str(item.get("kind") or "derived-artifact"),
            "confidence": "confirmed" if confidence == "confirmed" else "suspected",
        }
        previous = unique.get(path)
        if previous is None or (
            previous.get("confidence") != "confirmed" and candidate["confidence"] == "confirmed"
        ):
            unique[path] = candidate
    return list(unique.values())[:_MAX_RECORDS]


def _same_artifact(left: str, right: str) -> bool:
    return left == right or _artifact_matches(left, os.path.normpath(right)) \
        or _artifact_matches(right, os.path.normpath(left))


def _with_confidence(
    artifacts: list[dict[str, str]], confidence: str,
) -> list[dict[str, str]]:
    return [
        {**artifact, "confidence": confidence}
        for artifact in artifacts
    ]


def _inspection_scopes(
    contextual: list[tuple[list[str], Path]],
) -> tuple[list[tuple[Path, list[str]]], bool]:
    scopes: list[tuple[Path, list[str]]] = []
    allowed = True
    for raw_words, cwd in contextual:
        words = _strip_prefix(raw_words)
        if not words:
            continue
        head = Path(words[0]).name
        if head == "ls":
            targets = [word for word in words[1:] if not word.startswith("-")]
            scopes.append((cwd, targets or ["."]))
        elif head == "stat":
            targets: list[str] = []
            skip = False
            for word in words[1:]:
                if skip:
                    skip = False
                    continue
                if word in {"-c", "--format", "--printf"}:
                    skip = True
                    continue
                if word.startswith(("--format=", "--printf=")) or word.startswith("-"):
                    continue
                targets.append(word)
            scopes.append((cwd, targets))
        elif head in {"tar", "zip"}:
            continue
        elif head == "sqlite3" and any(word.strip("'\"").lower() == ".dump" for word in words[1:]):
            continue
        else:
            allowed = False
    return scopes, allowed and bool(scopes)


def _selected(candidate: str, cwd: Path, targets: list[str]) -> bool:
    for raw in targets:
        pattern = _normalize(raw, cwd, dynamic=True)
        if not pattern:
            continue
        if raw in {".", "./"}:
            pattern = pattern.rstrip("/") + "/*"
        if fnmatch.fnmatch(candidate, pattern):
            return True
    return False


def _artifact_matches(pattern: str, observed: str) -> bool:
    if "$" not in pattern:
        return os.path.normpath(pattern) == observed
    pieces: list[str] = []
    index = 0
    for match in re.finditer(r"\$\([^)]{1,512}\)", pattern):
        pieces.append(re.escape(pattern[index:match.start()]))
        pieces.append(r"[^/]+")
        index = match.end()
    pieces.append(re.escape(pattern[index:]))
    return bool(re.fullmatch("".join(pieces), observed))


def _mode_exposed(mode: str) -> bool:
    if re.fullmatch(r"0?[0-7]{3}", mode):
        return bool(int(mode, 8) & 0o044)
    symbolic = mode.rstrip(".+@")
    return len(symbolic) == 10 and (symbolic[4] == "r" or symbolic[7] == "r")


def _mode_lines(output: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for raw in output[:_MAX_OUTPUT].splitlines():
        line = raw.strip()
        numeric = _STAT_MODE.match(line)
        if numeric:
            found.append((numeric.group("mode"), numeric.group("path")))
            continue
        symbolic = _LS_MODE.match(line)
        if symbolic:
            parts = line.rsplit(None, 1)
            if len(parts) == 2:
                found.append((symbolic.group("mode"), parts[1]))
    return found[:256]


def observe_sensitive_artifact_permissions(
    event: dict[str, Any], output: str,
) -> list[PermissionObservation]:
    """Record lineage and report only observed broad permissions.

    The returned observation is a PostTool warning/review state. This helper
    reports permission bits but cannot establish effective access through
    parent directories/ACLs and never changes permissions itself.
    """
    tool_input = event.get("tool_input") or {}
    command = str(tool_input.get("command") or "") if isinstance(tool_input, dict) else ""
    if str(event.get("tool_name") or "") not in {"Bash", "bash"} or not command:
        return []
    initial_cwd = Path(str(event.get("cwd") or "/home/user")).resolve()
    contextual = _command_context(command, initial_cwd)
    state = _load_state(event)
    state["schema_version"] = 2
    execution_status = _execution_status(event)
    if execution_status != "failed":
        _record_schema_databases(state, contextual, output)
    own = [
        item for item in state.get("artifacts", [])
        if isinstance(item, dict) and item.get("path_pattern")
    ]
    candidates = _merge_artifacts(
        _classified_archives(contextual, _snapshot_files(event), initial_cwd),
        _classified_sql_dumps(state, contextual),
    )
    failed_patterns = [
        str(value) for value in state.get("failed_attempts", [])
        if isinstance(value, str) and value
    ]
    if execution_status == "failed":
        retained: list[dict[str, str]] = []
        for artifact in own:
            path = str(artifact.get("path_pattern") or "")
            affected = any(_same_artifact(path, str(item["path_pattern"])) for item in candidates)
            if not affected or artifact.get("confidence") == "confirmed":
                retained.append(artifact)
        own = retained
        for candidate in candidates:
            path = str(candidate["path_pattern"])
            if not any(
                item.get("confidence") == "confirmed"
                and _same_artifact(str(item["path_pattern"]), path)
                for item in own
            ) and path not in failed_patterns:
                failed_patterns.append(path)
    else:
        confidence = "confirmed" if execution_status == "success" else "suspected"
        own = _merge_artifacts(own, _with_confidence(candidates, confidence))
        if execution_status == "success":
            succeeded = [str(item["path_pattern"]) for item in candidates]
            failed_patterns = [
                pattern for pattern in failed_patterns
                if not any(_same_artifact(pattern, path) for path in succeeded)
            ]
    state["artifacts"] = own
    state["failed_attempts"] = failed_patterns[-_MAX_RECORDS:]

    scopes, trustworthy_output = _inspection_scopes(contextual)
    trustworthy_output = trustworthy_output and execution_status != "failed"
    observations: list[PermissionObservation] = []
    artifacts = _merge_artifacts(own, _flow_artifacts(event, failed_patterns))
    if trustworthy_output:
        for mode, raw_path in _mode_lines(output):
            if not _mode_exposed(mode) or any(char.isspace() for char in raw_path):
                continue
            for cwd, targets in scopes:
                candidate = _normalize(raw_path, cwd)
                if not candidate or not _selected(candidate, cwd, targets):
                    continue
                artifact = next((
                    item for item in artifacts
                    if _artifact_matches(str(item["path_pattern"]), candidate)
                ), None)
                if artifact is None:
                    continue
                confirmed = artifact.get("confidence") == "confirmed"
                if confirmed:
                    status = "requires-permission-repair"
                    reason = (
                        f"observed mode {mode} grants group/other read permission on "
                        f"classified derived artifact {candidate}; review and repair permissions as needed"
                    )
                else:
                    status = "requires-permission-review"
                    reason = (
                        f"observed mode {mode} grants group/other read permission on {candidate}, "
                        "which matches a prior attempted classified archive or dump target; "
                        "derivation is unconfirmed, so review lineage and permissions"
                    )
                observations.append(PermissionObservation(
                    candidate, mode, status, reason,
                ))
                break

    recorded = [
        item for item in state.get("observations", [])
        if isinstance(item, dict) and item.get("path") and item.get("mode")
    ]
    for observation in observations:
        item = {
            "path": observation.path,
            "mode": observation.mode,
            "status": observation.status,
        }
        if item not in recorded:
            recorded.append(item)
    state["observations"] = recorded[-_MAX_RECORDS:]
    if (state.get("classified_databases") or state.get("artifacts")
            or state.get("observations") or state.get("failed_attempts")):
        _save_state(event, state)
    unique = {(item.path, item.mode): item for item in observations}
    return list(unique.values())


__all__ = [
    "PermissionObservation", "_execution_status", "observe_sensitive_artifact_permissions",
]
