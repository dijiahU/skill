---
trigger: always_on
---

This project uses FORGE governance.

- read `docs/forge/AI.md` and `docs/forge/TASKS.yaml`
- use the installed `forge` skill when doing governed work
- if the `forge` skill is not installed or available, stop and tell the user FORGE must be installed before governed work continues
- if docs are missing, bootstrap `docs/forge/` first
- execute one bounded task at a time
- use the configured `task_source`; GitHub/GitLab/external trackers are authoritative when selected
- honor declared `contract_files` and update shared API/schema/client contracts with the task that changes them
- in team mode, follow `docs/forge/TEAM.md`, task claim rules, and PR-based merge discipline
- keep working responses terse and implementation-focused; avoid repeated recap unless a human asks for detail
