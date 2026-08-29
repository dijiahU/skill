---
title: Security Issues Checklist
impact: CRITICAL
tags: security, audit, vulnerabilities
---

# Security Issues Checklist

Comprehensive list of security issues to identify during code audits.

## Contents

- [Authentication & Authorization](#authentication--authorization)
- [Injection Risks](#injection-risks)
- [Server-Side Request Forgery (SSRF)](#server-side-request-forgery-ssrf)
- [Path Traversal](#path-traversal)
- [Secrets & Insecure Defaults](#secrets--insecure-defaults)
- [Cryptographic Issues](#cryptographic-issues)
- [Input Validation](#input-validation)
- [Dependency Vulnerabilities](#dependency-vulnerabilities)
- [Severity Classification](#severity-classification)

## Authentication & Authorization

**Auth errors to find:**

- Missing authentication on sensitive endpoints
- Broken session management
- Insecure password storage (plaintext, weak hashing)
- Missing or bypassable authorization checks
- Privilege escalation paths
- Insecure direct object references (IDOR)

**Example finding:**

```typescript
// BAD: No auth check before accessing user data
app.get('/api/users/:id', (req, res) => {
  return db.users.findById(req.params.id) // Anyone can access any user
})
```

## Injection Risks

**Types to identify:**

- SQL injection
- Command injection
- XSS (Cross-Site Scripting)
- LDAP injection
- XML injection
- Template injection

**Example finding:**

```typescript
// BAD: SQL injection vulnerability
const query = `SELECT * FROM users WHERE id = ${req.params.id}`
db.query(query)

// BAD: Command injection
exec(`ls ${userInput}`)

// BAD: XSS vulnerability
element.innerHTML = userProvidedContent
```

## Server-Side Request Forgery (SSRF)

**Indicators:**

- User-controlled URLs passed to fetch/request functions
- Missing URL validation or allowlisting
- Internal service URLs accessible via user input

**Example finding:**

```typescript
// BAD: SSRF vulnerability
const url = req.body.imageUrl
const response = await fetch(url) // Can access internal services
```

## Path Traversal

**Indicators:**

- User input used in file paths
- Missing path sanitization
- Relative path components (`..`) not blocked

**Example finding:**

```typescript
// BAD: Path traversal
const filePath = `./uploads/${req.params.filename}`
fs.readFile(filePath) // Can read ../../etc/passwd
```

## Secrets & Insecure Defaults

**Check for:**

- Hardcoded credentials, API keys, tokens
- Default passwords in config
- Secrets in source control
- Insecure default configurations
- Debug mode enabled in production

**Example finding:**

```typescript
// BAD: Hardcoded secret
const API_KEY = 'sk-1234567890abcdef'

// BAD: Insecure default
const config = {
  debug: true, // Should be false in production
  validateSSL: false, // Disables certificate validation
}
```

## Cryptographic Issues

**Check for:**

- Weak algorithms (MD5, SHA1 for security, DES, RC4)
- Hardcoded IVs or salts
- Missing encryption for sensitive data
- Insecure random number generation
- Improper key management

**Example finding:**

```typescript
// BAD: Weak hashing
const hash = crypto.createHash('md5').update(password).digest('hex')

// BAD: Insecure random
const token = Math.random().toString(36) // Not cryptographically secure
```

## Input Validation

**Check for:**

- Missing validation on user inputs
- Type coercion vulnerabilities
- Length/size limits not enforced
- Format validation missing
- Prototype pollution risks

**Example finding:**

```typescript
// BAD: No input validation
app.post('/api/update', (req, res) => {
  Object.assign(user, req.body) // Prototype pollution risk
})
```

## Dependency Vulnerabilities

**Check for:**

- Known CVEs in dependencies
- Outdated packages with security patches
- Unused dependencies increasing attack surface
- Dependencies from untrusted sources

**How to identify:**

```bash
npm audit
pip-audit
snyk test
```

## Severity Classification

| Severity | Criteria                                     | Examples                            |
| -------- | -------------------------------------------- | ----------------------------------- |
| P0       | Exploitable, high impact, no auth required   | RCE, SQL injection, auth bypass     |
| P1       | Exploitable with some prerequisites          | SSRF, stored XSS, IDOR              |
| P2       | Limited impact or difficult to exploit       | Reflected XSS, info disclosure      |
