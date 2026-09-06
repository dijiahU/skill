#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
run_stamp="$(date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-main-openweight-baseline-queue/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-main-openweight-baseline.lock"

mkdir -p "${log_dir}"
exec 9>"${lock_file}"
if ! flock -n 9; then
  printf '%s\tfailed queue_already_running\n' "$(date '+%F %T %Z')" >>"${status_file}"
  exit 2
fi

write_status() {
  printf '%s\t%s\n' "$(date '+%F %T %Z')" "$1" >>"${status_file}"
}

count_results() {
  local model_slug=$1
  local result_dir="${saber_dir}/results/${model_slug}_codex-native-none"
  if [[ ! -d "${result_dir}" ]]; then
    printf '0\n'
    return
  fi
  find "${result_dir}" -type f -name '*.json' | wc -l | tr -d ' '
}

write_status "queue_start"
write_status "already_complete model=codex_glm47_flash_baseline_716 results=$(count_results codex_glm47_flash_baseline_716)/716"
write_status "already_complete model=codex_gptoss120b_baseline_716 results=$(count_results codex_gptoss120b_baseline_716)/716"
write_status "framework_blocked model=Mistral-Small-4-119B-2603 reason=current_vllm_lacks_working_mistral4_fp8_backend"
write_status "framework_blocked model=DeepSeek-V4-Flash reason=current_vllm_does_not_register_deepseek_v4"

model_slugs=(
  "codex_qwen38_27b_baseline_716"
  "codex_minimax_m25_baseline_716"
)
run_scripts=(
  "${skills_root}/jobs/run_saber_qwen38_27b_baseline_716.sh"
  "${skills_root}/jobs/run_saber_minimax_m25_baseline_716.sh"
)

queue_status=0
for index in "${!model_slugs[@]}"; do
  model_slug=${model_slugs[$index]}
  run_script=${run_scripts[$index]}
  result_count=$(count_results "${model_slug}")
  if [[ "${result_count}" -ge 716 ]]; then
    write_status "model_skip_complete model=${model_slug} results=${result_count}/716"
    continue
  fi
  write_status "model_start model=${model_slug} existing=${result_count}/716 script=${run_script}"
  if "${run_script}"; then
    result_count=$(count_results "${model_slug}")
    write_status "model_complete model=${model_slug} results=${result_count}/716"
  else
    model_status=$?
    result_count=$(count_results "${model_slug}")
    write_status "model_failed model=${model_slug} status=${model_status} results=${result_count}/716"
    queue_status=1
  fi
done

write_status "queue_complete status=${queue_status}"
exit "${queue_status}"
