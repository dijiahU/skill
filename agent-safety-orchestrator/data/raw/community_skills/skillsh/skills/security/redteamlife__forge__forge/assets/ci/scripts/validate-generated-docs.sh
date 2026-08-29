#!/bin/bash
# FORGE CI: Validate that generated documentation files are complete and not template artifacts.
# Checks for unfilled placeholders, empty required sections, and missing required files.
# Intended to run as a setup gate and on every PR.

set -e

FORGE_DIR="docs/forge"
FAILED=0

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

check_file_exists() {
  local file="$1"
  if [ ! -f "$file" ]; then
    echo "FORGE: Missing required file: $file"
    FAILED=1
    return 1
  fi
  return 0
}

check_no_placeholders() {
  local file="$1"
  # Match common template placeholder patterns
  if grep -qE '\{\{[^}]+\}\}|<[A-Z][A-Z _]+>|\[TODO\]|\[PLACEHOLDER\]|\[YOUR_' "$file" 2>/dev/null; then
    echo "FORGE: Unfilled template placeholders found in: $file"
    grep -nE '\{\{[^}]+\}\}|<[A-Z][A-Z _]+>|\[TODO\]|\[PLACEHOLDER\]|\[YOUR_' "$file" | head -5
    FAILED=1
  fi
}

