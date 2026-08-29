---
name: forge-bootstrap
description: Bootstrap or migrate a repository into a FORGE skill-based workflow. Use when generating the initial `docs/forge/` files, reducing a document-heavy FORGE setup into a smaller skill-driven contract, or scaffolding the minimum governance files for a project.
---

# FORGE Bootstrap

Use this skill to create or refresh the smallest viable project-local files needed by the FORGE skill pack.

## Goal

Generate lean project state, not a maximal document set.

Treat bootstrap as choosing an explicit setup profile, not as dumping generic templates.

Prefer these profiles:

- `solo-simple`: minimal repo-local governance for one operator working directly with per-task checkpoints
- `solo-governed`: one operator, but each governed task runs on its own task branch and the agent must not merge to `release_branch` without explicit human instruction
- `team-full`: multi-human or multi-agent coordination with claims, branch discipline, and full team-ready repo docs, followed by an explicit choice about copying repo agent surfaces and CI scaffolding

Prefer this minimum:

- `docs/forge/AI.md`
- `docs/forge/TASKS.yaml`
- `docs/forge/ARCHITECTURE.md` when architecture constraints materially matter
- `docs/forge/EVALUATION.md` when explicit completion gates are needed
- `docs/forge/MEMORY.md` when the project benefits from reusable lessons
- `docs/forge/TEAM.md` when multiple developers or agents will work in parallel
- `docs/forge/SECURITY_CHECKLISTS.md` when `forge-security-review` will be used, composed from the relevant files in `assets/security-checklists/`
- `docs/forge/SETUP.md` when local hooks or hosted CI enforcement should be tracked explicitly
- `AGENTS.md` at repo root — always; instructs OpenAI Codex and other agents to read the forge docs before working
- `CLAUDE.md` at repo root — always; uses `@./docs/forge/` includes so Claude Code auto-loads the forge docs on every session
- `docs/` (separate from `docs/forge/`) — only when `application_docs: true`; human-facing delivery and operational documentation. The default subset is profile-aware; see `references/application-docs.md`.

Add more docs only if the project's risk, complexity, or compliance needs justify them.

## Workflow

The bootstrap workflow runs in three phases: **Detect**, **Generate**, and **Follow-up**.
Each phase has a single concern. Do not interleave them.

### Phase 1: Detect

Decide what to generate before writing anything.

1. Read `references/doc-minimums.md`.
2. Read `references/team-mode.md` when the repo will be shared by multiple developers or agents.
3. Inspect the repo shape and infer likely language, framework, and risk profile.
4. Determine the bootstrap profile (`solo-simple`, `solo-governed`, `team-full`) from explicit user intent.
5. If the profile is unspecified and the choice would materially change branch, CI, or collaboration behavior, ask one compact question.
6. Determine `task_source` from explicit user intent. If unspecified, ask one compact question: `local`, `github`, `gitlab`, or `external`.
7. When the repo has a GitHub remote and `gh auth status` succeeds, offer `github` as the default; when it has a GitLab remote and `glab auth status` succeeds, offer `gitlab`.
8. Determine `repo_flavor` only when useful. Most repos do not need it. Set it only when one of the flavors changes generated docs or task-selection behavior:
   - `contract-first` for projects with shared interface artifacts such as OpenAPI, protobuf, GraphQL, generated clients, or migration files
   - `tooling` for private/public tool release workflows
9. Determine `security_profile` from explicit user intent or project risk:
   - `baseline` for normal task-local review
   - `repo-fortress` for branch protection, CODEOWNERS, security policy, and risk visibility
   - `ci-security` for every-commit SAST, secret scanning, dependency/SCA, and findings visibility
   - `full-devsecops` for CI security plus CD pre-flight, DAST, SBOM, provenance, and cleanup evidence
10. Detect existing agent surfaces from the repo, for example `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`, `.github/copilot-instructions.md`, `.codex/hooks.json`, or `.windsurf/rules/`.
11. Determine `application_docs` from explicit user intent. Default `false`. Set `true` when the project wants a human-facing `docs/` tree alongside `docs/forge/` for overview, architecture, threat model, developer guide, interfaces, deployment, runbooks, and ADRs.
12. Load the matching reference docs only when their guidance affects generation:
    - `references/repo-flavors.md` when `repo_flavor` is set
    - `references/devsecops-gates.md` when `security_profile` is stronger than `baseline`
    - `references/agent-flavors.md` when generating or copying agent-specific surfaces
    - `references/application-docs.md` when `application_docs: true`

### Phase 2: Generate

Write only what the chosen configuration requires.

13. Generate the smallest set of governance docs that supports the chosen profile, task source, repo flavor, security profile, and detected agent surfaces.
14. If the repo already has FORGE docs, prefer targeted updates over full regeneration so project-specific edits are preserved.
15. Use `local` for `docs/forge/TASKS.yaml`, `github` for GitHub Issues, `gitlab` for GitLab Issues, and `external` for Jira, Linear, or another tracker managed through MCP, CLI, or human-owned workflow. Do not implement native Jira or Linear behavior in the skill pack itself; document the external tracker key, URL, or MCP expectation in project-local docs.
16. In `solo-governed`, emit explicit config and policy cues in `AI.md`:
    - `collaboration_mode: solo`
    - `solo_branch_flow: task-branches`
    - `task_source` matching the selected source
    - `repo_flavor` only when the repo clearly matches `contract-first` or `tooling`
    - `security_profile` when explicit DevSecOps requirements exist
    - `application_docs: true` only when human-facing docs are wanted
    - keep `release_branch` as the real protected branch
    - do not use wildcard patterns such as `task/*` as `integration_branch`
    - do not imply a team-style coordination branch unless explicitly wanted
