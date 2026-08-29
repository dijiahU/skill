#!/usr/bin/env bash
# Security Headers Validator

validate_headers() {
    local url="$1"
    
    echo "=== Security Headers Check for $url ==="
    
    headers=$(curl -s -I "$url")
    
    echo "$headers" | grep -q "Strict-Transport-Security" && echo "✓ HSTS header present" || echo "✗ Missing HSTS"
    echo "$headers" | grep -q "X-Content-Type-Options" && echo "✓ X-Content-Type-Options present" || echo "✗ Missing"
    echo "$headers" | grep -q "X-Frame-Options" && echo "✓ X-Frame-Options present" || echo "✗ Missing"
    echo "$headers" | grep -q "Content-Security-Policy" && echo "✓ CSP header present" || echo "✗ Missing"
    echo "$headers" | grep -q "X-XSS-Protection" && echo "✓ XSS protection present" || echo "✗ Missing"
    echo "$headers" | grep -q "Referrer-Policy" && echo "✓ Referrer-Policy present" || echo "✗ Missing"
}

# Usage
validate_headers "https://example.com"
