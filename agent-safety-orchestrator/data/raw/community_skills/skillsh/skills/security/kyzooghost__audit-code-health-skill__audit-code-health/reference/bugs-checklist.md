---
title: Bugs Checklist
impact: HIGH
tags: bugs, edge-cases, reliability
---

# Bugs Checklist

Common bug patterns to identify during code audits.

## Contents

- [Edge Cases & Boundary Conditions](#edge-cases--boundary-conditions)
- [Concurrency & Race Conditions](#concurrency--race-conditions)
- [Error Handling Gaps](#error-handling-gaps)
- [Resource Leaks](#resource-leaks)
- [Incorrect Assumptions](#incorrect-assumptions)
- [Undefined Behavior](#undefined-behavior)
- [Numeric Issues](#numeric-issues)
- [Retry & Timeout Bugs](#retry--timeout-bugs)
- [Severity Classification](#severity-classification)

## Edge Cases & Boundary Conditions

**Check for:**

- Empty arrays/objects not handled
- Null/undefined values
- Zero and negative numbers
- Maximum value boundaries
- Unicode and special characters
- Timezone edge cases

**Example finding:**

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

## Concurrency & Race Conditions

**Check for:**

- Shared mutable state without synchronization
- Check-then-act patterns
- Time-of-check to time-of-use (TOCTOU)
- Missing locks on critical sections
- Deadlock potential

**Example finding:**

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

## Error Handling Gaps

**Check for:**

- Uncaught exceptions
- Empty catch blocks
- Errors swallowed without logging
- Missing error boundaries (React)
- Unhandled promise rejections

**Example finding:**

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

## Resource Leaks

**Check for:**

- Unclosed file handles
- Database connections not released
- Event listeners not removed
- Timers/intervals not cleared
- Memory leaks from closures

**Example finding:**

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

## Incorrect Assumptions

**Check for:**

- Assuming API response shape
- Assuming environment variables exist
- Assuming file/network always available
- Assuming data is sorted/ordered
- Assuming unique values

**Example finding:**

```typescript
// BAD: Assumes response shape
const userName = response.data.user.profile.name
// Crashes if any intermediate property is undefined

// BAD: Assumes env var exists
const port = process.env.PORT.split(':')[1]
// Crashes if PORT is undefined
```

## Undefined Behavior

**Check for:**

- Accessing arrays out of bounds
- Modifying objects during iteration
- Relying on implementation details
- Platform-specific assumptions

**Example finding:**

```typescript
// BAD: Modifying during iteration
for (const item of items) {
  if (shouldRemove(item)) {
    items.splice(items.indexOf(item), 1) // Undefined behavior
  }
}
```

## Numeric Issues

**Check for:**

- Integer overflow/underflow
- Floating point precision errors
- Currency calculations with floats
- Large number handling (BigInt needed)

**Example finding:**

```typescript
// BAD: Floating point for currency
const total = 0.1 + 0.2 // 0.30000000000000004

// BAD: Large number overflow
const bigNum = 9999999999999999 // Loses precision in JS
```

## Retry & Timeout Bugs

**Check for:**

- Missing timeouts on network calls
- Infinite retry loops
- Exponential backoff missing
- Timeout values too short/long
- Circuit breaker patterns missing

**Example finding:**

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

## Severity Classification

| Severity | Criteria                               | Examples                               |
| -------- | -------------------------------------- | -------------------------------------- |
| P0       | Data loss, corruption, or crash        | Race condition causing data loss       |
| P1       | Incorrect behavior, recoverable        | Edge case returns wrong result         |
| P2       | Minor issue, workaround exists         | UI glitch, non-critical timeout        |
