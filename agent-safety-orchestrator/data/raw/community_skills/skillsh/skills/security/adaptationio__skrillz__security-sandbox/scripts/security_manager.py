"""
Security Manager for Autonomous Coding

Provides the main security interface including hooks, validation,
and sandbox configuration.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Any
import json
import logging


class SecurityDecision(Enum):
    """Security hook decisions."""
    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class HookResult:
    """Result from a security hook."""
    decision: SecurityDecision
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        result = {}
        if self.decision == SecurityDecision.BLOCK:
            result["decision"] = "block"
            result["reason"] = self.reason or "Blocked by security policy"
        return result


@dataclass
class SecurityConfig:
    """Security configuration options."""
    sandbox_enabled: bool = True
    allowlist_strict: bool = True
    log_blocked_commands: bool = True
    allow_network: bool = True
    allow_sudo: bool = False
    max_command_length: int = 10000
    blocked_paths: list = None

    def __post_init__(self):
        if self.blocked_paths is None:
            self.blocked_paths = ["/etc", "/sys", "/proc", "/boot"]


class SecurityManager:
    """
    Main security manager for autonomous coding.

    Provides:
    - Command validation
    - Security hooks for SDK integration
    - Allowlist management
    - Audit logging
    """

    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.logger = logging.getLogger("security_manager")
        self._audit_log: list[dict] = []

    async def pre_tool_hook(
        self,
        input_data: dict,
        tool_use_id: str = None,
        context: dict = None
    ) -> dict:
        """
        Pre-tool-use hook for Claude SDK integration.

        This hook is called before each tool invocation.

        Args:
            input_data: Tool input data containing tool_input
            tool_use_id: Unique ID for this tool use
            context: Additional context

        Returns:
            Empty dict if allowed, or {"decision": "block", "reason": "..."}
        """
        tool_input = input_data.get("tool_input", {})
        command = tool_input.get("command", "")

        if not command:
            return {}

        result = self.validate_command(command)

        if result.decision == SecurityDecision.BLOCK:
            self._log_blocked(command, result.reason, tool_use_id)
            return result.to_dict()

        return {}

    def validate_command(self, command: str) -> HookResult:
        """
        Validate a bash command.

        Args:
            command: The command to validate

        Returns:
            HookResult with decision
        """
        from .command_validator import validate_command, ValidationResult

        # Check command length
        if len(command) > self.config.max_command_length:
            return HookResult(
                SecurityDecision.BLOCK,
                f"Command exceeds max length ({self.config.max_command_length})"
            )

        # Run validation
        result = validate_command(command)

        if not result.allowed:
            return HookResult(SecurityDecision.BLOCK, result.reason)

        # Check for blocked paths
        for path in self.config.blocked_paths:
            if path in command:
                return HookResult(
                    SecurityDecision.BLOCK,
                    f"Access to {path} is not allowed"
                )

        # Check for sudo
        if not self.config.allow_sudo and "sudo" in command.split():
            return HookResult(
                SecurityDecision.BLOCK,
                "sudo is not allowed"
            )

        return HookResult(SecurityDecision.ALLOW)

    def _log_blocked(
        self,
        command: str,
        reason: str,
        tool_use_id: Optional[str] = None
    ) -> None:
        """Log a blocked command for audit."""
        if not self.config.log_blocked_commands:
            return

        entry = {
            "command": command[:500],  # Truncate for safety
            "reason": reason,
            "tool_use_id": tool_use_id,
        }
        self._audit_log.append(entry)
        self.logger.warning(f"Blocked command: {command[:100]}... Reason: {reason}")

    def get_audit_log(self) -> list[dict]:
        """Get the audit log of blocked commands."""
        return self._audit_log.copy()

    def clear_audit_log(self) -> None:
        """Clear the audit log."""
        self._audit_log.clear()


def create_bash_security_hook(
    config: Optional[SecurityConfig] = None
) -> Callable:
    """
    Create a bash security hook function for SDK integration.

    Args:
        config: Optional security configuration

    Returns:
        Async hook function
    """
    manager = SecurityManager(config)
    return manager.pre_tool_hook


def create_security_hooks(
    config: Optional[SecurityConfig] = None
) -> dict[str, list[Callable]]:
    """
    Create all security hooks for SDK configuration.

    Args:
        config: Optional security configuration

    Returns:
        Hooks dictionary for SDK options
    """
    manager = SecurityManager(config)

    return {
        "PreToolUse": [manager.pre_tool_hook]
    }
