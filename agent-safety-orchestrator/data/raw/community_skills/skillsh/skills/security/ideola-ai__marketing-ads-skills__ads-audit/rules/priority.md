# Priority Framework

System for ranking issues and actions by business impact.

## Impact Levels

### Critical (Business Impact >$1000/week or Brand Risk)
**Definition:** Issues causing immediate revenue loss or brand damage.

**Criteria:**
- Wasting >$1000/week on non-converting spend
- ROAS <0.5 (losing money directly)
- Broken landing pages (100% conversion loss)
- Policy violations (account at risk)
- Data not recording (flying blind)

**Action SLA:** Fix within 24 hours

**Examples:**
- Campaign spending $2000/week with ROAS 0.3
- Landing page 404 error on top spending campaign
- CAPI not firing (100% data loss on iOS)
- Ads disapproved for policy violation

---

### High (Business Impact $100-1000/week)
**Definition:** Significant but not existential revenue loss.

**Criteria:**
- Wasting $100-1000/week
- ROAS 0.5-1.0 (breaking even or losing)
- CPA 2x+ target
- Top spending campaign paused or limited
- Creative fatigued (missing 50%+ potential)

**Action SLA:** Fix within 1 week

**Examples:**
- Best performer fatigued (frequency 6+)
- CPA $60 vs $25 target
- Budget not spending (leaving 40% on table)
- Low relevance score causing 50% higher CPC

---

### Medium (Business Impact $10-100/week)
**Definition:** Noticeable inefficiency but not urgent.

**Criteria:**
- Wasting $10-100/week
- ROAS 1.0-2.0 (below target but profitable)
- CPA 1.2-2x target
- Single ad set or creative underperforming
- Minor targeting issues

**Action SLA:** Fix within 2-4 weeks

**Examples:**
- One placement underperforming
- Single ad set high CPA
- Small audience missing opportunities
- Could improve but not critical

---

### Low (Business Impact <$10/week)
**Definition:** Minor optimizations.

**Criteria:**
- Wasting <$10/week
- ROAS at/above target
- CPA at or below target
- Nice-to-have improvements

**Action SLA:** Backlog as capacity allows

**Examples:**
- Expand ad copy variations
- Test new audience segments
- Creative refresh (not fatigued)

---

## Effort Levels

### Low (Developer/Designer <2 hours)
**Examples:**
- Add negative keywords
- Pause ad/campaign
- Increase budget by percentage
- Simple bid adjustment
- Copy edit to existing ad

### Medium (Developer/Designer 2-8 hours)
**Examples:**
- Create new ad creative
- Landing page copy changes
- Audience refinement
- Conversion tracking fix
- Form field reduction

### High (Developer/Designer >8 hours or Dev Team)
**Examples:**
- Landing page redesign
- Conversion tracking reimplementation
- Full campaign rebuild
- Pixel/CAPI migration
- Major creative production

---

## Priority Matrix

| Impact / Effort | Low | Medium | High |
|------------------|-----|--------|------|
| **Critical** | 🔴 Immediate | 🔴 This Week | 🔴 This Sprint |
| **High** | 🟡 This Week | 🟡 This Week | 🟡 Next Sprint |
| **Medium** | 🟡 Next Sprint | 🟡 Next Sprint | 🟡 Backlog |
| **Low** | ⬜ Backlog | ⬜ Backlog | ⬜ Backlog |

---

## Quick Prioritization Rules

### Rule 1: Bleeding > Fixing
If ROAS <0.5 (losing money on ad spend):
- **Priority:** Critical
- **Action:** Pause immediately or fix creative/landing
- **Exception:** Only continue if test/negotiation phase with clear learning goal

### Rule 2: Broken Tracking > All Else
If conversions not tracking:
- **Priority:** Critical
- **Reason:** Flying blind, can't optimize anything
- **Action:** Fix tracking before any other work

### Rule 3: Fatigue First
If creative fatigued (high frequency, declining CTR):
- **Priority:** High
- **Action:** Pause fatigued creative before other optimizations
- **Reason:** Wasting budget on burned audience

### Rule 4: Quick Wins Before Deep Work
Before starting medium/high effort projects:
1. Pause worst 20% by ROAS (5 min)
2. Add obvious negative keywords (15 min)
3. Increase budget on winners by 20% (5 min)
4. Fix broken links (10 min)

