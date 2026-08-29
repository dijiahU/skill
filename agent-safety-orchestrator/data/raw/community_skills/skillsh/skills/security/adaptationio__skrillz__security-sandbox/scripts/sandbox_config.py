"""
Sandbox Configuration

Configuration for OS-level sandboxing and SDK security settings.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json


@dataclass
class FilesystemPermissions:
    """Filesystem access permissions."""
    # Paths the agent can read from
    read_paths: list[str] = field(default_factory=lambda: ["./**"])

    # Paths the agent can write to
    write_paths: list[str] = field(default_factory=lambda: ["./**"])

    # Paths that are always blocked
    blocked_paths: list[str] = field(default_factory=lambda: [
        "/etc/**",
        "/sys/**",
        "/proc/**",
        "/boot/**",
        "/root/**",
        "~/.ssh/**",
        "~/.aws/**",
        "~/.config/**",
    ])


@dataclass
class NetworkPermissions:
    """Network access permissions."""
    enabled: bool = True

    # Allowed domains (empty = all allowed if enabled)
    allowed_domains: list[str] = field(default_factory=list)

    # Blocked domains
    blocked_domains: list[str] = field(default_factory=lambda: [
        "*.internal",
        "localhost",
        "127.0.0.1",
    ])

    # Allowed ports (empty = all allowed)
    allowed_ports: list[int] = field(default_factory=list)


@dataclass
class ResourceLimits:
    """Resource usage limits."""
    # Maximum execution time in seconds
    max_execution_time: int = 300

    # Maximum memory in MB
    max_memory_mb: int = 4096

    # Maximum file size in MB
    max_file_size_mb: int = 100

    # Maximum number of processes
    max_processes: int = 50

    # Maximum open files
    max_open_files: int = 1000


@dataclass
class SandboxConfig:
    """
    Complete sandbox configuration.

    Combines filesystem, network, and resource settings.
    """
    enabled: bool = True

    filesystem: FilesystemPermissions = field(
        default_factory=FilesystemPermissions
    )
    network: NetworkPermissions = field(
        default_factory=NetworkPermissions
    )
    resources: ResourceLimits = field(
        default_factory=ResourceLimits
    )

    # Enable audit logging
    audit_enabled: bool = True

    # Break on security violations (vs just block)
    break_on_violation: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for SDK configuration."""
        return {
            "sandbox": {
                "enabled": self.enabled,
            },
            "permissions": {
                "allow": [
                    f"Read({p})" for p in self.filesystem.read_paths
                ] + [
                    f"Write({p})" for p in self.filesystem.write_paths
                ] + ["Bash(*)"],
                "deny": [
                    f"Read({p})" for p in self.filesystem.blocked_paths
                ] + [
                    f"Write({p})" for p in self.filesystem.blocked_paths
                ]
            }
        }

    def save(self, filepath: Path) -> None:
        """Save configuration to file."""
        config = {
            "enabled": self.enabled,
            "filesystem": {
                "read_paths": self.filesystem.read_paths,
                "write_paths": self.filesystem.write_paths,
                "blocked_paths": self.filesystem.blocked_paths,
            },
            "network": {
                "enabled": self.network.enabled,
                "allowed_domains": self.network.allowed_domains,
                "blocked_domains": self.network.blocked_domains,
                "allowed_ports": self.network.allowed_ports,
            },
            "resources": {
                "max_execution_time": self.resources.max_execution_time,
                "max_memory_mb": self.resources.max_memory_mb,
                "max_file_size_mb": self.resources.max_file_size_mb,
                "max_processes": self.resources.max_processes,
                "max_open_files": self.resources.max_open_files,
            },
            "audit_enabled": self.audit_enabled,
            "break_on_violation": self.break_on_violation,
        }
        Path(filepath).write_text(json.dumps(config, indent=2))

    @classmethod
    def load(cls, filepath: Path) -> "SandboxConfig":
        """Load configuration from file."""
        if not Path(filepath).exists():
            return cls()

        data = json.loads(Path(filepath).read_text())

        fs = FilesystemPermissions(
            read_paths=data.get("filesystem", {}).get("read_paths", ["./**"]),
            write_paths=data.get("filesystem", {}).get("write_paths", ["./**"]),
            blocked_paths=data.get("filesystem", {}).get("blocked_paths", []),
        )

        net = NetworkPermissions(
            enabled=data.get("network", {}).get("enabled", True),
            allowed_domains=data.get("network", {}).get("allowed_domains", []),
            blocked_domains=data.get("network", {}).get("blocked_domains", []),
            allowed_ports=data.get("network", {}).get("allowed_ports", []),
        )

        res = ResourceLimits(
            max_execution_time=data.get("resources", {}).get("max_execution_time", 300),
            max_memory_mb=data.get("resources", {}).get("max_memory_mb", 4096),
            max_file_size_mb=data.get("resources", {}).get("max_file_size_mb", 100),
            max_processes=data.get("resources", {}).get("max_processes", 50),
            max_open_files=data.get("resources", {}).get("max_open_files", 1000),
        )

        return cls(
            enabled=data.get("enabled", True),
            filesystem=fs,
            network=net,
            resources=res,
            audit_enabled=data.get("audit_enabled", True),
            break_on_violation=data.get("break_on_violation", False),
        )


def create_strict_sandbox() -> SandboxConfig:
    """Create a strict sandbox configuration."""
    return SandboxConfig(
        enabled=True,
        filesystem=FilesystemPermissions(
            read_paths=["./**"],
            write_paths=["./src/**", "./tests/**"],
            blocked_paths=[
                "/etc/**", "/sys/**", "/proc/**",
                "~/**", "/root/**", "/home/**",
            ],
        ),
        network=NetworkPermissions(
            enabled=False,
        ),
        resources=ResourceLimits(
            max_execution_time=60,
            max_memory_mb=1024,
        ),
        break_on_violation=True,
    )


def create_development_sandbox() -> SandboxConfig:
    """Create a permissive development sandbox."""
    return SandboxConfig(
        enabled=True,
        filesystem=FilesystemPermissions(
            read_paths=["**"],
            write_paths=["./**"],
        ),
        network=NetworkPermissions(
            enabled=True,
        ),
        resources=ResourceLimits(
            max_execution_time=600,
            max_memory_mb=8192,
        ),
    )
