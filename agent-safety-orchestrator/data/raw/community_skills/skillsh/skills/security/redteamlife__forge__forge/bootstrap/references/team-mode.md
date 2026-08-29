# Bootstrap Team Mode

Team mode exists to keep concurrent developers and agents from colliding.

At bootstrap time:

- define branch naming and PR policy in `docs/forge/TEAM.md`
- require task claiming before implementation
- require `file_scope` for executable tasks
- prefer GitHub/GitLab issue assignment and labels when `task_source` is issue-backed
- define role split and integration-boundary ownership when the repo is contract-first
- require contract artifacts such as OpenAPI, protobuf, GraphQL, schemas, or generated clients to move with behavior changes
- define the integration closeout contract so `implemented`, `integrated`, and `complete` are not conflated
- enable `ci_enforcement` in `docs/forge/AI.md`
