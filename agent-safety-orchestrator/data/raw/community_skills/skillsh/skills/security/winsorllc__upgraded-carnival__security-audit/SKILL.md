---
name: security-audit
description: Scan code for security vulnerabilities and secrets. Detect exposed secrets, insecure patterns, and common vulnerabilities.
---

# Security Audit

Scan code for security vulnerabilities and secrets. Detects exposed API keys, passwords, insecure patterns, and common vulnerabilities.

## Setup

No additional setup required.

## Usage

### Scan for Secrets

```bash
{baseDir}/security-audit.js --scan --path /path/to/code
```

### Check for Vulnerabilities

```bash
{baseDir}/security-audit.js --vulns --path /path/to/code
```

### Full Audit

```bash
{baseDir}/security-audit.js --full --path /path/to/code
```

## Options

| Option | Description | Required |
|--------|-------------|----------|
| `--scan` | Scan for secrets | No |
| `--vulns` | Check for vulnerabilities | No |
| `--full` | Full security audit | No |
| `--path` | Path to scan | Yes |
| `--output` | Output format (json, text) | No |

## Detected Patterns

### Secrets
- AWS keys: `AKIA...`
- GitHub tokens: `ghp_...`, `gho_...`
- Generic API keys
- Private keys (RSA, DSA, EC)
- Database connection strings
- JWT tokens

### Vulnerabilities
- SQL injection patterns
- Command injection patterns
- Path traversal
- Hardcoded passwords
- Weak cryptographic algorithms
- Insecure random

## Output Format

```json
{
  "secrets": [
    {
      "file": "config.js",
      "line": 10,
      "type": "api_key",
      "context": "apiKey = '..."
    }
  ],
  "vulnerabilities": [
    {
      "file": "app.js",
      "line": 25,
      "type": "sql_injection",
      "message": "Potential SQL injection"
    }
  ]
}
```

## When to Use

- Pre-commit security checks
- CI/CD security scanning
- Code review assistance
- Detecting accidental secret exposure
