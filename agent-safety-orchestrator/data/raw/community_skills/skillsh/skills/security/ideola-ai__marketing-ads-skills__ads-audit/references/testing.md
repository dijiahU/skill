# A/B Testing Framework

## Test prioritization Matrix

| Impact | Low Effort | High Effort |
|--------|------------|-------------|
| **High Impact** | Test Immediately | Plan for Next Sprint |
| **Low Impact** | Skip | Test If Resources Allow |

## Creative Tests

### Hook/Formula Tests
- Question hook vs. statement hook
- "How I..." vs. "Why I..." vs. "Stop doing..."
- Number-based hooks ("7 ways to...") vs. urgency hooks
- Problem-first vs. solution-first

### Visual Format Tests
- User-generated content vs. polished creative
- Product-only vs. lifestyle shot
- Video vs. static vs. carousel
- Vertical (9:16) vs. square (1:1) vs. horizontal (16:9)

### Copy Elements Tests
- Short copy (1-2 lines) vs. long copy (story)
- Emoji vs. no emoji
- CTA button only vs. CTA + headline
- Price reveal vs. price hidden

### UGC Style Tests
- UGC unboxing vs. UGC tutorial vs. UGC review
- Creator speaking vs. voiceover with b-roll
- Trend audio vs. branded audio vs. no audio

## Targeting Tests

### Audience Size Tests
- Broad audience (2M+) vs. interest-based (500K-1M)
- Lookalike 1% vs. Lookalike 2-3%
- Custom audience (website visitors) vs. interest-based

### Demographic Tests
- Age bands (18-24 vs. 25-34 vs. 35-44)
- Gender targeting vs. all genders
- Income segments (if available)

### Placement Tests
- All placements vs. Feed only vs. Stories/Reels only
- Automatic placements vs. manual placement selection
- Feed + Stories vs. Feed + Stories + Explore

## Offer Tests

### Discount Tests
- % off (20% off) vs. $ amount ($10 off)
- Free shipping vs. % off
- BOGO vs. % off
- Bundle vs. single item discount

### Urgency Tests
- Limited time (24 hours) vs. limited quantity (only 50 left)
- Countdown timer vs. static urgency
- Early access vs. exclusive discount

### Lead Magnet Tests
- Ebook vs. webinar vs. free trial
- Short form (name + email) vs. long form (more fields)
- Immediate download vs. email delivery

## Landing Page Tests

### Headline Tests
- Benefit-focused vs. feature-focused
- Short vs. long headline
- Question vs. statement

### CTA Tests
- Button color (green vs. blue vs. orange)
- Button text ("Buy Now" vs. "Get Started" vs. "Learn More")
- CTA placement (above fold vs. below fold)

### Layout Tests
- Single column vs. two column
- Video hero vs. image hero
- Long-form vs. short-form page

## Test Duration Guidelines

| Daily Conversions | Minimum Test Duration |
|-------------------|----------------------|
| 50+ | 3-7 days |
| 20-50 | 7-14 days |
| 10-20 | 14-21 days |
| <10 | Consider aggregate testing |

**Minimum sample size:** At least 100 conversions per variation for statistical significance.

## Statistical Significance Quick Reference

| Confidence Level | Z-Score |
|-----------------|---------|
| 90% | 1.65 |
| 95% | 1.96 |
| 99% | 2.58 |

**Quick rule of thumb:** If variation B has 20%+ improvement with similar spend, it's likely worth scaling.

## Common Test Mistakes to Avoid

1. **Testing too many variables at once** - Change one element at a time
2. **Ending tests too early** - Wait for statistical significance
3. **Ignoring seasonality** - Account for day-of-week and holidays
4. **Testing during major events** - Avoid launch days, sales events
5. **Not documenting learnings** - Record what worked and why

## Test Documentation Template

```markdown
## Test: [Name]
**Hypothesis:** [What you believe will happen and why]
**Variable Tested:** [One specific element]
**Variations:**
- Control: [Description]
- Test: [Description]
**Duration:** [Dates]
**Results:**
- Control: [CTR, CPC, CPA, ROAS]
- Test: [CTR, CPC, CPA, ROAS]
**Winner:** [Control/Test]
**Action:** [Scale, pause, iterate]
**Learning:** [What this tells us about audience]
```
