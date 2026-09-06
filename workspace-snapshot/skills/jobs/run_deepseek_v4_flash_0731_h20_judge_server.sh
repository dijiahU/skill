#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
model_dir="${skills_root}/models/modelscope/deepseek-ai/DeepSeek-V4-Flash-0731"
vllm_env="${skills_root}/envs/deepseekv4-vllm"
cuda_home="${skills_root}/envs/cuda-toolkit-12-9/usr/local/cuda-12.9"
compat_dir="${skills_root}/envs/cuda-compat-12-9/usr/local/cuda-12.9/compat"
nvjitlink_dir="${vllm_env}/lib/python3.10/site-packages/nvidia/nvjitlink/lib"
log_dir="${skills_root}/logs/deepseek-v4-flash-0731-h20-judge"
server_log="${log_dir}/server.log"
status_log="${log_dir}/status.tsv"
api_port="${DEEPSEEK_V4_PORT:-18020}"

mkdir -p "${log_dir}"
printf '%s\tstarting port=%s max_model_len=65536 dp=2 ep=true max_num_seqs=4\n' \
  "$(TZ=CST-8 date '+%F %T %Z')" "${api_port}" >>"${status_log}"

export CUDA_VISIBLE_DEVICES=0,1
export CUDA_HOME="${cuda_home}"
export CUDACXX="${cuda_home}/bin/nvcc"
export PATH="${vllm_env}/bin:${cuda_home}/bin:${PATH}"
export CPATH="${cuda_home}/include:${CPATH:-}"
export LIBRARY_PATH="${cuda_home}/lib64:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="${compat_dir}:${nvjitlink_dir}:${cuda_home}/lib64:${LD_LIBRARY_PATH:-}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export VLLM_NO_USAGE_STATS=1
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export FLASHINFER_WORKSPACE_BASE="${skills_root}/cache/flashinfer-deepseekv4"
export VLLM_CACHE_ROOT="${skills_root}/cache/vllm-deepseekv4"
export TORCHINDUCTOR_CACHE_DIR="${skills_root}/cache/torchinductor-deepseekv4"
export OMP_NUM_THREADS=8
export VLLM_ENGINE_READY_TIMEOUT_S=1800

exec "${vllm_env}/bin/vllm" serve "${model_dir}" \
  --served-model-name "deepseek-ai/DeepSeek-V4-Flash-0731" \
  --host 0.0.0.0 \
  --port "${api_port}" \
  --api-server-count 1 \
  --trust-remote-code \
  --tokenizer-mode deepseek_v4 \
  --data-parallel-size 2 \
  --enable-expert-parallel \
  --moe-backend auto \
  --kv-cache-dtype fp8 \
  --block-size 256 \
  --max-model-len 65536 \
  --max-num-seqs 4 \
  --max-num-batched-tokens 8192 \
  --gpu-memory-utilization 0.90 \
  --enforce-eager \
  --enable-auto-tool-choice \
  --tool-call-parser deepseek_v4 \
  --reasoning-parser deepseek_v4 \
  >>"${server_log}" 2>&1
