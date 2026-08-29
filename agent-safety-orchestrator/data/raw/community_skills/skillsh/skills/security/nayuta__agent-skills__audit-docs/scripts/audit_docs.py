#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""
audit_docs.py

Static validator for CLAUDE.md and AGENTS.md documentation files.

Validates:
- Marker format (required comment markers exist)
- Table structure (3 columns, separator row, valid format)
- Link validity (all file links resolve)
- Skill completeness (all skills listed unless unlisted: true)
- Agent completeness (all agents listed)
- Synchronization (AGENTS.md body matches CLAUDE.md)
- File-level checks (FILE_TOO_LONG, IMPORT_BROKEN, IMPORT_SENSITIVE)
- Cross-reference accuracy (DESCRIPTION_MISMATCH, NAME_MISMATCH)
- AGENTS.md import check (AGENTS_NO_IMPORT)
- Rules directory validation (RULES_INVALID_PATHS, RULES_BROKEN_LINK)
- Body-sensitive content (BODY_SENSITIVE)

Exit codes:
- 0: All checks passed
- 1: Issues found
- 2: Fatal error
"""
from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import re
import sys
from pathlib import Path
from typing import Optional, Sequence


@dataclasses.dataclass
class Finding:
    """Represents a validation finding."""
    severity: str  # ERROR, WARN, INFO
    code: str
    message: str
    file: str
    line: Optional[int] = None


@dataclasses.dataclass
class Report:
    """Validation report containing all findings."""
    findings: list[Finding]

    def has_errors(self) -> bool:
        """Check if report contains any errors."""
        return any(f.severity == "ERROR" for f in self.findings)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str, bool]:
    """
    Parse YAML frontmatter from markdown text.

    Returns: (frontmatter_dict, body, had_frontmatter)
    """
    if not text.startswith("---"):
        return {}, text, False

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, text, False

    raw_frontmatter = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:])

    # Simple key: value parser (no PyYAML dependency)
    data: dict[str, str] = {}
    for line in raw_frontmatter.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        # Handle boolean values
        value_stripped = value.strip().strip('"').strip()
        if value_stripped.lower() == "true":
            data[key.strip()] = "true"
        elif value_stripped.lower() == "false":
            data[key.strip()] = "false"
        else:
            data[key.strip()] = value_stripped

    return data, body, True


def find_marker_section(text: str, start_marker: str, end_marker: str) -> tuple[Optional[str], Optional[int], Optional[int]]:
    """
    Find content between marker comments.

    Returns: (content, start_line, end_line) or (None, None, None) if not found
    """
    start_pattern = f"<!-- {start_marker} -->"
    end_pattern = f"<!-- {end_marker} -->"

    start_idx = text.find(start_pattern)
    end_idx = text.find(end_pattern)

    if start_idx == -1 or end_idx == -1:
        return None, None, None

    if end_idx <= start_idx:
        return None, None, None

    # Get line numbers
    start_line = text[:start_idx].count("\n") + 1
    end_line = text[:end_idx].count("\n") + 1

    # Extract content between markers
    content_start = start_idx + len(start_pattern)
    content = text[content_start:end_idx]

    return content.strip(), start_line, end_line


def validate_table(table_text: str, file: str, line: int) -> list[Finding]:
    """
    Validate markdown table format.

    Expected format:
    | Name | Description | Link |
    | :--- | :---------- | :--- |
    | ... | ... | ... |
    """
    findings: list[Finding] = []

    if not table_text:
        findings.append(Finding("ERROR", "TABLE_MALFORMED", "Table is empty", file, line))
        return findings

    lines = [l for l in table_text.splitlines() if l.strip()]

    if len(lines) < 2:
        findings.append(Finding("ERROR", "TABLE_MALFORMED", "Table must have at least header and separator rows", file, line))
        return findings

    # Check header row
    header_line = lines[0]
    header_cols = [c.strip() for c in header_line.split("|") if c.strip()]

    if len(header_cols) != 3:
        findings.append(Finding("ERROR", "TABLE_MALFORMED", f"Table must have 3 columns (Name, Description, Link), found {len(header_cols)}", file, line))
        return findings

    # Check separator row
    separator_line = lines[1]
    separator_cols = [c.strip() for c in separator_line.split("|") if c.strip()]

    if len(separator_cols) != 3:
        findings.append(Finding("ERROR", "TABLE_MALFORMED", "Separator row must have 3 columns", file, line + 1))
    else:
        sep_pattern = re.compile(r"^:?-+:?$")
        for col in separator_cols:
            if not sep_pattern.match(col):
                findings.append(Finding("ERROR", "TABLE_MALFORMED", f"Invalid separator syntax: '{col}' (expected pattern like :--- or ---)", file, line + 1))

    # Validate data rows have 3 columns
    for i, data_line in enumerate(lines[2:], start=2):
        data_cols = [c.strip() for c in data_line.split("|") if c.strip()]
        if len(data_cols) != 3:
            findings.append(Finding("ERROR", "TABLE_MALFORMED", f"Data row must have 3 columns, found {len(data_cols)}", file, line + i))

    return findings


_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def extract_table_links(table_text: str) -> list[str]:
    """Extract file paths from markdown links in table."""
    links: list[str] = []

    for match in _LINK_PATTERN.finditer(table_text):
        link_path = match.group(2).strip()
        # Filter out external links and anchors
        if not link_path.startswith(("http://", "https://", "#", "mailto:")):
            links.append(link_path)

    return links


def extract_table_names(table_text: str) -> set[str]:
    """Extract names from first column of table."""
    names: set[str] = set()
    lines = [l for l in table_text.splitlines() if l.strip()]

    # Skip header and separator rows
    for line in lines[2:]:
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if cols:
            names.add(cols[0])

    return names


def strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks and inline code spans from markdown text."""
    text = re.sub(r'^(`{3,})[^\n]*\n.*?^\1', '', text, flags=re.DOTALL | re.MULTILINE)
    text = re.sub(r'^(~{3,})[^\n]*\n.*?^\1', '', text, flags=re.DOTALL | re.MULTILINE)
    text = re.sub(r'`[^`]+`', '', text)
    return text


