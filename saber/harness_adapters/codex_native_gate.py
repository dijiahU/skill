#!/usr/bin/env python3
"""Keep Codex host tools out of SABER's benchmark environment.

The native adapter exposes SABER tools as app-server dynamic functions.  This
hook blocks Codex's built-in shell and patch tools so they cannot bypass
TaskRuntime.  A narrow read-only exception lets an installed skill inspect its
own files; those reads never touch the benchmark container.
"""
from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path


READ_ONLY_COMMANDS = {"cat", "find", "grep", "head", "ls", "pwd", "rg", "sed", "tail"}


def _deny(reason: str) -> int:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 2


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _read_only_skill_command(event: dict) -> bool:
    raw_root = os.environ.get("SABER_CODEX_SKILL_ROOT", "").strip()
    if not raw_root:
        return False
    skill_root = Path(raw_root)
    tool_input = event.get("tool_input") or {}
    raw_command = tool_input.get("command", "")
    command = raw_command if isinstance(raw_command, str) else ""
    if not command or any(
        token in command for token in (";", "&&", "||", "|", ">", "<", "`", "$((", "$(")
    ):
        return False

    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False

    executable = Path(parts[0]).name
    if executable == "python3":
        if len(parts) < 2 or Path(parts[1]).name != "health_status.py":
            return False
    elif executable not in READ_ONLY_COMMANDS:
        return False

    raw_cwd = (
        tool_input.get("workdir") or tool_input.get("cwd") or event.get("cwd") or ""
    )
    if raw_cwd and _under(Path(raw_cwd), skill_root):
        return True

    for part in parts[1:]:
        if part.startswith("-"):
            continue
        candidate = Path(part)
        if candidate.is_absolute() and _under(candidate, skill_root):
            return True
    return False


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return _deny("Malformed Codex hook event; host tool blocked.")

    tool_name = event.get("tool_name", "")
    if tool_name == "Bash":
        if _read_only_skill_command(event):
            return 0
        return _deny(
            "SABER benchmark commands must use the saber_bash dynamic tool so "
            "execution and state deltas remain inside TaskRuntime."
        )
    if tool_name in {"apply_patch", "Edit", "Write", "MultiEdit"}:
        return _deny(
            "SABER benchmark file changes must use saber_bash or an exposed MCP "
            "dynamic tool so TaskRuntime records the state transition."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
