---
name: forge-execute-task
description: Execute one bounded FORGE task from repository-local governance docs. Use when reading `docs/forge/` state, selecting the next incomplete task, enforcing task scope, checking alignment, implementing changes, and stopping on ambiguity or failed gates.
---

# FORGE Execute Task

Use this skill to perform one controlled implementation pass.

## Required Inputs

Prefer to read only:

- `docs/forge/AI.md`
- `docs/forge/TASKS.yaml`
- `docs/forge/TEAM.md` if present
- `docs/forge/ARCHITECTURE.md` if present
- `docs/forge/MEMORY.md` if present

Read extra docs only when the selected task requires them.

## Output Discipline

- keep status updates short and persistent across the full task pass
- use direct statements, not assistant-style narration
- prefer fragments when they remain clear
- report implementation outcome, blocker, or next action without conversational filler
- do not narrate routine steps if code changes or concrete results can speak for themselves
- do not narrate that you are reading, checking, confirming, or planning unless that changes a decision
- do not restate reasoning already recorded in repo files
- do not echo file contents into chat unless the user asked to inspect them
- when blocked, explain only the minimum facts needed for a human decision

Default response shapes:

- working update: `Status: <done/doing/blocker>. Next: <next step>.`
- closeout: `Done: <result>. Changed: <files or areas>. Next: <next step or none>.`
- blocker: `Blocked: <fact>. Need: <decision or prerequisite>.`

Soft caps:

- working update: 2 short lines max
- normal closeout: 4 short lines max
- bootstrap-style closeout inside execution: 6 short lines max

## Workflow

1. Confirm branch safety and project-local prerequisites.
2. Parse `AI.md` for mode, execution style, collaboration settings, `task_source`, `repo_flavor`, and any solo branch-flow policy.
3. If `TEAM.md` exists, apply its integration branch, release branch, claiming, and review rules before task selection.
4. For `task_source: local`, select tasks from `TASKS.yaml`.
5. For `task_source: github`, use `gh issue list` / `gh issue view` to select work when `gh auth status` passes; otherwise stop and ask for authentication or an explicit issue reference.
6. For `task_source: gitlab`, use `glab issue list` / `glab issue view` to select work when `glab auth status` passes; otherwise stop and ask for authentication or an explicit issue reference.
7. For `task_source: external`, use only the configured MCP, CLI, or human-provided issue reference; do not invent local tasks as authoritative state.
8. In solo mode, select the first eligible task from the authoritative task source and treat it as the only task allowed in this execution pass.
9. In team mode with `task_source: local`, fetch the latest coordination branch and select only a task that is unclaimed or already claimed by the current actor and branch in the latest shared state.
10. In team mode with `task_source: github`, claim by assigning the GitHub Issue to the current actor and adding an `in-progress` label; if it is assigned to someone else, skip it.
11. In team mode with `task_source: gitlab`, claim by assigning the GitLab Issue to the current actor and adding an `in-progress` label; if it is assigned to someone else, skip it.
12. If team mode is active, derive operator identity from project policy or local git identity before claiming work.
13. For local team claims, record `claimed_by`, `claimed_by_email`, and `agent`, publish the claim on the coordination branch, and only then begin implementation.
14. For issue-backed team claims, record task state with issue assignment, labels, and comments rather than editing `TASKS.yaml` as the primary ledger.
15. After local claim publication, treat `forge-state` as the authoritative ledger and the feature-branch copy of `TASKS.yaml` as informational only.
16. If a local task includes `issue_provider`, `issue_iid`, or `issue_url`, reconcile claim and state through that issue before implementation even when `TASKS.yaml` is present.
17. If `MEMORY.md` exists, read recent high-signal entries first.
18. Check task alignment against scope and architecture constraints.
19. If the task or architecture declares `contract_files`, treat those files as shared interface boundaries.
20. When a task changes API, generated client, schema, wire format, or integration-boundary behavior, include the relevant contract file in scope and update it in the same task, PR, or MR.
21. If a needed contract file is owned by another active task, issue, PR, or MR, stop for sequencing rather than creating a parallel contract collision.
22. If `application_docs: true`, identify which human-facing `docs/` files the current task triggers an update for and include them in scope. The trigger map lives in `references/application-docs.md`; the most common cases:
    - API/schema/contract change → `docs/interfaces-and-protocols.md`
    - new component, trust boundary, or major dependency → `docs/architecture-overview.md`
    - build/test/local-dev/release-process change → `docs/developer-guide.md`
    - new attack surface or post-incident hardening → `docs/threat-model.md`
    - deployment process change → `docs/deployment-playbook.md`
    - newly observed failure mode → `docs/incident-runbook.md`
    - significant architectural decision → new `docs/adr/NNNN-<slug>.md`
