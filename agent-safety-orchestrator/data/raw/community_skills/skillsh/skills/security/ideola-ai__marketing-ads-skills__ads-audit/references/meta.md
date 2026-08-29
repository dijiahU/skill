# Meta Ads Audit Guide (2026)

## 2026 Platform Overview

Meta's **Andromeda algorithm** has fundamentally changed how ads work:
- Processes 10,000x more ad variants in parallel
- **Creative is the new targeting** - The visual/semantic data within the ad determines who sees it
- Broad targeting combined with specific creative angles outperforms narrow targeting
- Advantage+ (formerly ASC/AAC) is now the default for Sales/Leads/App objectives

> **Key 2026 Changes:**
> - Detailed targeting exclusions removed (March 2025) - 22.6% lower median cost per conversion
> - Advantage+ Shopping renamed to Advantage+ Sales (supports Sales, Leads, App)
> - 35% of US retail ad spend now uses Advantage+ ($60B annualized revenue)
> - Advantage+ delivers $4.52 ROAS (22% higher than manual)

## Campaign Structure: The 3-Stage System

### Modern Account Structure (2026)

Andromeda requires consolidated data. Replace fragmentation with:

| Stage | Campaign Type | Purpose | Key Settings |
|-------|---------------|---------|--------------|
| **1. Testing** | ABO (Ad Set Budget) | Test new concepts | Multiple ad sets, one campaign |
| **2. Challenger** | Advantage+ ASC | Graduate winners | Dedicated campaign, fair budget |
| **3. Core/Evergreen** | CBO (Campaign Budget) | Proven scalable assets | 1-3 winning campaigns |

**Critical Rule:** Never have >5 active campaigns per country/funnel stage (causes fragmentation)

### CBO vs ABO Decision Tree (2026)

| Factor | Use ABO | Use CBO |
|--------|---------|---------|
| Daily Budget | <$100 | >$500 |
| Campaign Goal | Creative testing | Scaling |
| Ad Sets | Need forced spend | Let AI allocate |

**Warning:** CBO with <$100 budget identifies false positive "early winner" and starves other ad sets.

## Pixel & CAPI Health (Critical Foundation)

### Event Match Quality (EMQ) Scoring

EMQ is Meta's grading of how well it can link events to users. This is THE north star metric.

| EMQ Score | Status | Action Required |
|-----------|--------|-----------------|
| 8-10 | Great/Premium | Optimal performance |
| 6-7 | Good | Acceptable baseline |
| 3-5 | OK/Poor | Action needed - below minimum |
| 0-2 | Poor | Critical - severe data loss |

**Critical Threshold:** EMQ < 6.0/10 = FAIL (ad delivery severely degraded)

### CAPI vs Pixel Performance

| Tracking Method | Match Rate | iOS 14+ Impact | Recommendation |
|-----------------|------------|----------------|----------------|
| Pixel Only | 60-70% | Severe degradation | Don't use alone |
| CAPI Only | 90%+ | Minimal impact | Use if pixel impossible |
| Both (Deduped) | 95%+ | Best performance | **RECOMMENDED** |

### Required User Parameters (by EMQ impact)

| Parameter | EMQ Impact | Pass | Fail |
|-----------|------------|------|------|
| Email (SHA256) | +4.0 pts | Passed | Missing |
| Phone (SHA256) | +3.0 pts | Passed | Missing |
| External ID | +1.5 pts | Passed | Missing |
| fbp (Browser ID) | +1.0 pts | Passed | Missing |
| fbc (Click ID) | +1.0 pts | Passed | Missing |
| IP Address | +0.5 pts | Passed | Missing |
| User Agent | +0.5 pts | Passed | Missing |

**Quick Win:** 87% of advertisers have poor EMQ. Fixing it improves performance 20-40%.

### Conversion Tracking Checklist

| Check | Critical If Missing |
|-------|---------------------|
| Pixel firing (recent events) | Critical |
| CAPI connected | Critical |
| EMQ ≥ 6.0 | Critical |
| Event deduplication (event_id) | High |
| Domain verification | High |
| 8 Priority Events configured | Medium |
| Advanced Matching ON | High |
| Standard Events used (not custom only) | Medium |

## Audience Strategy in 2026

### The New Reality: Creative = Targeting

**Andromeda's Total Value Equation:**
```
Total Value = Bid × Estimated Action Rate + User Value
```

The algorithm now finds the audience based on who engages with your creative.

### Broad Targeting Best Practices

| Old Way (Pre-2025) | New Way (2026+) |
|--------------------|-----------------|
| Narrow interest stacking | Broad (no interests/lookalikes) |
| Multiple ad sets per audience | Single campaign, multiple creatives |
| Manual exclusions | Let AI find audience |
| Test audiences | Test creative angles |

