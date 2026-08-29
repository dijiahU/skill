---
name: stakeholder-communication
description: Adapting technical communication for different audiences - engineers, product managers, executives, and customers. Use when communicating across functions, translating technical concepts, presenting to leadership, or building shared understanding with non-technical stakeholders.
allowed-tools: Read, Glob, Grep
---

# Stakeholder Communication Skill

A framework for adapting technical communication to different audiences, ensuring your message lands effectively whether speaking with engineers, product managers, executives, or customers.

## When to Use This Skill

- Presenting technical decisions to non-technical stakeholders
- Writing status updates for different audience levels
- Translating complex technical concepts for business partners
- Building alignment across engineering, product, and business teams
- Communicating with executives (brevity, business impact)
- Customer-facing technical communication
- Cross-functional project coordination

## Core Framework: Audience-First Communication

### The Fundamental Question

Before any communication, ask: **"Who is my audience and what do they need?"**

Different stakeholders have different:

- **Knowledge levels:** Technical depth they can absorb
- **Decision criteria:** What matters for their decisions
- **Time constraints:** How much attention they can give
- **Action orientation:** What they need to do with this information

### The Four Audience Types

| Audience | Primary Concern | Communication Style |
| -------- | --------------- | ------------------- |
| Engineers | How it works | Technical depth, implementation details |
| Product Managers | What it does | Features, trade-offs, timeline impact |
| Executives | Why it matters | Business impact, risks, decisions needed |
| Customers | How it helps them | Benefits, reliability, trust |

## Quick Adaptation Guide

### For Engineers

**Focus on:**

- Technical architecture and design decisions
- Implementation approach and trade-offs
- Code quality, testing, and reliability
- Performance characteristics and constraints

**Avoid:**