check_section_nonempty() {
  local file="$1"
  local heading="$2"
  # Find the heading line; check if the next non-blank line is another heading or EOF
  local content
  content=$(awk "
    /^#+ ${heading}/ { found=1; next }
    found && /^[[:space:]]*$/ { next }
    found && /^#/ { exit }
    found { print; exit }
  " "$file")
  if [ -z "$content" ]; then
    echo "FORGE: Required section '$heading' is empty in: $file"
    FAILED=1
  fi
}

check_yaml_field_nonempty() {
  local file="$1"
  local field="$2"
  local value
  value=$(python3 - "$file" "$field" <<'EOF'
import sys
import yaml

with open(sys.argv[1]) as f:
    data = yaml.safe_load(f)

field = sys.argv[2]
val = data.get(field) if data else None
print("" if val is None else str(val).strip())
EOF
)
  if [ -z "$value" ]; then
    echo "FORGE: Required YAML field '$field' is missing or empty in: $file"
    FAILED=1
  fi
}

# -----------------------------------------------------------------------
# Check required files exist
# -----------------------------------------------------------------------

REQUIRED_FILES=(
  "$FORGE_DIR/AI.md"
  "$FORGE_DIR/TASKS.yaml"
)

AI_MD="$FORGE_DIR/AI.md"
FORGE_MODE=""
COLLABORATION_MODE=""

if [ -f "$AI_MD" ]; then
  FORGE_MODE=$(grep 'FORGE_mode:' "$AI_MD" | sed 's/.*FORGE_mode: *//' | sed 's/[[:space:]]*$//')
  COLLABORATION_MODE=$(grep 'collaboration_mode:' "$AI_MD" | sed 's/.*collaboration_mode: *//' | sed 's/[[:space:]]*$//')
fi

# Mid and above require additional files
if [ "$FORGE_MODE" != "Lightweight" ] && [ -n "$FORGE_MODE" ]; then
  REQUIRED_FILES+=(
    "$FORGE_DIR/ARCHITECTURE.md"
    "$FORGE_DIR/TEST_STRATEGY.md"
    "$FORGE_DIR/EVALUATION.md"
    "$FORGE_DIR/MEMORY.md"
    "$FORGE_DIR/SECURITY_CHECKLISTS.md"
  )
fi

# Strict and above
if [ "$FORGE_MODE" = "Strict" ] || [ "$FORGE_MODE" = "Full Discipline" ]; then
  REQUIRED_FILES+=(
    "$FORGE_DIR/ARCHITECTURE_EXPLORATION.md"
    "$FORGE_DIR/REVIEW_GUIDE.md"
    "$FORGE_DIR/ROADMAP.md"
  )
fi

# Team collaboration requires explicit coordination docs.
if [ "$COLLABORATION_MODE" = "team" ]; then
  REQUIRED_FILES+=(
    "$FORGE_DIR/TEAM.md"
    "$FORGE_DIR/SECURITY_CHECKLISTS.md"
    "$FORGE_DIR/EVALUATION.md"
    "$FORGE_DIR/MEMORY.md"
  )
fi

FILES_OK=1
for f in "${REQUIRED_FILES[@]}"; do
  check_file_exists "$f" || FILES_OK=0
done

# If files are missing, report and exit - no point checking content
if [ "$FILES_OK" -eq 0 ]; then
  echo ""
  echo "FORGE: Required documentation files are missing. Bootstrap or refresh docs/forge with the forge skill before proceeding."
  exit 1
fi

# -----------------------------------------------------------------------
# Check for unfilled template placeholders in each required file
# -----------------------------------------------------------------------

for f in "${REQUIRED_FILES[@]}"; do
  [ -f "$f" ] && check_no_placeholders "$f"
done

# -----------------------------------------------------------------------
# Check required sections are non-empty
# -----------------------------------------------------------------------

check_section_nonempty "$FORGE_DIR/AI.md" "Purpose"
check_section_nonempty "$FORGE_DIR/AI.md" "Constraints"

if [ -f "$FORGE_DIR/ARCHITECTURE.md" ]; then
  check_section_nonempty "$FORGE_DIR/ARCHITECTURE.md" "Overview"
fi

if [ -f "$FORGE_DIR/EVALUATION.md" ]; then
  check_section_nonempty "$FORGE_DIR/EVALUATION.md" "Definition of Done"
fi

if [ -f "$FORGE_DIR/TEAM.md" ]; then
  check_section_nonempty "$FORGE_DIR/TEAM.md" "Branch Policy"
  check_section_nonempty "$FORGE_DIR/TEAM.md" "Task Claiming"
  check_section_nonempty "$FORGE_DIR/TEAM.md" "Task Ledger Semantics"
  check_section_nonempty "$FORGE_DIR/TEAM.md" "Integration Flow"
  check_section_nonempty "$FORGE_DIR/TEAM.md" "File Scope"
  check_section_nonempty "$FORGE_DIR/TEAM.md" "Task Closeout"
  check_section_nonempty "$FORGE_DIR/TEAM.md" "Review And Merge"
fi

if [ -f "$FORGE_DIR/SETUP.md" ]; then
  check_section_nonempty "$FORGE_DIR/SETUP.md" "Local Hooks"
  check_section_nonempty "$FORGE_DIR/SETUP.md" "CI Enforcement"
  check_section_nonempty "$FORGE_DIR/SETUP.md" "Branch Protection"
  check_section_nonempty "$FORGE_DIR/SETUP.md" "Team Closeout"
  check_section_nonempty "$FORGE_DIR/SETUP.md" "Release Reconciliation"
fi

# -----------------------------------------------------------------------
# Check TASKS.yaml structure
# -----------------------------------------------------------------------

TASKS_FILE="$FORGE_DIR/TASKS.yaml"
if [ -f "$TASKS_FILE" ]; then
  python3 - "$TASKS_FILE" <<'EOF'
import sys
import yaml

with open(sys.argv[1]) as f:
    data = yaml.safe_load(f)

tasks = data.get("tasks", []) if data else []
if not tasks:
    print("FORGE: TASKS.yaml contains no tasks.")
    sys.exit(1)

failed = False
for task in tasks:
    tid = task.get("id")
    desc = task.get("description")
    status = task.get("status")
    if not tid or str(tid).strip() == "":
        print(f"FORGE: A task is missing an 'id' field.")
        failed = True
    if not desc or str(desc).strip() == "":
        print(f"FORGE: Task '{tid}' is missing a 'description'.")
        failed = True
    if status not in ("incomplete", "claimed", "in_progress", "implemented", "integrated", "blocked", "complete"):
        print(f"FORGE: Task '{tid}' has invalid status '{status}'. Must be one of incomplete, claimed, in_progress, implemented, integrated, blocked, complete.")
        failed = True

if failed:
    sys.exit(1)
EOF
  TASKS_OK=$?
  if [ "$TASKS_OK" -ne 0 ]; then
    FAILED=1
  fi
fi

# -----------------------------------------------------------------------
# Check AI.md FORGE-config block has required fields
# -----------------------------------------------------------------------

if grep -q 'FORGE-config' "$AI_MD"; then
  if ! grep -q 'FORGE_mode:' "$AI_MD"; then
    echo "FORGE: FORGE-config block in AI.md is missing FORGE_mode."
    FAILED=1
  fi
  if ! grep -q 'execution_mode:' "$AI_MD"; then
    echo "FORGE: FORGE-config block in AI.md is missing execution_mode."
    FAILED=1
  fi
  for field in coordination_branch integration_branch release_branch; do
    if grep -q "${field}:" "$AI_MD"; then
      FIELD_VALUE=$(grep "${field}:" "$AI_MD" | sed "s/.*${field}: *//" | sed 's/[[:space:]]*$//')
      if [ -z "$FIELD_VALUE" ]; then
        echo "FORGE: ${field} must not be empty when present."
        FAILED=1
      fi
    fi
  done
  if grep -q 'collaboration_mode:' "$AI_MD"; then
    COLLAB_MODE_VALUE=$(grep 'collaboration_mode:' "$AI_MD" | sed 's/.*collaboration_mode: *//' | sed 's/[[:space:]]*$//')
    if [ "$COLLAB_MODE_VALUE" != "solo" ] && [ "$COLLAB_MODE_VALUE" != "team" ]; then
      echo "FORGE: collaboration_mode must be 'solo' or 'team' when present."
      FAILED=1
    fi
  fi
  if grep -q 'task_source:' "$AI_MD"; then
    TASK_SOURCE_VALUE=$(grep 'task_source:' "$AI_MD" | sed 's/.*task_source: *//' | sed 's/[[:space:]]*$//')
    case "$TASK_SOURCE_VALUE" in
      local|github|gitlab|external)
        ;;
      *)
        echo "FORGE: task_source must be local, github, gitlab, or external when present."
        FAILED=1
        ;;
    esac
  fi
  if grep -q 'repo_flavor:' "$AI_MD"; then
    REPO_FLAVOR_VALUE=$(grep 'repo_flavor:' "$AI_MD" | sed 's/.*repo_flavor: *//' | sed 's/[[:space:]]*$//')
    case "$REPO_FLAVOR_VALUE" in
      contract-first|tooling)
        ;;
      *)
        echo "FORGE: repo_flavor must be contract-first or tooling when present."
        FAILED=1
        ;;
    esac
  fi
  if grep -q 'application_docs:' "$AI_MD"; then
    APPLICATION_DOCS_VALUE=$(grep 'application_docs:' "$AI_MD" | sed 's/.*application_docs: *//' | sed 's/[[:space:]]*$//')
    case "$APPLICATION_DOCS_VALUE" in
      true|false)
        ;;
      *)
        echo "FORGE: application_docs must be true or false when present."
        FAILED=1
        ;;
    esac
  fi
  if grep -q 'security_profile:' "$AI_MD"; then
    SECURITY_PROFILE_VALUE=$(grep 'security_profile:' "$AI_MD" | sed 's/.*security_profile: *//' | sed 's/[[:space:]]*$//')
    case "$SECURITY_PROFILE_VALUE" in
      baseline|repo-fortress|ci-security|full-devsecops)
        ;;
      *)
        echo "FORGE: security_profile must be baseline, repo-fortress, ci-security, or full-devsecops when present."
        FAILED=1
        ;;
    esac
  fi
else
  echo "FORGE: AI.md is missing a FORGE-config block."
  FAILED=1
fi

# -----------------------------------------------------------------------
# Result
# -----------------------------------------------------------------------

if [ "$FAILED" -ne 0 ]; then
  echo ""
  echo "FORGE: Documentation validation failed."
  echo "  Review and correct the issues above before starting a governed session."
  exit 1
fi

echo "FORGE: Documentation validation passed (mode: ${FORGE_MODE:-unknown})."
