---
name: compliance-checker
description: Verify product listings, promotional claims, and creator practices against TikTok Shop policies to catch violations before they trigger penalties.
---

# Compliance Checker

TikTok Shop enforces strict policies on product listings, promotional claims, and creator content. Violations can lead to listing removal, account suspension, or permanent bans — often without warning. This skill helps ecommerce operators proactively audit their listings, ad copy, and creator deliverables against known TikTok Shop policy requirements, catching problems before the platform does.

## Use when

- You are about to publish a new TikTok Shop product listing and want to verify the title, images, and description meet current platform guidelines before going live
- A creator has submitted a draft video or caption for your product and you need to check whether the health claims, discount language, or before-after comparisons comply with TikTok Shop advertising rules
- You received a policy warning or listing suppression notice from TikTok Shop and want to audit your entire active catalog for similar violations across titles, descriptions, and images
- Your team is running a flash sale or promotional campaign and you need to confirm that countdown language, price strike-throughs, and urgency claims follow TikTok Shop promotional content guidelines

## What this skill does

This skill systematically reviews the text content of your product listings, promotional copy, and creator scripts against TikTok Shop's published policy categories. It checks for prohibited claims (such as unsubstantiated health benefits, fake scarcity language, or misleading before-after imagery descriptions), restricted product category language, required disclosures, and formatting violations. The analysis covers title compliance, bullet point and description review, promotional claim validation, and creator content script checks. It flags specific phrases or patterns that are known to trigger automated enforcement and suggests compliant alternatives.

## Inputs required

- **Listing content** (required): The full product title, description, bullet points, and any promotional taglines you want checked. Paste the exact text as it appears or will appear on TikTok Shop.
- **Content type** (required): Specify whether this is a product listing, ad creative copy, creator script, or promotional campaign material — each has different policy thresholds.
- **Product category** (required): The TikTok Shop category the product is listed under (e.g., Beauty & Personal Care, Health Supplements, Electronics). Category-specific rules vary significantly.
- **Target market** (optional): The country or region where the listing will be active. Policy enforcement intensity and specific rules differ between US, UK, and Southeast Asian markets.

## Output format

The output is a structured compliance report with four sections. First, a compliance status summary showing an overall pass, warning, or fail rating with a count of issues found by severity. Second, a line-by-line audit table listing each flagged phrase or pattern, the specific policy rule it may violate, the severity level (critical, warning, or advisory), and a suggested compliant replacement. Third, a category-specific checklist confirming whether required disclosures, restricted keywords, and mandatory label language for the product category are present or missing. Fourth, an action plan prioritizing fixes by enforcement risk, with the most likely triggers for automated takedown listed first.

## Scope

- Designed for: TikTok Shop sellers, ecommerce operators, and brand teams managing creator content
- Platform context: TikTok Shop (US, UK, Southeast Asia)
- Language: English

## Limitations

- Policy rules are based on publicly available TikTok Shop guidelines and may not reflect the most recent unpublished enforcement changes or internal policy updates
- This skill reviews text content only and cannot analyze actual images, videos, or audio for compliance
- Results are advisory and do not guarantee that a listing will pass TikTok Shop's automated or manual review process
