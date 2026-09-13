#!/usr/bin/env bash
set -euo pipefail
source /srv/benchmark/skills/aistation_env.sh
export OPENHANDS_SUPPRESS_BANNER=1 LITELLM_LOCAL_MODEL_COST_MAP=True
exec /srv/benchmark/skills/envs/api-saber-20260912/bin/python -u /srv/benchmark/skills/jobs/gptoss-oas-terminal-20260913-r1/lifecycle.py "$@"
