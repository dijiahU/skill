# State Machine Review Design

## Background

We are unifying a completion review flow used by multiple entry paths.
The system currently has separate review and completion handlers.

## Proposed Change

- Introduce a new intermediate status `pending_finalize`.
- A shared worker will pick records in `pending_finalize` and finish downstream work.
- Manual review can still approve or reject records.
- Retry logic will be reused from the old worker.

## Known Gaps

- The document does not define which component advances `pending_finalize`.
- The document does not define how stale retries are prevented.
- The document does not define what happens when manual review and worker retry overlap.
- The document does not define whether failure in one subflow blocks unrelated work.
