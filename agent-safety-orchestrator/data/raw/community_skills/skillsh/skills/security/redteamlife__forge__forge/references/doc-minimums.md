# FORGE Doc Minimums

This reference trims the original FORGE documentation model down to the smallest set that still works well with skills.

## Lightweight Skill-Based Default

Required:

- `docs/forge/AI.md`
- `docs/forge/TASKS.yaml`

Recommended:

- `docs/forge/ARCHITECTURE.md` when architecture constraints matter
- `docs/forge/EVALUATION.md` when explicit gates matter
- `docs/forge/MEMORY.md` when tasks recur across sessions
- `docs/forge/TEAM.md` when more than one developer or agent may execute in the same repo
- `docs/forge/SECURITY_CHECKLISTS.md` when security review should be checklist-driven
- `docs/forge/SETUP.md` when enforcement setup needs to be handed off clearly to humans
- root `AGENTS.md` and `CLAUDE.md` when the repo should remind agents how to load FORGE

Optional:

- `docs/forge/REVIEW_GUIDE.md`
- `docs/forge/ROADMAP.md`
- `docs/forge/ARCHITECTURE_EXPLORATION.md`

## Rule Of Thumb

Only keep a repo-local file if:

- it contains project-specific facts
- it needs to be updated over time
- another tool or CI check will read it

If the content is stable FORGE procedure, it belongs in the skill pack instead.

Token rule of thumb:

- keep repo-local docs factual and compact
- avoid writing long narrative guidance into project docs when short structured fields will do

## Setup Profiles

Use explicit bootstrap profiles when possible:

- `solo-simple`: minimal solo governance, direct branch work allowed, per-task checkpoints preserved
- `solo-governed`: solo operator, but task branches are required and the agent must not merge into `release_branch` without explicit human instruction
- `team-full`: multi-actor coordination with `TEAM.md`, `SETUP.md`, security checklists, and a follow-up choice about copying repo agent surfaces and CI scaffolding

If the user asks for "full setup" or "the full experience", treat that as `team-full` unless they explicitly describe a solo repo.

## Multi-Developer Team Mode

When a project is shared by multiple developers, multiple IDE agents, or both, treat this as the minimum practical set:

- `docs/forge/AI.md`
- `docs/forge/TASKS.yaml`
- `docs/forge/TEAM.md`
- `docs/forge/ARCHITECTURE.md`
- `docs/forge/EVALUATION.md`
- `docs/forge/MEMORY.md`
- `docs/forge/SECURITY_CHECKLISTS.md`
- `docs/forge/SETUP.md`

Additional expectations:

- `ci_enforcement` should be enabled
- task `file_scope` should be required for any task that will be implemented by an agent
- task claims should be recorded before code changes begin
- issue-backed task sources should record issue/MR or issue/PR traceability
- contract-first repos should record contract files, role split, and integration-boundary rules

## Governed Solo Mode

When one human operator wants strong review and branch discipline without team claim coordination, use:

- `docs/forge/AI.md`
- `docs/forge/TASKS.yaml`
- `docs/forge/ARCHITECTURE.md` when constraints matter
- `docs/forge/EVALUATION.md` when review gates matter
- `docs/forge/MEMORY.md` when lessons should persist
- `docs/forge/SETUP.md` when branch protection or review handoff should be recorded

Additional expectations:

- keep `collaboration_mode: solo`
- set `solo_branch_flow: task-branches`
- keep `release_branch` as the real protected branch, usually `main`
- keep `integration_branch` equal to the release branch or avoid inventing a separate integration flow
- create one task branch per governed task
- do not use wildcard branch patterns such as `task/*` as `integration_branch`
- stop after commit and review handoff unless the human explicitly instructs merge or promotion