def extract_table_rows(table_text: str) -> list[dict[str, str]]:
    """
    Extract rows from a markdown table as dicts with keys: name, description, link.

    Parses data rows (skipping header and separator) and extracts the three columns.
    The link column value is the raw cell text (may contain markdown link syntax).
    """
    rows: list[dict[str, str]] = []
    lines = [l for l in table_text.splitlines() if l.strip()]

    # Skip header and separator rows
    for line in lines[2:]:
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) >= 3:
            rows.append({
                "name": cols[0],
                "description": cols[1],
                "link": cols[2],
            })

    return rows


def validate_claude_md(repo_path: Path) -> Report:
    """Validate CLAUDE.md file."""
    findings: list[Finding] = []
    claude_path = repo_path / "CLAUDE.md"

    if not claude_path.exists():
        findings.append(Finding("ERROR", "FILE_MISSING", "CLAUDE.md not found", str(claude_path), None))
        return Report(findings)

    text = claude_path.read_text(encoding="utf-8")

    # Check markers
    required_markers = [
        ("AVAILABLE_SKILLS_START", "AVAILABLE_SKILLS_END"),
        ("AVAILABLE_AGENTS_START", "AVAILABLE_AGENTS_END"),
    ]

    skill_table_text = None
    agent_table_text = None

    for start_marker, end_marker in required_markers:
        content, start_line, end_line = find_marker_section(text, start_marker, end_marker)

        if content is None:
            findings.append(Finding("ERROR", "MARKER_MISSING", f"Missing marker pair: {start_marker} / {end_marker}", str(claude_path), None))
        else:
            # Validate table format
            if "SKILLS" in start_marker:
                skill_table_text = content
                findings.extend(validate_table(content, str(claude_path), start_line + 1))
            elif "AGENTS" in start_marker:
                agent_table_text = content
                findings.extend(validate_table(content, str(claude_path), start_line + 1))

    # Validate links in skills table
    if skill_table_text:
        links = extract_table_links(skill_table_text)
        for link in links:
            link_path = repo_path / link
            if not link_path.exists():
                findings.append(Finding("ERROR", "LINK_BROKEN", f"Broken link: {link}", str(claude_path), None))

    # Validate links in agents table
    if agent_table_text:
        links = extract_table_links(agent_table_text)
        for link in links:
            link_path = repo_path / link
            if not link_path.exists():
                findings.append(Finding("ERROR", "LINK_BROKEN", f"Broken link: {link}", str(claude_path), None))

    # Check for unlisted skills in both .claude/skills/ and root skills/
    listed_skills = extract_table_names(skill_table_text) if skill_table_text else set()
    skills_dirs = [repo_path / ".claude/skills", repo_path / "skills"]

    for skills_dir in skills_dirs:
        if not skills_dir.exists():
            continue

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            # Parse frontmatter to check for unlisted flag
            skill_text = skill_md.read_text(encoding="utf-8")
            frontmatter, _, had_fm = parse_frontmatter(skill_text)

            # Skip if unlisted: true
            if frontmatter.get("unlisted") == "true":
                continue

            skill_name = frontmatter.get("name", skill_dir.name)

            if skill_name not in listed_skills:
                findings.append(Finding("ERROR", "SKILL_UNLISTED", f"Skill '{skill_name}' not listed in CLAUDE.md table", str(skill_md), None))

    # Check for unlisted agents
    agents_dir = repo_path / ".claude/agents"
    if agents_dir.exists():
        listed_agents = extract_table_names(agent_table_text) if agent_table_text else set()

        for agent_file in agents_dir.glob("*.md"):
            # Parse frontmatter
            agent_text = agent_file.read_text(encoding="utf-8")
            frontmatter, _, had_fm = parse_frontmatter(agent_text)

            # Skip if unlisted: true
            if frontmatter.get("unlisted") == "true":
                continue

            agent_name = frontmatter.get("name", agent_file.stem)

            if agent_name not in listed_agents:
                findings.append(Finding("ERROR", "AGENT_UNLISTED", f"Agent '{agent_name}' not listed in CLAUDE.md table", str(agent_file), None))

    # Cross-reference checks: DESCRIPTION_MISMATCH and NAME_MISMATCH
    for table_text in [skill_table_text, agent_table_text]:
        if not table_text:
            continue
        for row in extract_table_rows(table_text):
            link_match = re.search(r'\[([^\]]*)\]\(([^)]+)\)', row["link"])
            if not link_match:
                continue
            link_path = link_match.group(2).strip()
            target = repo_path / link_path
            if not target.exists():
                continue
            target_text = target.read_text(encoding="utf-8")
            fm, _, had_fm = parse_frontmatter(target_text)
            if not had_fm:
                continue
            # NAME_MISMATCH
            fm_name = fm.get("name", "").strip()
            if fm_name and row["name"] != fm_name:
                findings.append(Finding("ERROR", "NAME_MISMATCH", f"Table name '{row['name']}' differs from frontmatter name '{fm_name}' in {link_path}", str(claude_path), None))
            # DESCRIPTION_MISMATCH
            fm_desc = fm.get("description", "").strip()
            table_desc = row["description"].strip()
            if fm_desc and table_desc and fm_desc != table_desc:
                findings.append(Finding("WARN", "DESCRIPTION_MISMATCH", f"Table description for '{row['name']}' differs from frontmatter in {link_path}", str(claude_path), None))

    return Report(findings)


