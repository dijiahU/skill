---
name: skylv-secrets-scanner
slug: skylv-secrets-scanner
version: 1.0.0
description: "Scans code for leaked secrets, API keys, tokens, and passwords. Triggers: scan secrets, check api key, security scan, leaked token."
author: SKY-lv
license: MIT
tags: [automation, tools]
keywords: [automation, tools]
triggers: secrets-scanner
---

# Secrets Scanner

## Overview
Scans repositories for accidentally committed secrets and API keys.

## When to Use
- User asks to "scan for secrets" or "security audit"
- Pre-commit or pre-push security check

## Patterns to Detect
AWS Key: AKIA[0-9A-Z]{16}
GitHub Token: ghp_[a-zA-Z0-9]{36}
Generic API Key: api[_-]?key.*[a-zA-Z0-9]{20,}
Private Key: -----BEGIN (RSA|DSA|EC) PRIVATE KEY-----
Password in URL: ://[^@]+:.*@
Slack Token: xox[baprs]-[0-9]{10,13}-[0-9]{10,13}

## Commands
Windows:
Select-String -Path . -Include *.js,*.py -Recurse -Pattern "ghp_[a-zA-Z0-9]{36}"

Linux/macOS:
grep -rE "ghp_[a-zA-Z0-9]{36}|AKIA[0-9A-Z]{16}" --include="*.js" --include="*.py" .

## Prevention
Add to .gitignore:
.env
*.key
credentials.*
secrets.*
*.pem
