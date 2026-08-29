#!/bin/bash
# FORGE helper: validate task-branch closeout expectations before integration or release.

set -euo pipefail

AI_MD="docs/forge/AI.md"
TASKS_FILE="docs/forge/TASKS.yaml"
TARGET="integration"
TASK_ID=""
REQUIRE_CLEAN="yes"

usage() {
  cat <<'EOF'
Usage: bash ci/scripts/verify-team-closeout.sh [--task <task-id>] [--target integration|release] [--allow-dirty]

Validates local task closeout against docs/forge/AI.md and docs/forge/TASKS.yaml.
If --task is omitted, the helper uses the latest FORGE-task trailer on the current branch.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --task)
      TASK_ID="${2:-}"
      shift 2
      ;;
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --allow-dirty)
      REQUIRE_CLEAN="no"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "FORGE: Unknown argument '$1'."
      usage
      exit 1
      ;;
  esac
done

if [ ! -f "$AI_MD" ] || [ ! -f "$TASKS_FILE" ]; then
  echo "FORGE: Missing $AI_MD or $TASKS_FILE."
  exit 1
fi

COLLABORATION_MODE=$(grep 'collaboration_mode:' "$AI_MD" | sed 's/.*collaboration_mode: *//' | sed 's/[[:space:]]*$//' || true)
INTEGRATION_BRANCH=$(grep 'integration_branch:' "$AI_MD" | sed 's/.*integration_branch: *//' | sed 's/[[:space:]]*$//' || true)
RELEASE_BRANCH=$(grep 'release_branch:' "$AI_MD" | sed 's/.*release_branch: *//' | sed 's/[[:space:]]*$//' || true)
[ -z "$INTEGRATION_BRANCH" ] && INTEGRATION_BRANCH="develop"
[ -z "$RELEASE_BRANCH" ] && RELEASE_BRANCH="main"

if [ "$COLLABORATION_MODE" != "team" ]; then
  echo "FORGE: collaboration_mode is not team."
  exit 1
fi

if [ "$TARGET" != "integration" ] && [ "$TARGET" != "release" ]; then
  echo "FORGE: --target must be integration or release."
  exit 1
fi

if [ "$REQUIRE_CLEAN" = "yes" ] && [ -n "$(git status --porcelain)" ]; then
  echo "FORGE: Working tree is not clean. Commit or stash changes before closeout."
  exit 1
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ -z "$TASK_ID" ]; then
  TASK_ID=$(git log --format="%B" --no-merges | grep -m 1 "^FORGE-task:" | sed 's/^FORGE-task: *//' | sed 's/[[:space:]]*$//' || true)
fi

if [ -z "$TASK_ID" ]; then
  echo "FORGE: Could not infer task id. Pass --task <task-id>."
  exit 1
fi

TASK_JSON=$(python3 - "$TASKS_FILE" "$TASK_ID" <<'EOF'
import json
import sys
import yaml

tasks_file = sys.argv[1]
task_id = sys.argv[2]

with open(tasks_file) as f:
    data = yaml.safe_load(f) or {}

for task in data.get("tasks", []):
    if str(task.get("id", "")) == task_id:
        print(json.dumps(task))
        sys.exit(0)

sys.exit(1)
EOF
) || {
  echo "FORGE: Task '$TASK_ID' not found in $TASKS_FILE."
  exit 1
}

STATUS=$(printf '%s' "$TASK_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))')
TASK_BRANCH=$(printf '%s' "$TASK_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("branch",""))')
CLAIM_RELEASED_BY=$(printf '%s' "$TASK_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("claim_released_by",""))')
CLAIM_RELEASED_AT=$(printf '%s' "$TASK_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("claim_released_at",""))')

if [ "$TARGET" = "integration" ]; then
  if [ -n "$TASK_BRANCH" ] && [ "$CURRENT_BRANCH" != "$TASK_BRANCH" ]; then
    echo "FORGE: Current branch '$CURRENT_BRANCH' does not match task branch '$TASK_BRANCH'."
    exit 1
  fi
  case "$STATUS" in
    implemented|integrated|complete) ;;
    *)
      echo "FORGE: Task '$TASK_ID' is not ready for integration closeout (status: $STATUS)."
      exit 1
      ;;
  esac
  TARGET_BRANCH="$INTEGRATION_BRANCH"
else
  case "$STATUS" in
    integrated|complete) ;;
    *)
      echo "FORGE: Task '$TASK_ID' is not ready for release closeout (status: $STATUS)."
      exit 1
      ;;
  esac
  TARGET_BRANCH="$RELEASE_BRANCH"
fi

COMMIT_RANGE="HEAD"
if git rev-parse --verify "$TARGET_BRANCH" >/dev/null 2>&1; then
  MERGE_BASE=$(git merge-base HEAD "$TARGET_BRANCH")
  COMMIT_RANGE="${MERGE_BASE}..HEAD"
fi

if ! git log --no-merges --format="%B" "$COMMIT_RANGE" | grep -q "^FORGE-task: ${TASK_ID}$"; then
  echo "FORGE: No task-scoped commit found for '$TASK_ID' between $COMMIT_RANGE."
  exit 1
fi

if [ "$TARGET" = "release" ] && [ -z "$CLAIM_RELEASED_AT" ]; then
  echo "FORGE: Task '$TASK_ID' does not record claim release metadata yet."
  echo "  Record claim_released_at and claim_released_by when the task becomes integrated."
  exit 1
fi

if [ "$TARGET" = "release" ] && [ -z "$CLAIM_RELEASED_BY" ]; then
  echo "FORGE: Task '$TASK_ID' does not record claim_released_by yet."
  exit 1
fi

echo "FORGE: Team closeout validation passed."
echo "  task: $TASK_ID"
echo "  source branch: $CURRENT_BRANCH"
echo "  target branch: $TARGET_BRANCH"
echo "  status: $STATUS"
