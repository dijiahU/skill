# Dependency Freshness: cargo-outdated and Alternatives

Three tools for checking and updating outdated Rust dependencies, plus emerging native Cargo support.

## Tool Comparison

| Tool                         | Purpose                                                  | Install                            |
| ---------------------------- | -------------------------------------------------------- | ---------------------------------- |
| `cargo-outdated`             | Full outdated report (compatible + latest versions)      | `cargo install cargo-outdated`     |
| `cargo-upgrades`             | Lightweight — only shows incompatible (breaking) updates | `cargo install cargo-upgrades`     |
| `cargo upgrade` (cargo-edit) | Actually updates Cargo.toml versions                     | `cargo install cargo-edit`         |
| `cargo update --breaking`    | Native Cargo support (nightly)                           | Built-in (nightly only)            |
| `cargo-unmaintained`         | Find unmaintained dependencies                           | `cargo install cargo-unmaintained` |

## cargo-outdated

Full dependency freshness report showing both compatible and incompatible updates.

### Usage

```bash
# Show all outdated dependencies
cargo outdated

# Root dependencies only (skip transitive)
cargo outdated --root-deps-only

# Specific depth
cargo outdated --depth 1

# Exit with error if outdated (for CI)
cargo outdated --exit-code 1

# Workspace mode
cargo outdated --workspace
```

### Output Format

```
Name             Project  Compat  Latest  Kind    Platform
----             -------  ------  ------  ----    --------
serde            1.0.180  1.0.195 1.0.195 Normal  ---
tokio            1.28.0   1.35.0  1.35.0  Normal  ---
clap             4.3.0    ---     4.5.0   Normal  ---
```

- **Project**: Current version in Cargo.toml
- **Compat**: Latest compatible version (within semver range)
- **Latest**: Absolute latest version (may require version bump)
- **Kind**: Normal, Build, or Development dependency

### Note on Maintenance

cargo-outdated works well for comprehensive audits. Cargo is gaining native support for dependency freshness (see `cargo update --breaking` below), which may eventually reduce the need for this tool.

## cargo-upgrades

Lightweight alternative that only shows incompatible (breaking) updates:

```bash
# Show only breaking updates needed
cargo upgrades
```

Output is simpler — only shows deps where the Cargo.toml version specifier doesn't include the latest.

**When to use**: Quick check in development. No flags needed, fast execution.

## cargo upgrade (cargo-edit)

Part of cargo-edit — actually updates version numbers in Cargo.toml:

```bash
# Dry run first (show what would change)
cargo upgrade --dry-run

# Update all dependencies to latest compatible
cargo upgrade

# Include incompatible (breaking) updates
cargo upgrade --incompatible

# Specific packages only
cargo upgrade -p serde -p tokio

# Specific package to specific version
cargo upgrade serde@<version>

# Workspace-wide
cargo upgrade --workspace
```

**When to use**: When you're ready to actually update dependencies, not just check.

## Native Cargo Support (Nightly)

Cargo has native support for updating dependencies including breaking changes:

```bash
# Update deps including breaking changes (check `cargo update --help` for availability)
cargo update --breaking
```

As Cargo's native features mature, this may reduce the need for cargo-outdated for basic use cases.

## cargo-unmaintained

Find dependencies that appear unmaintained:

```bash
# Check for unmaintained dependencies
cargo unmaintained
```

Checks for:

- No commits in 2+ years
- Repository archived
- No recent releases
- Marked unmaintained in RustSec DB

## Recommended Workflow

### Development

```bash
# Quick check: any breaking updates?
cargo upgrades

# Detailed check: what's outdated?
cargo outdated --root-deps-only
```

### Before Release

```bash
# Full audit
cargo outdated --root-deps-only
cargo unmaintained

# Update compatible deps
cargo update

# Consider breaking updates
cargo upgrade --incompatible --dry-run
```

### CI

```yaml
- name: Check outdated dependencies
  run: |
    cargo install cargo-outdated
    cargo outdated --root-deps-only --exit-code 1

# Or weekly schedule
on:
  schedule:
    - cron: '0 6 * * 1'  # Monday 6am
```

## Tips

- **`cargo update` first**: Always run `cargo update` before `cargo outdated` to refresh Cargo.lock
- **Root deps only**: `--root-deps-only` skips transitive deps (which you don't directly control)
- **Semver trust**: Compatible updates (`cargo update`) are generally safe; breaking updates need review
- **Yanked crates**: `cargo outdated` shows yanked versions — run `cargo update` to move off them
- **Lock file**: Commit `Cargo.lock` for binaries, omit for libraries (Cargo convention)