23. Implement only the selected task.
24. Before any task-state transition to `implemented`, `integrated`, or `complete`, reconcile again with the authoritative task source.
25. In team mode, treat merged feature branches as temporary and delete them after the integration PR is accepted unless project policy explicitly keeps them.
26. Do not move a task from `integrated` to `complete` unless release-branch acceptance is observable through explicit human confirmation, recorded release metadata, or a fetched release-branch reconciliation step.
27. Hand off to critique, security review, and evaluation before transition to the next task state.
28. In `collaboration_mode: solo` with `solo_branch_flow: task-branches`, create or continue the task branch before implementation, do not implement on `release_branch`, and do not merge or promote into `release_branch` unless the human explicitly instructs that action.
29. In solo mode, after a task reaches `complete`, update the authoritative task source, create a Conventional Commit for the completed task work, and stop. Do not begin or partially implement the next task in the same pass.
30. If the project explicitly allows batch or auto execution, start the next task only after the current task has been fully checkpointed: task state updated, required evidence recorded, and Conventional Commit created. Batch mode never permits combining multiple tasks into one uncommitted work span.
31. Do not include AI attribution, assistant branding, or tool-marketing lines in commit messages or trailers. Commit history should describe the work, not advertise the agent.

## Token Saving Rules

- prefer using the selected task description plus only the directly relevant docs
- do not reload unchanged architecture or memory files repeatedly in one pass
- for security review, read only the checklist sections that match the current change surface
- for team mode, do not treat ordinary feature-branch ledger drift as something worth repeated verbose reporting

## Hard Stops

Stop when:

- the task is ambiguous
- required repo-local docs are missing
- the change conflicts with documented architecture
- the task would exceed declared file scope
- the task would change an integration boundary but the relevant contract file is not in scope
- a contract file needed by the task is owned by another active task, issue, PR, or MR
- the task declares `requires_independent_review: true` and the same agent that implemented it is being asked to run `forge-evaluation` or move the task to `complete` without an independent reviewer or separate session
- team mode is active and the task lacks claim metadata or required `file_scope`
- the operator identity cannot be determined for a team-mode claim
- another actor already holds the claim for the selected task
- `task_source: github` is configured but GitHub issue state cannot be read or updated
- `task_source: gitlab` is configured but GitLab issue state cannot be read or updated
- `task_source: external` is configured but the external task cannot be read or updated through the configured interface
- the latest authoritative task source cannot be fetched or the claim cannot be published
- a task-state transition cannot be reconciled against the authoritative task source
- the current branch does not match the task's recorded branch policy
- an issue-backed task cannot verify that the issue assignee, label, branch, and PR/MR link match project policy
- solo-governed mode is active and the current branch is the configured `release_branch`
- solo-governed mode is active and merge or promotion into `release_branch` was not explicitly instructed by the human
- unresolved security concerns appear
- the completed task work has not been committed with a Conventional Commit yet
- a prior completed task remains uncommitted or `TASKS.yaml` is stale before selecting new work
- batch or auto behavior is requested but the prior task has not been checkpointed before next-task selection
- the commit message includes AI attribution such as "generated by", "coded with", or agent brand tags

For rationale, read `references/skill-pack-overview.md` only if needed.
