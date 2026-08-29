#!/usr/bin/env python3
"""Bash matcher — runs before every Bash tool call.

Atoms covered (8):
- detect-shell-command-injection
- detect-destructive-flag
- detect-secret-in-args
- detect-overbroad-resource-selector
- validate-tool-argument-schema (basic)
- enforce-filesystem-sandbox (path containment)
- enforce-process-sandbox (process-tree depth)
- detect-sandbox-escape-attempt
"""

import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_common import (
    read_event, aggregate, check, soft_check,
    SHELL_INJECTION_PATTERNS, SECRET_PATTERNS, DESTRUCTIVE_KEYWORDS, PATH_TRAVERSAL_PATTERNS,
)

OVERBROAD_SELECTORS = re.compile(
    r"(rm\s+(?:-[rfvR]*\s+)?(?:/|~/?|\.\.?/?)(?=\s|[;&|]|$)|"
    r"chmod\s+(-R\s+)?[0-7]{3,4}\s+[/.~]|"
    r"find\s+[/.~]\s+-(exec|delete))"
)

RM_COMMAND = re.compile(
    r"(?:^|&&|\|\||;|\n)\s*(?:(?:sudo|doas)\s+)?(?:\S*/)?rm\s+"
    r"(?P<arguments>[^;&|\n]+)",
    re.IGNORECASE,
)

SANDBOX_ESCAPE_PATTERNS = re.compile(
    r"(unshare\s+-|nsenter|setns|"
    r"docker\s+(exec|run)\s+--privileged|"
    r"mount\s+--bind\s+/|"
    r"chroot\s+/)"
)

PROCESS_SANDBOX_WEAKENING = re.compile(
    r"(docker\s+(?:run|create|exec)[^\n]*--privileged|"
    r"--security-opt\s+(?:seccomp|apparmor)=unconfined|"
    r"--cap-add\s*=\s*ALL|"
    r"--no-new-privileges\s*=\s*false|"
    r"setenforce\s+0|"
    r"sysctl\s+(-w\s+)?kernel\.)",
    re.IGNORECASE,
)

# Replacing a database file destroys the destination's current contents even
# when the command avoids explicit DROP/DELETE tokens. Treat it as the same
# destructive-argument class so an atomic-rebuild pattern cannot bypass the
# database safety gate.
DATABASE_REPLACEMENT = re.compile(
    r"\b(?:mv|cp)\s+(?:-[^\s;&|]+\s+)*[^\s;&|]+\s+"
    r"[\"']?[^\s;&|\"']+\.(?:db|sqlite|sqlite3)[\"']?(?=\s|;|&|\||$)",
    re.IGNORECASE,
)


def _recursive_rm_is_scoped(command: str, logical_cwd: str) -> bool:
    """Allow recursive deletion only for explicit cwd or temporary descendants."""
    cwd = Path(logical_cwd or "/home/user").resolve()
    temporary_roots = (Path("/tmp").resolve(), Path("/var/tmp").resolve())
    found_recursive_rm = False

    for match in RM_COMMAND.finditer(command):
        try:
            tokens = shlex.split(match.group("arguments"))
        except ValueError:
            return False
        recursive = any(
            token == "--recursive"
            or (token.startswith("-") and not token.startswith("--") and "r" in token.lower())
            for token in tokens
        )
        if not recursive:
            continue
        found_recursive_rm = True
        targets = [
            token
            for token in tokens
            if token != "--"
            and not token.startswith("-")
            and not re.match(r"^\d*[<>]", token)
        ]
        if not targets:
            return False
        for target in targets:
            if any(marker in target for marker in ("$", "`", "~", "{", "}")):
                return False
            path = Path(target)
            resolved = (path if path.is_absolute() else cwd / path).resolve()
            in_cwd = resolved != cwd and resolved.is_relative_to(cwd)
            in_temporary_root = any(
                resolved != root and resolved.is_relative_to(root)
                for root in temporary_roots
            )
            if not (in_cwd or in_temporary_root):
                return False
    return found_recursive_rm

