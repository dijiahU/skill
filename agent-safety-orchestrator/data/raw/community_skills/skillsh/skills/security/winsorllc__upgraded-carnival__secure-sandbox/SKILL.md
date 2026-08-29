---
name: secure-sandbox
description: Secure command execution sandbox with approval workflows, dangerous command detection, allowlisting, and audit logging. Runs commands in restricted environments with safety guardrails.
metadata:
  version: "1.0.0"
  author: "PopeBot (inspired by OpenClaw + ZeroClaw)"
  tags: ["security", "sandbox", "approval", "execution", "guardrails"]
---

# Secure Sandbox Execution Skill

A security-focused execution environment inspired by OpenClaw's exec-approvals and ZeroClaw's secure-by-default runtime. This skill provides guardrails for running commands safely with approval workflows, allowlisting, and comprehensive audit logging.

## Purpose

When enabled, this skill intercepts command execution and:
1. **Detects dangerous operations** (destructive commands, system modifications)
2. **Enforces allowlists** (only pre-approved commands run automatically)
3. **Queues approvals** (suspicious commands wait for user review)
4. **Creates audit trails** (every command is logged with context)
5. **Provides dry-run mode** (preview effects before execution)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Command Execution Flow                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  User Command → Parse → Classify → Decision → Execute/Queue     │
│                          │                                      │
│              ┌───────────┼───────────┐                         │
│              ▼           ▼           ▼                         │
│         [SAFE]      [DANGEROUS]   [DISALLOWED]                  │
│              │           │           │                         │
│              ▼           ▼           ▼                         │
│         Execute     Requires      Blocked                       │
│         + Log       Approval       + Alert                      │
│                     + Queue                                     │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Approval Queue                          │   │
│  │  Commands awaiting user review with full context          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Audit Log                               │   │
│  │  Timestamp | Command | User | Status | Output | Risk      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Setup

```bash
cd /job/.pi/skills/secure-sandbox
npm install
```

## Configuration

Create `SANDBOX.md` in your workspace root to configure the sandbox:

```markdown
# Secure Sandbox Configuration

## Security Level
Level: allowlist

## Allowed Commands (Auto-execute)
- ls
- pwd
- cat
- echo
- grep
- rg
- node --version
- npm list

## Dangerous Patterns (Require Approval)
- rm -rf
- dd if=
- mkfs
- sudo
- chmod 777
- *

## Disallowed Commands (Block)
- curl http://
- wget http://
- nc -l
- bash -c
- eval

## Approval Settings
- Auto-approve safe: true
- Dry-run by default: false
- Audit retention: 30 days
```

## Commands

### Check Command Safety

```bash
# Analyze a command's risk level
sandbox-check "rm -rf /tmp/*"
```

Output:
```json
{
  "command": "rm -rf /tmp/*",
  "risk_level": "dangerous",
  "risk_reasons": ["Recursive deletion", "Wildcard pattern"],
  "requires_approval": true,
  "suggested_action": "queue_for_approval"
}
```

### Execute with Approval

```bash
# Run with automatic safety checks
sandbox-exec "npm install --save express"

# Force approval even for safe commands
sandbox-exec --require-approval "cat ~/.ssh/id_rsa.pub"

# Dry-run mode (show what would happen)
sandbox-exec --dry-run "rm -rf node_modules"
```

### Manage Approval Queue

```bash
# List pending approvals
sandbox-queue list

# Approve a command
sandbox-queue approve <id>

# Reject a command
sandbox-queue reject <id> --reason "Too risky"

# Clear old approvals
sandbox-queue clear --older-than 7d
```

### View Audit Log

```bash
# Show recent executions
sandbox-audit log --last 20

# Show only dangerous commands
sandbox-audit log --risk-level dangerous

# Export audit log
sandbox-audit export --format json --output /tmp/audit.json

# Statistics
sandbox-audit stats
```

### Manage Allowlist

```bash
# Add command to allowlist
sandbox-allowlist add "cargo build" --reason "Safe build command"

# Remove from allowlist
sandbox-allowlist remove "cargo build"

# List all allowed patterns
sandbox-allowlist list

# Test if a command matches allowlist
sandbox-allowlist test "npm install"
```

## Tools Added

When this skill is active, the following tools are available:

### `sandbox_check`

