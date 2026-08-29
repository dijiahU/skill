#!/bin/bash
# FORGE CI: Validate task claiming and branch metadata for collaboration_mode: team.

set -e

BASE_REF="${GITHUB_BASE_REF:-main}"
HEAD_REF="${GITHUB_HEAD_REF:-$(git rev-parse --abbrev-ref HEAD)}"
AI_MD="docs/forge/AI.md"
TASKS_FILE="docs/forge/TASKS.yaml"
INTEGRATION_BRANCH="develop"
RELEASE_BRANCH="main"
TASK_SOURCE="local"

if [ ! -f "$AI_MD" ]; then
  echo "FORGE: $AI_MD not found - skipping team task metadata validation."
  exit 0
fi

COLLABORATION_MODE=$(grep 'collaboration_mode:' "$AI_MD" | sed 's/.*collaboration_mode: *//' | sed 's/[[:space:]]*$//' || true)
CI_ENFORCEMENT=$(grep 'ci_enforcement:' "$AI_MD" | sed 's/.*ci_enforcement: *//' | sed 's/[[:space:]]*$//' || true)
TASK_SOURCE=$(grep 'task_source:' "$AI_MD" | sed 's/.*task_source: *//' | sed 's/[[:space:]]*$//' || true)
INTEGRATION_BRANCH=$(grep 'integration_branch:' "$AI_MD" | sed 's/.*integration_branch: *//' | sed 's/[[:space:]]*$//' || true)
RELEASE_BRANCH=$(grep 'release_branch:' "$AI_MD" | sed 's/.*release_branch: *//' | sed 's/[[:space:]]*$//' || true)
[ -z "$TASK_SOURCE" ] && TASK_SOURCE="local"
[ -z "$INTEGRATION_BRANCH" ] && INTEGRATION_BRANCH="develop"
[ -z "$RELEASE_BRANCH" ] && RELEASE_BRANCH="main"

if [ "$COLLABORATION_MODE" != "team" ]; then
  echo "FORGE: collaboration_mode is not team - team task metadata validation skipped."
  exit 0
fi

if [ "$CI_ENFORCEMENT" != "enabled" ]; then
  echo "FORGE: collaboration_mode is team but ci_enforcement is not enabled."
  echo "  Enable ci_enforcement: enabled in docs/forge/AI.md for shared-repo workflows."
  exit 1
fi

if [ "$TASK_SOURCE" != "local" ]; then
  echo "FORGE: task_source is $TASK_SOURCE - local TASKS.yaml team metadata validation skipped."
  echo "FORGE: validate issue assignment, labels, and reviewer evidence through the hosting platform."
  exit 0
fi

if [ ! -f "$TASKS_FILE" ]; then
  echo "FORGE: $TASKS_FILE not found - team task metadata validation failed."
  exit 1
fi

COMMIT_HASHES=$(git log "origin/${BASE_REF}..HEAD" --format="%H")

if [ -z "$COMMIT_HASHES" ]; then
  echo "FORGE: No commits to validate."
  exit 0
fi

TASK_IDS=""
while IFS= read -r hash; do
  SUBJECT=$(git log --format="%s" -1 "$hash")
  FULL_MSG=$(git log --format="%B" -1 "$hash")

  if echo "$SUBJECT" | grep -qE "^(Merge |Revert \")"; then
    continue
  fi

  TASK_ID=$(echo "$FULL_MSG" | grep "^FORGE-task:" | sed 's/^FORGE-task: *//' | sed 's/[[:space:]]*$//')
  if [ -n "$TASK_ID" ]; then
    TASK_IDS="${TASK_IDS}${TASK_ID}"$'\n'
  fi
done <<< "$COMMIT_HASHES"

TASK_IDS=$(printf "%s" "$TASK_IDS" | awk 'NF && !seen[$0]++')

if [ -z "$TASK_IDS" ]; then
  echo "FORGE: No FORGE-task trailers found - team task metadata validation skipped."
  exit 0
fi

TASK_IDS_PAYLOAD="$TASK_IDS" python3 - "$TASKS_FILE" "$HEAD_REF" "$BASE_REF" "$INTEGRATION_BRANCH" "$RELEASE_BRANCH" <<'EOF'
import sys
import os
import yaml

tasks_file = sys.argv[1]
head_ref = sys.argv[2]
base_ref = sys.argv[3]
integration_branch = sys.argv[4]
release_branch = sys.argv[5]
task_ids = [line.strip() for line in os.environ.get("TASK_IDS_PAYLOAD", "").splitlines() if line.strip()]

with open(tasks_file) as f:
    data = yaml.safe_load(f) or {}

tasks = {str(task.get("id", "")): task for task in data.get("tasks", [])}
failed = False

for task_id in task_ids:
    task = tasks.get(task_id)
    if not task:
        print(f"FORGE: Task '{task_id}' not found in {tasks_file}.")
        failed = True
        continue

    status = task.get("status")
    file_scope = task.get("file_scope")
    claimed_by = task.get("claimed_by")
    claimed_by_email = task.get("claimed_by_email")
    agent = task.get("agent")
    claimed_at = task.get("claimed_at")
    claim_commit = task.get("claim_commit")
    branch = task.get("branch")
    claim_released_by = task.get("claim_released_by")
    claim_released_at = task.get("claim_released_at")

    if base_ref == integration_branch:
        if status not in ("implemented", "integrated", "complete"):
            print(f"FORGE: Team task '{task_id}' must be at least implemented before merge to integration (status: {status}).")
            failed = True
    elif base_ref == release_branch:
        if status not in ("integrated", "complete"):
            print(f"FORGE: Team task '{task_id}' must be integrated before merge to release (status: {status}).")
            failed = True
    elif status != "complete":
        print(f"FORGE: Team task '{task_id}' must be complete before merge (status: {status}).")
        failed = True

    if not file_scope:
        print(f"FORGE: Team task '{task_id}' must declare file_scope.")
        failed = True

    if not claimed_by:
        print(f"FORGE: Team task '{task_id}' is missing claimed_by.")
        failed = True

    if not claimed_by_email:
        print(f"FORGE: Team task '{task_id}' is missing claimed_by_email.")
        failed = True

    if not agent:
        print(f"FORGE: Team task '{task_id}' is missing agent.")
        failed = True

    if not claimed_at:
        print(f"FORGE: Team task '{task_id}' is missing claimed_at.")
        failed = True

    if not claim_commit:
        print(f"FORGE: Team task '{task_id}' is missing claim_commit.")
        failed = True

    if not branch:
        print(f"FORGE: Team task '{task_id}' is missing branch.")
        failed = True
    elif str(branch).strip() != head_ref:
        print(f"FORGE: Team task '{task_id}' branch '{branch}' does not match PR branch '{head_ref}'.")
        failed = True

    if status in ("integrated", "complete"):
        if not claim_released_by:
            print(f"FORGE: Team task '{task_id}' is missing claim_released_by for status '{status}'.")
            failed = True
        if not claim_released_at:
            print(f"FORGE: Team task '{task_id}' is missing claim_released_at for status '{status}'.")
            failed = True

if failed:
    sys.exit(1)
EOF

echo "FORGE: Team task metadata validation passed."
