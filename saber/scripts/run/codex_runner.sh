#!/usr/bin/env bash
set -euo pipefail

runner_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runner_repo_dir="$(cd "${runner_script_dir}/../.." && pwd)"
runner_workspace_dir="$(cd "${runner_repo_dir}/.." && pwd)"
runner_image="${SABER_CODEX_RUNNER_IMAGE:-saber-codex-runner:0.149.1}"
runner_codex_version="${SABER_CODEX_VERSION:-0.149.1}"
runner_docker_cli_version="${SABER_DOCKER_CLI_VERSION:-24.0.9}"
runner_base_image="${SABER_CODEX_RUNNER_BASE_IMAGE:-ubuntu:22.04}"
runner_docker_host=""
runner_docker_args=()
runner_runtime_args=()

usage() {
  echo "Usage: $0 {build|smoke|run|shell} [run_harness arguments...]" >&2
}

configure_runner_docker() {
  runner_docker_host="${DOCKER_HOST:-}"
  if [[ -z "${runner_docker_host}" ]]; then
    runner_docker_host="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
  fi
  case "${runner_docker_host}" in
    unix://*)
      local runner_socket="${runner_docker_host#unix://}"
      if [[ ! -S "${runner_socket}" ]]; then
        echo "Docker socket not found: ${runner_socket}" >&2
        return 2
      fi
      runner_docker_args=(
        --mount "type=bind,src=${runner_socket},dst=/var/run/docker.sock"
      )
      ;;
    tcp://*)
      runner_docker_args=(
        --env "DOCKER_HOST=${runner_docker_host}"
        --env "DOCKER_API_VERSION=${DOCKER_API_VERSION:-1.43}"
      )
      ;;
    *)
      echo "Unsupported Docker host: ${runner_docker_host}" >&2
      return 2
      ;;
  esac

  local runner_runtime="${SABER_DOCKER_RUNTIME:-}"
  if [[ -n "${runner_runtime}" ]]; then
    if [[ ! "${runner_runtime}" =~ ^[A-Za-z0-9_.-]+$ ]]; then
      echo "Invalid SABER_DOCKER_RUNTIME: ${runner_runtime}" >&2
      return 2
    fi
    runner_runtime_args=(--runtime "${runner_runtime}")
    runner_docker_args+=(--env "SABER_DOCKER_RUNTIME=${runner_runtime}")
  fi
}

