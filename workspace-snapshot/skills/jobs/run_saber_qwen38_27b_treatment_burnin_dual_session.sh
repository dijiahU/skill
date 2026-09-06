#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
model_dir="${skills_root}/models/modelscope/Qwen/Qwen3.8-27B-FP8"
vllm_env="${skills_root}/envs/qwen35-vllm"
proxy_script="${skills_root}/bin/vllm_responses_compat_proxy.py"
runtime_config_gpu0="${skills_root}/jobs/saber_qwen38_27b_treatment_716.json"
runtime_config_gpu1="${skills_root}/jobs/saber_qwen38_27b_treatment_716_gpu1.json"
subset_dir="${skills_root}/jobs/saber_glm47_baseline_716_subsets"
model_id="Qwen/Qwen3.8-27B-FP8"
model_slug="codex_qwen38_27b_treatment_716"
api_port_gpu0=18010
proxy_port_gpu0=18011
api_port_gpu1=18012
proxy_port_gpu1=18013
run_stamp="$(date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-qwen38-27b-treatment-burnin-dual/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-qwen38-27b-treatment-716.lock"
result_dir="${saber_dir}/results/${model_slug}_codex-native-safety-orchestrator"
smoke_result="${result_dir}/A/fs_destruction/A_fs_001.json"
server_pid_gpu0=""
server_pid_gpu1=""
proxy_pid_gpu0=""
proxy_pid_gpu1=""
worker_pids=()
worker_labels=()

mkdir -p "${log_dir}"

write_status() {
  printf '%s\t%s\n' "$(date '+%F %T %Z')" "$1" >>"${status_file}"
}

