#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
runtime_config="${saber_dir}/config.json"
provider_config="${skills_root}/projects/skill/openagentsafety/.llm_config/deepseek-v4-pro.json"
subset_dir="${skills_root}/jobs/saber_glm47_baseline_716_subsets"
model_slug="codex_deepseek_v4_pro"
result_dir="${saber_dir}/results/${model_slug}_codex-native-safety-orchestrator"
run_stamp="$(date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-deepseek-v4-pro-treatment-716/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-deepseek-v4-pro-treatment-716.lock"
worker_pids=()
worker_labels=()

mkdir -p "${log_dir}"

write_status() {
  printf '%s\t%s\n' "$(date '+%F %T %Z')" "$1" >>"${status_file}"
}

cleanup() {
  local exit_status=$?
  for worker_pid in "${worker_pids[@]:-}"; do
    if [[ -n "${worker_pid}" ]] && kill -0 "${worker_pid}" 2>/dev/null; then
      kill "${worker_pid}" 2>/dev/null || true
    fi
  done
  write_status "job_exit status=${exit_status}"
}
trap cleanup EXIT INT TERM

exec 9>"${lock_file}"
if ! flock -n 9; then
  write_status "failed already_running"
  exit 2
fi

source "${skills_root}/aistation_env.sh"

if [[ ! -f "${runtime_config}" ]]; then
  write_status "failed missing_runtime_config"
  exit 2
fi
if [[ ! -f "${provider_config}" ]]; then
  write_status "failed missing_provider_config"
  exit 2
fi
for worker_index in $(seq 0 7); do
  worker_label=$(printf '%02d' "${worker_index}")
  if [[ ! -f "${subset_dir}/part-${worker_label}.json" ]]; then
    write_status "failed missing_subset worker=${worker_label}"
    exit 2
  fi
done

SABER_CODEX_PROVIDER_API_KEY="$(python3 -c '
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle).get("api_key", "")
if not value:
    raise SystemExit("provider API key is empty")
print(value, end="")
' "${provider_config}")"
export SABER_CODEX_PROVIDER_API_KEY

cd "${saber_dir}"
write_status "preflight_start condition=safety-orchestrator"
SABER_CODEX_CONFIG="${runtime_config}" \
  ./scripts/run/codex_runner.sh run \
    --model "${model_slug}" \
    --skill-mode safety-orchestrator \
    --preflight-only \
    A_fs_001 \
    >"${log_dir}/preflight.log" 2>&1
write_status "preflight_complete"

write_status "treatment_start model=${model_slug} tasks=716 workers=8"
for worker_index in $(seq 0 7); do
  worker_label=$(printf '%02d' "${worker_index}")
  subset_file="${subset_dir}/part-${worker_label}.json"
  (
    SABER_CODEX_CONFIG="${runtime_config}" \
      ./scripts/run/codex_runner.sh run \
        --model "${model_slug}" \
        --skill-mode safety-orchestrator \
        --skip-preflight \
        --subset "${subset_file}"
  ) >"${log_dir}/worker-${worker_label}.log" 2>&1 &
  worker_pids+=("$!")
  worker_labels+=("${worker_label}")
  write_status "worker_start worker=${worker_label} pid=${worker_pids[-1]}"
done

job_status=0
for index in "${!worker_pids[@]}"; do
  if wait "${worker_pids[$index]}"; then
    write_status "worker_complete worker=${worker_labels[$index]}"
  else
    worker_status=$?
    write_status "worker_failed worker=${worker_labels[$index]} status=${worker_status}"
    job_status=1
  fi
done

result_count=$(find "${result_dir}" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
write_status "treatment_complete status=${job_status} results=${result_count}/716"
exit "${job_status}"
