# FORGE Agent Flavors

Use this reference when generating or copying agent-specific repo surfaces.
Agent surfaces are reminders and routing aids. They do not replace explicit
FORGE activation for governed work.

## Shared

- file: `AGENTS.md`
- use for Codex and other agents that read root agent instructions
- include only bootstrapped docs in reading order
- mention `task_source`, team policy, and contract files when configured

## Claude Code

- file: `CLAUDE.md`
- use `@./docs/forge/<file>` includes for bootstrapped docs
- keep narrative short because Claude auto-loads the file

## Cursor

- files: `.cursor/rules/*.mdc`
- use `alwaysApply: true` only for the minimal FORGE routing rule
- use path-scoped rules for stack, security, contract files, generated clients,
  or integration-boundary behavior
- mirror project-local policy from `TEAM.md`, `ARCHITECTURE.md`, and
  `SECURITY_CHECKLISTS.md`; do not invent new policy in Cursor-only files

## GitHub Copilot

- file: `.github/copilot-instructions.md`
- keep the instruction compact and repo-wide
- point to FORGE docs and issue/PR expectations

## Codex

- file: `.codex/hooks.json` when the repo wants session-start reminders
- keep hook output short and non-blocking
- use `AGENTS.md` for the durable policy when available

## Windsurf

- file: `.windsurf/rules/forge.md`
- use the existing frontmatter style
- mirror the same compact FORGE routing as other always-on surfaces

