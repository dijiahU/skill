# Budget & Bidding Framework (2026)

## Budget Allocation Analysis

### Cross-Channel Distribution (2026)

| Channel | B2C Allocation | B2B Allocation | Rationale |
|---------|----------------|----------------|-----------|
| Google Search | 30-40% | 40-50% | High intent capture |
| Meta (FB/IG) | 30-40% | 10-20% | Broad reach |
| TikTok/Social Video | 10-20% | 5-10% | CPM arbitrage |
| LinkedIn | 5-10% | 20-30% | B2B decision makers |
| Microsoft/Bing | 5-10% | 10-15% | Lower cost supplement |
| YouTube | 10-15% | 5-10% | Brand + consideration |

### Performance-Based Allocation

**The 70-20-10 Rule:**
- **70%** to proven performers (scale winners)
- **20%** to new tests (innovation)
- **10%** to experimental/high-risk (learning)

**Margin-Based Allocation:**
- If margin >40%: Aggressive scaling (70-20-10)
- If margin 20-40%: Moderate scaling (70-30-0)
- If margin <20%: Conservative (80-20-0)

---

## Smart Bidding Requirements (2026)

### Strategy Selection Matrix

| Goal | Best Strategy | Min Conversions | When to Use | When NOT to Use |
|------|---------------|-----------------|-------------|-----------------|
| Awareness | Maximize Clicks | 0 | Cold start, <15 conv/mo | Broad match |
| Traffic | Maximize Clicks | 0 | Driving visits, limited budget | Conversion vol >30 |
| Lead Generation | Target CPA (tCPA) | 30/mo (50+ ideal) | Have conversion history | <15 conv/mo, budget <2x target |
| E-commerce Sales | Target ROAS (tROAS) | 50/mo | Clear revenue per conversion | Homogenous value, <50 conv |
| Scaling | Maximize Conversions | 15-30/mo | Transition to tCPA, budget limited | Uncapped budget |
| Control | Manual with Bid Caps | 0 | Testing, learning phase | Broad match (dangerous) |

### tCPA Best Practices (2026)

**Initial Target Setting:**
```
Initial Target CPA = 1.1x to 1.2x × Historical 30-Day Average CPA
```

**Adjustment Protocol:**
- Max adjustment: **10% every 14 days**
- If CPA < Target (by >10%): Lower target 10%
- If CPA > Target: Raise target 10%

**Danger Signs:**
- Impressions drop >20% (target too high)
- 3 consecutive days with 0 conversions (target too high)
- Zero spend (target unreachable)

### tROAS Best Practices (2026)

**Initial Target Setting:**
```
Initial Target ROAS = Exact Historical ROAS (Last 30 Days)
```

**Scaling Protocol:**
- **To increase volume:** Lower target by 10-20%
- **To improve efficiency:** Raise target by 10-20%

**Danger Signs:**
- Zero spend (target too aggressive)
- CPA doubling from baseline (target too low)

---

## Budget Pacing Analysis (2026)

### Weekly Pacing Targets

| Week of Month | Target Spend % | Cumulative |
|---------------|----------------|------------|
| Week 1 | 22-25% | 22-25% |
| Week 2 | 22-25% | 44-50% |
| Week 3 | 22-25% | 66-75% |
| Week 4 | 25-30% | 100% |

### Pacing Issues & Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| Overspending | >100% budget spent early | Reduce daily budget 20%, add end-date caps |
| Underspending | <80% of budget utilized | Lower bids, expand audience, add placements |
| Volatile spending | Large daily fluctuations | Increase budget to 3-5x daily target |
| Late delivery | Most spend at month-end | Check delivery limits, bid caps |

---

## Scaling Framework (2026)

### The 20% Rule

**Condition:**
- CPA < Target (by >10%) **AND**
- Lost IS (Budget) >10%

**Action:**
- Increase budget by **20%**
- **WAIT 72 hours** before next increase

### The 3x Kill Rule

**Condition:**
- Spend > 3x Target CPA **AND**
- Conversions = 0

**Action:**
- Pause immediately
- Do not retry without creative/targeting changes

### Kill Logic - Quick Death

**Condition:**
- Spend > 1x Target CPA **AND**
- Clicks = 0 (or CTR <0.2%)

**Action:**
- Check technical issues (broken link, disapproval)
- Pause if technical check passes

### Incremental Spend Testing

**Question:** Does additional spend convert at same rate?

**Test Design:**
1. Establish baseline CPA at current spend
2. Increase daily budget by **20-30%**
3. Measure CPA of incremental conversions
4. If incremental CPA ≤ baseline CPA: Scale
5. If incremental CPA >1.5x baseline: Pause scaling

---

## CBO vs ABO Decision Framework (2026)

### Campaign Budget Optimization (CBO)