def validate_agents_sync(repo_path: Path) -> Report:
    """Validate that AGENTS.md body matches CLAUDE.md."""
    findings: list[Finding] = []

    claude_path = repo_path / "CLAUDE.md"
    agents_path = repo_path / "AGENTS.md"

    # Skip check if AGENTS.md doesn't exist
    if not agents_path.exists():
        return Report(findings)

    if not claude_path.exists():
        return Report(findings)  # Already reported in validate_claude_md

    claude_text = claude_path.read_text(encoding="utf-8")
    agents_text = agents_path.read_text(encoding="utf-8")

    # Extract body (everything after first line)
    claude_lines = claude_text.splitlines()
    agents_lines = agents_text.splitlines()

    # Validate first-line headers
    if claude_lines and claude_lines[0].strip() != "# CLAUDE.md":
        findings.append(Finding("WARN", "HEADER_UNEXPECTED", f"Expected first line '# CLAUDE.md', found '{claude_lines[0].strip()}'", str(claude_path), 1))
    if agents_lines and agents_lines[0].strip() != "# AGENTS.md":
        findings.append(Finding("WARN", "HEADER_UNEXPECTED", f"Expected first line '# AGENTS.md', found '{agents_lines[0].strip()}'", str(agents_path), 1))

    claude_body = "\n".join(claude_lines[1:]) if len(claude_lines) > 1 else ""
    agents_body = "\n".join(agents_lines[1:]) if len(agents_lines) > 1 else ""

    if claude_body.strip() != agents_body.strip():
        findings.append(Finding("ERROR", "AGENTS_DESYNC", "AGENTS.md body differs from CLAUDE.md (excluding first line)", str(agents_path), 2))

    return Report(findings)