Analyze a command for safety before execution.

```javascript
sandbox_check({
  command: "rm -rf /tmp/*",
  context: { working_dir: "/job", user: "agent" }
})
```

### `sandbox_exec`

Execute a command with safety checks and approval workflow.

```javascript
sandbox_exec({
  command: "npm install express",
  require_approval: false,      // Force approval even if safe
  dry_run: false,                // Show what would happen
  timeout: 60000,               // Execution timeout
  env: { NODE_ENV: "production" } // Extra environment variables
})
```

### `sandbox_queue_list`

List commands awaiting approval.

```javascript
sandbox_queue_list({ status: "pending" })  // pending, approved, rejected, all
```

### `sandbox_queue_approve`

Approve a queued command for execution.

```javascript
sandbox_queue_approve({
  id: "cmd_abc123",
  approved_by: "user@example.com",
  notes: "Approved for deployment"
})
```

### `sandbox_queue_reject`

Reject a queued command.

```javascript
sandbox_queue_reject({
  id: "cmd_abc123",
  rejected_by: "user@example.com",
  reason: "Security risk - deletes system files"
})
```

### `sandbox_audit_log`

Query the audit log.

```javascript
sandbox_audit_log({
  limit: 50,
  risk_level: "dangerous",  // safe, normal, dangerous, critical
  since: "2026-02-01",
  command_pattern: "rm*"
})
```

### `sandbox_audit_stats`

Get execution statistics.

```javascript
sandbox_audit_stats({
  period: "7d"  // 1d, 7d, 30d, all
})
```

### `sandbox_allowlist_add`

Add a command pattern to the allowlist.

```javascript
sandbox_allowlist_add({
  pattern: "npm install *",
  description: "Install npm packages",
  auto_approve: true
})
```

### `sandbox_allowlist_remove`

Remove a pattern from the allowlist.

```javascript
sandbox_allowlist_remove({ pattern: "npm install *" })
```

### `sandbox_allowlist_test`

Test if a command matches the allowlist.

```javascript
sandbox_allowlist_test({ command: "npm install express" })
```

## Risk Classification

Commands are classified by risk level:

| Level | Description | Examples | Default Action |
|-------|-------------|----------|----------------|
| `safe` | Read-only, informational | `ls`, `cat`, `pwd`, `echo` | Auto-execute |
| `normal` | Common operations | `npm install`, `git clone` | Auto-execute |
| `dangerous` | Destructive or system-modifying | `rm -rf`, `chmod 777` | Require approval |
| `critical` | High security risk | `curl | bash`, `eval` | Block + alert |
| `disallowed` | Explicitly forbidden | Patterns in denylist | Block |

## Usage in Agent Prompt

When this skill is active, include this context:

```
## Secure Sandbox Execution

You have access to a secure command execution environment with safety guardrails.

### When to Use

Always wrap potentially dangerous commands with sandbox tools:
- File deletion (`rm`, `unlink`)
- Permission changes (`chmod`, `chown`)
- System modifications (`sudo`, `mount`)
- Network downloads (`curl`, `wget`)
- Code evaluation (`eval`, `exec`)

### Available Commands

**sandbox_check(command)** - Analyze risk before execution
**sandbox_exec(command, options)** - Execute with safety checks
**sandbox_queue_list(status?)** - View pending approvals
**sandbox_queue_approve(id)** - Approve a queued command
**sandbox_queue_reject(id, reason)** - Reject a queued command
**sandbox_audit_log(options?)** - Query execution history
**sandbox_audit_stats(period?)** - Get execution statistics

### Risk Levels

- SAFE: Auto-executed (ls, cat, pwd)
- NORMAL: Auto-executed (npm install, git clone)  
- DANGEROUS: Requires approval (rm -rf, chmod 777)
- CRITICAL: Blocked (curl | bash, eval from network)
- DISALLOWED: Explicitly forbidden

### Best Practices

1. **Check first**: Use sandbox_check before dangerous operations
2. **Dry run**: Use --dry-run for destructive commands
3. **Context matters**: The sandbox considers working directory and user
4. **Audit trail**: Every command is logged - review regularly
5. **Allowlisting**: Pre-approve safe patterns for your workflow

### Example Workflow

```javascript
// 1. Check if command is safe
const check = sandbox_check({ command: "rm -rf node_modules" });

