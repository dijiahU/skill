# FORGE Skill Pack Overview

FORGE works best as a split system:

- Skills hold stable workflow behavior.
- Repo-local docs hold project-specific state.
- CI and hooks hold external enforcement.

## Why This Packaging Helps

- Avoids reloading the same long execution contract every session.
- Lets the agent load only the narrow procedure needed for the current step.
- Preserves project-specific governance data in version-controlled local files.

## Recommended Local State

Start small:

- `docs/forge/AI.md`
- `docs/forge/TASKS.yaml`

Add as needed:

- `docs/forge/ARCHITECTURE.md`
- `docs/forge/EVALUATION.md`
- `docs/forge/MEMORY.md`
- `docs/forge/SECURITY_CHECKLISTS.md`
- `docs/forge/TEAM.md` for shared-repo coordination

## Core FORGE Ideas To Preserve

- one bounded task at a time
- in solo mode, update task state and commit after each completed task before selecting the next one
- in governed solo mode, use task branches and require explicit human instruction before merge or promotion into the release branch
- use Conventional Commits for governed task commits in both solo and team workflows
- keep commit history free of AI attribution or tool-marketing lines
- if batch or auto execution is allowed, preserve the same per-task checkpoint boundary before continuing
- hard stops on ambiguity or conflict
- critique before completion
- explicit security review for risky work
- evidence-based evaluation
- reusable lessons captured in memory

## Team-Scale Additions

For multiple developers or multiple agents working concurrently, preserve these extra controls:

- tasks are claimed before implementation
- branch naming and PR flow are documented in repo-local policy
- executable tasks declare `file_scope`
- evidence and memory records are attributable to task, actor, and branch
- CI validates the same coordination artifacts that humans rely on
