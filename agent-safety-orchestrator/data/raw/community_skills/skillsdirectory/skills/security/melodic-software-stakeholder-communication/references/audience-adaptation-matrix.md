# Audience Adaptation Matrix

Complete communication tactics organized by audience type, situation, and channel.

## The Four Primary Audiences

### Engineers (Technical Peers)

**What they value:**

- Technical accuracy and depth
- Honest assessment of trade-offs
- Implementation details that affect their work
- Respect for their expertise

**Communication characteristics:**

| Aspect | Approach |
| ------ | -------- |
| Depth | High - they want details |
| Jargon | Use freely - it's efficient |
| Uncertainty | Express openly - they appreciate honesty |
| Diagrams | Architecture, sequence, data flow |
| Format | Technical docs, code comments, PRs |

**Effective phrases:**

- "Here's the trade-off we're making..."
- "The technical constraint is..."
- "I'd value your input on..."
- "The implementation approach is..."

**Ineffective phrases:**

- "You don't need to worry about..."
- "Just trust me on this..."
- "It's too complicated to explain..."
- "The business decided..."

**Channel preferences:**

1. Code reviews and PRs (for implementation)
2. Technical design docs (for decisions)
3. Slack/chat (for quick questions)
4. Architecture meetings (for significant changes)

### Product Managers

**What they value:**

- Understanding of user impact
- Clear trade-offs they can reason about
- Realistic timelines they can plan around
- Partnership, not just service

**Communication characteristics:**

| Aspect | Approach |
| ------ | -------- |
| Depth | Medium - enough to make decisions |
| Jargon | Translate to user/business terms |
| Uncertainty | Frame as options with trade-offs |
| Diagrams | User flows, feature comparisons |
| Format | Feature specs, roadmap updates, 1:1s |

**Effective phrases:**

- "Here are the options and trade-offs..."
- "This affects users because..."
- "If we do X, it enables Y but delays Z..."
- "What's most important for this release?"

**Ineffective phrases:**

- "That's technically impossible" (without alternatives)
- "It'll be done when it's done"
- "You wouldn't understand the complexity"
- "Engineering decided..."

**Channel preferences:**

1. 1:1 meetings (for planning and trade-offs)
2. Shared documents (for specs and requirements)
3. Sprint/planning meetings (for commitments)
4. Slack (for quick status checks)

### Executives (Leadership)

**What they value:**

- Business impact and strategic alignment
- Clear recommendations (not just options)
- Confidence and decisiveness
- Efficient use of their time

**Communication characteristics:**

| Aspect | Approach |
| ------ | -------- |
| Depth | Low - high-level unless asked |
| Jargon | Avoid entirely or translate immediately |
| Uncertainty | Present as risk with mitigation |
| Diagrams | Business metrics, timelines, org charts |
| Format | Executive summaries, dashboards, brief updates |

**Effective phrases:**

- "The bottom line is..."
- "I recommend X because..."
- "This impacts [revenue/customers/timeline] by..."
- "I need a decision on..."

**Ineffective phrases:**

- "It's complicated..."
- "We're not sure yet..."
- "There are many factors..."
- Technical jargon of any kind

**Channel preferences:**

1. Brief email summaries (async preferred)
2. Short scheduled meetings (decision-focused)
3. Dashboards (for ongoing visibility)
4. Escalation paths (for urgent issues)

### Customers (External)

**What they value:**

- Reliability and trust
- Clear, honest communication
- Understanding of their needs
- Professional, respectful treatment

**Communication characteristics:**

| Aspect | Approach |
| ------ | -------- |
| Depth | Low - focus on what they need |
| Jargon | Never - plain language only |
| Uncertainty | Acknowledge but reassure |
| Diagrams | Simple, benefit-focused |
| Format | Clear emails, status pages, documentation |

**Effective phrases:**

- "Here's what this means for you..."
- "You don't need to do anything..."
- "We're working to resolve this..."
- "Thank you for your patience..."

