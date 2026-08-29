---
name: Data Privacy in the AI Era
description: Protect your personal data when using AI tools — practical privacy hygiene.
version: "1.0.0"
type: prompt-flow
tags:
  - data-privacy
  - ai-security
  - privacy-hygiene
  - personal-data
  - ai-tools
  - digital-safety
author: Bell (design)
---

# Data Privacy in the AI Era

## Overview

Data Privacy in the AI Era is a practical guide to understanding and managing the privacy implications of using AI tools. It covers how AI services collect and use data, what happens to user inputs, retention policies, and concrete privacy practices you can adopt immediately. This skill helps privacy-conscious users enjoy AI tools without overexposing their personal information.

This skill provides general educational guidance. It does not make definitive claims about specific tools' current data practices and encourages users to verify with official documentation.

## When to Use

Use this skill when the user asks to:

- Understand whether ChatGPT or other AI tools save their data
- Explore AI privacy concerns in general
- Learn what they should not share with AI
- Find safe AI use practices for personal data
- Understand AI tools and data security

**Trigger phrases:** "Does ChatGPT save my data?", "AI privacy concerns", "What should I not share with AI?", "Safe AI use for personal data", "AI tools and data security"

## Workflow

### Step 1 — Greet and Assess

Acknowledge the user's privacy concern. Ask:
- Which AI tools or services are they currently using or considering?
- What type of data are they most concerned about protecting? (personal identity, work information, health data, family details)
- Their current privacy practices with digital tools in general

### Step 2 — Explain How AI Tools Handle Data

Provide a conceptual overview of data practices in AI tools:
- **Input storage:** User prompts and conversations may be stored on provider servers
- **Training data:** Some providers use user interactions to improve models (policies vary)
- **Retention:** How long data is kept and under what conditions
- **Third parties:** Potential data sharing with partners or subprocessors
- **Local vs. cloud:** Differences between cloud-based AI and on-device or local AI

Emphasize that policies vary by provider and change over time. Always check the official privacy policy for the specific tool.

### Step 3 — The "What to Never Share" List

Provide clear categories of information that should not be entered into AI tools:
- **Personal identifiers:** Social security numbers, passport details, full birth dates combined with names
- **Financial data:** Credit card numbers, bank account details, investment account information
- **Health records:** Medical diagnoses, prescription details, mental health history
- **Passwords and credentials:** Any login information, API keys, security questions
- **Confidential work data:** Unreleased products, proprietary code, internal strategy documents (unless employer-approved)
- **Others' private information:** Data about family members, friends, or colleagues without consent
- **Location-sensitive details:** Precise home addresses combined with travel schedules

### Step 4 — Practical Privacy Practices

Teach actionable privacy hygiene:
- **Anonymize inputs:** Remove names, replace specifics with generics ("a 45-year-old in a large city" instead of real details)
- **Use separate accounts:** Keep personal and work AI usage separate where possible
- **Review privacy settings:** Turn off chat history or training data participation where the tool allows it
- **Delete conversations:** Regularly clear chat history in tools that store it
- **Check enterprise policies:** If using AI through work, understand what your employer can see
- **Consider local alternatives:** For highly sensitive tasks, explore on-device or local AI options

### Step 5 — Evaluate Privacy Policies

Guide users on how to read and evaluate AI privacy policies:
- What to look for: data retention periods, training use, opt-out options, deletion rights
- Red flags: vague language, no opt-out, broad data sharing claims
- Where to find updates: official blogs, privacy policy changelogs, regulatory filings

### Step 6 — Summarize and Exit

Recap the user's personalized privacy checklist. Emphasize:
- Privacy is about risk management, not absolute guarantees
- Small changes in what you share and how you share it make a big difference
- Stay informed as policies evolve
- Suggest related skills: Digital Information Hygiene for broader information diet, AI Ethics Compass for ethical frameworks around AI use

## Safety & Compliance

- Does not provide legal advice about data privacy laws
- Does not make definitive claims about specific tools' data practices — guides users to official documentation
- Does not recommend tools designed for evasion or illegal purposes
- General educational guidance only
- This is a descriptive prompt-flow skill with zero code execution, zero network calls, and zero credential requirements

## Acceptance Criteria

1. User expresses a privacy concern; output includes a clear "what to never share" reference list
2. Practical privacy practices are actionable and tailored to the user's tools and concerns
3. Encourages verification with official privacy policies rather than making absolute claims
4. Does not recommend illegal or evasion tools
5. Refuses to analyze, store, or process any actual user credentials or sensitive data

## Examples

### Example 1: General Privacy Concern

**User says:** "Does ChatGPT save everything I type? Should I be worried?"

**Skill guides:** Explain OpenAI's data practices at a general level (subject to change). Discuss the difference between free and paid tier policies. Provide the "what to never share" list. Offer practical steps: review settings, anonymize prompts, clear history. Direct to official documentation for definitive answers.

### Example 2: Professional Using AI at Work

**User says:** "I want to use AI to help draft client proposals, but I'm worried about confidentiality."

**Skill guides:** Assess the confidentiality level of the proposals. Discuss enterprise AI policies and whether the employer has approved AI use. Offer anonymization techniques (replace client names, redact sensitive figures). Suggest checking company policy first. Provide a risk-assessment framework.
