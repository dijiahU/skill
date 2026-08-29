# cargo-deny

Comprehensive dependency policy enforcement: advisories, licenses, bans, and source restrictions. More powerful than cargo-audit alone.

## Installation

```bash
cargo install cargo-deny
```

## Why cargo-deny

cargo-deny checks four categories:

| Check          | What It Does                                                       |
| -------------- | ------------------------------------------------------------------ |
| **advisories** | RUSTSEC vulnerabilities (like cargo-audit) + unmaintained warnings |
| **licenses**   | Allow/deny license types for all dependencies                      |
| **bans**       | Block specific crates or duplicate versions                        |
| **sources**    | Restrict where crates can come from (crates.io, git, etc.)         |

## Quick Start

```bash
# Generate deny.toml template
cargo deny init

# Run all checks
cargo deny check

# Run specific check
cargo deny check licenses
cargo deny check advisories
cargo deny check bans
cargo deny check sources
```

## Configuration: deny.toml

### Advisories

```toml
[advisories]
# Vulnerability database
db-urls = ["https://github.com/rustsec/advisory-db"]

# How to handle advisories
vulnerability = "deny"      # Deny known vulnerabilities
unmaintained = "warn"       # Warn on unmaintained crates
unsound = "warn"            # Warn on unsound APIs
yanked = "warn"             # Warn on yanked versions

# Ignore specific advisories
ignore = [
    # Reason for ignoring
    "RUSTSEC-YYYY-NNNN",
]
```

### Licenses

```toml
[licenses]
# List of allowed licenses
allow = [
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "Unicode-3.0",
    "Zlib",
    "Unicode-DFS-2016",
]

# Confidence threshold for license detection
confidence-threshold = 0.8

# How to handle unlicensed crates
unlicensed = "deny"

# Crate-specific license clarifications
[[licenses.clarify]]
name = "ring"
# ring uses a custom license
expression = "MIT AND ISC AND OpenSSL"
license-files = [
    { path = "LICENSE", hash = 0xbd0eed23 },
]

# Exceptions for specific crates
[[licenses.exceptions]]
allow = ["OpenSSL"]
name = "ring"
```

### Bans

```toml
[bans]
# How to handle multiple versions of the same crate
multiple-versions = "warn"

# Deny specific crates
deny = [
    # Reasons should be documented
    { name = "openssl", wrappers = ["openssl-sys"] },
]

# Skip specific crate version combinations (for duplicate detection)
skip = [
    { name = "bitflags", version = "=1.3" },
]

# Skip entire dependency trees
skip-tree = [
    { name = "windows-sys" },
]
```

### Sources

```toml
[sources]
# Where crates are allowed to come from
unknown-registry = "deny"
unknown-git = "deny"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
allow-git = []

# Allow specific crates from git
[sources.allow-org]
github = ["my-org"]
```

## SARIF Output

Generate SARIF format for GitHub code scanning:

```bash
# SARIF output (for GitHub Security tab)
cargo deny check --format sarif > deny-results.sarif
```

## CI Integration

### GitHub Actions (Official Action)

```yaml
- uses: EmbarkStudios/cargo-deny-action@v2
  with:
    command: check
    arguments: --all-features
```

### Manual CI

```yaml
- name: cargo-deny
  run: |
    cargo install cargo-deny
    cargo deny check
```

### With SARIF Upload

```yaml
- name: cargo-deny (SARIF)
  run: |
    cargo install cargo-deny
    cargo deny check --format sarif > deny.sarif
  continue-on-error: true

- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: deny.sarif
```

## Workspace Support

```bash
# Check all workspace members
cargo deny check --workspace

# Check specific package
cargo deny check -p my-crate
```

## Common Patterns

### Permissive License Only

```toml
[licenses]
allow = ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib"]
copyleft = "deny"
```

### No Duplicate Dependencies

```toml
[bans]
multiple-versions = "deny"
```

### Crates.io Only (No Git Dependencies)

```toml
[sources]
unknown-registry = "deny"
unknown-git = "deny"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
```

## Tips

- **Start with `cargo deny init`**: Generates a well-documented template
- **Incremental adoption**: Start with `advisories`, add `licenses`, then `bans`
- **License clarifications**: Some crates need manual `[[licenses.clarify]]` entries
- **SARIF integration**: GitHub Security tab shows cargo-deny findings inline
- **Multiple versions**: `multiple-versions = "warn"` is a good default (strict: "deny")
- **Complements cargo-audit**: cargo-deny does everything cargo-audit does plus more
- **Active maintenance**: Frequent releases by Embark Studios — check crates.io for the latest
