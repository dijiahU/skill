# Conflict Checklist Design

## Background

A user profile service is migrating reads from `preferred_language` to `language_code`.

## Proposed Change

- New writes go to `language_code`.
- Older mobile clients may still read `preferred_language` during one transition window.
- No schema migration is planned in this iteration.

## Notes

- The team explicitly wants a design-decision audit, not a release checklist review.
- There is no rollout verification signal yet.
- Empty or invalid language values are not handled.
- Observability for fallback reads is not defined.
