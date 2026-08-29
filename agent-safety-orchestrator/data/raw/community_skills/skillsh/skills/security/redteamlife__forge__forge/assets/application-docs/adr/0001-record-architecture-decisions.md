---
title: ADR-0001 Record Architecture Decisions
owners:
status: accepted
updated:
---

## Status

Accepted

## Context

We need a durable, lightweight record of architectural decisions so that
future contributors and agents can understand why the system is shaped the
way it is.

## Decision

We adopt Architecture Decision Records (ADRs). Each ADR is a numbered
markdown file under `docs/adr/`. Use `0001-record-architecture-decisions.md`
as the template.

## Options Considered

- Inline comments only
- Wiki pages
- Versioned ADRs in the repo (chosen)

## Consequences

- Architectural intent is durable and reviewable.
- Each decision is small and focused.
- ADR maintenance must be kept lean to remain useful.

## Follow-Up

- New significant architectural decisions get a new numbered ADR.
- Superseding decisions update the prior ADR's status to `superseded by NNNN`.
