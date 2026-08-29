# Multi-AI Planning

Production-ready planning skill for creating agent-executable plans with verification-first approach, hierarchical decomposition, and quality gates.

## Quick Start

**Create a plan**:
```
Use multi-ai-planning to create a plan for [objective]
```

Follow the 6-step workflow in SKILL.md.

## What It Does

Creates comprehensive plans that:
- ✅ Are agent-executable (clear steps, success criteria)
- ✅ Use hierarchical decomposition (8-15 tasks per level)
- ✅ Map dependencies explicitly (parallel opportunities identified)
- ✅ Include verification for every task
- ✅ Score ≥90/100 on quality rubric
- ✅ Support safe checkpoints and rollback

## The 6-Step Workflow

```
1. OBJECTIVE ANALYSIS    → Research, approach, scope (30-120m)
2. DECOMPOSITION         → Break into hierarchical tasks (45-90m)
3. DEPENDENCY MAPPING    → Map deps, identify parallel (30-45m)
4. VERIFICATION PLANNING → Success criteria for all tasks (45-75m)
5. QUALITY VERIFICATION  → Score 0-100, approve if ≥90 (30-45m)
6. FINALIZATION          → Generate plan.json + PLAN.md (20-30m)
```

**Total**: 3.5-6.5 hours → Production-ready plan

## Outputs

**plan.json** - Machine-readable, schema-validated
**PLAN.md** - Human-readable with all details
**COORDINATION.md** - Agent execution guide
**VERIFICATION.md** - Quality report (score ≥90)

## Key Features

### Hierarchical Decomposition
```
Objective
  └→ Large Tasks (8-15)
       └→ Medium Tasks (3-8 each)
            └→ Small/Atomic Tasks (3-8 each)
```

### Verification-First
Define HOW TO VERIFY before defining WHAT TO DO:
- Success criteria (SMART)
- Verification method (automated preferred)
- Quality gates at milestones

### Quality Scoring (0-100)
- Comprehensiveness (/20)
- Feasibility (/20)
- Clarity (/20)
- Executability (/20)
- Integration (/20)

**Threshold**: ≥90 for execution approval

### Safe Checkpoints
Git tags + patch bundles (NOT git reset):
```bash
git commit -m "Checkpoint: foundation"
git tag -a cp-001 -m "metadata"
git format-patch -1 HEAD -o checkpoints/
```

## Prerequisites

**Required**:
- Clear objective
- 1-3 hours for planning

**Optional** (enhanced planning):
- multi-ai-research skill (tri-AI research)
- Gemini CLI (web research)
- Codex CLI (GitHub patterns)

## File Structure

```
.claude/skills/multi-ai-planning/
├── SKILL.md              # Complete workflow documentation
├── README.md             # This file
├── schemas/
│   ├── plan.schema.json  # Plan validation schema
│   ├── task.schema.json  # Task validation schema
│   └── checkpoint.schema.json
├── templates/
│   ├── PLAN_TEMPLATE.md
│   └── VERIFICATION_TEMPLATE.md
├── scripts/
│   ├── validate-schema.sh
│   └── verify-plan.sh
├── references/
│   ├── task-tool-coordination.md (Critical - how to use Task tool)
│   ├── planning-patterns.md
│   └── [more references]
└── examples/
    └── [example plans]
```

## Example Usage

```
"Create a plan for implementing user authentication with OAuth"

→ Follows 6-step workflow
→ Researches OAuth patterns (optional: multi-ai-research)
→ Breaks down into 8 large tasks
→ Maps dependencies
→ Defines verification for each task
→ Quality scores: 94/100 ✅
→ Generates plan.json + PLAN.md

Result: Production-ready plan ready for agent execution
```

## Quality Guarantees

Plans created by this skill:
- ✅ Score ≥90/100 (verified quality)
- ✅ Schema-validated (no structural errors)
- ✅ All tasks have success criteria
- ✅ All dependencies mapped
- ✅ Parallel execution optimized
- ✅ Checkpoints for safe resumption

## Best Practices

1. **Research first** for unfamiliar domains
2. **Decompose to atomic** tasks
3. **Map all dependencies** explicitly
4. **Verification before implementation**
5. **Quality threshold** ≥90
6. **Use safe checkpoints**

## Troubleshooting

**Low quality score (<90)?**
→ Review gap analysis in VERIFICATION.md
→ Apply recommended fixes
→ Re-verify

**Tasks too big?**
→ Decompose more (target: 8-15 per level)

**Circular dependencies?**
→ Use visualize-deps.sh to find cycles
→ Restructure task dependencies

## Related Skills

- `multi-ai-research` - Tri-AI research for planning
- `development-workflow` - Complete development process
- `planning-architect` - Skill architecture planning

---

**Validated by**: Claude + Gemini + Codex
**Feasibility**: 85% (production-ready architecture)
**Timeline**: Implemented following 12-week validated roadmap
