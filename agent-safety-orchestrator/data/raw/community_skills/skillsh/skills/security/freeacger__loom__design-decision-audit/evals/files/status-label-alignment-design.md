# Status Label Alignment Design

## Background

The admin dashboard currently maps numeric `status` values to outdated labels.
We want to align display labels with the latest operations terminology.

## Proposed Change

- Keep stored numeric `status` values unchanged.
- Update the API enum documentation for status display labels.
- Rename one response field from `status_label` to `display_status_label`.
- Keep `source` as a display-only field for analytics attribution.

## Constraints

- No new state transition.
- No retry worker.
- No lock or compare-and-set logic.
- No manual approval step.
- Existing clients may need one release to switch to the new display field.
