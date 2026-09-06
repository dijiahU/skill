#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
model_dir="${skills_root}/models/modelscope/ZhipuAI/GLM-4.7-Flash"
vllm_env="${skills_root}/envs/qwen35-vllm"
transformers_overlay="${skills_root}/envs/glm47-transformers-main"
proxy_script="${skills_root}/bin/vllm_responses_compat_proxy_glm47.py"
runtime_config="${skills_root}/jobs/saber_glm47_baseline_716.json"
subset_dir="${skills_root}/jobs/saber_glm47_baseline_716_subsets"
model_id="ZhipuAI/GLM-4.7-Flash"
model_slug="codex_glm47_flash_baseline_716"
api_port=18002
proxy_port=18003
run_stamp="$(date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-glm47-baseline-716/${run_stamp}"
status_file="${log_dir}/status.tsv"
server_pid=""
proxy_pid=""

mkdir -p "${log_dir}"

write_status() {
  printf '%s\t%s\n' "$(date '+%F %T %Z')" "$1" >>"${status_file}"
}

cleanup() {
  local exit_status=$?
  if [[ -n "${proxy_pid}" ]] && kill -0 "${proxy_pid}" 2>/dev/null; then
    kill "${proxy_pid}" 2>/dev/null || true
    wait "${proxy_pid}" 2>/dev/null || true
  fi
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  write_status "job_exit status=${exit_status}"
}
trap cleanup EXIT INT TERM

source "${skills_root}/aistation_env.sh"

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
  write_status "failed api_port_in_use port=${api_port}"
  exit 2
fi
if curl --noproxy '*' --silent --fail --max-time 2 \
  "http://127.0.0.1:${proxy_port}/v1/models" >/dev/null 2>&1; then
  write_status "failed proxy_port_in_use port=${proxy_port}"
  exit 2
fi

write_status "starting_vllm gpu=1 port=${api_port}"
PYTHONPATH="${transformers_overlay}" \
CUDA_VISIBLE_DEVICES=1 \
VLLM_WORKER_MULTIPROC_METHOD=spawn \
VLLM_USE_EXPERIMENTAL_PARSER_CONTEXT=1 \
  "${vllm_env}/bin/vllm" serve "${model_dir}" \
    --served-model-name "${model_id}" \
    --host 0.0.0.0 \
    --port "${api_port}" \
    --tensor-parallel-size 1 \
    --dtype bfloat16 \
    --max-model-len 32768 \
    --max-num-seqs 8 \
    --gpu-memory-utilization 0.80 \
    --enable-auto-tool-choice \
    --tool-call-parser glm47 \
    --reasoning-parser glm45 \
    --language-model-only \
    >"${log_dir}/vllm.log" 2>&1 &
server_pid=$!

ready=0
for _ in $(seq 1 180); do
  if curl --noproxy '*' --silent --fail --max-time 3 \
    "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "${server_pid}" 2>/dev/null; then
    write_status "failed vllm_exited"
    exit 1
  fi
  sleep 5
done
if [[ "${ready}" != 1 ]]; then
  write_status "failed vllm_timeout"
  exit 1
fi
write_status "vllm_ready pid=${server_pid}"

"${vllm_env}/bin/python" "${proxy_script}" \
  --host 0.0.0.0 \
  --port "${proxy_port}" \
  --upstream "http://127.0.0.1:${api_port}" \
  >"${log_dir}/proxy.log" 2>&1 &
proxy_pid=$!

proxy_ready=0
for _ in $(seq 1 30); do
  if curl --noproxy '*' --silent --fail --max-time 3 \
    "http://127.0.0.1:${proxy_port}/v1/models" >/dev/null 2>&1; then
    proxy_ready=1
    break
  fi
  if ! kill -0 "${proxy_pid}" 2>/dev/null; then
    write_status "failed proxy_exited"
    exit 1
  fi
  sleep 2
done
if [[ "${proxy_ready}" != 1 ]]; then
  write_status "failed proxy_timeout"
  exit 1
fi
write_status "proxy_ready pid=${proxy_pid}"

cd "${saber_dir}"
write_status "preflight_start"
SABER_CODEX_CONFIG="${runtime_config}" \
  ./scripts/run/codex_runner.sh run \
    --model "${model_slug}" \
    --skill-mode none \
    --preflight-only \
    A_fs_001 \
    >"${log_dir}/preflight.log" 2>&1
write_status "preflight_complete"

worker_pids=()
worker_labels=()
write_status "baseline_start model=${model_slug} tasks=716 workers=8"
for worker_index in $(seq 0 7); do
  worker_label=$(printf '%02d' "${worker_index}")
  subset_file="${subset_dir}/part-${worker_label}.json"
  if [[ ! -f "${subset_file}" ]]; then
    write_status "failed missing_subset worker=${worker_label}"
    exit 2
  fi
  (
    SABER_CODEX_CONFIG="${runtime_config}" \
      ./scripts/run/codex_runner.sh run \
        --model "${model_slug}" \
        --skill-mode none \
        --skip-preflight \
        --subset "${subset_file}"
  ) >"${log_dir}/worker-${worker_label}.log" 2>&1 &
  worker_pids+=("$!")
  worker_labels+=("${worker_label}")
  write_status "worker_start worker=${worker_label} pid=${worker_pids[-1]}"
done

job_status=0
for index in "${!worker_pids[@]}"; do
  if wait "${worker_pids[$index]}"; then
    write_status "worker_complete worker=${worker_labels[$index]}"
  else
    worker_status=$?
    write_status "worker_failed worker=${worker_labels[$index]} status=${worker_status}"
    job_status=1
  fi
done

result_dir="${saber_dir}/results/${model_slug}_codex-native-none"
result_count=$(find "${result_dir}" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
write_status "baseline_complete status=${job_status} results=${result_count}/716"
exit "${job_status}"
