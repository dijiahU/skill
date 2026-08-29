# Executive Communication Guide

Techniques for communicating effectively with senior leadership: business impact framing, brevity, and getting decisions made.

## Understanding Executives

### What They Care About

1. **Business outcomes:** Revenue, cost, risk, growth, competitive position
2. **Strategic alignment:** Does this support company goals?
3. **Resource allocation:** Is this worth the investment?
4. **Risk management:** What could go wrong?
5. **Timeline:** When will we see results?

### What They Don't Need

1. Technical implementation details (unless they ask)
2. Extensive background (get to the point)
3. Hedging and excessive caveats
4. Problems without solutions
5. Decisions they shouldn't be making

### Their Constraints

- **Time:** They have many competing priorities
- **Context switching:** They're jumping between topics all day
- **Incomplete information:** They rely on others to synthesize
- **Accountability:** They're responsible for outcomes

## The BLUF Principle

### Bottom Line Up Front

Always lead with the conclusion, recommendation, or ask. Then provide supporting context.

### Standard Structure

```text
1. BLUF: [The key message in one sentence]
2. Context: [Why this matters now - 2-3 sentences max]
3. Recommendation: [What you suggest]
4. Ask: [What you need from them]
5. Details: [Available if they want more]
```

### Example: Project Status

**Bad (buried lead):**
> "The team has been working on the payment integration for the past sprint. We encountered some API compatibility issues with the vendor's system, and their documentation was outdated. After some back-and-forth with their support team, we were able to identify a workaround. Testing is progressing well, though we did find some edge cases. Overall, we might need a bit more time..."

**Good (BLUF):**
> "**Summary:** Payment integration launch moving from Feb 1 to Feb 15. Root cause identified and resolved; new date is firm.
>
> **Impact:** Delayed revenue by 2 weeks, ~$50K. No customer commitments affected.
>
> **No action needed** unless you have questions."

### Example: Decision Request

**Bad (no clear ask):**
> "We've been looking at different approaches for the infrastructure migration. There are pros and cons to each option. AWS has better tooling, but Azure has better enterprise contracts. GCP might work too. The team is split on preferences..."

**Good (BLUF):**
> "**Request:** Approve AWS as our cloud provider.
>
> **Why AWS:** Best fit for our technical stack, 20% lower cost for our workload, team has most experience.
>
> **Trade-off:** Azure has better enterprise contract terms, but technical fit outweighs ($30K/year difference).
>
> **Ask:** Decision by Friday to maintain migration timeline."

## Business Impact Framing

### The Impact Formula

Every technical decision should be translatable to:

```text
[Action] → [Outcome] → [Business Metric]
```

### Common Business Metrics

| Category | Metrics |
| -------- | ------- |
| Revenue | Sales, conversion rate, average order value, churn |
| Cost | Infrastructure, development time, operational overhead |
| Risk | Security incidents, compliance violations, downtime |
| Speed | Time to market, development velocity, response time |
| Quality | Customer satisfaction, bug rate, support tickets |
| Growth | User acquisition, market expansion, capacity |

### Translation Examples

| Technical | Business Impact |
| --------- | --------------- |
| "Improve API response time by 200ms" | "Increase conversion by 1% (~$X/year)" |
| "Migrate to cloud" | "Reduce infrastructure costs by 30% (~$X/year)" |
| "Add automated testing" | "Reduce production bugs by 50%, saving X support hours" |
| "Upgrade framework" | "Maintain security compliance; avoid breach risk" |
| "Refactor codebase" | "Enable 2x faster feature development" |

### Quantify When Possible

Executives respond to numbers. Even rough estimates are better than vague claims.

| Vague | Quantified |
| ----- | ---------- |
| "This will be faster" | "This reduces load time from 3s to 1s" |
| "Improves reliability" | "Reduces outages from monthly to quarterly" |
| "Saves time" | "Saves 10 hours/week of manual work" |
| "Some risk" | "20% probability of 2-day delay" |

## Brevity Techniques

### The One-Pager Rule

If it's for an executive, it should fit on one page. If you need more detail, use appendices.

### Word Economy

