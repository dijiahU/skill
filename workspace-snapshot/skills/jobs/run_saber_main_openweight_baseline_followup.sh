#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
queue_script="${skills_root}/jobs/run_saber_main_openweight_baseline_queue.sh"
queue_lock="${skills_root}/jobs/.saber-main-openweight-baseline.lock"
followup_lock="${skills_root}/jobs/.saber-main-openweight-baseline-followup.lock"
run_stamp="$(date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-main-openweight-baseline-followup/${run_stamp}"
status_file="${log_dir}/status.tsv"

mkdir -p "${log_dir}"
exec 9<>"${followup_lock}"
if ! flock -n 9; then
  printf '%s\tfailed followup_already_waiting\n' "$(date '+%F %T %Z')" >>"${status_file}"
  exit 2
fi

printf '%s\twaiting_for_active_queue\n' "$(date '+%F %T %Z')" >>"${status_file}"
exec 8<>"${queue_lock}"
flock 8
flock -u 8
printf '%s\tactive_queue_finished launching_resume_queue\n' "$(date '+%F %T %Z')" >>"${status_file}"
exec "${queue_script}"
