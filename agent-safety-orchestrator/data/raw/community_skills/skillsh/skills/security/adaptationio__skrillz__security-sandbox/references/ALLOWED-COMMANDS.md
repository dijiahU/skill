# Allowed Commands Reference

## Default Allowlist

### File Inspection
| Command | Purpose | Safe |
|---------|---------|------|
| `ls` | List directory contents | Yes |
| `cat` | Display file contents | Yes |
| `head` | Display first lines | Yes |
| `tail` | Display last lines | Yes |
| `wc` | Word/line/byte count | Yes |
| `grep` | Search file contents | Yes |
| `find` | Find files | Yes |
| `file` | Determine file type | Yes |
| `stat` | File statistics | Yes |
| `du` | Disk usage | Yes |
| `df` | Filesystem space | Yes |

### File Operations
| Command | Purpose | Notes |
|---------|---------|-------|
| `cp` | Copy files | |
| `mv` | Move/rename files | |
| `mkdir` | Create directory | |
| `chmod` | Change permissions | Block 777 |
| `touch` | Create/update file | |
| `ln` | Create links | |

### Text Processing
| Command | Purpose |
|---------|---------|
| `sed` | Stream editor |
| `awk` | Pattern processing |
| `sort` | Sort lines |
| `uniq` | Filter duplicates |
| `cut` | Cut columns |
| `tr` | Translate characters |
| `diff` | Compare files |
| `patch` | Apply patches |

### Node.js Ecosystem
| Command | Purpose |
|---------|---------|
| `npm` | Package manager |
| `node` | JavaScript runtime |
| `npx` | Run npm packages |
| `yarn` | Alternative package manager |
| `pnpm` | Fast package manager |

### Python Ecosystem
| Command | Purpose |
|---------|---------|
| `python` | Python 2 interpreter |
| `python3` | Python 3 interpreter |
| `pip` | Package installer |
| `pip3` | Python 3 packages |
| `poetry` | Dependency management |
| `pipenv` | Virtual environments |
| `pytest` | Testing framework |
| `mypy` | Type checker |
| `black` | Code formatter |
| `isort` | Import sorter |
| `flake8` | Linter |
| `ruff` | Fast linter |

### Version Control
| Command | Purpose | Notes |
|---------|---------|-------|
| `git` | Git operations | All subcommands |

### Process Management
| Command | Purpose | Notes |
|---------|---------|-------|
| `ps` | List processes | |
| `lsof` | List open files | |
| `sleep` | Delay execution | |
| `pkill` | Kill by name | |
| `kill` | Kill by PID | |
| `pgrep` | Find processes | |

### System Information
| Command | Purpose |
|---------|---------|
| `pwd` | Print working directory |
| `whoami` | Current username |
| `uname` | System information |
| `which` | Locate command |
| `env` | Environment variables |
| `printenv` | Print environment |
| `date` | Current date/time |
| `hostname` | System hostname |
| `id` | User identity |

### Network
| Command | Purpose | Notes |
|---------|---------|-------|
| `curl` | Transfer data | Block pipe to shell |
| `wget` | Download files | Block pipe to shell |
| `ssh` | Secure shell | |
| `scp` | Secure copy | |

### Archive Tools
| Command | Purpose |
|---------|---------|
| `tar` | Archive files |
| `zip` | Compress files |
| `unzip` | Extract archives |
| `gzip` | Compress |
| `gunzip` | Decompress |

### Build Tools
| Command | Purpose |
|---------|---------|
| `make` | Build automation |
| `cmake` | Build configuration |
| `gcc` | C compiler |
| `g++` | C++ compiler |
| `clang` | LLVM compiler |

### Container Tools
| Command | Purpose |
|---------|---------|
| `docker` | Container management |
| `docker-compose` | Multi-container |
| `podman` | Rootless containers |

### Cloud CLI
| Command | Purpose |
|---------|---------|
| `aws` | Amazon Web Services |
| `gcloud` | Google Cloud |
| `az` | Microsoft Azure |
| `railway` | Railway.app |

## Restricted Commands

These commands are NOT in the default allowlist but can be added:

| Command | Risk | Notes |
|---------|------|-------|
| `rm` | File deletion | Add with caution |
| `sudo` | Privilege escalation | Generally blocked |
| `su` | User switching | Generally blocked |
| `chown` | Ownership changes | Add for deployment |
| `mount` | Filesystem mounting | Generally blocked |

## Adding Custom Commands

```python
from scripts.allowlist import Allowlist

allowlist = Allowlist()

# Add a command
allowlist.add("rm")

# Remove a command
allowlist.remove("curl")

# Save configuration
allowlist.save(".claude-allowlist.json")
```

## Environment-Specific Lists

### Minimal (High Security)
```python
MINIMAL = {
    "ls", "cat", "head", "tail", "grep", "find",
    "pwd", "whoami", "env", "which",
    "git", "node", "npm", "python", "python3",
}
```

### Development (Standard)
The default allowlist is suitable for most development.

### CI/CD (Extended)
```python
CI_CD = DEFAULT_ALLOWLIST | {
    "rm",  # For cleanup
    "docker",
    "kubectl",
}
```
