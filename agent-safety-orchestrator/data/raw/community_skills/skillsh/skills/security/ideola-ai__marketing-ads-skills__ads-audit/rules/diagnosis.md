# Issue Diagnosis Framework

Systematic approach to identifying root causes of ad performance issues.

## Decision Tree for Diagnosis

```
START: ROAS below target
│
├─ CPA above target?
│  ├─ YES → Is CTR below benchmark?
│  │        ├─ YES → Creative/Targeting issue
│  │        └─ NO → Landing page/offer issue
│  │
│  └─ NO → Conversions low despite clicks?
│           ├─ YES → Landing page/tracking issue
│           └─ NO → Budget/visibility issue
```

---

## Diagnostic Pathways

### Path A: Low CTR (Creative/Targeting)

**Symptoms:**
- CTR < 50% of benchmark
- Impressions are normal or high
- CPC is at or below benchmark

**Diagnostic Steps:**
1. Check creative diversity score
   - <3 variations = fatigue risk
   - Same creative >2 weeks = fatigued
2. Review creative quality scores
   - Relevance/quality <5 = poor match
3. Analyze targeting
   - Audience >10M = too broad
   - Audience <100K = too narrow
4. Check placement performance
   - One placement dragging down average

**Root Causes:**
| Cause | Evidence | Solution |
|-------|----------|---------|
| Creative fatigue | CTR declining over time | Refresh creative |
| Poor creative quality | Low relevance score | New creative direction |
| Wrong audience | Low CTR across all creative | Refine targeting |
| Bad placement mix | One placement 0% CTR | Exclude placement |

### Path B: High CPA with Normal CTR (Conversion/Landing Page)

**Symptoms:**
- CTR at or above benchmark
- CPA > 2x target
- Conversion rate below benchmark

**Diagnostic Steps:**
1. Test landing page load time
   - >3s on mobile = issue
2. Check pixel/conversion tracking
   - Test conversion doesn't record = broken
3. Review landing page experience
   - No clear CTA above fold = confused
   - Form has >5 fields = too long
4. Analyze by device
   - Mobile conv rate << desktop = mobile issue

**Root Causes:**
| Cause | Evidence | Solution |
|-------|----------|---------|
| Slow page | Load >3s | Optimize images, scripts |
| Broken tracking | 0 conversions recorded | Fix pixel |
| Confused user | High bounce rate | Clarify CTA |
| Long form | Low completion rate | Reduce fields |
| Mobile broken | 0% mobile conv rate | Fix mobile |

### Path C: Not Spending (Visibility/Delivery)

**Symptoms:**
- Spend <80% of daily budget
- Low impression share
- "Limited" or "Learning" delivery status

**Diagnostic Steps:**
1. Check budget sufficiency
   - Daily budget <50x target CPA = too low
2. Review bid strategy
   - Bid cap too aggressive = limiting
3. Check audience size
   - <100K available = too narrow
4. Verify ad approval
   - Disapproved/paused ads = not running

**Root Causes:**
| Cause | Evidence | Solution |
|-------|----------|---------|
| Budget too low | <80% spend consistently | Increase 2-3x |
| Bid too low | Lost IS due to rank | Raise bid |
| Audience too small | Low reach | Expand audience |
| Approval issue | Ads disapproved | Fix violations |
| Learning phase | <50 conv/week | Wait or combine |

### Path D: Overspending (Budget Control)

**Symptoms:**
- Spend >110% of budget
- CPA climbing with spend
- Frequency >5 per user

**Diagnostic Steps:**
1. Check frequency cap
   - No cap set = uncontrolled
2. Review bid landscape
   - Rising bids = competition
3. Analyze marginal ROAS
   - Last 10% spend ROAS <50% = diminishing returns

**Root Causes:**
| Cause | Evidence | Solution |
|-------|----------|---------|
| No frequency cap | Freq >5 | Add cap 3-4/week |
| Low quality spend | CPA rising with spend | Reduce budget, refine |
| Aggressive bidding | Auto-bid winning too much | Lower bids |

---

## Platform-Specific Diagnosis

### Meta Ads
| Symptom | Check | Action |
|---------|-------|--------|
| Learning phase | >2 weeks at <50 conv/wk | Combine ad sets |
| Limited delivery | Check: budget, bid, audience, policy | Fix specific limiter |
| Low relevance score | Creative, audience, landing page match | Test new creative |
| CAPI low match rate | Verify CAPI setup, events | Fix event mapping |

### Google Ads
| Symptom | Check | Action |
|---------|-------|--------|
| Low quality score | Expected CTR, ad relevance, LP experience | Improve relevance |
| Lost IS (rank) | Bid too low or quality poor | Raise bid or improve |
| Poor search terms | Irrelevant queries triggering | Add negatives |
| PMax not spending | Asset strength, exclusions | Add assets, exclude |

### TikTok Ads
| Symptom | Check | Action |
|---------|-------|--------|
| Low VTR (2s) | Hook not grabbing attention | Fix first 3 seconds |
| Low completion | Pacing/engagement issues | Trim video |
| High frequency | Same ad seen >4x | Refresh creative |
| Sound-off rate | Audio not compelling | Test trending sounds |

### LinkedIn Ads
| Symptom | Check | Action |
|---------|-------|--------|
| Low audience size | <50K available | Broaden targeting |
| High CPC | Competition, narrow targeting | Expand or lower bid |
| Low form completion | Form too long, value unclear | Reduce fields, clarify offer |

---

## Quick Diagnosis Checklist

For each underperforming campaign, run through:

### Creative (2 minutes)
- [ ] CTR declining over time?
- [ ] Less than 3 creative variations?
- [ ] Relevance/quality score below 5?
- [ ] Same creative running >2 weeks?

### Targeting (2 minutes)
- [ ] Audience size <100K or >10M?
- [ ] CTR uniformly low across all creative?
- [ ] Converted users still seeing ads?
- [ ] Multiple ad sets with same targeting?

### Budget/Bidding (2 minutes)
- [ ] Spending <80% of budget?
- [ ] Spending >110% of budget?
- [ ] Frequency >5 per user?
- [ ] Learning phase >2 weeks?

### Technical (2 minutes)
- [ ] Any ads disapproved/paused?
- [ ] Landing page load >3 seconds?
- [ ] Test conversion doesn't track?
- [ ] Landing page broken on mobile?

---

## Root Cause Template

After diagnosis, document:

```
Campaign: [Name]
Issue: [Observed symptom]
Root Cause: [Identified from diagnostic tree]
Evidence: [Data supporting conclusion]
Solution: [Specific fix required]
Expected Impact: [Quantifiable improvement]
Effort: [Low/Medium/High]
Priority: [Critical/High/Medium/Low]
```

**Example:**
```
Campaign: Summer Sale 2024
Issue: CPA $85 vs $25 target, CTR 2.1% (on benchmark)
Root Cause: Landing page load time 6.5 seconds on mobile
Evidence: Mobile conversion rate 0.2% vs desktop 3.5%
Solution: Compress images, remove unused scripts, add lazy loading
Expected Impact: Mobile CPA from $85 to $35, overall CPA to $38
Effort: Medium (dev required)
Priority: High
```
