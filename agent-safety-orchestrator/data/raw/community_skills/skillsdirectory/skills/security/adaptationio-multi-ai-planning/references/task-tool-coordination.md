# Task Tool Coordination Patterns

This guide documents how to coordinate multiple agents using the Task tool in Claude Code, based on analysis of existing workflow skills.

## Key Understanding

**Important**: The Task tool in Claude Code spawns agents that:
- Receive the full conversation context (not isolated)
- Have access to the same tools as the parent
- Execute a specific prompt you provide
- Return results back to the main conversation

**Pattern from existing skills**: Workflow skills don't spawn Task agents automatically. They **guide users through a process**, invoking component skills at each step.

---

## Pattern 1: Sequential Workflow Coordination

**Example**: development-workflow orchestrates 5 component skills sequentially

**How It Works**:
```markdown
### Step 1: Research Domain
**Component Skill**: skill-researcher
**Integration Method**: Guided execution (user invokes skill-researcher)

Process:
1. User sees instruction to use skill-researcher
2. User invokes: "Use skill-researcher for [objective]"
3. skill-researcher executes its operations
4. Results saved to research-synthesis.md
5. User proceeds to Step 2

### Step 2: Plan Architecture
**Component Skill**: planning-architect
**Integration Method**: Guided execution

Process:
1. User invokes planning-architect with research findings
2. planning-architect executes its workflow
3. Results saved to skill-plan.md
4. User proceeds to Step 3
```

**Key Insight**: No automatic Task spawning. The workflow skill **documents the process** and users **manually invoke** each component skill.

---

## Pattern 2: Parallel Decomposition (Advanced)

**When**: Complex objectives need to be broken down in parallel

**How**: Use Task tool to spawn multiple decomposition agents:

```typescript
// In a Claude Code session, you can do:

const decompositions = await Promise.all([
  task({
    subagent_type: "general-purpose",
    description: "Decompose database schema task",
    prompt: `Break down the "Database Schema" large task into 3-8 medium tasks.

For each medium task provide:
- Clear description
- Dependencies (which other tasks it depends on)
- Estimated hours
- Success criteria

Output format:
{
  "tasks": [
    {
      "id": "1.1",
      "description": "...",
      "dependencies": [],
      "estimated_hours": 2,
      "success_criteria": ["..."]
    }
  ]
}

Write complete JSON to: decomposition-task1.json`
  }),

  task({
    subagent_type: "general-purpose",
    description: "Decompose OAuth integration task",
    prompt: `Break down the "OAuth Integration" large task...
    Write to: decomposition-task2.json`
  })
]);

// After agents complete, read their outputs
const task1Decomp = JSON.parse(fs.readFileSync('decomposition-task1.json'));
const task2Decomp = JSON.parse(fs.readFileSync('decomposition-task2.json'));

// Integrate into main plan
```

**Benefits**:
- Parallel decomposition (faster)
- Each agent focuses on one large task
- Results are integrated by main agent

---

## Pattern 3: Shared State Coordination

**When**: Multiple agents need to coordinate via shared files

**How**: Agents write to specific files, next agent reads them

```typescript
// Agent 1: Research
await task({
  description: "Research OAuth best practices",
  prompt: `Research OAuth 2.0 implementation best practices.

Search for:
1. Security recommendations
2. Common implementation patterns
3. Popular libraries
4. Testing strategies

Write comprehensive findings to: research-findings.md`
});

// Agent 2: Plan based on research
await task({
  description: "Create OAuth implementation plan",
  prompt: `Read research-findings.md.

Based on the research, create detailed implementation plan for OAuth.

Include:
- Tasks broken down
- Dependencies mapped
- Verification for each task

Write plan to: oauth-plan.json`
});

// Main agent reads final plan
const plan = JSON.parse(fs.readFileSync('oauth-plan.json'));
```

**Pattern**: Agent A → file.md → Agent B reads file → next-file.md

---

## Pattern 4: Verification Agent

**When**: Need independent verification of work

**How**: Spawn separate agent to review/verify

```typescript
// After creating plan
await task({
  subagent_type: "general-purpose",
  description: "Verify plan quality",
  prompt: `Review the plan in plan.json.

Verification tasks:
1. Check all tasks have success criteria
2. Verify no circular dependencies
3. Score quality (0-100) using rubric:
   - Comprehensiveness (/20)
   - Feasibility (/20)
   - Clarity (/20)
   - Executability (/20)
   - Integration (/20)

Write verification report to: verification-report.md

Include:
- Quality score (total /100)
- Gaps identified
- Recommendations
- Approval decision (PASS ≥90 / FAIL <90)`
});

// Read verification results
const verification = fs.readFileSync('verification-report.md', 'utf8');
// Decide based on results
```

---

## Pattern 5: Iterative Refinement

**When**: Plan quality <90, needs improvement

**How**: Iteration loop until quality threshold met

