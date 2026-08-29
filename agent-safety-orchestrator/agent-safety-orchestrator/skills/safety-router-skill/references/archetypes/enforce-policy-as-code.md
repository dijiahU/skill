---
name: enforce-policy-as-code
description: "Evaluate the proposed agent plan against organization policy expressed as code (OPA/Rego rules or content-moderation rules). Trigger in the planning phase after the agent has a draft plan but before tool calls begin. Blocks plans that violate explicit org policy."
phase: planning
execution_type: checklist
skill_tools_count: 1
hook_tools_count: 1
---

# enforce-policy-as-code

## 1. Purpose

Run the proposed plan through a deterministic policy engine (OPA / Rego) and an LLM content-moderation check before any tool is invoked. The OPA path is hook-fast; the moderation path is the LLM-hybrid fallback.

This archetype contains **2 atoms** (1 skill/hybrid + 1 hook). Hook atoms are enforced by the host's hook config and not invoked from this SKILL.md; skill/hybrid atoms are invoked by the router at the `planning` phase boundary.

## 2. When to use

Planning phase, every time the agent has finalized a plan structure with concrete tools/resources. Skip only when the plan touches zero external resources (pure-text Q&A).

Invoked by `safety-router-skill` at the `planning` phase per its §3.2 phase routing table.

## 3. How to check

Execution type: **checklist**.

Run **all** of the following tools **in parallel**, aggregate by checklist rule (`block` wins, then `warn`, else `pass`):

- `evaluate-content-moderation-rule` (see §4)

Do not skip any tool unless its `helpers/health_status.py` reports the atom as `disabled`.

## 4. Internal tools (skill / hybrid)

### `evaluate-content-moderation-rule` (⚡ hybrid)

**Definition.** Apply explicit content moderation rules (toxicity / hate speech / NSFW / disinformation flags) as a planning gate, not just on output.

**Scope-in.** classifier-as-policy, content moderation API gate, planning-time content rejection

**Scope-out.** post-generation output review → `enforce-disallowed-content-rule`; agent-output safety more generally → archetype `enforce-output-content-policy`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.


## 5. Aggregate verdict

This skill returns a verdict struct consumed by `safety-router-skill`:

```json
{
  "archetype": "enforce-policy-as-code",
  "phase": "planning",
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

These atoms are **automatically enforced by host hook config** (see `hooks/`). The router does not invoke them from this SKILL.md; they fire at host-layer matcher points. Listed here so you know what protections are already in place.

| Atom | attack_surface |
| --- | --- |
| `evaluate-opa-rego-rule` | policy-as-code |