def validate_file_level(repo_path: Path) -> Report:
    """
    File-level checks for CLAUDE.md.

    Checks:
    - FILE_TOO_LONG: CLAUDE.md over 200 lines
    - IMPORT_BROKEN: @path imports that don't resolve
    - IMPORT_SENSITIVE: @path imports to sensitive files
    """
    findings: list[Finding] = []
    claude_path = repo_path / "CLAUDE.md"

    if not claude_path.exists():
        return Report(findings)

    text = claude_path.read_text(encoding="utf-8")

    # FILE_TOO_LONG
    line_count = len(text.splitlines())
    if line_count > 200:
        findings.append(Finding("WARN", "FILE_TOO_LONG", f"CLAUDE.md has {line_count} lines (recommended max: 200)", str(claude_path), None))

    # IMPORT_BROKEN and IMPORT_SENSITIVE
    # Strip code blocks first so we don't flag @paths inside them
    text_no_code = strip_code_blocks(text)

    # Pattern: @ followed by a file path, but NOT email addresses
    # Import pattern: @path/to/file or @filename.ext (starts with . or word, contains / or .)
    import_pattern = re.compile(r'(?<!\w)@(\.?[\w][\w./\-]*)')

    sensitive_patterns = [".env", ".pem", ".key", "credentials", "secret", "password", "token"]
    # File extensions recognized as imports (not email domains)
    file_extensions = {'.md', '.py', '.js', '.ts', '.yml', '.yaml', '.json', '.toml', '.txt', '.sh', '.env', '.pem', '.key'}

    for match in import_pattern.finditer(text_no_code):
        import_path = match.group(1)

        # Must contain a path separator or file extension to be considered an import
        if '/' not in import_path and '.' not in import_path:
            continue

        # For bare names without slashes (e.g., "example.com" vs "AGENTS.md"),
        # skip email-domain-like patterns that don't have recognized file extensions
        if '/' not in import_path and re.match(r'^[\w-]+\.\w+$', import_path):
            if not any(import_path.endswith(ext) for ext in file_extensions):
                continue

        resolved = repo_path / import_path
        if not resolved.exists():
            findings.append(Finding("ERROR", "IMPORT_BROKEN", f"Broken import: @{import_path}", str(claude_path), None))
        else:
            import_path_lower = import_path.lower()
            if any(pat in import_path_lower for pat in sensitive_patterns):
                findings.append(Finding("WARN", "IMPORT_SENSITIVE", f"Import references sensitive file: @{import_path}", str(claude_path), None))

    return Report(findings)


