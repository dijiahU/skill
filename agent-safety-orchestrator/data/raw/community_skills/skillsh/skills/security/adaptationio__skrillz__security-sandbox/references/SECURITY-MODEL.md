# Security Model Reference

## Defense in Depth

The security sandbox implements multiple layers of protection:

```
┌─────────────────────────────────────────────────────────────┐
│                      SECURITY LAYERS                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ LAYER 4: APPLICATION HOOKS                            │   │
│  │ PreToolUse hooks validate every tool call            │   │
│  │ Real-time blocking with audit logging                │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ LAYER 3: COMMAND VALIDATION                          │   │
│  │ Parse and validate bash commands                     │   │
│  │ Check against allowlist and dangerous patterns       │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ LAYER 2: SDK PERMISSIONS                             │   │
│  │ Tool and path restrictions via SDK config            │   │
│  │ Read/Write path patterns                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ LAYER 1: OS SANDBOX                                  │   │
│  │ Container/namespace isolation                        │   │
│  │ Resource limits (CPU, memory, files)                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Threat Model

### Threats Addressed

| Threat | Mitigation |
|--------|------------|
| Filesystem destruction | Allowlist blocks rm -rf / |
| Privilege escalation | sudo/su blocked |
| Data exfiltration | Network restrictions |
| Resource exhaustion | CPU/memory limits |
| Remote code execution | curl\|bash pattern blocked |
| Supply chain attack | Package manager monitoring |

### Threats NOT Addressed

- Logic bugs in application code
- Authorized but malicious prompts
- Zero-day vulnerabilities in allowed tools
- Social engineering of human operators

## SDK Integration

### Configuring Security

```python
from scripts.security_manager import SecurityManager, SecurityConfig
from scripts.sandbox_config import SandboxConfig

# Create security configuration
security_config = SecurityConfig(
    sandbox_enabled=True,
    allowlist_strict=True,
    log_blocked_commands=True,
    allow_network=True,
    allow_sudo=False,
)

# Create security manager
manager = SecurityManager(security_config)

# Create sandbox configuration
sandbox_config = SandboxConfig()

# SDK options
sdk_options = {
    **sandbox_config.to_dict(),
    "hooks": {
        "PreToolUse": [manager.pre_tool_hook]
    }
}
```

### Hook Response Format

```python
# Allow (empty response)
return {}

# Block
return {
    "decision": "block",
    "reason": "Command 'rm' is not in allowlist"
}
```

## Audit Logging

All security decisions are logged:

```python
# Get audit log
log = manager.get_audit_log()

# Example entry
{
    "command": "rm -rf important_files/",
    "reason": "Command 'rm' is not in allowlist",
    "tool_use_id": "tool_use_abc123",
    "timestamp": "2025-01-15T10:30:00",
}
```

## Security Best Practices

### 1. Principle of Least Privilege
- Start with minimal allowlist
- Add commands only as needed
- Review allowlist periodically

### 2. Defense in Depth
- Enable all security layers
- Don't rely on single control
- Monitor and alert

### 3. Fail Secure
- Default to blocking unknown commands
- Require explicit allowlist entries
- Log all violations

### 4. Audit Everything
- Enable audit logging
- Review blocked commands
- Investigate patterns

### 5. Limit Blast Radius
- Restrict filesystem paths
- Use minimal network access
- Set resource limits

## Configuration Profiles

### Strict (Recommended for Production)
```python
config = SecurityConfig(
    sandbox_enabled=True,
    allowlist_strict=True,
    allow_network=False,
    allow_sudo=False,
)
```

### Standard (Development)
```python
config = SecurityConfig(
    sandbox_enabled=True,
    allowlist_strict=True,
    allow_network=True,
    allow_sudo=False,
)
```

### Permissive (Trusted Environment Only)
```python
config = SecurityConfig(
    sandbox_enabled=True,
    allowlist_strict=False,
    allow_network=True,
    allow_sudo=False,  # Still block sudo
)
```
