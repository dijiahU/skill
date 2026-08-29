# Google Ads Audit Guide (2026)

## 2026 Platform Overview

Google Ads has fundamentally shifted to AI-driven automation with three core campaign types:
- **AI Max for Search** - AI-powered text customization with final URL expansion
- **Performance Max (PMax)** - Cross-channel workhorse with enhanced transparency
- **Demand Gen** - Replaced Discovery and Video Action campaigns (3B users)

> **Key 2026 Changes:**
> - Privacy Sandbox officially retired (Oct 2025) - third-party cookies remain active
> - Consent Mode v2 mandatory for EEA/UK
> - Enhanced CPC deprecated March 2025
> - Call Ads sunset Feb 2027 (new creation stopped Feb 2026)

## Campaign Types to Audit

### 1. Search Ads

**Key Checks:**
- Quality Score components (expected CTR ~39%, ad relevance ~22%, landing page ~39%)
- Search terms report for negative keyword opportunities
- Broad Match used ONLY with Smart Bidding (Critical: Broad + Manual CPC = FAIL)
- Keyword match type: Exact match now captures "same meaning" (not exact words)
- Impression share breakdown (lost to budget vs. rank)

**AI Max for Search (2025+):**
- Uses LLMs to match landing page content to conversational queries
- Requires structured data (Schema) for optimal performance
- Brand Guidelines configuration required to prevent hallucinated copy

**Red Flags:**
- Quality score < 5/10 (Critical if >20% spend on QS <5)
- Search terms triggering irrelevant queries (>10% irrelevant spend = FAIL)
- Broad Match + Manual CPC combination (Critical fail)
- Lost impression share > 30% due to rank
- Missing Enhanced Conversions

### 2. Performance Max (PMax)

**Maturity Level (2026):**
- Campaign-level negative keywords now supported (up to 10,000)
- Search themes increased to 50 per asset group
- Full search term reporting available (March 2025)
- Channel-level reporting across Search, YouTube, Display, Gmail, Discover, Maps

**Key Checks:**
- Asset group performance (channel breakdown available)
- Asset strength indicators (Poor = Critical issue)
- Final URL expansion settings (must have exclusions)
- Brand exclusions configured (if Search active)
- Audience signal utilization
- New Customer Acquisition (NCA) settings enabled

**PMax Structure Best Practice:**
- Organize Asset Groups by **User Intent** (High-Performance Athletes vs. Casual Commuters)
- NOT by Product Category

**Asset Density Requirements:**
| Asset Type | Min Qty | Max Qty | Critical Status |
|------------|---------|---------|----------------|
| Headlines | 8-10 | 15 | <5 = High Risk |
| Descriptions | 3-4 | 4 | <2 = Warning |
| Marketing Images (1.91:1) | 1 | 20 | 0 = Fail |
| Square Images (1:1) | 1 | 20 | 0 = Fail |
| Portrait Images (4:5) | 1 | 20 | 0 = Critical |
| Logo (1:1) | 1 | 5 | 0 = Warning |
| Videos | 1 | 5 | 0 = Critical |

**Red Flags:**
- Asset strength = "Poor" or "Below average"
- Missing vertical video (9:16) - excludes YouTube Shorts
- Spending on excluded categories
- High CPA without clear conversion path
- < 50 conversions/month on tCPA/tROAS

### 3. Demand Gen (Replaced Discovery March 2025)

**Key Checks:**
- Asset diversity: 5+ images, 1+ video, 5+ headlines, 5+ descriptions
- Format performance (Feeds, Shorts, Stories, YouTube)
- Audience lookalike performance
- Conversion value vs. cost

**Benefits vs. Video Action Campaigns:**
- 58% higher ROAS
- 20% more conversions with image+video vs video-only

**Red Flags:**
- Missing required asset combinations
- Skipped formats without testing

### 4. Display Campaigns

**Key Checks:**
- Placement performance (block sites with high spend/low conversion)
- Topic/category targeting alignment
- Creative sizes available (missing formats limit delivery)
- Viewable CTR vs. overall CTR
- Account-level placement exclusions (Games, Apps, MFA sites)