| Wordy | Concise |
| ----- | ------- |
| "At this point in time" | "Now" |
| "Due to the fact that" | "Because" |
| "In order to" | "To" |
| "It is important to note that" | [Delete - just state it] |
| "There are several factors that" | "Several factors" |

### Sentence Structure

- Lead with the subject
- Use active voice
- One idea per sentence
- Cut qualifying phrases when possible

| Before | After |
| ------ | ----- |
| "It was determined by the team that we should..." | "We recommend..." |
| "There are three options that should be considered" | "Three options:" |
| "Due to various factors, it appears that..." | "[State the conclusion]" |

### Information Hierarchy

1. **Must know:** Put first
2. **Should know:** Include if space permits
3. **Nice to know:** Move to appendix or omit

## Common Executive Communication Scenarios

### Status Updates

**Format:**

```markdown
## [Project] - [Date]

**Status:** 🟢 On Track | 🟡 At Risk | 🔴 Blocked

**Key Updates:**
- [Most important update]
- [Second most important]

**Risks/Blockers:** [If any]

**Decisions Needed:** [If any]
```

### Escalations

**Format:**

```markdown
**Issue:** [One sentence: what's wrong]

**Impact:** [Business impact if not resolved]

**Root Cause:** [Brief - one sentence]

**Options:**
1. [Option A]: [Outcome, trade-off]
2. [Option B]: [Outcome, trade-off]

**Recommendation:** [Which option and why]

**Ask:** [What you need from them]

**Timeline:** [When decision is needed]
```

### Budget Requests

**Format:**

```markdown
**Request:** [Amount] for [Purpose]

**Business Case:** [ROI or strategic value]

**Alternatives Considered:** [Why this is the best option]

**Timeline:** [When funds needed, expected return]

**Risk if Not Approved:** [What happens without this]
```

### Strategy Proposals

**Format:**

```markdown
**Proposal:** [One-sentence summary]

**Strategic Alignment:** [How this supports company goals]

**Expected Outcome:** [What success looks like]

**Investment Required:** [Cost, time, resources]

**Risks:** [What could go wrong, mitigation]

**Recommendation:** [Your position]

**Ask:** [Decision or approval needed]
```

## Presenting to Executives

### Before the Meeting

1. **Know your ask:** What decision or action do you need?
2. **Anticipate questions:** Prepare answers to likely challenges
3. **Prepare backup slides:** Have details ready if asked
4. **Know their priorities:** Align message with their concerns
5. **Time it right:** Don't bring big asks when they're distracted

### During the Meeting

1. **Start with BLUF:** Don't build suspense
2. **Watch the room:** Adjust if you're losing them
3. **Pause for questions:** Don't plow through
4. **Stay calm under challenge:** It's just inquiry, not attack
5. **Take notes on asks:** Capture action items

### After the Meeting

1. **Send summary:** Confirm decisions and next steps
2. **Follow through:** Do what you said you'd do
3. **Close the loop:** Report back on outcomes

## Executive Communication Anti-Patterns

### The Information Dump

**Problem:** Providing all information and expecting them to find what's relevant.

**Fix:** Curate. You are the filter. Give them what they need.

### The Hedge Fest

**Problem:** "It might be that perhaps we could consider..."

**Fix:** Take a position. You can acknowledge uncertainty while still recommending.

### The Problem Without Solution

**Problem:** "Here's what's broken. Any ideas?"

**Fix:** Always bring options. Even if you're unsure, propose something.

### The Surprise

**Problem:** First mention of a problem is in a big meeting.

**Fix:** No surprises. Pre-wire important stakeholders.

### The Detail Spiral

**Problem:** Getting pulled into technical weeds when asked a question.

**Fix:** Answer the business question. Offer technical follow-up separately.

## Building Executive Trust

### Consistency

- Deliver on commitments
- Be reliable in communication cadence
- Maintain quality over time

### Transparency

- Share bad news early
- Don't hide problems
- Acknowledge mistakes

### Competence

- Be prepared
- Know your area deeply
- Provide good judgment, not just information

### Brevity

- Respect their time
- Get to the point
- Don't repeat yourself
