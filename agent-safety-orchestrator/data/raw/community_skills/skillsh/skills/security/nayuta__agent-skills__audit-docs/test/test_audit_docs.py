#!/usr/bin/env python3
"""
test_audit_docs.py

Test suite for audit_docs.py script.
Tests the 15 categories of static checks plus exit code behavior.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent


def _minimal_claude_md() -> str:
    """Return a minimal valid CLAUDE.md with empty tables."""
    return dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_SKILLS_END -->

        ## Available Agents

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """)


def test_valid_claude_passes(tmp_path: Path) -> None:
    """Test that a valid CLAUDE.md with all skills and agents listed passes."""
    # Create valid skill
    skill_dir = tmp_path / ".claude/skills/listed-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: listed-skill
        description: A listed skill for testing
        ---

        # Listed Skill

        This skill is properly listed in the table.
        """))

    # Create valid agent
    agent_file = tmp_path / ".claude/agents/example-agent.md"
    agent_file.parent.mkdir(parents=True, exist_ok=True)
    agent_file.write_text(dedent("""\
        ---
        name: example-agent
        description: An example agent for testing
        ---

        # Example Agent

        This agent is properly listed.
        """))

    # Create valid CLAUDE.md
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |
        | listed-skill | A listed skill for testing | [.claude/skills/listed-skill/SKILL.md](.claude/skills/listed-skill/SKILL.md) |

        <!-- AVAILABLE_SKILLS_END -->

        ## Available Agents

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |
        | example-agent | An example agent for testing | [.claude/agents/example-agent.md](.claude/agents/example-agent.md) |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    # Run audit_docs.py
    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should pass with exit code 0
    assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}. Output: {result.stdout}\nError: {result.stderr}"


def test_missing_marker_fails(tmp_path: Path) -> None:
    """Test that missing or malformed markers cause MARKER_MISSING error."""
    # Create CLAUDE.md without proper markers
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        Some text but no markers.
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should fail with MARKER_MISSING error
    assert result.returncode == 1
    assert "MARKER_MISSING" in result.stdout or "marker" in result.stdout.lower()


def test_invalid_table_format_fails(tmp_path: Path) -> None:
    """Test that malformed table structure causes TABLE_MALFORMED error."""
    # Create CLAUDE.md with invalid table (only 2 columns instead of 3)
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description |
        | :--- | :---------- |
        | test-skill | A test skill |

        <!-- AVAILABLE_SKILLS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should fail with TABLE_MALFORMED error
    assert result.returncode == 1
    assert "TABLE_MALFORMED" in result.stdout or "table" in result.stdout.lower()


def test_broken_link_fails(tmp_path: Path) -> None:
    """Test that broken file links cause LINK_BROKEN error."""
    # Create CLAUDE.md with link to non-existent file
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |
        | missing-skill | This skill doesn't exist | [.claude/skills/missing-skill/SKILL.md](.claude/skills/missing-skill/SKILL.md) |

        <!-- AVAILABLE_SKILLS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should fail with LINK_BROKEN error
    assert result.returncode == 1
    assert "LINK_BROKEN" in result.stdout or "broken" in result.stdout.lower()


def test_orphan_skill_fails(tmp_path: Path) -> None:
    """Test that skills not listed in the table cause SKILL_UNLISTED error."""
    # Create skill that's not listed in CLAUDE.md
    skill_dir = tmp_path / ".claude/skills/orphan-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: orphan-skill
        description: This skill is not listed in the table
        ---

        # Orphan Skill

        This should trigger SKILL_UNLISTED.
        """))

    # Create CLAUDE.md without this skill
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_SKILLS_END -->

        ## Available Agents

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should fail with SKILL_UNLISTED error
    assert result.returncode == 1
    assert "SKILL_UNLISTED" in result.stdout or "unlisted" in result.stdout.lower()


