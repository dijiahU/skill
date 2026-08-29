#!/bin/bash

# Security Scanner Script
# Scans workspace for potential security risks including passwords, tokens, and API keys

set -euo pipefail

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Default scan directory is current directory
SCAN_DIR="${1:-.}"

# Patterns file location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Counter for findings
HIGH_COUNT=0
MEDIUM_COUNT=0
LOW_COUNT=0

# Check if we're in a git repository
IS_GIT_REPO=false
if git -C "${SCAN_DIR}" rev-parse --git-dir > /dev/null 2>&1; then
    IS_GIT_REPO=true
fi

echo -e "${BLUE}🔍 Security Scanner${NC}"
echo -e "${BLUE}===================${NC}"
echo ""
echo -e "Scanning directory: ${GREEN}${SCAN_DIR}${NC}"
if [ "$IS_GIT_REPO" = true ]; then
    echo -e "${BLUE}Git repository detected - respecting .gitignore${NC}"
fi
echo ""

# Directories to exclude (used for non-git fallback)
EXCLUDE_DIRS=(
    "node_modules"
    "vendor"
    ".git"
    "dist"
    "build"
    "target"
    ".next"
    "__pycache__"
    "venv"
    ".venv"
    "env"
    "security-scanner"
)

# Build exclude pattern for grep
EXCLUDE_PATTERN=""
for dir in "${EXCLUDE_DIRS[@]}"; do
    EXCLUDE_PATTERN="${EXCLUDE_PATTERN} --exclude-dir=${dir}"
done

# Function to search for pattern
search_pattern() {
    local pattern="$1"
    local description="$2"
    local severity="$3"

    echo -e "${BLUE}Checking for: ${description}${NC}"

    local results=""

    # Use git grep if in a git repo (respects .gitignore), otherwise use regular grep
    if [ "$IS_GIT_REPO" = true ]; then
        # git grep automatically respects .gitignore
        # -n: show line numbers, -i: case insensitive, -E: extended regex, -I: ignore binary files
        results=$(git -C "${SCAN_DIR}" grep -n -i -E "${pattern}" 2>/dev/null || true)
    else
        # Fallback to regular grep with manual exclusions
        results=$(grep -r -n -i -E "${pattern}" ${EXCLUDE_PATTERN} --exclude="*.{min.js,map,lock,log,svg,png,jpg,jpeg,gif,pdf,zip,tar,gz,bin,exe}" "${SCAN_DIR}" 2>/dev/null || true)
    fi

    if [ -n "$results" ]; then
        local count=$(echo "$results" | wc -l | tr -d ' ')

        if [ "$severity" = "HIGH" ]; then
            echo -e "${RED}❌ HIGH SEVERITY - Found ${count} match(es)${NC}"
            HIGH_COUNT=$((HIGH_COUNT + count))
        elif [ "$severity" = "MEDIUM" ]; then
            echo -e "${YELLOW}⚠️  MEDIUM SEVERITY - Found ${count} match(es)${NC}"
            MEDIUM_COUNT=$((MEDIUM_COUNT + count))
        else
            echo -e "${YELLOW}ℹ️  LOW SEVERITY - Found ${count} match(es)${NC}"
            LOW_COUNT=$((LOW_COUNT + count))
        fi

        echo "$results" | head -20  # Limit output to first 20 matches
        if [ "$count" -gt 20 ]; then
            echo -e "${YELLOW}... and $((count - 20)) more match(es)${NC}"
        fi
        echo ""
    else
        echo -e "${GREEN}✓ No matches found${NC}"
        echo ""
    fi
}

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  API Keys & Tokens${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

search_pattern 'AKIA[0-9A-Z]{16}' "AWS Access Key ID" "HIGH"
search_pattern '(aws_secret_access_key|aws_access_key_id)\s*=\s*["\047][A-Za-z0-9/+=]{40}["\047]' "AWS Secret Access Key" "HIGH"
search_pattern 'ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}|ghu_[a-zA-Z0-9]{36}|ghs_[a-zA-Z0-9]{36}|ghr_[a-zA-Z0-9]{36}' "GitHub Token" "HIGH"
search_pattern 'xox[baprs]-[0-9a-zA-Z]{10,48}' "Slack Token" "HIGH"
search_pattern 'sk_live_[0-9a-zA-Z]{24}|pk_live_[0-9a-zA-Z]{24}' "Stripe API Key" "HIGH"
search_pattern 'AIza[0-9A-Za-z\\-_]{35}' "Google API Key" "HIGH"
search_pattern 'sq0atp-[0-9A-Za-z\-_]{22}|sq0csp-[0-9A-Za-z\-_]{43}' "Square API Key" "HIGH"
search_pattern 'SK[0-9a-fA-F]{32}|AC[a-z0-9]{32}' "Twilio API Key" "HIGH"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Passwords & Credentials${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

search_pattern '(password|passwd|pwd)\s*[:=]\s*["\047][^"\047\s]{6,}["\047]' "Hardcoded Password" "HIGH"
search_pattern '(api_key|apikey|api-key)\s*[:=]\s*["\047][a-zA-Z0-9_\-]{16,}["\047]' "API Key Assignment" "HIGH"
search_pattern '(private_key|privatekey)\s*[:=]' "Private Key Reference" "HIGH"
search_pattern 'BEGIN\s+(RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY' "Private Key Block" "HIGH"
search_pattern '(bearer|token)\s+[a-zA-Z0-9_\-\.]{20,}' "Bearer/Token" "MEDIUM"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Database Connection Strings${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

search_pattern 'mongodb(\+srv)?://[^:]+:[^@]+@' "MongoDB Connection String with Credentials" "HIGH"
search_pattern 'postgres(ql)?://[^:]+:[^@]+@' "PostgreSQL Connection String with Credentials" "HIGH"
search_pattern 'mysql://[^:]+:[^@]+@' "MySQL Connection String with Credentials" "HIGH"
search_pattern 'redis://:[^@]+@' "Redis Connection String with Password" "HIGH"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Generic Secrets${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

search_pattern '["\047][a-zA-Z0-9+/]{40,}={0,2}["\047]' "Possible Base64 Encoded Secret" "MEDIUM"
search_pattern '(secret|token|key)\s*[:=]\s*["\047][0-9a-f]{32,}["\047]' "Hex Secret Pattern" "MEDIUM"
search_pattern 'Authorization:\s*Basic\s+[A-Za-z0-9+/=]{20,}' "Basic Auth Header" "MEDIUM"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${RED}High Severity Findings:    ${HIGH_COUNT}${NC}"
echo -e "${YELLOW}Medium Severity Findings:  ${MEDIUM_COUNT}${NC}"
echo -e "${YELLOW}Low Severity Findings:     ${LOW_COUNT}${NC}"
echo ""

TOTAL=$((HIGH_COUNT + MEDIUM_COUNT + LOW_COUNT))

if [ "$TOTAL" -gt 0 ]; then
    echo -e "${RED}⚠️  Security issues detected! Please review the findings above.${NC}"
    echo ""
    echo -e "${BLUE}Recommended Actions:${NC}"
    echo "1. Remove hardcoded secrets from code"
    echo "2. Move secrets to environment variables or secret management systems"
    echo "3. Ensure .env files are in .gitignore"
    echo "4. Rotate any exposed credentials"
    echo "5. Check git history for committed secrets"
    echo ""
    exit 1
else
    echo -e "${GREEN}✓ No security issues detected!${NC}"
    echo ""
    exit 0
fi
