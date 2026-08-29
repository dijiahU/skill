# Architecture Decision Records

Each significant architectural decision lives here as its own numbered file.

## Format

`NNNN-short-slug.md` where NNNN is a zero-padded sequence starting at 0001.

## Template

Copy `0001-record-architecture-decisions.md` and fill in:

- Status: Proposed | Accepted | Superseded by NNNN | Deprecated
- Context: what problem or constraint drove the decision
- Decision: what was decided
- Options Considered: at least the chosen option and one rejected
- Consequences: positive outcomes, tradeoffs, operational impacts
- Follow-Up: any tasks created by the decision

## When To Add One

Add a new ADR when a task represents a significant architectural decision
that future contributors or agents will need to understand to work
correctly. Examples:

- choosing a framework, runtime, or hosting model
- selecting a data store, schema strategy, or migration approach
- introducing a trust boundary or auth model
- deprecating or replacing a major component

Routine refactors, bug fixes, and small features do not need ADRs.
