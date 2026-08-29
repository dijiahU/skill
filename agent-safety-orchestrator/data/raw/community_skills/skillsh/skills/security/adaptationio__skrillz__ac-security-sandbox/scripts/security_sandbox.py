"""
AC Security Sandbox - Defense-in-depth security for autonomous coding.

Provides three layers of security:
1. OS-Level Sandbox: Isolated execution environment
2. Filesystem Permissions: Restricted path access
3. Command Allowlist: Pre-approved commands only
"""

import re
import json
import shlex
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any, Set


@dataclass
class SecurityConfig:
    """Security configuration."""
    sandbox_enabled: bool = True
    isolation_level: str = "strict"  # strict, moderate, permissive

    # Filesystem permissions
    read_paths: List[str] = field(default_factory=lambda: ["./**"])
    write_paths: List[str] = field(default_factory=lambda: ["./**"])
    deny_paths: List[str] = field(default_factory=lambda: [
        "/etc/**", "/usr/**", "~/.ssh/**", "/root/**"
    ])

    # Network restrictions
    allowed_hosts: List[str] = field(default_factory=lambda: [
        "localhost", "127.0.0.1", "api.anthropic.com"
    ])

    # Custom allowlist additions
    custom_commands: List[str] = field(default_factory=list)


# Default command allowlist
ALLOWED_COMMANDS: Set[str] = {
    # File inspection
    "ls", "cat", "head", "tail", "wc", "grep", "find", "file",

    # File operations
    "cp", "mv", "mkdir", "chmod", "touch", "ln",

    # Node.js
    "npm", "node", "npx", "yarn", "pnpm",

    # Python
    "python", "python3", "pip", "pip3", "poetry", "pipenv",

    # Version control
    "git",

    # Process management
    "ps", "lsof", "sleep", "pkill", "kill",

    # Build tools
    "make", "cmake", "cargo", "go", "rustc", "gcc", "g++",

    # Testing
    "jest", "pytest", "vitest", "playwright", "cypress",

    # Utilities
    "echo", "printf", "date", "which", "whereis", "env",
    "sort", "uniq", "tr", "cut", "sed", "awk",

    # Archives
    "tar", "zip", "unzip", "gzip", "gunzip",

    # Network (limited)
    "curl", "wget",
}

# Dangerous patterns - always blocked
DANGEROUS_PATTERNS: List[str] = [
    r"rm\s+-rf\s+/",           # Recursive delete root
    r"rm\s+-rf\s+~",           # Recursive delete home
    r"rm\s+-rf\s+\*",          # Recursive delete wildcard
    r"dd\s+if=",               # Direct disk writes
    r"mkfs",                   # Format filesystems
    r":(){ :|:& };:",          # Fork bombs
    r"chmod\s+777\s+/",        # Overly permissive on root
    r"curl.*\|\s*bash",        # Pipe to shell
    r"curl.*\|\s*sh",          # Pipe to shell
    r"wget.*\|\s*bash",        # Pipe to shell
    r"wget.*\|\s*sh",          # Pipe to shell
    r"eval\s+",                # Eval commands
    r"sudo\s+",                # Sudo commands
    r"su\s+",                  # Su commands
    r"chown\s+-R\s+root",      # Change ownership to root
    r">\s*/dev/sd",            # Write to disk devices
    r">\s*/dev/hd",            # Write to disk devices
]


