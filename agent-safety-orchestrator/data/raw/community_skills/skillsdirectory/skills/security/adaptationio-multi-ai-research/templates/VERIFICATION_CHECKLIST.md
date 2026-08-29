# Verification Checklist

**Analysis**: [OBJECTIVE]
**Date**: [TIMESTAMP]
**Verifier**: verification-agent

---

## Completeness Verification

### Objectives Coverage
Total objectives from plan: [ ]
Objectives addressed: [ ]
Objectives missing: [ ]

**Details**:
- [ ] Objective 1: [description] - STATUS
- [ ] Objective 2: [description] - STATUS
- [ ] Objective 3: [description] - STATUS

**Completeness Score**: ____%

---

### File Coverage
Files identified in glob: [ ]
Files analyzed: [ ]
Files not analyzed: [ ]

**Details**:
- [ ] [file path] - ANALYZED / NOT ANALYZED / SKIPPED (reason)

**File Coverage Score**: ____%

---

### Research Questions
Total questions: [ ]
Questions answered: [ ]
Questions unanswered: [ ]

**Details**:
- [ ] Question 1: [question] - ANSWERED / NOT ANSWERED

**Question Coverage**: ____%

---

## Accuracy Verification

### Citation Coverage
Total claims in analysis: [ ]
Claims with citations: [ ]
Claims without citations: [ ]

**Missing Citations**:
- Line [X]: "[claim]" - NO CITATION
- Line [Y]: "[claim]" - NO CITATION

**Citation Coverage**: ____%

---

### Source Accuracy
Citations checked: [ ]
Accurate citations: [ ]
Inaccurate citations: [ ]

**Issues**:
- Line [X]: Citation [file:line] → Content doesn't match
- Line [Y]: Citation [URL] → URL not accessible

**Source Accuracy**: ____%

---

### Quote Verification
Quotes found: [ ]
Exact matches: [ ]
Misquotes: [ ]

**Issues**:
- Line [X]: Quote doesn't match source at [file:line]

**Quote Accuracy**: ____%

---

## Cross-Source Validation

### High Confidence (All Sources Agree)
Count: [ ]

**Examples**:
- [ ] Finding 1: [description]
  - Claude: ✓
  - Gemini: ✓
  - Codex: ✓

---

### Medium Confidence (2/3 Agree)
Count: [ ]

**Examples**:
- [ ] Finding X: [description]
  - Sources agreeing: Claude, Gemini
  - Source differing: Codex

---

### Contradictions
Count: [ ]

**Details**:
- [ ] Contradiction 1: [description]
  - Source A says: [claim]
  - Source B says: [different claim]
  - Resolution status: RESOLVED / UNRESOLVED

---

## Quality Assessment

### Comprehensiveness (/20)
- [ ] All objectives covered: __/5
- [ ] All aspects addressed: __/5
- [ ] Edge cases considered: __/5
- [ ] Complete coverage: __/5

**Score**: __/20

---

### Accuracy (/20)
- [ ] All claims sourced: __/5
- [ ] Sources traceable: __/5
- [ ] Quotes accurate: __/5
- [ ] No factual errors: __/5

**Score**: __/20

---

### Specificity (/20)
- [ ] Specific file:line refs: __/5
- [ ] Code examples included: __/5
- [ ] Not vague claims: __/5
- [ ] Quantitative data: __/5

**Score**: __/20

---

### Actionability (/20)
- [ ] Recommendations specific: __/5
- [ ] Implementation guidance: __/5
- [ ] Prioritization clear: __/5
- [ ] Next steps defined: __/5

**Score**: __/20

---

### Consistency (/20)
- [ ] No contradictions: __/5
- [ ] Terminology consistent: __/5
- [ ] Logic sound: __/5
- [ ] Evidence supports claims: __/5

**Score**: __/20

---

**Overall Quality Score**: ____/100

---

## Gap Analysis

### Critical Gaps (MUST FIX)
Count: [ ]

**Details**:
1. **Gap**: [description]
   - **Impact**: Critical
   - **Action**: [specific task]
   - **Assigned to**: [AI system]

---

### Medium Gaps (SHOULD FIX)
Count: [ ]

**Details**:
1. **Gap**: [description]
   - **Impact**: Medium
   - **Action**: [specific task]

---

### Minor Gaps (NICE TO FIX)
Count: [ ]

---

## Quality Gates

### Gate 1: Completeness ≥95%
- **Result**: PASS ✓ / FAIL ✗
- **Score**: ____%
- **Status**: [details if fail]

---

### Gate 2: Citation Coverage 100%
- **Result**: PASS ✓ / FAIL ✗
- **Coverage**: ____%
- **Missing**: [count]

---

### Gate 3: Quality Score ≥95
- **Result**: PASS ✓ / FAIL ✗
- **Score**: ____/100
- **Issues**: [details if fail]

---

### Gate 4: No Critical Gaps
- **Result**: PASS ✓ / FAIL ✗
- **Critical Gaps**: [count]
- **Details**: [if any]

---

## OVERALL VERIFICATION RESULT

**STATUS**: PASS ✓ / NEEDS ITERATION ✗

**Summary**:
- Completeness: ____%
- Citation Coverage: ____%
- Quality Score: ____/100
- Critical Gaps: [count]

---

## Recommendations

### If PASS ✓
- [x] Proceed to final report
- [x] No iteration needed
- [x] Production-ready

### If FAIL ✗

**Priority 1 (MUST FIX)**:
1. [Specific action]
2. [Specific action]

**Priority 2 (SHOULD FIX)**:
1. [Specific action]

**Priority 3 (NICE TO FIX)**:
1. [Specific action]

---

## Iteration Guidance

### For Iteration 2
**Focus Areas**:
1. [Specific gap to fill]
2. [Specific quality improvement]
3. [Specific accuracy fix]

**Estimated Effort**: [X] hours
**Expected Improvement**: [current score] → [target score]

**Tasks for Next Iteration**:
- [ ] Task 1: [description] - Assigned to: [AI system]
- [ ] Task 2: [description] - Assigned to: [AI system]
- [ ] Task 3: [description] - Assigned to: [AI system]

---

**Verification Complete**: [TIMESTAMP]
**Next Action**: [Proceed to final / Start iteration 2]
