---
name: audit-docs
description: Validate CLAUDE.md and AGENTS.md against actual codebase structure and conventions.
---

# Audit Documentation Files

## Purpose

This skill provides static validation of `CLAUDE.md` and `AGENTS.md` documentation files to ensure they accurately reflect the actual codebase structure and follow proper conventions.

## What It Validates

### 1. Marker Format (MARKER_MISSING)

Required comment marker pairs must exist:

- `<!-- AVAILABLE_SKILLS_START -->` / `<!-- AVAILABLE_SKILLS_END -->`
- `<!-- AVAILABLE_AGENTS_START -->` / `<!-- AVAILABLE_AGENTS_END -->`

### 2. Table Structure (TABLE_MALFORMED)

Tables must have:

- Exactly 3 columns: Name | Description | Link
- Proper separator row with `:---` alignment
- Non-empty, well-formed markdown table syntax

### 3. Link Validity (LINK_BROKEN)

All file links in tables must:

- Resolve to existing files in the repository
- Use correct relative paths

### 4. Skill Completeness (SKILL_UNLISTED)

All skills in `.claude/skills/` and `skills/` must:

- Be listed in the Available Skills table
- Both directories are scanned: `.claude/skills/` (project skills) and `skills/` (distributed skills installed via `npx skills add`)
- Exception: Skills with `unlisted: true` in frontmatter are ignored

### 5. Agent Completeness (AGENT_UNLISTED)

All agents in `.claude/agents/` must:

- Be listed in the Available Agents table
- Exception: Agents with `unlisted: true` in frontmatter are ignored

### 6. Synchronization (AGENTS_DESYNC)

`AGENTS.md` must:

- Have identical body content to `CLAUDE.md` (excluding first line)
- The first line of `AGENTS.md` is `# AGENTS.md` while `CLAUDE.md` is `# CLAUDE.md`

### 7. File Length (FILE_TOO_LONG)

`CLAUDE.md` should not exceed 200 lines (official Claude Code recommendation):

- Severity: WARN
- Counts total lines in the file

### 8. Import Resolution (IMPORT_BROKEN)

`@path` imports in CLAUDE.md text must resolve to existing files:

- Regex-based detection of `@path` references outside fenced code blocks
- Excludes email addresses (e.g., `user@example.com`)
- Severity: ERROR

### 9. Sensitive Imports (IMPORT_SENSITIVE)

`@path` imports should not reference sensitive files:

- Checks for patterns: `.env`, `.pem`, `.key`, `credentials`, `secret`, `password`, `token`
- Only checked for valid (existing) imports
- Severity: WARN

### 10. Description Accuracy (DESCRIPTION_MISMATCH)

Table descriptions must match frontmatter descriptions:

- Compares description column in skills/agents tables with `description` field in SKILL.md or agent frontmatter
- Skips if either description is empty
- Severity: WARN

### 11. Name Accuracy (NAME_MISMATCH)

Table names must match frontmatter names:

- Compares name column in skills/agents tables with `name` field in frontmatter
- Severity: ERROR

### 12. AGENTS.md Import (AGENTS_NO_IMPORT)

CLAUDE.md should import AGENTS.md when it exists and bodies differ:

- Warns when AGENTS.md exists, no `@AGENTS.md` import is present, and bodies are not synchronized
- No warning if bodies are already in sync (content is already there)
- Severity: WARN

### 13. Rules Glob Patterns (RULES_INVALID_PATHS)

Glob patterns in `.claude/rules/*.md` frontmatter must be valid:

- Validates `globs` field in each rule file's frontmatter
- Checks bracket balance and uses `fnmatch` to verify pattern validity
- Graceful no-op when `.claude/rules/` doesn't exist
- Severity: WARN

### 14. Rules Links (RULES_BROKEN_LINK)

Markdown links in `.claude/rules/*.md` files must resolve:

