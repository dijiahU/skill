# Repository Guidelines

## Project Structure & Module Organization

This repository currently contains AIStation migration and environment-support files under `skills/`:

- `skills/AIStation_Skill_SABER_Codex_Migration.md` documents the cluster architecture, verified setup, and pending SABER compatibility work.
- `skills/aistation_env.sh` defines the Python environment, Docker endpoint, path mapping, and runtime settings.
- `skills/bin/` contains pinned operational binaries, including the Docker 24 client and Codex launchers.

The migration document describes the intended project checkout under `skills/projects/skill/`, with `agent-safety-orchestrator/`, `saber/`, and `benchflow/` as sibling modules. Keep models, datasets, results, environments, and caches outside source directories.

## Build, Test, and Development Commands

Load the cluster configuration before Docker-based work:

```bash
source skills/aistation_env.sh
docker version
```

`docker version` should report a client/server API compatible with 1.43. For the safety orchestrator, run the documented consistency checks from its module root:

```bash
python3 scripts/_atomic_capabilities.py
python3 scripts/gen_router_atom_catalog.py --check
python3 scripts/gen_archetype_skill_md.py --check
python3 scripts/vendor_plugin_docs.py --check
python3 -m py_compile hooks/scripts/*.py
```

There is no repository-wide build command in the current checkout; use module-specific instructions when project sources are restored.

## Coding Style & Naming Conventions

Use four-space indentation for Python and two spaces for shell continuation lines. Prefer `snake_case` for Python and shell helpers, uppercase names for exported environment variables, and lowercase hyphenated Docker resource names. Project-created containers and images must use an explicit prefix such as `rick-saber-*` or `skilldistill-*`. Preserve existing Unix-socket behavior when adding AIStation TCP Docker support.

## Testing Guidelines

Run the consistency and syntax checks above after changing generated catalogs, archetype skills, plugin docs, or hooks. For Docker changes, begin with a disposable smoke container using `--runtime=runc` and `--network none`. Never assume Pod paths are valid host bind-mount paths; test translation from `POD_USER_ROOT` to `HOST_USER_ROOT`.

## Commit & Pull Request Guidelines

No Git history is available in this checkout, so use concise imperative subjects, for example `Add TCP Docker host support`. Keep commits focused. Pull requests should explain the affected module, list validation commands and results, note AIStation-specific behavior, and link related issues. Include logs for CLI changes and screenshots only for user-interface changes.

## Security & Cluster Safety

The Docker endpoint targets the node's host daemon and effectively has root-level authority. Never run prune commands or stop/remove resources not created by this project. Do not expose port 2375, commit credentials, or store durable artifacts only in `/root`, `/tmp`, or container overlays.

## Agent Authorization Boundaries

Agents may inspect and modify repository files and run non-destructive development commands without additional approval. Ask the user before deleting any file, even when it appears generated or temporary. Do not delete, stop, retag, overwrite, or prune Docker images, containers, volumes, or other host resources identified in the migration documentation; never modify unrelated Kubernetes or shared-node resources. Treat all host-Docker cleanup as destructive and require explicit approval for the exact project-owned target.

## GPU Idle Controller & Foreground Tasks

Use `/2024233123/skills/bin/gpu-idle` to manage the user-authorized Qwen idle workload:

```bash
/2024233123/skills/bin/gpu-idle start
/2024233123/skills/bin/gpu-idle status
/2024233123/skills/bin/gpu-idle stop
```

While the controller is enabled, launch new GPU jobs through its priority entry point:

```bash
# Example: a job using both physical GPUs
/2024233123/skills/bin/gpu-idle run --gpus 0,1 -- bash your_job.sh
```

For single-GPU jobs, use `--gpus 0` or `--gpus 1`. Match the reservation to the job's actual GPU usage; do not override `CUDA_VISIBLE_DEVICES` to use unreserved cards. Wrap the complete model-server-and-consumer lifecycle, not a launcher that backgrounds its work and immediately exits.

The controller releases the selected idle replicas and confirms free memory before starting the foreground command. After that command exits and a card remains free for 30 seconds, Qwen reloads automatically. Each free card runs one replica with four SABER treatment workers looping indefinitely. A resident model server still owns its GPU even at 0% utilization; never stop another task's server to make room.

This user-authorized lifecycle permits automatic termination of the controller's own process groups and disposable containers, identified by both the exact session label and `rick-saber-idle-<session>-` name prefix. This permission does not extend to other resources or file deletion. Results stay in container `tmpfs`; operational logs remain under `skills/logs/gpu-idle/`.

Direct launches are detected only on a best-effort basis; reliable pre-allocation handoff requires the priority entry point. This is a local Pod controller, not a cluster-wide scheduler. Do not run the older single/dual forever scripts concurrently. After Pod/node restart, run `gpu-idle start` again.

See [the usage and validation guide](skills/jobs/gpu_idle_README.md) for details. After controller changes, run `python3 skills/jobs/tests/test_gpu_idle.py -v`.

## Formal GPU Scheduling Preference

Prefer concurrent use of both available, user-authorized GPUs for formal jobs.
Run a dual-GPU model with a matching two-GPU reservation; pair compatible
single-GPU jobs on separate cards instead of deliberately running them serially.
In particular, GLM and gpt-oss should run concurrently on GPU 1 and GPU 0 when
both are queued and their resource requirements permit it. Idle filler work
does not count as parallel progress on the formal evaluation.

Do not interrupt an active model merely to rebalance this pairing. Startup,
cleanup, unequal completion times, and lack of another compatible queued job
can leave a card temporarily unused. This preference does not authorize
additional jobs, unreserved GPUs, or host-Docker cleanup; all existing ownership
checks, approval boundaries, and result-validation gates still apply.
