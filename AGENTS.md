# Repository Guidelines

## Project Structure & Module Organization

The Git repository lives in `agent-safety-orchestrator/`; run project commands from that directory. Research and generation code is under `scripts/`, project documentation under `docs/`, derived manifests and dashboards under `reports/`, and upstream material under `data/raw/`. Treat `data/raw/` as immutable; write transformed outputs to `reports/`.

The distributable bundle is `agent-safety-orchestrator/agent-safety-orchestrator/`. Its main components are `hooks/scripts/` for deterministic checks, `helpers/` for shared runtime support, `skills/safety-router-skill/` for router documentation, and `adapters/` for Claude Code and Codex integration. Isolated end-to-end scenarios live in `pilot/`.

## Build, Test, and Development Commands

Create an optional environment with Python 3.9 or newer:

```bash
cd agent-safety-orchestrator
python3 -m venv .venv && source .venv/bin/activate
python -m pip install numpy requests Markdown
```

Run the core offline validation before submitting changes:

```bash
python3 scripts/_atomic_capabilities.py
python3 scripts/gen_router_atom_catalog.py --check
python3 scripts/gen_archetype_skill_md.py --check
python3 scripts/vendor_plugin_docs.py --check
python3 -m py_compile agent-safety-orchestrator/hooks/scripts/*.py
```

Use `./pilot/run.sh` and `./pilot/run.sh --vanilla` for comparable bundle/baseline integration runs. Fetch, embedding, and LLM-audit scripts may use networks or paid APIs; inspect `--help` and prefer `--dry-run`, `--dry-run-embedding`, or `--limit` first.

## Coding Style & Naming Conventions

Use four-space indentation, type hints, docstrings, and `snake_case` for Python. Keep shell scripts Bash-compatible, quote expansions, and retain `set -euo pipefail`. Matcher files follow `matcher_<event>.py`; atom and archetype IDs use lowercase kebab-case. Do not hand-edit generated catalogs or vendored bundle docs—update their source and rerun the generator.

## Testing Guidelines

There is no standalone unit-test suite. Match CI by compiling Python, validating JSON/TOML and shell syntax, and preserving the structural invariants: 95 atoms, one router skill, 14 archetype references, and eight matchers. Add focused stdin JSON fixtures when changing hook verdict behavior, then exercise relevant Pilot scenarios in both modes.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries in English or concise Chinese, such as `Add project-wide README` or `补齐缺失代码实现`; Conventional Commit prefixes are not required. Keep commits atomic. Pull requests should explain the safety behavior changed, list validation commands, link related issues, and include before/after logs or dashboard screenshots when behavior or generated reports change.

## Security & Configuration

Copy `.env.example` to `.env` for local keys, and never commit secrets, caches, credentials, or Pilot audit transcripts. Preserve third-party licenses within `data/raw/`.
