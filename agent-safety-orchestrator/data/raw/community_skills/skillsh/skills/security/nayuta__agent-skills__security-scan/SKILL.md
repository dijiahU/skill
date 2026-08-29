---
name: security-scan
description: |
  Runs available security scanning tools against the current project and produces
  a consolidated markdown report. Auto-detects installed tools (gitleaks, semgrep,
  grype, npm audit, bandit, pip-audit, gosec, govulncheck, cargo audit,
  bundle-audit) and activates language-specific scanners based on project files.
  Gracefully skips missing tools and provides installation hints.
  By default scans the entire target directory. Pass --full to make the intent
  explicit (useful in workflows that combine full-codebase and diff-only scans).
  Use when running security scans, checking for vulnerabilities, detecting leaked
  secrets in git history, or validating security posture before commits or releases.
  Pairs with security-review for a complete security workflow.
allowed-tools: Bash
compatibility: |
  Requires bash. Optional external tools: gitleaks, semgrep, grype, npm audit,
  bandit, pip-audit, gosec, govulncheck, cargo audit, bundle-audit. Missing
  tools are skipped gracefully.
metadata:
  version: "1.1.0"
  author: nayuta
---

# Security Scan

## Purpose

Auto-detect and run available security scanning tools, producing a structured
markdown report. Language-specific scanners activate automatically based on
detected project files. Missing tools are skipped with installation guidance.

## Scan Modes

| Mode                 | Flag       | Behavior                                                          |
| -------------------- | ---------- | ----------------------------------------------------------------- |
| Full scan (default)  | _(none)_   | Scans the entire target directory                                 |
| Full scan (explicit) | `--full`   | Same as default; use to make intent explicit in scripts or CI     |
| Strict mode          | `--strict` | Exit with non-zero code when findings are detected (for CI gates) |

Both modes scan the full directory tree. Pass `--full` when calling from a workflow
that combines this skill with diff-scoped reviews (e.g., `security-review`) so the
output header clearly identifies the scan scope.

Use `--strict` in CI pipelines or pre-commit hooks to fail the build when security
findings are detected. Without `--strict`, the script always exits 0 after completing
the scan (findings are reported in markdown output, but don't fail the pipeline).

## Workflow

### Step 1: Run the Scanner

Execute the bundled script from the project root:

```bash
# Default: scan full codebase
bash skills/security-scan/scripts/run-scans.sh [target-directory]

# Explicit full scan (identical result, intent is documented in output)
bash skills/security-scan/scripts/run-scans.sh --full [target-directory]

# Strict mode: exit non-zero if findings detected (for CI gates)
bash skills/security-scan/scripts/run-scans.sh --strict [target-directory]
```

If the skills directory is elsewhere, use the absolute path:

```bash
bash ~/.claude/skills/security-scan/scripts/run-scans.sh [--full] [--strict] [target-directory]
```

If the script is unavailable, run tools manually per the [Manual Scan](#manual-scan) section.

### Step 2: Review Raw Output

The script produces a markdown report. Parse each `## Tool:` section:

- **Status: Skipped** — tool not installed, note for summary
- **Status: Ran / No issues found** — clean for this tool
- **Status: Ran** + findings — requires triage

### Step 3: Triage Findings

For each finding:

1. Confirm it is in production code (not test fixtures or example files)
2. Check whether it is protected by existing validation or encoding
3. Classify severity: **Critical / High / Medium / Low**
4. Mark confirmed vs. likely false positive

Common false positives:

| Pattern           | Likely False Positive When                              |
| ----------------- | ------------------------------------------------------- |
| Secret detected   | Value matches `example`, `test`, `dummy`, `PLACEHOLDER` |
| Dependency vuln   | Only affects dev/test dependencies                      |
| Insecure function | Input is validated upstream                             |
| Weak crypto       | Used for non-security purpose (e.g., cache key)         |

### Step 4: Report

Present findings in this structure:

```markdown
## Security Scan Summary

**Date**: <ISO 8601>
**Directory**: <path>
**Mode**: full | full (--full)
**Tools run**: N | **Tools skipped**: N | **Tools with findings**: N

### Confirmed Findings

| Severity | Tool      | Description                          | File / Location |
| -------- | --------- | ------------------------------------ | --------------- |
| Critical | gitleaks  | AWS key exposed in git history       | commit abc123   |
| High     | npm audit | lodash < 4.17.21 prototype pollution | package.json    |

### Likely False Positives

| Tool    | Description  | Reason dismissed              |
| ------- | ------------ | ----------------------------- |
| semgrep | eval() usage | Only in sandboxed test runner |

### Install Missing Tools

<list tools skipped with install commands>
```

## Tool Coverage

### Universal (always attempted)

| Tool       | Purpose                                            | Install                 |
| ---------- | -------------------------------------------------- | ----------------------- |
| `gitleaks` | Secret detection in git history and working tree   | `brew install gitleaks` |
| `semgrep`  | Static analysis with OWASP and security rule packs | `brew install semgrep`  |
| `grype`    | Filesystem vulnerability scanning                  | `brew install grype`    |

### Language-Specific (auto-detected)

| Marker File                                        | Tool           | Purpose                          | Install                                                    |
| -------------------------------------------------- | -------------- | -------------------------------- | ---------------------------------------------------------- |
| `package.json`                                     | `npm audit`    | JS/TS dependency vulnerabilities | bundled with Node.js                                       |
| `requirements.txt` / `pyproject.toml` / `setup.py` | `bandit`       | Python insecure code patterns    | `pip install bandit`                                       |
| `requirements.txt` / `pyproject.toml` / `setup.py` | `pip-audit`    | Python dependency audit          | `pip install pip-audit`                                    |
| `go.mod`                                           | `gosec`        | Go insecure code patterns        | `go install github.com/securego/gosec/v2/cmd/gosec@latest` |
| `go.mod`                                           | `govulncheck`  | Go module vulnerability database | `go install golang.org/x/vuln/cmd/govulncheck@latest`      |
| `Cargo.toml`                                       | `cargo audit`  | Rust dependency audit            | `cargo install cargo-audit`                                |
| `Gemfile`                                          | `bundle-audit` | Ruby gem vulnerability audit     | `gem install bundler-audit`                                |

## Manual Scan

When the bundled script is unavailable, run each tool directly:

```bash
# Secrets
gitleaks detect --no-banner -v

# Static analysis
semgrep scan --config=auto --quiet

# Filesystem vulnerability scanning
grype dir:.

# Node.js
npm audit --omit=dev

# Python
bandit -r . -q --severity-level medium
pip-audit

# Go
gosec -quiet ./...
govulncheck ./...

# Rust
cargo audit

# Ruby
bundle-audit check --update
```

## Integration

- **security-review** — use after this scan to perform AI-driven code analysis; pass
  `--full` to that skill to review the entire codebase alongside this full scan
- **CI pipeline** — run as a pre-merge gate using `--strict` to fail when findings are
  detected; without `--strict`, scans exit 0 (findings are reported in output only)

## Bundled Resources

| File                   | Purpose                                                |
| ---------------------- | ------------------------------------------------------ |
| `scripts/run-scans.sh` | Scanner runner with auto-detection and markdown output |