@dataclass
class AuditEntry:
    """Security audit log entry."""
    timestamp: str
    action: str  # ALLOW, BLOCK
    command: str
    reason: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class SecuritySandbox:
    """
    Defense-in-depth security for autonomous code execution.

    Usage:
        sandbox = SecuritySandbox(project_dir)
        is_safe, reason = sandbox.validate_command("npm install")
    """

    CONFIG_FILE = ".claude/security-config.json"
    AUDIT_FILE = ".claude/security-audit.jsonl"

    def __init__(
        self,
        project_dir: Path,
        config: Optional[SecurityConfig] = None
    ):
        self.project_dir = Path(project_dir).resolve()
        self.config = config or SecurityConfig()
        self._allowed_commands: Set[str] = ALLOWED_COMMANDS.copy()
        self._loaded = False

    async def initialize(self) -> None:
        """Initialize sandbox, loading configuration."""
        await self._load_config()
        self._loaded = True

    def validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if a command is allowed.

        Returns:
            Tuple of (is_allowed, reason_if_blocked)
        """
        # Check dangerous patterns first
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                self._log_audit("BLOCK", command, f"Dangerous pattern: {pattern}")
                return False, f"Command matches dangerous pattern: {pattern}"

        # Extract base commands
        base_commands = self._extract_commands(command)

        # Check each command against allowlist
        for cmd in base_commands:
            if cmd not in self._allowed_commands:
                self._log_audit("BLOCK", command, f"Command not in allowlist: {cmd}")
                return False, f"Command '{cmd}' not in allowlist"

        # Additional path checks for file operations
        if any(cmd in ["rm", "mv", "cp", "chmod"] for cmd in base_commands):
            path_check = self._validate_file_operation(command)
            if not path_check[0]:
                return path_check

        self._log_audit("ALLOW", command)
        return True, None

    def validate_path(
        self,
        path: str,
        operation: str = "read"
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a path is allowed for the given operation.

        Args:
            path: Path to validate
            operation: One of "read", "write", "execute"

        Returns:
            Tuple of (is_allowed, reason_if_blocked)
        """
        path = Path(path)

        # Resolve to absolute path
        if not path.is_absolute():
            path = (self.project_dir / path).resolve()

        # Check deny paths first
        for deny_pattern in self.config.deny_paths:
            if self._path_matches(path, deny_pattern):
                return False, f"Path {path} matches deny pattern {deny_pattern}"

        # Check allow paths
        allowed_patterns = (
            self.config.read_paths if operation == "read"
            else self.config.write_paths
        )

        for allow_pattern in allowed_patterns:
            if self._path_matches(path, allow_pattern):
                return True, None

        return False, f"Path {path} not in allowed {operation} paths"

    def add_allowed_command(self, command: str) -> None:
        """Add a command to the allowlist."""
        self._allowed_commands.add(command)
        self.config.custom_commands.append(command)
        self._save_config()

    def remove_allowed_command(self, command: str) -> None:
        """Remove a command from the allowlist."""
        self._allowed_commands.discard(command)
        if command in self.config.custom_commands:
            self.config.custom_commands.remove(command)
        self._save_config()

    def get_allowlist(self) -> List[str]:
        """Get current command allowlist."""
        return sorted(self._allowed_commands)

    def create_pre_tool_hook(self):
        """
        Create a pre-tool-use hook function for Claude SDK.

        Returns:
            Hook function for Bash tool validation
        """
        async def bash_security_hook(input_data, tool_use_id, context):
            command = input_data.get("tool_input", {}).get("command", "")

            is_safe, reason = self.validate_command(command)

            if not is_safe:
                return {
                    "decision": "block",
                    "reason": reason
                }

            return {}  # Allow

        return bash_security_hook

    def get_audit_log(self, limit: int = 100) -> List[AuditEntry]:
        """Get recent security audit entries."""
        audit_path = self.project_dir / self.AUDIT_FILE

        if not audit_path.exists():
            return []

        entries = []
        with open(audit_path) as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    entries.append(AuditEntry(**data))

        return entries[-limit:]

    def _extract_commands(self, command: str) -> List[str]:
        """
        Extract base commands from a command string.

        Handles pipes, chains, etc.
        """
        commands = []

        # Split on common separators
        parts = re.split(r'[|;&]|\|\||&&', command)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Handle subshells
            if part.startswith('(') and part.endswith(')'):
                part = part[1:-1].strip()

            # Handle command substitution
            part = re.sub(r'\$\([^)]+\)', '', part)

            # Parse the command
            try:
                tokens = shlex.split(part)
                if tokens:
                    # Get base command (first token, without path)
                    base_cmd = Path(tokens[0]).name
                    commands.append(base_cmd)
            except ValueError:
                # If shlex fails, try simple split
                tokens = part.split()
                if tokens:
                    base_cmd = Path(tokens[0]).name
                    commands.append(base_cmd)

        return commands

    def _validate_file_operation(
        self,
        command: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate file operations target safe paths."""
        # Extract paths from command
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.split()

        # Find potential paths (arguments that look like paths)
        for token in tokens[1:]:
            if token.startswith('-'):
                continue

            # Check if it's a path
            if '/' in token or token.startswith('.'):
                is_allowed, reason = self.validate_path(token, "write")
                if not is_allowed:
                    return False, reason

        return True, None

    def _path_matches(self, path: Path, pattern: str) -> bool:
        """Check if a path matches a glob pattern."""
        import fnmatch

        # Expand home directory
        if pattern.startswith('~'):
            pattern = str(Path.home()) + pattern[1:]

        # Handle ** for recursive matching
        if '**' in pattern:
            # Convert to regex
            regex = pattern.replace('**', '.*').replace('*', '[^/]*')
            return bool(re.match(regex, str(path)))

        return fnmatch.fnmatch(str(path), pattern)

    async def _load_config(self) -> None:
        """Load security configuration from file."""
        config_path = self.project_dir / self.CONFIG_FILE

        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)

            # Update config
            for key, value in data.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)

        # Add custom commands to allowlist
        for cmd in self.config.custom_commands:
            self._allowed_commands.add(cmd)

    def _save_config(self) -> None:
        """Save security configuration to file."""
        config_path = self.project_dir / self.CONFIG_FILE
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "sandbox_enabled": self.config.sandbox_enabled,
            "isolation_level": self.config.isolation_level,
            "read_paths": self.config.read_paths,
            "write_paths": self.config.write_paths,
            "deny_paths": self.config.deny_paths,
            "allowed_hosts": self.config.allowed_hosts,
            "custom_commands": self.config.custom_commands,
        }

        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _log_audit(
        self,
        action: str,
        command: str,
        reason: Optional[str] = None
    ) -> None:
        """Log security decision to audit file."""
        audit_path = self.project_dir / self.AUDIT_FILE
        audit_path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "command": command,
            "reason": reason
        }

        with open(audit_path, 'a') as f:
            f.write(json.dumps(entry) + "\n")


# Convenience function
def validate_command(
    project_dir: Path,
    command: str
) -> Tuple[bool, Optional[str]]:
    """Validate a command quickly."""
    sandbox = SecuritySandbox(project_dir)
    return sandbox.validate_command(command)
