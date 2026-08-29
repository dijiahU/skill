#!/bin/bash
# FORGE CI: Verify that required evidence artifacts were modified in the PR.
# Skipped for Lightweight mode. Required for Mid and above.

set -e

BASE_REF="${GITHUB_BASE_REF:-main}"
AI_MD="docs/forge/AI.md"

# Read FORGE mode and ci_enforcement from AI.md
FORGE_MODE=""
CI_ENFORCEMENT=""
TASK_SOURCE="local"

if [ -f "$AI_MD" ]; then
  FORGE_MODE=$(grep 'FORGE_mode:' "$AI_MD" | sed 's/.*FORGE_mode: *//' | sed 's/[[:space:]]*$//')
  CI_ENFORCEMENT=$(grep 'ci_enforcement:' "$AI_MD" | sed 's/.*ci_enforcement: *//' | sed 's/[[:space:]]*$//')
  TASK_SOURCE=$(grep 'task_source:' "$AI_MD" | sed 's/.*task_source: *//' | sed 's/[[:space:]]*$//')
  [ -z "$TASK_SOURCE" ] && TASK_SOURCE="local"
fi

# Skip if ci_enforcement is not explicitly enabled
if [ "$CI_ENFORCEMENT" != "enabled" ]; then
  echo "FORGE: ci_enforcement not enabled in AI.md - evidence artifact check skipped."
  exit 0
fi

CHANGED_FILES=$(git diff "origin/${BASE_REF}..HEAD" --name-only)
TASK_STATE_CHANGED=0
TASK_REFERENCED=0
FAILED=0

if echo "$CHANGED_FILES" | grep -q "^docs/forge/TASKS.yaml$"; then
  TASK_STATE_CHANGED=1
fi

if git log "origin/${BASE_REF}..HEAD" --format=%B | grep -q "^FORGE-task:"; then
  TASK_REFERENCED=1
fi

check_artifact() {
  local artifact="$1"
  if echo "$CHANGED_FILES" | grep -q "^${artifact}$"; then
    echo "FORGE: $artifact updated."
  else
    echo "FORGE: Required evidence artifact not updated: $artifact"
    FAILED=1
  fi
}

if [ "$TASK_STATE_CHANGED" -eq 1 ] || [ "$TASK_REFERENCED" -eq 1 ]; then
  check_artifact "docs/forge/EVALUATION.md"
elif [ "$FORGE_MODE" = "Lightweight" ] || [ -z "$FORGE_MODE" ]; then
  echo "FORGE: Mode is Lightweight and no task transition detected - evidence artifact check skipped."
  exit 0
fi

if [ "$FORGE_MODE" != "Lightweight" ] && [ -n "$FORGE_MODE" ]; then
  check_artifact "docs/forge/MEMORY.md"
fi

# Strict and Full Discipline also require TASKS.yaml to be updated
if { [ "$FORGE_MODE" = "Strict" ] || [ "$FORGE_MODE" = "Full Discipline" ]; } && [ "$TASK_SOURCE" = "local" ]; then
  check_artifact "docs/forge/TASKS.yaml"
fi

if [ "$FAILED" -ne 0 ]; then
  echo ""
  echo "FORGE: Evidence artifact validation failed."
  echo "  All required governance documents must be updated in the same PR as the task work."
  exit 1
fi

echo "FORGE: Evidence artifact validation passed."