### Audience Size Guidelines

| Campaign Type | Minimum Audience | Optimal Range |
|---------------|-----------------|---------------|
| Cold/Awareness | 500,000+ | 1M - 10M |
| Retargeting | 1,000+ | 5K - 100K |
| Lookalike 1% | - | 100K - 500K |

**Red Flag:** Audience < 100,000 (for prospecting) = Delivery limited

### Advantage+ Audience Settings

| Setting | Recommended | When to Disable |
|---------|-------------|-----------------|
| Advantage+ Audience | ON (Expansion) | Niche testing only |
| Audience Expansion | ON | Strict compliance required |

**Performance:** Advantage+ Audience delivers 13% lower cost per catalog sale, 28% lower average CPC.

## Learning Phase Requirements (2026)

### The 50 Conversions Rule

**Learning Phase Definition:** 50 conversions per week per ad set

| Metric | Threshold | Status |
|--------|-----------|--------|
| Conversions/week | <50 | Learning Limited |
| Conversions/week | 50+ | Learning Complete |

**Critical:** If budget cannot support 50 conversions/week, CONSOLIDATE ad sets.

### Learning Phase Reset Triggers

Any of these actions reset learning phase:

| Action | Impact | Wait Time |
|--------|--------|-----------|
| Budget change >20% | Full reset | 1 week |
| Targeting change | Full reset | 1 week |
| Creative edit (active ad) | Full reset | 1 week |
| Bid cap change | Full reset | 1 week |

**Best Practice:** Make all changes at once, then wait 7 days.

### Budget Requirements for Learning

| Target CPA | Minimum Daily Budget |
|------------|---------------------|
| $10 | $50 |
| $25 | $125 |
| $50 | $250 |
| $100 | $500 |

**Formula:** Daily Budget = 5-7 × Target CPA (minimum to exit learning phase)

## Creative Best Practices (2026)

### Format Specifications

| Format | Resolution | Aspect Ratio | Character Limits |
|--------|------------|-------------|------------------|
| Feed (Primary) | 1080x1350 | 4:5 (preferred) | Primary: 125, Headline: 27-40 |
| Feed (Square) | 1080x1080 | 1:1 | Same as above |
| Stories/Reels | 1080x1920 | 9:16 | Primary: 72 (Reels) |
| Carousel | 1080x1080 | 1:1 | 2-10 cards |

**Critical:** 4:5 ratio occupies 25% more vertical pixels than 1:1 on mobile.

### Safe Zone Dimensions (2026)

#### Stories/Reels Safe Zones

| Zone | Pixels (from edge) | UI Element |
|------|-------------------|------------|
| Top | 0-250px | Profile/Time UI |
| Bottom | 0-350px | Reply/CTA buttons |
| Right (Reels only) | 0-120px | Like/Comment/Share |
| **Safe Content Area** | **Center 1080x1300px** | - |

**Critical:** Text in bottom 35% WILL be covered by user handle and caption.

### Ad Density Per Ad Set

| Count | Status | Action |
|-------|--------|--------|
| 1 ad | Critical | Andromeda needs more options |
| 2-3 ads | Warning | Add more variations |
| 3-6 ads | Optimal | Ideal for Andromeda |
| 7-10 ads | Good | More testing capacity |
| >10 ads | Diminishing returns | Consolidate |

### Creative Fatigue Indicators

| Metric | Early Fatigue | Advanced Fatigue |
|--------|---------------|------------------|
| Frequency | 2.5-3.0 | >4.0 (prospecting) |
| CTR Decline | -15% from peak | -30% from peak |
| CPA Increase | +20% from baseline | +50% from baseline |

**Refresh Cadence:**
- TOFU (awareness): Every 3-4 weeks
- BOFU (conversion): Every 6-7 weeks

### Creative Quality Indicators

| Element | Good Signal | Poor Signal |
|---------|------------|-------------|
| Format | Image + Video | Single format only |
| Aspect Ratio | 1:1, 9:16, 1.91:1 all present | Missing 9:16 (Reels/Stories) |
| Production | Native/UGC style | Polished/stock imagery |
| Hook Rate | >25% (3-sec view/impression) | <10% |
| Hold Rate | >15% (ThruPlay/impression) | <5% |

## Bidding Strategies (2026)

### Strategy Selection Guide

| Strategy | Use When | Initial Setting |
|----------|----------|-----------------|
| Lowest Cost | 90% of campaigns | Default |
| Cost Cap | Thin margins, scaling | 1.2-1.5x target CPA |
| Bid Cap | High-ticket, competitive | 2-3x target CPA |
| ROAS Goal | Catalog sales, varied AOV | Historical ROAS |
| Highest Value | Default for ASC | N/A |

