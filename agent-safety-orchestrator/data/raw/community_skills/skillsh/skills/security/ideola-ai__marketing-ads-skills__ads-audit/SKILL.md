---
name: ads-audit
description: Comprehensive ads audit system with platform-specific subcommands. Use /ads audit for full multi-platform audit. Platform-specific commands available - /ads google (Google Ads), /ads meta (Facebook/Instagram), /ads youtube (YouTube Ads), /ads linkedin (LinkedIn Ads), /ads tiktok (TikTok Ads), /ads microsoft (Microsoft/Bing Ads), /ads creative (creative audit), /ads landing (landing page audit), /ads budget (budget and bidding review). Also triggers on audit ads, ad review, performance audit, analyze my ads, why are my ads underperforming.
---

# Ads Audit System

**Purpose:** Audit and optimize existing ad campaigns across all major platforms.

This skill focuses exclusively on **performance analysis and optimization recommendations** - not campaign planning or strategy (use `/marketing-campaign` for that).

## Marketing OS Workflow Position

```
brand-voice → content-brief → content-planning → content-creation
                                          ↓
                                        marketing-campaign
                                          ↓
                                          ads-audit
```

**This skill is LAST** - Audit and optimize existing campaigns after they've been planned and launched.

**Input from:**
- `/marketing-campaign` - Campaign structure, KPIs, and benchmarks to compare against
- `/content-creation` - Creative quality reference for ad audit

**Output for:**
- Optimization recommendations (loop back to campaign planning or content creation)

## Command Reference

| Command | Description |
|---------|-------------|
| `/ads audit` | Full multi-platform audit with parallel subagent delegation |
| `/ads google` | Google Ads deep analysis (Search, PMax, Display, YouTube, Demand Gen) |
| `/ads meta` | Meta Ads deep analysis (FB, IG, Advantage+ Shopping) |
| `/ads youtube` | YouTube Ads specific analysis (Skippable, Shorts, Demand Gen) |
| `/ads linkedin` | LinkedIn Ads deep analysis (B2B, Lead Gen, TLA) |
| `/ads tiktok` | TikTok Ads deep analysis (Creative, Shop, Smart+) |
| `/ads microsoft` | Microsoft/Bing Ads deep analysis (Copilot, Import validation) |
| `/ads creative` | Cross-platform creative quality audit and fatigue detection |
| `/ads landing` | Landing page quality assessment for ad campaigns |
| `/ads budget` | Budget allocation and bidding strategy review |

## Universal Audit Workflow

All commands follow this core structure. See [rules/workflow.md](rules/workflow.md) for detailed step-by-step procedure.

### 1. Data Collection
- Campaign structure and objectives
- Key metrics (spend, impressions, CTR, CPC, CPA, ROAS)
- Targeting parameters
- Creative inventory
- Time period analyzed

### 2. Performance Analysis
Compare against platform benchmarks (see [references/benchmarks.md](references/benchmarks.md)):
- CTR vs. channel average
- CPA vs. target
- ROAS vs. goal
- Frequency vs. fatigue threshold

### 3. Issue Identification
Systematic diagnosis across:
- Creative (fatigue, format, quality)
- Targeting (audience, exclusions, overlap)
- Budget/Bidding (strategy, caps, pacing)
- Technical (tracking, landing pages)

**For detailed diagnosis process:** See [rules/diagnosis.md](rules/diagnosis.md)

### 4. Recommendations
Prioritized action plan with:

**For priority framework:** See [rules/priority.md](rules/priority.md)

- Quick wins (immediate actions)
- A/B test ideas (see [references/testing.md](references/testing.md))
- Long-term improvements

### 5. Output Format
```markdown
# [Platform] Ads Audit Report

## Executive Summary
- Overall Score: X/10
- Key Finding: [Top insight]
- Quick Impact: [Estimated improvement potential]

## Performance vs Benchmarks
| Metric | Actual | Benchmark | Gap |
|--------|--------|-----------|-----|
| CTR | X% | X% | X% |

## Issues Found (Priority Order)
### 🔴 Critical
1. [Issue] - Impact: High - Action: [Immediate step]

### 🟡 Moderate
1. [Issue] - Impact: Medium - Action: [Plan fix]

## Action Items
- [ ] [Action 1] - This week
- [ ] [Action 2] - This week
- [ ] [Test idea] - Next sprint
```

