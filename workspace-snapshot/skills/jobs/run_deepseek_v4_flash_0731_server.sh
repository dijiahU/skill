#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
model_dir="${skills_root}/models/modelscope/deepseek-ai/DeepSeek-V4-Flash-0731"
vllm_env="${skills_root}/envs/deepseekv4-vllm"
log_dir="${skills_root}/logs/deepseek-v4-flash-0731-vllm"
server_log="${log_dir}/server.log"
status_log="${log_dir}/status.tsv"
api_port="${DEEPSEEK_V4_PORT:-18020}"

mkdir -p "${log_dir}"

write_status() {
  printf '%s\t%s\n' "$(TZ=CST-8 date '+%F %T %Z')" "$1" >>"${status_log}"
}

if [[ ! -x "${vllm_env}/bin/vllm" ]]; then
  write_status "failed missing_vllm"
  exit 2
fi
if [[ ! -f "${model_dir}/model-00048-of-00048.safetensors" ]]; then
  write_status "failed incomplete_model"
  exit 2
fi
if curl --noproxy '*' --silent --fail --max-time 2 \
  "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then
  write_status "failed port_in_use port=${api_port}"
  exit 2
fi

write_status "starting port=${api_port} gpu=0,1 dp=2 ep=true max_model_len=4096"

export CUDA_VISIBLE_DEVICES=0,1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export VLLM_NO_USAGE_STATS=1
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export OMP_NUM_THREADS=8

exec "${vllm_env}/bin/vllm" serve "${model_dir}" \
  --served-model-name "deepseek-ai/DeepSeek-V4-Flash-0731" \
  --host 0.0.0.0 \
  --port "${api_port}" \
  --trust-remote-code \
  --tokenizer-mode deepseek_v4 \
  --data-parallel-size 2 \
  --enable-expert-parallel \
  --moe-backend deep_gemm_mega_moe \
  --attention-config '{"use_fp4_indexer_cache":true}' \
  --kv-cache-dtype fp8 \
  --block-size 256 \
  --max-model-len 4096 \
  --max-num-seqs 1 \
  --max-num-batched-tokens 4096 \
  --gpu-memory-utilization 0.90 \
  --enforce-eager \
  --enable-auto-tool-choice \
  --tool-call-parser deepseek_v4 \
  --reasoning-parser deepseek_v4 \
  >>"${server_log}" 2>&1
