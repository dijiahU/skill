# GitLab Setup

Use this when the project is hosted on GitLab and `ci_enforcement` should be enabled.

## Repo Files

- Copy the FORGE skill's bundled `assets/ci/` directory into the target project as `ci/` (e.g. `cp -R <skill-root>/assets/ci ./ci`, where `<skill-root>` is the installed FORGE skill directory such as `~/.claude/skills/forge`).
- Translate or wrap the FORGE validation scripts in `.gitlab-ci.yml` jobs.

## Local Hooks

- Run `bash <skill-root>/assets/scripts/install-forge-hooks.sh` (or `powershell -File <skill-root>/assets/scripts/install-forge-hooks.ps1` on Windows) against the target repo to install `pre-commit`, `commit-msg`, and `pre-push` hooks idempotently from the skill's bundled `assets/ci/hooks/`.
- Or install manually: copy `ci/hooks/pre-commit` into `.git/hooks/pre-commit` and `ci/hooks/commit-msg` into `.git/hooks/commit-msg` (and optionally `pre-push`) after the `ci/` directory is in place.

## Task Source

- For `task_source: gitlab`, use issue assignment and labels as the team claim ledger.
- Keep `docs/forge/TASKS.yaml` only as a planning snapshot when GitLab Issues are authoritative.
- Prefer read-only project access tokens for issue-state checks.
- Use a human account or user PAT for assignment when assignee means engineer ownership.
- Link each MR to the issue it closes or advances.

## Protected Branches And Merge Rules

For the integration branch:

- Require merge requests instead of direct pushes.
- Require the FORGE validation pipeline to pass before merge.
- Require the source branch to be up to date with target policy as appropriate.
- Document the merge semantics the repo uses for integration closeout, for example merge commit, squash merge, or fast-forward-only.
- Run `bash ci/scripts/verify-team-closeout.sh --task <task-id> --target integration` before opening the merge request when practical.

For the release branch:

- Require merge requests or a documented release automation path instead of ad hoc direct pushes.
- Require the release validation pipeline to pass before merge if the project uses one.
- Decide who runs the post-promotion release reconciliation step that moves tasks from `integrated` to `complete`.
- Record how claim release metadata is written when tasks move from active branch work to integrated or complete state.

For coordination-branch team mode:

- Consider protecting `forge-state` from casual direct pushes.
- Document who is allowed to publish task claims and how conflicts are resolved.