## Platform-Specific Commands

### `/ads google`

**Analyze:** Search, Performance Max, Display, YouTube, Demand Gen

**Key Metrics:**
- Quality Score (search)
- Impression Share
- Search Terms (negative opportunities)
- Asset performance (PMax)
- View rate (YouTube)

**Google-Specific Resources:** [references/google.md](references/google.md)

### `/ads meta`

**Analyze:** Facebook, Instagram, Messenger, Advantage+ Shopping

**Key Metrics:**
- Relevance Score / Quality Ranking
- Delivery Category
- Frequency
- CTR per placement
- Pixel vs CAPI comparison

**Meta-Specific Resources:** [references/meta.md](references/meta.md)

### `/ads youtube`

**Analyze:** Skippable in-stream, Non-skippable, Bumpers, Shorts, Discovery

**Key Metrics:**
- View rate (25%, 50%, 75%, 100%)
- CPV efficiency
- Audio/creative variations
- Audience retention graphs

**YouTube-Specific Resources:** [references/youtube.md](references/youtube.md)

### `/ads linkedin`

**Analyze:** Sponsored content, Message ads, Lead gen forms, Text ads

**Key Metrics:**
- Engagement rate
- Cost per send (message ads)
- Lead form completion rate
- Job title/industry performance

**LinkedIn-Specific Resources:** [references/linkedin.md](references/linkedin.md)

### `/ads tiktok`

**Analyze:** In-feed ads, Spark ads, TopView, Brand takeover

**Key Metrics:**
- Video completion rate
- 2s/6s VTR
- TikTok pixel events
- Creative diversity score

**TikTok-Specific Resources:** [references/tiktok.md](references/tiktok.md)

### `/ads microsoft`

**Analyze:** Search ads, Audience ads, Shopping, Import from Google

**Key Metrics:**
- Quality Score
- Import match rate
- Audience expansion performance
- Copilot bid suggestions

**Microsoft-Specific Resources:** [references/microsoft.md](references/microsoft.md)

### `/ads creative`

**Cross-platform creative audit covering:**
- Visual quality and format compliance
- Copy effectiveness (hook, CTA, clarity)
- Ad fatigue indicators
- A/B test coverage
- Creative diversity score

**Creative Framework:** [references/creative.md](references/creative.md)

### `/ads landing`

**Landing page audit covering:**
- Load time and Core Web Vitals
- Mobile optimization
- CTA clarity and placement
- Form optimization
- Trust signals and social proof
- Technical SEO basics

**Landing Page Framework:** [references/landing.md](references/landing.md)

### `/ads budget`

**Budget and bidding audit covering:**
- Budget allocation efficiency
- Bid strategy appropriateness
- Learning phase completion
- Dayparting opportunities
- Seasonal pacing
- Cross-channel budget balance

**Budget Framework:** [references/budget.md](references/budget.md)

## Resources

- [references/benchmarks.md](references/benchmarks.md) - Industry KPI benchmarks by platform
- [references/testing.md](references/testing.md) - A/B testing frameworks
- [references/checklist.md](references/checklist.md) - Complete audit checklist
- [references/google.md](references/google.md) - Google Ads specific guide
- [references/meta.md](references/meta.md) - Meta Ads specific guide
- [references/youtube.md](references/youtube.md) - YouTube Ads specific guide
- [references/linkedin.md](references/linkedin.md) - LinkedIn Ads specific guide
- [references/tiktok.md](references/tiktok.md) - TikTok Ads specific guide
- [references/microsoft.md](references/microsoft.md) - Microsoft Ads specific guide
- [references/creative.md](references/creative.md) - Creative audit framework
- [references/landing.md](references/landing.md) - Landing page audit framework
- [references/budget.md](references/budget.md) - Budget & bidding framework

---

## Integration with Marketing OS Workflow

**Input from:**
- `/marketing-campaign` - Campaign structure, KPIs, and benchmarks to compare against
- `/content-creation` - Creative quality reference for ad audit

**Output for:**
- Optimization recommendations (loop back to campaign planning or content creation)
- Performance insights that inform future briefs

**When to Use:**
- After campaigns have been running for 1-2 weeks
- When performance is below expectations
- As part of ongoing optimization (weekly/bi-weekly)
- Before scaling budget

**Note:** This skill can be used independently - you don't need to go through the full workflow to audit ads. Just provide campaign data and metrics.
