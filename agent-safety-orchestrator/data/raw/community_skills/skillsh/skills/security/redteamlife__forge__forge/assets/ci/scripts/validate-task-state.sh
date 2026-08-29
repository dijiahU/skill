#!/bin/bash
# FORGE CI: Verify that every task referenced via FORGE-task trailer
# has status: complete in TASKS.yaml at the time of the PR.

set -e

BASE_REF="${GITHUB_BASE_REF:-main}"
AI_MD="docs/forge/AI.md"
TASKS_FILE="docs/forge/TASKS.yaml"

INTEGRATION_BRANCH="develop"
RELEASE_BRANCH="main"
TASK_SOURCE="local"

if [ -f "$AI_MD" ]; then
  INTEGRATION_BRANCH=$(grep 'integration_branch:' "$AI_MD" | sed 's/.*integration_branch: *//' | sed 's/[[:space:]]*$//' || true)
  RELEASE_BRANCH=$(grep 'release_branch:' "$AI_MD" | sed 's/.*release_branch: *//' | sed 's/[[:space:]]*$//' || true)
  TASK_SOURCE=$(grep 'task_source:' "$AI_MD" | sed 's/.*task_source: *//' | sed 's/[[:space:]]*$//' || true)
  [ -z "$INTEGRATION_BRANCH" ] && INTEGRATION_BRANCH="develop"
  [ -z "$RELEASE_BRANCH" ] && RELEASE_BRANCH="main"
  [ -z "$TASK_SOURCE" ] && TASK_SOURCE="local"
fi

if [ "$TASK_SOURCE" != "local" ]; then
  echo "FORGE: task_source is $TASK_SOURCE - local TASKS.yaml state validation skipped."
  exit 0
fi

if [ ! -f "$TASKS_FILE" ]; then
  echo "FORGE: $TASKS_FILE not found - skipping task state validation."
  exit 0
fi

COMMIT_HASHES=$(git log "origin/${BASE_REF}..HEAD" --format="%H")

if [ -z "$COMMIT_HASHES" ]; then
  echo "FORGE: No commits to validate."
  exit 0
fi

FAILED=0

while IFS= read -r hash; do
  SUBJECT=$(git log --format="%s" -1 "$hash")
  FULL_MSG=$(git log --format="%B" -1 "$hash")

  # Skip merge commits
  if echo "$SUBJECT" | grep -qE "^(Merge |Revert \")"; then
    continue
  fi

  # Extract FORGE-task trailer
  TASK_ID=$(echo "$FULL_MSG" | grep "^FORGE-task:" | sed 's/^FORGE-task: *//' | sed 's/[[:space:]]*$//')

  if [ -z "$TASK_ID" ]; then
    continue
  fi

  # Use Python to check task status in TASKS.yaml
  STATUS=$(python3 - "$TASKS_FILE" "$TASK_ID" <<'EOF'
import sys
import yaml

tasks_file = sys.argv[1]
task_id = sys.argv[2]

with open(tasks_file) as f:
    data = yaml.safe_load(f)

tasks = data.get("tasks", []) if data else []
for task in tasks:
    if str(task.get("id", "")) == task_id:
        print(task.get("status", "not_found"))
        sys.exit(0)

print("not_found")
EOF
)

  if [ "$BASE_REF" = "$RELEASE_BRANCH" ]; then
    if [ "$STATUS" = "integrated" ] || [ "$STATUS" = "complete" ]; then
      echo "FORGE: Task '$TASK_ID' is ready for release branch merge (status: $STATUS)."
    elif [ "$STATUS" = "not_found" ]; then
      echo "FORGE: Task '$TASK_ID' not found in $TASKS_FILE."
      FAILED=1
    else
      echo "FORGE: Task '$TASK_ID' is not ready for release branch merge (status: $STATUS)."
      FAILED=1
    fi
  elif [ "$BASE_REF" = "$INTEGRATION_BRANCH" ]; then
    if [ "$STATUS" = "implemented" ] || [ "$STATUS" = "integrated" ] || [ "$STATUS" = "complete" ]; then
      echo "FORGE: Task '$TASK_ID' is ready for integration branch merge (status: $STATUS)."
    elif [ "$STATUS" = "not_found" ]; then
      echo "FORGE: Task '$TASK_ID' not found in $TASKS_FILE."
      FAILED=1
    else
      echo "FORGE: Task '$TASK_ID' is not ready for integration branch merge (status: $STATUS)."
      FAILED=1
    fi
  elif [ "$STATUS" = "complete" ]; then
    echo "FORGE: Task '$TASK_ID' is complete."
  elif [ "$STATUS" = "not_found" ]; then
    echo "FORGE: Task '$TASK_ID' not found in $TASKS_FILE."
    FAILED=1
  else
    echo "FORGE: Task '$TASK_ID' is not complete (status: $STATUS)."
    FAILED=1
  fi
done <<< "$COMMIT_HASHES"

if [ "$FAILED" -ne 0 ]; then
  echo ""
  echo "FORGE: Task state validation failed. All tasks in FORGE-task trailers must be marked complete in $TASKS_FILE."
  exit 1
fi

echo "FORGE: Task state validation passed."
