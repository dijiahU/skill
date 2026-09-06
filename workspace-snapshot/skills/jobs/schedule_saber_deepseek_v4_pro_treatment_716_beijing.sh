#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
job_script="${skills_root}/jobs/run_saber_deepseek_v4_pro_treatment_716.sh"
schedule_log="${skills_root}/logs/saber-deepseek-v4-pro-treatment-716-schedule.log"
schedule_lock="${skills_root}/jobs/.saber-deepseek-v4-pro-treatment-716-schedule.lock"
target_time="${1:-18:05:00}"

exec 8>"${schedule_lock}"
if ! flock -n 8; then
  printf '%s\talready_scheduled\n' "$(TZ=CST-8 date '+%F %T %Z')" >>"${schedule_log}"
  exit 2
fi

now_epoch="$(date +%s)"
target_epoch="$(TZ=CST-8 date -d "$(TZ=CST-8 date +%F) ${target_time}" +%s)"
if (( target_epoch <= now_epoch )); then
  target_epoch="$(TZ=CST-8 date -d "tomorrow ${target_time}" +%s)"
fi
delay_seconds=$((target_epoch - now_epoch))
target_display="$(TZ=CST-8 date -d "@${target_epoch}" '+%F %T %Z')"

printf '%s\tscheduled target=%s delay_seconds=%s\n' \
  "$(TZ=CST-8 date '+%F %T %Z')" \
  "${target_display}" \
  "${delay_seconds}" \
  >>"${schedule_log}"

sleep "${delay_seconds}"

printf '%s\tlaunching job=%s\n' \
  "$(TZ=CST-8 date '+%F %T %Z')" \
  "${job_script}" \
  >>"${schedule_log}"

exec "${job_script}" >>"${schedule_log}" 2>&1
