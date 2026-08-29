---
name: forge-evaluation
description: Apply FORGE definition-of-done and evidence checks to a task. Use when verifying completion gates, required testing, documentation updates, and whether the task is eligible to be marked complete and committed.
---

# FORGE Evaluation

Use this skill to decide whether a task is actually complete.

## Evaluate

- task scope is satisfied without unrelated work
- required validation was run
- critique pass is complete
- security review is complete
- if the task declares `requires_independent_review: true`, the implementing agent does not mark it `complete`; evaluation must be performed by a human reviewer or a separate agent session
- required docs are updated
- when `application_docs: true`, the human-facing `docs/` files matching the task's maintenance triggers are updated in the same change set; see `references/application-docs.md` for the trigger map
- when `application_docs: true` and `task_type: architecture-decision`, a new `docs/adr/NNNN-<slug>.md` is present in the change set
- required contract artifacts are updated in the same change set when API, client, schema, generated artifact, or integration-boundary behavior changes
- required DevSecOps evidence is present when the task changes repository controls, CI, CD, dependencies, build artifacts, SBOM, or deployment behavior
- task status and Conventional Commit metadata are ready
- commit message is free of AI attribution or tool-marketing lines
- in team mode, task claim, branch, reviewer, and PR metadata are consistent
- for `task_source: github` or `task_source: gitlab`, issue assignment, labels, and comments match the intended task transition
- for issue-backed work, PR/MR links, branch naming, and issue identifiers match project policy
- for `task_source: external`, external tracker evidence or human acceptance is recorded before completion
- in solo mode, the task is ready to be marked `complete` and committed with a Conventional Commit before any new task starts

## Evidence

Prefer storing structured evidence in `docs/forge/EVALUATION.md`.

If the project uses CI enforcement, confirm that the expected artifacts are updated in the same change set.
For team-full mode, prefer also posting the evaluation summary on the PR so reviewers see it in the review surface.
If a task declares `requires_independent_review: true`, do not self-evaluate completion; post the PR or handoff and wait for human sign-off or a separate review session.
In team mode, prefer task-scoped append-only entries over rewriting shared narrative summaries.

Keep evaluation output compact: gate result first, short evidence notes second.
Do not restate validation reasoning already captured in `EVALUATION.md` unless needed to explain a fail or blocker.
