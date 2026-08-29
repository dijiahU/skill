# Premortem Workflow

Gary Klein's technique for reducing overconfidence and identifying threats before they materialize.

## When to Use

- Before finalizing a significant decision
- When a plan seems solid but you suspect blind spots
- After achieving consensus too easily
- When stakes are high

## Getting Started

Before running the premortem, use the `AskUserQuestion` tool to gather essential context:

1. **What's the plan?** Get specifics: commitments, milestones, resources, responsibilities.
2. **What's the timeframe?** Needed to set the "one year from now" scenario appropriately.
3. **Who are the stakeholders?** Understanding perspectives helps generate diverse failure modes.
4. **What does success look like?** Defines the contrast for "disaster" scenarios.

This information is necessary to generate realistic and useful failure scenarios.

## The Setup

**Premise:** It is one year from now. We implemented the plan exactly as proposed. The outcome was a disaster.

**Objective:** Write a brief history of that disaster.

## The Process

### Step 1: State the Plan

Document the plan clearly:
- What are we committing to?
- What are the key milestones?
- What resources are allocated?
- Who is responsible for what?

### Step 2: Set the Scene

Read aloud or document:

> "Imagine we are one year into the future. We implemented this plan as it now exists. The outcome was a disaster. Please take 5-10 minutes to write a brief history of that disaster."

### Step 3: Individual Writing (5-10 minutes)

Each participant writes independently:
- What went wrong?
- Why did it fail?
- What warning signs did we miss?
- What assumptions proved false?

**Key rule:** No discussion yet. Write in silence.

### Step 4: Share and Compile

Go around the room. Each person shares their disaster scenario.

Document all threats identified:
- Technical failures
- Human factors
- External events
- Organizational issues
- Resource problems
- Timing issues
- Competitor actions
- Customer/user reactions

### Step 5: Categorize Threats

Group the identified threats:

| Category | Threats | Likelihood | Impact |
|----------|---------|------------|--------|
| Technical | | | |
| People/Team | | | |
| External | | | |
| Resources | | | |
| Timing | | | |
| Assumptions | | | |

### Step 6: Address Each Category

For each significant threat:
1. Is this a reason to abandon the plan?
2. Can we mitigate this risk? How?
3. What would be an early warning sign?
4. Who should monitor for this?

### Step 7: Revise the Plan

Based on the premortem findings:
- What changes should we make?
- What contingencies should we add?
- What assumptions should we validate first?
- What monitoring should we put in place?

## Why It Works

**Overcomes groupthink:** Once a decision appears made, public doubts are suppressed. The premortem legitimizes dissent.

**Unleashes imagination:** Asking "why did this fail?" is easier than "what might go wrong?" The future-past framing activates different thinking.

**Uses WYSIATI against itself:** Imagining failure makes failure scenarios available to System 1.

**Gives permission to voice concerns:** People who have doubts can express them without appearing disloyal.

## Output Template

```
## Premortem: [Plan Name]

### The Plan
[Brief description of what we're committing to]

### Disaster Scenarios Identified

#### Scenario 1: [Name]
- What happened: [Description of the failure]
- Why: [Root cause]
- Warning signs we missed: [What we should have noticed]
- Prevention/Mitigation: [What we can do about it]

#### Scenario 2: [Name]
...

### Key Threats Summary

| Threat | Likelihood | Impact | Mitigation | Early Warning |
|--------|------------|--------|------------|---------------|
| | | | | |

### Plan Revisions
[Changes to the plan based on premortem findings]

### Monitoring Plan
[What to watch for and who is responsible]
```

## Common Failure Modes in Premortems

1. **Not taking it seriously:** People write generic failures instead of engaging deeply
2. **Groupthink persists:** Dominant voices shape even the "disaster" scenarios
3. **No follow-through:** Insights are documented but not acted upon
4. **Too late:** Plan is already committed; premortem becomes performative

## Tips for Effective Premortems

- Do it before final commitment
- Ensure psychological safety
- Include people with different perspectives
- Reward the best disaster scenarios
- Actually change the plan based on findings
- Keep the documentation for post-project review
