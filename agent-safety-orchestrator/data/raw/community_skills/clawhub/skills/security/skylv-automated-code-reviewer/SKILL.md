---
name: automated-code-reviewer
slug: automated-code-reviewer
version: 1.0.1
description: Review code in seconds, not hours. Detect bugs, security flaws, and style issues before they reach production.
author: SKY-lv
license: MIT-0
tags: [automation, code-quality, review]
keywords: [code review, PR review, automated review, code analysis, code quality, pull request, bug detection, coding standards]
triggers: code review, PR review, review code, analyze code, code quality
---

# automated-code-reviewer

> Review code in seconds, not hours. Catch bugs, security flaws, and style issues before they reach production — consistent, thorough, and unbiased.

## What It Does

- **Bug detection** — Null pointers, resource leaks, race conditions, off-by-one
- **Security scan** — OWASP Top 10, injection, XSS, auth issues
- **Style enforcement** — Airbnb, Google, PEP8, or custom rules
- **Performance** — N+1 queries, memory leaks, slow algorithms
- **PR integration** — Auto-review every pull request

---

## Quick Start

```bash
# 1. Review a pull request
node review.js analyze --pr 42 --repo owner/repo

# 2. Review local diff
node review.js analyze --diff HEAD~3

# 3. Security-focused review
node review.js security --check owasp-top10

# 4. Apply auto-fixes
node review.js lint --standard airbnb --fix
```

---

## Common Use Cases

### 🔍 Review Pull Request
```bash
# Full PR review
node review.js analyze --pr 42 --repo owner/repo

# Review with specific focus
node review.js analyze --pr 42 --focus bugs,security

# Block merge if issues found
node review.js analyze --pr 42 --fail-on error
```

### 🛡️ Security Audit
```bash
# OWASP Top 10 scan
node review.js security --check owasp-top10

# Focus on specific vulnerabilities
node review.js security --focus injection,xss,auth

# Full codebase scan
node review.js security --src ./src --recursive
```

### 🐛 Find Bugs Early
```bash
# Detect common bug patterns
node review.js detect-bugs --severity medium+

# Focus on specific issues
node review.js detect-bugs --focus null-pointer,resource-leak,off-by-one

# Include suggestions
node review.js detect-bugs --suggest-fix
```

### 📏 Enforce Coding Standards
```bash
# Lint with auto-fix
node review.js lint --standard airbnb --fix

# Custom rules
node review.js lint --custom-rules .reviewrules.json

# Check multiple languages
node review.js lint --js airbnb --python pep8 --go effective-go
```

---

## All Commands

| Command | Purpose |
|---------|---------|
| `analyze --pr <n>` | Review pull request |
| `detect-bugs` | Find bug patterns |
| `security --check <type>` | Security vulnerability scan |
| `lint --standard <s>` | Enforce coding style |
| `performance` | Find performance issues |
| `analyze --diff <ref>` | Review local diff |

---

## Configuration

```json
{
  "review": {
    "severity": "medium",
    "categories": ["bugs", "security", "performance", "style"],
    "autoApprove": ["docs-only", "formatting"],
    "requireApproval": ["security", "breaking-change"],
    "languageRules": {
      "javascript": "airbnb",
      "python": "pep8",
      "go": "effective-go"
    }
  }
}
```