- Over-simplified explanations (they'll feel condescended to)
- Hiding technical debt or known issues
- Vague timelines without technical justification

### For Product Managers

**Focus on:**

- Feature capabilities and limitations
- Timeline and scope trade-offs
- User impact and experience changes
- Dependencies and risks to roadmap

**Avoid:**

- Deep implementation details (unless relevant to decisions)
- Technical jargon without context
- Binary answers when trade-offs exist

### For Executives

**Focus on:**

- Business impact (revenue, cost, risk)
- Decision points requiring their input
- Progress against strategic objectives
- Resource implications

**Avoid:**

- Technical details (unless specifically asked)
- Problems without proposed solutions
- Lengthy explanations (get to the point)

### For Customers

**Focus on:**

- Benefits and value they receive
- Reliability and trust signals
- Clear, jargon-free explanations
- What they need to do (if anything)

**Avoid:**

- Internal technical details
- Blame or excuses
- Uncertainty without reassurance

## The Translation Principle

**Technical → Business Translation:**

| Technical Concept | Business Translation |
| ----------------- | -------------------- |
| "Refactoring the codebase" | "Improving system reliability and reducing future bugs" |
| "Database migration" | "Upgrading our data infrastructure for better performance" |
| "Technical debt" | "Accumulated shortcuts that slow new feature development" |
| "API rate limiting" | "Protection against system overload" |
| "Microservices architecture" | "Modular design that allows faster, independent updates" |

**The Formula:**

```text
[Technical action] → [Business benefit] + [Risk if not done]
```

Example:

- Technical: "We need to upgrade from .NET 6 to .NET 8"
- Business: "Upgrading our framework ensures continued security support and enables 20% faster response times, avoiding security vulnerabilities when .NET 6 support ends in November"

## Communication Patterns

### The Executive Summary Pattern

For any executive communication:

1. **Bottom Line Up Front (BLUF):** Lead with the conclusion or ask
2. **Context:** Minimal background needed to understand
3. **Options/Recommendation:** What you suggest and why
4. **Ask:** What you need from them

**Template:**

```markdown
**Summary:** [One sentence: what this is about and what you need]

**Context:** [2-3 sentences: why this matters now]

**Recommendation:** [What you propose]

**Ask:** [Specific decision or action needed]

**Details:** [Available if they want to dig deeper]
```

### The Cross-Functional Update Pattern

For status updates that go to mixed audiences:

1. **Progress:** What's done (accomplishments, metrics)
2. **Plans:** What's next (upcoming work, timeline)
3. **Problems:** What's blocking (issues, risks, needs)

**Template:**

```markdown
## [Project Name] Update - [Date]

### Progress
- [Accomplishment with metric or outcome]
- [Accomplishment with metric or outcome]

### Plans
- [Upcoming work] - [Target date]
- [Upcoming work] - [Target date]

### Problems
- [Issue]: [Impact] - [Proposed solution or ask]
```

### The Technical Decision Pattern

For communicating technical decisions to non-technical stakeholders:

1. **Decision:** What we decided
2. **Why:** Business rationale (not technical details)
3. **Impact:** What changes for them
4. **Timeline:** When it happens

**Template:**

```markdown
**Decision:** We're [decision].

**Why:** This [business benefit] and [risk mitigation].

**Impact:** [What they'll see/experience differently].

**Timeline:** [When this takes effect].
```

## Common Mistakes

### Mistake 1: Same Message to All Audiences

**Problem:** Sending identical communication to engineers and executives.

**Fix:** Create layered communication:

- Executive summary for leadership
- Detailed version for technical teams
- Customer-facing version if applicable

### Mistake 2: Leading with Technical Details

**Problem:** Starting with how something works before why it matters.

**Fix:** Always lead with business impact, then offer technical details for those who want them.

### Mistake 3: Assuming Shared Context

**Problem:** Using acronyms, project names, or references others don't know.

**Fix:** Define terms, provide context, link to background information.

### Mistake 4: All Problems, No Solutions

**Problem:** Escalating issues without proposed solutions.

**Fix:** Always bring options. "We have a problem" → "We have a problem. I recommend X because Y."

### Mistake 5: Binary Answers to Complex Questions

**Problem:** "Yes we can" or "No we can't" without nuance.

**Fix:** "Yes, with these trade-offs" or "Not as asked, but here's what we could do."

## References (Load When Needed)

### Detailed Frameworks

- **[Audience Adaptation Matrix](references/audience-adaptation-matrix.md)**: Complete communication tactics by audience type
- **[Technical Translation](references/technical-translation.md)**: Simplifying jargon for non-technical audiences
- **[Executive Communication](references/executive-communication.md)**: Business impact framing and brevity techniques
- **[Cross-Functional Alignment](references/cross-functional-alignment.md)**: Building shared understanding across teams

## Related Skills and Commands

- `professional-communication` skill - General communication patterns
- `difficult-conversations` skill - Challenging stakeholder discussions
- `/soft-skills:adapt-communication` command - Transform content for audience

## Example Scenarios

### Scenario 1: Explaining a Delay to Executives

```markdown
**Situation:** Feature launch delayed 2 weeks due to unexpected technical complexity.

**Bad:** "The API integration is taking longer because the third-party
documentation was incorrect and we had to reverse-engineer their
authentication flow, plus we discovered race conditions in our queue
processing that required refactoring."

**Good:** "Launch is moving to [date] - 2 weeks later than planned.
The integration was more complex than estimated based on available
documentation. We've de-risked the remaining work and are confident
in the new date. Impact: [business impact]. No action needed from you
unless you have questions."
```

### Scenario 2: Technical Update for Mixed Audience

```markdown
**Situation:** Database migration completed successfully.

**For Engineers:**
"Migration complete. 2.3M records transferred with zero data loss.
Rollback scripts tested and available. New indexes improving query
performance by 40% on high-traffic endpoints. Monitoring dashboard
updated. On-call runbook in wiki."

**For Executives:**
"Database upgrade complete. System is faster and more reliable.
No customer impact during transition. Cost savings of $X/month
from improved efficiency."

**For Customers (if applicable):**
"We've upgraded our systems to serve you better. You may notice
faster load times. No action needed on your end."
```

### Scenario 3: Requesting Resources

```markdown
**Situation:** Need additional engineer for critical project.

**Bad:** "We're behind and need help."

**Good:** "Request: 1 additional engineer for [project] through [date].

Why: Current velocity puts us 3 weeks behind [strategic goal].
Adding capacity now enables on-time delivery.

Impact of not acting: [Specific business consequence].

Recommendation: Temporarily reassign [name] from [lower-priority work].

Cost: [Lower-priority work] delayed by [X weeks].

Ask: Approve reassignment by [date] to maintain timeline."
```

## Anti-Patterns to Avoid

### In Written Communication

- **Wall of text:** Break into scannable sections
- **Buried lead:** Put the key point first
- **Jargon soup:** Define terms or use plain language
- **Missing ask:** Be clear about what you need

### In Verbal Communication

- **Monologuing:** Pause for questions and reactions
- **Defensive posture:** Be open to feedback
- **Over-explaining:** Match depth to audience interest
- **Vague commitments:** Be specific about next steps

## Success Metrics

Effective stakeholder communication achieves:

- **Understanding:** They grasp what you're saying
- **Alignment:** They agree on direction or know how to disagree
- **Action:** They can take appropriate next steps
- **Trust:** They feel informed and respected
- **Efficiency:** Neither party's time was wasted

## Version History

- v1.0.0 (2025-12-23): Initial release with audience-first framework
