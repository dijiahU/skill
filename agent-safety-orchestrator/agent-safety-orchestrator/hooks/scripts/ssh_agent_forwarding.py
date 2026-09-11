"""Bounded authorization and diff review for SSH agent forwarding.

Only trusted UserPromptSubmit events can authorize newly enabling
``ForwardAgent yes``. The write review requires a concrete previous snapshot
and complete candidate for an active per-user SSH client config. It does not
ban SSH tunnels, local forwarding, or unchanged forwarding directives.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from lib_common import _state_dir

_MAX_TEXT = 200_000
_FEATURE = (
    r"(?:\bForwardAgent\b|\b(?:SSH\s+)?agent[- ]forwarding\b|"
    r"\bforward\s+(?:my\s+|the\s+)?SSH\s+agent\b|"
    r"(?:SSH\s*)?(?:agent|代理)\s*转发|转发\s*(?:SSH\s*)?(?:agent|代理))"
)
_POSITIVE_REQUEST = re.compile(
    rf"(?is)(?:"
    rf"\b(?:enable|allow|use|want|request|configure|turn\s+on)\b[^.\n]{{0,60}}{_FEATURE}|"
    rf"{_FEATURE}[^.\n]{{0,60}}\b(?:enable|allow|use|wanted|requested|configure|turn\s+on)\b|"
    rf"\b(?:set|add)\s+ForwardAgent(?:\s+|\s*=\s*)yes\b|"
    rf"\bforward\s+(?:my\s+|the\s+)?SSH\s+agent\b|"
    rf"(?:启用|开启|打开|允许|使用|需要|想要|请求|配置)[^。\n]{{0,40}}{_FEATURE}|"
    rf"{_FEATURE}[^。\n]{{0,40}}(?:启用|开启|打开|允许|使用|需要|想要|请求|配置)"
    rf")"
)
_NEGATIVE_OR_ADVISORY = re.compile(
    rf"(?is)(?:"
    rf"\bForwardAgent(?:\s+|\s*=\s*)(?:no|false|off)\b|"
    rf"{_FEATURE}[^.\n]{{0,40}}\b(?:disabled?|off|false|no)\b|"
    rf"\b(?:do\s+not|don't|never|without|disable|turn\s+off)\b[^.\n]{{0,80}}{_FEATURE}|"
    rf"\b(?:explain|how\s+to|example|documentation|plan\s+only|dry[- ]run)\b"
    rf"[^.\n]{{0,100}}{_FEATURE}|"
    rf"(?:不要|别|禁止|关闭|禁用|无需|不需要)[^。\n]{{0,50}}{_FEATURE}|"
    rf"{_FEATURE}[^。\n]{{0,40}}(?:关闭|禁用|不要|不启用)|"
    rf"(?:说明|如何|怎么|示例|文档|只做计划)[^。\n]{{0,60}}{_FEATURE}"
    rf")"
)
_CONFIG_PATH = re.compile(r"^/(?:home/[^/]+|root)/\.ssh/config$")
_PROMPT_PATH = re.compile(
    r"(?<!\S)(?:~|/home/[A-Za-z0-9_.-]+|/root)/\.ssh/config"
    r"(?=$|[\s`'\"，。,:;!?）])"
)
_PROMPT_HOST = re.compile(
    r"(?i)(?:\bHost\s+|(?:for|on)\s+(?:SSH\s+)?host\s+|"
    r"(?:为|在)\s*(?:SSH\s*)?Host\s*)([A-Za-z0-9*?!._-]+)"
)


def _context_key(event: Mapping[str, Any]) -> str:
    session = str(event.get("session_id") or "")
    turn = str(event.get("turn_id") or "")
    if not session and not turn:
        return ""
    return hashlib.sha256(f"{session}\0{turn}".encode()).hexdigest()


def _authorization_path(context_key: str) -> Path:
    return _state_dir() / f"ssh-agent-forwarding-auth-{context_key}.json"


def _logical_home(cwd: Path) -> Path | None:
    parts = cwd.parts
    if len(parts) >= 3 and parts[1] == "home":
        return Path("/") / parts[1] / parts[2]
    if len(parts) >= 2 and parts[1] == "root":
        return Path("/root")
    return None


def _authorized_targets(prompt: str, cwd: Path) -> list[str]:
    home = _logical_home(cwd)
    targets: set[str] = set()
    for raw in _PROMPT_PATH.findall(prompt):
        if raw.startswith("~/"):
            if home is not None:
                targets.add(str((home / raw[2:]).resolve()))
        else:
            targets.add(str(Path(raw).resolve()))
    if not targets and home is not None:
        targets.add(str((home / ".ssh/config").resolve()))
    return sorted(targets)


def _authorized_sites(prompt: str) -> list[str]:
    hosts = {
        match.rstrip(".,;:!?，。").lower()
        for match in _PROMPT_HOST.findall(prompt)
        if match.rstrip(".,;:!?，。")
    }
    return sorted(f"host:{host}" for host in hosts) if hosts else ["*"]


def record_agent_forwarding_authorization(event: Mapping[str, Any]) -> None:
    """Persist only a scoped positive authorization; never retain raw prompt."""
    context = _context_key(event)
    if not context:
        return
    prompt = str(event.get("prompt") or event.get("user_message") or "")[:_MAX_TEXT]
    explicit = bool(_POSITIVE_REQUEST.search(prompt) and not _NEGATIVE_OR_ADVISORY.search(prompt))
    cwd = Path(str(event.get("cwd") or "/home/user")).resolve()
    payload = {
        "schema_version": 2,
        "allowed_class": "ssh_agent_forwarding" if explicit else "",
        "allowed_targets": _authorized_targets(prompt, cwd) if explicit else [],
        "allowed_sites": _authorized_sites(prompt) if explicit else [],
    }
    path = _authorization_path(context)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)
    except OSError:
        pass


def _authorization(context_key: str) -> dict[str, Any]:
    if not context_key:
        return {}
    try:
        payload = json.loads(_authorization_path(context_key).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _active_line(raw: str) -> str:
    line = raw.strip()
    if not line or line.startswith("#"):
        return ""
    return line.split("#", 1)[0].strip()


def _forward_agent_states(text: str) -> dict[str, str]:
    """Return each block's first active value, matching OpenSSH precedence."""
    states: dict[str, str] = {}
    block = "global"
    for raw in text[:_MAX_TEXT].splitlines():
        line = _active_line(raw)
        if not line:
            continue
        section = re.match(r"(?i)^(Host|Match)\s+(\S.*?)\s*$", line)
        if section:
            label = " ".join(section.group(2).lower().split())
            block = f"{section.group(1).lower()}:{label}"
            continue
        directive = re.match(r"(?i)^ForwardAgent(?:\s+|\s*=\s*)(\S+)\s*$", line)
        if directive and block not in states:
            states[block] = directive.group(1).lower()
    return states


