#!/usr/bin/env bash
# Run a selected OAS infrastructure probe against the GPU 0 debug endpoint.
# Uses 1 synthetic continuation, not the historical 10: engineering results only.
set -Eeuo pipefail
selection=${1:?selection file required}
probe_note=${2:?unique result note required}
shift 2
skills_root=/2024233123/skills
source "${skills_root}/aistation_env.sh"
cd "${skills_root}/projects/skill/openagentsafety"
export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MODELSCOPE_OFFLINE=1
export OPENHANDS_SUPPRESS_BANNER=1 CONVERSATION_TIMEOUT=600
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
unset NPC_API_KEY NPC_BASE_URL NPC_MODEL
exec .venv/bin/openagentsafety-infer .llm_config/glm47-flash-local-oas-debug-gpu0.json \
  --dataset mgulavani/openagentsafety_full_updated_v3 --split train \
  --workspace docker --max-iterations 50 --num-workers 1 \
  --output-dir "${skills_root}/results/openagentsafety" \
  --n-critic-runs 1 --critic pass --max-retries 0 --max-fake-responses 1 \
  --tool-preset default --enable-condenser --condenser-max-tokens 22000 \
  --condenser-max-output-tokens 1024 --select "${selection}" \
  --note "${probe_note}" --skill-mode none "$@"
