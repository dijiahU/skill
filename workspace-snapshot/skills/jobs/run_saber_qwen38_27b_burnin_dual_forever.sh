#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
session_script="${skills_root}/jobs/run_saber_qwen38_27b_treatment_burnin_dual_session.sh"
run_stamp="$(TZ=CST-8 date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-qwen38-27b-burnin-dual-forever/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-qwen38-27b-burnin-forever.lock"
child_pid=""
round=0

mkdir -p "${log_dir}"

write_status() {
  printf '%s\t%s\n' "$(TZ=CST-8 date '+%F %T CST')" "$1" >>"${status_file}"
}

cleanup() {
  local exit_status=$?
  trap - EXIT INT TERM
  if [[ -n "${child_pid}" ]] && kill -0 "${child_pid}" 2>/dev/null; then
    kill -TERM "${child_pid}" 2>/dev/null || true
    wait "${child_pid}" 2>/dev/null || true
  fi
  write_status "supervisor_exit status=${exit_status}"
  exit "${exit_status}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

exec 9>"${lock_file}"
if ! flock -n 9; then
  write_status "failed another_qwen_burnin_is_running"
  exit 2
fi

write_status "supervisor_start mode=dual gpus=0,1 loop=forever results=discarded"
while true; do
  gpu0_used="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0 2>/dev/null | tr -d ' ' || true)"
  gpu1_used="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1 2>/dev/null | tr -d ' ' || true)"
  if [[ "${gpu0_used}" =~ ^[0-9]+$ && "${gpu1_used}" =~ ^[0-9]+$ ]] && (( gpu0_used <= 2048 && gpu1_used <= 2048 )); then
    round=$((round + 1))
    write_status "round_start round=${round} gpu0_used_mib=${gpu0_used} gpu1_used_mib=${gpu1_used}"
    set +e
    "${session_script}" &
    child_pid=$!
    wait "${child_pid}"
    session_status=$?
    child_pid=""
    set -e
    write_status "round_complete round=${round} status=${session_status} results=discarded restart_in_seconds=15"
    sleep 15
  else
    write_status "waiting gpus=0,1 memory_used_mib=${gpu0_used:-unknown},${gpu1_used:-unknown}"
    sleep 30
  fi
done