```typescript
let quality_score = 0;
let iteration = 1;

while (quality_score < 90 && iteration <= 3) {
  console.log(`Iteration ${iteration}: Creating/refining plan...`);

  // Create or refine plan
  await task({
    description: `Create plan (iteration ${iteration})`,
    prompt: `Create implementation plan for [objective].
    ${iteration > 1 ? `Previous plan had issues: ${gaps}. Address these.` : ''}
    Write to: plan-v${iteration}.json`
  });

  // Verify quality
  await task({
    description: "Verify plan quality",
    prompt: `Verify plan-v${iteration}.json. Score quality (0-100).
    Write report to: verification-v${iteration}.md`
  });

  // Read quality score
  quality_score = extractQualityScore(`verification-v${iteration}.md`);
  gaps = extractGaps(`verification-v${iteration}.md`);

  iteration++;
}

if (quality_score >= 90) {
  console.log(`✅ Plan approved (score: ${quality_score}/100)`);
} else {
  console.log(`❌ Plan failed after ${iteration-1} iterations`);
}
```

---

## Anti-Patterns to Avoid

### ❌ Don't: Try to Orchestrate Everything in Scripts

**Problem**: Bash scripts can't spawn Task agents
**Reason**: Task tool is Claude Code specific, not accessible from bash

**Wrong Approach**:
```bash
# This WON'T work:
# analyze.sh tries to spawn Task agents
task spawn --type research --prompt "..."  # No such command
```

**Correct Approach**:
- Scripts are utilities (validation, template generation)
- Claude Code spawns Task agents via conversation
- Workflow skills guide the process, don't automate it

### ❌ Don't: Assign Tools to Subagents

**Problem**: Can't restrict tools for Task agents

**Wrong**: "Research agent has tools: [read, grep, glob]"
**Correct**: All agents have same tools as parent, instruct them what to do

### ❌ Don't: Specify Model for Task Agents

**Problem**: Task agents use same model as parent

**Wrong**: "Spawn Haiku agent for verification"
**Correct**: All Task agents are same model, focus on instructions not model

---

## Best Practices

### ✅ Clear, Specific Instructions

When spawning Task agents, provide:
- Clear objective
- Specific output format
- Where to write results
- Success criteria
- Examples (if helpful)

### ✅ External File Communication

Agents coordinate via files:
- Agent 1 writes research-findings.md
- Agent 2 reads research-findings.md
- Main agent integrates all

### ✅ Parallel When Independent

Spawn multiple agents if tasks are independent:
```typescript
const [research, tests, docs] = await Promise.all([
  task({description: "Research", prompt: "..."}),
  task({description: "Generate tests", prompt: "..."}),
  task({description: "Write docs", prompt: "..."})
]);
```

### ✅ Sequential When Dependent

Wait for dependencies:
```typescript
const research = await task({description: "Research", prompt: "..."});
// Use research results for next step
const plan = await task({
  description: "Create plan",
  prompt: `Based on research in research-findings.md, create plan...`
});
```

---

## Example: Complete Planning Coordination

```typescript
// Full planning workflow using Task tool

// Step 1: Parallel research (if multi-ai-research available)
// (User invokes: "Use multi-ai-research for objective")

// Step 2: Decomposition (parallel for complex projects)
const decompositions = await Promise.all([
  task({
    description: "Decompose component A",
    prompt: `Break down component A into 3-8 medium tasks.
    Write to: decomp-a.json`
  }),
  task({
    description: "Decompose component B",
    prompt: `Break down component B into 3-8 medium tasks.
    Write to: decomp-b.json`
  })
]);

// Step 3: Integration (sequential - needs decomposition results)
await task({
  description: "Integrate decompositions into plan",
  prompt: `Read decomp-a.json and decomp-b.json.

  Create integrated plan with:
  - All tasks from both decompositions
  - Dependencies mapped
  - Parallel groups identified

  Write to: plan.json (validate against schema)`
});

// Step 4: Verification (sequential - needs plan)
await task({
  description: "Verify plan quality",
  prompt: `Verify plan.json.

  Check:
  - Schema validation
  - Completeness
  - Quality score (0-100)
  - Gaps

  Write to: verification.md`
});

// Step 5: Read verification, decide
const verification = fs.readFileSync('verification.md', 'utf8');
if (qualityScore >= 90) {
  // Generate final outputs
  await task({
    description: "Finalize plan",
    prompt: `Generate final artifacts from plan.json:
    - PLAN.md (human-readable)
    - COORDINATION.md (execution guide)

    Write both files.`
  });
}
```

---

## Coordination Checklist

When using Task tool for planning:

- [ ] Clear objective for each agent
- [ ] Specific output file specified
- [ ] Output format defined (JSON/Markdown)
- [ ] Success criteria included
- [ ] Dependencies between agents understood
- [ ] Parallel opportunities identified
- [ ] Results integration plan clear
- [ ] Verification planned

---

**Remember**: Task tool is for parallel/delegated execution. Workflow skills guide users through a process, they don't fully automate it.
