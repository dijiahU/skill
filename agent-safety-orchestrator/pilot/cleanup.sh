#!/bin/bash
# Tear down all pilot artifacts.
#
# Usage:
#   ./pilot/cleanup.sh           # remove container + audit logs (keep image)
#   ./pilot/cleanup.sh --image   # also remove the container image
#   ./pilot/cleanup.sh --all     # nuclear: container + audit + image

set -euo pipefail

PILOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="safety-orch-pilot"
# run.sh names containers per mode (safety-orch-pilot-bundle / -vanilla) and
# writes audit logs (incl. transcript/) to a per-mode dir. Clean both.
CONTAINERS=("safety-orch-pilot-bundle" "safety-orch-pilot-vanilla")
AUDIT_DIRS=("$PILOT_DIR/.audit-bundle" "$PILOT_DIR/.audit-vanilla")

# Auto-detect container CLI (podman preferred, docker fallback)
CONTAINER_CLI="${CONTAINER_CLI:-}"
if [ -z "$CONTAINER_CLI" ]; then
    if command -v podman >/dev/null 2>&1; then
        CONTAINER_CLI=podman
    elif command -v docker >/dev/null 2>&1; then
        CONTAINER_CLI=docker
    fi
fi

remove_image=0
case "${1:-}" in
    --image|--all) remove_image=1 ;;
esac

# Containers (both modes)
for c in "${CONTAINERS[@]}"; do
    if [ -n "$CONTAINER_CLI" ] && "$CONTAINER_CLI" rm -f "$c" 2>/dev/null; then
        echo "  ✓ removed container $c"
    else
        echo "  · no container $c to remove"
    fi
done

# Audit dirs (both modes; transcript/ lives inside each, so this clears it too)
for d in "${AUDIT_DIRS[@]}"; do
    if [ -d "$d" ]; then
        rm -rf "$d"
        echo "  ✓ removed audit logs at $d"
    else
        echo "  · no audit logs at $d to remove"
    fi
done

# Image (optional)
if [ "$remove_image" -eq 1 ] && [ -n "$CONTAINER_CLI" ]; then
    if "$CONTAINER_CLI" rmi "$IMAGE" 2>/dev/null; then
        echo "  ✓ removed image $IMAGE"
    else
        echo "  · no image to remove (or in use by another container)"
    fi
fi

echo
echo "Host ~/.claude/ has not been touched (it was never mounted writable)."
