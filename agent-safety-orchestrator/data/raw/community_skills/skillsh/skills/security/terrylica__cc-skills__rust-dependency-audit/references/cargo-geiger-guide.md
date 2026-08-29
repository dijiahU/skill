# cargo-geiger

Quantifies unsafe code usage across your entire Rust dependency tree. Answers the question: **how much unsafe code am I pulling in through my dependencies?**

## Installation

```bash
cargo install cargo-geiger
```

## Why cargo-geiger

Rust's safety guarantees only hold for safe code. Dependencies can (and do) use `unsafe` blocks. cargo-geiger gives visibility into:

- Which dependencies use `unsafe` code
- How much `unsafe` exists per crate
- Which crates declare `#![forbid(unsafe_code)]`
- Overall safety ratio of your dependency tree

This complements clippy's `unsafe` lints, which only check **your** code — cargo-geiger audits the entire dependency tree.

## Quick Usage

### Fast Mode (No Compilation)

```bash
# Check which deps declare #![forbid(unsafe_code)] — no compilation needed
cargo geiger --forbid-only
```

This is the fastest check. It scans source files for the `#![forbid(unsafe_code)]` attribute without compiling anything. Ideal for CI pipelines.

### Full Audit

```bash
# Count all unsafe blocks across the dependency tree
cargo geiger
```

Full mode parses and analyzes every crate, counting `unsafe` usage in functions, expressions, and impls.

## Output Formats

```bash
# Default ASCII tree (human-readable)
cargo geiger

# Ratio output (for CI thresholds)
cargo geiger --forbid-only --output-format ratio

# Markdown report (for documentation/PRs)
cargo geiger --output-format markdown > unsafe-report.md

# JSON output (for scripting/tooling)
cargo geiger --output-format json
```

### Understanding the Output

The default ASCII output shows a dependency tree with counters:

```
Metric output format: x/y
    x = unsafe code used by the build
    y = total unsafe code found

Symbols:
    :) = No unsafe code found
    !  = Unsafe code detected

Functions  Expressions  Impls  Traits  Methods  Dependency
0/0        0/0          0/0    0/0     0/0      :) my-crate 0.1.0
2/4        18/30        0/0    0/0     0/2      !  ├── some-dep 1.2.3
0/0        0/0          0/0    0/0     0/0      :) │   └── safe-dep 0.5.0
```

Columns explained:

| Column      | Meaning                                       |
| ----------- | --------------------------------------------- |
| Functions   | Functions containing `unsafe` blocks          |
| Expressions | Individual `unsafe` expressions               |
| Impls       | `unsafe impl` blocks                          |
| Traits      | `unsafe trait` declarations                   |
| Methods     | Methods containing `unsafe` code              |
| x/y format  | x = used in build / y = total found in source |

## Key Flags

| Flag                    | Purpose                                             |
| ----------------------- | --------------------------------------------------- |
| `--forbid-only`         | Fast mode: only check for `#![forbid(unsafe_code)]` |
| `--output-format`       | `ascii`, `ratio`, `markdown`, `json`                |
| `--all-features`        | Check with all features enabled                     |
| `--no-default-features` | Check without default features                      |
| `--features`            | Check with specific features                        |
| `--workspace`           | Check all workspace crates                          |
| `--package`             | Check a specific package                            |
| `--update-readme`       | Update safety badge in README                       |

## CI Integration

### GitHub Actions

```yaml
- name: Unsafe code audit
  run: |
    cargo install cargo-geiger
    cargo geiger --forbid-only
```

### Threshold-Based CI Gate

cargo-geiger's `ratio` output can be used to enforce safety thresholds:

```yaml
- name: Unsafe code threshold
  run: |
    cargo install cargo-geiger
    RATIO=$(cargo geiger --forbid-only --output-format ratio 2>/dev/null | tail -1)
    echo "Safety ratio: $RATIO"
    # Parse and enforce threshold (example: fail if <70% safe)
```

### Generate PR Report

````yaml
- name: Unsafe code report
  run: |
    cargo install cargo-geiger
    echo "## Unsafe Code Report" >> $GITHUB_STEP_SUMMARY
    echo '```' >> $GITHUB_STEP_SUMMARY
    cargo geiger --forbid-only 2>/dev/null >> $GITHUB_STEP_SUMMARY
    echo '```' >> $GITHUB_STEP_SUMMARY
````

## Comparison with Clippy's Unsafe Lints

| Aspect         | `clippy::unsafe`                        | `cargo-geiger`            |
| -------------- | --------------------------------------- | ------------------------- |
| Scope          | Your code only                          | Entire dependency tree    |
| Granularity    | Per-lint warnings                       | Per-crate counters        |
| Speed          | Part of normal build                    | Separate pass             |
| `forbid` check | `#![forbid(unsafe_code)]` in your crate | Across all deps           |
| CI integration | Built into `cargo clippy`               | Separate tool             |
| Actionability  | Fix your code                           | Choose safer dependencies |

Use both: clippy for your own code, cargo-geiger for your dependency tree.

## Threshold Configuration

cargo-geiger does not have a built-in threshold config file. Implement thresholds via scripting:

```bash
#!/usr/bin/env bash
# scripts/check-unsafe-threshold.sh

# Count crates that use unsafe
UNSAFE_COUNT=$(cargo geiger --forbid-only 2>/dev/null | grep -c '!')
TOTAL_COUNT=$(cargo geiger --forbid-only 2>/dev/null | grep -cE '[:!]')

echo "Unsafe crates: $UNSAFE_COUNT / $TOTAL_COUNT"

MAX_UNSAFE=${1:-10}  # Default threshold: 10 crates
if [ "$UNSAFE_COUNT" -gt "$MAX_UNSAFE" ]; then
    echo "FAIL: $UNSAFE_COUNT crates use unsafe (threshold: $MAX_UNSAFE)"
    exit 1
fi
echo "PASS: within threshold"
```

## Tips

- Start with `--forbid-only` — it is fast and gives a useful overview
- Use the full audit when evaluating new dependencies
- Generate markdown reports for security reviews and audits
- Combine with `cargo-audit` (known vulns) and `cargo-vet` (review coverage) for complete supply chain security
- Some `unsafe` is expected and necessary (e.g., `libc`, `crossbeam`) — focus on unexpected or excessive usage
- The `x/y` format helps distinguish between unsafe code that is actually used in your build vs. dead unsafe code in the crate
