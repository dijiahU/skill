#!/bin/bash
# Pilot container entrypoint.
# Runs inside the container at startup. Two modes (controlled by env BUNDLE_MODE):
#
#   BUNDLE_MODE=bundle   (default) — install full bundle: 1 router skill (with 14
#                                    archetype reference docs nested under it) + 8 matcher hooks
#   BUNDLE_MODE=vanilla            — empty .claude/, no hooks, no skills (baseline)
#
# Both modes drop to interactive bash with `claude` ready to invoke. The mode
# is printed in the banner so you don't confuse runs.

set -euo pipefail

BUNDLE_MODE="${BUNDLE_MODE:-bundle}"

# ----- Sanity check: bundle is mounted (only required for bundle mode) -----
if [ "$BUNDLE_MODE" = "bundle" ] && [ ! -d "$BUNDLE_PATH/skills" ]; then
    echo "ERROR: bundle not mounted at $BUNDLE_PATH" >&2
    echo "Did you run via pilot/run.sh? Or pass -v <host-bundle-path>:$BUNDLE_PATH:ro?" >&2
    exit 1
fi

# ----- Create fresh workspace -----
rm -rf "$PILOT_WORKSPACE"
mkdir -p "$PILOT_WORKSPACE/.claude"
cd "$PILOT_WORKSPACE"

