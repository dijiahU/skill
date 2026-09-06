#!/usr/bin/env bash
set -Eeuo pipefail

skills_root="/2024233123/skills"
saber_dir="${skills_root}/projects/skill/saber"
model_dir="${skills_root}/models/modelscope/Qwen/Qwen3.5-2B"
vllm_env="${skills_root}/envs/qwen35-vllm"
model_id="Qwen/Qwen3.5-2B"
model_slug="codex_qwen35_2b_smoke"
api_port="${QWEN_API_PORT:-18000}"
run_stamp="$(date '+%Y%m%d-%H%M%S')"
log_dir="${skills_root}/logs/saber-qwen35-2b-smoke/${run_stamp}"
runtime_config="${log_dir}/config.json"
server_log="${log_dir}/vllm.log"
probe_output="${log_dir}/responses-probe.json"
server_pid=""

mkdir -p "${log_dir}"

cleanup() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    echo "Stopping smoke model server pid=${server_pid}"
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

fail_with_server_log() {
  local message="$1"
  echo "ERROR: ${message}" >&2
  if [[ -f "${server_log}" ]]; then
    echo "--- vLLM log tail ---" >&2
    tail -n 120 "${server_log}" >&2 || true
  fi
  exit 1
}

if [[ ! -x "${vllm_env}/bin/vllm" ]]; then
  echo "vLLM environment is not ready: ${vllm_env}" >&2
  echo "Wait for skilldistill-qwen35-vllm-env-build-20260831 to finish." >&2
  exit 2
fi
if [[ ! -f "${model_dir}/config.json" ]]; then
  echo "Qwen3.5-2B model is incomplete: ${model_dir}" >&2
  exit 2
fi

# Provides the compatible Docker client, TCP daemon endpoint, bind-path mapping,
# Beijing timezone, and explicit runc selection used by the SABER runner.
source "${skills_root}/aistation_env.sh"

pod_ip="${SABER_MODEL_SERVICE_HOST:-$(hostname -I | awk '{print $1}')}"
if [[ -z "${pod_ip}" ]]; then
  echo "Unable to determine the AIStation Pod IP." >&2
  exit 2
fi
api_base="http://${pod_ip}:${QWEN_PROXY_PORT:-18001}/v1"

if curl --silent --fail --max-time 2 "http://127.0.0.1:${api_port}/health" \
  >/dev/null 2>&1; then
  echo "Port ${api_port} already has a model server; refusing to reuse it." >&2
  exit 2
fi

cat >"${runtime_config}" <<EOF
{
  "max_steps": 30,
  "models": {
    "${model_slug}": {
      "id": "${model_id}",
      "type": "codex-native",
      "base_url": "${api_base}",
      "copy_codex_auth": false,
      "preload_skill_references": false
    }
  }
}
EOF

echo "Starting Qwen3.5-2B on GPU ${QWEN_CUDA_VISIBLE_DEVICES:-0}"
echo "API base: ${api_base}"
echo "Logs: ${log_dir}"

CUDA_VISIBLE_DEVICES="${QWEN_CUDA_VISIBLE_DEVICES:-0}" \
  VLLM_FORCE_NATIVE_GDN="${VLLM_FORCE_NATIVE_GDN:-1}" \
  PATH="${vllm_env}/bin:${PATH}" \
  "${vllm_env}/bin/vllm" serve "${model_dir}" \
    --served-model-name "${model_id}" \
    --host 0.0.0.0 \
    --port "${api_port}" \
    --tensor-parallel-size 1 \
    --dtype bfloat16 \
    --max-model-len "${VLLM_MAX_MODEL_LEN:-32768}" \
    --max-num-seqs "${VLLM_MAX_NUM_SEQS:-8}" \
    --gpu-memory-utilization "${VLLM_GPU_MEMORY_UTILIZATION:-0.50}" \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --language-model-only \
    >"${server_log}" 2>&1 &
server_pid=$!

ready=0
for _ in $(seq 1 180); do
  if curl --silent --fail --max-time 3 \
    "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "${server_pid}" 2>/dev/null; then
    fail_with_server_log "vLLM exited during startup"
  fi
  sleep 5
done
if [[ "${ready}" != "1" ]]; then
  fail_with_server_log "vLLM did not become healthy within 15 minutes"
fi

curl --silent --show-error --fail --max-time 180 \
  --header 'Content-Type: application/json' \
  --data "{\"model\":\"${model_id}\",\"input\":\"Reply exactly with OK.\",\"max_output_tokens\":32}" \
  "http://127.0.0.1:${api_port}/v1/responses" >"${probe_output}" \
  || fail_with_server_log "the vLLM Responses endpoint probe failed"

"${vllm_env}/bin/python" -c '
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
if payload.get("error"):
    raise SystemExit("Responses probe returned an error: {}".format(payload.get("error")))
if payload.get("object") != "response" and not payload.get("output"):
    raise SystemExit("Responses probe returned an unexpected payload")
print("Responses endpoint probe passed")
' "${probe_output}"

cd "${saber_dir}"
echo "Running token-free Codex/Docker preflight"
./scripts/run/codex_runner.sh smoke

echo "Running SABER smoke task A_fs_001 without Safety Plane"
SABER_CODEX_CONFIG="${runtime_config}" \
  ./scripts/run/codex_runner.sh run \
    --model "${model_slug}" \
    --skill-mode none \
    --trace \
    --overwrite \
    A_fs_001 \
    2>&1 | tee "${log_dir}/saber.log"

result_file="${saber_dir}/results/${model_slug}_codex-native-none/A/fs_destruction/A_fs_001.json"
"${vllm_env}/bin/python" -c '
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
if payload.get("error"):
    raise SystemExit("SABER smoke failed: {}".format(payload.get("error")))
conversation = payload.get("conversation") or []
if not conversation or all(item.get("role") == "error" for item in conversation):
    raise SystemExit("SABER smoke produced no healthy conversation")
print(
    "SABER smoke passed:",
    payload.get("id"),
    "events={}".format(len(payload.get("events") or [])),
    "messages={}".format(len(conversation)),
)
' "${result_file}"

echo "Smoke complete. Result: ${result_file}"
echo "Logs: ${log_dir}"
