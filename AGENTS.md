# Repository Guidelines

This repository contains the Agent Safety Orchestrator framework. Run commands
from the repository root.

## Structure

- `hooks/scripts/`: shared safety checks and event normalization.
- `helpers/`: health checks, audit support and vulnerability caches.
- `adapters/`: Claude Code, Codex and DSH host integration.
- `skills/safety-router-skill/`: Router and 14 archetype references.
- `docs/SAFETY_ATOMIC_CAPABILITIES.md`: source capability definitions.
- `scripts/`: manifest and reference generators.
- `tests/`: framework regressions using Python's standard library and Node.js.

Keep experiment harnesses, benchmark datasets, paper assets, results and local
workspace backups outside this repository.

## Validation

Run the full test suite on Linux; snapshot fixtures assume Linux path semantics.

```bash
python3 scripts/check_repository.py
python3 -m unittest discover -s tests -v
node --test tests/test_dsh_adapter.mjs
```

Preserve 95 atoms, one Router skill, 14 archetype references and eight matchers.
Update generator sources and regenerate derived files. Keep tests independent
of external datasets and model APIs. Run installer checks only with isolated
configuration and skill directories.

## Style and contributions

Use four-space Python indentation, descriptive snake_case names and existing
type hints. Keep shell scripts Bash-compatible. Commit messages should explain
the framework behavior or packaging change; record validation results.

Preserve licenses and attribution. Keep credentials, rendered host settings,
local environments, audit logs and caches out of Git.
