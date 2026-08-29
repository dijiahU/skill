# Multi-AI Research & Analysis

Comprehensive research and analysis using Claude (subagents), Gemini CLI, and Codex CLI with multi-perspective verification and iterative refinement.

## Quick Start

```bash
# Automated analysis
bash scripts/analyze.sh "Security analysis of authentication system"

# Or via Claude Code
# Ask: "Use multi-ai-research for [objective]"
```

## What It Does

Produces analysis **more thorough than any single AI** through:

1. **Specialized Research** - Claude, Gemini, Codex each research independently
2. **Cross-Validation** - All findings verified across sources
3. **Iterative Refinement** - Automatic improvement until quality ≥95/100
4. **100% Citations** - Every claim traced to source (file:line or URL)
5. **Production-Ready** - Comprehensive, verified, actionable

## The 5-Phase Pipeline

```
1. PLANNING        → Create analysis strategy
2. RESEARCH        → Claude + Gemini + Codex in parallel
3. ANALYSIS        → Deep pattern recognition
4. SYNTHESIS       → Multi-source integration + verification
5. ITERATION       → Gap filling until quality ≥95
6. FINAL REPORT    → Comprehensive deliverable
```

**Time**: 45-90 minutes for complete analysis

## Analysis Types

| Type | Use For | Output |
|------|---------|--------|
| **Security** | OWASP, vulnerabilities, auth | Critical/High/Med issues with fixes |
| **Architecture** | System design, scalability | Component maps, integration analysis |
| **Code Quality** | Patterns, complexity, debt | Quality score, refactoring priorities |
| **Performance** | Bottlenecks, optimization | Hotspots, specific improvements |
| **Research** | Best practices, patterns | Multi-source synthesis, recommendations |

## Quality Guarantees

- ✓ **100% coverage** - All objectives addressed, zero gaps
- ✓ **100% citations** - Every claim sourced
- ✓ **Multi-perspective** - 3 AI systems cross-validated
- ✓ **≥95/100 quality** - Verified through 3-pass system
- ✓ **Actionable** - Specific recommendations
- ✓ **Resumable** - External memory, multi-session support

## Prerequisites

**Required**:
- Claude Code (with Task tool)

**Recommended**:
```bash
# Gemini CLI
npm install -g @google/gemini-cli
gemini  # Authenticate via OAuth

# Codex CLI
npm install -g @openai/codex
codex login  # Authenticate with ChatGPT Plus/Pro
```

**Note**: Works with Claude-only fallback if Gemini/Codex unavailable.

## File Structure

```
.claude/skills/multi-ai-research/
├── SKILL.md                    # Main documentation
├── README.md                   # This file
├── scripts/
│   └── analyze.sh             # Main orchestration script
├── subagents/
│   ├── research-agent.md      # Claude research subagent
│   ├── analysis-agent.md      # Claude analysis subagent
│   └── verification-agent.md  # Claude verification subagent
├── templates/
│   ├── ANALYSIS_PLAN_TEMPLATE.md
│   ├── VERIFICATION_CHECKLIST.md
│   └── SYNTHESIS_TEMPLATE.md
├── references/
│   └── [Reference documentation]
└── examples/
    └── [Example workflows]
```

## Output Structure

Analysis creates `.analysis/` with:

```
.analysis/
├── ANALYSIS_PLAN.md           # Strategy
├── research/
│   ├── claude-docs.md         # Claude findings
│   ├── gemini-web.md          # Gemini findings
│   └── codex-github.md        # Codex findings
├── analysis/
│   └── code-patterns.md       # Pattern analysis
├── verification/
│   └── cross-check.md         # Verification results
├── iterations/
│   ├── ITERATION_1.md         # First pass
│   └── ITERATION_2.md         # Gap fills (if needed)
└── ANALYSIS_FINAL.md          # Complete report
```

## Examples

### Security Analysis

```
Objective: "Security audit of authentication"

Output:
- 8 issues (3 critical, 5 high) with specific fixes
- OWASP Top 10 coverage
- Code examples with file:line
- Priority implementation plan

Quality: 97/100 ✓
```

### Architecture Analysis

```
Objective: "Analyze microservices architecture"

Output:
- Component map (7 services, dependencies)
- Integration analysis (12 patterns)
- Scalability assessment
- Modernization roadmap

Quality: 96/100 ✓
```

## How It's Different

| Traditional | Multi-AI Research |
|-------------|-------------------|
| Single AI perspective | 3 AI systems, cross-validated |
| No verification | 3-pass verification system |
| One-shot analysis | Iterative until quality ≥95 |
| Manual citation | 100% automatic citations |
| Context limited | External memory, unlimited scope |

## Best Practices

1. **Be Specific**: "Security analysis of auth module for OWASP compliance" vs "Analyze code"
2. **Trust Verification**: Quality <95 triggers automatic iteration
3. **Check Progress**: Review `.analysis/` during execution
4. **Use Citations**: Every claim has file:line or URL for validation
5. **Multi-Session**: Large projects can span multiple sessions

## Troubleshooting

**Low quality score?**
→ Automatic iteration 2 fills gaps

**Missing citations?**
→ Verification catches and iteration adds them

**Gemini/Codex unavailable?**
→ Fallback to Claude-only with warning

**Conflicting info?**
→ Synthesis investigates and resolves with documentation

## Related Skills

- `anthropic-expert` - Anthropic product expertise
- `codex-cli` - Codex integration
- `gemini-cli` - Gemini integration
- `tri-ai-collaboration` - General tri-AI workflows

## Documentation

- **SKILL.md** - Complete documentation with examples
- **subagents/** - Subagent specifications
- **templates/** - Analysis templates
- **references/** - Detailed guides

---

**Delivers production-ready analysis through multi-AI collaboration, rigorous verification, and iterative refinement.**
