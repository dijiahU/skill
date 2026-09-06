#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
server_script="${skills_root}/jobs/run_deepseek_v4_flash_0731_h20_judge_server.sh"
judge_runner="${skills_root}/bin/run_saber_parallel_judge_deepseekv4.py"
python_bin="${skills_root}/envs/deepseekv4-vllm/bin/python"
output_root="${saber_dir}/judged_deepseek_v4_flash"
run_stamp="$(TZ=CST-8 date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-deepseek-v4-flash-resume-judge/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-deepseek-v4-flash-resume-judge.lock"
api_port=18020
workers=4
server_pid=""

targets=(
  "codex_mistral_small4_119b_baseline_716_codex-native-none"
  "codex_qwen38_27b_treatment_716_codex-native-safety-orchestrator"
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
  write_status "job_exit status=${exit_status}"
}
trap cleanup EXIT INT TERM

exec 9>"${lock_file}"
if ! flock -n 9; then
  write_status "failed already_running"
  exit 2
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

probe_target="${targets[1]}"
write_status "probe_start target=${probe_target}"
"${python_bin}" "${judge_runner}" --probe "${probe_target}" \
  >"${log_dir}/probe.log" 2>&1
write_status "probe_complete target=${probe_target}"

for target in "${targets[@]}"; do
  raw_dir="${saber_dir}/results/${target}"
  judged_dir="${output_root}/${target}"
  raw_count="$(count_results "${raw_dir}")"
  before_count="$(count_results "${judged_dir}")"
  write_status "judge_start target=${target} raw=${raw_count} existing=${before_count} workers=${workers}"
  "${python_bin}" "${judge_runner}" \
    --workers "${workers}" \
    --max-attempts 3 \
    "${target}" \
    >"${log_dir}/judge-${target}.log" 2>&1
  judged_count="$(count_results "${judged_dir}")"
  write_status "judge_complete target=${target} judged=${judged_count}/${raw_count} summary=${judged_dir}/summary.json"
done

write_status "judge_queue_complete targets=${#targets[@]}"
