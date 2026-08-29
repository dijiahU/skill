---
name: forge
description: Turn AI coding from chaotic one-shot prompting into a reliable engineering workflow. FORGE gives you clear task boundaries, safer commits, review gates, and team-ready coordination so agents can ship real work without losing control of the project.
---

# FORGE

Use this skill when you want agents to stop behaving like unpredictable pair-programmers and start working like disciplined teammates. FORGE gives AI work a real execution model: clear task boundaries, hard stops when things get fuzzy, safer commits, review gates, and a workflow teams can actually trust.

FORGE works best when you want to:

- bootstrap or refresh `docs/forge/` without bloating the repo
- execute the next task with bounded scope and explicit stop conditions
- keep solo work checkpointed and committed one task at a time
- coordinate multiple developers or IDE agents without losing track of ownership
- add CI-backed enforcement when a project needs stronger guarantees

## Quick Routing

- For creating or refreshing FORGE project docs, use `forge-bootstrap`.
- For selecting and implementing the next bounded task, use `forge-execute-task`.
- For scope and quality review before completion, use `forge-critique`.
- For checklist-based security review, use `forge-security-review`.
- For definition-of-done and evidence checks, use `forge-evaluation`.
- For reading and updating reusable lessons, use `forge-memory`.
- For private/public tool release workflows, use `forge-tool-workflow`.
- For multi-developer coordination rules, branch discipline, and task claiming, read `references/team-mode.md`.
- For repo-shape routing such as contract-first or tooling projects, read `references/repo-flavors.md`.
- For agent-specific files such as `AGENTS.md`, `CLAUDE.md`, Cursor rules, Copilot instructions, Codex hooks, or Windsurf rules, read `references/agent-flavors.md`.
- For DevSecOps gate profiles, repository hardening, CI/CD security, SCA, or SBOM controls, read `references/devsecops-gates.md`.
- For human-facing application documentation (overview, architecture, threat model, developer guide, interfaces, deployment, runbooks, ADRs), read `references/application-docs.md`.

## Operating Model

Keep the runtime contract lean:

1. Read only the minimum project-local files needed for the current step.
2. Preserve bounded-task checkpoints at all times. If the project explicitly permits batch or auto behavior, that only means the agent may continue to the next task after finishing the current one, updating task state, and creating the required Conventional Commit.
3. Stop on ambiguity, missing prerequisites, architecture conflict, or unresolved security concerns.
4. Record evidence and memory updates in deterministic project-local files.

## Token Discipline

Default to persistent low-token behavior across working responses.

Drop by default:

- pleasantries and conversational filler
- repeated context recap
- narration of routine inspection or planning steps
- file-purpose explanations when the file path already says enough
- reasoning already captured in project docs or changed files
- file content echo after writing files
- changelog-style narration unless the user asks for it

Prefer by default:

- short action updates
- direct statements
- fragments when they remain clear
- file references over prose recap
- outcome first, next step second

Response shape:

- working update: `Status: <done/doing/blocker>. Next: <next step>.`
- task closeout: `Done: <result>. Changed: <files or areas>. Next: <next step or none>.`
- blocker: `Blocked: <fact>. Need: <decision or missing prerequisite>.`

Soft caps:

- working updates: 2 short lines max
- normal task closeout: 4 short lines max
- bootstrap closeout: 6 short lines max

Exceptions:

- security warnings
- destructive action confirmations
- places where extra clarity prevents misread risk

## Team Mode

When a repository is worked on by multiple developers or multiple IDE agents at the same time:

- require feature branches rather than direct work on shared branches
- require task claiming before implementation begins
- require explicit `file_scope` for executable tasks
- prefer append-only evidence and memory records over rewriting shared summaries
- require CI enforcement and protected branch merging for completed task work

Read these shared references only when needed:

- `references/skill-pack-overview.md`
- `references/doc-minimums.md`
- `references/forge-to-skills-mapping.md`
- `references/team-mode.md`
- `references/repo-flavors.md`
- `references/agent-flavors.md`
- `references/devsecops-gates.md`
- `references/application-docs.md`
- `references/token-efficiency.md`

Use templates from `assets/templates/` only when scaffolding or migrating a project into this skill-based flow.