def test_unlisted_frontmatter_ignored(tmp_path: Path) -> None:
    """Test that skills with unlisted: true in frontmatter are ignored."""
    # Create skill with unlisted: true
    skill_dir = tmp_path / ".claude/skills/unlisted-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: unlisted-skill
        description: This skill has unlisted flag
        unlisted: true
        ---

        # Unlisted Skill

        This should NOT trigger SKILL_UNLISTED.
        """))

    # Create CLAUDE.md without this skill
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_SKILLS_END -->

        ## Available Agents

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should pass because unlisted skills are ignored
    assert result.returncode == 0


def test_agents_desync_fails(tmp_path: Path) -> None:
    """Test that AGENTS.md differing from CLAUDE.md causes AGENTS_DESYNC error."""
    # Create CLAUDE.md
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_SKILLS_END -->
        """))

    # Create AGENTS.md with different content
    (tmp_path / "AGENTS.md").write_text(dedent("""\
        # AGENTS.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |
        | extra-skill | This is extra | [link](link) |

        <!-- AVAILABLE_SKILLS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should fail with AGENTS_DESYNC error
    assert result.returncode == 1
    assert "AGENTS_DESYNC" in result.stdout or "desync" in result.stdout.lower() or "differ" in result.stdout.lower()


def test_exit_code_clean(tmp_path: Path) -> None:
    """Test that clean validation returns exit code 0."""
    # Create minimal valid setup
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_SKILLS_END -->

        ## Available Agents

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should return 0
    assert result.returncode == 0


def test_exit_code_issues(tmp_path: Path) -> None:
    """Test that issues found returns exit code 1."""
    # Create CLAUDE.md with missing markers
    (tmp_path / "CLAUDE.md").write_text("# CLAUDE.md\n\nNo markers here.")

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should return 1
    assert result.returncode == 1


def test_root_skills_unlisted_fails(tmp_path: Path) -> None:
    """Test that skills in root skills/ directory trigger SKILL_UNLISTED when not listed."""
    # Create skill in root skills/ directory (not .claude/skills/)
    skill_dir = tmp_path / "skills/root-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: root-skill
        description: A skill installed via npx skills add
        ---

        # Root Skill

        This should trigger SKILL_UNLISTED because it is not in the table.
        """))

    # Create CLAUDE.md without this skill
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_SKILLS_END -->

        ## Available Agents

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should fail with SKILL_UNLISTED error
    assert result.returncode == 1
    assert "SKILL_UNLISTED" in result.stdout
    assert "root-skill" in result.stdout