**Expected:** 15-30% improvement in 1 hour with low effort

### Rule 5: Test Before Scaling
Never scale budget until:
- [ ] ROAS at/above target for 2 weeks
- [ ] Stable performance (not volatile)
- [ ] Conversion tracking verified
- [ ] Creative freshness confirmed

---

## Decision Framework for Each Issue

### Question 1: What's the Weekly Financial Impact?
```
Weekly Impact = (Current ROAS - Target ROAS) × Weekly Spend
```

| Weekly Impact | Priority |
|---------------|----------|
| >$1000 | Critical |
| $100-1000 | High |
| $10-100 | Medium |
| <$10 | Low |

### Question 2: How Quick to Implement?
| Time to Implement | Priority Modifier |
|------------------|---------------------|
| <1 day | No modifier |
| 1-3 days | High → Medium if impact <$100 |
| >1 week | High → Medium if impact <$500 |
| >1 month | Consider ROI |

### Question 3: What's the Risk of Not Doing?
| Risk | Priority Modifier |
|------|---------------------|
| Account suspension | Critical regardless of effort |
| Brand damage | Critical regardless of effort |
| Continuing loss | High if >$500/week |
| Missed opportunity | No modifier |

### Question 4: Does This Block Other Work?
| Blocks | Priority Modifier |
|--------|---------------------|
| Yes, blocks optimizations | +1 priority level |
| Yes, blocks scaling | +1 priority level |
| No blocking | No modifier |

---

## Action Item Template

```
## [Issue Title]

**Priority:** [Critical/High/Medium/Low]
**Impact:** $[amount]/week (or [description])
**Effort:** [Low/Medium/High] - [estimated hours]
**Owner:** [Name]
**Due:** [Date]

### Problem
[Describe the issue clearly]

### Root Cause
[From diagnosis]

### Solution
[Specific steps to fix]

### Expected Outcome
- Before: [Current metric]
- After: [Expected metric]
- Impact: [Quantified improvement]

### Dependencies
- [ ] Blocked by [other item]
- [ ] Blocks [other item]
```

---

## Example Prioritizations

### Example 1: Broken Landing Page
```
## Fix 404 on Best Sellers Campaign

**Priority:** Critical
**Impact:** $2,500/week (100% conv loss on top campaign)
**Effort:** Low - 0.5 hours (redirect URL)
**Owner:** Dev Team
**Due:** Today

### Problem
Best Sellers campaign landing page returns 404 error

### Root Cause
Page deleted during site migration

### Solution
1. Redirect to working homepage (temporary)
2. Restore landing page permanently

### Expected Outcome
- Before: 0 conversions, $5,000/week wasted
- After: 75 conversions/week, 3.5 ROAS
- Impact: +$2,500/week

### Dependencies
- [ ] Blocked by Dev Team availability
```

### Example 2: Creative Fatigue
```
## Refresh Summer Sale Creative

**Priority:** High
**Impact:** $800/week (CTR down 60%, frequency 7.2)
**Effort:** Medium - 3 hours (new creative production)
**Owner:** Design Team
**Due:** This Friday

### Problem
Summer Sale ads fatigued - CTR declined from 2.8% to 1.1%, frequency at 7.2 per user

### Root Cause
Same 3 creatives running for 6 weeks

### Solution
1. Pause fatigued ads (immediate)
2. Produce 3 new variations
3. Launch new creative by Friday

### Expected Outcome
- Before: 1.1% CTR, $65 CPA
- After: 2.2% CTR, $40 CPA
- Impact: +$800/week

### Dependencies
- [ ] Blocked by Design Team
- [ ] Blocks budget increase decision
```

### Example 3: Negative Keywords
```
## Add Free Software Negatives

**Priority:** Medium
**Impact:** $150/week (wasted clicks on non-buyers)
**Effort:** Low - 0.5 hours
**Owner:** PPC Manager
**Due:** Tomorrow

### Problem
Search terms "free", "freeware", "open source" triggering software ads

### Root Cause
No negative keywords for non-intent searches

### Solution
Add negative: free, freeware, open source, torrent, crack

### Expected Outcome
- Before: 1.8% CTR, $42 CPA
- After: 2.4% CTR, $35 CPA
- Impact: +$150/week

### Dependencies
None
```
