#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
judge_runner="${skills_root}/bin/run_saber_parallel_judge_deepseekv4.py"
python_bin="${skills_root}/envs/deepseekv4-vllm/bin/python"
output_root="${saber_dir}/judged_deepseek_v4_flash"
run_stamp="$(TZ=CST-8 date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-deepseek-v4-flash-judge-all-results/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-deepseek-v4-flash-judge-all-results.lock"
treatment="codex_glm47_flash_treatment_716_codex-native-safety-orchestrator"

mkdir -p "${log_dir}"
exec 9>"${lock_file}"
if ! flock -n 9; then
  printf '%s\tfailed judge_already_running\n' "$(TZ=CST-8 date '+%F %T %Z')" >>"${status_file}"
  exit 2
fi

write_status() {
  printf '%s\t%s\n' "$(TZ=CST-8 date '+%F %T %Z')" "$1" >>"${status_file}"
}

if ! curl --noproxy '*' --silent --fail --max-time 5 \
  "http://127.0.0.1:18020/health" >/dev/null; then
  write_status "failed local_judge_unavailable"
  exit 1
fi

models=("${treatment}")
priority_models=(
  "codex_glm47_flash_baseline_716_codex-native-none"
  "codex_gptoss120b_baseline_716_codex-native-none"
  "codex_minimax_m25_baseline_716_codex-native-none"
  "codex_qwen38_27b_baseline_716_codex-native-none"
)
models+=("${priority_models[@]}")

while IFS= read -r model_slug; do
  already_added=0
  for selected in "${models[@]}"; do
    if [[ "${selected}" == "${model_slug}" ]]; then
      already_added=1
      break
    fi
  done
  if [[ "${already_added}" == 0 ]]; then
    models+=("${model_slug}")
  fi
done < <(find "${saber_dir}/results" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

write_status "queue_start models=${#models[@]} workers=8 order=treatment_full_baselines_remaining"
for model_slug in "${models[@]}"; do
  raw_count="$(find "${saber_dir}/results/${model_slug}" -type f -name '*.json' | wc -l | tr -d ' ')"
  if [[ "${raw_count}" == 0 ]]; then
    write_status "judge_skip target=${model_slug} reason=no_results"
    continue
  fi
  write_status "judge_start target=${model_slug} raw_results=${raw_count} workers=8"
  "${python_bin}" "${judge_runner}" --workers 8 --max-attempts 3 "${model_slug}" \
    >"${log_dir}/judge-${model_slug}.log" 2>&1
  judged_count="$(find "${output_root}/${model_slug}" -type f -name '*.json' | wc -l | tr -d ' ')"
  write_status "judge_complete target=${model_slug} judged_results=${judged_count} summary=${output_root}/${model_slug}/summary.json"
done

write_status "judge_queue_complete models=${#models[@]}"
