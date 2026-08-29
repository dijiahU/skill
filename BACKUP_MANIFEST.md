# Workspace Backup Manifest

This repository is a flattened backup of `/Users/rick/Desktop/skills`, last
updated on 2026-08-30. Nested Git metadata is intentionally removed so working
tree changes are stored as ordinary files in this repository.

Source repository baselines:

- `agent-safety-orchestrator`: `8eceea45`
- `saber`: `95942a5b`
- `benchflow`: `fbababf`

The snapshot excludes generated benchmark outputs (`saber/results/`,
`saber/judged/`, `saber/baselines/results/`, and `saber/logs/`), local API
configuration and authentication files, virtual environments, dependency
caches, bytecode, and nested `.git/` directories.

This update includes the SABER Codex-native runner, Docker runner image,
DeepSeek-compatible provider configuration, cluster migration guidance, and
Safety Orchestrator hook regression fixes. API credentials remain runtime-only
and are not part of the snapshot.
