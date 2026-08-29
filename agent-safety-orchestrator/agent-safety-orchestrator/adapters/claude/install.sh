#!/usr/bin/env bash
# Agent Safety Orchestrator — manual (non-plugin) installer.
#
# RECOMMENDED install is via the Claude Code plugin system:
#   /plugin marketplace add tychenn/agent-safety-orchestrator
#   /plugin install agent-safety-orchestrator@safety-tools
#   /reload-plugins
#
# This script is the MANUAL path (no marketplace) — e.g. air-gapped, or wiring
# hooks straight into settings.json. It renders hooks/hooks.json (substituting
# ${CLAUDE_PLUGIN_ROOT} with the repo root's absolute path) and merges it in.
# - Validates Python 3.9+
# - Substitutes ${CLAUDE_PLUGIN_ROOT} in hooks/hooks.json
# - Optionally merges into ~/.claude/settings.json
# - Runs health-status banner
#
# Usually invoked via the repo-root dispatcher:  ./install.sh --host claude

set -euo pipefail

# This installer lives at adapters/claude/; the bundle root is two levels up.
BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLAUDE_SETTINGS="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"

echo "Safety Orchestrator installer"
echo "  bundle root:     $BUNDLE_ROOT"
echo "  claude settings: $CLAUDE_SETTINGS"
echo

# 1. Python check
PY=$(command -v python3 || true)
if [[ -z "$PY" ]]; then
    echo "ERROR: python3 not found" >&2
    exit 1
fi
PY_VER=$("$PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)'; then
    echo "ERROR: python 3.9+ required, found $PY_VER" >&2
    exit 1
fi
echo "  ✓ python $PY_VER"

# 2. Substitute ${CLAUDE_PLUGIN_ROOT} in hooks/hooks.json
SNIPPET_RENDERED="$BUNDLE_ROOT/hooks/settings.json.rendered"
sed "s#\${CLAUDE_PLUGIN_ROOT}#$BUNDLE_ROOT#g" \
    "$BUNDLE_ROOT/hooks/hooks.json" \
    > "$SNIPPET_RENDERED"
echo "  ✓ rendered hook config → $SNIPPET_RENDERED"

# 3. Optional merge into ~/.claude/settings.json
if [[ -f "$CLAUDE_SETTINGS" ]]; then
    echo "  ℹ existing $CLAUDE_SETTINGS detected — manual merge required."
    echo "    Copy 'hooks' block from $SNIPPET_RENDERED into it."
else
    mkdir -p "$(dirname "$CLAUDE_SETTINGS")"
    cp "$SNIPPET_RENDERED" "$CLAUDE_SETTINGS"
    echo "  ✓ installed fresh $CLAUDE_SETTINGS"
fi

# 4. Optional refresh of offline OSV snapshot
if [[ "${SAFETY_ORCH_REFRESH_DB:-0}" == "1" ]]; then
    echo
    echo "Refreshing offline snapshot..."
    PYTHONPATH="$BUNDLE_ROOT" "$PY" -m helpers.cache_snapshot refresh-db \
        "${SAFETY_ORCH_OSV_SNAPSHOT_SOURCE:-}"
fi

# 5. Health banner
echo
echo "=== Health check ==="
PYTHONPATH="$BUNDLE_ROOT" "$PY" -m helpers.health_status

echo
echo "Done."
echo
echo "Next steps:"
echo "  1. (Optional) Copy .env.example to .env and fill in API keys for Tier-1 atoms."
echo "  2. (Optional) Set SAFETY_ORCH_OSV_SNAPSHOT_SOURCE to a validated indexed"
echo "     snapshot and SAFETY_ORCH_REFRESH_DB=1, then rerun."
echo "  3. Restart Claude Code to load the new hook config."
