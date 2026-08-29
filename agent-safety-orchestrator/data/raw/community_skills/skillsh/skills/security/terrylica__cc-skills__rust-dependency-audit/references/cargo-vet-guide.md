# cargo-vet

Mozilla's supply chain security tool for Rust. Tracks which crates have been audited, by whom, and enables importing audits from trusted organizations.

## Installation

```bash
cargo install cargo-vet
```

## Why cargo-vet

While cargo-audit checks for **known vulnerabilities** and cargo-deny enforces **policies**, cargo-vet answers a different question: **has anyone actually reviewed this code?**

cargo-vet maintains an audit trail:

- Which crate versions have been reviewed
- Who reviewed them
- What they certified (safe-to-deploy, safe-to-run)
- Imported audits from trusted organizations (Mozilla, Google, etc.)

## Quick Start

```bash
# Initialize cargo-vet in your project
cargo vet init

# Check supply chain status
cargo vet

# See what needs auditing
cargo vet suggest

# Audit a crate (certify you've reviewed it)
cargo vet certify <crate> <version>
```

## How It Works

### Certification Levels

| Level            | Meaning                     | Use For                         |
| ---------------- | --------------------------- | ------------------------------- |
| `safe-to-deploy` | Reviewed for production use | Production dependencies         |
| `safe-to-run`    | Reviewed for dev/build use  | Dev-dependencies, build scripts |

### Directory Structure

```
supply-chain/
├── config.toml      # Trusted organizations, criteria
├── audits.toml      # Your organization's audits
├── imports.lock     # Imported audits (auto-generated)
└── exemptions.toml  # Temporary exemptions (unaudited)
```

## Trusting Organizations

Import audits from organizations you trust:

```bash
# Trust all audits from Mozilla
cargo vet trust --all mozilla

# Trust all audits from Google
cargo vet trust --all google

# Trust specific crate audits
cargo vet trust serde --who mozilla
```

### Available Audit Sources

Major organizations publishing cargo-vet audits:

- **Mozilla** — Firefox codebase audits
- **Google** — Chromium/Android codebase audits
- **Bytecode Alliance** — Wasmtime/Cranelift audits
- **Embark Studios** — Game engine audits

## Auditing a Crate

```bash
# Mark a crate version as audited
cargo vet certify serde <version>

# With specific certification level
cargo vet certify serde <version> --criteria safe-to-deploy

# Diff audit (review only the diff between versions)
cargo vet diff serde <old-version> <new-version>
```

### Diff Auditing

The most practical workflow — review only what changed between versions:

```bash
# See what changed between versions
cargo vet diff serde <old-version> <new-version>

# Opens a diff viewer
# After review, certify the delta:
cargo vet certify serde <new-version> --criteria safe-to-deploy
```

## Exemptions

For crates you haven't audited yet:

```bash
# Add temporary exemption
cargo vet add-exemption <crate> <version>
```

Exemptions are tracked in `supply-chain/exemptions.toml` and serve as a TODO list.

## Configuration

### config.toml

```toml
[policy]
# Default criteria for dependencies
criteria = "safe-to-deploy"

# Per-crate policy overrides
[policy.my-dev-tool]
criteria = "safe-to-run"  # Only used in development

[imports.mozilla]
url = "https://raw.githubusercontent.com/nickel-org/nickel.rs/cargo-vet/supply-chain/audits.toml"

[imports.google]
url = "https://chromium.googlesource.com/chromium/src/+/main/aspect/aspect-supply-chain/audits.toml?format=TEXT"
```

## CI Integration

```yaml
- name: Supply chain audit
  run: |
    cargo install cargo-vet
    cargo vet
```

cargo-vet fails if any dependency lacks audits or exemptions — enforcing review coverage.

## Workflow

### Initial Setup

1. `cargo vet init` — creates supply-chain/ directory
2. `cargo vet trust --all mozilla` — import trusted audits
3. `cargo vet suggest` — see what's unaudited
4. For each unaudited crate: `cargo vet certify` or `cargo vet add-exemption`

### Ongoing

1. `cargo vet` on every PR (CI)
2. When adding new deps: audit or exempt
3. When updating deps: diff-audit the changes
4. Periodically: review and remove exemptions

### Reducing Audit Burden

```bash
# Import from multiple trusted orgs
cargo vet trust --all mozilla
cargo vet trust --all google

# Check remaining unaudited
cargo vet suggest
```

Most popular crates are already audited by Mozilla or Google.

## The Trifecta

For comprehensive dependency security, use all three:

| Tool          | Question Answered                        |
| ------------- | ---------------------------------------- |
| `cargo-audit` | Are there known vulnerabilities?         |
| `cargo-deny`  | Do licenses and policies comply?         |
| `cargo-vet`   | Has someone actually reviewed this code? |

```bash
# Complete supply chain audit
cargo audit && cargo deny check && cargo vet
```

## Tips

- **Start with imports**: Trusting Mozilla/Google covers most popular crates
- **Diff audits**: Review only deltas between versions — much faster than full audits
- **Exemptions are OK**: They're a tracking mechanism, not a failure
- **Team workflow**: Share `supply-chain/` in version control — audits are cumulative
- **`cargo vet suggest`**: Prioritizes crates by download count and dependency depth
- **Not a replacement**: cargo-vet complements cargo-audit and cargo-deny, doesn't replace them
