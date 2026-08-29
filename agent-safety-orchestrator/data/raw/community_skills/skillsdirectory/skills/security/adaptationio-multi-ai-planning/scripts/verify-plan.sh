#!/bin/bash
#
# Comprehensive Plan Verification Script
# Validates plan completeness, quality, and readiness for execution
#
# Usage: bash verify-plan.sh <plan-file.md or plan.json>
#

set -e

PLAN_FILE="$1"

if [ -z "$PLAN_FILE" ]; then
    echo "Usage: $0 <plan-file.md or plan.json>"
    exit 1
fi

if [ ! -f "$PLAN_FILE" ]; then
    echo "Error: File '$PLAN_FILE' not found"
    exit 1
fi

echo "═══════════════════════════════════════"
echo "  PLAN VERIFICATION"
echo "═══════════════════════════════════════"
echo ""
echo "Plan: $PLAN_FILE"
echo "Date: $(date)"
echo ""

# Initialize scores
TOTAL_CHECKS=0
PASSED_CHECKS=0

check_pass() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    echo "✅ $1"
}

check_fail() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo "❌ $1"
}

echo "─────────────────────────────────────────"
echo "1. STRUCTURE VALIDATION"
echo "─────────────────────────────────────────"
echo ""

# Check for required sections in markdown
if [[ "$PLAN_FILE" == *.md ]]; then
    if grep -q "^## .*Objective" "$PLAN_FILE"; then
        check_pass "Has Objective section"
    else
        check_fail "Missing Objective section"
    fi

    if grep -q "^## .*Task" "$PLAN_FILE"; then
        check_pass "Has Task breakdown section"
    else
        check_fail "Missing Task breakdown"
    fi

    if grep -q "^## .*Verification" "$PLAN_FILE" || grep -q "Success Criteria" "$PLAN_FILE"; then
        check_pass "Has Verification section"
    else
        check_fail "Missing Verification section"
    fi

    if grep -q "^## .*Dependency\|^## .*Dependencies" "$PLAN_FILE"; then
        check_pass "Has Dependency section"
    else
        check_fail "Missing Dependency mapping"
    fi
fi

echo ""
echo "─────────────────────────────────────────"
echo "2. COMPLETENESS CHECK"
echo "─────────────────────────────────────────"
echo ""

# Count tasks
TASK_COUNT=$(grep -c "^###\? Task [0-9]" "$PLAN_FILE" 2>/dev/null || echo "0")
echo "Tasks found: $TASK_COUNT"

if [ "$TASK_COUNT" -ge 3 ]; then
    check_pass "Has sufficient tasks (≥3)"
else
    check_fail "Too few tasks (<3) - needs decomposition"
fi

# Check for success criteria
SUCCESS_CRITERIA_COUNT=$(grep -c "Success Criteria\|success criteria\|- \[.\]" "$PLAN_FILE" 2>/dev/null || echo "0")
echo "Success criteria found: $SUCCESS_CRITERIA_COUNT"

if [ "$SUCCESS_CRITERIA_COUNT" -ge "$TASK_COUNT" ]; then
    check_pass "All tasks appear to have success criteria"
else
    check_fail "Some tasks missing success criteria"
fi

echo ""
echo "─────────────────────────────────────────"
echo "3. QUALITY INDICATORS"
echo "─────────────────────────────────────────"
echo ""

# Check for verification commands
if grep -q "```bash\|```sh" "$PLAN_FILE"; then
    check_pass "Contains verification commands"
else
    check_fail "No verification commands found"
fi

# Check for dependency mapping
if grep -q "depend\|Depend" "$PLAN_FILE"; then
    check_pass "Dependencies documented"
else
    check_fail "No dependency documentation found"
fi

# Check for examples
if grep -q "Example\|example" "$PLAN_FILE"; then
    check_pass "Includes examples"
else
    check_fail "No examples provided"
fi

# Check for quality score
if grep -q "Quality Score\|quality score" "$PLAN_FILE"; then
    check_pass "Quality score documented"
else
    check_fail "No quality score found"
fi

echo ""
echo "─────────────────────────────────────────"
echo "4. VERIFICATION SUMMARY"
echo "─────────────────────────────────────────"
echo ""

PASS_RATE=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))

echo "Checks Run: $TOTAL_CHECKS"
echo "Passed: $PASSED_CHECKS"
echo "Failed: $((TOTAL_CHECKS - PASSED_CHECKS))"
echo "Pass Rate: $PASS_RATE%"
echo ""

if [ "$PASS_RATE" -ge 90 ]; then
    echo "✅ VERIFICATION PASSED (≥90%)"
    echo ""
    echo "Plan is ready for execution"
    exit 0
elif [ "$PASS_RATE" -ge 70 ]; then
    echo "⚠️  NEEDS MINOR REVISION (70-89%)"
    echo ""
    echo "Address failed checks before execution"
    exit 1
else
    echo "❌ NEEDS MAJOR REVISION (<70%)"
    echo ""
    echo "Significant issues found - recommend re-planning"
    exit 2
fi
