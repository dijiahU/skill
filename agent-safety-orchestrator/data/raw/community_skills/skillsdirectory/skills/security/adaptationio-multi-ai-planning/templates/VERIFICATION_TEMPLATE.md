# Plan Verification Report

**Plan ID**: [plan-id]
**Verified**: [TIMESTAMP]
**Verifier**: [claude/human]

---

## Schema Validation

- [x] plan.json validates against plan.schema.json
- [x] All task objects validate against task.schema.json
- [x] All checkpoint objects validate against checkpoint.schema.json
- [x] No schema errors

**Result**: ✅ PASS / ❌ FAIL

---

## Completeness Check

### Requirements Coverage
- Total requirements: [N]
- Requirements mapped to tasks: [N]
- **Coverage**: [X]% (target: ≥95%)

**Details**:
- ✅ Requirement 1 → Task [X]
- ✅ Requirement 2 → Task [Y]
- ❌ Requirement 3 → NOT MAPPED

### Task Verification Coverage
- Total tasks: [N]
- Tasks with verification: [N]
- **Coverage**: [X]% (target: 100%)

**Missing Verification**:
- Task [X]: No success criteria defined
- Task [Y]: No verification method specified

---

## Dependency Validation

- [x] All dependencies documented
- [x] No circular dependencies detected
- [x] Critical path calculated
- [x] Parallel groups identified

**Dependency Graph**: Valid ✅ / Invalid ❌

**Issues**:
- [If any circular dependencies or issues]

---

## Quality Scoring

### Comprehensiveness (/20)
- All requirements covered: [X]/5
- All edge cases identified: [X]/5
- Failure scenarios documented: [X]/5
- Resource requirements clear: [X]/5
**Score**: [X]/20

### Feasibility (/20)
- Resources available: [X]/5
- Timeline realistic: [X]/5
- No blocking constraints: [X]/5
- Dependencies manageable: [X]/5
**Score**: [X]/20

### Clarity (/20)
- All steps unambiguous: [X]/5
- Terms defined: [X]/5
- Examples provided: [X]/5
- Agent assignments clear: [X]/5
**Score**: [X]/20

### Executability (/20)
- Success criteria measurable: [X]/5
- Verification methods defined: [X]/5
- Failure handling planned: [X]/5
- Rollback procedures clear: [X]/5
**Score**: [X]/20

### Integration (/20)
- Integration points identified: [X]/5
- Backward compatibility checked: [X]/5
- Testing strategy defined: [X]/5
- Documentation plan clear: [X]/5
**Score**: [X]/20

**Total Quality Score**: [X]/100 (threshold: ≥90)

---

## Quality Gates

### Gate 1: Schema Valid
- **Status**: PASS ✅ / FAIL ❌
- **Details**: [If fail, what errors]

### Gate 2: Completeness ≥95%
- **Status**: PASS ✅ / FAIL ❌
- **Coverage**: [X]%

### Gate 3: Quality Score ≥90
- **Status**: PASS ✅ / FAIL ❌
- **Score**: [X]/100

### Gate 4: No Circular Dependencies
- **Status**: PASS ✅ / FAIL ❌
- **Details**: [If any found]

### Gate 5: All Tasks Verifiable
- **Status**: PASS ✅ / FAIL ❌
- **Missing**: [Count]

**Overall**: ALL GATES PASS ✅ / NEEDS REVISION ❌

---

## Gaps Identified

### Critical Gaps (Must Fix)
1. [Gap description]
   - **Impact**: Critical
   - **Fix**: [Specific action needed]

### Medium Gaps (Should Fix)
1. [Gap description]
   - **Impact**: Medium
   - **Fix**: [Action]

### Minor Gaps (Nice to Fix)
1. [Gap]

---

## Recommendations

### If PASS ✅
- **Status**: Plan approved for execution
- **Next Step**: Begin Task 1
- **Monitoring**: Track progress in progress.json

### If FAIL ❌

**Priority 1 (Must Fix Before Execution)**:
1. [Specific fix needed]
2. [Fix 2]

**Priority 2 (Should Fix)**:
1. [Fix]

**Estimated Effort to Address**: [X] hours

**Re-verification**: Required after fixes applied

---

**Verification Complete**: [TIMESTAMP]
**Result**: APPROVED ✅ / NEEDS REVISION ❌
**Next Action**: [Execute plan / Apply fixes]
