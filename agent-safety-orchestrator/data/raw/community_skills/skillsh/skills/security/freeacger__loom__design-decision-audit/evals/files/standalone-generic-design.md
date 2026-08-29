# Standalone Generic Design

## Background

A service wants to rename `preferred_timezone` to `user_timezone` in its public API.

## Proposed Change

- New clients will read `user_timezone`.
- Existing clients may still read `preferred_timezone` for one release.
- No background jobs or workflow state changes are involved.

## Known Gaps

- No rollback plan is defined.
- Existing data handling is not described.
- Logging and metrics are deferred.
