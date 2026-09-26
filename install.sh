#!/usr/bin/env bash
# Agent Safety Orchestrator — unified installer.
#
# ONE safety core, multiple hosts. This dispatcher installs the same atom
# library onto whichever agent you run — Claude Code, OpenAI Codex, or both —
# by delegating to the per-host installer under adapters/<host>/.
#
# Usage:
#   ./install.sh                 # auto-detect installed agents, install for each
#   ./install.sh --host claude   # Claude Code only  (manual hook merge; or use /plugin)
#   ./install.sh --host codex    # OpenAI Codex only
#   ./install.sh --host both     # both
#   ./install.sh --list          # show what was detected, install nothing
#
# Isolated trials (keep all state in the current workspace):
#   HOME="$PWD/.work/codex-user" CODEX_HOME="$PWD/.work/codex-home" \
#     ./install.sh --host codex
#   CLAUDE_SETTINGS="$PWD/.work/claude/settings.json" ./install.sh --host claude

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; }

HOST="auto"
while [ $# -gt 0 ]; do
    case "$1" in
        --host)    HOST="${2:-}"; shift 2 ;;
        --host=*)  HOST="${1#*=}"; shift ;;
        claude|codex|both|auto) HOST="$1"; shift ;;
        --list)    HOST="list"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown argument: $1" >&2; echo; usage; exit 2 ;;
    esac
done

# --- detect installed agents (binary on PATH, or a home dir, or an env override) ---
have_claude=0; have_codex=0
if command -v claude >/dev/null 2>&1 || [ -d "$HOME/.claude" ] || [ -n "${CLAUDE_SETTINGS:-}" ]; then have_claude=1; fi
if command -v codex  >/dev/null 2>&1 || [ -d "$HOME/.codex" ]  || [ -n "${CODEX_HOME:-}" ];      then have_codex=1;  fi

echo "Agent Safety Orchestrator — unified installer"
echo "  repo:     $ROOT"
echo "  detected: Claude Code=$([ $have_claude = 1 ] && echo yes || echo no)   Codex=$([ $have_codex = 1 ] && echo yes || echo no)"
echo

run_claude() { echo "=== Claude Code ==="; bash "$ROOT/adapters/claude/install.sh"; }
run_codex()  { echo "=== Codex ==="; bash "$ROOT/adapters/codex/install.sh"; }

case "$HOST" in
    list)
        echo "Detected agents listed above. Nothing installed (--list)."
        ;;
    claude) run_claude ;;
    codex)  run_codex ;;
    both)   run_claude; echo; run_codex ;;
    auto)
        did=0
        [ $have_claude = 1 ] && { run_claude; did=1; }
        [ $have_codex  = 1 ] && { [ $did = 1 ] && echo; run_codex; did=1; }
        if [ $did = 0 ]; then
            echo "No supported agent detected (looked for the claude/codex binary, ~/.claude, ~/.codex)."
            echo "Install explicitly:   ./install.sh --host claude | codex | both"
            echo "Isolated trial:       HOME=\"\$PWD/.work/codex-user\" CODEX_HOME=\"\$PWD/.work/codex-home\" ./install.sh --host codex"
            exit 1
        fi
        ;;
    *) echo "unknown --host '$HOST' (use: claude | codex | both | auto)" >&2; exit 2 ;;
esac

echo
echo "All done."
