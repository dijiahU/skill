#!/usr/bin/env bash
# Install evaluation harness dependencies only; never launch a model server.
set -euo pipefail

bench_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(dirname "$bench_dir")"
uv_bin="${UV_BIN:-$bench_dir/.venv-tools/bin/uv}"
if [[ ! -x "$uv_bin" ]]; then
  uv_bin="$(command -v uv || true)"
fi
if [[ -z "$uv_bin" ]]; then
  echo "Install uv first, or set UV_BIN to its executable." >&2
  exit 1
fi
export UV_CACHE_DIR="${UV_CACHE_DIR:-$bench_dir/.cache/uv}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$bench_dir/.cache/python}"
export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-300}"
export UV_HTTP_RETRIES="${UV_HTTP_RETRIES:-3}"

case "${1:-deps}" in
  deps)
    "$uv_bin" venv --python 3.12 --allow-existing "$bench_dir/.venv-saber"
    "$uv_bin" pip install --python "$bench_dir/.venv-saber/bin/python" \
      -r "$bench_dir/requirements-saber.lock.txt"
    "$uv_bin" venv --python 3.12 --allow-existing "$bench_dir/.venv-harbor"
    "$uv_bin" pip install --python "$bench_dir/.venv-harbor/bin/python" \
      -r "$bench_dir/requirements-harbor.lock.txt"
    "$uv_bin" sync --project "$workspace_dir/openagentsafety" --python 3.12 --frozen --no-dev
    ;;
  saber-image)
    docker build -t osbench-sandbox "$workspace_dir/saber"
    ;;
  terminalbench-cli)
    python3 "$bench_dir/prepare_codex.py"
    ;;
  oas-images)
    export OPENAGENTSAFETY_WHEELHOUSE="${OPENAGENTSAFETY_WHEELHOUSE:-$bench_dir/.cache/oas-wheels}"
    export OPENAGENTSAFETY_BUILD_NETWORK="${OPENAGENTSAFETY_BUILD_NETWORK:-default}"
    export EVAL_AGENT_SERVER_IMAGE="${EVAL_AGENT_SERVER_IMAGE:-skilldistill-openagentsafety-agent-server}"
    export OPENAGENTSAFETY_IMAGE_TAG_PREFIX="${OPENAGENTSAFETY_IMAGE_TAG_PREFIX:-api}"
    export PATH="$(dirname "$uv_bin"):$PATH"
    (cd "$workspace_dir" && python3 -m api_benchmarks.prepare_oas_wheels)
    cd "$workspace_dir/openagentsafety"
    .venv/bin/python -m benchmarks.openagentsafety.build_images
    .venv/bin/python "$bench_dir/build_oas_hooks.py"
    ;;
  *) echo "Usage: bash api_benchmarks/setup.sh {deps|saber-image|oas-images|terminalbench-cli}" >&2; exit 2 ;;
esac
