"""Bounded review of writes over configured, existing SSH identities.

This module parses shell text and trusted UserPromptSubmit state.  It does not
read private-key bytes from the live filesystem and never executes a command.
Only a literal ``cp SOURCE DESTINATION`` whose destination is both present in
the workspace snapshot and referenced by an observed SSH ``IdentityFile`` is
considered confirmed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from pathlib import Path
from typing import Any, Mapping

from lib_common import _state_dir


_ROTATION_ACTION = re.compile(
    r"(?is)(?:"
    r"\b(?:rotate|rotation|replace|replacement|regenerate|renew|overwrite|change)\b[^.\n]{0,60}"
    r"\b(?:ssh\s+)?(?:private\s+key|identity(?:\s+file)?|id_(?:rsa|dsa|ecdsa|ed25519))\b|"
    r"\b(?:ssh\s+)?(?:private\s+key|identity(?:\s+file)?|id_(?:rsa|dsa|ecdsa|ed25519))\b"
    r"[^.\n]{0,60}\b(?:rotate|rotation|replace|replacement|regenerate|renew|overwrite|change)\b|"
    r"(?:轮换|更换|替换|重建|重新生成|覆盖)[^。\n]{0,40}(?:SSH\s*)?(?:私钥|身份密钥)|"
    r"(?:SSH\s*)?(?:私钥|身份密钥)[^。\n]{0,40}(?:轮换|更换|替换|重建|重新生成|覆盖)"
    r")"
)
_SSH_PATH = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:~|/home/[A-Za-z0-9_.-]+|/root)/\.ssh/"
    r"id_[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*(?=$|[\s`\'\"，。.,:;!?）)])"
)
_PRIVATE_IDENTITY_NAME = re.compile(r"^id_[A-Za-z0-9_.-]+$")
_NON_AUTHORIZING_CONTEXT = re.compile(
    r"(?is)(?:"
    r"\b(?:do\s+not|don['’]t|never|must\s+not|should\s+not)\b[^.\n]{0,45}"
    r"\b(?:rotate|rotation|replace|replacement|regenerate|renew|overwrite|change)\b|"
    r"\b(?:how\s+to|explain|document|instructions?\s+for|dry[- ]run|plan\s+only)\b"
    r"[^.\n]{0,60}\b(?:rotate|rotation|replace|replacement|regenerate|renew|overwrite|change)\b|"
    r"(?:不要|别|禁止|不允许|无需|不需要)[^。\n]{0,30}(?:轮换|更换|替换|重建|重新生成|覆盖)|"
    r"(?:如何|怎么|说明|文档|只做计划)[^。\n]{0,35}(?:轮换|更换|替换|重建|重新生成|覆盖)"
    r")"
)


def _context_key(event: Mapping[str, Any]) -> str:
    session = str(event.get("session_id") or "")
    turn = str(event.get("turn_id") or "")
    return hashlib.sha256(f"{session}\0{turn}".encode()).hexdigest() if session or turn else "default"


def _authorization_path(event: Mapping[str, Any]) -> Path:
    return _state_dir() / f"identity-rotation-auth-{_context_key(event)}.json"


def record_identity_rotation_authorization(event: Mapping[str, Any]) -> None:
    """Record only an explicit SSH private-identity rotation authorization.

    The raw prompt is not retained.  Named identity paths are retained because
    they constrain the authorization; otherwise it is restricted to an
    identity confirmed active by the workspace snapshot at Bash review time.
    """
    prompt = str(
        event.get("prompt") or event.get("user_prompt")
        or event.get("user_message") or ""
    )
    explicit = bool(
        _ROTATION_ACTION.search(prompt) and not _NON_AUTHORIZING_CONTEXT.search(prompt)
    )
    targets = sorted(set(_SSH_PATH.findall(prompt))) if explicit else []
    payload = {
        "schema_version": 1,
        "allowed_class": "configured_active_ssh_private_identity" if explicit else "",
        "allowed_targets": targets,
        "requires_configured_active_target": True,
    }
    path = _authorization_path(event)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


def _authorization(event: Mapping[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(_authorization_path(event).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _logical_home(cwd: Path) -> Path | None:
    parts = cwd.parts
    if len(parts) >= 3 and parts[1] == "home":
        return Path("/") / parts[1] / parts[2]
    if len(parts) >= 2 and parts[1] == "root":
        return Path("/root")
    return None


def _snapshot_paths(snapshot: Mapping[str, str], cwd: Path) -> dict[Path, str]:
    normalized: dict[Path, str] = {}
    for raw, contents in snapshot.items():
        if not isinstance(raw, str) or not isinstance(contents, str):
            continue
        path = Path(raw)
        normalized[(path if path.is_absolute() else cwd / path).resolve()] = contents
    return normalized


def _resolve_literal(raw: str, cwd: Path, home: Path | None) -> Path | None:
    value = raw.strip()
    if not value or any(marker in value for marker in ("$", "`", "*", "?", "[", "]", "{", "}")):
        return None
    if value == "~":
        return home
    if value.startswith("~/"):
        return (home / value[2:]).resolve() if home else None
    path = Path(value)
    return (path if path.is_absolute() else cwd / path).resolve()


def _active_identities(files: Mapping[Path, str], cwd: Path) -> set[Path]:
    active: set[Path] = set()
    for config_path, contents in files.items():
        if config_path.name != "config" or config_path.parent.name != ".ssh":
            continue
        home = config_path.parent.parent
        for line in contents.splitlines():
            match = re.match(r"^\s*IdentityFile\s+(.+?)\s*$", line, re.IGNORECASE)
            if not match:
                continue
            try:
                words = shlex.split(match.group(1), comments=True, posix=True)
            except ValueError:
                continue
            if len(words) != 1:
                continue
            identity = _resolve_literal(words[0].replace("%d", str(home)), cwd, home)
            if identity is not None and identity in files:
                active.add(identity)
    return active


def _segments(command: str) -> list[list[str]]:
    try:
        lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        words = list(lexer)
    except ValueError:
        return []
    result: list[list[str]] = []
    current: list[str] = []
    for word in words:
        if word in {";", "&&", "||", "|", "&"}:
            if current:
                result.append(current)
                current = []
        else:
            current.append(word)
    if current:
        result.append(current)
    return result


def _cp_operands(words: list[str]) -> tuple[str, str] | None:
    current = list(words)
    while current and (current[0] in {"sudo", "doas", "command"}
                       or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", current[0])):
        current.pop(0)
    if not current or Path(current.pop(0)).name != "cp":
        return None
    operands: list[str] = []
    options_done = False
    for word in current:
        if not options_done and word == "--":
            options_done = True
            continue
        if not options_done and word.startswith("-"):
            # Destination-directory and suffix options consume an argument or
            # change destination semantics, outside this bounded review.
            if word in {"-t", "--target-directory", "-S", "--suffix"}:
                return None
            continue
        operands.append(word)
    return (operands[0], operands[1]) if len(operands) == 2 else None


def _source_is_reasonable(source: Path, destination: Path) -> bool:
    return (
        source.parent == destination.parent
        and bool(_PRIVATE_IDENTITY_NAME.fullmatch(source.name))
        and not source.name.endswith(".pub")
    )


def _is_authorized(
    event: Mapping[str, Any], source: Path, destination: Path, cwd: Path,
    trusted_home: Path | None,
) -> bool:
    authorization = _authorization(event)
    if authorization.get("allowed_class") != "configured_active_ssh_private_identity":
        return False
    if not _source_is_reasonable(source, destination):
        return False
    named = authorization.get("allowed_targets")
    if not isinstance(named, list) or not named:
        return trusted_home is not None and destination.parent.parent == trusted_home
    allowed = {
        resolved for raw in named if isinstance(raw, str)
        for resolved in [_resolve_literal(raw, cwd, trusted_home)] if resolved is not None
    }
    return destination in allowed


def active_identity_write_risk(
    command: str,
    event: Mapping[str, Any],
    snapshot: Mapping[str, str],
) -> str:
    """Return a reason for a confirmed active private-identity replacement."""
    if not isinstance(command, str) or not command:
        return ""
    cwd = Path(str(event.get("cwd") or "/home/user")).resolve()
    files = _snapshot_paths(snapshot, cwd)
    active = _active_identities(files, cwd)
    if not active:
        return ""
    default_home = _logical_home(cwd)
    for words in _segments(command):
        operands = _cp_operands(words)
        if operands is None:
            continue
        raw_source, raw_destination = operands
        destination = _resolve_literal(raw_destination, cwd, default_home)
        source = _resolve_literal(raw_source, cwd, default_home)
        if destination is not None:
            if destination not in active or destination not in files:
                continue
            if source is None or source == destination:
                continue
            if _is_authorized(event, source, destination, cwd, default_home):
                continue
            return (
                "copy from a different source path would overwrite an existing SSH "
                f"private identity referenced by observed SSH config ({destination}); "
                "a backup does not establish user authorization to rotate the active identity"
            )
    return ""

