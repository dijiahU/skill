#!/bin/bash
# FORGE CI: Validate that the configured security_profile is reflected in
# project-local setup evidence rather than silently passing.
#
# When security_profile is stronger than baseline, SETUP.md must contain
# matching sections and at least one non-default value per section.
# When security_profile claims SAST or secret scanning are enabled, a
# matching workflow file or documented external pipeline must exist.

set -e

FORGE_DIR="docs/forge"
AI_MD="$FORGE_DIR/AI.md"
SETUP_MD="$FORGE_DIR/SETUP.md"
FAILED=0

if [ ! -f "$AI_MD" ]; then
  echo "FORGE: $AI_MD missing; cannot validate security_profile."
  exit 1
fi

if ! grep -q 'security_profile:' "$AI_MD"; then
  exit 0
fi

PROFILE=$(grep 'security_profile:' "$AI_MD" | head -1 | sed 's/.*security_profile: *//' | sed 's/[[:space:]]*$//')

case "$PROFILE" in
  baseline|"")
    exit 0
    ;;
  repo-fortress|ci-security|full-devsecops)
    ;;
  *)
    echo "FORGE: security_profile must be baseline, repo-fortress, ci-security, or full-devsecops; got '$PROFILE'."
    exit 1
    ;;
esac

if [ ! -f "$SETUP_MD" ]; then
  echo "FORGE: security_profile=$PROFILE requires $SETUP_MD with matching setup evidence."
  exit 1
fi

require_section() {
  local heading="$1"
  if ! grep -qE "^## $heading\$" "$SETUP_MD"; then
    echo "FORGE: $SETUP_MD missing required section for security_profile=$PROFILE: '$heading'."
    FAILED=1
  fi
}

# Returns 0 if any line under the section heading contains a non-default value.
# A "non-default" value is anything other than blank, a yes/no/n/a placeholder,
# or a slash-delimited choice like 'yes/no'.
section_has_evidence() {
  local heading="$1"
  awk -v h="## $heading" '
    BEGIN { in_section = 0 }
    $0 == h { in_section = 1; next }
    in_section && /^## / { exit }
    in_section {
      line = $0
      sub(/^[[:space:]]*-[[:space:]]*[^:]+:[[:space:]]*/, "", line)
      gsub(/[[:space:]]+$/, "", line)
      if (length(line) == 0) next
      if (line ~ /^(yes|no|n\/a)$/) next
      if (line ~ /\//) next
      print line
      exit
    }
  ' "$SETUP_MD" | grep -q .
}

require_evidence() {
  local heading="$1"
  if ! section_has_evidence "$heading"; then
    echo "FORGE: $SETUP_MD section '$heading' has no concrete evidence values for security_profile=$PROFILE."
    FAILED=1
  fi
}

case "$PROFILE" in
  repo-fortress|ci-security|full-devsecops)
    require_section "Branch Protection"
    require_evidence "Branch Protection"
    ;;
esac

case "$PROFILE" in
  ci-security|full-devsecops)
    require_section "CI Security"
    require_evidence "CI Security"
    require_section "Supply Chain"
    require_evidence "Supply Chain"
    if grep -E '^- SAST enabled:.*yes' "$SETUP_MD" >/dev/null; then
      WORKFLOW_DIR=".github/workflows"
      if [ -d "$WORKFLOW_DIR" ]; then
        if ! grep -lEi 'codeql|semgrep|sast' "$WORKFLOW_DIR"/*.yml "$WORKFLOW_DIR"/*.yaml 2>/dev/null | grep -q .; then
          if ! grep -E '^- SAST tool:' "$SETUP_MD" | grep -vE '(/|^- SAST tool:[[:space:]]*$)' >/dev/null; then
            echo "FORGE: SAST is marked enabled in $SETUP_MD but no SAST workflow found in $WORKFLOW_DIR and no SAST tool recorded."
            FAILED=1
          fi
        fi
      fi
    fi
    ;;
esac

case "$PROFILE" in
  full-devsecops)
    require_section "Continuous Delivery Security"
    require_evidence "Continuous Delivery Security"
    ;;
esac

exit $FAILED
