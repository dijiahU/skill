# GitHub Setup

Use this when the project is hosted on GitHub and `ci_enforcement` should be enabled.

## Repo Files

- Copy the FORGE skill's bundled `assets/ci/` directory into the target project as `ci/` (e.g. `cp -R <skill-root>/assets/ci ./ci`, where `<skill-root>` is the installed FORGE skill directory such as `~/.claude/skills/forge`).
- Copy `ci/workflows/forge-governance.yml` from the just-copied `ci/` tree into `.github/workflows/`.

## Local Hooks

- Run `bash <skill-root>/assets/scripts/install-forge-hooks.sh` (or `powershell -File <skill-root>/assets/scripts/install-forge-hooks.ps1` on Windows) against the target repo to install `pre-commit`, `commit-msg`, and `pre-push` hooks idempotently from the skill's bundled `assets/ci/hooks/`.
- Or install manually: copy `ci/hooks/pre-commit` into `.git/hooks/pre-commit` and `ci/hooks/commit-msg` into `.git/hooks/commit-msg` (and optionally `pre-push`) after the `ci/` directory is in place.

## Task Source

- For `task_source: github`, use issue assignment and labels as the team claim ledger.
- Keep `docs/forge/TASKS.yaml` only as a planning snapshot when GitHub Issues are authoritative.
- Prefer read-only tokens for issue-state checks.
- Use a human account or user-scoped token for assignment when assignee means engineer ownership.
- Link each PR to the issue it closes or advances.

## Branch Protection

For the integration branch:

- Require pull requests before merge.
- Require status checks to pass before merging.
- Add `FORGE Governance Checks` as a required check.
- Require branches to be up to date before merging.
- Document the merge semantics the repo uses for integration closeout, for example merge commit, squash merge, or fast-forward-only.
- Run `bash ci/scripts/verify-team-closeout.sh --task <task-id> --target integration` before opening the feature PR when practical.

For the release branch:

- Require pull requests before merge unless the team has a documented release automation path.
- Require status checks to pass before merging.
- Limit who can promote integrated work if the project needs stronger release control.
- Decide who runs the post-promotion release reconciliation step that moves tasks from `integrated` to `complete`.
- Record how claim release metadata is written when tasks move from active branch work to integrated or complete state.

For coordination-branch team mode:

- Consider protecting `forge-state` from casual direct pushes.
- If only automation or maintainers should update claim state directly, document that rule explicitly.
