# cargo-audit

Vulnerability scanning for Rust dependencies using the RustSec Advisory Database. The canonical tool for checking Cargo.lock against known CVEs.

## Installation

```bash
cargo install cargo-audit
```

## Basic Usage

```bash
# Scan for known vulnerabilities
cargo audit

# Auto-fix where possible (updates Cargo.lock)
cargo audit fix

# Dry-run fix (show what would change)
cargo audit fix --dry-run

# Update the advisory database
cargo audit fetch
```

## Output

cargo-audit reports:

- **Advisory ID**: RUSTSEC-YYYY-NNNN format
- **Affected crate**: Name and version range
- **Severity**: Informational, Low, Medium, High, Critical
- **Description**: What the vulnerability does
- **Patched version**: Version to upgrade to (if available)

## Binary Scanning

Scan compiled binaries for vulnerable dependencies (doesn't need source):

```bash
# Scan a binary
cargo audit bin ./target/release/my-binary

# Scan multiple binaries
cargo audit bin ./target/release/*
```

Binary scanning reads embedded dependency metadata from the Rust binary.

## Configuration

### audit.toml

Create `audit.toml` at project root:

```toml
[advisories]
# Ignore specific advisories (with documented reason)
ignore = [
    # RUSTSEC-YYYY-NNNN: Not affected because we don't use feature X
    "RUSTSEC-YYYY-NNNN",
]

# Severity threshold (ignore below this level)
severity-threshold = "medium"

# Treat informational advisories as warnings (not errors)
informational-warnings = ["unmaintained", "unsound"]

[database]
# Advisory database URL (default: RustSec GitHub)
# url = "https://github.com/RustSec/advisory-db"

# Path to local database (for air-gapped environments)
# path = "/path/to/advisory-db"
```

## CI Integration

### GitHub Actions

```yaml
- name: Security audit
  run: |
    cargo install cargo-audit
    cargo audit
```

### With audit-check Action

```yaml
- uses: rustsec/audit-check@v2
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
```

### Scheduled Scanning

```yaml
name: Security Audit
on:
  schedule:
    - cron: "0 0 * * *" # Daily
  push:
    paths:
      - "Cargo.lock"

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cargo install cargo-audit && cargo audit
```

## RustSec Database

- Open source: <https://github.com/RustSec/advisory-db>
- Community-maintained advisories
- Covers: vulnerabilities, unmaintained crates, unsound APIs
- Auto-fetched on first run (cached locally)
- Update with `cargo audit fetch`

## Complementary Tools

| Tool             | Overlaps With     | Unique Value                        |
| ---------------- | ----------------- | ----------------------------------- |
| `cargo-deny`     | Advisory checking | Also checks licenses, bans, sources |
| `cargo-vet`      | Supply chain      | Audit trail, trusted organizations  |
| `cargo-outdated` | None              | Freshness (not security)            |

**Recommendation**: Use cargo-audit for quick vulnerability checks, cargo-deny for comprehensive policy enforcement.

## Tips

- **Run on CI**: Every PR should pass `cargo audit`
- **Schedule daily scans**: New advisories are added frequently
- **Ignore with reason**: Always document why you're ignoring an advisory
- **Auto-fix**: `cargo audit fix` is safe — it only updates Cargo.lock within semver
- **Binary scanning**: Useful for auditing deployed artifacts
- **Exit codes**: 0 = clean, non-zero = vulnerabilities found (good for CI)
