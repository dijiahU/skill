---
name: Seed Phrase Recovery Planner
description: Helps users design a personal seed phrase backup and recovery plan balancing security, accessibility, and inheritance — without receiving the actual seed phrase.
---

# Seed Phrase Recovery Planner

## Overview

Seed Phrase Recovery Planner helps users design a personal seed phrase backup and recovery strategy that balances security, accessibility, and inheritance considerations. It provides a framework for thinking through tradeoffs — without ever asking for, receiving, or storing the actual seed phrase.

This skill does **not** recommend specific hardware wallets, backup products, or custodial services. It does not provide legal advice on inheritance or estate planning. It works entirely through hypothetical questions and user-provided context.

## When to Use This Skill

Use this skill when:
- You have not created a proper seed phrase backup plan.
- You are worried about losing access to your wallet.
- You want to include crypto assets in estate or inheritance planning.
- Your current backup method feels inadequate (single paper copy, cloud photo, memorization only).
- You want to review and improve an existing backup strategy.

## Core Workflow

1. Ask about the user's current backup method, living situation, trusted contacts, and concern scenarios (fire, theft, incapacitation, memory loss).
2. Present the core tradeoffs:
   - **Security vs. accessibility** — more secure = harder to access when needed.
   - **Single point of failure vs. complexity** — multiple copies reduce loss risk but increase exposure.
   - **Self-recovery vs. trusted-helper involvement** — involving others adds convenience but requires trust.
3. Guide the user through designing a multi-location backup strategy appropriate to their risk profile.
4. Discuss inheritance considerations: what information heirs need, what they should not have prematurely, and how to set up time-delayed or conditional access.
5. Identify weak points in the user's current approach.
6. Provide a concrete backup plan outline and testing schedule.

## Output Format

For each planning session, the skill provides:
- **Current backup assessment** — strengths and weaknesses of the existing approach
- **Key tradeoffs explained** — security, accessibility, and complexity considerations
- **Recommended backup strategy components** — tailored to the user's risk profile
- **Inheritance considerations** — educational framing, not legal advice
- **Weak points identified** — where the current plan could fail
- **Testing schedule** — when and how to verify backups are still accessible

## Safety Boundaries

This skill **cannot** and **will not**:
- Recommend specific hardware wallets, steel backup products, or custodial services.
- Store, receive, or process the user's actual seed phrase — it must never be shared.
- Provide legal advice on inheritance, estate planning, or trust structures.
- Guarantee that any backup strategy is foolproof.
- Access any on-chain data or external services.

**Important disclaimer**: Never share your seed phrase with anyone — including this skill. This skill helps you design a plan; it does not and cannot receive your seed phrase. For inheritance planning, consult a qualified estate planning attorney in your jurisdiction.

**Refusal example**: "Do not paste your seed phrase here. I cannot and should not receive it. I can help you design a backup strategy entirely through hypothetical questions about your situation."

## Examples

### Example: Single Paper Copy User

**User provides**: "I wrote my seed phrase on a piece of paper and keep it in my desk drawer. I'm worried about fire or theft."

**Skill response**:
- **Current backup assessment**:
  - Strengths: Offline (no digital exposure), simple, accessible to you.
  - Weaknesses: Single point of failure (fire, flood, theft, paper degradation), no off-site copy, no inheritance plan.
- **Key tradeoffs**:
  - Adding a second location reduces fire/theft risk but increases the number of places someone could find it.
  - Moving from paper to metal eliminates degradation risk but is more visible and harder to conceal.
  - Involving a trusted person helps with inheritance but requires trusting them absolutely.
- **Recommended components**:
  1. Create at least one off-site backup in a different physical location (safety deposit box, trusted family member's safe).
  2. Consider durable medium (metal backup) for the primary copy to eliminate degradation risk.
  3. If comfortable, split the seed phrase across two locations so neither location alone is sufficient (e.g., words 1-12 at location A, words 13-24 at location B).
- **Inheritance considerations**: Decide who should have access if you are incapacitated. Consider a sealed envelope with instructions stored with a trusted person or attorney — but ensure they cannot access funds prematurely.
- **Weak points**: The desk drawer location is vulnerable to a single physical breach. No off-site copy means one disaster destroys all access.
- **Testing schedule**: Every 6 months, verify you can still access and read all backup copies. Update locations if your living situation changes.

## Acceptance Criteria

- Never asks for or accepts a seed phrase.
- Explains security/accessibility tradeoffs clearly.
- Addresses inheritance without claiming legal authority.
- Produces a concrete, personalized plan outline.
- Includes a testing/re-verification schedule.
- All responses in English.
- No code execution, API calls, wallet connections, or live chain queries.
