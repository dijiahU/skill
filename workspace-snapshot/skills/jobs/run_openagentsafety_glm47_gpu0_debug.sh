#!/usr/bin/env bash
set -Eeuo pipefail
skills_root=/2024233123/skills
source "${skills_root}/aistation_env.sh"
export PATH="${skills_root}/envs/qwen35-vllm/bin:${PATH}"
export PYTHONPATH="${skills_root}/envs/glm47-transformers-main"
export VLLM_USE_EXPERIMENTAL_PARSER_CONTEXT=1
export CUDA_VISIBLE_DEVICES=0
export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MODELSCOPE_OFFLINE=1
export VLLM_WORKER_MULTIPROC_METHOD=spawn VLLM_NO_USAGE_STATS=1
export VLLM_CACHE_ROOT="${skills_root}/cache/vllm-oas-glm47"
export TORCHINDUCTOR_CACHE_DIR="${skills_root}/cache/torchinductor-oas-glm47"
export OMP_NUM_THREADS=8
exec "${skills_root}/envs/qwen35-vllm/bin/vllm" serve \
  "${skills_root}/models/modelscope/ZhipuAI/GLM-4.7-Flash" \
  --served-model-name ZhipuAI/GLM-4.7-Flash \
  --host 0.0.0.0 --port 18010 \
  --tensor-parallel-size 1 --dtype bfloat16 --max-model-len 32768 \
  --max-num-seqs 4 --gpu-memory-utilization 0.65 \
  --enable-auto-tool-choice --tool-call-parser glm47 \
  --reasoning-parser glm45 --language-model-only
