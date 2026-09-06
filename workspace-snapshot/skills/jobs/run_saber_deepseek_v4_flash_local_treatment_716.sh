#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
server_script="${skills_root}/jobs/run_deepseek_v4_flash_0731_h20_judge_server.sh"
runtime_config="${skills_root}/jobs/saber_deepseek_v4_flash_local_treatment_716.json"
subset_dir="${skills_root}/jobs/saber_glm47_baseline_716_subsets"
validator="${skills_root}/bin/validate_saber_treatment_smoke.py"
python_bin="${skills_root}/envs/deepseekv4-vllm/bin/python"
model_slug="codex_deepseek_v4_flash_local_treatment_716"
api_port=18020
run_stamp="$(TZ=CST-8 date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-deepseek-v4-flash-local-treatment-716/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-deepseek-v4-flash-local-treatment-716.lock"
result_dir="${saber_dir}/results/${model_slug}_codex-native-safety-orchestrator"
smoke_result="${result_dir}/A/fs_destruction/A_fs_001.json"
server_pid=""
worker_pids=()
worker_labels=()

mkdir -p "${log_dir}"

write_status() {
  printf '%s\t%s\n' "$(TZ=CST-8 date '+%F %T %Z')" "$1" >>"${status_file}"
}

cleanup() {
  local exit_status=$?
  for worker_pid in "${worker_pids[@]:-}"; do
    if [[ -n "${worker_pid}" ]] && kill -0 "${worker_pid}" 2>/dev/null; then
      kill "${worker_pid}" 2>/dev/null || true
    fi
  done
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  write_status "job_exit status=${exit_status}"
}
trap cleanup EXIT INT TERM

exec 9>"${lock_file}"
if ! flock -n 9; then
  write_status "failed already_running"
  exit 2
fi

source "${skills_root}/aistation_env.sh"

for required_file in "${server_script}" "${runtime_config}" "${validator}"; do
  if [[ ! -f "${required_file}" ]]; then
    write_status "failed missing_file path=${required_file}"
    exit 2
  fi
done
for worker_index in $(seq 0 7); do
  worker_label=$(printf '%02d' "${worker_index}")
  if [[ ! -f "${subset_dir}/part-${worker_label}.json" ]]; then
    write_status "failed missing_subset worker=${worker_label}"
    exit 2
  fi
done
if curl --noproxy '*' --silent --fail --max-time 2 \
  "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then
  write_status "failed api_port_in_use port=${api_port}"
  exit 2
fi

write_status "starting_vllm gpus=0,1 dp=2 port=${api_port}"
"${server_script}" >"${log_dir}/server-launcher.log" 2>&1 &
server_pid=$!

ready=0
for _ in $(seq 1 360); do
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

cd "${saber_dir}"
write_status "preflight_start condition=safety-orchestrator"
SABER_CODEX_CONFIG="${runtime_config}" \
  ./scripts/run/codex_runner.sh run \
    --model "${model_slug}" \
    --skill-mode safety-orchestrator \
    --preflight-only \
    A_fs_001 \
    >"${log_dir}/preflight.log" 2>&1
write_status "preflight_complete"

write_status "smoke_start task=A_fs_001"
SABER_CODEX_CONFIG="${runtime_config}" \
  ./scripts/run/codex_runner.sh run \
    --model "${model_slug}" \
    --skill-mode safety-orchestrator \
    --skip-preflight \
    --overwrite \
    --trace \
    A_fs_001 \
    >"${log_dir}/smoke.log" 2>&1
"${python_bin}" "${validator}" "${smoke_result}" \
  >"${log_dir}/smoke-validation.json"
write_status "smoke_complete validation=${log_dir}/smoke-validation.json"

write_status "treatment_start model=${model_slug} tasks=716 workers=8 replicas=2"
for worker_index in $(seq 0 7); do
  worker_label=$(printf '%02d' "${worker_index}")
  subset_file="${subset_dir}/part-${worker_label}.json"
  (
    SABER_CODEX_CONFIG="${runtime_config}" \
      ./scripts/run/codex_runner.sh run \
        --model "${model_slug}" \
        --skill-mode safety-orchestrator \
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

result_count=$(find "${result_dir}" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
write_status "treatment_complete status=${job_status} results=${result_count}/716"
exit "${job_status}"
