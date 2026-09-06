#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
baseline_result_dir="${saber_dir}/results/codex_minimax_m25_baseline_716_codex-native-none"
baseline_queue_script="${skills_root}/jobs/run_saber_main_openweight_baseline_queue.sh"
judge_script="${skills_root}/jobs/run_saber_gptoss120b_judge_4models.sh"
run_stamp="$(date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-gptoss120b-judge-watcher/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-gptoss120b-judge-watcher.lock"

mkdir -p "${log_dir}"
exec 9>"${lock_file}"
if ! flock -n 9; then
  printf '%s\tfailed watcher_already_running\n' "$(date '+%F %T %Z')" >>"${status_file}"
  exit 2
fi

write_status() {
  printf '%s\t%s\n' "$(date '+%F %T %Z')" "$1" >>"${status_file}"
}

count_results() {
  find "${baseline_result_dir}" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' '
}

write_status "watcher_start waiting_for=codex_minimax_m25_baseline_716 results=$(count_results)/716"
polls=0
while [[ "$(count_results)" -lt 716 ]]; do
  if ! pgrep -f "^bash ${baseline_queue_script}$" >/dev/null 2>&1; then
    write_status "failed baseline_queue_exited_early results=$(count_results)/716"
    exit 1
  fi
  polls=$((polls + 1))
  if (( polls % 20 == 0 )); then
    write_status "waiting baseline_results=$(count_results)/716"
  fi
  sleep 30
done
write_status "baseline_results_complete results=$(count_results)/716"

while pgrep -f "^bash ${baseline_queue_script}$" >/dev/null 2>&1; do
  sleep 10
done
while curl --noproxy '*' --silent --fail --max-time 2 \
  "http://127.0.0.1:18006/health" >/dev/null 2>&1; do
  sleep 10
done

write_status "launching_judge script=${judge_script} judge_gpu=0 gpu1_reserved_free=true"
if "${judge_script}"; then
  write_status "watcher_complete status=0"
else
  judge_status=$?
  write_status "watcher_failed judge_status=${judge_status}"
  exit "${judge_status}"
fi
