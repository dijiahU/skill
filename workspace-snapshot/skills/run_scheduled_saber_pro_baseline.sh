#!/usr/bin/env bash
set -uo pipefail

start_epoch=1788170400  # 2026-08-31 10:00:00 UTC / 18:00:00 Asia/Shanghai
saber_dir="/2024233123/skills/projects/skill/saber"
log_dir="/2024233123/skills/logs/saber-pro-baseline-20260831"
model="codex_deepseek_v4_pro"

if [[ -z "${SABER_CODEX_PROVIDER_API_KEY:-}" ]]; then
  echo "$(date -u '+%F %T UTC') missing SABER_CODEX_PROVIDER_API_KEY" >&2
  exit 2
fi

mkdir -p "${log_dir}"
echo "$(date -u '+%F %T UTC') scheduler started; target=2026-08-31 10:00:00 UTC"

while (( $(date -u +%s) < start_epoch )); do
  remaining=$((start_epoch - $(date -u +%s)))
  if (( remaining > 60 )); then
    sleep 60
  else
    sleep "${remaining}"
  fi
done

source /2024233123/skills/aistation_env.sh
cd "${saber_dir}"

echo "$(date -u '+%F %T UTC') starting ${model} baseline with A/B/C workers"

pids=()
scenarios=(A B C)
for scenario in "${scenarios[@]}"; do
  (
    ./scripts/run/codex_runner.sh run \
      --model "${model}" \
      --skill-mode none \
      "${scenario}"
  ) >"${log_dir}/${scenario}.log" 2>&1 &
  pids+=("$!")
  echo "$(date -u '+%F %T UTC') scenario=${scenario} pid=${pids[-1]}"
done

status=0
for index in "${!pids[@]}"; do
  if wait "${pids[$index]}"; then
    echo "$(date -u '+%F %T UTC') scenario=${scenarios[$index]} completed"
  else
    worker_status=$?
    echo "$(date -u '+%F %T UTC') scenario=${scenarios[$index]} failed status=${worker_status}" >&2
    status=1
  fi
done

result_dir="results/${model}_codex-native-none"
result_count=$(find "${result_dir}" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
echo "$(date -u '+%F %T UTC') baseline finished status=${status} results=${result_count}/716"
exit "${status}"
