# Phase Reference

Detailed instructions and checklists for each Spec Kit workflow phase.

## Phase 0: Constitution

### Objective

Establish project-wide principles and constraints before any feature work begins.

### Prerequisites

- Project repository exists
- Team has discussed fundamental principles
- Key technical decisions are made

### Process

1. **Gather Input**
   - Existing documentation (README, CONTRIBUTING, etc.)
   - Team discussions and agreements
   - Technical requirements and constraints
   - Compliance and regulatory requirements

2. **Draft Sections**
   - Core Principles (3-7 items)
   - Technical Constraints (platform, dependencies, limits)
   - Quality Standards (testing, documentation, security)
   - Non-Functional Requirements (performance, reliability, scalability)
   - Team Conventions (naming, git, review)

3. **Review and Approve**
   - Share with full team
   - Address concerns and objections
   - Achieve consensus (not unanimity)
   - Document dissenting opinions if any

4. **Finalize**
   - Create `.constitution.md` at project root
   - Add version and date
   - Commit to repository
   - Announce to team

### Validation Checklist

- [ ] `.constitution.md` exists at project root
- [ ] All required sections are present
- [ ] Principles are specific and actionable
- [ ] Constraints have measurable criteria
- [ ] Team has reviewed and approved
- [ ] Version and date are documented

### Output

```text
.constitution.md (committed to repository)
```

---

## Phase 1: Specify

### Objective

Transform a feature request into a structured specification with requirements and acceptance criteria.

### Prerequisites

- Constitution exists (Phase 0 complete)
- Feature request or user story available
- Understanding of business context

### Process

1. **Understand the Request**
   - Read the feature request thoroughly
   - Identify the core problem being solved
   - Note any explicit constraints or requirements
   - Ask clarifying questions if needed

2. **Extract Context**
   - Problem Statement: What issue does this address?
   - Motivation: Why is this important now?
   - Scope: What's included? What's explicitly excluded?
   - Success Criteria: How do we know we're done?

