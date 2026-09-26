# Changelog

All notable changes to the Agent Safety Orchestrator plugin are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [1.3.0] — 2026-06-08

Router-first **strict hierarchy**: the 14 archetypes are no longer top-level skills.

### Changed
- **Single entry point.** The only host-registered skill is now `safety-router-skill`.
  The 14 archetype checks moved from `skills/<archetype>/SKILL.md` to reference docs
  under `skills/safety-router-skill/references/archetypes/<archetype>.md`. The Router
  routes a phase by telling the model to `Read` the relevant archetype doc, instead
  of the model invoking an archetype skill directly.
- **Guaranteed router-first.** Because archetypes are no longer independently-invocable
  skills, there is no way to reach a child check without first going through the Router
  — closing the previous gap where the model could invoke an archetype skill (or be
  primed by all 14 archetype descriptions) without the Router.
- **Leaner session-start context.** Only the Router's description is injected at session
  start; the 14 archetype descriptions no longer sit in context until the model `Read`s
  them. Passive priming surface drops from 15 skill descriptions to 1.

### Notes
- No vocabulary change — still 95 atoms / 19 archetypes / 5 phases; `atoms.json`,
  hook layer, and helpers are untouched. This is a packaging/hierarchy change only.
- Both installers pick up the new layout automatically (the Claude plugin and the
  Codex adapter both enumerate `skills/*/`, which now matches only the Router whose
  nested `references/` travels with it).

## [1.2.0] — 2026-06-05

Multi-host: the same safety core now installs on **OpenAI Codex** as well as Claude Code.

### Added
- **OpenAI Codex adapter** (`adapters/codex/`) — a thin hook bridge
  (`codex_hook.py`) that translates Codex hook events into the **same** matcher
  core and returns Codex's `permissionDecision: deny` / `exit 2`, so the hook
  layer is **deterministic on Codex too**. Ships a Codex `hooks.json`, a
  `config.backstop.toml` (sandbox + approvals) for the channels Codex
  `PreToolUse` can't intercept (`unified_exec` streaming shell, `WebSearch`), and
  a safe installer. The 15 skills are reused as-is for the Codex skill layer.
- **Unified installer** — repo-root `./install.sh` is now a dispatcher
  (`--host claude | codex | both | auto`) that auto-detects installed agents and
  installs onto each.
- **CI dual-host proof** — `validate.yml` now compiles/parses the adapter and
  asserts the Codex bridge denies a destructive call (`deny` + `exit 2`).

### Changed
- **One safety core, no duplication** — the Codex adapter reuses the repo's own
  `hooks/scripts/`, `helpers/`, `atoms.json`, and `skills/` (the bridge resolves
  them at runtime; the installer assembles a self-contained deployment at install
  time). There is no vendored copy.
- The Claude Code manual (non-plugin) installer moved from the repo root to
  `adapters/claude/install.sh`. The `/plugin` install flow is unchanged.

## [1.1.0] — 2026-06-05

Initial public release as a Claude Code plugin.

### Added
- **95 safety atoms** across **19 archetypes** and **5 execution phases**
  (input-understanding / planning / tool-invocation / output-generation / cross-cutting).
- **Two enforcement layers:**
  - **Hook layer** — 8 always-on matcher scripts wired into `UserPromptSubmit` /
    `PreToolUse` / `PostToolUse` / `Stop`, covering 60 pure-hook + 21 hybrid
    fast-path atoms; block (`exit 2`) or warn before a tool runs.
  - **Skill layer** — a model-invoked `safety-router-skill` meta-skill that routes,
    per execution phase, to 14 archetype safety skills (14 skill + 21 hybrid
    LLM-fallback atoms), loaded via progressive disclosure.
- **Supply-chain checks** (typosquat / hallucinated package / CVE) against
  OSV / PyPI / npm, with an offline cached-snapshot fallback and circuit breaker.
- **Deployment metadata** per atom (`requires_network`, `fail_policy`) with
  three-state degradation semantics (`fail-open-warn` / `fail-soft-block` /
  `fail-closed`) and a session-start health banner so degradation is never silent.
- **Self-contained packaging**: `.claude-plugin/{plugin.json,marketplace.json}`,
  vendored atom-vocabulary reference under `docs/`, MIT `LICENSE`, and a manual
  `install.sh` path for non-plugin / air-gapped setups.

[1.2.0]: https://github.com/tychenn/agent-safety-orchestrator/releases/tag/v1.2.0
[1.1.0]: https://github.com/tychenn/agent-safety-orchestrator/releases/tag/v1.1.0