# ----- Mode-specific setup -----
case "$BUNDLE_MODE" in
    bundle)
        mkdir -p .claude/skills
        # Link skills (read-only references; edits to host bundle visible after restart).
        # As of the v1.2 hierarchy refactor skills/ holds exactly ONE top-level skill —
        # safety-router-skill — whose references/archetypes/ holds the 14 archetype docs.
        for skill_dir in "$BUNDLE_PATH"/skills/*/; do
            skill_name="$(basename "$skill_dir")"
            ln -sfn "$skill_dir" ".claude/skills/$skill_name"
        done
        # Render settings.json with absolute bundle path
        sed "s#\${CLAUDE_PLUGIN_ROOT}#${BUNDLE_PATH}#g" \
            "$BUNDLE_PATH/hooks/hooks.json" \
            > .claude/settings.json
        # Validate rendered JSON
        if ! python3 -c "import json; json.load(open('.claude/settings.json'))" 2>/dev/null; then
            echo "ERROR: rendered .claude/settings.json is not valid JSON" >&2
            exit 1
        fi
        # Optional .env
        if [ -f "$BUNDLE_PATH/.env.example" ] && [ ! -f .env ]; then
            cp "$BUNDLE_PATH/.env.example" .env
        fi
        ;;
    vanilla)
        # No skills, no hooks. Empty settings.json with comment so we know why.
        cat > .claude/settings.json <<'EOF'
{
  "_comment": "VANILLA pilot mode: no Safety Orchestrator bundle. Used as A/B baseline to attribute blocks to bundle vs Claude Code built-in safety. See pilot/scenarios.md."
}
EOF
        ;;
    *)
        echo "ERROR: unknown BUNDLE_MODE='$BUNDLE_MODE' (expected 'bundle' or 'vanilla')" >&2
        exit 1
        ;;
esac

# ----- Pilot-specific permission mode (overrides Claude Code default) -----
# bypassPermissions skips the human-in-the-loop "allow tool call?" prompt so
# scenario testing (especially batch / benchmark-driven 4.7.2) doesn't stall
# on per-call approvals. Hooks still fire — the bundle's safety layer is
# unaffected; only the redundant human confirmation step is gone. Both bundle
# and vanilla modes need this for a fair A/B comparison (otherwise vanilla
# would block more "attacks" merely via permission prompts, inflating built-in
# safety credit and obscuring real bundle attribution).
# Written to settings.local.json (Claude Code merges this over settings.json)
# so the bundle's hook config in settings.json stays clean and
# production-compatible.
cat > .claude/settings.local.json <<'EOF'
{
  "_comment": "Pilot-only: bypassPermissions skips per-tool-call human approval. Hooks still fire. See pilot/entrypoint.sh for rationale.",
  "permissions": {
    "defaultMode": "bypassPermissions"
  }
}
EOF

# ----- Initialize git (Claude Code expects a git repo for some features) -----
if [ ! -d .git ]; then
    git init -q
    git config user.email "pilot@localhost" && git config user.name "Pilot Test"
    echo ".claude/" > .gitignore
    echo ".env" >> .gitignore
    echo ".audit/" >> .gitignore
    git add .gitignore && git commit -q -m "pilot init" || true
fi

# ----- Banner -----
if [ "$BUNDLE_MODE" = "bundle" ]; then
    cat <<'BANNER'

╔══════════════════════════════════════════════════════════════╗
║   Safety Orchestrator — Pilot Container [BUNDLE MODE]        ║
║                                                              ║
║   Bundle: 1 router skill (+14 archetype docs) + 8 hooks.     ║
║   Audit log → /home/pilot/.safety-orch/ (host: .audit-bundle)║
╚══════════════════════════════════════════════════════════════╝
BANNER

    echo
    # Seed the offline CVE snapshot stub so check-package-cve doesn't degrade
    # with "no offline snapshot". The stub is meta-only (per cache_snapshot.py:
    # production should replace with real osv-export.json from GCS, but for
    # pilot the stub satisfies the freshness check). ~/.cache/ is container-
    # local and wiped on exit, so we re-seed every startup. Failure non-fatal.
    python3 -m helpers.cache_snapshot refresh-db >/dev/null 2>&1 || true

    echo "=== Bundle health check ==="
    python3 -m helpers.health_status 2>&1 || echo "(health_status returned non-zero; some atoms may be degraded)"
    echo
    echo "=== Workspace ready ==="
    echo "  Top-level skills: $(ls .claude/skills/ | wc -l) (safety-router-skill; 14 archetype docs nested under references/archetypes/)"
    echo "  Archetype docs:   $(ls "$BUNDLE_PATH"/skills/safety-router-skill/references/archetypes/ 2>/dev/null | wc -l)"
    echo "  Hook entries:     $(jq '[.hooks | .[] | length] | add' .claude/settings.json) total"

else
    cat <<'BANNER'

╔══════════════════════════════════════════════════════════════╗
║   Safety Orchestrator — Pilot Container [VANILLA MODE]       ║
║                                                              ║
║   NO bundle / NO hooks / NO skills.                          ║
║   This is the A/B baseline — only Claude Code built-in       ║
║   safety is active. Run same scenarios as bundle mode then   ║
║   diff to attribute blocks to bundle vs built-in.            ║
║   Audit log → /home/pilot/.safety-orch/ (host: .audit-vanilla)║
╚══════════════════════════════════════════════════════════════╝
BANNER

    echo
    echo "=== Vanilla workspace ready ==="
    echo "  Skills:        none"
    echo "  Hook entries:  none (empty settings.json)"
fi

echo "  Workspace:        $PILOT_WORKSPACE"
echo "  Permission mode:  bypassPermissions (settings.local.json) — hooks still active"

# ----- Auth check -----
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "  Auth:             ANTHROPIC_API_KEY env (programmatic)"
elif [ -f "$HOME/.claude/.credentials.json" ]; then
    echo "  Auth:             mounted credentials.json (host OAuth)"
else
    echo "  Auth:             ⚠ NONE detected — run 'claude login' before invoking 'claude'"
fi

cat <<'NEXT'

=== Next steps ===
  1. `claude` to launch Claude Code TUI in this workspace
  2. Run scenarios from pilot/scenarios.md (same scenarios in both modes!)
  3. Exit (Ctrl-D), then check audit log:
       cat ~/.safety-orch/*.jsonl
  4. After running BOTH modes, build A/B comparison table per scenarios.md §A/B methodology

NEXT

exec bash
