#!/usr/bin/env bash
set -euo pipefail

runner_codex_home="${CODEX_HOME:-/home/saber/.codex}"

if [[ -f "${runner_codex_home}/auth.json" ]] \
  && [[ "${SABER_ALLOW_CODEX_AUTH:-0}" != "1" ]]; then
  echo "Refusing to start: Codex login state is mounted in the isolated runner." >&2
  echo "Use a model base_url, or explicitly set SABER_ALLOW_CODEX_AUTH=1." >&2
  exit 2
fi

if [[ -n "${OPENAI_API_KEY:-}" ]] \
  && [[ "${SABER_ALLOW_OPENAI_API_KEY:-0}" != "1" ]]; then
  echo "Refusing to start: OPENAI_API_KEY reached the isolated runner." >&2
  echo "Use the model-specific key in config.json for an external provider." >&2
  exit 2
fi

exec "$@"
