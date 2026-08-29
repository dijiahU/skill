# Analysis Plan: [OBJECTIVE]

**Created**: [TIMESTAMP]
**Status**: Planning

---

## 1. Objective and Scope

### Primary Objective
[Clearly state what needs to be analyzed]

### Scope
**Include**:
- [What to analyze]
- [What areas to cover]

**Exclude**:
- [What to skip]
- [Boundaries]

### Analysis Type
[ ] Code Quality Analysis
[ ] Security Analysis
[ ] Architecture Analysis
[ ] Performance Analysis
[ ] Dependency Analysis
[ ] Research Synthesis
[ ] Other: [specify]

---

## 2. File Reading Strategy

### Phase 1: Metadata Discovery (Glob)
```bash
# Map project structure
glob "[pattern]"
glob "[pattern]"
glob "[pattern]"
```

**Expected**: [What we expect to find]

### Phase 2: Pattern Recognition (Grep)
```bash
# Search for specific patterns
grep "[pattern]" --glob "[glob pattern]"
grep "[pattern]" --glob "[glob pattern]"
grep "[pattern]" --glob "[glob pattern]"
```

**Expected**: [What patterns we're looking for]

### Phase 3: Targeted Reading (Read)
**Files to read** (based on Phase 2 results):
- [file path] - Reason: [why]
- [file path] - Reason: [why]
- [file path] - Reason: [why]

---

## 3. AI System Assignments

### Claude Research Subagent
**Tasks**:
- [ ] Analyze official documentation
- [ ] Examine codebase with progressive disclosure
- [ ] Identify architecture and patterns
- [ ] Map dependencies

**Tools**: read, grep, glob, web_search
**Output**: `.analysis/research/claude-docs.md`
**Time Estimate**: [X] minutes

### Gemini CLI (Web Research)
**Tasks**:
- [ ] Research latest best practices (2024-2025)
- [ ] Find community patterns and trends
- [ ] Identify popular libraries/frameworks
- [ ] Discover common pitfalls

**Output Format**: JSON
**Output File**: `.analysis/research/gemini-web.md`
**Time Estimate**: [X] minutes

### Codex CLI (Code Research)
**Tasks**:
- [ ] Search GitHub for implementation patterns
- [ ] Collect code examples from top repos
- [ ] Analyze API design patterns
- [ ] Review testing strategies

**Model**: gpt-5.1-codex (or o3 for deep reasoning)
**Output Format**: JSON
**Output File**: `.analysis/research/codex-github.md`
**Time Estimate**: [X] minutes

### Claude Analysis Agent
**Tasks**:
- [ ] Synthesize findings from all sources
- [ ] Perform deep pattern analysis
- [ ] Map architecture
- [ ] Generate insights

**Tools**: read, grep, glob
**Mode**: Extended thinking for complex synthesis
**Output**: `.analysis/analysis/code-patterns.md`
**Time Estimate**: [X] minutes

### Claude Verification Agent
**Tasks**:
- [ ] Cross-validate all findings
- [ ] Check completeness
- [ ] Verify citations
- [ ] Calculate quality score

**Output**: `.analysis/verification/cross-check.md`
**Time Estimate**: [X] minutes

---

## 4. Research Questions

### Primary Questions
1. [Question 1]
2. [Question 2]
3. [Question 3]

### Secondary Questions
1. [Question 4]
2. [Question 5]

---

## 5. Success Criteria

### Completeness Requirements
- [ ] All objectives addressed
- [ ] All identified files analyzed
- [ ] All research questions answered
- [ ] No critical gaps

### Quality Requirements
- [ ] 100% citation coverage
- [ ] Quality score ≥95/100
- [ ] All sources cross-validated
- [ ] No unresolved contradictions

### Deliverables
- [ ] Claude research findings
- [ ] Gemini web research
- [ ] Codex code research
- [ ] Pattern analysis
- [ ] Synthesis report
- [ ] Verification report
- [ ] Final comprehensive report

---

## 6. Verification Checklist

### Phase 1: Research
- [ ] Claude subagent completed
- [ ] Gemini CLI research completed
- [ ] Codex CLI research completed
- [ ] All outputs saved to external files

### Phase 2: Analysis
- [ ] Pattern analysis completed
- [ ] Architecture mapped
- [ ] Metrics calculated
- [ ] Insights generated

### Phase 3: Synthesis
- [ ] All sources read and integrated
- [ ] Themes identified
- [ ] Conflicts resolved
- [ ] Comprehensive synthesis created

### Phase 4: Verification
- [ ] Completeness verified (≥95%)
- [ ] Citations verified (100%)
- [ ] Quality score calculated (≥95)
- [ ] Gaps identified and documented

### Phase 5: Iteration (if needed)
- [ ] Gaps filled
- [ ] Quality improved
- [ ] Re-verification passed
- [ ] Final report created

---

## 7. External Memory Structure

```
.analysis/
├── ANALYSIS_PLAN.md (this file)
├── research/
│   ├── claude-docs.md
│   ├── gemini-web.md
│   ├── codex-github.md
│   └── gap-fills/ (iteration 2)
├── analysis/
│   ├── code-patterns.md
│   ├── architecture-map.md
│   └── metrics.md
├── verification/
│   ├── cross-check.md
│   ├── completeness.md
│   └── gaps.md
├── iterations/
│   ├── ITERATION_1.md
│   ├── ITERATION_2.md
│   └── ITERATION_3_FINAL.md
└── ANALYSIS_FINAL.md
```

---

## 8. Quality Gates

### Gate 1: Research Completion
**Criteria**: All three AI systems completed research
**Check**: All output files exist and contain findings

### Gate 2: Analysis Quality
**Criteria**: Pattern analysis comprehensive and evidence-based
**Check**: All patterns have file:line citations

### Gate 3: Synthesis Completeness
**Criteria**: All sources integrated, conflicts resolved
**Check**: Synthesis includes all perspectives

### Gate 4: Verification Pass
**Criteria**: Quality score ≥95, no critical gaps
**Check**: Verification report shows PASS status

### Gate 5: Final Quality
**Criteria**: Production-ready comprehensive analysis
**Check**: All gates passed, final report complete

---

## 9. Risk Mitigation

### Risk: AI Service Outage
**Mitigation**: Fallback to Claude-only analysis with warning

### Risk: Context Overflow
**Mitigation**: External memory, progressive disclosure, checkpoints

### Risk: Low Quality Score
**Mitigation**: Iteration 2 to fill gaps and improve quality

### Risk: Conflicting Information
**Mitigation**: Ground truth verification against codebase/docs

---

## 10. Timeline Estimate

| Phase | Tasks | Time Estimate |
|-------|-------|---------------|
| Planning | Create this plan | [X] min |
| Research | Claude + Gemini + Codex | [X] min |
| Analysis | Pattern analysis | [X] min |
| Synthesis | Multi-source integration | [X] min |
| Verification | Cross-check + quality | [X] min |
| Iteration | If needed | [X] min |
| Final Report | Comprehensive output | [X] min |
| **TOTAL** | | **[X] min** |

---

## 11. Notes

[Any additional notes, special considerations, or context]

---

**Plan Status**: READY FOR EXECUTION
**Next Step**: Launch parallel research agents