3. **Identify Requirements**
   - List all functional requirements
   - List non-functional requirements specific to this feature
   - Prioritize using MoSCoW (Must, Should, Could, Won't)

4. **Apply EARS Patterns**
   - Classify each requirement by type
   - Write using appropriate EARS syntax
   - Ensure each requirement is testable
   - Assign unique IDs (REQ-001, REQ-002, etc.)

5. **Write Acceptance Criteria**
   - For each requirement, write Given/When/Then
   - Cover happy path and error cases
   - Be specific about observable outcomes
   - Assign unique IDs (AC-001, AC-002, etc.)

6. **Document Dependencies and Risks**
   - External dependencies (services, data, approvals)
   - Internal dependencies (other features, infrastructure)
   - Technical risks
   - Business risks

### Validation Checklist

- [ ] Context section is complete (problem, motivation, scope)
- [ ] All requirements use EARS patterns
- [ ] All requirements have unique IDs
- [ ] All requirements have acceptance criteria
- [ ] Priorities are assigned (must/should/could)
- [ ] Dependencies are documented
- [ ] Risks are identified
- [ ] Specification is self-contained and readable

### Output

```text
.specs/<feature-name>/feature.md
```

---

## Phase 2: Plan

### Objective

Design the technical implementation approach that addresses all requirements.

### Prerequisites

- Phase 1 complete (feature.md exists)
- Understanding of current codebase
- Access to architectural documentation

### Process

1. **Review Inputs**
   - Read feature.md thoroughly
   - Review relevant constitution sections
   - Examine related existing code
   - Note integration points

2. **Design Architecture**
   - Identify components needed
   - Define component responsibilities
   - Map data flow between components
   - Document API/interface contracts

3. **Model Data**
   - Identify entities and relationships
   - Design database schema changes
   - Consider migration strategy
   - Plan for backward compatibility

4. **Consider Alternatives**
   - Identify at least 2 approaches
   - Document pros and cons of each
   - Select approach with rationale
   - Document why alternatives were rejected

5. **Plan Integration**
   - External service integrations
   - Internal module dependencies
   - Event/message contracts
   - Error handling across boundaries

6. **Define Testing Strategy**
   - Unit test approach
   - Integration test approach
   - E2E test scenarios
   - Performance test considerations

7. **Plan Rollout**
   - Deployment strategy (big bang, canary, feature flag)
   - Rollback plan
   - Monitoring and alerting
   - Communication plan

### Validation Checklist

- [ ] Design addresses ALL requirements from feature.md
- [ ] Architecture aligns with constitution
- [ ] Alternatives were considered and documented
- [ ] Data model is complete
- [ ] API contracts are defined
- [ ] Integration points are documented
- [ ] Testing strategy covers all acceptance criteria
- [ ] Rollout plan exists with rollback

### Output

```text
.specs/<feature-name>/design.md
```

---

## Phase 3: Tasks

### Objective

Break down the design into implementable, independently deliverable tasks.

### Prerequisites

- Phase 2 complete (design.md exists)
- Understanding of team capacity
- Knowledge of development workflow

### Process

1. **Identify Work Items**
   - Review design.md for all implementation work
   - List infrastructure setup tasks
   - List development tasks
   - List testing tasks
   - List documentation tasks

2. **Decompose to Appropriate Size**
   - Each task: 2-8 hours of work
   - Tasks larger than 8 hours: split further
   - Tasks smaller than 2 hours: consider combining

3. **Map to Requirements**
   - Each requirement must have at least one task
   - Document which requirement(s) each task addresses
   - Ensure full coverage of acceptance criteria

4. **Define Dependencies**
   - Identify task prerequisites
   - Build dependency graph
   - Identify critical path
   - Look for parallelization opportunities

5. **Estimate Effort**
   - Use t-shirt sizes (S, M, L, XL)
   - Base on similar past work
   - Include testing and documentation time
   - Account for review and iteration

6. **Write Task Details**
   - Clear description of what to do
   - Specific deliverables (files, tests, docs)
   - Acceptance criteria (how to verify done)
   - Dependencies (what must be complete first)

### Validation Checklist

- [ ] Every requirement has at least one task
- [ ] All tasks have unique IDs
- [ ] All tasks have effort estimates
- [ ] Dependencies are documented
- [ ] No task exceeds XL size
- [ ] Critical path is identified
- [ ] Parallel tracks are identified
- [ ] All tasks have clear deliverables
- [ ] All tasks have acceptance criteria

### Output

```text
.specs/<feature-name>/tasks.md
```

---

## Phase 4: Implement

### Objective

Execute tasks systematically, validating against specifications at each step.

### Prerequisites

- Phase 3 complete (tasks.md exists)
- Development environment ready
- All blocking dependencies resolved

### Process

1. **Select Next Task**
   - Check dependency graph
   - Choose task with no incomplete prerequisites
   - Consider critical path priority
   - Mark task as "in progress"

2. **Review Task Context**
   - Read task description and deliverables
   - Review related design.md section
   - Review related acceptance criteria
   - Understand integration points

3. **Implement**
   - Follow design.md guidance
   - Write tests before/during implementation
   - Keep changes focused on task scope
   - Document decisions and deviations

4. **Validate**
   - Check all deliverables are complete
   - Run acceptance criteria checks
   - Ensure tests pass
   - Verify no regressions

5. **Complete Task**
   - Mark task as "complete" in tasks.md
   - Commit changes with reference to task ID
   - Update any related documentation
   - Note any issues for future tasks

6. **Repeat**
   - Continue until all tasks complete
   - Re-validate dependencies after each completion
   - Communicate blockers immediately

### Per-Task Checklist

- [ ] Dependencies are satisfied
- [ ] Task description understood
- [ ] Design guidance reviewed
- [ ] Implementation complete
- [ ] Tests written and passing
- [ ] Acceptance criteria verified
- [ ] Documentation updated
- [ ] Changes committed
- [ ] Task marked complete

### Feature Completion Checklist

- [ ] All tasks marked complete
- [ ] All acceptance criteria verified
- [ ] Full test suite passing
- [ ] Documentation complete
- [ ] Code review completed
- [ ] Feature demo ready
- [ ] Deployment plan confirmed

### Output

```text
Implemented feature (code, tests, documentation)
Updated tasks.md with completion status
```

---

## Phase Transitions

### Transition Gates

Each phase transition has explicit gates that must be passed.

| From | To | Gate |
| --- | --- | --- |
| 0 | 1 | Constitution exists and is valid |
| 1 | 2 | Specification complete with EARS and AC |
| 2 | 3 | Design addresses all requirements |
| 3 | 4 | Tasks mapped to all requirements |

### Gate Validation Process

1. Run validation checklist for current phase
2. All items must pass
3. Document any exceptions or waivers
4. Get explicit approval to proceed (if required)

### Handling Gate Failures

If a gate fails:

1. Document what's missing
2. Return to previous phase to address
3. Re-run validation
4. Do not proceed until gate passes

---

## Emergency Procedures

### Scope Changes Mid-Phase

1. **During Specify:** Update feature.md, re-validate
2. **During Plan:** Assess impact, update design.md if needed
3. **During Tasks:** Assess impact, update tasks.md, recalculate estimates
4. **During Implement:** Stop, assess, potentially return to earlier phase

### Blocking Issues

1. Document the blocker in current phase output
2. Identify alternatives or workarounds
3. Escalate if blocker cannot be resolved
4. Update timeline and communicate

### Specification Defects Found During Implementation

1. Document the defect discovered
2. Assess: specification error or implementation error?
3. If specification error: return to appropriate phase
4. If implementation error: fix and continue
