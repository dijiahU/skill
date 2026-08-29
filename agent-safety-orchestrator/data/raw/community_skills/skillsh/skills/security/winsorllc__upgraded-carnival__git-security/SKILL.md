---
name: git-security
description: Git security scanner with secret detection, commit validation, and pre-commit hooks. Inspired by ZeroClaw's gitleaks integration.
---

# Git Security

Git security scanner with secret detection, commit validation, and pre-commit hooks.

## Capabilities

- Secret detection (API keys, passwords, tokens)
- Pre-commit validation
- Commit message linting
- Branch protection checks
- Security policy validation

## Usage

```bash
# Scan for secrets
/job/.pi/skills/git-security/scan.js --path /repo/path

# Install pre-commit hook
/job/.pi/skills/git-security/install-hook.js /repo/path

# Validate commit message
/job/.pi/skills/git-security/validate-commit.js "commit message"

# Check branch protection
/job/.pi/skills/git-security/check-branch.js
```

## Secret Patterns

- API keys (OpenAI, AWS, GitHub, etc.)
- Database connection strings
- Password patterns
- Token patterns
- Private keys

## When to Use

- Before committing sensitive data
- CI/CD security checks
- Repository audits
- Security compliance

## Inspired By

- ZeroClaw gitleaks integration
- Git hooks security patterns