host_bind_source() {
  local source_path="$1"
  if [[ "${runner_docker_host}" != tcp://* ]]; then
    printf '%s\n' "${source_path}"
    return 0
  fi

  local pod_root="${POD_USER_ROOT:-}"
  local host_root="${HOST_USER_ROOT:-}"
  if [[ -z "${pod_root}" || -z "${host_root}" ]]; then
    echo "TCP Docker bind mounts require POD_USER_ROOT and HOST_USER_ROOT." >&2
    return 2
  fi
  pod_root="${pod_root%/}"
  host_root="${host_root%/}"

  case "${source_path}" in
    "${pod_root}") printf '%s\n' "${host_root}" ;;
    "${pod_root}"/*)
      printf '%s%s\n' "${host_root}" "${source_path#${pod_root}}"
      ;;
    "${host_root}"|"${host_root}"/*) printf '%s\n' "${source_path}" ;;
    *)
      echo "TCP Docker bind source is outside POD_USER_ROOT: ${source_path}" >&2
      return 2
      ;;
  esac
}

runner_action="${1:-}"
if [[ -z "${runner_action}" ]]; then
  usage
  exit 2
fi
shift

case "${runner_action}" in
  build)
    case "$(uname -m)" in
      x86_64) runner_target_arch="amd64" ;;
      aarch64|arm64) runner_target_arch="arm64" ;;
      *) echo "Unsupported Runner architecture: $(uname -m)" >&2; exit 2 ;;
    esac
    docker build \
      --pull=false \
      --file "${runner_repo_dir}/Dockerfile.codex-runner" \
      --build-arg "BASE_IMAGE=${runner_base_image}" \
      --build-arg "CODEX_VERSION=${runner_codex_version}" \
      --build-arg "DOCKER_CLI_VERSION=${runner_docker_cli_version}" \
      --build-arg "TARGETARCH=${runner_target_arch}" \
      --tag "${runner_image}" \
      "${runner_workspace_dir}"
    ;;
  smoke)
    configure_runner_docker
    docker run --rm \
      "${runner_runtime_args[@]}" \
      "${runner_docker_args[@]}" \
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
    runner_config="$(readlink -f "${runner_config}")"
    runner_adapter="$(readlink -f "${runner_repo_dir}/harness_adapters/codex_native_adapter.py")"
    runner_safety_orchestrator="$(readlink -f "${runner_workspace_dir}/agent-safety-orchestrator/agent-safety-orchestrator")"
    if [[ ! -d "${runner_safety_orchestrator}" ]]; then
      echo "Safety Orchestrator bundle not found: ${runner_safety_orchestrator}" >&2
      exit 2
    fi
    configure_runner_docker
    runner_config_source="$(host_bind_source "${runner_config}")"
    runner_adapter_source="$(host_bind_source "${runner_adapter}")"
    runner_safety_orchestrator_source="$(host_bind_source "${runner_safety_orchestrator}")"
    runner_results_mount_args=()
    case "${SABER_DISCARD_RESULTS:-0}" in
      0)
        runner_results="$(readlink -f "${runner_repo_dir}/results")"
        runner_results_source="$(host_bind_source "${runner_results}")"
        runner_results_mount_args=(
          --mount "type=bind,src=${runner_results_source},dst=/workspace/saber/results"
        )
        ;;
      1)
        runner_results_mount_args=(
          --tmpfs "/workspace/saber/results:rw,nosuid,nodev,size=1g"
        )
        ;;
      *)
        echo "SABER_DISCARD_RESULTS must be 0 or 1." >&2
        exit 2
        ;;
    esac
    runner_harness_args=("$@")
    runner_subset_mount_args=()
    for ((runner_arg_index=0; runner_arg_index<${#runner_harness_args[@]}; runner_arg_index++)); do
      if [[ "${runner_harness_args[$runner_arg_index]}" != "--subset" ]]; then
        continue
      fi
      runner_subset_index=$((runner_arg_index + 1))
      if (( runner_subset_index >= ${#runner_harness_args[@]} )); then
        echo "--subset requires a file path" >&2
        exit 2
      fi
      runner_subset="$(readlink -f "${runner_harness_args[$runner_subset_index]}")"
      if [[ ! -f "${runner_subset}" ]]; then
        echo "Runner subset not found: ${runner_subset}" >&2
        exit 2
      fi
      runner_subset_source="$(host_bind_source "${runner_subset}")"
      runner_subset_container="/run/secrets/saber-subset.json"
      runner_subset_mount_args=(
        --mount "type=bind,src=${runner_subset_source},dst=${runner_subset_container},readonly"
      )
      runner_harness_args[$runner_subset_index]="${runner_subset_container}"
      break
    done
    runner_provider_env_args=()
    if [[ -n "${SABER_CODEX_PROVIDER_API_KEY:-}" ]]; then
      runner_provider_env_args=(--env SABER_CODEX_PROVIDER_API_KEY)
    fi
    docker run --rm \
      "${runner_runtime_args[@]}" \
      "${runner_docker_args[@]}" \
      --mount "type=bind,src=${runner_config_source},dst=/run/secrets/saber-config.json,readonly" \
      --mount "type=bind,src=${runner_adapter_source},dst=/workspace/saber/harness_adapters/codex_native_adapter.py,readonly" \
      --mount "type=bind,src=${runner_safety_orchestrator_source},dst=/workspace/agent-safety-orchestrator/agent-safety-orchestrator,readonly" \
      "${runner_results_mount_args[@]}" \
      "${runner_subset_mount_args[@]}" \
      "${runner_provider_env_args[@]}" \
      "${runner_image}" \
      python3 run_harness.py \
      --harness codex-native \
      --config /run/secrets/saber-config.json \
      --safety-orchestrator \
        /workspace/agent-safety-orchestrator/agent-safety-orchestrator \
      "${runner_harness_args[@]}"
    ;;
  shell)
    configure_runner_docker
    runner_provider_env_args=()
    if [[ -n "${SABER_CODEX_PROVIDER_API_KEY:-}" ]]; then
      runner_provider_env_args=(--env SABER_CODEX_PROVIDER_API_KEY)
    fi
    docker run --rm \
      "${runner_runtime_args[@]}" \
      "${runner_docker_args[@]}" \
      "${runner_provider_env_args[@]}" \
      --interactive --tty \
      "${runner_image}" bash
    ;;
  *)
    usage
    exit 2
    ;;
esac
