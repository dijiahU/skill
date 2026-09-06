#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
oas_dir="${skills_root}/projects/skill/openagentsafety"
oas_bin="${oas_dir}/.venv/bin/openagentsafety-infer"
config="${oas_dir}/.llm_config/gptoss120b-local-oas-responses.json"
proxy_script="${skills_root}/bin/vllm_responses_compat_proxy_gptoss.py"
selection_dir="${skills_root}/jobs/openagentsafety-retry-directfix-20260904"
results_dir="${skills_root}/results/openagentsafety"
orchestrator_root="${skills_root}/projects/skill/agent-safety-orchestrator/agent-safety-orchestrator"
run_stamp="$(TZ=CST-8 date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/openagentsafety-gptoss120b-gpu0-parallel/${run_stamp}"
status_file="${log_dir}/status.tsv"
parent_queue_pid="${PARENT_QUEUE_PID:?PARENT_QUEUE_PID is required}"

server_pid=""
proxy_pid=""
baseline_pid=""
skill_pid=""
parent_paused=0

mkdir -p "${log_dir}"

write_status() {
  printf '%s\t%s\n' "$(TZ=CST-8 date '+%F %T %Z')" "$1" \
    | tee -a "${status_file}"
}

stop_server() {
  local attempt
  if [[ -z "${server_pid}" ]] || ! kill -0 "${server_pid}" 2>/dev/null; then
    return 0
  fi

  write_status "server_stop pid=${server_pid} signal=INT"
  kill -INT "${server_pid}" 2>/dev/null || true
  for attempt in $(seq 1 30); do
    if ! kill -0 "${server_pid}" 2>/dev/null; then
      break
    fi
    sleep 2
  done
  if kill -0 "${server_pid}" 2>/dev/null; then
    write_status "server_stop pid=${server_pid} signal=TERM"
    kill -TERM "${server_pid}" 2>/dev/null || true
  fi
  wait "${server_pid}" 2>/dev/null || true
  server_pid=""
}

