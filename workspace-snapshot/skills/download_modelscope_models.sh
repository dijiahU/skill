#!/usr/bin/env bash
set -euo pipefail

# Download the Safety Plane evaluation models from ModelScope without using
# workstation/Clash proxy settings. Downloads are resumable in their local dirs.
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy

modelscope_bin="/2024233123/skills/envs/skills/bin/modelscope"
model_root="/2024233123/skills/models/modelscope"
log_root="${model_root}/logs"
max_workers="${MODELSCOPE_MAX_WORKERS:-6}"

mkdir -p "${model_root}" "${log_root}"

download_model() {
  local model_id="$1"
  local local_name="$2"
  shift 2
  local destination="${model_root}/${local_name}"
  local log_file="${log_root}/${local_name//\//__}.log"
  local attempt

  mkdir -p "${destination}"
  for attempt in 1 2 3 4 5; do
    {
      printf '[%s] START model=%s attempt=%s destination=%s\n' \
        "$(date -u +%FT%TZ)" "${model_id}" "${attempt}" "${destination}"
      "${modelscope_bin}" download "${model_id}" \
        --revision master \
        --local-dir "${destination}" \
        --max-workers "${max_workers}" \
        "$@"
    } >>"${log_file}" 2>&1 && {
      printf '[%s] COMPLETE model=%s\n' \
        "$(date -u +%FT%TZ)" "${model_id}" >>"${log_file}"
      return 0
    }
    printf '[%s] RETRY model=%s attempt=%s\n' \
      "$(date -u +%FT%TZ)" "${model_id}" "${attempt}" >>"${log_file}"
  done

  printf '[%s] FAILED model=%s after=5-attempts\n' \
    "$(date -u +%FT%TZ)" "${model_id}" >>"${log_file}"
  return 1
}

worker_a() {
  download_model "MiniMax/MiniMax-M2.5" "MiniMax/MiniMax-M2.5"
}

worker_b() {
  download_model \
    "deepseek-ai/DeepSeek-V4-Flash-0731" \
    "deepseek-ai/DeepSeek-V4-Flash-0731"
}

worker_c() {
  download_model "Qwen/Qwen3.8-27B-FP8" "Qwen/Qwen3.8-27B-FP8"
}

worker_d() {
  download_model \
    "mistralai/Mistral-Small-4-119B-2603" \
    "mistralai/Mistral-Small-4-119B-2603" \
    --exclude "consolidated-*.safetensors"
}

worker_e() {
  download_model \
    "OpenAI-Mirror/gpt-oss-120b" \
    "OpenAI-Mirror/gpt-oss-120b" \
    --exclude "metal/*" "original/*"
}

worker_f() {
  download_model "ZhipuAI/GLM-4.7-Flash" "ZhipuAI/GLM-4.7-Flash"
}

worker_g() {
  download_model "Qwen/Qwen3.5-2B" "Qwen/Qwen3.5-2B"
  download_model "Qwen/Qwen3.5-4B" "Qwen/Qwen3.5-4B"
  download_model "Qwen/Qwen3.5-9B" "Qwen/Qwen3.5-9B"
  download_model "Qwen/Qwen3.5-27B" "Qwen/Qwen3.5-27B"
}

worker_a &
pid_a=$!
worker_b &
pid_b=$!
worker_c &
pid_c=$!
worker_d &
pid_d=$!
worker_e &
pid_e=$!
worker_f &
pid_f=$!
worker_g &
pid_g=$!

status=0
for worker_pid in \
  "${pid_a}" "${pid_b}" "${pid_c}" "${pid_d}" \
  "${pid_e}" "${pid_f}" "${pid_g}"; do
  if ! wait "${worker_pid}"; then
    status=1
  fi
done

exit "${status}"
