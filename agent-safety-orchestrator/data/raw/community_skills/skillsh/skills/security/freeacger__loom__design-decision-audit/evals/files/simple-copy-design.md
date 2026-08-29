# Simple Copy Design

## Background

We want to rename the wallet page label from `Balance` to `Available Balance`.

## Proposed Change

- Update the mobile client copy.
- Update one API response display field from `balance_label` to `available_balance_label`.
- Keep the underlying numeric balance field unchanged.

## Constraints

- No database schema change.
- No async worker, retry logic, or scheduled task.
- No manual review flow.
- No concurrency-sensitive write path.
- Existing clients may still read the old display label for one release.
