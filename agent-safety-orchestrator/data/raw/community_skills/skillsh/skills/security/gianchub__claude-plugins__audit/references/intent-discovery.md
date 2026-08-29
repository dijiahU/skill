# Intent Discovery

## Purpose

Detailed subagent instructions for intent discovery (SKILL.md Step 3). Three subagents run in parallel; their combined output is merged into an Intent Brief. See SKILL.md Step 4 for how findings are cross-referenced against the Intent Brief during analysis.

---

## Documentation Scanner

### Objective

Discover and read all documentation files across the project. Scan project-wide regardless of the audit scope — a root-level `ARCHITECTURE.md` or a `docs/design-decisions.md` is relevant even when the audit targets a single subdirectory. Extract intent signals: stated design decisions, trade-offs, constraints, conventions, and deliberate limitations.

### File Discovery

Scan for files matching documentation patterns:

**By extension:** `.md`, `.txt`, `.rst`, `.adoc`, `.org`

**By well-known name (extensionless or any extension):** `ARCHITECTURE`, `DECISIONS`, `CONTRIBUTING`, `SECURITY`, `LICENSE`, `AUTHORS`, `HISTORY`, `CONVENTIONS`, `STANDARDS`

**By name or content keywords (case-insensitive):** `readme`, `architecture`, `design`, `decision`, `adr`, `contributing`, `changelog`, `history`, `conventions`, `standards`, `guide`, `rationale`, `trade-off`, `principles`

This list is non-exhaustive. Recognize any file that serves a documentation purpose based on its name, location (e.g., `docs/`, `doc/`, `.github/`), or content.

**Agent instruction files:** `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `CURSORRULES`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`, and similar. These often contain project conventions and architectural constraints.

### Extraction

Read each discovered file and extract:

- Stated design decisions and their rationale.
- Documented trade-offs (what was chosen, what was rejected, why).
- Constraints (performance budgets, compatibility requirements, regulatory).
- Coding conventions and style standards beyond formatting.
- Deliberate limitations and known technical debt acknowledged by the team.

Ignore purely procedural content (setup instructions, API reference docs) unless it contains embedded rationale.

### Report Format

```
- **Source:** <file path>
  **Summary:** <one-line summary of the decision, convention, or trade-off>
  **Quote:** "<direct quote from the file, if useful>" (optional)
```

---

## Code Intent Scanner

### Objective

Search in-scope source files for comments and annotations that express rationale — the "why" behind code choices. Capture suppression directives that indicate intentional deviation from rules or standards.

### Rationale Markers

Scan for comments containing these marker words (case-insensitive):

`NOTE`, `HACK`, `WHY`, `DESIGN`, `TRADE-OFF`, `TRADEOFF`, `INTENTIONAL`, `DELIBERATE`, `BY DESIGN`, `RATIONALE`, `REASON`, `CAVEAT`, `WORKAROUND`, `TODO`, `FIXME`

`TODO` and `FIXME` are weaker intent signals than explicit rationale markers like `DELIBERATE` or `BY DESIGN`, but they frequently indicate known limitations and acknowledged technical debt. Include them in the scan but weight them lower during Intent Brief compilation.

### Suppression Markers

Scan for inline suppression directives that indicate acknowledged and intentional deviations:

- Python: `noqa`, `type: ignore`, `# pylint: disable`, `# mypy: ignore`
- JavaScript/TypeScript: `eslint-disable`, `@ts-ignore`, `@ts-expect-error`, `// noinspection`
- Go: `//nolint`
- Java/Kotlin: `@SuppressWarnings`, `//noinspection`
- Rust: `#[allow(...)]`, `#[expect(...)]`
- Ruby: `# rubocop:disable`
- C/C++: `#pragma warning disable`, `// NOLINT`
- C#: `#pragma warning disable`, `[SuppressMessage]`
- Swift: `// swiftlint:disable`

This list is representative. Recognize language-specific equivalents for any language encountered in scope.

### Explanatory Block Comments

Identify multi-sentence comments that contain words suggesting rationale:

`because`, `trade-off`, `instead of`, `chosen`, `deliberately`, `intentionally`, `the reason`, `we decided`, `this approach`, `opted for`, `prefer`, `avoid`, `risk of`, `constraint`

Focus on comments that explain *why*, not *what*. A comment restating what the code does provides no intent signal.

### Config File Comments

Check for rationale embedded in configuration files:

`.env.example`, `Dockerfile`, `docker-compose.yml`, CI configuration files (`.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/config.yml`), `Makefile`, `pyproject.toml`, `package.json`, `tsconfig.json`, build configuration files.

### Report Format

```
- **Source:** <file path>:<line number>
  **Comment:** "<comment text>"
  **Interpretation:** <brief statement of the intent signal>
```

---

## History Scanner

### Objective

Extract intent signals from git commit history for in-scope files. Identify commits whose messages explain *why* a change was made, particularly architectural changes, deliberate removals, and design pivots.

### Execution

Run `git log` on in-scope files to retrieve commit messages. Limit to the most recent 200 commits per file (or use `--since="1 year ago"` for long-lived repositories) to avoid unbounded retrieval on large histories. Use `--follow` for renamed files when practical.

### Filtering

**Include** commits with substantive messages that explain rationale:

- Messages containing words like `because`, `instead of`, `trade-off`, `refactor`, `redesign`, `migrate`, `deprecate`, `remove`, `revert`, `security`, `performance`, `simplify`, `consolidate`.
- Merge and PR commit messages, which often contain richer context than individual commits.
- Commits that touch many files simultaneously (potential architectural changes).

**Exclude** noise commits with messages that provide no intent signal:

- `fix typo`, `bump version`, `update dependencies`, `formatting`, `lint`, `wip`, `merge branch`, single-word messages, auto-generated messages.

### Graceful Handling

If no git history is available (fresh `git init`, exported tarball, shallow clone with insufficient depth), report "No meaningful git history available" and complete without error. Do not fail the overall intent discovery process.

### Report Format

```
- **Commit:** <short hash>
  **Date:** <YYYY-MM-DD>
  **Summary:** <one-line summary of the intent signal from the commit message>
  **Files:** <comma-separated list of affected in-scope files>
```

---

## Intent Brief Template

Merge and deduplicate entries from all three subagents into the following structure. Omit sections that have no entries.

```markdown
## Intent Brief

### Architectural Decisions
- <decision summary> (source: <file or commit>)

### Deliberate Trade-offs
- <trade-off summary> (source: <file or commit>)

### Conventions & Standards
- <convention summary> (source: <file or commit>)

### Known Limitations & Technical Debt
- <limitation summary> (source: <file or commit>)

### Suppressed Warnings & Intentional Deviations
- <deviation summary> (source: <file or commit>)
```

---

## Size and Prioritization

Target no more than 100 entries in the Intent Brief. When raw entries exceed this limit:

- Filter by relevance to the confirmed audit categories. Discard entries unrelated to any category being audited.
- Rank remaining entries by specificity — a per-file suppression directive is more useful than a general architectural statement.
- Prioritize entries that directly address patterns the audit checklists would flag (e.g., a documented decision to use mutable global state is highly relevant to the anti-patterns category).

---

## Re-audit Behavior

Regenerate the Intent Brief from scratch on every audit run. Never persist or cache the Intent Brief between runs.
