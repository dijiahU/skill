# Ads Audit Workflow

Step-by-step procedure for conducting comprehensive ad campaign audits.

## Phase 1: Data Collection (5-10 minutes)

### Step 1.1: Define Audit Scope
- [ ] Determine platforms to audit (Google, Meta, TikTok, LinkedIn, Microsoft)
- [ ] Set date range (minimum 2 weeks, ideally 4 weeks)
- [ ] Identify campaign objectives (awareness, traffic, leads, sales)

### Step 1.2: Gather Required Metrics
| Metric | Where to Find | Minimum Required |
|--------|---------------|-------------------|
| Spend | Campaign level | Total by campaign |
| Impressions | Ad set level | Total + breakdown |
| Clicks | Ad set level | Total + breakdown |
| Conversions | Ad level | Total + value |
| Reach | Campaign level | Total |
| Frequency | Campaign level | Average per user |

### Step 1.3: Export Account Structure
- [ ] Campaign names and objectives
- [ ] Ad set targeting parameters
- [ ] Ad creative inventory (count by type)
- [ ] Active audiences and exclusions

**Check:** If any data is missing or inaccessible, flag as blocker.

---

## Phase 2: Performance Analysis (10-15 minutes)

### Step 2.1: Calculate Core KPIs
For each campaign, calculate:

```
CTR = (Clicks / Impressions) × 100
CPC = Spend / Clicks
Conversion Rate = (Conversions / Clicks) × 100
CPA = Spend / Conversions
ROAS = Revenue / Spend
Frequency = Impressions / Reach
```

### Step 2.2: Compare to Benchmarks
See [references/benchmarks.md](../references/benchmarks.md)

For each metric:
1. Find platform/industry benchmark
2. Calculate gap: (Actual - Benchmark) / Benchmark
3. Flag if gap > 30% in either direction

### Step 2.3: Identify Red Flags
| Metric | Red Flag Threshold | Action |
|--------|---------------------|--------|
| CTR vs Benchmark | Below -50% | Critical |
| CPA vs Target | Above +100% | Critical |
| Frequency | >5 per week | High |
| ROAS | <1.0x | Critical |
| Quality Score | <5/10 | High |
| Delivery Underspend | <80% | High |

### Step 2.4: Score Campaign Health
For each campaign, assign score 1-10:

| Score | Criteria |
|-------|----------|
| 9-10 | All metrics green, ROAS at/above target |
| 7-8 | Minor gaps, ROAS within 80% of target |
| 5-6 | Some red flags, ROAS 50-80% of target |
| 3-4 | Multiple red flags, ROAS below 50% |
| 1-2 | Critical issues, ROAS <1.0x |

---

## Phase 3: Issue Diagnosis (15-20 minutes)

### Step 3.1: Creative Issues Checklist
For bottom 20% spending ads by creative:

| Issue | Symptom | Check |
|-------|---------|-------|
| Ad fatigue | Frequency >4, CTR declining | [ ] |
| Poor creative | Low relevance/quality score | [ ] |
| Format mismatch | Vertical creative on horizontal | [ ] |
| Weak copy | No hook, unclear CTA | [ ] |
| Low diversity | <3 creative variations | [ ] |

**Action:** Document specific creative elements causing issues.

### Step 3.2: Targeting Issues Checklist
For each ad set:

| Issue | Symptom | Check |
|-------|---------|-------|
| Too narrow | Audience <100K, limited delivery | [ ] |
| Too broad | Audience >10M, low CTR | [ ] |
| Missing exclusions | Converted users still seeing ads | [ ] |
| Overlap | Multiple ad sets targeting same | [ ] |
| Wrong placements | Low-performing placements active | [ ] |

**Action:** Map specific targeting parameters to fix.

### Step 3.3: Budget/Bidding Issues Checklist
For each campaign:

| Issue | Symptom | Check |
|-------|---------|-------|
| Budget too low | Learning phase never completes | [ ] |
| Wrong strategy | Cost cap on awareness campaign | [ ] |
| No bid control | High CPA on auto-bid | [ ] |
| Underdelivery | Spend <80% of budget | [ ] |
| Overdelivery | Spend >110% without approval | [ ] |

**Action:** Document bid/budget changes needed.

### Step 3.4: Technical Issues Checklist
| Issue | How to Check | Check |
|-------|--------------|-------|
| Broken links | Test each ad URL | [ ] |
| Slow LP | Load time >3s on mobile | [ ] |
| Pixel not firing | Test conversion event | [ ] |
| Mobile issues | View on mobile device | [ ] |
| Policy violations | Check ad status | [ ] |

**Action:** List technical fixes with priority.

---

## Phase 4: Recommendations (10 minutes)

### Step 4.1: Categorize by Impact/Effort
For each identified issue, assign:

| Impact | Effort | Priority |
|--------|--------|----------|
| High | Low | Immediate (today) |
| High | Medium | This week |
| High | High | Next sprint |
| Medium | Low | This week |
| Medium | Medium | Backlog |
| Low | Any | Skip |

### Step 4.2: Generate Action Items
Create specific, actionable items:

**Format:** `[ ] [Action] - Campaign: [Name] - Expected: [Outcome]`

Examples:
- [ ] Pause ad "Summer Sale 2024" - Campaign: Retargeting - Expected: Save $500/week
- [ ] Increase budget on "Best Sellers" to $100/day - Campaign: Sales - Expected: +20% conversions
- [ ] Add negative keyword "free" - Campaign: Search - Expected: +15% CTR

### Step 4.3: Identify A/B Tests
See [references/testing.md](../references/testing.md)

Priority order:
1. High-impact, low-effort tests first
2. Winner vs. challenger creative tests
3. Audience expansion tests
4. Bid strategy tests

---

## Phase 5: Output Delivery (5 minutes)

### Step 5.1: Create Audit Report
Use template in SKILL.md:

```markdown
# [Platform] Ads Audit Report
Date: [Date]
Auditor: [Name]
Period: [Date range]

## Executive Summary
- Overall Score: X/10
- Total Spend: $X
- Total ROAS: X.x
- Key Finding: [Top insight]
- Quick Impact Potential: [Estimated improvement]

## Campaign Health Scores
| Campaign | Score | ROAS | Status |
|----------|-------|------|--------|
| [Name] | 8/10 | 3.2x | Healthy |
| [Name] | 4/10 | 1.1x | Critical |

## Issues by Priority
### Critical (Fix Today)
1. [Issue] - Campaign: [Name] - Impact: $X/week
2. [Issue] - Campaign: [Name] - Impact: $X/week

### High (Fix This Week)
1. [Issue] - Campaign: [Name]
2. [Issue] - Campaign: [Name]

## Action Items
- [ ] [Action 1] - Owner: [Name] - Due: [Date]
- [ ] [Action 2] - Owner: [Name] - Due: [Date]

## A/B Tests to Run
- [ ] [Test idea] - Hypothesis: [Expected outcome]
```

### Step 5.2: Schedule Follow-up
- [ ] Schedule review meeting in 1 week
- [ ] Set calendar reminder for action item due dates
- [ ] Create tracking for A/B test results