def test_root_skills_unlisted_frontmatter_ignored(tmp_path: Path) -> None:
    """Test that root skills/ skills with unlisted: true are ignored."""
    # Create skill in root skills/ with unlisted: true
    skill_dir = tmp_path / "skills/hidden-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: hidden-skill
        description: A hidden distributed skill
        unlisted: true
        ---

        # Hidden Skill

        This should NOT trigger SKILL_UNLISTED.
        """))

    # Create CLAUDE.md without this skill
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_SKILLS_END -->

        ## Available Agents

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should pass because unlisted skills are ignored
    assert result.returncode == 0


def test_both_skill_dirs_valid_passes(tmp_path: Path) -> None:
    """Test that skills in both .claude/skills/ and skills/ pass when all listed."""
    # Create skill in .claude/skills/
    claude_skill_dir = tmp_path / ".claude/skills/claude-skill"
    claude_skill_dir.mkdir(parents=True)
    (claude_skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: claude-skill
        description: A skill in .claude/skills
        ---

        # Claude Skill
        """))

    # Create skill in root skills/
    root_skill_dir = tmp_path / "skills/root-skill"
    root_skill_dir.mkdir(parents=True)
    (root_skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: root-skill
        description: A skill in root skills/
        ---

        # Root Skill
        """))

    # Create valid agent
    agent_file = tmp_path / ".claude/agents/test-agent.md"
    agent_file.parent.mkdir(parents=True, exist_ok=True)
    agent_file.write_text(dedent("""\
        ---
        name: test-agent
        description: A test agent
        ---

        # Test Agent
        """))

    # Create CLAUDE.md listing both skills and the agent
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |
        | claude-skill | A skill in .claude/skills | [.claude/skills/claude-skill/SKILL.md](.claude/skills/claude-skill/SKILL.md) |
        | root-skill | A skill in root skills/ | [skills/root-skill/SKILL.md](skills/root-skill/SKILL.md) |

        <!-- AVAILABLE_SKILLS_END -->

        ## Available Agents

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |
        | test-agent | A test agent | [.claude/agents/test-agent.md](.claude/agents/test-agent.md) |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should pass with exit code 0
    assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}. Output: {result.stdout}\nError: {result.stderr}"


def test_unlisted_agent_fails(tmp_path: Path) -> None:
    """Test that agents not listed in the table cause AGENT_UNLISTED error."""
    # Create agent that's not listed in CLAUDE.md
    agent_dir = tmp_path / ".claude/agents"
    agent_dir.mkdir(parents=True)
    (agent_dir / "orphan-agent.md").write_text(dedent("""\
        ---
        name: orphan-agent
        description: This agent is not listed in the table
        ---

        # Orphan Agent

        This should trigger AGENT_UNLISTED.
        """))

    # Create CLAUDE.md without this agent
    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_SKILLS_END -->

        ## Available Agents

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    # Should fail with AGENT_UNLISTED error
    assert result.returncode == 1
    assert "AGENT_UNLISTED" in result.stdout


# =============================================================================
# FILE_TOO_LONG tests
# =============================================================================


def test_file_too_long_warns(tmp_path: Path) -> None:
    """Test that CLAUDE.md with 201+ lines triggers FILE_TOO_LONG warning."""
    lines = ["# CLAUDE.md\n"] + [f"Line {i}\n" for i in range(200)]
    # Add markers so we don't get MARKER_MISSING errors
    lines.append("<!-- AVAILABLE_SKILLS_START -->\n")
    lines.append("| Name | Description | Link |\n")
    lines.append("| :--- | :---------- | :--- |\n")
    lines.append("<!-- AVAILABLE_SKILLS_END -->\n")
    lines.append("<!-- AVAILABLE_AGENTS_START -->\n")
    lines.append("| Name | Description | Link |\n")
    lines.append("| :--- | :---------- | :--- |\n")
    lines.append("<!-- AVAILABLE_AGENTS_END -->\n")
    (tmp_path / "CLAUDE.md").write_text("".join(lines))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "FILE_TOO_LONG" in result.stdout


def test_file_under_limit_passes(tmp_path: Path) -> None:
    """Test that CLAUDE.md with exactly 200 lines does not trigger FILE_TOO_LONG."""
    # Build a CLAUDE.md that is exactly 200 lines with valid markers
    header = dedent("""\
        # CLAUDE.md

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_SKILLS_END -->

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """)
    header_lines = header.splitlines(keepends=True)
    # Pad to exactly 200 lines
    padding_count = 200 - len(header_lines)
    padding = [f"Line {i}\n" for i in range(padding_count)]
    (tmp_path / "CLAUDE.md").write_text("".join(header_lines + padding))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "FILE_TOO_LONG" not in result.stdout


# =============================================================================
# IMPORT_BROKEN tests
# =============================================================================


def test_import_broken_fails(tmp_path: Path) -> None:
    """Test that @nonexistent/path in CLAUDE.md triggers IMPORT_BROKEN error."""
    claude_text = _minimal_claude_md() + "\nSee @nonexistent/path.md for details.\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "IMPORT_BROKEN" in result.stdout


def test_import_valid_passes(tmp_path: Path) -> None:
    """Test that @existing/path in CLAUDE.md passes when file exists."""
    (tmp_path / "existing").mkdir()
    (tmp_path / "existing/file.md").write_text("# Existing file\n")
    claude_text = _minimal_claude_md() + "\nSee @existing/file.md for details.\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "IMPORT_BROKEN" not in result.stdout


def test_import_in_code_block_ignored(tmp_path: Path) -> None:
    """Test that @path inside a fenced code block is NOT flagged."""
    claude_text = _minimal_claude_md() + dedent("""\

        ```
        @nonexistent/path.md
        ```
        """)
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "IMPORT_BROKEN" not in result.stdout


def test_import_in_code_block_with_backticks_ignored(tmp_path: Path) -> None:
    """Test that @path inside a code block containing backticks is NOT flagged."""
    claude_text = _minimal_claude_md() + dedent("""\

        ```yaml
        # See @nonexistent/file.md for `details`
        ```
        """)
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "IMPORT_BROKEN" not in result.stdout


# =============================================================================
# IMPORT_SENSITIVE tests
# =============================================================================


def test_import_sensitive_warns(tmp_path: Path) -> None:
    """Test that @.env or @secrets.key triggers IMPORT_SENSITIVE warning."""
    (tmp_path / ".env").write_text("SECRET=value\n")
    claude_text = _minimal_claude_md() + "\nConfig at @.env\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "IMPORT_SENSITIVE" in result.stdout


def test_import_non_sensitive_passes(tmp_path: Path) -> None:
    """Test that @AGENTS.md (non-sensitive file) does not trigger IMPORT_SENSITIVE."""
    (tmp_path / "AGENTS.md").write_text("# AGENTS.md\n")
    claude_text = _minimal_claude_md() + "\nSee @AGENTS.md\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "IMPORT_SENSITIVE" not in result.stdout


# =============================================================================
# DESCRIPTION_MISMATCH tests
# =============================================================================


def test_description_mismatch_warns(tmp_path: Path) -> None:
    """Test that table description differing from frontmatter triggers DESCRIPTION_MISMATCH."""
    skill_dir = tmp_path / ".claude/skills/my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: my-skill
        description: The real description from frontmatter
        ---

        # My Skill
        """))

    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |
        | my-skill | Wrong description in table | [.claude/skills/my-skill/SKILL.md](.claude/skills/my-skill/SKILL.md) |

        <!-- AVAILABLE_SKILLS_END -->

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "DESCRIPTION_MISMATCH" in result.stdout