**Ineffective phrases:**

- Internal technical terms
- Blame or excuses
- "It's not our fault..."
- Vague timelines

**Channel preferences:**

1. Official communication channels (email, in-app)
2. Status pages (for incidents)
3. Documentation (for self-service)
4. Support tickets (for individual issues)

## Secondary Audiences

### Finance/Accounting

**Focus on:** Cost, budget, ROI, compliance, audit trails

**Translate:** Technical decisions → Financial impact

**Example:** "Cloud migration" → "Reduces infrastructure costs by $X/year with $Y one-time investment"

### Legal/Compliance

**Focus on:** Risk, liability, regulatory requirements, documentation

**Translate:** Technical capabilities → Compliance posture

**Example:** "Data encryption" → "Meets SOC 2 and GDPR requirements for data protection"

### HR/People Operations

**Focus on:** Team impact, hiring needs, skills, culture

**Translate:** Technical decisions → People implications

**Example:** "Adopting new framework" → "Requires training investment; expands hiring pool by 30%"

### Sales/Business Development

**Focus on:** Customer value, competitive advantage, timeline to value

**Translate:** Technical features → Selling points

**Example:** "Real-time sync" → "Customers see updates instantly; competitors have 5-minute delay"

### Marketing

**Focus on:** Story, differentiation, customer benefit, timing

**Translate:** Technical capabilities → Marketing messages

**Example:** "ML-based recommendations" → "Personalized experience that learns your preferences"

## Situation-Based Adaptation

### Delivering Good News

| Audience | Lead with | Include |
| -------- | --------- | ------- |
| Engineers | What was accomplished technically | Lessons learned, metrics |
| PMs | Feature delivered, user impact | Timeline for rollout |
| Executives | Business outcome | Credit to team |
| Customers | Benefit to them | How to use it |

### Delivering Bad News

| Audience | Lead with | Include |
| -------- | --------- | ------- |
| Engineers | What happened (honestly) | Root cause, prevention plan |
| PMs | Impact and timeline change | Options and trade-offs |
| Executives | Impact and mitigation | Recommendation, ask |
| Customers | What happened, what we're doing | Reassurance, timeline |

### Requesting Resources

| Audience | Lead with | Include |
| -------- | --------- | ------- |
| Engineers | Technical need | How it helps them |
| PMs | Roadmap impact | Trade-offs if not granted |
| Executives | Business case, ROI | Clear ask, alternatives |
| Customers | N/A | N/A |

### Explaining Delays

| Audience | Lead with | Include |
| -------- | --------- | ------- |
| Engineers | What's blocking | What help is needed |
| PMs | New timeline, impact | Options to reduce scope |
| Executives | New date, business impact | Mitigation, confidence level |
| Customers | New expectation | Apology, value still coming |

## Channel Effectiveness Matrix

| Channel | Best For | Avoid For |
| ------- | -------- | --------- |
| Email | Formal updates, decisions, records | Urgent issues, complex discussions |
| Slack/Chat | Quick questions, informal updates | Important decisions, sensitive topics |
| Video Call | Complex discussions, relationship building | Simple updates, one-way info |
| Document | Detailed specs, reference material | Time-sensitive communication |
| In-Person | Difficult conversations, brainstorming | Simple updates |

## Combining Audiences

When communicating to mixed audiences:

1. **Create layers:** Executive summary + detailed sections
2. **Use progressive disclosure:** High-level first, details available
3. **Segment when possible:** Separate communications if needs differ significantly
4. **Acknowledge differences:** "For those who want technical details, see appendix"

**Example layered document:**

```markdown
# [Title]

## Executive Summary (Executives)
[1-2 paragraphs: outcome, recommendation, ask]

## Overview (PMs, Leads)
[Context, options, trade-offs, timeline]

## Technical Details (Engineers)
[Implementation approach, architecture, constraints]

## Appendix
[Supporting data, detailed analysis]
```
