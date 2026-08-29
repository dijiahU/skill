#!/usr/bin/env bash
# Dependency Audit Tool
# Check for security vulnerabilities and outdated packages

audit_npm_dependencies() {
    echo "=== NPM Dependency Audit ==="
    
    # Check for vulnerabilities
    npm audit --audit-level=moderate
    
    if [ $? -eq 0 ]; then
        echo "✓ No vulnerabilities found"
    else
        echo "❌ Vulnerabilities detected"
        echo ""
        echo "Run: npm audit fix"
    fi
}

check_outdated_packages() {
    echo ""
    echo "=== Outdated Packages ==="
    npm outdated || true
}

check_security_advisories() {
    echo ""
    echo "=== Security Advisories ==="
    npm audit --json | jq '.metadata.vulnerabilities'
}

# Usage
audit_npm_dependencies
check_outdated_packages