cleanup() {
  local exit_status=$?
  local pid

  for pid in "${baseline_pid}" "${skill_pid}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill -TERM "${pid}" 2>/dev/null || true
    fi
  done
  if [[ -n "${proxy_pid}" ]] && kill -0 "${proxy_pid}" 2>/dev/null; then
    kill -TERM "${proxy_pid}" 2>/dev/null || true
    wait "${proxy_pid}" 2>/dev/null || true
  fi
  stop_server || true
  if [[ "${parent_paused}" -eq 1 ]] && kill -0 "${parent_queue_pid}" 2>/dev/null; then
    kill -CONT "${parent_queue_pid}" 2>/dev/null || true
    write_status "parent_queue_resumed pid=${parent_queue_pid}"
  fi
  write_status "parallel_queue_exit status=${exit_status}"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

source "${skills_root}/aistation_env.sh"

export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export MODELSCOPE_OFFLINE=1
export OPENHANDS_SUPPRESS_BANNER=1
export HTTP_PROXY="http://127.0.0.1:17892"
export HTTPS_PROXY="http://127.0.0.1:17892"
export http_proxy="${HTTP_PROXY}"
export https_proxy="${HTTPS_PROXY}"
export NO_PROXY="127.0.0.1,localhost,${LOCAL_HOST_IP},raw.githubusercontent.com"
export no_proxy="${NO_PROXY}"
export OPENAGENTSAFETY_SAFETY_ORCHESTRATOR_ROOT="${orchestrator_root}"
unset NPC_API_KEY NPC_BASE_URL NPC_MODEL

if ! ps -p "${parent_queue_pid}" -o args= \
  | grep -Fq 'run_openagentsafety_local_models_queue.sh'; then
  write_status "failed unexpected_parent pid=${parent_queue_pid}"
  exit 2
fi

if [[ -n "$(nvidia-smi -i 0 --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null)" ]]; then
  write_status "failed gpu0_in_use"
  exit 2
fi

if curl --noproxy '*' --silent --fail --max-time 2 \
  http://127.0.0.1:18004/health >/dev/null 2>&1; then
  write_status "failed port_in_use port=18004"
  exit 2
fi

kill -STOP "${parent_queue_pid}"
parent_paused=1
write_status "parent_queue_paused pid=${parent_queue_pid} reason=parallel_gptoss"

(
  export CUDA_VISIBLE_DEVICES=0
  export VLLM_WORKER_MULTIPROC_METHOD=spawn
  export VLLM_NO_USAGE_STATS=1
  export PYTHONPATH="${skills_root}/envs/gptoss-oss-harmony-overlay${PYTHONPATH:+:${PYTHONPATH}}"
  exec "${skills_root}/envs/qwen35-vllm/bin/vllm" serve \
    "${skills_root}/models/modelscope/OpenAI-Mirror/gpt-oss-120b" \
    --served-model-name OpenAI-Mirror/gpt-oss-120b \
    --host 0.0.0.0 \
    --port 18004 \
    --tensor-parallel-size 1 \
    --max-model-len 32768 \
    --max-num-seqs 8 \
    --gpu-memory-utilization 0.85 \
    --enable-auto-tool-choice \
    --tool-call-parser openai \
    --language-model-only
) >>"${log_dir}/gptoss120b.server.log" 2>&1 &
server_pid=$!
write_status "server_start model=gptoss120b gpu=0 port=18004 pid=${server_pid}"

ready=0
for attempt in $(seq 1 360); do
  if curl --noproxy '*' --silent --fail --max-time 3 \
    http://127.0.0.1:18004/health >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "${server_pid}" 2>/dev/null; then
    write_status "failed server_exited model=gptoss120b"
    exit 1
  fi
  sleep 5
done
if [[ "${ready}" -ne 1 ]]; then
  write_status "failed server_timeout model=gptoss120b"
  exit 1
fi
write_status "server_ready model=gptoss120b gpu=0 port=18004 pid=${server_pid}"

"${skills_root}/envs/qwen35-vllm/bin/python" "${proxy_script}" \
  --host 0.0.0.0 \
  --port 18005 \
  --upstream http://127.0.0.1:18004 \
  >>"${log_dir}/gptoss120b.responses-proxy.log" 2>&1 &
proxy_pid=$!

proxy_ready=0
for attempt in $(seq 1 30); do
  if curl --noproxy '*' --silent --fail --max-time 3 \
    http://127.0.0.1:18005/v1/models >/dev/null 2>&1; then
    proxy_ready=1
    break
  fi
  if ! kill -0 "${proxy_pid}" 2>/dev/null; then
    write_status "failed responses_proxy_exited"
    exit 1
  fi
  sleep 2
done
if [[ "${proxy_ready}" -ne 1 ]]; then
  write_status "failed responses_proxy_timeout"
  exit 1
fi
write_status "responses_proxy_ready model=gptoss120b port=18005 pid=${proxy_pid}"

common_args=(
  --dataset mgulavani/openagentsafety_full_updated_v3
  --split train
  --workspace docker
  --max-iterations 50
  --num-workers 2
  --output-dir "${results_dir}"
  --n-critic-runs 1
  --critic pass
  --max-retries 0
  --tool-preset default
  --enable-condenser
  --condenser-max-tokens 22000
  --condenser-max-output-tokens 1024
)

write_status "oas_start model=gptoss120b mode=baseline workers=2"
(
  cd "${oas_dir}"
  "${oas_bin}" "${config}" \
    "${common_args[@]}" \
    --select "${selection_dir}/gptoss120b.baseline.txt" \
    --note gptoss120b-nodeps222-baseline-retry-contextfix-20260904-w2 \
    --skill-mode none
) >"${log_dir}/gptoss120b.baseline.log" 2>&1 &
baseline_pid=$!

write_status "oas_start model=gptoss120b mode=safety-orchestrator workers=2"
(
  cd "${oas_dir}"
  "${oas_bin}" "${config}" \
    "${common_args[@]}" \
    --select "${selection_dir}/gptoss120b.safety-orchestrator.txt" \
    --note gptoss120b-nodeps222-safety-orchestrator-retry-contextfix-20260904-w2 \
    --skill-mode safety-orchestrator \
    --safety-orchestrator-root "${orchestrator_root}"
) >"${log_dir}/gptoss120b.safety-orchestrator.log" 2>&1 &
skill_pid=$!

set +e
wait "${baseline_pid}"
baseline_status=$?
baseline_pid=""
wait "${skill_pid}"
skill_status=$?
skill_pid=""
set -e
write_status "oas_complete model=gptoss120b mode=baseline status=${baseline_status}"
write_status "oas_complete model=gptoss120b mode=safety-orchestrator status=${skill_status}"

if [[ "${baseline_status}" -ne 0 || "${skill_status}" -ne 0 ]]; then
  exit 1
fi

