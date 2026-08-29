---
title: Audit Examples
impact: HIGH
tags: examples, workflow, findings
---

# Audit Examples

Complete examples showing audit workflows and properly formatted findings.

## Contents

- [Quick Audit Example (2 Cycles)](#quick-audit-example-2-cycles)
- [Standard Audit Example (5 Cycles)](#standard-audit-example-5-cycles)
- [Findings Format Reference](#findings-format-reference)

## Quick Audit Example (2 Cycles)

**Target**: `src/api/users/` (small PR review)

### Cycle 1 Summary

#### Findings Table

| Severity | Type     | File(s)              | Description                    | Confidence |
| -------- | -------- | -------------------- | ------------------------------ | ---------- |
| P0       | Security | `search.ts:42`       | SQL injection in search query  | High       |
| P1       | Bug      | `pagination.ts:28`   | Division by zero on empty results | High    |

#### Work Items Created

- [ ] [P0/Security] `search.ts:42`: SQL injection - user input passed directly to query
- [ ] [P1/Bug] `pagination.ts:28`: Handle empty result set before pagination calc

#### Triage Notes

P0 security issue should be addressed immediately. P1 bug causes user-visible errors.

### Cycle 2 Summary

#### Findings Table

| Severity | Type        | File(s)           | Description                  | Confidence |
| -------- | ----------- | ----------------- | ---------------------------- | ---------- |
| P2       | Code Health | `handler.ts:15`   | Missing error handling       | Medium     |

#### Work Items Created

- [ ] [P2/Health] `handler.ts:15`: Add try-catch for async operations

#### Backlog Overview

**P0 (Immediate)**
- SQL injection in search.ts

**P1 (This Sprint)**
- Empty result pagination bug

**P2 (Backlog)**
- Error handling improvement

---

## Standard Audit Example (5 Cycles)

**Target**: `packages/auth-service/` (feature module audit)

### Cycle 1 Summary

Focus: Authentication flow

#### Findings Table

| Severity | Type     | File(s)           | Description                      | Confidence |
| -------- | -------- | ----------------- | -------------------------------- | ---------- |
| P0       | Security | `jwt.ts:67`       | Token signature not verified     | High       |
| P0       | Security | `session.ts:23`   | Session fixation vulnerability   | High       |
| P1       | Bug      | `login.ts:45`     | Race condition on concurrent login | Medium   |

### Cycle 2 Summary

Focus: Authorization checks

#### Findings Table

| Severity | Type     | File(s)           | Description                      | Confidence |
| -------- | -------- | ----------------- | -------------------------------- | ---------- |
| P0       | Security | `middleware.ts:12`| Missing auth check on admin route | High      |
| P1       | Security | `roles.ts:34`     | IDOR - user can access other profiles | High  |

### Cycle 3 Summary

Focus: Input validation

#### Findings Table

| Severity | Type     | File(s)            | Description                    | Confidence |
| -------- | -------- | ------------------ | ------------------------------ | ---------- |
| P1       | Security | `register.ts:28`   | No email format validation     | High       |
| P1       | Bug      | `password.ts:15`   | Password strength not enforced | High       |
| P2       | Health   | `validator.ts:*`   | Duplicated validation logic    | Medium     |

### Cycle 4 Summary

Focus: Error handling and edge cases

#### Findings Table

| Severity | Type   | File(s)           | Description                      | Confidence |
| -------- | ------ | ----------------- | -------------------------------- | ---------- |
| P1       | Bug    | `oauth.ts:89`     | Unhandled rejection on timeout   | High       |
| P1       | Bug    | `refresh.ts:34`   | Token refresh race condition     | Medium     |
| P2       | Health | `error.ts:*`      | Empty catch blocks swallow errors | High      |

### Cycle 5 Summary

Focus: Code health and maintainability

#### Findings Table

| Severity | Type   | File(s)           | Description                    | Confidence |
| -------- | ------ | ----------------- | ------------------------------ | ---------- |
| P2       | Health | `auth.ts`         | File exceeds 500 lines         | High       |
| P2       | Health | `utils.ts:45-89`  | Dead code - unused functions   | High       |
| P2       | Health | `types.ts`        | Missing JSDoc on public APIs   | Medium     |

### Final Backlog Overview

**P0 - Critical (3 issues)**
- [ ] JWT signature verification missing
- [ ] Session fixation vulnerability
- [ ] Missing auth on admin routes

**P1 - High (6 issues)**
- [ ] Race condition on concurrent login
- [ ] IDOR vulnerability in profiles
- [ ] Email validation missing
- [ ] Password strength not enforced
- [ ] OAuth timeout not handled
- [ ] Token refresh race condition

**P2 - Medium (4 issues)**
- [ ] Duplicated validation logic
- [ ] Empty catch blocks
- [ ] auth.ts file too large
- [ ] Dead code in utils.ts

---

## Findings Format Reference

### Markdown Task List Format

When bd is not available, use this format:

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

### Beads Issue Format

When using bd, structure issues like this:

```yaml
Issue: Fix SQL injection in user search
Priority: P0
Context: |
  User-controlled input passed directly to SQL query.
  Allows arbitrary database access.
Evidence:
  File: src/api/users/search.ts:42
  Code: |
    const query = `SELECT * FROM users WHERE name LIKE '%${term}%'`
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

See [beads-format.md](beads-format.md) for the complete format guide.
