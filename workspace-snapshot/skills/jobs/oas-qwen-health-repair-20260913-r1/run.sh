#!/usr/bin/env bash
set -euo pipefail
source /srv/benchmark/skills/aistation_env.sh
source /srv/benchmark/skills/jobs/eval-retry-20260913-r2/network.sh
export PATH="/srv/benchmark/skills/envs/git-api/usr/bin:$PATH"
export GIT_EXEC_PATH=/srv/benchmark/skills/envs/git-api/usr/lib/git-core
export LD_LIBRARY_PATH="/srv/benchmark/skills/envs/git-api/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONPATH=/srv/benchmark/skills/jobs/eval-retry-20260913-r2/frozen
export OPENHANDS_SUPPRESS_BANNER=1 LITELLM_LOCAL_MODEL_COST_MAP=True
exec /srv/benchmark/skills/envs/api-saber-20260912/bin/python -u /srv/benchmark/skills/jobs/oas-qwen-health-repair-20260913-r1/oas_api.py
