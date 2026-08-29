#!/bin/bash
# Install FORGE git hooks into the current repo's .git/hooks directory.
# Idempotent: if a non-FORGE hook is already present, back it up to <name>.bak
# before installing. Run from the repo root or any subdirectory.

set -e

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "$REPO_ROOT" ]; then
  echo "install-forge-hooks: not inside a git repository."
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
SOURCE_DIR="$SCRIPT_DIR/../ci/hooks"
if [ ! -d "$SOURCE_DIR" ]; then
  echo "install-forge-hooks: source hooks not found at $SOURCE_DIR"
  exit 1
fi

TARGET_DIR="$REPO_ROOT/.git/hooks"
mkdir -p "$TARGET_DIR"

INSTALLED=()
BACKED_UP=()
SKIPPED=()

for hook in commit-msg pre-commit pre-push; do
  src="$SOURCE_DIR/$hook"
  tgt="$TARGET_DIR/$hook"

  if [ ! -f "$src" ]; then
    continue
  fi

  if [ -f "$tgt" ]; then
    if cmp -s "$src" "$tgt"; then
      SKIPPED+=("$hook")
      continue
    fi
    if grep -q '^# FORGE' "$tgt" 2>/dev/null; then
      cp "$src" "$tgt"
      chmod +x "$tgt"
      INSTALLED+=("$hook (updated)")
      continue
    fi
    cp "$tgt" "$tgt.bak"
    BACKED_UP+=("$hook -> $hook.bak")
  fi

  cp "$src" "$tgt"
  chmod +x "$tgt"
  INSTALLED+=("$hook")
done

echo "Installed: ${INSTALLED[*]:-none}"
[ ${#BACKED_UP[@]} -gt 0 ] && echo "Backed up: ${BACKED_UP[*]}"
[ ${#SKIPPED[@]} -gt 0 ] && echo "Already current: ${SKIPPED[*]}"
