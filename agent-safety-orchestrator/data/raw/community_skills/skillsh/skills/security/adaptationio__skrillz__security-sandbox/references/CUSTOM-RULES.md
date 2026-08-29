# Custom Security Rules Reference

## Adding Custom Commands

### Via Code
```python
from scripts.allowlist import Allowlist

allowlist = Allowlist()

# Add single command
allowlist.add("docker")

# Add multiple commands
for cmd in ["kubectl", "helm", "terraform"]:
    allowlist.add(cmd)

# Save to file
allowlist.save(".claude-allowlist.json")
```

### Via Configuration File
```json
{
  "additions": ["docker", "kubectl", "helm"],
  "removals": ["curl", "wget"]
}
```

## Custom Dangerous Patterns

Add patterns to block:

```python
from scripts.command_validator import DANGEROUS_PATTERNS

# Add custom pattern
DANGEROUS_PATTERNS.append(
    (r"aws\s+s3\s+rm\s+--recursive", "Bulk S3 deletion")
)
```

## Custom Validation Rules

Create custom validator:

```python
from scripts.command_validator import ValidationResult

def validate_database_commands(command: str) -> ValidationResult:
    """Block dangerous database operations."""

    if "DROP DATABASE" in command.upper():
        return ValidationResult(
            allowed=False,
            reason="DROP DATABASE is blocked"
        )

    if "DELETE FROM" in command.upper() and "WHERE" not in command.upper():
        return ValidationResult(
            allowed=False,
            reason="DELETE without WHERE clause is blocked"
        )

    return ValidationResult(allowed=True)
```

## Project-Specific Rules

### Node.js Project
```json
{
  "additions": [
    "npm", "npx", "yarn", "pnpm",
    "jest", "vitest", "playwright"
  ],
  "removals": []
}
```

### Python Project
```json
{
  "additions": [
    "python", "python3", "pip", "pip3",
    "poetry", "pytest", "mypy", "ruff"
  ],
  "removals": []
}
```

### Infrastructure Project
```json
{
  "additions": [
    "terraform", "ansible", "kubectl",
    "helm", "docker", "docker-compose"
  ],
  "removals": ["rm"]
}
```

## Environment-Based Configuration

```python
import os
from scripts.sandbox_config import SandboxConfig

env = os.getenv("ENVIRONMENT", "development")

if env == "production":
    config = SandboxConfig(
        enabled=True,
        network=NetworkPermissions(enabled=False),
        break_on_violation=True,
    )
elif env == "staging":
    config = SandboxConfig(
        enabled=True,
        network=NetworkPermissions(enabled=True),
    )
else:  # development
    config = SandboxConfig(
        enabled=True,
        audit_enabled=True,
    )
```

## Rule Precedence

1. **Dangerous patterns** - Always checked first, always block
2. **Custom validators** - Project-specific rules
3. **Removals** - Explicitly removed commands
4. **Additions** - Explicitly added commands
5. **Default allowlist** - Base allowed commands

## Testing Custom Rules

```python
from scripts.command_validator import validate_command
from scripts.allowlist import Allowlist

# Create test allowlist
test_allowlist = Allowlist()
test_allowlist.add("mycommand")
test_allowlist.remove("curl")

# Test commands
def test_custom_rules():
    # Should pass
    result = validate_command("mycommand arg1", test_allowlist.commands)
    assert result.allowed

    # Should fail
    result = validate_command("curl http://example.com", test_allowlist.commands)
    assert not result.allowed
```

## Logging Rule Changes

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("security_rules")

def add_command_with_logging(allowlist: Allowlist, command: str, reason: str):
    """Add command to allowlist with audit logging."""
    logger.info(f"Adding '{command}' to allowlist. Reason: {reason}")
    allowlist.add(command)

# Usage
add_command_with_logging(
    allowlist,
    "docker",
    "Required for container builds in CI"
)
```
