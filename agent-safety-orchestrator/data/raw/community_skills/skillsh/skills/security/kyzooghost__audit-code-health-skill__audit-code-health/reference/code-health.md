---
title: Code Health Checklist
impact: MEDIUM
tags: maintainability, technical-debt, code-quality
---

# Code Health Checklist

Code health issues to identify during audits that impact maintainability.

## Contents

- [Complexity Issues](#complexity-issues)
- [Test Coverage Gaps](#test-coverage-gaps)
- [Duplication & Redundancy](#duplication--redundancy)
- [Dead Code](#dead-code)
- [Documentation Issues](#documentation-issues)
- [File Organization](#file-organization)
- [Naming Issues](#naming-issues)
- [Build Artifacts](#build-artifacts)
- [Dependency Issues](#dependency-issues)
- [Severity Classification](#severity-classification)

## Complexity Issues

**Check for:**

- Files over 500 lines
- Functions over 50 lines
- Cyclomatic complexity > 10
- Deep nesting (> 3 levels)
- Too many parameters (> 5)

**Example finding:**

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

## Test Coverage Gaps

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

**Example finding:**

```typescript
// auth/login.ts has 0% test coverage but handles:
// - Password validation
// - Token generation
// - Session management
// This is CRITICAL untested code
```

## Duplication & Redundancy

**Check for:**

- Copy-pasted code blocks
- Similar functions with slight variations
- Redundant abstractions
- Multiple implementations of same logic

**Example finding:**

```typescript
// BAD: Duplicated validation logic
// Found in: user-service.ts, admin-service.ts, api-handler.ts
function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}
// Should be extracted to shared utility
```

## Dead Code

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

**Example finding:**

```typescript
// BAD: Dead code
export function legacyHandler() {
  // No imports found in codebase
}

// BAD: Unreachable
function process(x) {
  return x * 2
  console.log('Done') // Never executed
}
```

## Documentation Issues

**Check for:**

- Missing README or outdated
- No JSDoc/TSDoc on public APIs
- Outdated comments that mislead
- Missing architecture docs
- Undocumented environment requirements

**Example finding:**

```typescript
// BAD: Misleading comment
// Returns user's full name
function getName(user) {
  return user.email // Actually returns email!
}
```

## File Organization

**Check for:**

- Mis-layered files (UI in data layer)
- Inconsistent folder structure
- Related code spread across distant locations
- Circular dependencies

**Example finding:**

```
// BAD: Database logic in UI component
components/
  UserProfile/
    UserProfile.tsx
    database.ts  // Should be in data layer
```

## Naming Issues

**Check for:**

- Misleading names
- Inconsistent naming conventions
- Abbreviations that aren't obvious
- Names that don't match behavior

**Example finding:**

```typescript
// BAD: Misleading name
function getUsers() {
  // Actually deletes users!
  return db.users.deleteMany({})
}

// BAD: Inconsistent naming
const userData = fetch('/users')
const customerInfo = fetch('/customers') // userData vs Info
const productList = fetch('/products') // Data vs Info vs List
```

## Build Artifacts

**Check for:**

- Committed node_modules or vendor folders
- Build output in source control
- Generated files checked in
- Large binary files

**Example finding:**

```
# Files that shouldn't be in git:
dist/
node_modules/
*.min.js
*.bundle.js
coverage/
```

## Dependency Issues

**Check for:**

- Unpinned versions (`^` or `*`)
- Ancient dependencies (2+ major versions behind)
- Abandoned packages (no updates in 2+ years)
- Duplicate dependencies at different versions

**Example finding:**

```json
// BAD: Risky version pinning
{
  "dependencies": {
    "lodash": "*",        // Any version - dangerous
    "react": "^16.0.0",   // Allows 16.x - may break
    "moment": "2.29.1"    // Abandoned package
  }
}
```

## Severity Classification

| Severity | Criteria                               | Examples                           |
| -------- | -------------------------------------- | ---------------------------------- |
| P0       | Blocks development or causes failures  | Circular deps, broken build        |
| P1       | Significant maintainability impact     | No tests on critical code          |
| P2       | Minor issues, incremental improvement  | Naming inconsistencies             |
