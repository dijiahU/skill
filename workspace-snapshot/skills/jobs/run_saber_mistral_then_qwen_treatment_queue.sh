#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
deepseek_model_dir="${skills_root}/models/modelscope/deepseek-ai/DeepSeek-V4-Flash-0731"
deepseek_vllm="${skills_root}/envs/deepseekv4-vllm/bin/vllm"
mistral_script="${skills_root}/jobs/run_saber_mistral_small4_119b_baseline_716.sh"
qwen_script="${skills_root}/jobs/run_saber_qwen38_27b_treatment_716.sh"
run_stamp="$(date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-mistral-qwen-treatment-queue/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-mistral-qwen-treatment-queue.lock"
active_child=""

mkdir -p "${log_dir}"

write_status() {
  printf '%s\t%s\n' "$(date '+%F %T %Z')" "$1" >>"${status_file}"
}

cleanup() {
  local exit_status=$?
  if [[ -n "${active_child}" ]] && kill -0 "${active_child}" 2>/dev/null; then
    kill "${active_child}" 2>/dev/null || true
    wait "${active_child}" 2>/dev/null || true
  fi
  write_status "queue_exit status=${exit_status}"
}
trap cleanup EXIT INT TERM

exec 9>"${lock_file}"
if ! flock -n 9; then
  write_status "failed queue_already_running"
  exit 2
fi

source "${skills_root}/aistation_env.sh"

count_results() {
  local result_dir=$1
  if [[ ! -d "${result_dir}" ]]; then
    printf '0\n'
    return
  fi
  find "${result_dir}" -type f -name '*.json' | wc -l | tr -d ' '
}

deepseek_result_dir="${saber_dir}/results/codex_deepseek_v4_flash_local_baseline_716_codex-native-none"
write_status "queue_start order=deepseek-finish,mistral-baseline,qwen-treatment"
write_status "waiting_for_deepseek baseline=$(count_results "${deepseek_result_dir}")/716"
wait_round=0
while pgrep -f '[r]un_saber_deepseek_v4_flash_local_baseline_716.sh' >/dev/null 2>&1; do
  sleep 30
  wait_round=$((wait_round + 1))
  if (( wait_round % 20 == 0 )); then
    write_status "waiting_for_deepseek baseline=$(count_results "${deepseek_result_dir}")/716"
  fi
done
write_status "deepseek_job_finished baseline=$(count_results "${deepseek_result_dir}")/716"

for _ in $(seq 1 20); do
  if ! pgrep -f '[c]odex_deepseek_v4_flash_local_baseline_716' >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
if pgrep -f '[c]odex_deepseek_v4_flash_local_baseline_716' >/dev/null 2>&1; then
  write_status "failed deepseek_workers_still_running"
  exit 1
fi

mapfile -t deepseek_pids < <(
  pgrep -f "${deepseek_vllm} serve ${deepseek_model_dir}" || true
)
if (( ${#deepseek_pids[@]} > 0 )); then
  write_status "stopping_deepseek_server pids=${deepseek_pids[*]}"
  kill -TERM "${deepseek_pids[@]}"
fi
for _ in $(seq 1 120); do
  if ! curl --noproxy '*' --silent --fail --max-time 2 \
    "http://127.0.0.1:18020/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
if curl --noproxy '*' --silent --fail --max-time 2 \
  "http://127.0.0.1:18020/health" >/dev/null 2>&1; then
  write_status "failed deepseek_server_did_not_stop"
  exit 1
fi
write_status "deepseek_server_stopped"

queue_status=0

mistral_result_dir="${saber_dir}/results/codex_mistral_small4_119b_baseline_716_codex-native-none"
mistral_count=$(count_results "${mistral_result_dir}")
if [[ "${mistral_count}" -ge 716 ]]; then
  write_status "job_skip_complete job=mistral-baseline results=${mistral_count}/716"
else
  write_status "job_start job=mistral-baseline existing=${mistral_count}/716"
  "${mistral_script}" >>"${log_dir}/mistral-baseline.log" 2>&1 &
  active_child=$!
  if wait "${active_child}"; then
    active_child=""
    write_status "job_complete job=mistral-baseline results=$(count_results "${mistral_result_dir}")/716"
  else
    child_status=$?
    active_child=""
    write_status "job_failed job=mistral-baseline status=${child_status} results=$(count_results "${mistral_result_dir}")/716"
    queue_status=1
  fi
fi

qwen_result_dir="${saber_dir}/results/codex_qwen38_27b_treatment_716_codex-native-safety-orchestrator"
qwen_count=$(count_results "${qwen_result_dir}")
if [[ "${qwen_count}" -ge 716 ]]; then
  write_status "job_skip_complete job=qwen-treatment results=${qwen_count}/716"
else
  write_status "job_start job=qwen-treatment existing=${qwen_count}/716"
  "${qwen_script}" >>"${log_dir}/qwen-treatment.log" 2>&1 &
  active_child=$!
  if wait "${active_child}"; then
    active_child=""
    write_status "job_complete job=qwen-treatment results=$(count_results "${qwen_result_dir}")/716"
  else
    child_status=$?
    active_child=""
    write_status "job_failed job=qwen-treatment status=${child_status} results=$(count_results "${qwen_result_dir}")/716"
    queue_status=1
  fi
fi

write_status "queue_complete status=${queue_status}"
exit "${queue_status}"