| Factor | Use CBO | Don't Use CBO |
|--------|---------|---------------|
| Daily Budget | >$500 | <$100 |
| Ad Sets | 3+ | <2 |
| Goal | Let AI allocate | Forced spend for testing |
| Delivery | Fair share across sets | Unequal delivery needed |

**Warning:** CBO with <$100 budget identifies false positive "early winner" and starves other ad sets.

### Ad Set Budget Optimization (ABO)

| Factor | Use ABO | Don't Use ABO |
|--------|---------|--------------|
| Daily Budget | <$100 | >$500 |
| Ad Sets | Any | >5 (fragmentation risk) |
| Goal | Creative testing, forced spend | Scaling proven winners |
| Testing | New creative concepts | Proven combinations |

**Warning:** ABO requires manual monitoring to redistribute budget from winners to losers.

---

## Learning Phase Requirements (2026)

### Platform-Specific Thresholds

| Platform | Conversions Needed | Time Period | Budget Formula |
|----------|-------------------|-------------|----------------|
| Google Search | 30-50 | 1-2 weeks | Daily = 5-7 × Target CPA |
| Google PMax | 50+ | 2 weeks | Daily = 5-7 × Target CPA |
| Meta | 50/week per ad set | 1 week | Daily = 5-7 × Target CPA |
| TikTok | 20-30 | 1 week | Daily = 3-5 × Target CPA |
| LinkedIn | 15-20 | 1-2 weeks | Daily = 5-10 × Target CPA |

**Minimum Budget Formula (Universal):**
```
Minimum Daily Budget = (Target CPA × 50) / 30 days
Simplified: Daily Budget = 1.7 × Target CPA
```

### Learning Phase Reset Triggers

Any of these actions FULLY RESET learning phase:

| Action | Reset Impact | Wait Time |
|--------|--------------|-----------|
| Budget change >20% | Full reset | 1 week |
| Targeting change | Full reset | 1 week |
| Creative edit (active ad) | Full reset | 1 week |
| Bid cap change | Full reset | 1 week |
| Bid strategy change | Full reset | 1 week |
| New ad creation (active campaign) | Partial reset | 3 days |

**Best Practice:** Make all changes at once, then wait 7 days.

---

## Budget Efficiency Metrics (2026)

### Key Metrics to Track

| Metric | Formula | Target | Red Flag |
|--------|---------|--------|----------|
| Budget utilization | Actual spend / Budget | 95-100% | <80% or >105% |
| Cost efficiency | CPA / Target CPA | <1.0 | >1.2 |
| ROAS | Revenue / Spend | >3.0 (varies) | <1.5 |
| Diminishing returns | Last 10% CPA / Overall CPA | <1.5 | >2.0 |
| MER | Total Revenue / Total Ad Spend | 3.0-5.0 | <3.0 |

### Red Flags Requiring Immediate Action

- Budget utilization <80% (money left on table)
- Budget utilization >105% (overspend risk)
- CPA doubling with 2x budget (diminishing returns)
- One campaign consuming >60% of total budget
- MER dropping below 3.0 (stop scaling)

---

## Bid Management (2026)

### Device Bid Adjustments

| Device | Typical Modifier | When to Adjust |
|--------|------------------|----------------|
| Mobile | +0% to +30% | Higher conversion rate |
| Desktop | -20% to +20% | Varies by industry |
| Tablet | -50% to -20% | Usually lower performance |

### Time-of-Day (Dayparting)

| Daypart | Typical Modifier | Use Case |
|---------|------------------|----------|
| Business hours (9-5) | +0% to +50% | B2B campaigns |
| Evening (6-10pm) | +0% to +30% | B2C campaigns |
| Late night (11pm-6am) | -50% to -100% | Most campaigns |

### Audience Bid Adjustments

| Segment | Adjustment | Rationale |
|---------|------------|-----------|
| Previous customers | +20% to +50% | Higher LTV |
| Website visitors | +10% to +30% | Proven interest |
| Lookalike 1% | +10% to +25% | High intent |
| Cold audiences | -20% to baseline | Unproven |

---

## Budget Testing Framework (2026)

### Test Budget Allocation

1. **Baseline period:** Run current allocation for 2 weeks
2. **Test period:** Shift 10-20% to new channel
3. **Measure:** Compare CPA/ROAS change
4. **Decide:** Keep shift or revert

### Seasonal Budget Planning

| Industry | Peak Season | Budget Modifier |
|----------|-------------|-----------------|
| Retail | Nov-Dec | +200-400% |
| Travel | Jan-Mar, Jun-Aug | +50-100% |
| B2B | Jan-Feb, Sep-Oct | +30-50% |
| Education | Aug-Sep | +100-200% |
| Fitness | Jan, Apr-Jun | +50-100% |

