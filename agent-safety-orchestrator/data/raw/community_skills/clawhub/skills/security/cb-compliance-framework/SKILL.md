---
name: Cross-border Compliance Framework
slug: cb-compliance-framework
description: Comprehensive compliance requirements mapping for international e-commerce operations
category: cross-border-ecommerce
type: descriptive
language: en
author: Harry (code agent)
version: 1.0.0
---

# Cross-border Compliance Framework

## Overview

Comprehensive compliance requirements mapping for international e-commerce operations. Maps tax, consumer protection, data privacy, product safety, and customs requirements across major markets: Germany, France, Japan, Australia, UK, Brazil, Canada, Netherlands, India, and more. Provides implementation roadmaps, documentation frameworks, and professional consultation recommendations. This is a pure descriptive skill. No code execution, API calls, or network access.

## Trigger Keywords

Use this skill when the user mentions or asks about:

### Primary Triggers (tax & registration)
- "what compliance do I need for selling in Germany"
- "VAT registration threshold in France"
- "GST requirements for Australia"
- "tax obligations for UK e-commerce"
- "what certifications or permits needed for Japan market"

### Secondary Triggers (regulations & laws)
- "GDPR compliance for European customers"
- "consumer protection laws in Germany"
- "cooling-off period for Brazil"
- "product safety regulations for Australia"
- "data privacy laws in Japan (APPI/PIPA)"

### Tertiary Triggers (specific topics)
- "CE marking requirements for electronics"
- "UKCA marking post-Brexit"
- "PSE marking for Japan electronics"
- "customs duties for shipping to India"
- "cross-border payment regulations"
- "returns and refund policies in Netherlands"
- "language requirements for European websites"
- "Impressum requirement for German website"

## Workflow

1. **Receive input** — Parse target markets, business activities, and product types from natural language or structured input
2. **Map requirements** — Retrieve compliance database for each target market covering:
   - Tax/VAT registration thresholds and rates
   - Consumer protection laws and cooling-off periods
   - Data privacy regulations (GDPR, APPI, PIPEDA, LGPD)
   - Product safety markings (CE, UKCA, PSE, RCM, INMETRO)
   - Customs and import requirements
3. **Build roadmap** — Generate phased implementation roadmap with immediate (0-30 days), short-term (1-3 months), and ongoing actions
4. **Document framework** — List required documentation per market with localization and update frequency requirements
5. **Recommend professionals** — Suggest qualified specialists (tax advisors, legal counsel, customs brokers) needed for each market

## Input Format

Accepts natural language or structured JSON describing:
- Target markets (one or more countries)
- Business activities: online sales, data collection, physical goods shipping, digital products, B2B/B2C
- Product types: electronics, apparel, cosmetics, food supplements, children's products, etc.

Example natural language input:
- "what compliance requirements for selling cosmetics in Germany and France"
- "regulations for cross-border sales of electronics to Japan and Australia"

Example structured input (JSON):
```json
{
  "markets": ["DE", "FR", "AU"],
  "activities": ["online_sales", "data_collection"],
  "products": ["electronics", "accessories"]
}
```

## Output Structure

Returns JSON with the following top-level fields:

```json
{
  "input_analysis": {
    "detected_markets": ["DE", "FR"],
    "detected_activities": ["online_sales", "data_collection"],
    "detected_products": ["electronics"]
  },
  "compliance_requirements": {
    "DE": {
      "tax_vat": { "rate": "19%", "threshold": "€22,000", "registration_required": true },
      "consumer_protection": { "cooling_off_days": 14, "language": "German required" },
      "data_privacy": { "regulation": "GDPR", "dpiya_required": false },
      "product_safety": { "marking": "CE", "standard": "EN 60950" },
      "customs": { "duty_rate": "varies", "hs_code_required": true }
    }
  },
  "implementation_roadmap": {
    "immediate": ["Register for VAT", "Draft privacy policy"],
    "short_term": ["Obtain CE certification", "Set up local entity"],
    "ongoing": ["Monitor regulatory changes", "File periodic reports"]
  },
  "compliance_documentation_framework": {
    "DE": ["VAT registration certificate", "Privacy policy (German)", "Terms & conditions"],
    "FR": ["VAT registration", "Consumer rights notice", "Returns policy"]
  },
  "professional_consultation_recommendations": {
    "DE": ["German tax advisor (Steuerberater)", "EU data privacy lawyer"],
    "FR": ["French VAT consultant", "Consumer law specialist"]
  },
  "disclaimer": "Descriptive guidance only. Not professional legal, tax, or compliance advice..."
}
```

## Examples

### Example 1: Electronics to Germany and France
**Input:** "what compliance requirements do I need for selling electronics in Germany and France"

**Output:** Detailed mapping covering:
- VAT requirements: DE 19%, FR 20%, registration threshold €10,000 for OSS scheme
- Consumer protection: 14-day cooling-off period in both countries, German-language T&Cs required
- GDPR: appoint EU representative, data processing records required
- Product safety: CE marking mandatory, EN 60950 / EN 62368 standards
- Website requirements: German Impressum, French mention of seller
- Implementation roadmap with phased timeline
- Professional recommendations: German Steuerberater, French expert-comptable

### Example 2: Apparel to Japan and Australia
**Input:** "help me understand regulations for shipping apparel to Japan and Australia"

**Output:** Detailed mapping covering:
- Japan: consumption tax (10%), APPI data privacy compliance, product safety (no special marking for apparel), customs duties based on HS code, PSSA for children's garments
- Australia: GST (10%), ACMA requirements for online sellers, Privacy Act compliance, RCM not required for general apparel, customs processing requirements
- Documentation framework: Japanese-language product labels, country of origin marking
- Implementation roadmap for both markets

### Example 3: Health supplements to Brazil and Canada
**Input:** "regulations for selling health supplements cross-border to Brazil and Canada"

**Output:** Detailed mapping covering:
- Brazil: ICMS state tax, ANVISA registration required for supplements, LGPD data requirements, INMETRO standards for packaging
- Canada: GST/HST (5-15% depending on province), PIPEDA privacy compliance, Health Canada natural product number (NPN) may be required
- Customs: detailed ingredient declaration, certificates of analysis
- Professional recommendations: Brazilian regulatory consultant, Canadian customs broker

## Safety and Disclaimer

Descriptive guidance only. Not professional legal, tax, or compliance advice. Always verify with qualified legal counsel, tax advisor, or regulatory specialist before implementation. Regulations change frequently and vary by specific product type and business structure. This tool provides general information only and does not constitute a legal opinion or compliance guarantee.

## Acceptance Criteria

- Maps compliance requirements for at least 1 target market
- Provides implementation roadmap with clear timelines (immediate, short-term, ongoing phases)
- Includes compliance documentation framework listing required documents per market
- Recommends professional consultation specialists where appropriate
- Returns valid JSON with all documented fields present
- Contains complete safety disclaimer in every output
- Includes input_analysis summarizing parsed input
- Pure descriptive — no code execution, API calls, network access, file writes, or database operations