### Cost Cap Best Practices

**Critical:** Don't set Cost Cap AT target CPA. Set at 1.2-1.5x to allow pacing buffer.

| Target CPA | Recommended Cost Cap |
|------------|---------------------|
| $10 | $12-15 |
| $25 | $30-37 |
| $50 | $60-75 |
| $100 | $120-150 |

**Danger Sign:** Zero delivery with Cost Cap ON → Cap too tight or insufficient budget.

## 2026 Benchmarks

### By Objective (WordStream 2025)

| Objective | CTR | CPC | CVR | CPL |
|-----------|-----|-----|-----|-----|
| Traffic | 1.71% | $0.70 | - | - |
| Leads | 2.59% | $1.92 | 7.72% | $27.66 |

### ROAS Benchmarks by Type

| Type | ROAS Benchmark |
|------|----------------|
| All-industries median | 2.19:1 |
| Retargeting | 3.61:1 |
| Advantage+ Sales | 4.52:1 |

### CPM by Industry (2026)

| Industry | CPM Range |
|----------|-----------|
| Arts & Entertainment | $5-6 |
| Most Industries | $6-8 |
| B2B | $30-40 |
| Finance | $45-50 |

### Engagement Metrics

| Metric | Good | Needs Help |
|--------|------|------------|
| Feed CTR | 1.5%+ | <0.8% |
| Stories CTR | 1.0%+ | <0.5% |
| Reels CTR | 2.0%+ | <1.0% |
| Quality Ranking | Above Average | Below Average |
| Conversion Rate | 3%+ | <1.5% |

### Frequency Thresholds

| Audience Type | Good | Warning | Critical |
|---------------|------|---------|----------|
| Prospecting | <2.5 | 2.5-3.0 | >3.0 |
| Retargeting | <4 | 4-6 | >6 |

## Quick Audit Checklist (2026)

### Critical (Immediate Action Required)
- [ ] Pixel firing (recent activity)
- [ ] CAPI connected
- [ ] EMQ ≥ 6.0
- [ ] Event deduplication configured (event_id)
- [ ] <5 active campaigns per country (avoid fragmentation)
- [ ] Budget sufficient for 50 conversions/week per ad set

### High Priority
- [ ] Multiple creative formats (Image + Video minimum)
- [ ] 9:16 aspect ratio present (Reels/Stories)
- [ ] 3-6 ads per ad set
- [ ] Advantage+ Audience enabled (unless niche testing)
- [ ] CPO used if budget >$500
- [ ] Frequency <3.0 (prospecting), <6 (retargeting)
- [ ] Creative refreshed in <30 days

### Medium Priority
- [ ] Audience size 100K-10M (prospecting)
- [ ] Purchaser exclusions active (for prospecting)
- [ ] Lookalike refreshed <60 days ago
- [ ] UTM parameters present
- [ ] Advantage+ Placements enabled
- [ ] Audience Network spend <20%

## Common Issues & Solutions (2026)

| Issue | Root Cause | Solution |
|-------|------------|----------|
| Learning Limited | <50 conv/week, fragmented structure | Consolidate ad sets, increase budget |
| Low EMQ | Missing user parameters | Add email/phone hashing to CAPI |
| High CPA, Low Delivery | Cost cap too tight | Raise to 1.2-1.5x target |
| High Frequency | Low creative diversity | Add 3+ new creatives weekly |
| Zero Delivery | Budget <5x target CPA | Increase budget, consolidate campaigns |
| CAPI Not Matching | Missing event_id | Add deduplication parameter |
| Advantage+ Underperforming | Insufficient creative volume | Upload 6+ assets per ad group |

## 2026 Platform-Specific Features

### Advantage+ Creative (14+ Options)
- AI-generated backgrounds
- Text variations
- Music overlays
- CTA stickers
- Aspect ratio optimization

**Recommendation:** Enable "Standard Enhancements" for better delivery.

### Thought Leader Ads (TLA) - Coming to Meta
Similar to LinkedIn TLAs - sponsor posts from executive profiles
- 1.7x higher CTR
- 1.6x more engagement
- Lower CPCs

### Message Updates
Conversation ads with branching CTAs now available for lead nurturing.

## Scaling Framework (2026)

### The 20% Rule
**IF** CPA < Target (by >10%) **AND** IS Lost to Budget >10%:
**THEN** Increase budget by 20%
**WAIT** 72 hours before next increase

### The 3x Kill Rule
**IF** Spend > 3x Target CPA **AND** Conversions = 0:
**THEN** Pause immediately

### Kill Logic - Quick Death
**IF** Spend > 1x Target CPA **AND** Clicks = 0 (or CTR <0.2%):
**THEN** Check creative/technical (broken link, disapproval)
