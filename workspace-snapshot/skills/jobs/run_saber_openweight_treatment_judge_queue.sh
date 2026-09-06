#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
server_script="${skills_root}/jobs/run_deepseek_v4_flash_0731_h20_judge_server.sh"
judge_runner="${skills_root}/bin/run_saber_parallel_judge_deepseekv4.py"
python_bin="${skills_root}/envs/deepseekv4-vllm/bin/python"
output_root="${saber_dir}/judged_deepseek_v4_flash"
treatment_queue_pid="${TREATMENT_QUEUE_PID:-668347}"
run_stamp="$(TZ=CST-8 date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-openweight-treatment-judge-queue/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-openweight-treatment-judge-queue.lock"
api_port=18020
workers=2
server_pid=""

targets=(
  "codex_deepseek_v4_flash_local_treatment_716_codex-native-safety-orchestrator"
  "codex_mistral_small4_119b_treatment_716_codex-native-safety-orchestrator"
  "codex_gptoss120b_treatment_716_codex-native-safety-orchestrator"
  "codex_minimax_m25_treatment_716_codex-native-safety-orchestrator"
)

mkdir -p "${log_dir}"

write_status() {
  printf '%s\t%s\n' "$(TZ=CST-8 date '+%F %T %Z')" "$1" >>"${status_file}"
}

count_results() {
  local directory=$1
  if [[ ! -d "${directory}" ]]; then
    printf '0\n'
    return
  fi
  find "${directory}" -type f -name '*.json' ! -name summary.json \
    | wc -l | tr -d ' '
}

cleanup() {
  local exit_status=$?
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  write_status "judge_queue_exit status=${exit_status}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

exec 9>"${lock_file}"
if ! flock -n 9; then
  write_status "failed judge_queue_already_running"
  exit 2
fi

write_status "judge_queue_submitted order=deepseek,mistral,gptoss,minimax wait_for_treatment_pid=${treatment_queue_pid}"
wait_round=0
while kill -0 "${treatment_queue_pid}" 2>/dev/null; do
  queue_cmd="$(tr '\0' ' ' <"/proc/${treatment_queue_pid}/cmdline" 2>/dev/null || true)"
  if [[ "${queue_cmd}" != *"run_saber_openweight_treatment_queue.sh"* ]]; then
    write_status "treatment_pid_identity_changed pid=${treatment_queue_pid}"
    break
  fi
  sleep 30
  wait_round=$((wait_round + 1))
  if (( wait_round % 10 == 0 )); then
    write_status "waiting_for_treatments pid=${treatment_queue_pid}"
  fi
done
write_status "treatment_queue_finished preparing_judge"

probe_target=""
for target in "${targets[@]}"; do
  raw_dir="${saber_dir}/results/${target}"
  raw_count="$(count_results "${raw_dir}")"
  if [[ "${raw_count}" -gt 0 ]]; then
    probe_target="${target}"
    break
  fi
done
if [[ -z "${probe_target}" ]]; then
  write_status "failed no_treatment_results"
  exit 1
fi

if curl --noproxy '*' --silent --fail --max-time 2 \
  "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then
  write_status "failed api_port_in_use port=${api_port}"
  exit 2
fi

write_status "server_start port=${api_port} workers=${workers}"
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
    write_status "failed server_exited"
    exit 1
  fi
  sleep 5
done
if [[ "${ready}" != 1 ]]; then
  write_status "failed server_timeout"
  exit 1
fi
write_status "server_ready pid=${server_pid}"

write_status "probe_start target=${probe_target}"
"${python_bin}" "${judge_runner}" --probe "${probe_target}" \
  >"${log_dir}/probe.log" 2>&1
write_status "probe_complete target=${probe_target}"

judge_status=0
for target in "${targets[@]}"; do
  raw_dir="${saber_dir}/results/${target}"
  judged_dir="${output_root}/${target}"
  raw_count="$(count_results "${raw_dir}")"
  before_count="$(count_results "${judged_dir}")"
  if [[ "${raw_count}" -eq 0 ]]; then
    write_status "judge_skip_no_raw target=${target}"
    judge_status=1
    continue
  fi
  write_status "judge_start target=${target} raw=${raw_count} existing=${before_count} workers=${workers}"
  if "${python_bin}" "${judge_runner}" \
    --workers "${workers}" \
    --max-attempts 3 \
    "${target}" \
    >"${log_dir}/judge-${target}.log" 2>&1; then
    judged_count="$(count_results "${judged_dir}")"
    write_status "judge_complete target=${target} judged=${judged_count}/${raw_count} summary=${judged_dir}/summary.json"
  else
    run_status=$?
    judged_count="$(count_results "${judged_dir}")"
    write_status "judge_failed target=${target} status=${run_status} judged=${judged_count}/${raw_count}"
    judge_status=1
  fi
done

write_status "judge_queue_complete status=${judge_status} targets=${#targets[@]}"
exit "${judge_status}"
