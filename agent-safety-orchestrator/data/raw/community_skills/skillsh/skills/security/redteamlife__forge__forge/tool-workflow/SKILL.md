---
name: forge-tool-workflow
description: Apply the FORGE private-dev and public-release workflow for tools. Use when scaffolding a tool repo, reasoning about preserve-history publishing, importing accepted public pull requests, or maintaining the dev-public repository split under FORGE governance.
---

# FORGE Tool Workflow

Use this skill when the repository is a tool project with private governance and a public release surface.

## Covers

- `forge.yaml` shape
- private dev repo versus public repo roles
- preserve-history versus snapshot-force-push publishing
- public PR intake back into the private dev repo

## Read On Demand

- `references/tool-workflow-summary.md`

Prefer scripts for deterministic publish or sync operations; do not restate shell logic unless the user needs it explained or adapted.
