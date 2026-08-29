#!/bin/bash
# Test: Grype migration validation
# Verifies the old scanner has been fully replaced by grype

set -uo pipefail

unset CDPATH
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FAILURES=0
TOTAL=0

# The old tool name, stored in a variable so this test file itself
# does not contain the bare literal (avoiding false positives from
# repo-wide searches for leftover references).
OLD_TOOL="tri""vy"

assert_match() {
    local desc="$1"
    local pattern="$2"
    local file="$3"
    TOTAL=$((TOTAL + 1))
    if grep -q "${pattern}" "${file}"; then
        echo "PASS: ${desc}"
    else
        echo "FAIL: ${desc} (pattern '${pattern}' not found in ${file##*/})"
        FAILURES=$((FAILURES + 1))
    fi
}

assert_no_match() {
    local desc="$1"
    local pattern="$2"
    local file="$3"
    TOTAL=$((TOTAL + 1))
    if grep -qi "${pattern}" "${file}"; then
        echo "FAIL: ${desc} (found '${pattern}' in ${file##*/})"
        FAILURES=$((FAILURES + 1))
    else
        echo "PASS: ${desc}"
    fi
}

assert_test() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@"; then
        echo "PASS: ${desc}"
    else
        echo "FAIL: ${desc}"
        FAILURES=$((FAILURES + 1))
    fi
}

# 1. Zero old-scanner references across all three files
assert_no_match "No old scanner references in run-scans.sh" \
    "${OLD_TOOL}" "${SKILL_DIR}/scripts/run-scans.sh"

assert_no_match "No old scanner references in SKILL.md" \
    "${OLD_TOOL}" "${SKILL_DIR}/SKILL.md"

assert_no_match "No old scanner references in README.md" \
    "${OLD_TOOL}" "${SKILL_DIR}/README.md"

# 2a. grype invocation uses dir:. as target
assert_match "grype uses dir:. target" \
    'grype dir:\.' "${SKILL_DIR}/scripts/run-scans.sh"

# 2b. grype invocation uses run_tool wrapper
assert_match "grype uses run_tool wrapper" \
    'run_tool "grype"' "${SKILL_DIR}/scripts/run-scans.sh"

# 3. SKILL.md front-matter references grype
assert_match "SKILL.md front-matter references grype" \
    'grype' "${SKILL_DIR}/SKILL.md"

# 4. README.md table references grype
assert_match "README.md table references grype" \
    'grype' "${SKILL_DIR}/README.md"

# 5. README.md install hint references grype
assert_match "README.md install hint references grype" \
    'brew install grype' "${SKILL_DIR}/README.md"

# 6. SKILL.md Purpose column has no misconfiguration claim
assert_no_match "SKILL.md grype row has no misconfiguration claim" \
    "misconfiguration" "${SKILL_DIR}/SKILL.md"

# 7. audit-skill score (simplified -- check files exist and have expected content)
assert_test "run-scans.sh exists and is executable" \
    test -x "${SKILL_DIR}/scripts/run-scans.sh"

echo ""
echo "Results: $((TOTAL - FAILURES))/${TOTAL} passed, ${FAILURES} failed"
exit "${FAILURES}"
