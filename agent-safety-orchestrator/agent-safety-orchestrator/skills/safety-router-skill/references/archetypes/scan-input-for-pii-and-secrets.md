---
name: scan-input-for-pii-and-secrets
description: "Detect PII, payment card data, credentials, and private keys in user input or pasted content, before that content reaches downstream tools or logs. Trigger on every new user message and on any large paste. Hook tools catch high-confidence patterns (credit cards, AWS keys); LLM tools catch contextual leaks (names tied to addresses, etc.)."
phase: input-understanding
execution_type: mixed
skill_tools_count: 2
hook_tools_count: 3
---

# scan-input-for-pii-and-secrets

## 1. Purpose

Stop user-provided sensitive data from leaking into tool calls, logs, or generated artifacts. Five categories are scanned: general PII (name+address pairs, ID numbers), payment card data, generic credentials, private keys, and the redaction operation itself.

This archetype contains **5 atoms** (2 skill/hybrid + 3 hook). Hook atoms are enforced by the host's hook config and not invoked from this SKILL.md; skill/hybrid atoms are invoked by the router at the `input-understanding` phase boundary.

## 2. When to use

Every new user message. Especially on pasted blocks > 200 chars. Also called by `redact-sensitive-output` archetype as a pre-output sweep.

Invoked by `safety-router-skill` at the `input-understanding` phase per its §3.2 phase routing table.

## 3. How to check

Execution type: **mixed**.

**Step 1 — fast path.** Host hook config has already run the hook portion of any hybrid atom. Read recent tool results / hook events for `block` or `warn` markers from these atoms before invoking any LLM tools.

**Step 2 — LLM fallback.** For each of the following skill/hybrid LLM tools, invoke only if the fast path returned `pass` or `inconclusive`:

- `detect-pii-in-input`
- `detect-credential-in-input`

Aggregate by: hook `block` wins; otherwise checklist rule over LLM tools.

## 4. Internal tools (skill / hybrid)

### `detect-pii-in-input` (⚡ hybrid)

**Definition.** Detect PII (names, addresses, emails, phone numbers, SSN/government IDs, biometrics) in user-supplied input before it gets logged / forwarded to external tools.

**Scope-in.** regex / NER PII detection on user message, GDPR / HIPAA category classification, government ID format validation, medical record numbers (MRN / NHS), crypto-wallet address (BTC / ETH / etc.)

**Scope-out.** PII in agent **output** → `redact-output-pii`; payment card specifically → `detect-payment-card-data`; auth tokens → `detect-credential-in-input`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.

### `detect-credential-in-input` (⚡ hybrid)

**Definition.** Detect API keys, OAuth tokens, JWT, session cookies, cloud access keys, database connection strings in user input or pasted content.

**Scope-in.** AWS/GCP/Azure key patterns, OpenAI/Anthropic key prefixes, JWT structure, generic high-entropy string detection, .env content paste

**Scope-out.** private signing keys → `detect-private-key-input`; secrets in code repositories → `detect-hardcoded-secret-in-code`; secrets in tool **arguments** → `detect-secret-in-args`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.


## 5. Aggregate verdict

This skill returns a verdict struct consumed by `safety-router-skill`:

```json
{
  "archetype": "scan-input-for-pii-and-secrets",
  "phase": "input-understanding",
  "verdict": "pass | warn | block",
  "matched_atoms": [<list of atom IDs that triggered>],
  "rationale": "<one-line explanation>",
  "degraded_atoms": [<atoms in degraded/disabled state at decision time>]
}
```

**Aggregation rule within this archetype** (mixed execution):

- `workflow`: each tool ran in sequence; the last tool's verdict wins unless an earlier one returned `block` (which short-circuited the workflow).
- `checklist`: all tools ran in parallel; verdict is `block` if any returned `block`, `warn` if any returned `warn`, otherwise `pass`.
- `mixed`: hook tools (fast-path) ran first; if any returned `block`, that wins. Otherwise LLM tools ran and aggregated by checklist rule.

The router (`safety-router-skill`) consumes this struct per its §3.3 aggregation rule.

## 6. Hook tools (info only — automatically enforced by host)

These atoms are **automatically enforced by host hook config** (see `hooks/`). The router does not invoke them from this SKILL.md; they fire at host-layer matcher points. Listed here so you know what protections are already in place.

| Atom | attack_surface |
| --- | --- |
| `detect-payment-card-data` | PCI DSS |
| `detect-private-key-input` | OWASP LLM02.crypto |
| `redact-input-pii` | OWASP LLM02.preprocess |
