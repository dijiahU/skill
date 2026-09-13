#!/usr/bin/env bash
set -euo pipefail
source /srv/benchmark/skills/aistation_env.sh
export PATH="/srv/benchmark/skills/envs/git-api/usr/bin:$PATH"
export GIT_EXEC_PATH=/srv/benchmark/skills/envs/git-api/usr/lib/git-core
export LD_LIBRARY_PATH="/srv/benchmark/skills/envs/git-api/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export HF_HOME=/srv/benchmark/skills/hf_cache
export HF_DATASETS_CACHE=/srv/benchmark/skills/hf_cache/datasets
export OPENHANDS_SUPPRESS_BANNER=1
cd /srv/benchmark/skills/projects/skill-api-20260912/openagentsafety
exec /srv/benchmark/skills/envs/api-oas-20260912/bin/python -u /srv/benchmark/skills/jobs/oas-api222-20260912-r1/skills100/run_stage.py "$@"
