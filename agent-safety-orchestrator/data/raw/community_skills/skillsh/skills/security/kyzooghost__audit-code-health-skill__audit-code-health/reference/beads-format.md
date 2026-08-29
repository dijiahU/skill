---
title: Beads Format Guide
impact: HIGH
tags: beads, work-items, epics, issues
---

# Beads Format Guide

How to structure Beads epics and issues for audit findings.

## Contents

- [Beads Epics](#beads-epics)
- [Beads Issues](#beads-issues)
- [Issue Examples](#issue-examples)
- [Priority Guidelines](#priority-guidelines)
- [Uncertain Findings](#uncertain-findings)

## Beads Epics

Epics are lightweight containers that group related issues.

### Required Fields

```yaml
Epic:
  Title: [Theme] - Clear problem area
  Success Criteria: How we know the epic is complete
  Child Issues: Links to related issues
```

### Optional Fields (use sparingly)

```yaml
  Risk Notes: Only if rollout is non-trivial
  Dependencies: Other epics that must complete first
```

### Example Epic

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

## Beads Issues

Issues should be small enough to complete in one session.

### Required Fields

```yaml
Issue:
  Title: Concise, action-oriented title
  Context: Why this matters (security/correctness/health)
  Evidence:
    - File paths
    - Function names
    - Code snippets (minimal)
    - Repro steps (if applicable)
  Scope:
    Change: What to modify
    Preserve: What NOT to touch
  Acceptance Criteria:
    - Concrete, testable outcomes
  Priority: P0 | P1 | P2
```

### Optional Fields (use sparingly)

```yaml
  Dependencies: Blocking or prerequisite issues
  Risk Notes: Only for dangerous/irreversible changes
  Validation Hints: Only if verification is non-obvious
```

### Do NOT Require

- Effort sizing
- Confidence ratings
- Long proposed approaches
- Full test plans

Let executors derive these at execution time.

## Issue Examples

### Security Issue (P0)

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

### Bug Issue (P1)

```yaml
Issue: Handle empty results in pagination
Priority: P1
Context: |
  Pagination crashes when result set is empty.
  Users see error page instead of "no results" message.
Evidence:
  File: src/components/ResultsList.tsx:28
  Code: |
    const lastPage = Math.ceil(total / pageSize) // NaN when total=0
  Repro: |
    1. Search for term with no results
    2. Observe TypeError in console
Scope:
  Change:
    - Add zero-result check before pagination calc
    - Show empty state component
  Preserve:
    - Pagination logic for non-empty results
Acceptance Criteria:
  - Empty search returns empty state UI
  - No console errors
  - Pagination hidden when 0 results
```

### Code Health Issue (P2)

```yaml
Issue: Extract duplicated email validation
Priority: P2
Context: |
  Same email regex appears in 4 files.
  Changes require updating multiple locations.
Evidence:
  Files:
    - src/services/user-service.ts:15
    - src/services/admin-service.ts:22
    - src/api/handlers/signup.ts:8
    - src/api/handlers/invite.ts:12
  Pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/
Scope:
  Change:
    - Create shared validation utility
    - Replace all instances with shared function
  Preserve:
    - Validation behavior (same regex)
Acceptance Criteria:
  - Single source of truth for email validation
  - All existing tests pass
  - No duplicate regex in codebase
```

## Priority Guidelines

| Priority | Criteria                                    | Response Time |
| -------- | ------------------------------------------- | ------------- |
| P0       | Security exploit, data loss, system down    | Immediate     |
| P1       | Significant bug, major functionality broken | This sprint   |
| P2       | Minor issue, tech debt, improvements        | Backlog       |

## Uncertain Findings

Still file them, but:
- Use lower priority (P2)
- Add explicit "how to validate" notes
- Mark confidence in the title or context

```yaml
Issue: [Investigate] Possible race condition in cache update
Priority: P2
Context: |
  Potential race condition when multiple requests update cache.
  Confidence: MEDIUM - needs load testing to confirm.
Validation Hints: |
  - Run concurrent requests to POST /cache
  - Check for stale reads under load
  - Monitor for cache inconsistencies
```
