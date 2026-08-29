# Index Tuning Design

## Background

The admin gift-card list is slow when filtering by `status` and sorting by `created_at`.

## Proposed Change

- Keep API behavior unchanged.
- Add an index to support the common filter and sort path.
- Review whether the old single-column index on `status` is still needed.

## Constraints

- No new workflow state.
- No new background worker.
- No human approval step.
- No lock or retry coordination.
- Main risk is query performance and migration safety for the new index.
