#!/usr/bin/env bash
# Git Secret Scanner
# Detect secrets in repository

scan_for_secrets() {
    echo "=== Scanning for Secrets ==="
    
    # Common patterns
    patterns=(
        "password.*="
        "api_key.*="
        "secret.*="
        "token.*="
        "aws_access_key"
        "-----BEGIN RSA PRIVATE KEY-----"
        "-----BEGIN PRIVATE KEY-----"
        "AWS_SECRET_ACCESS_KEY="
    )
    
    for pattern in "${patterns[@]}"; do
        echo ""
        echo "Searching for: $pattern"
        grep -r "$pattern" . --include="*.py" --include="*.js" --include="*.env" 2>/dev/null | \
            grep -v node_modules | grep -v ".git" | head -10
    done
}

check_git_history() {
    echo "=== Checking Git History for Secrets ==="
    
    # Search git history
    git log -p --all -S "password" | head -50
}

setup_secret_check() {
    echo "=== Setting up Pre-commit Secret Check ==="
    
    cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Check for secrets before commit

patterns=(
    "password"
    "api_key"
    "secret_key"
    "AWS_SECRET"
)

for pattern in "${patterns[@]}"; do
    if git diff --cached | grep -qi "$pattern"; then
        echo "❌ Possible secret found in commit!"
        echo "   Pattern: $pattern"
        exit 1
    fi
done

echo "✓ No secrets detected"
EOF
    
    chmod +x .git/hooks/pre-commit
}

# Usage
scan_for_secrets
