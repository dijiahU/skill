---
name: Security Scanner
author: PopeBot
description: Security analysis and vulnerability scanning for code and configuration files. Detects secrets, misconfigurations, and potential security issues.
version: "1.0.0"
tags:
  - security
  - scanning
  - vulnerabilities
  - secrets
  - audit
---

# Security Scanner

Security analysis and vulnerability scanning for code and configuration files. Detects secrets, misconfigurations, and potential security issues.

## When to Use

Use the security-scanner skill when:
- Auditing security before commits
- Finding hardcoded secrets
- Detecting misconfigurations
- Scanning for vulnerabilities
- Validating security posture

## Usage Examples

Full scan:
```bash
node /job/.pi/skills/security-scanner/security.js scan --full
```

Scan specific files:
```bash
node /job/.pi/skills/security-scanner/security.js scan file.js config.json
```

Check for secrets:
```bash
node /job/.pi/skills/security-scanner/security.js check --secrets
```

Generate security report:
```bash
node /job/.pi/skills/security-scanner/security.js report --output security.json
```