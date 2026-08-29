# FORGE Team Mode

Use this reference when a repository will be worked on by multiple developers, multiple IDE agents, or both.

## Goals

- avoid two actors implementing the same task at the same time
- avoid hidden overlap in edited files
- keep review and merge flow legible across tools
- preserve a lightweight local-state model rather than recreating the full FORGE document set

## Required Controls

- Work from feature branches, never shared long-lived branches.
- Claim a task before implementation starts.
- Publish claims in the configured task source before editing implementation files.
- Require explicit `file_scope` for executable tasks.
- Record the actor and branch on the task itself.
- Use PR-based merge with CI enforcement for completed task work.

## Task Source

`task_source` in `docs/forge/AI.md` selects the authoritative task ledger:

- `local`: `docs/forge/TASKS.yaml`, published through the coordination branch.
- `github`: GitHub Issues, using issue assignment and labels.
- `gitlab`: GitLab Issues, using issue assignment and labels.
- `external`: Jira, Linear, or another tracker managed through MCP, CLI, or human-owned workflow.

For serious multi-agent work on GitHub or GitLab, prefer issue-backed
coordination over `forge-state`. The hosting platform is the lock and audit
ledger; `TASKS.yaml` may still exist as a planning snapshot, but it is not
authoritative.

## Recommended Task Fields

Each executable task should support:

- `status`: `incomplete` | `claimed` | `in_progress` | `implemented` | `integrated` | `blocked` | `complete`
- `task_type`
- `file_scope`
- `depends_on`
- `assignee`
- `issue_provider`
- `issue_iid`
- `issue_url`
- `plan_ref`
- `mr_url`
- `pr_url`
- `claimed_by`
- `claimed_by_email`
- `agent`
- `claimed_at`
- `claim_commit`
- `branch`
- `claim_released_by`
- `claim_released_at`
- `pr`
- `release_pr`
- `release_commit`
- `contract_files`
- `requires_independent_review`

## Claim Protocol

1. Fetch the latest authoritative task source before selecting work.
2. Select only a task whose dependencies are already complete and which is still unclaimed in the latest shared state.
3. If the task is unclaimed in `task_source: local`, record the current actor identity, email, agent/runtime, and feature branch in `TASKS.yaml` and set `status: claimed` or `in_progress`.
4. Commit and push the local claim to the coordination branch immediately before implementation starts.
5. If the task is unclaimed in `task_source: github` or `task_source: gitlab`, assign the issue to the current actor, add an `in-progress` label, and comment with the branch name when useful.
6. If another actor already holds the claim, do not proceed.
7. If the task's `file_scope` overlaps heavily with another active task, stop and split or resequence the work.
8. If publishing the claim fails because the authoritative task source changed, stop, refresh, and retry from the latest state.

## Closeout Contract

Team mode should treat branch implementation, integration, and release acceptance as separate checkpoints.

- `implemented` means the recorded feature branch contains the task work, that work is committed with a task-scoped Conventional Commit, and the branch is ready for review against the integration branch.
- `integrated` means the recorded feature branch was accepted into the integration branch through the repo's documented merge path and the active claim was released.
- `complete` means the integrated work was accepted on the release branch or was otherwise formally accepted by explicit team policy.

Do not treat "work exists on a feature branch" as completion by itself.

When a task reaches `integrated` or `complete`:

- record `claim_released_by`
- record `claim_released_at`
- treat the task as no longer actively claimed even though original claim metadata remains for audit history

Projects should document merge semantics in `TEAM.md` or `SETUP.md`, for example PR merge, squash merge, or fast-forward-only.
FORGE should not assume one merge strategy unless the project-local policy says so.

## Coordination Branch

Use a shared branch for governance state, for example `forge-state`, only when `task_source: local`.

- `TASKS.yaml` claims are published there first.
- `forge-state` is the authoritative task ledger.
- Feature branches carry implementation work.
- `TASKS.yaml` on feature branches is informational only and may be stale during implementation.
- An integration branch, for example `develop`, is where completed feature branches converge.
- A release branch, for example `main`, is where approved integrated work is promoted.
- The task's `branch` field should record the feature branch that will carry the code changes.
- Teams should fetch the coordination branch before claiming any task.

For `task_source: github` or `task_source: gitlab`, the issue tracker replaces
the coordination branch for claims and task-state labels.

## Reconciliation Rules

