# Audit Code Health Skill

A Claude skill for systematic code auditing that identifies security vulnerabilities, bugs, and code health issues. Creates structured work items for remediation using a flexible cycle-based workflow.

## Installation

Install this skill using the Skills CLI:

```bash
npx skills add https://github.com/kyzooghost/audit-code-health-skill --skill audit-code-health
```

## Usage

Once installed, use the skill in Claude Code:

```bash
For @folder do /audit-code-health
```

The skill will systematically scan the target directory, identify issues across three priority categories (Security → Bugs → Code Health), and create structured work items for remediation.

## What This Skill Does

This skill performs systematic code audits across three priority categories:

- **Security Issues (CRITICAL)** - Auth/authz errors, injection risks, SSRF, path traversal, secrets, broken crypto, missing validation, dependency vulnerabilities
- **Bugs (HIGH)** - Edge cases, race conditions, error handling gaps, resource leaks, numeric issues, retry/timeout bugs
- **Code Health (MEDIUM)** - Complexity issues, test coverage gaps, duplication, dead code, documentation issues, naming problems

The audit follows a structured workflow:
1. **SCAN** - Inspect target directory for issues
2. **FINDINGS** - Document issues in a prioritized table
3. **VERIFY** - Validate findings before filing
4. **FILE** - Create work items (Beads epics/issues or Markdown task lists)
5. **TRIAGE** - Assign priorities and group related issues

Audits can run from quick scans (1-2 cycles) to deep audits (6-10 cycles) depending on scope.

## Repository Structure

```
audit-code-health-skill/
├── README.md                    # This file
├── metadata.json               # Repository metadata
├── LICENSE                     # MIT License
└── skills/
    └── audit-code-health/
        ├── SKILL.md            # Skill documentation and implementation
        ├── AGENTS.md           # Comprehensive agent reference guide
        ├── metadata.json       # Skill metadata
        └── reference/
            ├── security-issues.md    # Security checklist
            ├── bugs-checklist.md     # Bugs checklist
            ├── code-health.md        # Code health checklist
            ├── beads-format.md       # Beads work item format guide
            └── examples.md           # Audit workflow examples
```

## Development

### Testing Locally

1. Clone this repository
2. Make your changes to `skills/audit-code-health/SKILL.md` or other files
3. Test locally:
   ```bash
   npx skills add .
   ```
4. Verify the skill appears in Claude Code:
   ```bash
   /skills
   ```

### Skill Structure

The skill is located in `skills/audit-code-health/` and includes:

- **SKILL.md** - Main skill documentation with workflow, principles, and quick reference
- **AGENTS.md** - Comprehensive reference guide for agents/LLMs (700+ lines)
- **reference/** - Detailed checklists and format guides:
  - Security issues checklist (CRITICAL)
  - Bugs checklist (HIGH)
  - Code health checklist (MEDIUM)
  - Beads format guide for work items
  - Complete audit examples

## Verification

After installation, verify the skill works correctly:

```bash
# In Claude Code, list all skills
/skills

# Use the skill on a directory
For @your-directory do /audit-code-health

# Check skill metadata
npx skills list
```

## Core Principles

The skill follows these principles:

1. **Audit only, no fixes** - Discover and document issues, never modify code
2. **Track everything** - All findings become work items
3. **Scoped analysis** - Stay within target directory unless context requires external references
4. **Prioritize by impact** - Security → Bugs → Code Health

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally using `npx skills add .`
5. Submit a pull request

## License

MIT

## Resources

- [Agent Skills Specification](https://agentskills.io/specification)
- [Skills Repository](https://github.com/vercel-labs/skills)
- [Claude Code Documentation](https://claude.ai/code)
- [OWASP Top Ten](https://owasp.org/www-project-top-ten/)
- [CWE Common Weakness Enumeration](https://cwe.mitre.org/)

## Support

For issues or questions:
- Open an issue in this repository
- Refer to the [Skills CLI documentation](https://github.com/vercel-labs/skills)
- Check the [Agent Skills specification](https://agentskills.io/specification)
