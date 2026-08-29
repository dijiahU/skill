# Microsoft Advertising (Bing) Audit Guide

## Campaign Types

### 1. Search Ads
**Key Checks:**
- Quality Score
- Impression Share
- Position metrics
- Keyword match types
- Negative keyword usage

**Benchmarks:**
- CTR: 2-4%
- CPC: $1-2 (typically lower than Google)
- Conversion rate: 2-4%
- Quality Score: 7-10

### 2. Audience Ads (Native)
**Placement:** MSN, Outlook, Microsoft Edge, premium publishers
**Key Checks:**
- CTR by placement
- Viewable impressions
- Engagement rate
- Cost per engagement

**Benchmarks:**
- CTR: 0.3-0.6%
- CPC: $0.80-2.00
- VTR: 60%+

### 3. Shopping Ads
**Key Checks:**
- Product feed quality
- Merchant Center status
- Bid by product category
- Competition level

**Benchmarks:**
- CTR: 1-2%
- CPC: $0.50-1.50
- Conversion rate: 3-6%

### 4. Microsoft Import from Google
**Key Checks:**
- Import success rate
- Campaign budget sync status
- Ad approval status
- Keyword match type compatibility
- Negative keyword transfer

**Common Issues:**
- Shopping campaigns not supported (must rebuild)
- Smart bidding strategies may not transfer
- Responsive search ads may need manual adjustment

## Microsoft-Specific Metrics

| Metric | Good | Needs Help |
|--------|------|------------|
| Quality Score | 7-10 | 1-6 |
| Search Impression Share | 70%+ | <50% |
| Search Top IS | 40%+ | <20% |
| CTR | 3%+ | <1.5% |
| Position | 1-2 | 4+ |
| Conversion Rate | 3%+ | <2% |

## Microsoft vs Google Key Differences

| Feature | Microsoft | Google |
|---------|-----------|--------|
| Volume | ~35% of Google | Full market |
| CPC | Typically 20-40% lower | Higher |
| Competition | Less competitive | More competitive |
| Demographics | Older, higher income | Broader |
| B2B Performance | Often better | Varies |
| Shopping | Separate setup | Google Merchant Center |

## Quick Audit Checklist

- [ ] Review import status (if importing from Google)
- [ ] Check Quality Score by keyword
- [ ] Analyze impression share and bid adjustments
- [ ] Review search terms for negative opportunities
- [ ] Check campaign budgets and delivery
- [ ] Verify conversion tracking is firing
- [ ] Review Audience Network performance
- [ ] Check for disapproved ads
- [ ] Analyze device performance (desktop strong on Bing)
- [ ] Review demographic targeting (age, gender)

## Microsoft Advertising Editor

**Tips for bulk operations:**
- Use for bulk keyword bid changes
- Negative keyword management
- Ad copy updates across campaigns
- Import/export for backup

## Audience Segments

### LinkedIn Profile Targeting
Available only on Microsoft Advertising:
- Job function
- Industry
- Company size
- Job title

**Best for:** B2B campaigns, high-consideration products

### Remarketing
- Website visitors
- Microsoft account activities
- Custom combinations

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Not importing from Google | Check account linking, review import errors |
| Low impression share | Increase bids, expand keywords |
| Low Quality Score | Improve ad relevance, landing page |
| Poor shopping performance | Rebuild natively (can't import Google Shopping) |
| Low traffic | Add keywords, broaden match types |
| High CPC | Lower bids, improve quality score |

## Copilot Bid Suggestions

Microsoft Advertising now uses AI for bid suggestions:
- Review suggested bids for top keywords
- Test bid adjustments based on recommendations
- Monitor performance after accepting suggestions
- Compare actual vs. suggested performance

## Seasonal & Device Insights

### Device Performance
- **Desktop:** Stronger on Bing vs Google (older demographic)
- **Mobile:** Growing but lower share than Google
- **Tablet:** Lower volume, test separately

### Time-of-Day Patterns
- Business hours performance often stronger
- Weekend volume typically lower
- Test dayparting for B2B campaigns

## Integration Opportunities

### Import Strategy
1. **Start with import** from Google (available campaigns)
2. **Rebuild Shopping** campaigns natively
3. **Adjust bids** downward initially (20-40%)
4. **Monitor and optimize** based on performance
5. **Leverage unique features** (LinkedIn targeting)

### Cross-Platform Tactics
- Use Microsoft for **lower-cost testing**
- Test creatives on Microsoft before Google rollout
- Capture **older/higher-income** demographics
- Fill gaps where Google CPC is too high
