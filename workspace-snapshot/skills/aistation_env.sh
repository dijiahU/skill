# Python env
source /2024233123/skills/envs/skills/bin/activate

# Compatible Docker 24 CLI
export PATH="/2024233123/skills/bin:$PATH"
export DOCKER_CONFIG="/2024233123/skills/docker-config"

# AIStation injects LOCAL_HOST_IP into the Pod init process, but some exec
# sessions do not inherit it. Recover only that variable when necessary.
if [[ -z "${LOCAL_HOST_IP:-}" && -r /proc/1/environ ]]; then
  while IFS='=' read -r env_name env_value; do
    if [[ "${env_name}" == "LOCAL_HOST_IP" ]]; then
      export LOCAL_HOST_IP="${env_value}"
      break
    fi
  done < <(tr '\0' '\n' < /proc/1/environ)
fi

if [[ -z "${LOCAL_HOST_IP:-}" ]]; then
  echo "AIStation LOCAL_HOST_IP is unavailable; Docker host cannot be configured." >&2
  return 1 2>/dev/null || exit 1
fi

# AIStation exposes the host Docker daemon on the current node
export DOCKER_HOST="tcp://${LOCAL_HOST_IP}:2375"
export DOCKER_API_VERSION="1.43"

# Keep Docker and local model API traffic away from HTTP/Clash proxies.
for aistation_bypass_host in "${LOCAL_HOST_IP}" localhost 127.0.0.1 ::1; do
  case ",${NO_PROXY:-}," in
    *,"${aistation_bypass_host}",*) ;;
    *) export NO_PROXY="${NO_PROXY:+${NO_PROXY},}${aistation_bypass_host}" ;;
  esac
  case ",${no_proxy:-}," in
    *,"${aistation_bypass_host}",*) ;;
    *) export no_proxy="${no_proxy:+${no_proxy},}${aistation_bypass_host}" ;;
  esac
done
unset aistation_bypass_host

# Path inside AIStation Pod
export POD_USER_ROOT="/2024233123"

# Same persistent storage as seen by host Docker
export HOST_USER_ROOT="/mnt/inaisfs/user-fs/2024233123"

# The image does not include IANA tzdata. POSIX CST-8 is fixed UTC+8 and keeps
# cluster-side commands and experiment logs aligned with Beijing time.
export TZ="CST-8"

# SABER containers should not use the host's default NVIDIA runtime
export SABER_DOCKER_RUNTIME="runc"

# OpenAgentSafety/OpenHands containers use the same remote host daemon. The
# host address is also where Pod-side health checks reach published ports.
export OPENAGENTSAFETY_DOCKER_RUNTIME="runc"
export OPENAGENTSAFETY_DOCKER_HOST_ADDR="${LOCAL_HOST_IP}"
export OPENAGENTSAFETY_SERVICE_HOST_ADDR="${LOCAL_HOST_IP}"
export EVAL_AGENT_SERVER_IMAGE="skilldistill-openagentsafety-agent-server"
export OPENAGENTSAFETY_IMAGE_TAG_PREFIX="aistation-20260831-reasoningfix"
export OPENAGENTSAFETY_BUILD_NETWORK="host"
export OPENAGENTSAFETY_WHEELHOUSE="/2024233123/skills/cache/openagentsafety-wheels-reasoningfix"
export OPENAGENTSAFETY_ASSET_CACHE="/2024233123/skills/cache/openagentsafety-assets"
