#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
model_dir="${skills_root}/models/modelscope/OpenAI-Mirror/gpt-oss-120b"
vllm_env="${skills_root}/envs/qwen35-vllm"
judge_runner="${skills_root}/bin/run_saber_parallel_judge.py"
model_id="OpenAI-Mirror/gpt-oss-120b"
api_port=18004
run_stamp="$(date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-gptoss120b-judge-4models/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-gptoss120b-judge-4models.lock"
server_pid=""

mkdir -p "${log_dir}"
exec 9>"${lock_file}"
if ! flock -n 9; then
  printf '%s\tfailed judge_already_running\n' "$(date '+%F %T %Z')" >>"${status_file}"
  exit 2
fi

write_status() {
  printf '%s\t%s\n' "$(date '+%F %T %Z')" "$1" >>"${status_file}"
}

cleanup() {
  local exit_status=$?
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  write_status "job_exit status=${exit_status}"
}
trap cleanup EXIT INT TERM

source "${skills_root}/aistation_env.sh"
export PATH="${vllm_env}/bin:${PATH}"
export NO_PROXY="127.0.0.1,localhost,${NO_PROXY:-}"
export no_proxy="${NO_PROXY}"

if [[ ! -x "${vllm_env}/bin/vllm" ]] || [[ ! -x "${vllm_env}/bin/python" ]]; then
  write_status "failed missing_vllm_environment"
  exit 2
fi
if [[ ! -f "${model_dir}/model-00014-of-00014.safetensors" ]]; then
  write_status "failed incomplete_model"
  exit 2
fi
if curl --noproxy '*' --silent --fail --max-time 2 \
  "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then
  write_status "failed api_port_in_use port=${api_port}"
  exit 2
fi

write_status "starting_vllm judge=${model_id} gpu=0 tp=1 port=${api_port}"
CUDA_VISIBLE_DEVICES=0 \
VLLM_WORKER_MULTIPROC_METHOD=spawn \
VLLM_NO_USAGE_STATS=1 \
  "${vllm_env}/bin/vllm" serve "${model_dir}" \
    --served-model-name "${model_id}" \
    --host 0.0.0.0 \
    --port "${api_port}" \
    --tensor-parallel-size 1 \
    --max-model-len 131072 \
    --max-num-seqs 8 \
    --gpu-memory-utilization 0.85 \
    --enable-auto-tool-choice \
    --tool-call-parser openai \
    --language-model-only \
    >"${log_dir}/vllm.log" 2>&1 &
server_pid=$!

ready=0
for _ in $(seq 1 180); do
  if curl --noproxy '*' --silent --fail --max-time 3 \
    "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "${server_pid}" 2>/dev/null; then
    write_status "failed vllm_exited"
    exit 1
  fi
  sleep 5
done
if [[ "${ready}" != 1 ]]; then
  write_status "failed vllm_timeout"
  exit 1
fi
write_status "vllm_ready pid=${server_pid} gpu=0 gpu1_reserved_free=true"

cd "${saber_dir}"
probe_model="codex_qwen38_27b_baseline_716_codex-native-none"
write_status "judge_probe_start target=${probe_model}"
"${vllm_env}/bin/python" "${judge_runner}" --probe "${probe_model}" \
  >"${log_dir}/probe.log" 2>&1
write_status "judge_probe_complete target=${probe_model}"

models=(
  "codex_glm47_flash_baseline_716_codex-native-none"
  "codex_gptoss120b_baseline_716_codex-native-none"
  "codex_qwen38_27b_baseline_716_codex-native-none"
  "codex_minimax_m25_baseline_716_codex-native-none"
)

for model_slug in "${models[@]}"; do
  raw_count=$(find "${saber_dir}/results/${model_slug}" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
  write_status "judge_start target=${model_slug} raw_results=${raw_count} workers=8"
  "${vllm_env}/bin/python" "${judge_runner}" \
    --workers 8 \
    --max-attempts 3 \
    "${model_slug}" \
    >"${log_dir}/judge-${model_slug}.log" 2>&1
  judged_count=$(find "${saber_dir}/judged/${model_slug}" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
  write_status "judge_complete target=${model_slug} judged_results=${judged_count} summary=${saber_dir}/judged/${model_slug}/summary.json"
done

write_status "judge_queue_complete models=${#models[@]} gpu=0 gpu1_reserved_free=true"
