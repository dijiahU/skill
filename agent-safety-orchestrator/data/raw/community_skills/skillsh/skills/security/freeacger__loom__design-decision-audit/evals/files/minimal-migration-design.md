# Minimal Migration Design

## Background

We want to move user locale reads from field `lang` to field `language_code`.
New writes will use `language_code`.

## Proposed Change

- Add `language_code` to the user profile payload.
- New app versions read `language_code`.
- Old app versions continue to read `lang` for now.

## Notes

- Existing records may not have `language_code`.
- We have not decided whether to backfill old data.
- We have not written a rollback plan yet.
- Logging and metrics will be added later if needed.
