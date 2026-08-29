# SKILL.md Template

Use this template when creating new Claude Code skills.

---

## Template

```markdown
---
name: skill-name-in-hyphen-case
description: [What it does]. [Pattern type - workflow/task/reference/capabilities]. Use when [trigger keywords and scenarios].
allowed-tools: Task, Read, Write, Edit, Glob, Grep, Bash
---

# Skill Name

## Overview

[1-2 sentences describing the skill]

**Purpose**: [One-line purpose statement]

**Pattern**: [Workflow-based / Task-based / Reference / Capabilities-based]

**Key Principles** (validated by [source]):
1. **[Principle Name]** - [Brief description]
2. **[Principle Name]** - [Brief description]
3. **[Principle Name]** - [Brief description]
[Add 3-6 principles]

**Quality Targets**:
- [Metric 1]: [Target]
- [Metric 2]: [Target]
[Add relevant metrics]

---

## When to Use

Use [skill-name] when:

- [Use case 1]
- [Use case 2]
- [Use case 3]
[Add relevant use cases]

**When NOT to Use**:
- [Non-use case 1]
- [Non-use case 2]
[Add scenarios where skill shouldn't be used]

---

## Prerequisites

### Required
- [Requirement 1]
- [Requirement 2]

### Recommended
- [Recommendation 1]
- [Recommendation 2]

### Understanding
- [Background knowledge 1]
- [Background knowledge 2]

---

## [Operations / Workflow Steps]

### [Operation 1 / Step 1]: [Name]

**Time**: [Estimated time]
**Automation**: [Percentage]
**Purpose**: [What this achieves]

**Process**:

1. **[Sub-step name]**:
```[language]
[Code example]
```

2. **[Sub-step name]**:
```[language]
[Code example]
```

[Add more sub-steps as needed]

---

### [Operation 2 / Step 2]: [Name]

[Repeat structure for each operation/step]

---

## [Additional Sections]

Add domain-specific sections as needed:
- Configuration
- Integration patterns
- Decision trees
- Troubleshooting
- Best practices

---

## Multi-AI Coordination

### Agent Assignment

| Task | Primary | Verification | Notes |
|------|---------|--------------|-------|
| [Task 1] | [AI] | [AI] | [Notes] |
| [Task 2] | [AI] | [AI] | [Notes] |

### Coordination Commands

**[AI Name]**:
```bash
[Command example]
```

---

## Related Skills

- **[skill-name]**: [Relationship description]
- **[skill-name]**: [Relationship description]

---

## References

- `references/[file].md` - [Description]
- `references/[file].md` - [Description]
```

---

## Template Guidelines

### YAML Frontmatter

**name**: Use hyphen-case, be descriptive
```yaml
name: multi-ai-code-review  # Good
name: review                 # Too vague
```

**description**: Include:
- What it does (first sentence)
- Pattern type (workflow/task/reference/capabilities)
- Trigger keywords ("Use when...")

```yaml
description: Multi-perspective code review using AI ensemble. Task-based with 5 dimensions. Use when reviewing PRs, auditing code, or establishing review workflows.
```

### Overview Section

Keep it scannable:
- 1-2 sentence description
- One-line purpose
- Pattern type
- 3-6 key principles
- Measurable quality targets

### When to Use

Be specific:
- List 3-6 concrete use cases
- List 2-4 non-use cases
- Help users quickly determine relevance

### Prerequisites

Three categories:
- **Required**: Must have to use skill
- **Recommended**: Better experience with these
- **Understanding**: Background knowledge needed

### Operations/Workflows

For each operation/step:
- Estimated time
- Automation percentage
- Clear purpose
- Step-by-step process
- Code examples

### Code Examples

Every skill needs:
- [ ] Quick start example (first operation)
- [ ] 3+ common use case examples
- [ ] 1+ advanced example
- [ ] Error handling example
- [ ] Integration example (if applicable)

### Progressive Disclosure

- SKILL.md: <1500 lines, overview and quick reference
- references/: Detailed guides, loaded on demand
- scripts/: Automation tools, loaded when needed
