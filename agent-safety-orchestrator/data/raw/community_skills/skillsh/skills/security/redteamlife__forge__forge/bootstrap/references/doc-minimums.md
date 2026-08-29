# Bootstrap Doc Minimums

Use the smallest project-local governance set that still supports bounded execution.

## Solo Default

Required:

- `docs/forge/AI.md`
- `docs/forge/TASKS.yaml`

Recommended:

- `docs/forge/ARCHITECTURE.md` when architecture constraints materially matter
- `docs/forge/EVALUATION.md` when explicit completion gates are needed
- `docs/forge/MEMORY.md` when the project benefits from reusable lessons
- root `AGENTS.md` and `CLAUDE.md` when the repo should remind agents how to load FORGE

Use this for `solo-simple`.

## Solo Governed

Use the solo-governed profile when one operator still wants branch discipline and human-controlled merges.

Required:

- `docs/forge/AI.md`
- `docs/forge/TASKS.yaml`

Recommended:

- `docs/forge/ARCHITECTURE.md` when architecture constraints materially matter
- `docs/forge/EVALUATION.md` when explicit completion gates are needed
- `docs/forge/MEMORY.md` when the project benefits from reusable lessons
- `docs/forge/SETUP.md` when branch protection or human review handoff needs to be recorded
- root `AGENTS.md` and `CLAUDE.md` when the repo should remind agents how to load FORGE

Additional expectations:

- set `collaboration_mode: solo`
- set `solo_branch_flow: task-branches`
- keep `release_branch` as the real protected branch, usually `main`
- keep `integration_branch` equal to the release branch or omit any special integration flow unless the project truly has one
- work from task branches rather than directly from `release_branch`
- do not use wildcard branch patterns such as `task/*` as `integration_branch`
- do not merge into `release_branch` without explicit human instruction

## Team Default

Add these from the start when multiple developers or agents will work in parallel:

- `docs/forge/TEAM.md`
- `docs/forge/SECURITY_CHECKLISTS.md`
- explicit `file_scope` on executable tasks
- task claim metadata in `TASKS.yaml`
- copy repo agent-surface files when the user wants persistent repo reminders
- copy CI assets when the user wants hosted enforcement from the start
- add contract files, role split, and integration-boundary rules when `repo_flavor: contract-first`
- add issue/MR or issue/PR traceability when `task_source` is GitHub, GitLab, or external
- generate the human-facing `docs/` tree (overview, developer guide, ADRs, plus the profile-appropriate subset of architecture, threat model, interfaces, deployment, runbook) when `application_docs: true`