- Drift between a feature branch copy of `TASKS.yaml` and `forge-state` is expected during implementation.
- Do not treat ordinary ledger drift on a feature branch as a hard stop by itself.
- Reconcile against the authoritative task source when task state transitions matter:
  - before claiming a task
  - before changing a task to `implemented`, `integrated`, or `complete`
  - when resolving claim conflicts or blocked state transitions
- Outside those transitions, use the coordination branch as reference context and continue implementation on the feature branch.

## Release Reconciliation

Agents should not guess when a task becomes `complete`.

- `implemented` means the feature branch is ready for review.
- `integrated` means the work was accepted on the integration branch and the active claim was released.
- `complete` means the integrated work is confirmed on the release branch or was otherwise explicitly accepted by team policy.

Use one of these signals before moving a task to `complete`:

- a human explicitly confirms the promotion or formal acceptance
- a release PR into `release_branch` is merged and recorded on the task
- a reconciliation step fetches the latest `release_branch` and confirms the task's merge or release commit is present there

If none of those signals is available, leave the task as `integrated`.

## Branch Roles

- `coordination_branch`: authoritative governance state and task ledger
- `integration_branch`: staging branch where feature work is merged and reviewed together
- `release_branch`: production or release branch promoted from the integration branch

Agents should never target the release branch directly from a feature branch.
Merged feature branches should be deleted after the integration PR is accepted unless project policy explicitly keeps them for a short-lived reason.
Promotion from the integration branch to the release branch should be treated as a separate acceptance step.

## Shared Artifact Guidance

- With `task_source: local`, `TASKS.yaml` is the coordination ledger on the shared coordination branch. Keep edits deterministic.
- Optional issue fields such as `issue_provider`, `issue_iid`, `issue_url`, and `plan_ref` provide traceability when an external tracker is authoritative.
- Optional PR/MR fields such as `pr_url` and `mr_url` should point at the review surface where critique and evaluation evidence are visible.
- `contract_files` marks shared interface artifacts that must not drift from implementation.
- `EVALUATION.md` should prefer append-only task evidence sections or entries.
- `MEMORY.md` should capture reusable lessons, not full PR narratives.
- `TEAM.md` should define the task source, branch naming, claim ownership rules, review expectations, and CI requirements.
- `SETUP.md` should record whether hooks, CI workflows, protected-branch settings, and closeout helper usage were actually configured.

## Role Split And Contract Boundaries

When multiple people or agents split work by layer, record:

- `engineering_roles`, for example backend, frontend, infrastructure, data, or QA
- `integration_boundary`, for example OpenAPI, protobuf, GraphQL, generated client, database migration, or message schema
- contract owners and sequencing rules for shared interface files

If an active task changes behavior across the boundary, it should update the
contract artifact in the same PR/MR. If another active task owns that contract,
stop and resequence rather than creating competing contract changes.

## Tracker Access

Use the least privilege mechanism that still supports the project policy:

- read-only project or service tokens for issue-state verification
- human account or user-scoped token for assignment when assignee means human owner
- bot assignment only when project policy explicitly accepts bot ownership

## Identity Source

In team mode, claim ownership should identify the human operator, not only the agent product.

- `claimed_by` should come from the operator identity, preferably `git config user.name`
- `claimed_by_email` should come from `git config user.email`
- `agent` should record the runtime used, for example `codex` or `claude`

If the operator identity cannot be determined from project policy or local git config, stop rather than inventing a placeholder.

## Minimum Team Workflow

1. Fetch the authoritative task source.
2. Claim the task in that source and publish the claim.
3. Create or update the feature branch recorded on the task or issue.
4. Implement only within declared `file_scope` and contract-boundary rules.
5. Treat non-authoritative task snapshots as informational while implementing.
6. Run critique, security review, and evaluation.
7. Reconcile with the authoritative task source and move the task to `implemented` when the feature branch is ready for review.
8. Run the team's closeout helper or equivalent validation procedure to confirm branch, commit, task-state, tracker links, contract updates, and target-branch expectations before opening the PR/MR.
9. Open a PR/MR from the feature branch to the integration branch and link the issue.
10. Merge only after CI and required review pass.
11. Delete the merged feature branch after acceptance on the integration branch unless project policy says otherwise.
12. Reconcile with the authoritative task source, record claim release evidence, and move the task to `integrated` when the change is accepted on the integration branch.
13. Promote the integration branch to the release branch per project policy.
14. After promotion, run a release reconciliation step: fetch the latest release branch, record any release PR/MR or release commit metadata, and confirm the task's work is now present on the release branch.
15. Move the task to `complete` only after that release-branch acceptance is confirmed or otherwise formally accepted by the team.
