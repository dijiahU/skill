#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
qwen_script="${skills_root}/jobs/run_saber_qwen38_27b_treatment_716.sh"
qwen_result_dir="${saber_dir}/results/codex_qwen38_27b_treatment_716_codex-native-safety-orchestrator"
judge_queue_pid="${DEEPSEEK_JUDGE_QUEUE_PID:-644536}"
deepseek_server_pid="${DEEPSEEK_JUDGE_SERVER_PID:-643766}"
run_stamp="$(date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-deepseek-judge-qwen-treatment-queue/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-deepseek-judge-qwen-treatment-queue.lock"
active_child=""

mkdir -p "${log_dir}"

write_status() {
  printf '%s\t%s\n' "$(date '+%F %T %Z')" "$1" >>"${status_file}"
}

count_qwen_results() {
  if [[ ! -d "${qwen_result_dir}" ]]; then
    printf '0\n'
    return
  fi
  find "${qwen_result_dir}" -type f -name '*.json' | wc -l | tr -d ' '
}

cleanup() {
  local exit_status=$?
  if [[ -n "${active_child}" ]] && kill -0 "${active_child}" 2>/dev/null; then
    kill "${active_child}" 2>/dev/null || true
    wait "${active_child}" 2>/dev/null || true
  fi
  write_status "queue_exit status=${exit_status} qwen=$(count_qwen_results)/716"
}
trap cleanup EXIT INT TERM

exec 9>"${lock_file}"
if ! flock -n 9; then
  write_status "failed queue_already_running"
  exit 2
fi

write_status "queued wait_for_deepseek_judge judge_pid=${judge_queue_pid} server_pid=${deepseek_server_pid} qwen=$(count_qwen_results)/716"
wait_round=0
while kill -0 "${judge_queue_pid}" 2>/dev/null; do
  sleep 30
  wait_round=$((wait_round + 1))
  if (( wait_round % 10 == 0 )); then
    write_status "waiting_for_deepseek_judge qwen=$(count_qwen_results)/716"
  fi
done
write_status "deepseek_judge_finished"

if kill -0 "${deepseek_server_pid}" 2>/dev/null; then
  server_cmd="$(tr '\0' ' ' <"/proc/${deepseek_server_pid}/cmdline")"
  server_pgid="$(ps -o pgid= -p "${deepseek_server_pid}" | tr -d ' ')"
  if [[ "${server_cmd}" != *"DeepSeek-V4-Flash-0731"* ]] || \
    [[ "${server_pgid}" != "${deepseek_server_pid}" ]]; then
    write_status "failed unexpected_deepseek_server_identity pid=${deepseek_server_pid} pgid=${server_pgid}"
    exit 1
  fi
  write_status "stopping_project_deepseek_server pid=${deepseek_server_pid} pgid=${server_pgid}"
  kill -TERM -- "-${server_pgid}"
fi

for _ in $(seq 1 120); do
  if ! kill -0 "${deepseek_server_pid}" 2>/dev/null && \
    ! curl --noproxy '*' --silent --fail --max-time 2 \
      "http://127.0.0.1:18020/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
if kill -0 "${deepseek_server_pid}" 2>/dev/null || \
  curl --noproxy '*' --silent --fail --max-time 2 \
    "http://127.0.0.1:18020/health" >/dev/null 2>&1; then
  write_status "failed deepseek_server_did_not_stop"
  exit 1
fi
write_status "deepseek_server_stopped"

qwen_count="$(count_qwen_results)"
if [[ "${qwen_count}" -ge 716 ]]; then
  write_status "qwen_skip_complete results=${qwen_count}/716"
  exit 0
fi

write_status "qwen_resume_start existing=${qwen_count}/716"
"${qwen_script}" >>"${log_dir}/qwen-treatment.log" 2>&1 &
active_child=$!
if wait "${active_child}"; then
  active_child=""
  write_status "qwen_resume_complete results=$(count_qwen_results)/716"
else
  child_status=$?
  active_child=""
  write_status "qwen_resume_failed status=${child_status} results=$(count_qwen_results)/716"
  exit "${child_status}"
fi
