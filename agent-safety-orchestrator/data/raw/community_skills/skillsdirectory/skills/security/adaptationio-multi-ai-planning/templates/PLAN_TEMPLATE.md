# Plan: [OBJECTIVE]

**Plan ID**: plan-YYYYMMDD-HHMMSS
**Created**: [TIMESTAMP]
**Status**: Planning
**Quality Score**: TBD / 100

---

## 1. Objective & Scope

### Primary Objective
[Clear, specific statement of what needs to be accomplished]

### Success Criteria
1. [Specific, measurable criterion]
2. [Criterion 2]
3. [Criterion 3]

### Scope

**Included**:
- [What is in scope]
- [Component/area 2]
- [Component/area 3]

**Excluded**:
- [What is explicitly out of scope]
- [Boundary 2]

---

## 2. Approach & Strategy

**High-Level Approach**: [One paragraph explaining the strategy]

**Key Decisions**:
1. **Decision**: [Technology/pattern choice]
   - **Rationale**: [Why this decision]
   - **Alternatives Considered**: [What else was considered]

2. **Decision**: [Approach choice]
   - **Rationale**: [Why]

**Risks & Mitigations**:
1. **Risk**: [Potential risk]
   - **Probability**: Low/Medium/High
   - **Impact**: Low/Medium/High/Critical
   - **Mitigation**: [How we'll handle this]

---

## 3. Task Breakdown

### Large Tasks (8-15 tasks)

#### Task 1: [Name]
- **ID**: 1
- **Level**: Large
- **Description**: [What needs to be done]
- **Dependencies**: None
- **Estimated**: [X] hours
- **Agent Suggestion**: [Which type of agent]
- **Status**: ⬜ Pending

**Medium Tasks** (Break down to 3-8 if complex):
- 1.1: [Subtask]
- 1.2: [Subtask]
- 1.3: [Subtask]

**Verification**:
- [ ] Success criterion 1
- [ ] Success criterion 2
- **Method**: [automated_test/manual_check/etc]
- **Commands**: `[verification command if automated]`

#### Task 2: [Name]
[Same format as Task 1]

---

## 4. Dependency Map

### Dependency Graph
```
Task 1 (start immediately)
  ├→ Task 2 (after Task 1)
  └→ Task 3 (after Task 1)
       └→ Task 5 (after Task 3)
Task 4 (independent, can run parallel to above)
```

### Critical Path
Longest chain: Task 1 → Task 2 → Task 5
**Est. Critical Path Time**: [X] hours

### Parallel Execution Opportunities

**Parallel Group 1** (can start immediately):
- Task 1

**Parallel Group 2** (after Task 1):
- Task 2
- Task 3

**Parallel Group 3** (independent):
- Task 4

---

## 5. Verification Strategy

### Per-Task Verification
Each task includes specific success criteria and verification method (see task details above).

### Integration Verification

**After Task 1**:
- [ ] [Integration check 1]
- [ ] [Integration check 2]

**After Task 3**:
- [ ] [Integration check]

**Final Integration**:
- [ ] All components work together
- [ ] End-to-end workflows function
- [ ] No regressions introduced

### Quality Gates

**Gate 1: Planning Complete**
- [ ] All requirements mapped to tasks
- [ ] All tasks have verification
- [ ] Dependencies documented
- [ ] Quality score ≥90

**Gate 2: Implementation Phase 1**
- [ ] First 3 tasks complete and verified
- [ ] Integration checks pass
- [ ] No blocking issues

**Gate 3: Implementation Phase 2**
- [ ] All tasks complete
- [ ] All verification passing
- [ ] Integration verified

**Gate 4: Production Ready**
- [ ] All quality gates passed
- [ ] Documentation complete
- [ ] Tested end-to-end
- [ ] Rollback plan ready

---

## 6. Checkpoint Strategy

### Checkpoint Locations

**Checkpoint 1** (cp-001):
- **After Tasks**: 1, 2
- **Description**: Foundation complete
- **Rollback Safe**: Yes

**Checkpoint 2** (cp-002):
- **After Tasks**: 3, 4, 5
- **Description**: Core functionality complete
- **Rollback Safe**: Yes

**Checkpoint 3** (cp-003):
- **After Tasks**: All
- **Description**: Pre-deployment checkpoint
- **Rollback Safe**: Yes

### Checkpoint Process

**Creating Checkpoint**:
```bash
# Commit current work
git add .
git commit -m "Checkpoint: [description]"

# Create tag
git tag -a "checkpoint-[id]" -m "[metadata]"

# Create patch bundle (safety)
git format-patch -1 HEAD -o checkpoints/

# Save metadata
echo '{"id":"cp-001","tasks":["1","2"],...}' > checkpoints/cp-001.json
```

**Resuming from Checkpoint**:
```bash
# Read checkpoint metadata
cat checkpoints/cp-001.json

# Verify git is clean
git status

# Continue from checkpoint tasks
```

**Rollback (if needed)**:
```bash
# Create recovery branch
git checkout -b recovery-from-cp-001 checkpoint-001

# Or apply patch
git am checkpoints/cp-001.patch
```

---

## 7. Agent Assignment & Coordination

### Task Agent Suggestions

| Task | Suggested Agent | Coordination Method |
|------|----------------|---------------------|
| 1 | research-agent | Spawn via Task tool, outputs to research.md |
| 2 | code-agent | Reads research.md, implements based on findings |
| 3 | test-agent | Parallel to Task 2, generates tests |
| 4 | review-agent | After Task 2 & 3, reviews implementation |

### Coordination Mechanisms

**Shared Files**:
- `progress.json` - Real-time progress tracking
- `research-findings.md` - Research outputs
- `implementation-notes.md` - Implementation details

**Execution Pattern**:
```typescript
// Parallel execution where possible
const [research, tests] = await Promise.all([
  task({description: "Research", prompt: "..."}),
  task({description: "Tests", prompt: "..."})
]);

// Sequential where dependent
const impl = await task({
  description: "Implementation",
  prompt: `Based on research in ${research.output}, implement...`
});
```

---

## 8. Resource Requirements

**Agents**: [Number and types]
**Tools**: [write, read, bash, grep, etc.]
**Permissions**: [Any special permissions needed]
**External Services**: [APIs, databases, etc.]
**Estimated Total Time**: [X] hours

---

## 9. Timeline

| Phase | Tasks | Estimated | Actual | Status |
|-------|-------|-----------|--------|--------|
| Phase 1 | 1-2 | [X]h | TBD | ⬜ Pending |
| Phase 2 | 3-4 | [X]h | TBD | ⬜ Pending |
| Phase 3 | 5-7 | [X]h | TBD | ⬜ Pending |
| **Total** | | **[X]h** | **TBD** | |

---

## 10. Rollback Plan

### Failure Scenarios

**Scenario 1**: [Specific failure]
- **Detection**: [How we know it failed]
- **Rollback**: Restore from checkpoint [X]
- **Re-plan**: [What changes to make]

**Scenario 2**: [Another failure type]
- **Detection**: [How to detect]
- **Rollback**: [Rollback procedure]
- **Recovery**: [How to recover and continue]

### Safe Rollback Procedure

1. Identify failure point (which task failed?)
2. Find last good checkpoint before failure
3. Verify checkpoint is safe (git tag exists, patch exists, metadata complete)
4. Create recovery branch from checkpoint tag
5. Re-plan from that point with lessons learned

---

## 11. Monitoring & Progress

### Progress Tracking
- **Tool**: progress.json (updated after each task)
- **Format**: `{"completed": ["1","2"], "current": "3", "remaining": ["4","5"]}`
- **Frequency**: Real-time updates

### Success Indicators
- All tasks status = "complete"
- All verification criteria met
- All quality gates passed
- Integration verification complete

### Completion Criteria
- [ ] All tasks in task breakdown are complete
- [ ] All verification passed
- [ ] All quality gates passed
- [ ] Integration verified
- [ ] Documentation updated
- [ ] Rollback plan tested

---

## 12. Next Steps

### Immediate Actions
1. [First specific action to take]
2. [Second action]
3. [Third action]

### Approval Required
- [ ] Review this plan
- [ ] Approve approach and scope
- [ ] Confirm resource allocation
- [ ] Authorize execution

### Begin Execution
Once approved, start with Task 1 and follow task order, updating progress in real-time.

---

**Plan Status**: ⬜ Pending Approval
**Next Action**: Review and approve this plan
**Estimated Total**: [X] hours
**Quality Target**: ≥90/100
