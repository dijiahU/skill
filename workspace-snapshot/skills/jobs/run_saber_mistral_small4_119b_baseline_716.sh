#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
model_dir="${skills_root}/models/modelscope/mistralai/Mistral-Small-4-119B-2603"
vllm_env="${skills_root}/envs/deepseekv4-vllm"
cuda_home="${skills_root}/envs/cuda-toolkit-12-9/usr/local/cuda-12.9"
compat_dir="${skills_root}/envs/cuda-compat-12-9/usr/local/cuda-12.9/compat"
mistral_compat_dir="${skills_root}/compat/mistral_developer_role"
nvjitlink_dir="${vllm_env}/lib/python3.10/site-packages/nvidia/nvjitlink/lib"
runtime_config="${skills_root}/jobs/saber_mistral_small4_119b_baseline_716.json"
subset_dir="${skills_root}/jobs/saber_glm47_baseline_716_subsets"
model_id="mistralai/Mistral-Small-4-119B-2603"
model_slug="codex_mistral_small4_119b_baseline_716"
api_port=18030
run_stamp="$(date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-mistral-small4-119b-baseline-716/${run_stamp}"
status_file="${log_dir}/status.tsv"
lock_file="${skills_root}/jobs/.saber-mistral-small4-119b-baseline-716.lock"
result_dir="${saber_dir}/results/${model_slug}_codex-native-none"
smoke_result="${result_dir}/A/fs_destruction/A_fs_001.json"
server_pid=""
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
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  write_status "job_exit status=${exit_status}"
}
trap cleanup EXIT INT TERM

exec 9>"${lock_file}"
if ! flock -n 9; then
  write_status "failed already_running"
  exit 2
fi

source "${skills_root}/aistation_env.sh"

if [[ ! -x "${vllm_env}/bin/vllm" ]]; then
  write_status "failed missing_vllm"
  exit 2
fi
if [[ ! -f "${model_dir}/model.safetensors.index.json" ]] || \
  [[ ! -f "${model_dir}/model-00003-of-00003.safetensors" ]]; then
  write_status "failed incomplete_model"
  exit 2
fi
if curl --noproxy '*' --silent --fail --max-time 2 \
  "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then
  write_status "failed api_port_in_use port=${api_port}"
  exit 2
fi
for worker_index in $(seq 0 7); do
  worker_label=$(printf '%02d' "${worker_index}")
  if [[ ! -f "${subset_dir}/part-${worker_label}.json" ]]; then
    write_status "failed missing_subset worker=${worker_label}"
    exit 2
  fi
done

export CUDA_VISIBLE_DEVICES=0,1
export CUDA_HOME="${cuda_home}"
export CUDACXX="${cuda_home}/bin/nvcc"
export PATH="${vllm_env}/bin:${cuda_home}/bin:${PATH}"
export CPATH="${cuda_home}/include:${CPATH:-}"
export LIBRARY_PATH="${cuda_home}/lib64:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="${compat_dir}:${nvjitlink_dir}:${cuda_home}/lib64:${LD_LIBRARY_PATH:-}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export VLLM_NO_USAGE_STATS=1
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONPATH="${mistral_compat_dir}:${PYTHONPATH:-}"
export FLASHINFER_WORKSPACE_BASE="${skills_root}/cache/flashinfer-mistral-small4"
export VLLM_CACHE_ROOT="${skills_root}/cache/vllm-mistral-small4"
export TORCHINDUCTOR_CACHE_DIR="${skills_root}/cache/torchinductor-mistral-small4"
export OMP_NUM_THREADS=8

write_status "starting_vllm gpus=0,1 tp=2 port=${api_port} max_model_len=32768"
SABER_MISTRAL_DEVELOPER_ROLE_COMPAT=1 \
"${vllm_env}/bin/vllm" serve "${model_dir}" \
  --served-model-name "${model_id}" \
  --host 0.0.0.0 \
  --port "${api_port}" \
  --trust-remote-code \
  --tokenizer-mode mistral \
  --config-format mistral \
  --load-format mistral \
  --tensor-parallel-size 2 \
  --dtype bfloat16 \
  --max-model-len 32768 \
  --max-num-seqs 8 \
  --max-num-batched-tokens 8192 \
  --gpu-memory-utilization 0.90 \
  --attention-backend FLASH_ATTN_MLA \
  --enable-auto-tool-choice \
  --tool-call-parser mistral \
  --reasoning-parser mistral \
  --language-model-only \
  >"${log_dir}/vllm.log" 2>&1 &
server_pid=$!

ready=0
for _ in $(seq 1 600); do
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
write_status "vllm_ready pid=${server_pid}"

cd "${saber_dir}"
write_status "preflight_start"
SABER_CODEX_CONFIG="${runtime_config}" \
  ./scripts/run/codex_runner.sh run \
    --model "${model_slug}" \
    --skill-mode none \
    --preflight-only \
    A_fs_001 \
    >"${log_dir}/preflight.log" 2>&1
write_status "preflight_complete"

write_status "smoke_start task=A_fs_001"
SABER_CODEX_CONFIG="${runtime_config}" \
  ./scripts/run/codex_runner.sh run \
    --model "${model_slug}" \
    --skill-mode none \
    --skip-preflight \
    --overwrite \
    A_fs_001 \
    >"${log_dir}/smoke.log" 2>&1

"${vllm_env}/bin/python" -c '
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    result = json.load(handle)
assert result.get("error") is None, result.get("error")
meta = result.get("harness_meta") or {}
assert meta.get("condition") == "none", meta
print(json.dumps({"task": result.get("id"), "condition": meta.get("condition")}))
' "${smoke_result}" >"${log_dir}/smoke-validation.json"
write_status "smoke_complete validation=${log_dir}/smoke-validation.json"

write_status "baseline_start model=${model_slug} tasks=716 workers=8"
for worker_index in $(seq 0 7); do
  worker_label=$(printf '%02d' "${worker_index}")
  subset_file="${subset_dir}/part-${worker_label}.json"
  (
    SABER_CODEX_CONFIG="${runtime_config}" \
      ./scripts/run/codex_runner.sh run \
        --model "${model_slug}" \
        --skill-mode none \
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
write_status "baseline_complete status=${job_status} results=${result_count}/716"
exit "${job_status}"
