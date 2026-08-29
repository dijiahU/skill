---
name: enforce-output-content-policy
description: "Apply content-policy review on generated code, generated messages, generated file writes, and detect dangerous instructions or disallowed-content rule violations in agent output. Trigger before every output_generation phase. Heavily LLM-driven (3 of 5 atoms are skill-mode)."
phase: output-generation
execution_type: checklist
skill_tools_count: 5
hook_tools_count: 0
---

# enforce-output-content-policy

## 1. Purpose

Final-stage content policy enforcement on agent output. Five sub-checks: code review, message review, file-write review, dangerous-instruction detection, disallowed-content rule enforcement.

This archetype contains **5 atoms** (5 skill/hybrid + 0 hook). Hook atoms are enforced by the host's hook config and not invoked from this SKILL.md; skill/hybrid atoms are invoked by the router at the `output-generation` phase boundary.

## 2. When to use

Every output. The most LLM-heavy archetype (3 skill + 2 hybrid) — expect ~1-2s latency per output.

Invoked by `safety-router-skill` at the `output-generation` phase per its §3.2 phase routing table.

## 3. How to check

Execution type: **checklist**.

Run **all** of the following tools **in parallel**, aggregate by checklist rule (`block` wins, then `warn`, else `pass`):

- `review-generated-code-output` (see §4)
- `review-generated-message-output` (see §4)
- `review-generated-file-write` (see §4)
- `detect-dangerous-instruction-in-output` (see §4)
- `enforce-disallowed-content-rule` (see §4)

Do not skip any tool unless its `helpers/health_status.py` reports the atom as `disabled`.

## 4. Internal tools (skill / hybrid)

### `review-generated-code-output` (⚡ hybrid)

**Definition.** Review code blocks / scripts in agent output for dangerous instructions (rm -rf, curl|bash, fork bomb, hardcoded backdoor) before showing to user.

**Scope-in.** dangerous-shell-pattern in code block, suspicious `curl ... | sh`, fork-bomb pattern, backdoor-pattern in generated code

**Scope-out.** SAST on user-supplied code → `run-sast-scan`; tool-arg shell injection → `detect-shell-command-injection`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.

### `review-generated-message-output` (🧠 skill)

**Definition.** Review free-text agent messages (replies / emails / Slack / PR comments) for policy-prohibited content, false claims with high confidence, or operator-impersonation.

**Scope-in.** outgoing-message review, false-claim hedging enforcement, impersonation gate, persuasion-tactic flag

**Scope-out.** code-block review → `review-generated-code-output`; secret in message → `redact-output-secret`

**Implementation.** Pure LLM judgment. No fast path. Invoked by router at this archetype's phase.

### `review-generated-file-write` (🧠 skill)

**Definition.** Review the content the agent is about to write to a file before the write commits (config files, code files, env files).

**Scope-in.** pre-write content scan, env-file write gate, config-write content review, drop-into-prod gate

**Scope-out.** filesystem boundary → `enforce-filesystem-sandbox`; SAST on the new code → `run-sast-scan`

**Implementation.** Pure LLM judgment. No fast path. Invoked by router at this archetype's phase.

### `detect-dangerous-instruction-in-output` (🧠 skill)

**Definition.** Detect dangerous operational instructions in agent output (instructions to user that could harm them or third parties: malware-write, unsafe medical/legal advice, financial-fraud guidance).

**Scope-in.** harmful-instruction classifier, dual-use-output filter, dangerous-advice gating

**Scope-out.** pure toxicity / NSFW (planning-side) → `evaluate-content-moderation-rule`; code-block scan → `review-generated-code-output`

**Implementation.** Pure LLM judgment. No fast path. Invoked by router at this archetype's phase.

### `enforce-disallowed-content-rule` (⚡ hybrid)

**Definition.** Apply the deployer's disallowed-content rule pack to agent output post-generation (block / rewrite / escalate / redact).

**Scope-in.** output-side content rule pack, classifier-as-policy on output, post-gen rewrite, post-gen escalation

**Scope-out.** pre-planning content moderation → `evaluate-content-moderation-rule`; system-prompt redaction → `redact-output-system-prompt`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.


## 5. Aggregate verdict

This skill returns a verdict struct consumed by `safety-router-skill`:

```json
{
  "archetype": "enforce-output-content-policy",
  "phase": "output-generation",
  "verdict": "pass | warn | block",
  "matched_atoms": [<list of atom IDs that triggered>],
  "rationale": "<one-line explanation>",
  "degraded_atoms": [<atoms in degraded/disabled state at decision time>]
}
```

**Aggregation rule within this archetype** (checklist execution):

- `workflow`: each tool ran in sequence; the last tool's verdict wins unless an earlier one returned `block` (which short-circuited the workflow).
- `checklist`: all tools ran in parallel; verdict is `block` if any returned `block`, `warn` if any returned `warn`, otherwise `pass`.
- `mixed`: hook tools (fast-path) ran first; if any returned `block`, that wins. Otherwise LLM tools ran and aggregated by checklist rule.

The router (`safety-router-skill`) consumes this struct per its §3.3 aggregation rule.

## 6. Hook tools (info only — automatically enforced by host)

_(All atoms in this archetype are skill/hybrid — no pure-hook tools to cross-reference.)_