def test_description_match_passes(tmp_path: Path) -> None:
    """Test that matching table description and frontmatter passes."""
    skill_dir = tmp_path / ".claude/skills/my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: my-skill
        description: Correct description
        ---

        # My Skill
        """))

    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |
        | my-skill | Correct description | [.claude/skills/my-skill/SKILL.md](.claude/skills/my-skill/SKILL.md) |

        <!-- AVAILABLE_SKILLS_END -->

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "DESCRIPTION_MISMATCH" not in result.stdout


# =============================================================================
# NAME_MISMATCH tests
# =============================================================================


def test_name_mismatch_fails(tmp_path: Path) -> None:
    """Test that table name differing from frontmatter name triggers NAME_MISMATCH."""
    skill_dir = tmp_path / ".claude/skills/my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: actual-name
        description: Some description
        ---

        # My Skill
        """))

    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |
        | wrong-name | Some description | [.claude/skills/my-skill/SKILL.md](.claude/skills/my-skill/SKILL.md) |

        <!-- AVAILABLE_SKILLS_END -->

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "NAME_MISMATCH" in result.stdout


def test_name_match_passes(tmp_path: Path) -> None:
    """Test that matching table name and frontmatter name passes."""
    skill_dir = tmp_path / ".claude/skills/my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: my-skill
        description: Some description
        ---

        # My Skill
        """))

    (tmp_path / "CLAUDE.md").write_text(dedent("""\
        # CLAUDE.md

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |
        | my-skill | Some description | [.claude/skills/my-skill/SKILL.md](.claude/skills/my-skill/SKILL.md) |

        <!-- AVAILABLE_SKILLS_END -->

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "NAME_MISMATCH" not in result.stdout


# =============================================================================
# AGENTS_NO_IMPORT tests
# =============================================================================