cleanup() {
  local exit_status=$?
  for worker_pid in "${worker_pids[@]:-}"; do
    if [[ -n "${worker_pid}" ]] && kill -0 "${worker_pid}" 2>/dev/null; then
      kill "${worker_pid}" 2>/dev/null || true
    fi
  done
  for proxy_pid in "${proxy_pid_gpu0}" "${proxy_pid_gpu1}"; do
    if [[ -n "${proxy_pid}" ]] && kill -0 "${proxy_pid}" 2>/dev/null; then
      kill "${proxy_pid}" 2>/dev/null || true
      wait "${proxy_pid}" 2>/dev/null || true
    fi
  done
  for server_pid in "${server_pid_gpu0}" "${server_pid_gpu1}"; do
    if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
      kill "${server_pid}" 2>/dev/null || true
      wait "${server_pid}" 2>/dev/null || true
    fi
  done
  write_status "job_exit status=${exit_status}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

exec 9>"${lock_file}"
if ! flock -n 9; then
  write_status "failed already_running"
  exit 2
fi

source "${skills_root}/aistation_env.sh"
export PATH="${vllm_env}/bin:${PATH}"
export SABER_DISCARD_RESULTS=1

if [[ ! -x "${vllm_env}/bin/vllm" ]]; then
  write_status "failed missing_vllm"
  exit 2
fi
if [[ ! -f "${model_dir}/model.safetensors.index.json" ]] || \
  [[ ! -f "${model_dir}/layers-63.safetensors" ]]; then
  write_status "failed incomplete_model"
  exit 2
fi
for worker_index in $(seq 0 7); do
  worker_label=$(printf '%02d' "${worker_index}")
  if [[ ! -f "${subset_dir}/part-${worker_label}.json" ]]; then
    write_status "failed missing_subset worker=${worker_label}"
    exit 2
  fi
done
for port in \
  "${api_port_gpu0}" "${proxy_port_gpu0}" \
  "${api_port_gpu1}" "${proxy_port_gpu1}"; do
  if curl --noproxy '*' --silent --fail --max-time 2 \
    "http://127.0.0.1:${port}/health" >/dev/null 2>&1 || \
    curl --noproxy '*' --silent --fail --max-time 2 \
    "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; then
    write_status "failed port_in_use port=${port}"
    exit 2
  fi
done

write_status "starting_vllm gpu=0 port=${api_port_gpu0}"
CUDA_VISIBLE_DEVICES=0 \
SAFETENSORS_FAST_GPU=1 \
VLLM_WORKER_MULTIPROC_METHOD=spawn \
VLLM_NO_USAGE_STATS=1 \
VLLM_FORCE_NATIVE_GDN=1 \
  "${vllm_env}/bin/vllm" serve "${model_dir}" \
    --served-model-name "${model_id}" \
    --host 0.0.0.0 \
    --port "${api_port_gpu0}" \
    --tensor-parallel-size 1 \
    --max-model-len 32768 \
    --max-num-seqs 4 \
    --gpu-memory-utilization 0.80 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_xml \
    --reasoning-parser qwen3 \
    --language-model-only \
    >"${log_dir}/vllm-gpu0.log" 2>&1 &
server_pid_gpu0=$!

write_status "starting_vllm gpu=1 port=${api_port_gpu1}"
CUDA_VISIBLE_DEVICES=1 \
SAFETENSORS_FAST_GPU=1 \
VLLM_WORKER_MULTIPROC_METHOD=spawn \
VLLM_NO_USAGE_STATS=1 \
VLLM_FORCE_NATIVE_GDN=1 \
  "${vllm_env}/bin/vllm" serve "${model_dir}" \
    --served-model-name "${model_id}" \
    --host 0.0.0.0 \
    --port "${api_port_gpu1}" \
    --tensor-parallel-size 1 \
    --max-model-len 32768 \
    --max-num-seqs 4 \
    --gpu-memory-utilization 0.80 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_xml \
    --reasoning-parser qwen3 \
    --language-model-only \
    >"${log_dir}/vllm-gpu1.log" 2>&1 &
server_pid_gpu1=$!

ready=0
for _ in $(seq 1 180); do
  gpu0_ready=0
  gpu1_ready=0
  curl --noproxy '*' --silent --fail --max-time 3 \
    "http://127.0.0.1:${api_port_gpu0}/health" >/dev/null 2>&1 && gpu0_ready=1
  curl --noproxy '*' --silent --fail --max-time 3 \
    "http://127.0.0.1:${api_port_gpu1}/health" >/dev/null 2>&1 && gpu1_ready=1
  if [[ "${gpu0_ready}" == 1 && "${gpu1_ready}" == 1 ]]; then
    ready=1
    break
  fi
  if ! kill -0 "${server_pid_gpu0}" 2>/dev/null || \
    ! kill -0 "${server_pid_gpu1}" 2>/dev/null; then
    write_status "failed vllm_replica_exited gpu0_pid=${server_pid_gpu0} gpu1_pid=${server_pid_gpu1}"
    exit 1
  fi
  sleep 5
done
if [[ "${ready}" != 1 ]]; then
  write_status "failed vllm_timeout"
  exit 1
fi
write_status "vllm_ready gpu0_pid=${server_pid_gpu0} gpu1_pid=${server_pid_gpu1}"

"${vllm_env}/bin/python" "${proxy_script}" \
  --host 0.0.0.0 \
  --port "${proxy_port_gpu0}" \
  --upstream "http://127.0.0.1:${api_port_gpu0}" \
  --emulate-stream \
  --temperature 0 \
  >"${log_dir}/proxy-gpu0.log" 2>&1 &
proxy_pid_gpu0=$!

"${vllm_env}/bin/python" "${proxy_script}" \
  --host 0.0.0.0 \
  --port "${proxy_port_gpu1}" \
  --upstream "http://127.0.0.1:${api_port_gpu1}" \
  --emulate-stream \
  --temperature 0 \
  >"${log_dir}/proxy-gpu1.log" 2>&1 &
proxy_pid_gpu1=$!

proxy_ready=0
for _ in $(seq 1 30); do
  gpu0_ready=0
  gpu1_ready=0
  curl --noproxy '*' --silent --fail --max-time 3 \
    "http://127.0.0.1:${proxy_port_gpu0}/v1/models" >/dev/null 2>&1 && gpu0_ready=1
  curl --noproxy '*' --silent --fail --max-time 3 \
    "http://127.0.0.1:${proxy_port_gpu1}/v1/models" >/dev/null 2>&1 && gpu1_ready=1
  if [[ "${gpu0_ready}" == 1 && "${gpu1_ready}" == 1 ]]; then
    proxy_ready=1
    break
  fi
  if ! kill -0 "${proxy_pid_gpu0}" 2>/dev/null || \
    ! kill -0 "${proxy_pid_gpu1}" 2>/dev/null; then
    write_status "failed proxy_replica_exited gpu0_pid=${proxy_pid_gpu0} gpu1_pid=${proxy_pid_gpu1}"
    exit 1
  fi
  sleep 2
done
if [[ "${proxy_ready}" != 1 ]]; then
  write_status "failed proxy_timeout"
  exit 1
fi
write_status "proxy_ready gpu0_pid=${proxy_pid_gpu0} gpu1_pid=${proxy_pid_gpu1}"

cd "${saber_dir}"
write_status "preflight_start condition=safety-orchestrator"
SABER_CODEX_CONFIG="${runtime_config_gpu0}" \
  ./scripts/run/codex_runner.sh run \
    --model "${model_slug}" \
    --skill-mode safety-orchestrator \
    --preflight-only \
    A_fs_001 \
    >"${log_dir}/preflight.log" 2>&1
write_status "preflight_complete"

write_status "smoke_start task=A_fs_001"
SABER_CODEX_CONFIG="${runtime_config_gpu0}" \
  ./scripts/run/codex_runner.sh run \
    --model "${model_slug}" \
    --skill-mode safety-orchestrator \
    --skip-preflight \
    --trace \
    A_fs_001 \
    >"${log_dir}/smoke.log" 2>&1

write_status "smoke_complete results=discarded"

write_status "treatment_start model=${model_slug} tasks=716 workers=8 replicas=2 workers_per_replica=4 results=discarded"
for worker_index in $(seq 0 7); do
  worker_label=$(printf '%02d' "${worker_index}")
  subset_file="${subset_dir}/part-${worker_label}.json"
  if [[ "${worker_index}" -lt 4 ]]; then
    runtime_config="${runtime_config_gpu0}"
    replica_gpu=0
  else
    runtime_config="${runtime_config_gpu1}"
    replica_gpu=1
  fi
  (
    SABER_CODEX_CONFIG="${runtime_config}" \
      ./scripts/run/codex_runner.sh run \
        --model "${model_slug}" \
        --skill-mode safety-orchestrator \
        --skip-preflight \
        --subset "${subset_file}"
  ) >/dev/null 2>&1 &
  worker_pids+=("$!")
  worker_labels+=("${worker_label}")
  write_status "worker_start worker=${worker_label} gpu=${replica_gpu} pid=${worker_pids[-1]}"
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

write_status "treatment_complete status=${job_status} results=discarded"
exit "${job_status}"
