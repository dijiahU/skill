# security-review

AI-driven security code review of changes in the current branch. Analyzes diffs for logic flaws, design issues, and vulnerabilities across 8 categories, reporting only high-confidence findings.

## What it does

1. Builds repository context (tech stack, existing security patterns)
2. Collects the diff vs. `origin/main`
3. Systematically checks each changed file against 8 vulnerability categories
4. Filters findings to confidence ≥ 8/10 to minimize noise
5. Produces a structured report with severity ratings and remediation guidance

## Platform support

Language-agnostic — works on any codebase. No tools to install.

## Usage

```
/security-review
```

By default, reviews only changed files in the current branch. Pass `--full` to review the entire codebase instead of just the diff.

## References

- [Vulnerability Categories Detail](references/vulnerability-categories.md) — detailed patterns and examples for all 8 vulnerability categories
- See SKILL.md for complete workflow instructions and confidence scoring

## Pairs with

- **security-scan** — tool-based scanning for secrets and known CVEs; run before this skill for complete coverage
