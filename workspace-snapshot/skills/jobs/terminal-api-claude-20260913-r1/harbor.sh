#!/usr/bin/env bash
set -euo pipefail
source /srv/benchmark/skills/aistation_env.sh
export PATH="/srv/benchmark/skills/envs/terminal-bench/bin:$PATH"
export PYTHONPATH=/srv/benchmark/skills/jobs/terminal-verifier-repair-20260913-r1/adapter:/srv/benchmark/skills/jobs/terminal-api-claude-20260913-r1/frozen/adapter:/srv/benchmark/skills/jobs/terminal-api-claude-20260913-r1/frozen
export TERMINAL_BENCH_SABER_ROOT=/srv/benchmark/skills/jobs/terminal-api-claude-20260913-r1/frozen/saber
export XDG_CACHE_HOME=/srv/benchmark/skills/cache/terminal-bench
export UV_CACHE_DIR=/srv/benchmark/skills/cache/uv-terminal-bench
export HARBOR_CACHE_DIR=/srv/benchmark/skills/cache/terminal-bench
source /srv/benchmark/skills/jobs/terminal-api-claude-20260913-r1/network.sh
export TERMINAL_BENCH_IMAGE_MIRROR=dockerproxy.net.
export RES_OPTIONS="ndots:1 timeout:2 attempts:2"
export TERMINAL_BENCH_DIRECT_DOWNLOAD=0
export TERMINAL_BENCH_DOWNLOAD_PROXY="${HTTPS_PROXY:-http://private-host-fb6337b4cc5a.invalid:7899}"

export PIP_INDEX_URL=https://pypi.org/simple
export PIP_EXTRA_INDEX_URL=
export PIP_CONFIG_FILE=/dev/null
export UV_DEFAULT_INDEX=https://pypi.org/simple
export UV_INDEX_URL=https://pypi.org/simple
export PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=5
export TERMINAL_BENCH_KEY_ENV=RESPONSES_API_KEY
exec /srv/benchmark/skills/envs/terminal-bench/bin/harbor "$@"