def test_agents_no_import_warns(tmp_path: Path) -> None:
    """Test that AGENTS.md exists without @AGENTS.md import and bodies differ triggers warning."""
    (tmp_path / "CLAUDE.md").write_text(_minimal_claude_md())
    (tmp_path / "AGENTS.md").write_text(dedent("""\
        # AGENTS.md

        Different body content here.
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "AGENTS_NO_IMPORT" in result.stdout


def test_agents_import_present_passes(tmp_path: Path) -> None:
    """Test that CLAUDE.md with @AGENTS.md reference does not trigger AGENTS_NO_IMPORT."""
    claude_text = _minimal_claude_md() + "\nImport: @AGENTS.md\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)
    (tmp_path / "AGENTS.md").write_text(dedent("""\
        # AGENTS.md

        Different body content.
        """))

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "AGENTS_NO_IMPORT" not in result.stdout


def test_agents_synced_no_warn(tmp_path: Path) -> None:
    """Test that synced bodies produce no AGENTS_NO_IMPORT even without @import."""
    body = dedent("""\

        ## Available Skills

        <!-- AVAILABLE_SKILLS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_SKILLS_END -->

        ## Available Agents

        <!-- AVAILABLE_AGENTS_START -->

        | Name | Description | Link |
        | :--- | :---------- | :--- |

        <!-- AVAILABLE_AGENTS_END -->
        """)
    (tmp_path / "CLAUDE.md").write_text("# CLAUDE.md" + body)
    (tmp_path / "AGENTS.md").write_text("# AGENTS.md" + body)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "AGENTS_NO_IMPORT" not in result.stdout


# =============================================================================
# RULES_INVALID_PATHS tests
# =============================================================================


def test_rules_invalid_glob_warns(tmp_path: Path) -> None:
    """Test that a rule file with invalid glob pattern triggers RULES_INVALID_PATHS."""
    rules_dir = tmp_path / ".claude/rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "test-rule.md").write_text(dedent("""\
        ---
        globs: "[unclosed-bracket"
        ---

        # Test Rule
        """))

    (tmp_path / "CLAUDE.md").write_text(_minimal_claude_md())

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "RULES_INVALID_PATHS" in result.stdout


def test_rules_valid_glob_passes(tmp_path: Path) -> None:
    """Test that a rule file with valid glob pattern passes."""
    rules_dir = tmp_path / ".claude/rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "test-rule.md").write_text(dedent("""\
        ---
        globs: "*.py"
        ---

        # Test Rule
        """))

    (tmp_path / "CLAUDE.md").write_text(_minimal_claude_md())

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "RULES_INVALID_PATHS" not in result.stdout


# =============================================================================
# RULES_BROKEN_LINK tests
# =============================================================================


def test_rules_broken_link_fails(tmp_path: Path) -> None:
    """Test that a rule file with broken markdown link triggers RULES_BROKEN_LINK."""
    rules_dir = tmp_path / ".claude/rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "test-rule.md").write_text(dedent("""\
        ---
        globs: "*.py"
        ---

        # Test Rule

        See [reference](docs/nonexistent.md) for details.
        """))

    (tmp_path / "CLAUDE.md").write_text(_minimal_claude_md())

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "RULES_BROKEN_LINK" in result.stdout


def test_rules_valid_link_passes(tmp_path: Path) -> None:
    """Test that a rule file with valid markdown link passes."""
    rules_dir = tmp_path / ".claude/rules"
    rules_dir.mkdir(parents=True)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text("# Guide\n")
    (rules_dir / "test-rule.md").write_text(dedent("""\
        ---
        globs: "*.py"
        ---

        # Test Rule

        See [guide](docs/guide.md) for details.
        """))

    (tmp_path / "CLAUDE.md").write_text(_minimal_claude_md())

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "RULES_BROKEN_LINK" not in result.stdout


# =============================================================================
# BODY_SENSITIVE tests
# =============================================================================


def test_body_sensitive_api_key_warns(tmp_path: Path) -> None:
    """Test that API key assignment in CLAUDE.md body triggers BODY_SENSITIVE."""
    claude_text = _minimal_claude_md() + "\nSet api_key = sk-abc123xyz in your config.\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" in result.stdout
    assert result.returncode == 0  # WARN severity, not ERROR


def test_body_sensitive_password_in_url_warns(tmp_path: Path) -> None:
    """Test that database connection string with credentials triggers BODY_SENSITIVE."""
    claude_text = _minimal_claude_md() + "\nConnect via postgres://admin:p4ssw0rd@localhost/db\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" in result.stdout


def test_body_sensitive_clean_passes(tmp_path: Path) -> None:
    """Test that clean CLAUDE.md without secrets produces no BODY_SENSITIVE."""
    claude_text = _minimal_claude_md() + "\nUse environment variables for secrets. Never hardcode passwords or tokens in documentation.\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" not in result.stdout


def test_body_sensitive_in_code_block_ignored(tmp_path: Path) -> None:
    """Test that secrets inside fenced code blocks are NOT flagged."""
    claude_text = _minimal_claude_md() + dedent("""\

        ```
        api_key = sk-abc123xyz
        ```
        """)
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" not in result.stdout


def test_body_sensitive_bearer_token_warns(tmp_path: Path) -> None:
    """Test that Bearer token with 20+ char value triggers BODY_SENSITIVE."""
    claude_text = _minimal_claude_md() + "\nAuthorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" in result.stdout


def test_body_sensitive_aws_key_warns(tmp_path: Path) -> None:
    """Test that AWS access key pattern triggers BODY_SENSITIVE."""
    claude_text = _minimal_claude_md() + "\nAWS key: AKIAIOSFODNN7EXAMPLE\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" in result.stdout


# =============================================================================
# Edge case tests
# =============================================================================


def test_email_not_treated_as_import(tmp_path: Path) -> None:
    """Test that user@example.com in CLAUDE.md is NOT flagged as import."""
    claude_text = _minimal_claude_md() + "\nContact: user@example.com\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "IMPORT_BROKEN" not in result.stdout
    assert "IMPORT_SENSITIVE" not in result.stdout


def test_no_rules_dir_passes(tmp_path: Path) -> None:
    """Test that no .claude/rules/ directory produces no RULES findings."""
    (tmp_path / "CLAUDE.md").write_text(_minimal_claude_md())

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "RULES_INVALID_PATHS" not in result.stdout
    assert "RULES_BROKEN_LINK" not in result.stdout


# =============================================================================
# Inline code span tests (strip_code_blocks fix)
# =============================================================================


def test_import_in_inline_code_ignored(tmp_path: Path) -> None:
    """Test that @path inside inline backticks is NOT flagged as IMPORT_BROKEN."""
    claude_text = _minimal_claude_md() + "\nSee `@nonexistent/path.md` for details.\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "IMPORT_BROKEN" not in result.stdout


# =============================================================================
# IMPORT_SENSITIVE directory path tests
# =============================================================================


def test_import_sensitive_directory_warns(tmp_path: Path) -> None:
    """Test that @secrets/config.md triggers IMPORT_SENSITIVE when path contains sensitive dir."""
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "config.md").write_text("# Config\n")
    claude_text = _minimal_claude_md() + "\nSee @secrets/config.md for details.\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "IMPORT_SENSITIVE" in result.stdout



# =============================================================================
# Placeholder detection with underscore-joined tokens
# =============================================================================


def test_body_sensitive_underscore_placeholder_not_flagged(tmp_path: Path) -> None:
    """Test that underscore-joined placeholder values like your_api_key are NOT flagged."""
    claude_text = _minimal_claude_md() + "\nSet api_key = your_api_key in config.\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" not in result.stdout


def test_body_sensitive_changeme_with_digits_not_flagged(tmp_path: Path) -> None:
    """Test that placeholder with trailing digits like changeme123 is NOT flagged."""
    claude_text = _minimal_claude_md() + "\npassword = changeme123\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" not in result.stdout


def test_body_sensitive_replace_this_value_not_flagged(tmp_path: Path) -> None:
    """Test that underscore-joined replace_this_value is NOT flagged."""
    claude_text = _minimal_claude_md() + "\nsecret = replace_this_value\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" not in result.stdout


def test_body_sensitive_sample_token_value_not_flagged(tmp_path: Path) -> None:
    """Test that sample_token_value placeholder is NOT flagged."""
    claude_text = _minimal_claude_md() + "\ntoken = sample_token_value\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" not in result.stdout


def test_body_sensitive_example_between_underscores_not_flagged(tmp_path: Path) -> None:
    """Test that my_example_key placeholder is NOT flagged."""
    claude_text = _minimal_claude_md() + "\napi_key = my_example_key\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" not in result.stdout


def test_body_sensitive_real_secret_still_flagged(tmp_path: Path) -> None:
    """Test that real-looking secrets are still flagged (no regression)."""
    claude_text = _minimal_claude_md() + "\napi_key = sk-abc123xyz in your config.\n"
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" in result.stdout


def test_body_sensitive_in_extended_tilde_fence_ignored(tmp_path: Path) -> None:
    """Test that secrets inside ~~~~ (4+ tilde) fences are NOT flagged."""
    claude_text = _minimal_claude_md() + dedent("""
        ~~~~
        api_key = sk-abc123xyz
        ~~~~
        """)
    (tmp_path / "CLAUDE.md").write_text(claude_text)

    script = Path(__file__).parent.parent / "scripts/audit_docs.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert "BODY_SENSITIVE" not in result.stdout
