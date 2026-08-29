#!/usr/bin/env bash
# Safety Orchestrator — Codex adapter installer.
# Installs the deterministic hook bridge into a Codex home and the safety
# skills into Codex's user skill directory.
#
# Usage:
#   ./install.sh                              # ~/.codex + ~/.agents/skills
#   HOME=/workspace/.work/home \
#     CODEX_HOME=/workspace/.work/codex-home \
#     ./install.sh                            # isolated workspace-local trial
#
# SAFE: never overwrites an existing hooks.json or config.toml — it writes a
# sidecar and tells you exactly what to merge. Skills with a name collision are
# skipped, not clobbered.

set -euo pipefail

ADAPTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The shared safety core lives at the repo root (adapters/codex/ -> ../..).
# Nothing is vendored under the adapter; we assemble the deployment from the
# SAME core the Claude Code plugin ships, so there is exactly one source of truth.
REPO_ROOT="$(cd "$ADAPTER_DIR/../.." && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CODEX_SKILLS_DIR="${SAFETY_ORCH_CODEX_SKILLS_DIR:-$HOME/.agents/skills}"
DEST="$CODEX_HOME/safety-orchestrator"

echo "Safety Orchestrator — Codex adapter installer"
echo "  adapter:    $ADAPTER_DIR"
echo "  CODEX_HOME: $CODEX_HOME"
echo "  skills:     $CODEX_SKILLS_DIR"
echo

# --- Python check ---
PY=$(command -v python3 || true)
[ -z "$PY" ] && { echo "ERROR: python3 not found" >&2; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' \
    || { echo "ERROR: python 3.9+ required, found $($PY --version)" >&2; exit 1; }
echo "  ✓ $("$PY" --version)"

if [ "$CODEX_HOME" = "$HOME/.codex" ]; then
    echo "  ⚠ Installing into your REAL ~/.codex. For a no-risk trial, rerun with:"
    echo "      HOME=\"\$PWD/.work/codex-user\" CODEX_HOME=\"\$PWD/.work/codex-home\" ./install.sh"
fi

# --- 1. bridge + shared core (assembled from the repo root, not vendored) ---
mkdir -p "$DEST/core/hooks"
cp "$ADAPTER_DIR/codex_hook.py" "$DEST/"
rm -rf "$DEST/core/hooks/scripts"; cp -r "$REPO_ROOT/hooks/scripts" "$DEST/core/hooks/scripts"
rm -rf "$DEST/core/helpers";      cp -r "$REPO_ROOT/helpers"      "$DEST/core/helpers"
cp "$REPO_ROOT/atoms.json" "$DEST/core/atoms.json"
find "$DEST" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
echo "  ✓ bridge + core (assembled from $REPO_ROOT) → $DEST"

# --- 2. skills (skip collisions) ---
# Current Codex discovers personal skills under $HOME/.agents/skills. The old
# $CODEX_HOME/skills path is not a current local-skill discovery location and
# can make a custom skill resolve incorrectly under skills/.system/.
mkdir -p "$CODEX_SKILLS_DIR"
for d in "$REPO_ROOT"/skills/*/; do
    name="$(basename "$d")"
    if [ -e "$CODEX_SKILLS_DIR/$name" ]; then
        echo "  · skill '$name' already present — skipped (remove it to update)"
    else
        cp -r "$d" "$CODEX_SKILLS_DIR/$name"
    fi
done
echo "  ✓ skills → $CODEX_SKILLS_DIR/"

# The shared Router invokes `python3 helpers/health_status.py` from its own
# skill directory. In the Codex deployment, helpers live in the assembled
# shared core rather than beside the skill. Link the skill-visible path back to
# that core so the command remains host-neutral without duplicating helpers.
ROUTER_SKILL="$CODEX_SKILLS_DIR/safety-router-skill"
ROUTER_HELPERS="$ROUTER_SKILL/helpers"
if [ -d "$ROUTER_SKILL" ] \
    && cmp -s "$REPO_ROOT/skills/safety-router-skill/SKILL.md" \
        "$ROUTER_SKILL/SKILL.md" \
    && [ ! -e "$ROUTER_HELPERS" ] \
    && [ ! -L "$ROUTER_HELPERS" ]; then
    ln -s "$DEST/core/helpers" "$ROUTER_HELPERS"
    echo "  ✓ Router health helper → $ROUTER_HELPERS"
fi

# --- 3. hooks.json (rendered with the absolute install path) ---
RENDERED="$(sed "s#__SAFETY_ADAPTER_ROOT__#$DEST#g" "$ADAPTER_DIR/hooks.json")"
if [ -f "$CODEX_HOME/hooks.json" ]; then
    printf '%s\n' "$RENDERED" > "$CODEX_HOME/hooks.json.safety-orchestrator"
    echo "  ℹ existing hooks.json found — wrote $CODEX_HOME/hooks.json.safety-orchestrator"
    echo "    Merge its \"hooks\" block into your hooks.json."
else
    printf '%s\n' "$RENDERED" > "$CODEX_HOME/hooks.json"
    echo "  ✓ hooks.json → $CODEX_HOME/hooks.json"
fi

# --- 4. backstop config (never auto-merged) ---
cp "$ADAPTER_DIR/config.backstop.toml" "$CODEX_HOME/config.backstop.toml"
echo "  ℹ backstop config → $CODEX_HOME/config.backstop.toml"
echo "    Review + merge into config.toml (covers hosted WebSearch / network"
echo "    atoms the PreToolUse hook cannot intercept)."

# --- 5. compile check ---
PYTHONDONTWRITEBYTECODE=1 "$PY" -m py_compile "$DEST/codex_hook.py" \
    "$DEST"/core/hooks/scripts/*.py && echo "  ✓ compiles"

echo
echo "Done. Ensure [features] hooks = true in config.toml, launch codex, then review /hooks."
echo "Quick test: HOME=$HOME CODEX_HOME=$CODEX_HOME codex exec --dangerously-bypass-hook-trust 'inspect the installed safety-router-skill'"
