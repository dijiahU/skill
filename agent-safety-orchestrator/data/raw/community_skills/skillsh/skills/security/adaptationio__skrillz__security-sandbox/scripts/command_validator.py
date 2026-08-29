"""
Command Validator

Parses and validates bash commands against allowlists and
dangerous patterns.
"""

from dataclasses import dataclass
from typing import Optional
import re
import shlex


@dataclass
class ValidationResult:
    """Result of command validation."""
    allowed: bool
    reason: Optional[str] = None
    commands_found: list[str] = None

    def __post_init__(self):
        if self.commands_found is None:
            self.commands_found = []


# Dangerous patterns that are always blocked
DANGEROUS_PATTERNS = [
    # Filesystem destruction
    (r"rm\s+(-[rf]+\s+)*[/~]", "Removing root or home directory"),
    (r"rm\s+-rf\s+/", "Removing root filesystem"),
    (r">\s*/dev/[hs]d[a-z]", "Writing to raw disk device"),
    (r"mkfs\.", "Formatting filesystem"),

    # Fork bombs and resource exhaustion
    (r":\(\)\s*{\s*:\|:&\s*}", "Fork bomb detected"),
    (r"dd\s+if=/dev/(zero|random)", "dd with infinite input"),

    # Privilege escalation
    (r"chmod\s+777", "World-writable permissions"),
    (r"chmod\s+-R\s+777", "Recursive world-writable"),
    (r"chown\s+root", "Changing to root ownership"),

    # Remote code execution
    (r"curl\s+.*\|\s*(ba)?sh", "Piping curl to shell"),
    (r"wget\s+.*\|\s*(ba)?sh", "Piping wget to shell"),
    (r"curl\s+.*-o\s*/tmp.*&&.*sh", "Download and execute"),

    # System damage
    (r">\s*/etc/passwd", "Overwriting passwd"),
    (r">\s*/etc/shadow", "Overwriting shadow"),
    (r"shutdown", "System shutdown"),
    (r"reboot", "System reboot"),
    (r"init\s+0", "System halt"),

    # History manipulation (could hide malicious activity)
    (r"history\s+-c", "Clearing command history"),
    (r"unset\s+HISTFILE", "Disabling history"),
]


def extract_commands(command_string: str) -> list[str]:
    """
    Extract individual commands from a command string.

    Handles:
    - Pipes (|)
    - Command chains (&&, ||, ;)
    - Subshells ($())
    - Command substitution

    Args:
        command_string: The full command string

    Returns:
        List of base command names
    """
    commands = []

    # Split on command separators
    # This is a simplified parser - real bash parsing is complex
    separators = r'[;&|]+|\$\('
    parts = re.split(separators, command_string)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Try to extract the first word (the command)
        try:
            tokens = shlex.split(part)
            if tokens:
                cmd = tokens[0]
                # Handle path-based commands
                if '/' in cmd:
                    cmd = cmd.split('/')[-1]
                # Handle env and other prefixes
                if cmd in ('env', 'time', 'nice', 'nohup'):
                    if len(tokens) > 1:
                        cmd = tokens[1]
                        if '/' in cmd:
                            cmd = cmd.split('/')[-1]
                commands.append(cmd)
        except ValueError:
            # shlex parse error - try simple split
            words = part.split()
            if words:
                cmd = words[0]
                if '/' in cmd:
                    cmd = cmd.split('/')[-1]
                commands.append(cmd)

    return commands


def check_dangerous_patterns(command: str) -> Optional[str]:
    """
    Check command against dangerous patterns.

    Args:
        command: The command to check

    Returns:
        Reason string if dangerous, None if safe
    """
    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return reason
    return None


def validate_command(
    command: str,
    allowlist: set[str] = None
) -> ValidationResult:
    """
    Validate a command against security policies.

    Args:
        command: The command to validate
        allowlist: Optional custom allowlist (uses default if None)

    Returns:
        ValidationResult with allowed status and reason
    """
    from .allowlist import get_default_allowlist

    if allowlist is None:
        allowlist = get_default_allowlist()

    # Empty command is allowed (no-op)
    if not command or not command.strip():
        return ValidationResult(allowed=True)

    # Check for dangerous patterns first
    danger = check_dangerous_patterns(command)
    if danger:
        return ValidationResult(
            allowed=False,
            reason=f"Dangerous pattern detected: {danger}"
        )

    # Extract commands
    commands = extract_commands(command)

    if not commands:
        return ValidationResult(allowed=True, commands_found=[])

    # Check each command against allowlist
    for cmd in commands:
        if cmd not in allowlist:
            return ValidationResult(
                allowed=False,
                reason=f"Command '{cmd}' is not in allowlist",
                commands_found=commands
            )

    return ValidationResult(
        allowed=True,
        commands_found=commands
    )


def is_safe_command(command: str) -> bool:
    """
    Simple check if a command is safe.

    Args:
        command: The command to check

    Returns:
        True if safe, False otherwise
    """
    return validate_command(command).allowed
