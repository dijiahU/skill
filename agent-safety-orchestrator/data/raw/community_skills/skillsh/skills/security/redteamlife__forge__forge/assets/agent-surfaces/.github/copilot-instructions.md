This repository uses FORGE governance for agent-assisted development.

When working here:

- read `docs/forge/AI.md` and `docs/forge/TASKS.yaml`
- use the installed `forge` skill for governed work
- if the `forge` skill is not installed or available in this session, stop and tell the user FORGE must be installed before governed work continues
- bootstrap `docs/forge/` before implementation if the docs are missing
- execute one bounded task at a time
- use the configured `task_source`; GitHub/GitLab/external trackers are authoritative when selected
- honor declared `contract_files` and update shared API/schema/client contracts with the task that changes them
- in team mode, follow `docs/forge/TEAM.md`, declared `file_scope`, and CI-backed PR workflow
- keep working responses terse and implementation-focused; avoid repeated recap unless a human asks for detail
