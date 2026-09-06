#!/usr/bin/env bash
set -euo pipefail

container_name=${1:-}
tail_lines=${2:-80}

case "$container_name" in
  skilldistill-*) ;;
  *)
    echo "Refusing to inspect non-project container: $container_name" >&2
    exit 2
    ;;
esac

case "$tail_lines" in
  ''|*[!0-9]*)
    echo "Tail line count must be numeric" >&2
    exit 2
    ;;
esac

source /2024233123/skills/aistation_env.sh

docker inspect "$container_name" \
  --format 'status={{.State.Status}} exit={{.State.ExitCode}} started={{.State.StartedAt}} finished={{.State.FinishedAt}}'
docker stats --no-stream \
  --format 'cpu={{.CPUPerc}} mem={{.MemUsage}} net={{.NetIO}} pids={{.PIDs}}' \
  "$container_name"
docker logs --tail "$tail_lines" "$container_name"
