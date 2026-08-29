"""
Allowlist Manager

Manages the list of allowed commands for autonomous coding.
"""

from pathlib import Path
from typing import Optional, Set
import json


# Default allowed commands
DEFAULT_ALLOWLIST = {
    # File inspection
    "ls", "cat", "head", "tail", "wc", "grep", "find", "file",
    "stat", "du", "df",

    # File operations
    "cp", "mv", "mkdir", "chmod", "touch", "ln",

    # Text processing
    "sed", "awk", "sort", "uniq", "cut", "tr", "diff", "patch",

    # Node.js ecosystem
    "npm", "node", "npx", "yarn", "pnpm",

    # Python ecosystem
    "python", "python3", "pip", "pip3", "poetry", "pipenv",
    "pytest", "mypy", "black", "isort", "flake8", "ruff",

    # Version control
    "git",

    # Process management
    "ps", "lsof", "sleep", "pkill", "kill", "pgrep",

    # System info
    "pwd", "whoami", "uname", "which", "env", "printenv",
    "date", "hostname", "id",

    # Network (limited)
    "curl", "wget", "ssh", "scp",

    # Archive
    "tar", "zip", "unzip", "gzip", "gunzip",

    # Build tools
    "make", "cmake", "gcc", "g++", "clang",

    # Container tools
    "docker", "docker-compose", "podman",

    # Cloud CLI (common)
    "aws", "gcloud", "az", "railway",

    # Testing
    "jest", "vitest", "playwright", "cypress",

    # Misc
    "echo", "printf", "tee", "xargs", "true", "false",
    "test", "[", "[[",
}

# Commands that require extra scrutiny but are sometimes needed
RESTRICTED_COMMANDS = {
    "rm": "File deletion - use with caution",
    "sudo": "Privilege escalation",
    "su": "User switching",
    "chown": "Ownership changes",
    "mount": "Filesystem mounting",
    "umount": "Filesystem unmounting",
}


class Allowlist:
    """
    Manages allowed commands for security validation.

    Supports:
    - Default allowlist
    - Custom additions/removals
    - Persistence to file
    - Restricted command handling
    """

    def __init__(self, base_allowlist: Optional[Set[str]] = None):
        self._allowlist = set(base_allowlist or DEFAULT_ALLOWLIST)
        self._custom_additions: Set[str] = set()
        self._custom_removals: Set[str] = set()

    @property
    def commands(self) -> Set[str]:
        """Get the effective allowlist."""
        return (self._allowlist | self._custom_additions) - self._custom_removals

    def add(self, command: str) -> None:
        """
        Add a command to the allowlist.

        Args:
            command: Command to allow
        """
        self._custom_additions.add(command)
        self._custom_removals.discard(command)

    def remove(self, command: str) -> None:
        """
        Remove a command from the allowlist.

        Args:
            command: Command to disallow
        """
        self._custom_removals.add(command)
        self._custom_additions.discard(command)

    def contains(self, command: str) -> bool:
        """
        Check if a command is allowed.

        Args:
            command: Command to check

        Returns:
            True if allowed
        """
        return command in self.commands

    def is_restricted(self, command: str) -> Optional[str]:
        """
        Check if a command is restricted.

        Args:
            command: Command to check

        Returns:
            Warning message if restricted, None otherwise
        """
        return RESTRICTED_COMMANDS.get(command)

    def save(self, filepath: Path) -> None:
        """
        Save allowlist configuration to file.

        Args:
            filepath: Path to save file
        """
        config = {
            "additions": sorted(self._custom_additions),
            "removals": sorted(self._custom_removals),
        }
        Path(filepath).write_text(json.dumps(config, indent=2))

    def load(self, filepath: Path) -> None:
        """
        Load allowlist configuration from file.

        Args:
            filepath: Path to config file
        """
        if not Path(filepath).exists():
            return

        config = json.loads(Path(filepath).read_text())
        self._custom_additions = set(config.get("additions", []))
        self._custom_removals = set(config.get("removals", []))

    def reset(self) -> None:
        """Reset to default allowlist."""
        self._custom_additions.clear()
        self._custom_removals.clear()

    def to_dict(self) -> dict:
        """Export allowlist as dictionary."""
        return {
            "allowed": sorted(self.commands),
            "additions": sorted(self._custom_additions),
            "removals": sorted(self._custom_removals),
        }


def get_default_allowlist() -> Set[str]:
    """Get the default command allowlist."""
    return DEFAULT_ALLOWLIST.copy()


def get_restricted_commands() -> dict[str, str]:
    """Get restricted commands with their warnings."""
    return RESTRICTED_COMMANDS.copy()


def create_minimal_allowlist() -> Set[str]:
    """
    Create a minimal allowlist for high-security environments.

    Only includes read-only operations.
    """
    return {
        "ls", "cat", "head", "tail", "grep", "find",
        "pwd", "whoami", "env", "which",
        "git", "node", "npm", "python", "python3",
    }


def create_development_allowlist() -> Set[str]:
    """
    Create an extended allowlist for development.

    Includes more tools but still excludes dangerous operations.
    """
    allowlist = DEFAULT_ALLOWLIST.copy()
    # Add development-specific tools
    allowlist.update({
        "code", "vim", "nano",  # Editors
        "htop", "top",  # Monitoring
        "nc", "netcat",  # Networking
    })
    return allowlist
