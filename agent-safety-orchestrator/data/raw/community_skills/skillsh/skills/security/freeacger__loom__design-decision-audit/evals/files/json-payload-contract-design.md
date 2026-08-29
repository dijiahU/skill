# JSON Payload Contract Design

## Background

Several services share an `extra_payload` JSON blob that includes keys like `status`, `source`, and `notes`.

## Proposed Change

- Define one canonical schema for `extra_payload`.
- Keep unknown keys during read-modify-write merges unless they are explicitly rejected by schema version rules.
- Clarify which keys are contract fields versus display-only fields.

## Constraints

- No workflow state transition is introduced.
- No human review flow is added.
- No alerting or anomaly scan is part of this change.
- Main risk is payload merge correctness and compatibility between producers and consumers.
