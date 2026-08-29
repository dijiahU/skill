# Bias Check Workflow

Systematically check a decision, plan, or judgment for common cognitive biases.

## When to Use

- Before finalizing an important decision
- When reviewing a plan or proposal
- When a judgment feels too confident
- When something seems too good to be true

## Getting Started

Before running through the bias checklist, use the `AskUserQuestion` tool to gather essential context:

1. **What decision or judgment needs checking?** Get a clear statement of what's being evaluated.
2. **What's at stake?** Understand the significance to calibrate depth of analysis.
3. **What information is available?** Identify what data, estimates, or reasoning they've already done.
4. **Any known concerns?** The user may already suspect specific biases.

This information shapes which checks to prioritize and how to interpret findings.

## The Process

### Step 1: State the Decision Clearly

Write out exactly what is being decided or judged. Be specific.

> "We believe [X] and plan to do [Y] because [Z]."

### Step 2: Check for Substitution

**Question:** What was the actual question we needed to answer?

**Check:** Did we answer that question, or a related but easier one?

Common substitutions:
- "Should we hire this person?" → "Did they interview well?"
- "Is this project viable?" → "Do we like the idea?"
- "Is this risk significant?" → "Can I imagine it happening?"

### Step 3: Check for WYSIATI

**Question:** What information is missing?

Make two lists:
1. Information we have
2. Information we don't have but would be relevant

**Red flag:** If the decision feels obvious based on limited information.

### Step 4: Check Base Rates

**Question:** What happens to similar decisions/projects/plans?

- What is the reference class?
- What are the success/failure rates for that class?
- Are we treating our case as special without justification?

### Step 5: Check for Anchoring

**Question:** Where did our initial estimates come from?

- Did someone propose an initial number?
- Was there an available comparison?
- Would our estimate be different with a different starting point?

### Step 6: Check for Availability Bias

**Question:** Are we overweighting vivid, recent, or personally experienced events?

- What made certain examples come to mind?
- Are there equally relevant examples that are harder to recall?
- Is recent news or personal experience skewing our assessment?

### Step 7: Check for Affect Heuristic

**Question:** Are we conflating liking with probability?

- Do we like the people/company/idea involved?
- Are we underweighting risks because we're enthusiastic?
- Are we overweighting risks because we dislike something?

### Step 8: Check for Overconfidence

**Question:** How confident are we, and is that confidence justified?

- What is our confidence level?
- What evidence supports that confidence?
- What would have to be true for us to be wrong?

**Calibration check:** If we're 80% confident, we should be wrong 20% of the time. Is our track record consistent with this?

### Step 9: Check for Planning Fallacy

**Question:** Are our time/cost/effort estimates realistic?

- What did similar projects take?
- What could go wrong?
- Have we anchored on best-case scenarios?

### Step 10: Synthesize Findings

List the biases identified and their likely impact:

| Bias | Evidence | Impact on Decision |
|------|----------|-------------------|
| [Bias name] | [What suggests this bias] | [How it affects the decision] |

### Step 11: Adjust and Decide

- For each identified bias, consider how the decision changes if you correct for it
- Determine if the decision still makes sense
- Document the reasoning for future reference

## Output Template

```
## Bias Check: [Decision Name]

### Decision Statement
[Clear statement of what is being decided]

### Biases Identified

#### [Bias 1]
- Evidence: [What suggests this bias is present]
- Impact: [How it might be affecting the decision]
- Adjustment: [How the decision changes if corrected]

#### [Bias 2]
...

### Revised Assessment
[How the decision looks after accounting for biases]

### Recommendation
[What to do next]
```
