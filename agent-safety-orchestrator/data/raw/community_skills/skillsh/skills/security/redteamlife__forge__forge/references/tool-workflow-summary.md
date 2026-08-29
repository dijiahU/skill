# Tool Workflow Summary

FORGE tool projects separate:

- private development and governance
- public release artifacts or source

## Open Source

- `preserve-history` is preferred when public PRs are accepted.
- `snapshot-force-push` fits release-mirror repos with maintainer-only contribution.

## Closed Source

- publish binaries as release assets
- do not push private source into the public repo

## Public PR Intake

Merged public changes should be imported into the private dev flow before the next governed publish so validation and memory stay authoritative in one place.
