---
name: audit-errors
description: Audit code for error-handling inconsistencies, anti-patterns, and silent failures such as empty catch blocks, ignored promise rejections, log-and-continue paths, fallback values that hide faults, broad catch clauses, and inconsistent error translation across layers. Use when reviewing controllers, services, jobs, API handlers, async workflows, UI actions, or any change where errors may be swallowed, downgraded, or surfaced unreliably.
---

# Audit Errors

Audit failure paths before changing behavior. Find where errors disappear, lose context, or surface inconsistently, then apply the smallest safe fix.

## Follow this workflow

1. Map the failure boundaries in scope.
2. Search for handlers, retries, fallbacks, and async branches.
3. Classify each error path as recover, translate, retry, report, cleanup, or swallow.
4. Flag silent failures, inconsistent handling, and misleading success states.
5. Prioritize findings as `P1` through `P4`.
6. Auto-fix only local, low-risk issues.

## Map the failure boundaries

Inspect the full path, not just the visible bug site.

- request parsing and validation
- controllers, routes, and UI actions
- domain services and business logic
- network and third-party integrations
- persistence, cache, and filesystem paths
- background jobs, workers, and schedulers
- retries, timeouts, and cancellation paths
- logging, telemetry, and user-facing error states

## Search for risky patterns

Start with the language-appropriate equivalents of:

- `try`
- `catch`
- `.catch(`
- `finally`
- `throw`
- `throws`
- `rescue`
- `except`
- `return null`
- `return false`
- `return []`
- `console.error`
- `logger.error`
- `report(`
- ignored promise or task creation

Also inspect code paths that convert errors into:

- empty states
- default values
- partial success responses
- retries with no terminal failure
- generic "something went wrong" wrappers

## Detect these error-handling anti-patterns

### Swallowed errors

Flag handlers that consume an error without preserving signal.

Common signals:

- empty `catch` or `rescue` blocks
- comment-only handlers like `// ignore`
- logging without rethrowing, returning an error result, or marking failure
- callback error parameters accepted but never checked
- background task failures dropped on the floor

### Misleading fallbacks

Flag exceptional paths that pretend success.

Common signals:

- returning `null`, `[]`, `{}`, or `false` after a real failure with no caller distinction
- showing an empty state when data loading actually failed
- suppressing write failures and continuing as if persistence succeeded
- using stale cache data without marking it degraded

### Inconsistent translation

Flag the same failure class being mapped differently across boundaries.

Common signals:

- one API path returns `404` while another returns `500` for the same missing record condition
- one service wraps an integration timeout as retryable while another treats it as success
- UI paths show contradictory messages for the same backend error

Prefer translation at clear boundaries, not ad hoc at every call site.

### Overbroad catches

Flag handlers that catch too much and hide programmer or invariant bugs.

Common signals:

- `catch (Exception)` or `catch (Throwable)` used deep inside core logic
- generic `catch (error)` blocks that handle all failures the same way
- rescue paths that convert unexpected faults into normal control flow

Catch expected, recoverable errors narrowly. Let unexpected faults fail loudly at the right boundary.

### Lost context

Flag paths that surface an error but strip away the information needed to debug it.

Common signals:

- throwing a new error without preserving the original cause
- logs with no request id, record id, operation name, or upstream context
- replacing specific error codes with vague generic messages too early
- finally blocks or cleanup code overwriting the original failure

### Async blind spots

Flag async work whose failures are not awaited, returned, observed, or reported.

Common signals:

- floating promises
- fire-and-forget tasks without error hooks
- retries that log intermediate failures but never surface the terminal one
- timeout or cancellation branches that abandon in-flight errors silently

## Classify findings

### `P1`

Use for silent failures that can cause data loss, corruption, security issues, billing mistakes, stuck jobs, false success states, or user-visible contradictions in normal use.

### `P2`

Use for error paths that regularly lose signal or apply inconsistent translation, especially in shared services, integrations, and async workflows.

### `P3`

Use for observability gaps, overbroad catches, weak wrapping, and fallback behavior that raises regression risk but does not clearly break the happy path yet.

### `P4`

Use for cleanup work such as redundant logging, minor wrapping inconsistencies, and dead handlers with low immediate risk.

## Auto-fix only when safe

Auto-fix local issues when the intent is unambiguous.

Safe examples:

- remove empty handlers by rethrowing or returning an explicit error result already used nearby
- preserve the original `cause` when wrapping errors
- return or await an existing promise chain so failure is observable
- add a local log or report call when the code already has a clear error contract
- replace ambiguous fallback values with an explicit failure path inside one module

Do not auto-fix without explicit approval when the change affects:

- public API contracts
- retry policy or backoff semantics
- monitoring or alerting expectations
- shared error taxonomies
- database transaction behavior
- cross-service message formats
- user-facing copy or product semantics around degraded mode

For those, report the issue and propose the smallest migration path.

## Choose the smallest defensible fix

Prefer this order:

1. Preserve the failure signal.
2. Handle only expected, recoverable errors.
3. Translate errors at the boundary that owns the contract.
4. Keep the original cause and enough context to debug.
5. Fail explicitly rather than pretending success.

Avoid broad rewrites unless the current design makes localized fixes unsafe.

## Report findings in this format

List findings first, highest severity first.

For each finding, include:

- priority: `P1` to `P4`
- pattern: swallowed error, misleading fallback, inconsistent translation, overbroad catch, lost context, or async blind spot
- location: file and line or the smallest concrete scope available
- what fails silently or inconsistently
- trigger path: how normal execution reaches it
- recommended fix
- whether it is safe to auto-fix now

If no issues are found, say so explicitly and mention which boundaries were inspected plus any residual blind spots.

## Default review stance

- Prefer explicit failure over fake success.
- Prefer narrow recovery over broad suppression.
- Prefer one translation boundary per contract.
- Prefer preserving original cause and context.
- Prefer concrete failure paths over abstract style feedback.
