#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
judge_pid="${DEEPSEEK_JUDGE_JOB_PID:-662890}"
run_stamp="$(TZ=CST-8 date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-openweight-treatment-queue/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-openweight-treatment-queue.lock"
active_child=""

model_slugs=(
  "codex_deepseek_v4_flash_local_treatment_716"
  "codex_mistral_small4_119b_treatment_716"
  "codex_gptoss120b_treatment_716"
  "codex_minimax_m25_treatment_716"
)
run_scripts=(
  "${skills_root}/jobs/run_saber_deepseek_v4_flash_local_treatment_716.sh"
  "${skills_root}/jobs/run_saber_mistral_small4_119b_treatment_716.sh"
  "${skills_root}/jobs/run_saber_gptoss120b_treatment_716.sh"
  "${skills_root}/jobs/run_saber_minimax_m25_treatment_716.sh"
)

mkdir -p "${log_dir}"

write_status() {
  printf '%s\t%s\n' "$(TZ=CST-8 date '+%F %T %Z')" "$1" >>"${status_file}"
}

count_results() {
  local model_slug=$1
  local result_dir="${saber_dir}/results/${model_slug}_codex-native-safety-orchestrator"
  if [[ ! -d "${result_dir}" ]]; then
    printf '0\n'
    return
  fi
  find "${result_dir}" -type f -name '*.json' | wc -l | tr -d ' '
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

write_status "queue_submitted order=deepseek,mistral,gptoss,minimax wait_for_judge_pid=${judge_pid}"
wait_round=0
while kill -0 "${judge_pid}" 2>/dev/null; do
  judge_cmd="$(tr '\0' ' ' <"/proc/${judge_pid}/cmdline" 2>/dev/null || true)"
  if [[ "${judge_cmd}" != *"run_saber_deepseek_v4_flash_resume_judge.sh"* ]]; then
    write_status "judge_pid_identity_changed pid=${judge_pid}"
    break
  fi
  sleep 30
  wait_round=$((wait_round + 1))
  if (( wait_round % 10 == 0 )); then
    write_status "waiting_for_judge pid=${judge_pid}"
  fi
done
write_status "judge_finished starting_treatment_queue"

queue_status=0
for index in "${!model_slugs[@]}"; do
  model_slug="${model_slugs[$index]}"
  run_script="${run_scripts[$index]}"
  result_count="$(count_results "${model_slug}")"
  if [[ "${result_count}" -ge 716 ]]; then
    write_status "model_skip_complete model=${model_slug} results=${result_count}/716"
    continue
  fi
  write_status "model_start model=${model_slug} existing=${result_count}/716 script=${run_script}"
  "${run_script}" >>"${log_dir}/${model_slug}.log" 2>&1 &
  active_child=$!
  if wait "${active_child}"; then
    active_child=""
    result_count="$(count_results "${model_slug}")"
    write_status "model_complete model=${model_slug} results=${result_count}/716"
  else
    child_status=$?
    active_child=""
    result_count="$(count_results "${model_slug}")"
    write_status "model_failed model=${model_slug} status=${child_status} results=${result_count}/716"
    queue_status=1
  fi
done

write_status "queue_complete status=${queue_status}"
exit "${queue_status}"