def validate_agents_import(repo_path: Path) -> Report:
    """
    Check if CLAUDE.md should import AGENTS.md.

    AGENTS_NO_IMPORT: Warns when AGENTS.md exists, CLAUDE.md lacks @AGENTS.md import,
    and the bodies are NOT already synchronized.
    """
    findings: list[Finding] = []
    claude_path = repo_path / "CLAUDE.md"
    agents_path = repo_path / "AGENTS.md"

    if not agents_path.exists() or not claude_path.exists():
        return Report(findings)

    claude_text = claude_path.read_text(encoding="utf-8")
    agents_text = agents_path.read_text(encoding="utf-8")

    # Check if @AGENTS.md appears outside code blocks
    text_no_code = strip_code_blocks(claude_text)
    has_import = bool(re.search(r'(?<!\w)@AGENTS\.md', text_no_code))

    if has_import:
        return Report(findings)

    # Check if bodies are in sync
    claude_lines = claude_text.splitlines()
    agents_lines = agents_text.splitlines()
    claude_body = "\n".join(claude_lines[1:]) if len(claude_lines) > 1 else ""
    agents_body = "\n".join(agents_lines[1:]) if len(agents_lines) > 1 else ""

    if claude_body.strip() == agents_body.strip():
        # Bodies in sync — no warning needed
        return Report(findings)

    findings.append(Finding("WARN", "AGENTS_NO_IMPORT", "CLAUDE.md lacks @AGENTS.md import while AGENTS.md exists and bodies differ", str(claude_path), None))

    return Report(findings)


def validate_rules_dir(repo_path: Path) -> Report:
    """
    Validate .claude/rules/ directory.

    Checks:
    - RULES_INVALID_PATHS: Invalid glob patterns in frontmatter
    - RULES_BROKEN_LINK: Broken markdown links in rule files
    """
    findings: list[Finding] = []
    rules_dir = repo_path / ".claude/rules"

    if not rules_dir.exists():
        return Report(findings)

    for rule_file in rules_dir.glob("*.md"):
        rule_text = rule_file.read_text(encoding="utf-8")
        fm, body, had_fm = parse_frontmatter(rule_text)

        # RULES_INVALID_PATHS: validate glob patterns
        if had_fm and "globs" in fm:
            globs_value = fm["globs"]
            # Handle comma-separated globs
            patterns = [p.strip() for p in globs_value.split(",")]
            for pattern in patterns:
                if not pattern:
                    continue
                if pattern.count('[') != pattern.count(']'):
                    findings.append(Finding("WARN", "RULES_INVALID_PATHS", f"Invalid glob pattern '{pattern}' in {rule_file.name}: unbalanced brackets", str(rule_file), None))
                    continue
                try:
                    re.compile(fnmatch.translate(pattern))
                except re.error:
                    findings.append(Finding("WARN", "RULES_INVALID_PATHS", f"Invalid glob pattern '{pattern}' in {rule_file.name}", str(rule_file), None))

        # RULES_BROKEN_LINK: check markdown links
        for match in _LINK_PATTERN.finditer(body if had_fm else rule_text):
            link_path = match.group(2).strip()
            # Skip external links
            if link_path.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = repo_path / link_path
            if not target.exists():
                findings.append(Finding("ERROR", "RULES_BROKEN_LINK", f"Broken link '{link_path}' in {rule_file.name}", str(rule_file), None))

    return Report(findings)


