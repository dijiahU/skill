# FORGE Repo Flavors

Use this reference only when the repository shape changes which FORGE docs or
checks should be loaded.

`repo_flavor` is optional. Most projects do not need it. Set it only when one
of the flavors below materially changes generated docs or task-selection
behavior. The default repo shape (a normal local or issue-backed project) is
captured by `task_source` alone.

## Contract-First

Use when shared interface artifacts define the implementation boundary.

Examples:

- OpenAPI or AsyncAPI
- protobuf
- GraphQL schema
- generated client configuration
- database migration or data contract files

Rules:

- declare `contract_files` in `ARCHITECTURE.md` or executable task metadata
- API, client, schema, wire-format, and integration-boundary changes must update
  the relevant contract in the same task, PR, or MR
- if another active task owns the required contract file, stop for sequencing

## Tooling

Use for private/public tool repositories and release-surface publishing.

- read `forge-tool-workflow`
- keep private planning/evaluation/memory in the development repo
- publish only intended release artifacts to the public repo
