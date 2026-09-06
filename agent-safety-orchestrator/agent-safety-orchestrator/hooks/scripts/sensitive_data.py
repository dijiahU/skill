"""Trusted authorization and bounded source-to-sink state for sensitive reads.

Authorization is derived only from an explicit user request or a trusted host
policy.  Ground-truth/task IDs are never consulted.  Raw values may be read
only when the host can replace tool output before the model observes it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from pathlib import Path
from typing import Any

from lib_common import _state_dir

_READERS = {"cat", "head", "tail", "less", "more", "sed", "awk", "jq", "grep", "rg", "cut"}
_NETWORK = {"curl", "wget", "nc", "ncat", "socat", "scp", "rsync"}
_SAFE_ENV_SUFFIXES = {"example", "sample", "template", "dist"}


def _context_key(event: dict[str, Any]) -> str:
    session = str(event.get("session_id") or "")
    turn = str(event.get("turn_id") or "")
    return hashlib.sha256(f"{session}\0{turn}".encode()).hexdigest() if session or turn else "default"


def _auth_path(event: dict[str, Any]) -> Path:
    return _state_dir() / f"sensitive-read-auth-{_context_key(event)}.json"


def _flow_path(event: dict[str, Any]) -> Path:
    return _state_dir() / f"sensitive-flow-{_context_key(event)}.json"


def output_replacement_available() -> bool:
    return (
        os.environ.get("SAFETY_ORCH_MANUAL_BRIDGE", "0") == "1"
        or os.environ.get("SAFETY_ORCH_CAN_REPLACE_TOOL_OUTPUT", "0") == "1"
    )


def _sensitive_class(raw: str) -> str:
    value = raw.strip("'\" ,").lower().replace("$home", "~")
    leaf = value.rsplit("/", 1)[-1]
    if leaf == ".env" or (leaf.startswith(".env.") and leaf.removeprefix(".env.") not in _SAFE_ENV_SUFFIXES):
        return "dotenv"
    if "/.ssh/" in value or value.startswith(("~/.ssh/", ".ssh/")):
        return "private_key" if leaf.startswith("id_") and not leaf.endswith(".pub") else ""
    if value.endswith(("/.aws/credentials", "/.kube/config", "/.cargo/credentials", "/.cargo/credentials.toml", "/.npmrc", "/.netrc", "/.git-credentials", "/.vault-token", "/.docker/config.json", "/.config/gh/hosts.yml", "/.m2/settings.xml")):
        return "credential_file"
    if value.endswith(("terraform.tfstate", "terraform.tfstate.backup")):
        return "credential_file"
    if re.fullmatch(r"(?:service[_-]?account|credentials?|secrets?)[^/]*\.json", leaf):
        return "credential_file"
    if re.search(r"(?:^|/)credentials/(?:[^/]+)$", value) or "vault-token" in leaf:
        return "credential_file"
    if value in {"/etc/shadow", "/etc/sudoers"} or value.startswith("/etc/sudoers.d/"):
        return "access_control"
    return ""


def _segments(command: str) -> list[list[str]]:
    try:
        lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        words = list(lexer)
    except ValueError:
        return []
    segments, current = [], []
    for word in words:
        if word in {";", "&&", "||", "|"}:
            if current:
                segments.append(current); current = []
        else:
            current.append(word)
    if current:
        segments.append(current)
    return segments


def sensitive_read_paths(command: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for words in _segments(command):
        while words and (words[0] in {"sudo", "doas", "command"} or "=" in words[0]):
            words = words[1:]
        if not words or Path(words[0]).name not in _READERS:
            continue
        for word in words[1:]:
            if word.startswith("-") or word in {"p", "d", "s"}:
                continue
            kind = _sensitive_class(word)
            if kind and (word, kind) not in found:
                found.append((word, kind))
    return found


def _trusted_policy() -> dict[str, Any]:
    raw = os.environ.get("SAFETY_ORCH_SENSITIVE_READ_POLICY_JSON", "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def record_prompt_authorization(event: dict[str, Any]) -> None:
    """Persist only narrow intent classes, never the user prompt or secrets."""
    prompt = str(event.get("prompt") or event.get("user_prompt") or "")
    allowed: list[str] = []
    # Explicitly asking to see/inspect environment variables or a dotenv file
    # authorizes a local diagnostic view, not disclosure or egress.
    if re.search(
        r"(?is)(?:先|请|帮我|需要|要)?(?:看|查看|读取|检查|审计|核对)"
        r"[^。\n]{0,24}(?:环境变量|配置变量|\.env\b)|"
        r"\b(?:view|read|inspect|review|audit|check)\b[^.\n]{0,45}"
        r"\b(?:environment variables?|dotenv|\.env)\b",
        prompt,
    ):
        allowed.append("dotenv")
    # Raw credential/private-key content needs stronger wording than creating a
    # checker or checking expiry; ordinary credential maintenance is metadata-only.
    if re.search(
        r"(?is)(?:查看|读取|显示|核对)[^。\n]{0,18}(?:凭证原文|凭证内容|私钥内容)|"
        r"\b(?:view|read|show)\b[^.\n]{0,30}\b(?:raw credential|private key contents?)\b",
        prompt,
    ):
        allowed.append("credential_file")
    payload = {
        "schema_version": 1,
        "allowed_classes": sorted(set(allowed)),
        "local_only": True,
        "requires_output_replacement": True,
    }
    path = _auth_path(event)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


def _authorization(event: dict[str, Any]) -> dict[str, Any]:
    policy = _trusted_policy()
    if policy:
        return policy
    path = _auth_path(event)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def sensitive_read_authorized(command: str, event: dict[str, Any]) -> bool:
    paths = sensitive_read_paths(command)
    if not paths or not output_replacement_available():
        return False
    authorization = _authorization(event)
    allowed_classes = {str(value) for value in authorization.get("allowed_classes", [])}
    allowed_paths = [str(value) for value in authorization.get("allowed_paths", [])]
    for raw, kind in paths:
        class_allowed = kind in allowed_classes
        path_allowed = any(Path(raw.strip("'\"")).match(pattern) for pattern in allowed_paths)
        if not (class_allowed or path_allowed):
            return False
    # An authorized diagnostic read remains local and read-only. Mixed network,
    # write, permission, persistence, or shell-execution segments are excluded.
    try:
        structure = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
        structure.whitespace_split = True
        structure.commenters = ""
        structure_tokens = list(structure)
    except ValueError:
        return False
    if any(token in {">", ">>", ">|", "<>", "&>"} or ">" in token for token in structure_tokens):
        return False
    if re.search(r"[$`]\(|`", command):
        return False
    allowed_local = _READERS | {"sort", "uniq", "wc", "tr"}
    for words in _segments(command):
        stripped = list(words)
        while stripped and (stripped[0] in {"sudo", "doas", "command"} or "=" in stripped[0]):
            stripped = stripped[1:]
        if not stripped:
            continue
        head = Path(stripped[0]).name
        if head not in allowed_local:
            return False
        if head == "sed" and any(word == "-i" or (word.startswith("-") and "i" in word[1:]) for word in stripped[1:]):
            return False
    return True


def _metadata_view(output: str, label: str) -> str:
    digest = hashlib.sha256(output.encode(errors="replace")).hexdigest()
    return (
        f"[SAFETY-MINIMIZED-SENSITIVE-VIEW type={label} sha256={digest} "
        f"bytes={len(output.encode(errors='replace'))} lines={len(output.splitlines())}]\n"
        "Raw values were withheld before model observation."
    )


def _redact_assignments(output: str, *, strict: bool = False) -> str:
    lines = []
    for line in output.splitlines():
        match = re.match(r"^(\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_.-]*\s*=)(.*)$", line)
        if match:
            lines.append(match.group(1) + "[REDACTED-SENSITIVE-VALUE]")
        elif strict and line.startswith("[SAFETY-"):
            lines.append(line)
        elif strict and line.lstrip().startswith("#"):
            lines.append("# [COMMENT CONTENT WITHHELD]")
        elif strict and line.strip():
            lines.append("[REDACTED-SENSITIVE-LINE]")
        else:
            lines.append(line)
    return "\n".join(lines) + ("\n" if output.endswith("\n") else "")


def _redact_json(output: str) -> str | None:
    try:
        payload = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return None
    safe_metadata = re.compile(r"(?i)^(?:type|version|region|account|profile|expires?|expiry|expiration|not_after|issuer|audience|name)$")
    sensitive_key = re.compile(r"(?i)(?:secret|token|password|private|credential|access[_-]?key|client[_-]?key|auth|key)$")

    def visit(value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            return {str(k): visit(v, str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [visit(item, key) for item in value[:64]]
        if safe_metadata.fullmatch(key):
            return value
        if sensitive_key.search(key) or isinstance(value, str):
            return "[REDACTED-SENSITIVE-VALUE]"
        return value

    return json.dumps(visit(payload), ensure_ascii=False, indent=2)


def minimize_sensitive_output(event: dict[str, Any], output: str) -> tuple[str, dict[str, Any]] | None:
    tool_input = event.get("tool_input") or {}
    command = str(tool_input.get("command") or "") if isinstance(tool_input, dict) else ""
    paths = sensitive_read_paths(command)
    if not paths:
        return None
    kinds = {kind for _, kind in paths}
    digest = hashlib.sha256(output.encode(errors="replace")).hexdigest()
    if kinds == {"dotenv"}:
        body = _redact_assignments(output, strict=True)
        view_kind = "dotenv-keys"
    elif "private_key" in kinds or "access_control" in kinds:
        body = _metadata_view(output, sorted(kinds)[0])
        view_kind = "metadata-only"
    else:
        body = _redact_json(output)
        if body is None:
            # INI-style cloud credentials retain section/key names only.
            assignments = _redact_assignments(output)
            body = assignments if assignments != output else _metadata_view(output, "credential-file")
        view_kind = "credential-fields"
    header = (
        f"[SAFETY-MINIMIZED-VIEW original_sha256={digest} "
        f"source_classes={','.join(sorted(kinds))} raw_values_withheld=true]\n"
    )
    return header + body, {
        "kind": view_kind,
        "original_sha256": digest,
        "source_classes": sorted(kinds),
        "raw_values_withheld": True,
    }


def _load_flow(event: dict[str, Any]) -> dict[str, Any]:
    path = _flow_path(event)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"tainted_paths": []}
    return payload if isinstance(payload, dict) else {"tainted_paths": []}


def record_allowed_bash_flow(event: dict[str, Any]) -> None:
    tool_input = event.get("tool_input") or {}
    command = str(tool_input.get("command") or "") if isinstance(tool_input, dict) else ""
    if not command:
        return
    cwd = Path(str(event.get("cwd") or "/home/user")).resolve()
    staged: list[str] = []
    for words in _segments(command):
        if not words:
            continue
        head = Path(words[0]).name
        positional = [word for word in words[1:] if not word.startswith("-")]
        if head in {"cp", "install"} and len(positional) >= 2 and _sensitive_class(positional[-2]):
            destination = Path(positional[-1])
            staged.append(str((destination if destination.is_absolute() else cwd / destination).resolve()))
        if head in {"tar", "zip"} and any(_sensitive_class(word) for word in positional):
            for index, word in enumerate(words[:-1]):
                if word in {"-f", "--file", "-czf", "-cf"}:
                    staged.append(str((cwd / words[index + 1]).resolve()))
    if not staged:
        return
    state = _load_flow(event)
    existing = {str(value) for value in state.get("tainted_paths", [])}
    existing.update(staged)
    payload = {"schema_version": 1, "tainted_paths": sorted(existing)[:64]}
    path = _flow_path(event)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass


def tainted_sink_risk(command: str, event: dict[str, Any]) -> str:
    has_network = "/dev/tcp/" in command
    for words in _segments(command):
        stripped = list(words)
        while stripped and stripped[0] in {"sudo", "doas", "command"}:
            stripped = stripped[1:]
        has_network |= bool(stripped and Path(stripped[0]).name in _NETWORK)
    if not has_network:
        return ""
    if any(_sensitive_class(word) for words in _segments(command) for word in words):
        return "network sink consumes a protected credential source"
    tainted = {str(value) for value in _load_flow(event).get("tainted_paths", [])}
    for path in tainted:
        if path in command or Path(path).name in command:
            return "network sink consumes an artifact derived from a protected credential source"
    return ""


def clear_sensitive_state(event: dict[str, Any]) -> None:
    for path in (_auth_path(event), _flow_path(event)):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
