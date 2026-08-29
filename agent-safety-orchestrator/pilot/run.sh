#!/bin/bash
# Host-side launcher for the Safety Orchestrator pilot container.
#
# Two modes:
#   ./pilot/run.sh             # BUNDLE: 1 router skill (14 archetype docs nested) + 8 hook matchers (default)
#   ./pilot/run.sh --vanilla   # VANILLA: empty .claude/, no bundle (A/B baseline)
#
# Audit logs go to separate host dirs per mode so you can diff:
#   pilot/.audit-bundle/    (bundle mode)
#   pilot/.audit-vanilla/   (vanilla mode — should be empty since no hooks)
#
# Container engine: auto-detects podman (preferred on rootless RHEL/Rocky)
# then docker. Override with CONTAINER_CLI=docker (or =podman).
#
# Other flags:
#   --rebuild   force rebuild image (after Dockerfile / entrypoint changes)
#   --vanilla   run in vanilla / baseline mode (no bundle)

set -euo pipefail

PILOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PILOT_DIR/.." && pwd)"
BUNDLE="$REPO_ROOT/agent-safety-orchestrator"
IMAGE="safety-orch-pilot"

# Claude Code version baked into the image. Pinned for pilot reproducibility
# (built-in safety behavior — the A/B baseline — is version-dependent). Override
# with CLAUDE_CODE_VERSION=2.1.149 ./pilot/run.sh --rebuild to test another rev.
CLAUDE_CODE_VERSION="${CLAUDE_CODE_VERSION:-2.1.158}"

# ----- Parse flags -----
BUNDLE_MODE="bundle"
do_rebuild=0
for arg in "$@"; do
    case "$arg" in
        --vanilla)  BUNDLE_MODE="vanilla" ;;
        --rebuild)  do_rebuild=1 ;;
        *)          echo "Unknown flag: $arg" >&2; exit 1 ;;
    esac
done

CONTAINER="safety-orch-pilot-${BUNDLE_MODE}"
AUDIT_DIR="$PILOT_DIR/.audit-${BUNDLE_MODE}"

# ----- Source repo-root .env if present -----
# Bash doesn't auto-load .env the way Python's scripts/_env.py does. Pilot
# credentials (VIRUSTOTAL_API_KEY etc.) live in $REPO_ROOT/.env (gitignored).
# `set -a` exports every var assigned during the source so they propagate to
# child processes (including the container env passthrough below).
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$REPO_ROOT/.env"
    set +a
    echo "  Loaded env: $REPO_ROOT/.env"
fi

# ----- Container CLI auto-detect -----
CONTAINER_CLI="${CONTAINER_CLI:-}"
if [ -z "$CONTAINER_CLI" ]; then
    if command -v podman >/dev/null 2>&1; then
        CONTAINER_CLI=podman
    elif command -v docker >/dev/null 2>&1; then
        CONTAINER_CLI=docker
    else
        echo "ERROR: neither podman nor docker found." >&2
        echo "  Rocky / RHEL:  sudo dnf install podman" >&2
        echo "  Other:         https://docs.docker.com/get-docker/" >&2
        exit 1
    fi
fi
echo "  Container CLI: $CONTAINER_CLI"
echo "  Mode:          $BUNDLE_MODE"

# ----- Pre-flight (bundle mode only — vanilla doesn't need bundle dir) -----
if [ "$BUNDLE_MODE" = "bundle" ] && [ ! -d "$BUNDLE/skills" ]; then
    echo "ERROR: bundle not found at $BUNDLE" >&2
    echo "Did you cd into the repo root before running?" >&2
    exit 1
fi

# ----- Build (idempotent unless --rebuild) -----
if [ "$do_rebuild" -eq 1 ] || ! "$CONTAINER_CLI" image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Building $IMAGE..."
    # --network=host so build can use host's DNS / proxy / mirror config.
    # Override with CONTAINER_BUILD_NET=bridge if you want default rootless networking.
    BUILD_NET="${CONTAINER_BUILD_NET:-host}"
    echo "  Claude Code:   $CLAUDE_CODE_VERSION (pinned)"
    "$CONTAINER_CLI" build --network="$BUILD_NET" \
        --build-arg "CLAUDE_CODE_VERSION=$CLAUDE_CODE_VERSION" \
        -t "$IMAGE" "$PILOT_DIR"
fi

# ----- Cleanup any stale container -----
"$CONTAINER_CLI" rm -f "$CONTAINER" >/dev/null 2>&1 || true

# ----- Auth handling -----
AUTH_ARGS=()
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    AUTH_ARGS+=(-e "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY")
    echo "  Auth: ANTHROPIC_API_KEY env"
elif [ -f "$HOME/.claude/.credentials.json" ]; then
    AUTH_ARGS+=(-v "$HOME/.claude/.credentials.json:/home/pilot/.claude/.credentials.json:ro")
    echo "  Auth: host ~/.claude/.credentials.json (mounted read-only)"
else
    echo "  Auth: ⚠ none detected. You'll need to 'claude login' inside the container."
