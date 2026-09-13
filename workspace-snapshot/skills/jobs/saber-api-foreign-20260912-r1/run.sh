#!/usr/bin/env bash
set -euo pipefail
source /srv/benchmark/skills/aistation_env.sh
export PATH="/srv/benchmark/skills/jobs/saber-api-foreign-20260912-r1/bin:/srv/benchmark/skills/envs/git-api/usr/bin:$PATH"
export GIT_EXEC_PATH=/srv/benchmark/skills/envs/git-api/usr/lib/git-core
export LD_LIBRARY_PATH="/srv/benchmark/skills/envs/git-api/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="/srv/benchmark/skills/projects/skill-api-20260912:/srv/benchmark/skills/projects/skill-api-20260912/saber${PYTHONPATH:+:$PYTHONPATH}"
export SABER_RESULTS_ROOT=/srv/benchmark/skills/results/saber-api-foreign-20260912-r1/raw
export SABER_LOG_ROOT=/srv/benchmark/skills/jobs/saber-api-foreign-20260912-r1/logs/harness
export SABER_RESOURCE_SCOPE=api-foreign-20260912-r1
export SABER_DOCKER_IMAGE=docker.io/library/osbench-sandbox:latest
export SABER_DOCKER_RUNTIME=runc
export OPENHANDS_SUPPRESS_BANNER=1
cd /srv/benchmark/skills/projects/skill-api-20260912
exec /srv/benchmark/skills/envs/api-saber-20260912/bin/python -u /srv/benchmark/skills/jobs/saber-api-foreign-20260912-r1/controller.py "$@"
