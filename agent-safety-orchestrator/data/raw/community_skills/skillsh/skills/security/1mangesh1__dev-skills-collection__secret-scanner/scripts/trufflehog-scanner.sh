#!/usr/bin/env bash
# TruffleHog Secret Detector
# Advanced secret detection tool

install_trufflehog() {
    echo "=== Installing TruffleHog ==="
    pip install truffle-hog
}

scan_directory_with_trufflehog() {
    local directory="$1"
    
    echo "=== Scanning with TruffleHog ==="
    truffleHog filesystem "$directory" \
        --json \
        --include-paths '.*' \
        --exclude-paths '.git/*' \
        > scan-results.json
    
    echo "Results saved to scan-results.json"
}

scan_git_repo() {
    echo "=== Scanning Git Repository ==="
    truffleHog git . --json > git-scan-results.json
}

# Usage
scan_directory_with_trufflehog "."