// 2. If dangerous, use approval workflow
if (check.risk_level === "dangerous") {
  const result = sandbox_exec({
    command: "rm -rf node_modules",
    dry_run: true  // Preview first
  });
  
  // After review, execute for real
  sandbox_exec({ command: "rm -rf node_modules" });
}

// 3. Review audit log periodically
const stats = sandbox_audit_stats({ period: "7d" });
console.log(`Executed ${stats.total_commands} commands (${stats.dangerous} dangerous)`);
```
```

## File Structure

```
.pi/skills/secure-sandbox/
├── SKILL.md                    # This file
├── package.json                # Dependencies
├── index.js                    # Main entry point
├── lib/
│   ├── classifier.js          # Risk classification engine
│   ├── allowlist.js         # Allowlist matching
│   ├── queue.js             # Approval queue management
│   ├── auditor.js           # Audit logging
│   └── sandbox.js           # Sandbox execution environment
├── bin/
│   ├── sandbox-check.js     # Check command safety
│   ├── sandbox-exec.js      # Execute with safety
│   ├── sandbox-queue.js     # Manage approval queue
│   └── sandbox-audit.js     # View audit logs
├── templates/
│   └── SANDBOX.md           # Example configuration
├── test/
│   └── sandbox.test.js      # Test suite
└── .sandbox/                 # Runtime data (gitignored)
    ├── queue.json           # Pending approvals
    └── audit/               # Audit log files
        ├── 2026-02-25.jsonl
        └── ...
```

## Security Model

### Threats Addressed

1. **Accidental Destruction**: Prevents unintentional `rm -rf /` type mistakes
2. **Malicious Code**: Blocks known dangerous patterns (eval, curl | bash)
3. **Supply Chain**: Flags installation of unverified packages
4. **Privilege Escalation**: Requires approval for sudo/root operations
5. **Data Exfiltration**: Alerts on suspicious network operations

### Trust Boundaries

- **Sandbox Config**: Controlled by workspace owner (trusted)
- **Allowlist**: Pre-approved commands from config (trusted)
- **Approval Queue**: User-reviewed before execution (trusted after review)
- **Audit Log**: Immutable record of all activity (verification)

## Integration with Other Skills

### With multi-agent-orchestrator
Sub-agents can delegate dangerous operations to the sandbox:
```javascript
parallel_delegates({
  tasks: [
    { agent: "security-checker", task: "scan for vulnerabilities" },
    { agent: "sandbox", task: "safely clean build artifacts" }
  ]
})
```

### With code-intelligence
Analyze code changes before approving related commands:
```javascript
const impact = code_impact_analysis({ files: changed });
if (impact.deletes_important_files) {
  sandbox_allowlist_remove("rm *");
}
```

## Performance

| Metric | Expected |
|--------|----------|
| Classification | <10ms |
| Allowlist lookup | <5ms |
| Audit write | <20ms (async) |
| Sandboxed execution | Add ~50ms overhead |
| Queue operations | <50ms |

## Error Handling

- **Classification failure**: Conservative - treat as dangerous
- **Queue full**: Reject new commands with alert
- **Audit write failure**: Continue execution, alert user
- **Permission denied**: Block with clear error message

## Future Enhancements

- [ ] Container-based sandboxing (Docker)
- [ ] Network policy enforcement
- [ ] File system access controls
- [ ] Resource limits (CPU, memory, IO)
- [ ] Integration with OS-level sandboxing (macOS sandbox, Linux namespaces)
- [ ] Machine learning for anomaly detection
- [ ] Policy as Code (OPA/Rego)

## Inspiration

This skill is inspired by:
- **OpenClaw's exec-approvals**: Per-command security with allowlists
- **ZeroClaw's secure runtime**: Secure-by-default philosophy
- **Linux capabilities**: Fine-grained permission model
- **Docker security**: Container isolation patterns

## When NOT to Use

Don't use the secure sandbox when:
- Running in a fully isolated throwaway environment
- Performance is critical (<50ms overhead matters)
- Commands are fully trusted and generated internally
- The agent needs unrestricted system access

Use it when:
- Commands come from user input or external sources
- Running in production or persistent environments
- Multiple users/agents share the system
- Compliance requires audit trails
