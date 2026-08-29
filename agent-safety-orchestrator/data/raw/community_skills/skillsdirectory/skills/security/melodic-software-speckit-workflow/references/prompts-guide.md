# Prompts Guide

Prompt templates for each phase of the Spec Kit workflow.

## Overview

Each phase has an associated prompt template that guides AI-assisted specification generation. These prompts are designed to produce consistent, high-quality outputs that follow the Spec Kit workflow.

## Specify Prompt

### Purpose

Transform a feature request into a structured specification.

### Template

```markdown
# Specification Generation Prompt

## Context
You are a requirements engineer creating a specification for a software feature.

## Inputs
- Feature Request: {{feature_request}}
- Project Constitution: {{constitution}}
- Existing Codebase Context: {{codebase_context}}

## Task
Generate a complete feature specification following this structure:

### 1. Context Section
- **Problem Statement:** Clearly articulate the problem being solved
- **Motivation:** Explain why this is important and valuable
- **Scope:** Define what's in and out of scope

### 2. Requirements
For each requirement:
- Assign a unique ID (REQ-001, REQ-002, etc.)
- Apply the appropriate EARS pattern:
  - Ubiquitous: "The system SHALL..."
  - State-Driven: "WHILE <condition>, the system SHALL..."
  - Event-Driven: "WHEN <trigger>, the system SHALL..."
  - Unwanted: "IF <condition>, THEN the system SHALL..."
  - Optional: "WHERE <feature>, the system SHALL..."
- Assign priority (must/should/could)

### 3. Acceptance Criteria
For each requirement, write Given/When/Then criteria:
- AC-xxx-01, AC-xxx-02, etc. (linked to requirement)
- Cover happy path and error cases
- Be specific about observable outcomes

### 4. Dependencies and Risks
- List external and internal dependencies
- Identify technical and business risks

## Output Format
Generate a complete feature.md following the Spec Kit template.

## Validation
Before finalizing, verify:
- [ ] All requirements use EARS patterns
- [ ] All requirements have acceptance criteria
- [ ] Priorities are assigned
- [ ] Scope is clearly defined
```

### Variables

| Variable | Source | Description |
| --- | --- | --- |
| `feature_request` | User input | The original feature request or user story |
| `constitution` | `.constitution.md` | Project principles and constraints |
| `codebase_context` | Codebase analysis | Relevant existing code and patterns |

---

## Plan Prompt

### Purpose

Design technical implementation approach from specification.

### Template

```markdown
# Design Generation Prompt

## Context
You are a software architect designing the implementation for a specified feature.

## Inputs
- Feature Specification: {{feature_md}}
- Project Constitution: {{constitution}}
- Current Architecture: {{architecture_context}}
- Technology Stack: {{tech_stack}}

## Task
Generate a complete design document following this structure:

### 1. Overview
Provide a high-level summary of the implementation approach.

### 2. Architecture
- **Component Design:** List components and their responsibilities
- **Data Model:** Entities, relationships, schema changes
- **API Design:** Endpoints, contracts, interfaces

### 3. Technical Approach
- **Selected Approach:** Describe the chosen approach with rationale
- **Alternatives Considered:** Document at least 2 alternatives with:
  - Pros and cons
  - Why not selected

### 4. Integration Points
Document all integration points with:
- External services
- Internal modules
- Event/message contracts

### 5. Testing Strategy
- Unit testing approach
- Integration testing approach
- E2E test scenarios

### 6. Rollout Plan
- Deployment strategy
- Rollback plan
- Monitoring requirements

## Output Format
Generate a complete design.md following the Spec Kit template.

## Validation
Before finalizing, verify:
- [ ] Design addresses ALL requirements
- [ ] Architecture aligns with constitution
- [ ] Alternatives documented
- [ ] Testing strategy is comprehensive
```

### Variables

| Variable | Source | Description |
| --- | --- | --- |
| `feature_md` | Phase 1 output | The feature specification |
| `constitution` | `.constitution.md` | Project principles and constraints |
| `architecture_context` | Codebase analysis | Current architecture patterns |
| `tech_stack` | Project configuration | Technologies and frameworks |

---

## Tasks Prompt

### Purpose

Break down design into implementable tasks.

### Template