---

## Platform-Specific Budget Rules

### Google Ads

**Minimum Viable Budget:**
- $50/day minimum for learning phase
- $1,000/month recommended starting point

**Budget Pacing:**
- Use "Accelerated" for <$100/day (immediate spend)
- Use "Standard" for >$100/day (smooth delivery)

**Budget Rules:**
- Minimum ad group budget: $1/day
- Shared budgets: Allow flexibility across campaigns
- Account-level budgets: Enable for cross-campaign optimization

### Meta Ads

**Minimum Viable Budget:**
- $20/day minimum per campaign
- $20/day minimum per ad set (ABO)
- $600-800/month recommended starting point

**CBO Budget Rules:**
- Minimum total CBO budget: $100/day
- Minimum ad set budget in CBO: $1/day

**Learning Phase Budget:**
```
Minimum Daily Budget = 5-7 × Target CPA
Example: $25 Target CPA → $125-175/day minimum
```

### TikTok Ads

**Minimum Viable Budget:**
- $50/day minimum campaign budget
- $20/day minimum ad group budget
- $300/month recommended starting point

**TikTok Shop Budget:**
- Minimum campaign: $50/day
- Minimum ad group: $20/day

### LinkedIn Ads

**Minimum Viable Budget:**
- $10/day minimum per campaign
- $3,000/month recommended for meaningful results

**Budget Notes:**
- Higher costs require larger budgets
- CPM $30-40 typically
- Recommend starting at $50/day

### Microsoft Ads

**Minimum Viable Budget:**
- Scale from Google (import available)
- Typically 20-40% lower CPC than Google
- Same daily minimums as Google

---

## Advanced Bidding Strategies (2026)

### Portfolio Bid Strategies (Google)

**Use When:**
- Multiple campaigns with same goal
- Want to pool conversion data
- Simplify bid management

**Requirements:**
- All campaigns use same conversion action
- Sufficient combined conversions (50+/month)

### Bid Strategy Experiments (Meta)

**Testing Framework:**
1. Duplicate campaign (identical setup)
2. Change only bid strategy
3. Run for 2 learning cycles (14 days)
4. Compare CPA/ROAS

### Value-Based Bidding (Google tROAS)

**Use When:**
- Conversion values vary significantly
- Have 50+ value-based conversions/month
- Want to optimize for revenue, not count

**Requirements:**
- Dynamic value tracking implemented
- Value variance >3x between lowest/highest

---

## Quick Audit Checklist

- [ ] Budget allocation matches performance (80/20 rule check)
- [ ] Pacing is on track for month/quarter
- [ ] Bidding strategy aligns with campaign objective
- [ ] Learning phase complete before optimization
- [ ] Bid caps are not limiting delivery
- [ ] Budget is sufficient for scale (min 50x target CPA)
- [ ] Dayparting configured if applicable
- [ ] Device bid adjustments based on data
- [ ] Audience bid adjustments reflect value
- [ ] No campaigns severely overspending or underspending
- [ ] CBO vs ABO choice is appropriate for budget level
- [ ] 20% scaling rule followed when expanding
- [ ] 3x kill rule monitored for underperformers

---

## Common Issues & Solutions (2026)

| Issue | Root Cause | Solution |
|-------|------------|----------|
| Not spending | Budget too low, bids too low | Increase budget 2x, raise bid caps |
| Overspending | No budget caps, learning phase | Add campaign budget caps, set end dates |
| High CPA | Wrong bid strategy, low quality | Change strategy, improve creative/landing |
| Inconsistent delivery | Low budget, high competition | Raise budget to meet delivery threshold |
| Learning limited | Insufficient conversions/budget | Combine campaigns, increase budget |
| CBO early winner bias | Budget <$100 | Switch to ABO or increase budget |
| Zero delivery (tCPA) | Target too low/high | Adjust 1.1-1.2x of historical |
| Zero delivery (tROAS) | Target unreachable | Lower target by 20% |

---

## Budget Formulas Reference

### Minimum Budget for Learning Phase
```
Daily Budget = 5 × Target CPA
Monthly Budget = 150 × Target CPA
```

### Target CPA Calculation
```
Target CPA = (Average Order Value × Target Margin%) / Target Conversion Rate
```

### Break-even ROAS
```
Break-even ROAS = 1 / Margin %
Example: 30% margin → 1 / 0.3 = 3.33x ROAS
```

### MER (Marketing Efficiency Ratio)
```
MER = Total Revenue / Total Ad Spend
Healthy range: 3.0 - 5.0 for e-commerce
```

### Budget for 50 Conversions/Month
```
Daily Budget = (50 × Target CPA) / 30
Simplified: Daily Budget = 1.67 × Target CPA
```
