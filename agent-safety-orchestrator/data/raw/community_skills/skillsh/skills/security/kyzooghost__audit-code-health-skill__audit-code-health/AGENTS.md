# Code Health Auditor

**Version 1.1.0**  
Vercel Engineering  
January 2026

> **Note:**  
> This document is mainly for agents and LLMs to follow when auditing codebases.
> It compiles all reference material into a single document for deep context.

---

## Abstract

Systematic code audit process that scans directories to identify security vulnerabilities, bugs, and code health issues. Findings are tracked as work items for remediation. Supports flexible audit depth from quick scans (1-2 cycles) to deep audits (6-10 cycles).

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [When to Apply](#when-to-apply)
3. [When NOT to Apply](#when-not-to-apply)
4. [Workflow Overview](#workflow-overview)
5. [Cycle Process](#cycle-process)
6. [Security Issues](#security-issues) — **CRITICAL**
7. [Bugs](#bugs) — **HIGH**
8. [Code Health](#code-health) — **MEDIUM**
9. [Work Item Formats](#work-item-formats)
10. [Output Format](#output-format)
11. [Examples](#examples)

---

## Quick Start

Example: `For @native-yield-operations/automation-service/ do /audit-code-health`

1. **Scan** the target directory for issues
2. **Document** findings in a table (Security → Bugs → Code Health)
3. **File** work items or create a findings summary

---

## When to Apply

Use this skill when:

- Auditing a codebase for security vulnerabilities
- Identifying bugs and edge cases
- Assessing technical debt and code health
- Creating structured work items for remediation
- Running systematic code reviews

---

## When NOT to Apply

Do not use this skill when:

- Developing a new feature
- Writing a new test

---

## Workflow Overview

Audits run in cycles. Choose depth based on scope:

| Scope          | Cycles | When to Use                              |
| -------------- | ------ | ---------------------------------------- |
| Quick scan     | 1-2    | Small PRs, single files, targeted review |
| Standard audit | 3-5    | Feature modules, API surfaces            |
| Deep audit     | 6-10   | Full codebase, security-critical systems |

Each cycle follows: **SCAN → FINDINGS → VERIFY → FILE → TRIAGE**

---

## Cycle Process

### Step 1: SCAN

Analyze the target directory:

- Review code for security issues, bugs, and health problems
- Run read-only tooling: build, tests, lint, typecheck

### Step 2: FINDINGS

Produce a findings table grouped by Security, Bugs, Code Health:

| Severity | Type     | File(s)       | Description        | Confidence |
| -------- | -------- | ------------- | ------------------ | ---------- |
| P0       | Security | `auth/jwt.ts` | Token not verified | High       |

### Step 3: VERIFY

Before filing, validate each finding:

- Confirmed the issue exists (not a false positive)
- Identified the correct file and line number
- Assessed severity accurately
- Checked if issue is already tracked

### Step 4: FILE

Create work items for verified findings.

**If using Beads (`bd`):**
Use the epic/issue structure defined in [Work Item Formats](#work-item-formats).

**If bd is not available:**
Use Markdown task lists:
```markdown
- [ ] [P0/Security] auth/jwt.ts: Token not verified
```

### Step 5: TRIAGE

- Assign P0/P1/P2 priorities
- Identify quick wins vs deep refactors
- Group related issues under epics (if using bd)

---

## Security Issues

**Impact: CRITICAL**

### Authentication & Authorization

**Auth errors to find:**

- Missing authentication on sensitive endpoints
- Broken session management
- Insecure password storage (plaintext, weak hashing)
- Missing or bypassable authorization checks
- Privilege escalation paths
- Insecure direct object references (IDOR)

**Example:**

```typescript
// BAD: No auth check before accessing user data
app.get('/api/users/:id', (req, res) => {
  return db.users.findById(req.params.id) // Anyone can access any user
})
```

### Injection Risks

**Types to identify:**

- SQL injection
- Command injection
- XSS (Cross-Site Scripting)
- LDAP injection
- XML injection
- Template injection

**Example:**

```typescript
// BAD: SQL injection vulnerability
const query = `SELECT * FROM users WHERE id = ${req.params.id}`
db.query(query)

// BAD: Command injection
exec(`ls ${userInput}`)

// BAD: XSS vulnerability
element.innerHTML = userProvidedContent
```

### Server-Side Request Forgery (SSRF)

**Indicators:**

- User-controlled URLs passed to fetch/request functions
- Missing URL validation or allowlisting
- Internal service URLs accessible via user input

**Example:**

```typescript
// BAD: SSRF vulnerability
const url = req.body.imageUrl
const response = await fetch(url) // Can access internal services
```

### Path Traversal

**Indicators:**

- User input used in file paths
- Missing path sanitization
- Relative path components (`..`) not blocked

**Example:**

```typescript
// BAD: Path traversal
const filePath = `./uploads/${req.params.filename}`
fs.readFile(filePath) // Can read ../../etc/passwd
```

### Secrets & Insecure Defaults

**Check for:**

- Hardcoded credentials, API keys, tokens
- Default passwords in config
- Secrets in source control
- Insecure default configurations
- Debug mode enabled in production

**Example:**

```typescript
// BAD: Hardcoded secret
const API_KEY = 'sk-1234567890abcdef'

// BAD: Insecure default
const config = {
  debug: true, // Should be false in production
  validateSSL: false, // Disables certificate validation
}
```

### Cryptographic Issues

**Check for:**

- Weak algorithms (MD5, SHA1 for security, DES, RC4)
- Hardcoded IVs or salts
- Missing encryption for sensitive data
- Insecure random number generation
- Improper key management

**Example:**

```typescript
// BAD: Weak hashing
const hash = crypto.createHash('md5').update(password).digest('hex')

// BAD: Insecure random
const token = Math.random().toString(36) // Not cryptographically secure
```

### Input Validation

**Check for:**

- Missing validation on user inputs
- Type coercion vulnerabilities
- Length/size limits not enforced
- Format validation missing
- Prototype pollution risks

**Example:**

```typescript
// BAD: No input validation
app.post('/api/update', (req, res) => {
  Object.assign(user, req.body) // Prototype pollution risk
})
```

### Dependency Vulnerabilities

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

### Security Severity Classification

| Severity | Criteria                                   | Examples                        |
| -------- | ------------------------------------------ | ------------------------------- |
| P0       | Exploitable, high impact, no auth required | RCE, SQL injection, auth bypass |
| P1       | Exploitable with some prerequisites        | SSRF, stored XSS, IDOR          |
| P2       | Limited impact or difficult to exploit     | Reflected XSS, info disclosure  |

---

## Bugs

**Impact: HIGH**

### Edge Cases & Boundary Conditions

**Check for:**

- Empty arrays/objects not handled
- Null/undefined values
- Zero and negative numbers
- Maximum value boundaries
- Unicode and special characters
- Timezone edge cases

**Example:**

```typescript
// BAD: Doesn't handle empty array
function getFirst(items) {
  return items[0].name // Crashes if items is empty
}

// BAD: Division by zero
function average(numbers) {
  return numbers.reduce((a, b) => a + b) / numbers.length
}
```

### Concurrency & Race Conditions

**Check for:**

- Shared mutable state without synchronization
- Check-then-act patterns
- Time-of-check to time-of-use (TOCTOU)
- Missing locks on critical sections
- Deadlock potential

**Example:**

```typescript
// BAD: Race condition
let counter = 0
async function increment() {
  const current = counter // Read
  await someAsyncWork()
  counter = current + 1 // Write - may lose updates
}

// BAD: Check-then-act
if (!fs.existsSync(file)) {
  fs.writeFileSync(file, data) // File may be created between check and write
}
```

### Error Handling Gaps

**Check for:**

- Uncaught exceptions
- Empty catch blocks
- Errors swallowed without logging
- Missing error boundaries (React)
- Unhandled promise rejections

**Example:**

```typescript
// BAD: Swallowed error
try {
  await riskyOperation()
} catch (e) {
  // Silent failure - bug goes unnoticed
}

// BAD: Unhandled rejection
fetchData().then((data) => process(data))
// Missing .catch() - rejection crashes app
```

### Resource Leaks

**Check for:**

- Unclosed file handles
- Database connections not released
- Event listeners not removed
- Timers/intervals not cleared
- Memory leaks from closures

**Example:**

```typescript
// BAD: Connection leak
async function query(sql) {
  const conn = await pool.getConnection()
  return conn.query(sql) // Connection never released
}

// BAD: Event listener leak
useEffect(() => {
  window.addEventListener('resize', handler)
  // Missing cleanup - listener accumulates on re-renders
}, [])
```

### Numeric Issues

**Check for:**

- Integer overflow/underflow
- Floating point precision errors
- Currency calculations with floats
- Large number handling (BigInt needed)

**Example:**

```typescript
// BAD: Floating point for currency
const total = 0.1 + 0.2 // 0.30000000000000004

// BAD: Large number overflow
const bigNum = 9999999999999999 // Loses precision in JS
```

### Retry & Timeout Bugs

**Check for:**

- Missing timeouts on network calls
- Infinite retry loops
- Exponential backoff missing
- Timeout values too short/long
- Circuit breaker patterns missing

**Example:**

```typescript
// BAD: No timeout
const response = await fetch(url) // Can hang forever

// BAD: Infinite retry
async function fetchWithRetry(url) {
  while (true) {
    try {
      return await fetch(url)
    } catch {
      // Retries forever on persistent failure
    }
  }
}
```

### Bug Severity Classification

| Severity | Criteria                         | Examples                         |
| -------- | -------------------------------- | -------------------------------- |
| P0       | Data loss, corruption, or crash  | Race condition causing data loss |
| P1       | Incorrect behavior, recoverable  | Edge case returns wrong result   |
| P2       | Minor issue, workaround exists   | UI glitch, non-critical timeout  |

---

## Code Health

**Impact: MEDIUM**

### Complexity Issues

**Check for:**

- Files over 500 lines
- Functions over 50 lines
- Cyclomatic complexity > 10
- Deep nesting (> 3 levels)
- Too many parameters (> 5)

**Example:**

```typescript
// BAD: Deeply nested
if (a) {
  if (b) {
    if (c) {
      if (d) {
        // 4 levels deep - hard to follow
      }
    }
  }
}

// BAD: Too many parameters
function createUser(name, email, age, role, dept, manager, startDate, salary) {
  // 8 params - use an options object
}
```

### Test Coverage Gaps

**Check for:**

- Critical paths without tests
- Business logic untested
- Error paths untested
- Integration points untested
- Edge cases not covered

**How to identify:**

```bash
# Check coverage reports for uncovered lines in critical files
coverage report --show-missing
```

### Duplication & Redundancy

**Check for:**

- Copy-pasted code blocks
- Similar functions with slight variations
- Redundant abstractions
- Multiple implementations of same logic

**Example:**

```typescript
// BAD: Duplicated validation logic
// Found in: user-service.ts, admin-service.ts, api-handler.ts
function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}
// Should be extracted to shared utility
```

### Dead Code

**Check for:**

- Unused functions/methods
- Unused exports
- Unreachable code paths
- Commented-out code
- Unused dependencies

**How to identify:**

```bash
# Find unused exports
ts-prune

# Find unused dependencies
depcheck
```

### Documentation Issues

**Check for:**

- Missing README or outdated
- No JSDoc/TSDoc on public APIs
- Outdated comments that mislead
- Missing architecture docs
- Undocumented environment requirements

### Code Health Severity Classification

| Severity | Criteria                             | Examples                    |
| -------- | ------------------------------------ | --------------------------- |
| P0       | Blocks development or causes failures | Circular deps, broken build |
| P1       | Significant maintainability impact   | No tests on critical code   |
| P2       | Minor issues, incremental improvement | Naming inconsistencies      |

---

## Work Item Formats

### Markdown Task List Format

When bd is not available:

```markdown
## Audit Findings: [target-directory]

### P0 - Critical
- [ ] [Security] `file.ts:line`: Brief description
- [ ] [Security] `file.ts:line`: Brief description

### P1 - High
- [ ] [Bug] `file.ts:line`: Brief description
- [ ] [Security] `file.ts:line`: Brief description

### P2 - Medium
- [ ] [Health] `file.ts:line`: Brief description
```

### Beads Epic Format

```yaml
Epic: Harden Input Validation in /api/users
Success Criteria:
  - All user-facing endpoints validate input schemas
  - No SQL injection vectors remain
  - Input length limits enforced
Child Issues:
  - #123 Add schema validation to POST /users
  - #124 Sanitize query parameters in GET /users
  - #125 Add rate limiting to /users endpoints
Risk Notes: Validation changes may reject previously-accepted input
```

### Beads Issue Format

```yaml
Issue: Fix SQL injection in user search endpoint
Priority: P0
Context: |
  User-controlled input passed directly to SQL query.
  Allows arbitrary database access.
Evidence:
  File: src/api/users/search.ts:42
  Code: |
    const query = `SELECT * FROM users WHERE name LIKE '%${term}%'`
  Repro: |
    GET /api/users/search?q='; DROP TABLE users;--
Scope:
  Change:
    - Parameterize the SQL query
    - Add input validation
  Preserve:
    - Search functionality
    - Response format
Acceptance Criteria:
  - Query uses parameterized statements
  - Special characters are escaped
  - Existing search tests pass
```

---

## Output Format

Each cycle produces:

```markdown
## Cycle N Summary

### Findings Table
| Severity | Type | File(s) | Description | Confidence | Status |

### Work Items Created
- [P0] ...
- [P1] ...

### Triage Notes
...

### Backlog Overview
Open items grouped by priority
```

---

## Examples

### Quick Audit (2 Cycles)

**Target**: `src/api/users/`

**Cycle 1 Findings:**

| Severity | Type     | File(s)            | Description                       | Confidence |
| -------- | -------- | ------------------ | --------------------------------- | ---------- |
| P0       | Security | `search.ts:42`     | SQL injection in search query     | High       |
| P1       | Bug      | `pagination.ts:28` | Division by zero on empty results | High       |

**Cycle 2 Findings:**

| Severity | Type   | File(s)         | Description            | Confidence |
| -------- | ------ | --------------- | ---------------------- | ---------- |
| P2       | Health | `handler.ts:15` | Missing error handling | Medium     |

**Final Backlog:**

```markdown
### P0 - Critical
- [ ] [Security] `search.ts:42`: SQL injection - parameterize query

### P1 - High
- [ ] [Bug] `pagination.ts:28`: Handle empty result set

### P2 - Medium
- [ ] [Health] `handler.ts:15`: Add try-catch for async operations
```

---

## Constraints

- **DO NOT** implement code changes
- **STAY WITHIN** target directory unless minimal external context needed
- **PREFER** many small issues over large vague ones
- **VERIFY** findings before filing to avoid false positives
