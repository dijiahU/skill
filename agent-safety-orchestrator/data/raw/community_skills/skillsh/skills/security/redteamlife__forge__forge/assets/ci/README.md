# FORGE CI Enforcement Layer

This directory contains the pipeline enforcement artifacts for FORGE governance.
They validate FORGE workflow outputs externally, independent of agent behavior.

## Commit Format

FORGE commits follow [Conventional Commits](https://www.conventionalcommits.org) with FORGE metadata as git trailers.

### Subject line

```text
<type>[optional scope]: <description>
```

Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, `revert`

### Required trailers

```text
FORGE-mode: <Lightweight|Mid|Strict|Full Discipline>
FORGE-task: <task-id>
FORGE-gate: pass
```

Trailers must appear in the commit footer, separated from any body text by a blank line.

### Full example

```text
feat(auth): add JWT token validation

Implements token validation per ARCHITECTURE.md trust boundary constraints.

FORGE-mode: Mid
FORGE-task: AUTH-003
FORGE-gate: pass
```

Using git trailers keeps the primary commit message compatible with Conventional Commits tooling (commitlint, semantic-release, conventional-changelog) while making FORGE metadata machine-readable via `git log --format=%(trailers)`.

---

## What the CI Layer Enforces

| Check | Mechanism | Catches |
| --- | --- | --- |
| Commit message format | `commit-msg` hook + CI script | CC format violations, missing FORGE trailers |
| Local task evidence | `pre-commit` hook | Local `TASKS.yaml` state changed without `EVALUATION.md` |
| Task state | CI script | Task in FORGE-task trailer not marked complete |
| Team task metadata | CI script | Missing claim or branch metadata in `collaboration_mode: team` |
| Evidence artifacts | CI script | PR missing updated EVALUATION.md or MEMORY.md |
| Team closeout helper | Optional local script | Task branch lacks task-scoped commit or does not match recorded closeout expectations |

---

## Directory Structure

```text
ci/
├── hooks/
│   ├── pre-commit                      ← local hook: task-state evidence coupling
│   └── commit-msg                      ← local git hook
├── scripts/
│   ├── validate-commit-format.sh       ← CI: subject line + trailer validation
│   ├── validate-team-task-metadata.sh  ← CI: task claim and branch metadata for team mode
│   ├── validate-task-state.sh          ← CI: task marked complete in TASKS.yaml
│   ├── verify-team-closeout.sh         ← local helper: task-branch closeout validation
│   └── validate-evidence-artifacts.sh  ← CI: EVALUATION.md and MEMORY.md updated
├── workflows/
│   └── forge-governance.yml            ← GitHub Actions workflow template
└── policy/
    └── forge-org-policy.template.yaml  ← org-level policy template
```

---

## Setup

### 1. Install the local hooks

```bash
cp ci/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
cp ci/hooks/commit-msg .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
```

These validate local task/evidence coupling and commit format before git accepts the commit. No CI cost. Instant feedback.

### 2. Copy the workflow into the project

```bash
mkdir -p .github/workflows
cp ci/workflows/forge-governance.yml .github/workflows/forge-governance.yml
```

The workflow runs on every pull request and executes the validation scripts in sequence.

### 3. Set the workflow as a required status check

In your repository settings:

- Go to **Settings > Branches > Branch protection rules**
- Add or edit the rule for `main`
- Under **Require status checks to pass before merging**, add `FORGE Governance Checks`
- Enable **Require branches to be up to date before merging**

PRs cannot be merged until all three checks pass.

### 4. Enable ci_enforcement in AI.md

Add `ci_enforcement: enabled` to the `FORGE-config` block in `docs/forge/AI.md`:

```text
FORGE_mode: Mid
execution_mode: manual
collaboration_mode: team
task_source: github
coordination_branch: forge-state
integration_branch: develop
release_branch: main
ci_enforcement: enabled
```

The evidence artifact check reads this field. If absent or not `enabled`, that check is skipped.
In `collaboration_mode: team`, the team metadata validator also requires it and fails closed if it is not enabled.
When `ci_enforcement: enabled`, a PR that changes `docs/forge/TASKS.yaml` or contains a `FORGE-task` trailer must also update `docs/forge/EVALUATION.md` in the same PR. Mid and higher modes still require `docs/forge/MEMORY.md`.

For issue-backed task sources, validate issue assignment, labels, and PR/MR
links through the hosting platform. For contract-first repos, document the
contract file check in project CI or review policy so API/schema/client changes
cannot merge without the matching contract update.
For stronger security profiles, document which external checks are required:
branch protection, CODEOWNERS, security policy, SAST, secret scanning, SCA,
SBOM, DAST, provenance, and cleanup/rollback evidence.

### Evaluation Currency Validator

`ci/scripts/validate-evaluation-currency.sh` requires that any commit that
transitions a task into `implemented`, `integrated`, or `complete` in
`docs/forge/TASKS.yaml` also updates `docs/forge/EVALUATION.md` in the
**same commit**. This is stricter than the same-PR check in
`validate-evidence-artifacts.sh`: it prevents splitting state changes and
their evidence across separate commits. Skipped in Lightweight mode and when
`ci_enforcement` is disabled.

### Memory Bounds Validator

`ci/scripts/validate-memory-bounds.sh` fails closed when
`docs/forge/MEMORY.md` exceeds its declared `max_entries`. Forces
consolidation of oldest entries into a `consolidated` summary entry before
new entries can land.

### Security Profile Validator

`ci/scripts/validate-security-profile.sh` enforces that a stronger
`security_profile` is backed by concrete setup evidence rather than blank
checkboxes. It runs only when `security_profile` is set to `repo-fortress`,
`ci-security`, or `full-devsecops`, and fails closed when:

- the profile-required SETUP.md sections are missing
- profile-required sections contain only blank or placeholder values
- SAST is marked enabled but no SAST workflow or recorded tool exists

Baseline projects skip this check.

### Team Mode Enforcement

If `docs/forge/AI.md` declares `collaboration_mode: team`, CI additionally expects:

- `docs/forge/TEAM.md` to exist and contain branch, claiming, file-scope, and review policy
- every task referenced by a `FORGE-task` trailer to include `file_scope`
- every merged task to include `claimed_by`, `claimed_by_email`, `agent`, `claimed_at`, `claim_commit`, and `branch`
- every task at `integrated` or `complete` to include `claim_released_by` and `claim_released_at`
- the task's recorded `branch` to match the PR branch being validated
- teams should publish claims from a shared coordination branch before feature-branch implementation begins
- teams using `task_source: github` or `task_source: gitlab` should use issue assignment and labels as the claim ledger instead of `forge-state`
- feature PRs should target the configured integration branch, and release promotion should flow from the integration branch to the release branch

Task-state expectations are branch-aware:

- PRs targeting `integration_branch` require task status `implemented`, `integrated`, or `complete`
- PRs targeting `release_branch` require task status `integrated` or `complete`

This gives teams a minimal but enforceable coordination contract across multiple developers and multiple IDE agents.

### Optional team closeout helper

Use the local helper before opening a feature PR when team mode is active:

```bash
bash ci/scripts/verify-team-closeout.sh --task <task-id> --target integration
```

The helper validates the current branch against `docs/forge/TASKS.yaml`, checks for task-scoped commits carrying the matching `FORGE-task` trailer, and confirms the task state is ready for the requested target branch. It can also enforce a clean working tree before closeout.

### 5. (Optional) Configure org-level policy

Copy `ci/policy/forge-org-policy.template.yaml` to a central location your org controls.
Add a fetch step to `forge-governance.yml` to download and validate the project's `AI.md` config against it.

This enforces a minimum mode floor and auto-mode restrictions across all projects in the org.

---

## FORGE Docs and the Repository

FORGE governance documents in `docs/forge/` can be managed in three ways depending on your team's needs:

### Pattern 1 - Embedded (default)

`docs/forge/` is committed alongside code. Simple. All governance artifacts are version-controlled with the project. Appropriate when the repository is private or when public visibility of governance process is acceptable.

### Pattern 2 - Excluded

Add `docs/forge/` to `.gitignore`. Governance docs exist locally and inform execution but are never committed. No audit trail in git history. Appropriate for solo developers or when governance artifacts must not be shared.

```gitignore
# .gitignore
docs/forge/
```

### Pattern 3 - Companion private repository

Code lives in the public repository. Governance docs live in a separate private repository. You clone both locally, work in the public repo with FORGE context available, and push only code publicly. Appropriate for open source projects or any situation requiring separation of internal process from the public artifact.

There is no single correct pattern. Choose the one that matches your team's visibility and audit requirements.

---

## Script Requirements

- `bash`
- `git`
- `python3` with `pyyaml` (used by `validate-task-state.sh`; installed automatically in the workflow)

---

## Scope Notes

The CI scripts validate the *outputs* of the FORGE agent workflow. They do not replace the agent workflow steps. A commit can pass all CI checks and still represent poor work. The CI layer validates governance artifacts, not implementation quality.

Evidence that CI checks passed is itself a valid audit record. The pipeline run log (timestamped, attributed to a specific actor) supplements the evaluation record in `EVALUATION.md`.
