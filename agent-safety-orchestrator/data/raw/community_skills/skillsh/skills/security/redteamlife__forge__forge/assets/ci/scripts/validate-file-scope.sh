#!/bin/bash
# FORGE CI: Validate that each commit only modifies files within the task's declared file_scope.
# If a task has no file_scope declared, validation is skipped for that task.
# Skipped entirely for Lightweight mode.

set -e

BASE_REF="${GITHUB_BASE_REF:-main}"
AI_MD="docs/forge/AI.md"
TASKS_FILE="docs/forge/TASKS.yaml"

# Read FORGE mode from AI.md
FORGE_MODE=""
COLLABORATION_MODE=""
TASK_SOURCE="local"
if [ -f "$AI_MD" ]; then
  FORGE_MODE=$(grep 'FORGE_mode:' "$AI_MD" | sed 's/.*FORGE_mode: *//' | sed 's/[[:space:]]*$//')
  COLLABORATION_MODE=$(grep 'collaboration_mode:' "$AI_MD" | sed 's/.*collaboration_mode: *//' | sed 's/[[:space:]]*$//')
  TASK_SOURCE=$(grep 'task_source:' "$AI_MD" | sed 's/.*task_source: *//' | sed 's/[[:space:]]*$//')
  [ -z "$TASK_SOURCE" ] && TASK_SOURCE="local"
fi

if [ "$TASK_SOURCE" != "local" ]; then
  echo "FORGE: task_source is $TASK_SOURCE - local TASKS.yaml file-scope validation skipped."
  echo "FORGE: validate issue-backed scope through issue metadata and review evidence."
  exit 0
fi

# Skip for Lightweight mode only when not in team collaboration mode.
if [ "$COLLABORATION_MODE" != "team" ] && { [ "$FORGE_MODE" = "Lightweight" ] || [ -z "$FORGE_MODE" ]; }; then
  echo "FORGE: Mode is Lightweight or unset - file scope validation skipped."
  exit 0
fi

if [ ! -f "$TASKS_FILE" ]; then
  echo "FORGE: $TASKS_FILE not found - skipping file scope validation."
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

  TASK_ID=$(echo "$FULL_MSG" | grep "^FORGE-task:" | sed 's/^FORGE-task: *//' | sed 's/[[:space:]]*$//')

  if [ -z "$TASK_ID" ]; then
    continue
  fi

  # Get file_scope for this task from TASKS.yaml
  FILE_SCOPE=$(python3 - "$TASKS_FILE" "$TASK_ID" <<'EOF'
import sys
import yaml

tasks_file = sys.argv[1]
task_id = sys.argv[2]

with open(tasks_file) as f:
    data = yaml.safe_load(f)

tasks = data.get("tasks", []) if data else []
for task in tasks:
    if str(task.get("id", "")) == task_id:
        scope = task.get("file_scope")
        if scope:
            for entry in scope:
                print(str(entry))
        sys.exit(0)
EOF
)

  # If no file_scope declared, skip only outside team mode
  if [ -z "$FILE_SCOPE" ]; then
    if [ "$COLLABORATION_MODE" = "team" ]; then
      echo "FORGE: Task '$TASK_ID' has no file_scope declared - required in collaboration_mode: team."
      FAILED=1
      continue
    else
      echo "FORGE: Task '$TASK_ID' has no file_scope declared - skipping scope check."
      continue
    fi
  fi

  # Get files changed in this specific commit
  CHANGED_FILES=$(git diff-tree --no-commit-id -r --name-only "$hash")

  TASK_FAILED=0
  while IFS= read -r changed_file; do
    MATCHED=0
    while IFS= read -r scope_entry; do
      # Match if the changed file starts with the scope entry (path prefix)
      if echo "$changed_file" | grep -q "^${scope_entry}"; then
        MATCHED=1
        break
      fi
    done <<< "$FILE_SCOPE"

    if [ "$MATCHED" -eq 0 ]; then
      echo "FORGE: File '$changed_file' in commit ${hash:0:8} (task: $TASK_ID) is outside declared file_scope."
      TASK_FAILED=1
    fi
  done <<< "$CHANGED_FILES"

  if [ "$TASK_FAILED" -eq 0 ]; then
    echo "FORGE: Task '$TASK_ID' - all changed files within declared file_scope."
  else
    FAILED=1
  fi
done <<< "$COMMIT_HASHES"

if [ "$FAILED" -ne 0 ]; then
  echo ""
  echo "FORGE: File scope validation failed."
  echo "  Files changed outside declared file_scope in TASKS.yaml."
  echo "  Either update the task's file_scope or keep changes within declared boundaries."
  exit 1
fi

echo "FORGE: File scope validation passed."
