#!/usr/bin/env bash
set -euo pipefail

runner_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runner_repo_dir="$(cd "${runner_script_dir}/../.." && pwd)"
runner_workspace_dir="$(cd "${runner_repo_dir}/.." && pwd)"
runner_image="${SABER_CODEX_RUNNER_IMAGE:-saber-codex-runner:0.149.1}"
runner_codex_version="${SABER_CODEX_VERSION:-0.149.1}"

usage() {
  echo "Usage: $0 {build|smoke|run|shell} [run_harness arguments...]" >&2
}

docker_socket_path() {
  local runner_docker_host="${DOCKER_HOST:-}"
  if [[ -z "${runner_docker_host}" ]]; then
    runner_docker_host="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
  fi
  case "${runner_docker_host}" in
    unix://*) printf '%s\n' "${runner_docker_host#unix://}" ;;
    *)
      echo "Codex Runner currently requires a Unix Docker socket; got: ${runner_docker_host}" >&2
      return 2
      ;;
  esac
}

require_docker_socket() {
  local runner_socket="$1"
  if [[ ! -S "${runner_socket}" ]]; then
    echo "Docker socket not found: ${runner_socket}" >&2
    return 2
  fi
}

runner_action="${1:-}"
if [[ -z "${runner_action}" ]]; then
  usage
  exit 2
fi
shift

case "${runner_action}" in
  build)
    docker build \
      --pull=false \
      --file "${runner_repo_dir}/Dockerfile.codex-runner" \
      --build-arg "CODEX_VERSION=${runner_codex_version}" \
      --tag "${runner_image}" \
      "${runner_workspace_dir}"
    ;;
  smoke)
    runner_socket="$(docker_socket_path)"
    require_docker_socket "${runner_socket}"
    docker run --rm \
      --mount "type=bind,src=${runner_socket},dst=/var/run/docker.sock" \
      "${runner_image}" \
      python3 scripts/codex_runner_smoke.py
    ;;
  run)
    runner_config="${SABER_CODEX_CONFIG:-${runner_repo_dir}/config.json}"
    if [[ ! -f "${runner_config}" ]]; then
      echo "Runner config not found: ${runner_config}" >&2
      exit 2
    fi
    mkdir -p "${runner_repo_dir}/results"
    runner_socket="$(docker_socket_path)"
    require_docker_socket "${runner_socket}"
    runner_provider_env_args=()
    if [[ -n "${SABER_CODEX_PROVIDER_API_KEY:-}" ]]; then
      runner_provider_env_args=(--env SABER_CODEX_PROVIDER_API_KEY)
    fi
    docker run --rm \
      --mount "type=bind,src=${runner_socket},dst=/var/run/docker.sock" \
      --mount "type=bind,src=${runner_config},dst=/run/secrets/saber-config.json,readonly" \
      --mount "type=bind,src=${runner_repo_dir}/results,dst=/workspace/saber/results" \
      "${runner_provider_env_args[@]}" \
      "${runner_image}" \
      python3 run_harness.py \
      --harness codex-native \
      --config /run/secrets/saber-config.json \
      --safety-orchestrator \
        /workspace/agent-safety-orchestrator/agent-safety-orchestrator \
      "$@"
    ;;
  shell)
    runner_socket="$(docker_socket_path)"
    require_docker_socket "${runner_socket}"
    runner_provider_env_args=()
    if [[ -n "${SABER_CODEX_PROVIDER_API_KEY:-}" ]]; then
      runner_provider_env_args=(--env SABER_CODEX_PROVIDER_API_KEY)
    fi
    docker run --rm \
      --mount "type=bind,src=${runner_socket},dst=/var/run/docker.sock" \
      "${runner_provider_env_args[@]}" \
      --interactive --tty \
      "${runner_image}" bash
    ;;
  *)
    usage
    exit 2
    ;;
esac