17. In `solo-governed`, include task-branch policy and an explicit rule that the agent must not merge into `release_branch` without human instruction.
18. In `team-full`, include branch policy, task-claiming, and integration closeout rules from the start.
19. In `team-full` with `task_source: github` or `gitlab`, make issue assignment and labels the primary coordination ledger.
20. In `team-full` with `task_source: local`, use `docs/forge/TASKS.yaml` plus `coordination_branch` as the shared ledger; document that this is best for smaller teams or offline work.
21. In `team-full` with `repo_flavor: contract-first`, include `contract_files`, role split, and integration-boundary rules in `ARCHITECTURE.md`, `TEAM.md`, and executable task fields.
22. When generating `docs/forge/SECURITY_CHECKLISTS.md`, select only the relevant shared checklist assets rather than copying every possible checklist.
23. Include security checklist sections matching the configured `security_profile` (each level is additive):
    - `repo-fortress` adds Repository Governance
    - `ci-security` adds CI Security and Supply Chain
    - `full-devsecops` adds Continuous Delivery Security
24. When generating `docs/forge/SETUP.md`, include only sections whose `<!-- FORGE-section: <profile> -->` marker matches the configured `security_profile` or is marked `always`. Drop sections that exceed the profile so the file does not carry dead checklist boilerplate.
25. Keep IDE-rule files optional and explicit. Do not turn FORGE into mandatory always-on behavior beyond the user-selected agent-surface files. For Cursor repos, mirror only the project-local collaboration, security, stack, and contract constraints that should be automatic.
26. After all `docs/forge/` files are written, generate `AGENTS.md` at the repo root. List only the docs that were actually bootstrapped, in reading order, with a one-line description of each. Use the repo directory name as the title. Instruct the agent to read them before doing any work.
27. After writing `AGENTS.md`, generate `CLAUDE.md` at the repo root. Use `@./docs/forge/<file>` include syntax for each bootstrapped doc in the same reading order. Add a one-line repo title heading above the includes.
28. When `application_docs: true`, copy the profile-appropriate subset of `assets/application-docs/` into the target repo's `docs/` directory:
    - always: `tool-overview.md`, `developer-guide.md`, `adr/0001-record-architecture-decisions.md`, `adr/README.md`
    - `solo-governed` and `team-full` add: `architecture-overview.md`, `interfaces-and-protocols.md`, `deployment-playbook.md`, `incident-runbook.md`
    - `security_profile >= repo-fortress` adds: `threat-model.md`
    - Fill `updated:` with today's date in each frontmatter.
    - If a file already exists, prefer targeted updates over full overwrite.
29. Keep templates concise and project-specific. Do not generate application code.

### Phase 3: Follow-up

Hand off cleanly with explicit next steps.

30. For `solo-governed` and `team-full`, install the FORGE git hooks automatically by running `bash <skill-root>/assets/scripts/install-forge-hooks.sh` (or `powershell -File <skill-root>/assets/scripts/install-forge-hooks.ps1` on Windows) against the target repo, where `<skill-root>` is the installed FORGE skill directory (for example `~/.claude/skills/forge` or wherever the skill was installed). The installer is idempotent, sources hooks from the skill's bundled `assets/ci/hooks/`, and backs up any non-FORGE hooks to `<name>.bak`. Record the installation outcome in `docs/forge/SETUP.md` under Local Hooks. For `solo-simple`, leave hook installation manual unless the user asks.
31. In `team-full`, after bootstrapping the full team-ready docs, ask one explicit follow-up question: whether the user wants the agent to also copy the reusable agent-surface files and CI scaffolding into the target repo now, or leave those steps manual.
32. If the user chooses manual setup for those repo-level assets, generate explicit next-step guidance instead of copying them.
33. If the project uses GitHub or GitLab, generate explicit next-step setup guidance for CI assets, branch protection, issue-token access, issue/MR or issue/PR linking, and enabled security scanning rather than assuming the team already knows how to wire them.

## Output Style

- Favor short, high-signal docs over exhaustive boilerplate.
- Preserve deterministic headings and field names.
- Keep instructions compatible with both skill-aware and document-first agents.
- Generate only the docs the project actually needs; do not inflate the repo with optional governance files by default.
- Keep generated narrative compact and factual so future sessions do not pay token cost for unnecessary prose.
- Do not narrate routine inspection or planning steps such as "I'm checking" or "I have enough context" unless a blocker or scope decision appears.
- Do not echo generated file contents back into chat unless the user asked to review them.
- Bootstrap closeout should be compact:
  - `Done: <what was bootstrapped>.`
  - `Changed: <docs created or updated, including AGENTS.md and CLAUDE.md>.`
  - `Next: <next task or setup step>.`
- Do not explain the purpose of every generated file unless the user asks.