fi

# ----- Atom credential passthrough -----
# Network atoms that need API keys to run in active mode. Host shell exports
# these (e.g. `export VIRUSTOTAL_API_KEY=...`); run.sh propagates into the
# container env so the bundle's helpers can read them. NEVER hardcode keys
# here — they belong in host shell / .bashrc / .env (gitignored), not in
# pilot/ files.
ATOM_ENV_VARS=(
    VIRUSTOTAL_API_KEY   # check-malware-hash-ioc
    OSV_API_KEY          # check-package-cve (OSV public tier is keyless; optional)
)
ENV_ARGS=()
for var in "${ATOM_ENV_VARS[@]}"; do
    if [ -n "${!var:-}" ]; then
        ENV_ARGS+=(-e "$var=${!var}")
        echo "  Atom env: $var (propagated)"
    fi
done

# ----- Audit log persistence (separate dir per mode) -----
mkdir -p "$AUDIT_DIR"
echo "  Audit logs: $AUDIT_DIR"

# ----- Claude Code session transcript persistence -----
# Claude Code writes its full session transcript (every tool_use block, incl.
# the Skill tool + which skill + tool results) under ~/.claude/projects/. The
# container is --rm with a fresh ~/.claude, so without this mount the transcript
# is destroyed on exit. It's the GROUND TRUTH for model-invoked skills and for
# Claude Code's own refusals (the built-in line in A/B attribution), so persist
# it to the host per mode.
TRANSCRIPT_DIR="$AUDIT_DIR/transcript"
mkdir -p "$TRANSCRIPT_DIR"
echo "  Transcript: $TRANSCRIPT_DIR"
echo

# ----- Rootless podman: keep-id user namespace with explicit uid mapping -----
# Container's `pilot` user is uid 1001 (node:20-slim base image takes 1000 for
# its `node` user, so `useradd pilot` in our Dockerfile gets 1001). The host
# runner's uid (cty) is typically NOT 1001 — e.g. 1114 on the test cluster.
#
# Plain `--userns=keep-id` maps "host uid X → container uid X" (same number),
# which doesn't reconcile with the Dockerfile's USER pilot (1001). Result:
# container writes appear on host as uid 1001 (which doesn't exist) and the
# host bind-mount dir owned by cty is unwritable → PermissionError on
# .safety-orch/atom-status.json.
#
# The fix is podman 4+'s extended syntax: `keep-id:uid=N,gid=N` says
# "map the host runner's uid/gid to N inside the container". With N=1001,
# host cty becomes container pilot, and writes to the bind mount land back
# on host as cty-owned files.
#
# PILOT_CONTAINER_UID/GID override if you change the Dockerfile to use a
# different uid (e.g. switch base image to one without a default node user).
USERNS_ARGS=()
if [ "$CONTAINER_CLI" = "podman" ] || [ "${USERNS_KEEP_ID:-0}" = "1" ]; then
    PILOT_CONTAINER_UID="${PILOT_CONTAINER_UID:-1001}"
    PILOT_CONTAINER_GID="${PILOT_CONTAINER_GID:-1001}"
    USERNS_ARGS+=(--userns="keep-id:uid=${PILOT_CONTAINER_UID},gid=${PILOT_CONTAINER_GID}")
fi

# ----- Runtime network: host by default for pilot -----
# Without --network=host, container has its own loopback. Host's
# http_proxy=http://127.0.0.1:NNNN is unreachable from container → 3
# network-dependent atoms (check-package-cve / detect-hallucinated-package /
# check-package-recency-anomaly) degrade with [Errno 111] Connection refused,
# fall back to LLM judgment / bundled snapshots. Pilot 4.7.2 needs the
# *active* path of these atoms to validate atom design (not just fallback),
# so we default to --network=host. Trade-off: container shares host's
# network namespace; pilot's isolation goal was ~/.claude/, not network,
# so this is acceptable.
#
# Set CONTAINER_NET_MODE=bridge to get isolated rootless networking (will
# re-degrade those 3 atoms — useful only to test the fallback path itself).
CONTAINER_NET_MODE="${CONTAINER_NET_MODE:-host}"
NET_ARGS=(--network="$CONTAINER_NET_MODE")
echo "  Network mode:  $CONTAINER_NET_MODE"
echo

# ----- Run -----
# Bundle mount is read-only; vanilla mode also gets it (harmless) so the
# image works the same regardless. Mode is decided by BUNDLE_MODE env.
exec "$CONTAINER_CLI" run -it --rm \
    --name "$CONTAINER" \
    "${USERNS_ARGS[@]}" \
    "${NET_ARGS[@]}" \
    -v "$BUNDLE:/home/pilot/bundle:ro" \
    -v "$AUDIT_DIR:/home/pilot/.safety-orch" \
    -v "$TRANSCRIPT_DIR:/home/pilot/.claude/projects" \
    -e "BUNDLE_MODE=$BUNDLE_MODE" \
    "${AUTH_ARGS[@]}" \
    "${ENV_ARGS[@]}" \
    "$IMAGE"