def _new_forwarding_sites(previous: str, candidate: str) -> list[str]:
    before = _forward_agent_states(previous)
    after = _forward_agent_states(candidate)
    # An effective global yes already covers every Host. A preceding global no
    # is retained as no by _forward_agent_states and does not take this path.
    if before.get("global") == "yes":
        return []
    return sorted(
        site for site, value in after.items()
        if value == "yes" and before.get(site) != "yes"
    )


def agent_forwarding_write_findings(
    path: str,
    previous: str | None,
    candidate: str | None,
    *,
    complete: bool,
    context_key: str,
) -> list[str]:
    """Return one finding for an unauthorized new ForwardAgent enablement."""
    normalized = str(Path(path).resolve())
    if (not _CONFIG_PATH.fullmatch(normalized) or previous is None
            or candidate is None or not complete):
        return []
    new_sites = _new_forwarding_sites(previous, candidate)
    if not new_sites:
        return []
    authorization = _authorization(context_key)
    allowed_targets = {
        str(Path(value).resolve())
        for value in authorization.get("allowed_targets", [])
        if isinstance(value, str) and _CONFIG_PATH.fullmatch(str(Path(value).resolve()))
    }
    allowed_sites = {
        str(value).lower() for value in authorization.get("allowed_sites", [])
        if isinstance(value, str)
    }
    sites_allowed = "*" in allowed_sites or set(new_sites).issubset(allowed_sites)
    if (authorization.get("allowed_class") == "ssh_agent_forwarding"
            and normalized in allowed_targets and sites_allowed):
        return []
    return [
        "SSH client configuration newly enables agent forwarding without explicit, target-and-Host-scoped user authorization"
    ]


__all__ = [
    "_context_key",
    "agent_forwarding_write_findings",
    "record_agent_forwarding_authorization",
]
