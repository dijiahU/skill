# Public deployment template. Set these values for your own environment.
: "${POD_USER_ROOT:?Set the persistent workspace path inside your Pod}"
: "${HOST_USER_ROOT:?Set its corresponding path on the Docker host}"
: "${DOCKER_HOST:?Set your authorized Docker socket or remote endpoint}"

source "${POD_USER_ROOT}/skills/envs/skills/bin/activate"
export POD_USER_ROOT HOST_USER_ROOT DOCKER_HOST
export DOCKER_API_VERSION="${DOCKER_API_VERSION:-1.43}"
export DOCKER_CONFIG="${DOCKER_CONFIG:-${POD_USER_ROOT}/skills/docker-config}"
export PATH="${POD_USER_ROOT}/skills/bin:${POD_USER_ROOT}/skills/node/bin:${POD_USER_ROOT}/skills/npm-global/bin:$PATH"
export CODEX_HOME="${CODEX_HOME:-${POD_USER_ROOT}/skills/codex-home}"
export TZ="${TZ:-CST-8}"
export SABER_DOCKER_RUNTIME="${SABER_DOCKER_RUNTIME:-runc}"
export OPENAGENTSAFETY_DOCKER_RUNTIME="${OPENAGENTSAFETY_DOCKER_RUNTIME:-runc}"
export OPENAGENTSAFETY_DOCKER_HOST_ADDR="${OPENAGENTSAFETY_DOCKER_HOST_ADDR:-${LOCAL_HOST_IP:-127.0.0.1}}"
export OPENAGENTSAFETY_SERVICE_HOST_ADDR="${OPENAGENTSAFETY_SERVICE_HOST_ADDR:-${OPENAGENTSAFETY_DOCKER_HOST_ADDR}}"
export OPENAGENTSAFETY_WHEELHOUSE="${OPENAGENTSAFETY_WHEELHOUSE:-${POD_USER_ROOT}/skills/cache/openagentsafety-wheels-reasoningfix}"
export OPENAGENTSAFETY_ASSET_CACHE="${OPENAGENTSAFETY_ASSET_CACHE:-${POD_USER_ROOT}/skills/cache/openagentsafety-assets}"

# Supply image tags and network/proxy settings locally when required.
# Credentials remain outside the checkout.
if [[ -r "${POD_USER_ROOT}/skills/secrets/api-benchmarks.env" ]]; then
  source "${POD_USER_ROOT}/skills/secrets/api-benchmarks.env"
fi

for benchmark_bypass_host in localhost 127.0.0.1 ::1 "${LOCAL_HOST_IP:-}"; do
  [[ -n "$benchmark_bypass_host" ]] || continue
  case ",${NO_PROXY:-}," in
    *,"${benchmark_bypass_host}",*) ;;
    *) export NO_PROXY="${NO_PROXY:+${NO_PROXY},}${benchmark_bypass_host}" ;;
  esac
  case ",${no_proxy:-}," in
    *,"${benchmark_bypass_host}",*) ;;
    *) export no_proxy="${no_proxy:+${no_proxy},}${benchmark_bypass_host}" ;;
  esac
done
unset benchmark_bypass_host
