# security-scan

Auto-detect and run security scanning tools against the current project, producing a consolidated markdown report.

## What it does

Runs all available security tools and reports findings with severity classification. Missing tools are gracefully skipped with installation hints.

## Platform support

### Universal (always attempted)

| Tool       | Purpose                                          | Install                 |
| ---------- | ------------------------------------------------ | ----------------------- |
| `gitleaks` | Secret detection in git history and working tree | `brew install gitleaks` |
| `semgrep`  | Static analysis — OWASP and security rule packs  | `brew install semgrep`  |
| `grype`    | Filesystem vulnerability scanning                | `brew install grype`    |

### Language-specific (auto-detected by project files)

| Language                | Marker File                                        | Tools                  |
| ----------------------- | -------------------------------------------------- | ---------------------- |
| JavaScript / TypeScript | `package.json`                                     | `npm audit`            |
| Python                  | `requirements.txt` / `pyproject.toml` / `setup.py` | `bandit`, `pip-audit`  |
| Go                      | `go.mod`                                           | `gosec`, `govulncheck` |
| Rust                    | `Cargo.toml`                                       | `cargo audit`          |
| Ruby                    | `Gemfile`                                          | `bundle-audit`         |

## Usage

```
/security-scan
```

## Output format

```markdown
## Security Scan Summary

**Date**: 2026-04-08T00:00:00Z
**Directory**: .
**Tools run**: 5 | **Tools skipped**: 2 | **Tools with findings**: 1

### Confirmed Findings

| Severity | Tool      | Description                          | File / Location |
| -------- | --------- | ------------------------------------ | --------------- |
| High     | npm audit | lodash < 4.17.21 prototype pollution | package.json    |

### Likely False Positives

| Tool    | Description  | Reason dismissed              |
| ------- | ------------ | ----------------------------- |
| semgrep | eval() usage | Only in sandboxed test runner |

### Install Missing Tools

- grype: `brew install grype`
```

## Bundled resources

| File                   | Purpose                                       |
| ---------------------- | --------------------------------------------- |
| `scripts/run-scans.sh` | Scanner runner with auto-detection and output |

## Pairs with

- **security-review** — AI-driven code analysis for logic flaws after tool-based scanning