**Red Flags:**
- CTR < 0.2%
- High spend on low-performing placements
- Limited creative sizes

## Google-Specific Metrics

### 2026 Benchmarks (WordStream 16,000+ campaigns)

| Metric | All Industries | E-commerce | B2B SaaS | Legal | Healthcare |
|--------|----------------|------------|----------|-------|------------|
| Search CTR | 6.66% | 4.13% | 4.28% | 5.20% | 4.90% |
| Search CPC | $5.26 | $1.15 | $4.50 | $750+ | $40+ |
| Search CVR | 7.52% | 2.81% | 1.65% | 4.60% | 3.10% |
| Quality Score | 7-10 good | <5 fail | | | |

### Impression Share Thresholds

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Search IS | 80%+ | 60-79% | <60% |
| Search Top IS | 50%+ | 30-49% | <30% |
| Absolute Top IS | 20%+ | 10-19% | <10% |
| Lost to Budget | <10% | 10-20% | >20% |
| Lost to Rank | <20% | 20-40% | >50% |

## Bidding Strategy Audit (2026)

### Smart Bidding Requirements

| Strategy | Min Conversions | When to Use | When NOT to Use |
|----------|----------------|-------------|-----------------|
| Maximize Clicks | 0 | Cold start, <15 conv/mo | Conversion vol >30, Broad match |
| Maximize Conversions | 15-30/mo | Transition to tCPA, budget limited | Uncapped budget, fixed margin |
| Target CPA (tCPA) | 30/mo (50+ ideal) | Lead gen, B2B | <15 conv/mo, budget <2x target |
| Target ROAS (tROAS) | 50/mo | E-commerce, value varies | Homogenous value, <50 conv |
| Target Impression Share | 0 | Brand protection, local dominance | Direct response, generic keywords |
| Manual CPC | 0 | <15 conv/mo, granular control | Broad match (dangerous) |

### tCPA Setting Protocol
- **Initial Target:** 1.1x - 1.2x of historical 30-day average CPA
- **Adjustment:** Max 10% every 14 days
- **Danger Signs:** Impressions drop >20%, 3 consecutive days with 0 conversions

### tROAS Setting Protocol
- **Initial Target:** Exact historical ROAS (last 30 days)
- **Scaling:** Lower target to scale volume, raise to increase efficiency
- **Danger Signs:** Zero spend (target too high)

## Quality Score Deep Dive

### Quality Score Formula (2026)
**Ad Rank = CPC Bid × Quality Score × Expected Impact of Ad Assets**

**Component Weights:**
1. Expected CTR: ~39% (heaviest)
2. Landing Page Experience: ~39% (critical for AI Overviews)
3. Ad Relevance: ~22%

### Quality Score Audit Rules
| Score Range | Status | Action Required |
|-------------|--------|-----------------|
| 8-10 | Excellent | Scale budget |
| 7 | Good | Monitor |
| 5-6 | Average | Optimization opportunity |
| <5 | Critical | Wasting budget, immediate fix needed |

### QS × Spend Analysis
- **Critical Fail:** >20% of spend on keywords with QS <5
- **Warning:** 10-20% of spend on QS <5

## Conversion Tracking Requirements

### Minimum (Must Have)
- Google Tag (gtag.js) installed
- Enhanced Conversions enabled (hashed email/phone)
- Consent Mode v2 (EEA/UK mandatory)
- At least 1 Primary Conversion action

### Ideal (Should Have)
- Server-Side GTM (bypasses ITP, 10-30% accuracy improvement)
- Data-Driven Attribution (now mandatory default)
- Offline Conversion Import (scheduled/API)

### Conversion Health Checks
| Check | Pass | Fail |
|-------|------|------|
| Pixel Status | Recording conversions | No recent conversions (>7 days) |
| Enhanced Conversions | Active/On | Off |
| Attribution Model | Data-Driven | Last Click (Legacy) |
| Duplicate Tracking | Repeat Rate <1.1 | >1.5 (double counting) |

## Account Structure Best Practices (2026)