- Checks `[text](path)` links in rule file bodies
- Excludes external links (http://, https://, #, mailto:)
- Resolves paths relative to repository root
- Graceful no-op when `.claude/rules/` doesn't exist
- Severity: ERROR

### 15. Body Sensitive Content (BODY_SENSITIVE)

CLAUDE.md body text must not contain hardcoded secrets:

- Scans text outside fenced code blocks for secret patterns
- Detects: AWS access keys, Bearer tokens, API key assignments, password assignments, secret/token assignments, database connection strings
- Complements IMPORT_SENSITIVE (which only checks `@path` import targets)
- Only scans CLAUDE.md (AGENTS.md is intentionally excluded)
- Severity: WARN

## Usage

### Basic Validation

```bash
# Validate current repository
uv run .claude/skills/audit-docs/scripts/audit_docs.py .

# Validate specific repository
uv run .claude/skills/audit-docs/scripts/audit_docs.py /path/to/repo
```

### Via Makefile

```bash
make audit-docs
```

### Exit Codes

- `0` - All checks passed
- `1` - Issues found (validation errors)
- `2` - Fatal error (invalid arguments, invalid repository path)

## Output Format

Human-readable plain text listing all findings:

```
[ERROR] MARKER_MISSING @ /path/to/CLAUDE.md :: Missing marker pair: AVAILABLE_SKILLS_START / AVAILABLE_SKILLS_END
[ERROR] SKILL_UNLISTED @ /path/to/.claude/skills/example/SKILL.md :: Skill 'example' not listed in CLAUDE.md table
[ERROR] LINK_BROKEN @ /path/to/CLAUDE.md :: Broken link: .claude/skills/missing/SKILL.md
```

## Edge Cases

- **Missing CLAUDE.md**: Reports `FILE_MISSING` error
- **Empty skills directory**: Passes (no findings)
- **Skill directory without SKILL.md**: Ignored (not validated)
- **Skills with `unlisted: true`**: Excluded from completeness check
- **No AGENTS.md**: Skips synchronization check
- **Multi-line table cells**: Not supported; rows are validated line-by-line
- **Email addresses**: `user@example.com` is not treated as an `@import`
- **Code blocks**: `@path` references inside fenced code blocks are ignored
- **No `.claude/rules/` directory**: Skips rules validation (no findings)

## Implementation Details

- **Zero dependencies**: Uses only Python 3.11+ standard library
- **PEP 723 compliant**: Inline script metadata for `uv run`
- **Simple frontmatter parser**: Manual YAML parsing for basic key: value pairs
- **Pattern**: Follows `skill_audit.py` architecture (dataclasses, Finding/Report)

## Testing

Run test suite:

```bash
uv run pytest .claude/skills/audit-docs/test/test_audit_docs.py -v
```

49 test functions covering:

1. Valid CLAUDE.md passes
2. Missing markers fail
3. Invalid table format fails
4. Broken links fail
5. Orphan skills fail
6. Unlisted frontmatter ignored
7. AGENTS.md desync fails
8. Exit code 0 for clean
9. Exit code 1 for issues
10. Unlisted agents fail
11. Root skills/ unlisted triggers SKILL_UNLISTED
12. Root skills/ with unlisted: true ignored
13. Skills in both directories pass when all listed
14. FILE_TOO_LONG warns on 201+ lines
15. File under 200 lines passes
16. IMPORT_BROKEN on nonexistent @path
17. Valid @import passes
18. @path in code block ignored
19. @path in code block with backticks ignored
20. IMPORT_SENSITIVE on .env/@secrets.key
21. Non-sensitive import passes
22. DESCRIPTION_MISMATCH warns
23. Matching description passes
24. NAME_MISMATCH on differing names
25. Matching name passes
26. AGENTS_NO_IMPORT warns when bodies differ
27. @AGENTS.md import present passes
28. Synced bodies produce no warning
29. Invalid glob pattern warns
30. Valid glob pattern passes
31. Broken link in rules fails
32. Valid link in rules passes
33. Email not treated as import
34. No rules directory passes
35. @path in inline code ignored
36. IMPORT_SENSITIVE on sensitive directories
37. BODY_SENSITIVE on API key assignment
38. BODY_SENSITIVE on database connection string
39. Clean CLAUDE.md produces no BODY_SENSITIVE
40. Secrets in code blocks ignored by BODY_SENSITIVE
41. BODY_SENSITIVE on Bearer token
42. BODY_SENSITIVE on AWS access key
43. Underscore-joined placeholder values not flagged
44. Placeholder with trailing digits not flagged
45. Underscore-joined replace_this_value not flagged
46. sample_token_value placeholder not flagged
47. Placeholder with example between underscores not flagged
48. Real-looking secrets still flagged (no regression)
49. Secrets inside 4+ tilde fences ignored by strip_code_blocks

## Integration

This skill is designed to be:

- Run in CI/CD pipelines to catch documentation drift
- Integrated into pre-commit hooks
- Used by documentation maintenance agents
- Part of the `mend-docs` skill workflow
