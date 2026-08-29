# Dangerous Commands Reference

This file documents the dangerous patterns that `hooks/danger_guard.py` intercepts.
Used by the PreToolUse hook for always-active protection.

## Severity Levels

| Level | Meaning | Hook Action |
|-------|---------|-------------|
| CRITICAL | Irreversible system/data destruction | Always block, require explicit user confirmation |
| HIGH | Significant security risk | Block first occurrence, allow after user confirms |
| MEDIUM | Moderate risk, usually intentional | Warn and block, low threshold to allow |

## CRITICAL — Bash Patterns

### BASH_RM_ROOT
- **What it catches**: Recursive or forced deletion commands targeting the filesystem root or critical system directories (e.g., `/usr`, `/etc`, `/var`, `/home`, `/boot`)
- **Risk**: Destroys entire filesystem or critical system directories
- **Whitelist**: None — always block

### BASH_RM_HOME
- **What it catches**: Recursive or forced deletion commands targeting the user's home directory
- **Risk**: Destroys all user data
- **Whitelist**: None — always block

### BASH_DISK_DESTROY
- **What it catches**: Commands that format disks, overwrite block devices directly, or wipe filesystem signatures
- **Risk**: Formats disk or overwrites device directly
- **Whitelist**: None — always block

### BASH_FORK_BOMB
- **What it catches**: Classic fork bomb patterns and similar constructs that recursively spawn processes
- **Risk**: Crashes system by exhausting process table
- **Whitelist**: None — always block

### BASH_SQL_DROP
- **What it catches**: Destructive SQL statements that drop tables/databases, truncate tables, or delete all rows without a WHERE clause
- **Risk**: Irreversible data loss in databases
- **Whitelist**: None — always block

## HIGH — Bash Patterns

### BASH_RCE_PIPE
- **What it catches**: Commands that download content from a remote URL and pipe it directly to a script interpreter for execution
- **Risk**: Executes arbitrary remote code
- **Whitelist**: None

### BASH_RCE_DOWNLOAD_EXEC
- **What it catches**: Commands that download a file, then make it executable and/or run it in a subsequent step
- **Risk**: Downloads and executes unknown binary
- **Whitelist**: None

### BASH_GIT_FORCE_MAIN
- **What it catches**: Force-push commands targeting protected branches (main/master)
- **Risk**: Rewrites shared branch history, may lose team's work
- **Whitelist**: Force push to non-main/master branches is allowed

### BASH_GIT_RESET_HARD
- **What it catches**: Hard reset commands that discard all uncommitted changes
- **Risk**: Discards all uncommitted changes
- **Whitelist**: None (user must confirm explicitly)

### BASH_REVERSE_SHELL
- **What it catches**: Commands that establish a reverse shell connection — redirecting an interactive shell through a network socket to a remote host
- **Risk**: Opens reverse shell to attacker
- **Whitelist**: None

### BASH_SYSTEM_FILE
- **What it catches**: Commands that write to or overwrite critical system configuration files (password files, sudoers, SSH config) or shell startup scripts
- **Risk**: System or shell configuration tampering
- **Whitelist**: None

### BASH_SSH_KEY
- **What it catches**: Commands that read, copy, or transmit SSH private key files
- **Risk**: SSH private key exposure
- **Whitelist**: None

## MEDIUM — Bash Patterns

### BASH_CHMOD_777
- **What it catches**: Permission changes that set files or directories to world-readable/writable (777 permissions)
- **Risk**: Makes files world-readable/writable
- **Whitelist**: None

### BASH_SUDO
- **What it catches**: Commands executed with elevated privileges via sudo
- **Risk**: Elevated privilege operation
- **Whitelist**: Common package manager invocations (apt, brew, yum, dnf, pacman, pip)

### BASH_NO_VERIFY
- **What it catches**: Flags that explicitly skip verification or weaken security posture <!-- noscan -->
- **Risk**: Bypasses security checks <!-- noscan -->
- **Whitelist**: Git commit verification skip (sometimes intentional) <!-- noscan -->

### BASH_SSL_DISABLE
- **What it catches**: Environment variable assignments that turn off certificate verification <!-- noscan -->
- **Risk**: Turns off transport layer encryption verification <!-- noscan -->
- **Whitelist**: None

### BASH_CRONTAB_WRITE <!-- noscan -->
- **What it catches**: Commands that modify scheduled task configurations or write to their config directories <!-- noscan -->
- **Risk**: Persistence mechanism — schedules recurring execution
- **Whitelist**: None

## HIGH — File Write Patterns

### WRITE_SSH / WRITE_AWS / WRITE_GNUPG
- **Target**: SSH, cloud provider, and GPG credential directories
- **Risk**: Modifying credential stores
- **Whitelist**: Host key database and client config files (safe to update) <!-- noscan -->

### WRITE_ETC
- **Target**: System configuration directory (`/etc/`)
- **Risk**: System configuration modification
- **Whitelist**: None

### WRITE_SHELL_RC
- **Target**: Shell startup configuration files (bashrc, zshrc, profile, etc.)
- **Risk**: Shell startup script injection
- **Whitelist**: None

### WRITE_LAUNCH_AGENT
- **Target**: OS-specific autostart directories (macOS LaunchAgents/Daemons, Linux systemd/init.d)
- **Risk**: Autostart persistence
- **Whitelist**: None

## Global Bash Whitelist

These patterns match dangerous rules but are known-safe common operations:

- Deleting common build artifact and cache directories (node_modules, .cache, __pycache__, dist, build, etc.)
- Deleting files under `/tmp/` (temp file cleanup)
- Deleting files using relative paths within the project directory (`./...`)
