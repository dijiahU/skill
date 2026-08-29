# Standalone Checklist Design

## Background

A profile service will start reading `display_locale` instead of `locale`.

## Proposed Change

- Keep writes on `display_locale`.
- Continue to read `locale` for older clients temporarily.
- No database schema change is planned in this iteration.

## Open Gaps

- There is no rollout verification plan.
- There is no explicit fallback for empty values.
- There is no observability plan for fallback reads.