def validate_body_sensitive(repo_path: Path) -> Report:
    """
    Check CLAUDE.md body text for hardcoded secrets.

    Scans outside fenced code blocks for patterns like API keys,
    Bearer tokens, password assignments, and database connection strings.
    Complements IMPORT_SENSITIVE which only checks @path import targets.
    """
    findings: list[Finding] = []
    claude_path = repo_path / "CLAUDE.md"

    if not claude_path.exists():
        return Report(findings)

    text = claude_path.read_text(encoding="utf-8")
    text_no_code = strip_code_blocks(text)

    secret_patterns: list[tuple[str, re.Pattern[str]]] = [
        ("AWS access key", re.compile(r'AKIA[0-9A-Z]{16}')),
        ("Bearer token", re.compile(r'Bearer\s+[A-Za-z0-9\-._~+/]{20,}=*', re.IGNORECASE)),
        ("API key assignment", re.compile(r'(?:api[_-]?key|apikey)\s*[:=]\s*\S+', re.IGNORECASE)),
        ("password assignment", re.compile(r'\b(?:password|passwd|pwd)\s*=\s*\S{8,}', re.IGNORECASE)),
        ("secret/token assignment", re.compile(r'\b(?:secret|token)\s*=\s*\S{8,}', re.IGNORECASE)),
        ("database connection string", re.compile(r'(?:mysql|postgres(?:ql)?|mongodb|redis)://[^\s]+@[^\s]+', re.IGNORECASE)),
    ]

    matched_regions: list[tuple[int, int]] = []

    # Common placeholder words used in documentation examples
    _PLACEHOLDER_WORDS_RE = re.compile(
        r'(?<![a-zA-Z])(?:your|replace|example|xxx|changeme|placeholder|sample|here)(?![a-zA-Z])',
        re.IGNORECASE,
    )

    for label, pattern in secret_patterns:
        for match in pattern.finditer(text_no_code):
            matched_text = match.group()

            # --- Placeholder filtering (before overlap check) ---
            # Skip placeholder values in key=value patterns
            kv_match = re.search(r'[:=]\s*(\S)', matched_text)
            if kv_match and kv_match.group(1) in ('$', '<', '{'):
                continue
            if 'ENV[' in matched_text.upper():
                continue

            # For key=value patterns, extract the value portion for extra checks
            kv_value_match = re.search(r'[:=]\s*(\S+)', matched_text)
            if kv_value_match:
                value_part = kv_value_match.group(1)
                # Skip ALL_CAPS values (likely env var names like API_KEY, TOKEN_NAME)
                if re.fullmatch(r'[A-Z][A-Z0-9_]{2,}', value_part):
                    continue
                # Skip values containing common placeholder words
                if _PLACEHOLDER_WORDS_RE.search(value_part):
                    continue

            # Skip bearer tokens that look like placeholders
            if label == "Bearer token":
                parts = matched_text.split(None, 1)
                token_part = parts[1] if len(parts) > 1 else ''
                if re.search(r'[<>{}]', token_part):
                    continue
                if _PLACEHOLDER_WORDS_RE.search(token_part):
                    continue

            # --- Overlap deduplication (after placeholder filtering) ---
            # Standard interval overlap: two spans overlap iff neither is
            # entirely before or entirely after the other.
            span = (match.start(), match.end())
            if any(not (span[1] <= s or span[0] >= e) for s, e in matched_regions):
                continue

            matched_regions.append(span)
            msg = (
                f"Possible {label} in CLAUDE.md body: '{matched_text[:50]}...'"
                if len(matched_text) > 50
                else f"Possible {label} in CLAUDE.md body: '{matched_text}'"
            )
            findings.append(Finding("WARN", "BODY_SENSITIVE", msg, str(claude_path), None))

    return Report(findings)


def format_report(report: Report) -> str:
    """Format report as human-readable text."""
    if not report.findings:
        return "All checks passed."

    lines: list[str] = []
    for finding in report.findings:
        loc = f"{finding.file}:{finding.line}" if finding.line else finding.file
        lines.append(f"[{finding.severity}] {finding.code} @ {loc} :: {finding.message}")

    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate CLAUDE.md and AGENTS.md documentation files.")
    parser.add_argument("repo_path", help="Path to repository root containing CLAUDE.md")
    args = parser.parse_args(argv)

    repo_path = Path(args.repo_path).resolve()

    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}", file=sys.stderr)
        return 2

    if not repo_path.is_dir():
        print(f"Error: Path is not a directory: {repo_path}", file=sys.stderr)
        return 2

    # Run validations
    claude_report = validate_claude_md(repo_path)
    sync_report = validate_agents_sync(repo_path)
    file_level_report = validate_file_level(repo_path)
    agents_import_report = validate_agents_import(repo_path)
    rules_report = validate_rules_dir(repo_path)
    body_sensitive_report = validate_body_sensitive(repo_path)

    # Combine findings
    all_findings = (claude_report.findings + sync_report.findings +
                    file_level_report.findings + agents_import_report.findings +
                    rules_report.findings + body_sensitive_report.findings)
    combined_report = Report(all_findings)

    # Print report
    print(format_report(combined_report))

    # Return exit code
    if combined_report.has_errors():
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
