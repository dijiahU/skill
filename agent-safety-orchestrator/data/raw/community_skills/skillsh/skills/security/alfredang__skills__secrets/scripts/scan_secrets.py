#!/usr/bin/env python3
"""
Scan codebase for hardcoded secrets, API keys, and OAuth2 credentials.

Usage:
    python3 scan_secrets.py [directory]

Scans the given directory (default: current directory) for patterns that
indicate hardcoded secrets. Checks for:
- API keys, tokens, and passwords in source code
- OAuth2 client secrets and credentials
- Private keys and certificates
- Connection strings with embedded credentials
- Missing .gitignore entries for .env files
"""

import os
import re
import sys
from pathlib import Path

# File extensions to scan
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.kt', '.go', '.rb',
    '.php', '.rs', '.swift', '.dart', '.cs', '.c', '.cpp', '.h', '.hpp',
    '.vue', '.svelte', '.yaml', '.yml', '.toml', '.json', '.xml',
    '.properties', '.gradle', '.tf', '.hcl', '.sh', '.bash', '.zsh',
    '.ps1', '.bat', '.cmd', '.env.example', '.env.sample',
}

# Directories to skip
SKIP_DIRS = {
    'node_modules', '.git', '__pycache__', 'venv', '.venv', 'env',
    '.env', 'dist', 'build', '.next', '.nuxt', 'vendor', 'target',
    '.gradle', 'Pods', '.dart_tool', 'coverage', '.pytest_cache',
}

# Patterns that indicate hardcoded secrets
SECRET_PATTERNS = [
    # Generic API keys and tokens
    (r'''(?:api[_-]?key|apikey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]''', 'Hardcoded API key'),
    (r'''(?:api[_-]?secret|apisecret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]''', 'Hardcoded API secret'),
    (r'''(?:access[_-]?token|accesstoken)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]''', 'Hardcoded access token'),
    (r'''(?:auth[_-]?token|authtoken)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]''', 'Hardcoded auth token'),
    (r'''(?:secret[_-]?key|secretkey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]''', 'Hardcoded secret key'),
    (r'''(?:private[_-]?key|privatekey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]''', 'Hardcoded private key'),

    # OAuth2 specific
    (r'''(?:client[_-]?secret|clientsecret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{8,}['\"]''', 'Hardcoded OAuth2 client secret'),
    (r'''(?:client[_-]?id|clientid)\s*[:=]\s*['\"][0-9]{5,}[A-Za-z0-9_\-]*['\"]''', 'Possible hardcoded OAuth2 client ID'),
    (r'''(?:refresh[_-]?token|refreshtoken)\s*[:=]\s*['\"][A-Za-z0-9_\-\.\/]{16,}['\"]''', 'Hardcoded refresh token'),

    # Passwords
    (r'''(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]''', 'Hardcoded password'),
    (r'''(?:db[_-]?password|database[_-]?password)\s*[:=]\s*['\"][^'\"]{4,}['\"]''', 'Hardcoded database password'),

    # Connection strings with credentials
    (r'''(?:mongodb|postgres|mysql|redis|amqp):\/\/[^:]+:[^@]+@''', 'Connection string with embedded credentials'),

    # AWS
    (r'''AKIA[0-9A-Z]{16}''', 'AWS Access Key ID'),
    (r'''(?:aws[_-]?secret[_-]?access[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9\/+=]{40}['\"]''', 'AWS Secret Access Key'),

    # Google / GCP
    (r'''AIza[0-9A-Za-z_\-]{35}''', 'Google API Key'),

    # Stripe
    (r'''sk_live_[0-9a-zA-Z]{24,}''', 'Stripe Live Secret Key'),
    (r'''rk_live_[0-9a-zA-Z]{24,}''', 'Stripe Live Restricted Key'),

    # GitHub
    (r'''ghp_[0-9a-zA-Z]{36}''', 'GitHub Personal Access Token'),
    (r'''gho_[0-9a-zA-Z]{36}''', 'GitHub OAuth Token'),
    (r'''ghs_[0-9a-zA-Z]{36}''', 'GitHub App Token'),

    # Slack
    (r'''xoxb-[0-9]{10,}-[0-9a-zA-Z]{24,}''', 'Slack Bot Token'),
    (r'''xoxp-[0-9]{10,}-[0-9a-zA-Z]{24,}''', 'Slack User Token'),

    # Private keys in code
    (r'''-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----''', 'Embedded private key'),
]

# Files that should never contain secrets
SUSPICIOUS_SECRET_FILES = ['.env', '.env.local', '.env.production', '.env.development']


def should_scan(filepath: Path) -> bool:
    """Check if a file should be scanned based on extension."""
    return filepath.suffix in CODE_EXTENSIONS or filepath.name in {'.env.example', '.env.sample'}


def scan_file(filepath: Path) -> list:
    """Scan a single file for hardcoded secrets."""
    findings = []
    try:
        content = filepath.read_text(errors='ignore')
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip comments
            if stripped.startswith(('#', '//', '/*', '*', '--', '<!--')):
                continue
            for pattern, description in SECRET_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append({
                        'file': str(filepath),
                        'line': i,
                        'description': description,
                        'content': line.strip()[:120],
                    })
    except (PermissionError, UnicodeDecodeError):
        pass
    return findings


def check_gitignore(root: Path) -> list:
    """Check if .env files are properly gitignored."""
    issues = []
    gitignore_path = root / '.gitignore'
    gitignore_entries = set()
    if gitignore_path.exists():
        gitignore_entries = set(gitignore_path.read_text().splitlines())

    env_patterns = {'.env', '.env.*', '.env.local', '.env*.local'}
    has_env_ignore = any(p in gitignore_entries for p in env_patterns)

    if not has_env_ignore:
        # Check if any .env files exist
        for env_file in SUSPICIOUS_SECRET_FILES:
            if (root / env_file).exists():
                issues.append({
                    'file': str(root / '.gitignore'),
                    'line': 0,
                    'description': f'.env files exist but .gitignore does not exclude them',
                    'content': f'Missing .gitignore entry for {env_file}',
                })
                break

    return issues


def check_env_example(root: Path) -> list:
    """Check if .env.example exists when .env exists."""
    issues = []
    has_env = (root / '.env').exists()
    has_example = (root / '.env.example').exists() or (root / '.env.sample').exists()

    if has_env and not has_example:
        issues.append({
            'file': str(root),
            'line': 0,
            'description': 'Missing .env.example file',
            'content': '.env exists but no .env.example or .env.sample for documentation',
        })
    return issues


def scan_directory(root: str) -> list:
    """Scan an entire directory tree for hardcoded secrets."""
    root_path = Path(root).resolve()
    all_findings = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Remove skip directories in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            if should_scan(filepath):
                findings = scan_file(filepath)
                all_findings.extend(findings)

    # Check project-level configurations
    all_findings.extend(check_gitignore(root_path))
    all_findings.extend(check_env_example(root_path))

    return all_findings


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else '.'
    print(f"Scanning {Path(target).resolve()} for hardcoded secrets...\n")

    findings = scan_directory(target)

    if not findings:
        print("No hardcoded secrets detected.")
        sys.exit(0)

    print(f"Found {len(findings)} potential issue(s):\n")
    for f in findings:
        loc = f"{f['file']}:{f['line']}" if f['line'] else f['file']
        print(f"  [{f['description']}]")
        print(f"  Location: {loc}")
        print(f"  Content:  {f['content']}")
        print()

    sys.exit(1)


if __name__ == '__main__':
    main()