### Modern Structure Philosophy
- **SKAGs (Single Keyword Ad Groups)** - Largely obsolete
- **STAGs (Single Theme Ad Groups)** - Recommended (10-20 related keywords per group)
- **Consolidation** - More data density for AI learning

### Campaign Consolidation Rules
| Metric | Good | Warning |
|--------|------|---------|
| Campaigns per $500/mo spend | <1 | >1 (fragmented) |
| Ad Groups per Campaign | 5-20 | <1 or >50 |
| Keywords per Ad Group | ≤10 | >20 (theme drift) |
| Active RSAs per Ad Group | 1-3 | 0 or >3 |

### Location Settings
- **Presence: People in** - For local businesses
- **Interest: People in or interested in** - FAIL for service businesses (Critical)
- Check geo-exclusions are populated

## Extensions/Assets Audit (2026)

Google now treats extensions as "Assets" with 15+ types:

| Asset Type | Character Limit | Max Count | Critical if Missing |
|------------|-----------------|-----------|---------------------|
| Sitelinks | 25 text, 35 desc | 20 | <2 = Warning |
| Callouts | 25 | 20 | <2 = Low |
| Structured Snippets | 25 | 10 | 0 = Low |
| Image Extensions | N/A | 20 | 0 = Medium |
| Call Assets | N/A | 1 | N/A |
| Lead Forms | 30 headline, 25 business | 1 | N/A |
| Price Assets | 25 header | 8 | N/A |

**Quick Win:** Advertisers with 6 sitelinks see 3.5% more conversions.

## Quick Audit Checklist (2026 Edition)

### Critical Checks (Fail if missing)
- [ ] Enhanced Conversions enabled
- [ ] At least 1 Primary Conversion action active
- [ ] Broad Match ONLY used with Smart Bidding
- [ ] No Broad Match + Manual CPC combinations
- [ ] PMax has vertical video (9:16) asset
- [ ] Data-Driven Attribution selected
- [ ] Consent Mode v2 configured (if EEA)

### High Priority
- [ ] Quality Score ≥7 on 70%+ of keywords
- [ ] Lost IS (Budget) <15%
- [ ] Lost IS (Rank) <40%
- [ ] Zero-conversion terms with >30 clicks added as negatives
- [ ] Brand Guidelines configured in PMax/Search
- [ ] NCA (New Customer Acquisition) enabled for prospecting
- [ ] Campaign-level negative keywords configured

### Medium Priority
- [ ] 4+ sitelinks per campaign
- [ ] 4+ callouts per campaign
- [ ] Image extensions active
- [ ] Account-level placement exclusions set
- [ ] Customer Match uploaded <90 days ago
- [ ] Observation mode audiences active

## Common Issues & Solutions (2026)

| Issue | Solution | Quick Win |
|-------|----------|-----------|
| Low Quality Score | Improve ad relevance, landing page, expected CTR | Add keywords to headlines |
| Poor search terms | Add negatives, refine match types | Auto-negate >30 clicks 0 conv |
| Lost IS (Rank) | Increase bids, improve quality score | Enable Enhanced Conversions |
| Poor PMax performance | Add exclusions, improve assets, add vertical video | Add 4:5 portrait images |
| Display low CTR | Refresh creatives, refine placements | Exclude Games/Apps |
| Low conversions with Broad Match | Switch to Smart Bidding | Enable tCPA with 1.2x historical |
| PMax not spending | Check asset density, add video | Add 9:16 vertical video |
| High CPA on Search | Check match types, add negatives | Exclude Audience Network |

## 2026 Specific Recommendations

1. **Consolidate fragmented structures** - Merge campaigns to feed AI learning
2. **Enable Enhanced Conversions** - 10% more measured conversions
3. **Use PMax with full asset groups** - Missing assets = missing inventory
4. **Implement server-side tracking** - Bypass ITP, improve accuracy
5. **Set Brand Guidelines** - Prevent AI hallucination in ad copy
6. **Monitor Ad Strength** - "Poor" to "Excellent" = 15% more conversions
7. **Leverage AI Max for Search** - Requires Schema markup on landing pages
