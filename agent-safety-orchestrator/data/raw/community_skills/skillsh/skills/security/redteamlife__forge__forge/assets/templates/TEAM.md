# Team Workflow

Use this file when multiple developers or multiple agents work in the same repository.

## Branch Policy

- Coordination branch: `forge-state`
- Integration branch: `develop`
- Release branch: `main`
- Task source: `local`
- Work on feature branches only.
- Branch naming pattern: `<task-id>/<actor>`
- Do not implement governed tasks directly on `main` or other protected branches.
- Document the merge semantics used for integration and release promotion, for example PR merge, squash merge, or fast-forward-only.

## Role Split

- Engineering roles:
  - Backend:
  - Frontend:
  - Infrastructure:
- Integration boundary:
  - Contract files:
  - Owner:
  - Sequencing rule:

## Task Claiming

- Fetch the latest authoritative task source before claiming any task.
- A task must be claimed in the configured task source before implementation starts.
- For `task_source: local`, claim in `docs/forge/TASKS.yaml` and push on the coordination branch.
- For `task_source: github`, claim by assigning the GitHub Issue and adding an `in-progress` label.
- For `task_source: gitlab`, claim by assigning the GitLab Issue and adding an `in-progress` label.
- For `task_source: external`, use the configured MCP, CLI, or human-owned tracker workflow.
- If a task includes `issue_url`, `issue_iid`, or `issue_provider`, reconcile claim state through that issue before starting implementation.
- The claim must record `claimed_by`, `claimed_by_email`, `agent`, `claimed_at`, `claim_commit`, and `branch`.
- Do not work a task already claimed by another actor.
- If a local claim push conflicts, refresh the coordination branch and retry rather than proceeding from stale state.
- If an issue-backed claim changes while selecting work, re-fetch the issue and retry from the latest tracker state.
- Derive identity from local git config or explicit project policy; do not use only `codex` or `claude` as the owner identifier.

## Task Ledger Semantics

- `forge-state` is the authoritative task ledger branch only when `task_source: local`.
- For `task_source: github` or `task_source: gitlab`, the issue tracker is the authoritative task ledger.
- For `task_source: external`, the named external tracker is authoritative; repo-local task files are planning snapshots unless project policy says otherwise.
- `docs/forge/TASKS.yaml` on feature branches is informational only during implementation.
- Ordinary drift between a feature branch and `forge-state` does not block implementation by itself.
- Claim and task-state transitions must reconcile against the authoritative task source.

## Integration Flow

- Feature branches open PRs into the integration branch.
- Agents do not target the release branch directly from feature branches.
- Work should reach `implemented` only after the task branch has a task-scoped Conventional Commit and is ready for feature PR review.
- `integrated` means the work was accepted on the integration branch and the active claim was released.
- `complete` means the integrated work was accepted on the release branch or otherwise formally accepted by team policy.
- Delete merged feature branches after the integration PR is accepted unless the project has an explicit short-lived retention reason.
- Treat promotion from the integration branch to the release branch as a separate acceptance step.

## File Scope

- Every executable task must declare `file_scope`.
- If two active tasks overlap materially in `file_scope`, resequence or split them before implementation.

## Task Closeout

- Do not treat "implemented on a task branch" as task completion.
- Before moving a task to `implemented`, create at least one task-scoped Conventional Commit on the recorded feature branch.
- Before moving a task to `integrated`, verify the recorded feature branch was accepted into the integration branch through the repo's documented merge path.
- Before moving a task to `complete`, verify release-branch acceptance through promotion, release PR evidence, release commit evidence, or explicit team policy.
- When a task reaches `integrated` or `complete`, record `claim_released_by` and `claim_released_at` so the ledger shows there is no longer an active claim.
- Use a standard closeout helper or equivalent local procedure to validate branch, commit, task-state, and merge-target expectations before integration.

## Review And Merge

- Complete critique, security review, and evaluation before opening a PR.
- Record reviewer and validation evidence in `docs/forge/EVALUATION.md`.
- Reconcile with the authoritative task source before marking a task `implemented`, `integrated`, or `complete`.
- Merge only through PR after required CI checks pass.
- Keep the feature branch named in the authoritative task source aligned with the actual PR/MR branch.
- After merge, delete the feature branch so the integration branch stays the durable convergence point.
- After promotion to the release branch, run a release reconciliation step before moving tasks from `integrated` to `complete`.
- Record release evidence on the task when available, for example `release_pr` or `release_commit`.
- Record branch-protection and CI setup status in `docs/forge/SETUP.md`.