FS_SANDBOX_ROOT = os.environ.get("SAFETY_ORCH_FS_SANDBOX")
# When set, deny any command that names absolute paths outside this root.


def main() -> int:
    event = read_event()
    cmd = event.get("command") or event.get("tool_input", {}).get("command", "")

    # validate-tool-argument-schema must run before any regex access so a
    # non-string command produces a safe block instead of a TypeError.
    if not isinstance(cmd, str) or not cmd:
        verdicts = []
        if not isinstance(cmd, str):
            verdicts.append(check(
                "validate-tool-argument-schema", True,
                "Bash command is not a string",
            ))
        return aggregate(verdicts) if verdicts else 0

    verdicts = []

    # detect-shell-command-injection
    if SHELL_INJECTION_PATTERNS.search(cmd):
        verdicts.append(check(
            "detect-shell-command-injection", True,
            "Shell injection pattern (dangerous command substitution, pipe-to-shell, or /dev/tcp) detected",
        ))

    # detect-destructive-flag
    destructive_match = DESTRUCTIVE_KEYWORDS.search(cmd)
    recursive_rm_scoped = _recursive_rm_is_scoped(
        cmd, str(event.get("cwd") or "/home/user")
    )
    if destructive_match and recursive_rm_scoped:
        command_without_scoped_rm = RM_COMMAND.sub("", cmd)
        destructive_match = DESTRUCTIVE_KEYWORDS.search(command_without_scoped_rm)
    database_replacement = DATABASE_REPLACEMENT.search(cmd)
    if destructive_match or database_replacement:
        reason = (
            f"Destructive flag / verb detected: '{destructive_match.group()}'"
            if destructive_match
            else f"Database file replacement detected: '{database_replacement.group()}'"
        )
        verdicts.append(check(
            "detect-destructive-flag", True,
            reason,
        ))

    # detect-secret-in-args
    secret_hits = [name for name, rx in SECRET_PATTERNS.items() if rx.search(cmd)]
    if secret_hits:
        verdicts.append(check(
            "detect-secret-in-args", True,
            f"Secret material in Bash args: {', '.join(secret_hits)}",
        ))

    # detect-overbroad-resource-selector
    if OVERBROAD_SELECTORS.search(cmd):
        verdicts.append(check(
            "detect-overbroad-resource-selector", True,
            "Overbroad resource selector (recursive root-level operation) detected",
        ))

    # enforce-filesystem-sandbox (only when SAFETY_ORCH_FS_SANDBOX is set)
    if FS_SANDBOX_ROOT:
        sandbox = Path(FS_SANDBOX_ROOT).resolve()
        for token in cmd.split():
            if token.startswith("/") and not Path(token).resolve().is_relative_to(sandbox):
                verdicts.append(check(
                    "enforce-filesystem-sandbox", True,
                    f"Path '{token}' escapes sandbox root {sandbox}",
                ))
                break

    # enforce-process-sandbox + detect-sandbox-escape-attempt
    if SANDBOX_ESCAPE_PATTERNS.search(cmd):
        verdicts.append(check(
            "detect-sandbox-escape-attempt", True,
            "Sandbox-escape primitive (unshare/nsenter/chroot/privileged) detected",
        ))

    # enforce-process-sandbox — config-gated: when SAFETY_ORCH_PROCESS_SANDBOX
    # is set, reject commands that weaken or escape a process sandbox.
    if os.environ.get("SAFETY_ORCH_PROCESS_SANDBOX", "").strip():
        if PROCESS_SANDBOX_WEAKENING.search(cmd):
            verdicts.append(check(
                "enforce-process-sandbox", True,
                "Command attempts to weaken or escape the process sandbox",
            ))

    return aggregate(verdicts) if verdicts else 0


if __name__ == "__main__":
    sys.exit(main())