```markdown
# Task Generation Prompt

## Context
You are a technical lead breaking down a design into implementable tasks.

## Inputs
- Feature Specification: {{feature_md}}
- Design Document: {{design_md}}
- Team Capacity: {{capacity_info}}
- Development Workflow: {{workflow_info}}

## Task
Generate a complete task breakdown following this structure:

### 1. Task Identification
For each task:
- Assign unique ID (TSK-001, TSK-002, etc.)
- Write clear title
- Link to requirement(s) it addresses

### 2. Task Details
For each task include:
- **Status:** pending (initial state)
- **Requirement:** REQ-xxx (which requirement)
- **Estimated Effort:** S/M/L/XL
- **Description:** What needs to be done
- **Deliverables:** Specific outputs (files, tests, docs)
- **Acceptance Criteria:** How to verify completion

### 3. Dependency Graph
Map task dependencies:
- Which tasks must complete before others
- Identify parallel execution opportunities
- Highlight critical path

### 4. Effort Summary
Summarize effort distribution:
| Size | Count | Typical Duration |
| S | n | < 2 hours |
| M | n | 2-4 hours |
| L | n | 4-8 hours |
| XL | n | > 8 hours |

## Sizing Guidelines
- **S (Small):** Simple, isolated change, < 2 hours
- **M (Medium):** Moderate complexity, 2-4 hours
- **L (Large):** Significant work, 4-8 hours
- **XL (Extra Large):** Complex, should consider splitting, > 8 hours

## Output Format
Generate a complete tasks.md following the Spec Kit template.

## Validation
Before finalizing, verify:
- [ ] Every requirement has at least one task
- [ ] All tasks have clear deliverables
- [ ] Dependencies are mapped
- [ ] No task exceeds XL size
```

### Variables

| Variable | Source | Description |
| --- | --- | --- |
| `feature_md` | Phase 1 output | The feature specification |
| `design_md` | Phase 2 output | The design document |
| `capacity_info` | Team configuration | Team size and availability |
| `workflow_info` | Process docs | Development workflow details |

---

## Implementation Guidance Prompt

### Purpose

Guide task implementation with context.

### Template

```markdown
# Implementation Guidance Prompt

## Context
You are implementing a specific task from the specification workflow.

## Inputs
- Current Task: {{task}}
- Feature Specification: {{feature_md}}
- Design Document: {{design_md}}
- Full Task List: {{tasks_md}}
- Codebase Context: {{codebase_context}}

## Task
Implement TSK-{{task_id}} following these guidelines:

### 1. Pre-Implementation Check
- [ ] All dependencies ({{dependencies}}) are complete
- [ ] Design guidance understood
- [ ] Acceptance criteria clear

### 2. Implementation Steps
Based on the design, implement:
{{implementation_guidance}}

### 3. Validation Steps
Verify completion:
{{acceptance_criteria}}

### 4. Post-Implementation
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Ready for review

## Output
Implemented code that:
- Follows design.md guidance
- Passes acceptance criteria
- Includes appropriate tests
- Has updated documentation
```

### Variables

| Variable | Source | Description |
| --- | --- | --- |
| `task` | tasks.md | Current task details |
| `task_id` | tasks.md | Task identifier |
| `dependencies` | tasks.md | Task prerequisites |
| `feature_md` | Phase 1 output | Feature specification |
| `design_md` | Phase 2 output | Design document |
| `tasks_md` | Phase 3 output | Full task list |
| `codebase_context` | Codebase analysis | Relevant existing code |
| `implementation_guidance` | design.md | Specific implementation notes |
| `acceptance_criteria` | tasks.md | Task acceptance criteria |

---

## Prompt Customization

### Adding Project-Specific Context

Enhance prompts with:

```markdown
## Project-Specific Guidelines
{{project_guidelines}}

## Coding Standards
{{coding_standards}}

## Architectural Patterns
{{architectural_patterns}}
```

### Adjusting Detail Level

For more detailed output:

```markdown
## Detail Level: High
Provide comprehensive explanations and examples.
```

For concise output:

```markdown
## Detail Level: Minimal
Focus on essential elements only.
```

### Iterative Refinement

```markdown
## Feedback
Previous output review: {{feedback}}

## Revision Request
Please update the following sections:
{{revision_sections}}
```

---

## Prompt Locations

| Phase | Prompt | Recommended Location |
| --- | --- | --- |
| 1 | Specify | `prompts/specify.prompt.md` |
| 2 | Plan | `prompts/plan.prompt.md` |
| 3 | Tasks | `prompts/tasks.prompt.md` |
| 4 | Implement | `prompts/implement.prompt.md` |

---

## Best Practices

### Prompt Engineering

1. **Be Explicit:** State exactly what output format is expected
2. **Provide Context:** Include all relevant inputs
3. **Set Constraints:** Define boundaries and requirements
4. **Include Examples:** Show desired output patterns
5. **Add Validation:** Include verification checklists

### Variable Management

1. **Consistent Naming:** Use descriptive, consistent variable names
2. **Document Sources:** Note where each variable comes from
3. **Handle Missing:** Define behavior when variables are empty
4. **Validate Inputs:** Check variable content before use

### Output Quality

1. **Structured Output:** Use consistent document structures
2. **Traceable Links:** Maintain ID links between documents
3. **Validation Points:** Include explicit validation checklists
4. **Iteration Support:** Design for refinement cycles
