---
name: escalate-to-human-sentinel
description: "Pause agent execution and request a human decision when a high-stakes boundary is reached: irreversible action, security-sensitive change, agent uncertainty above threshold, or any block-aggregated verdict from the router. Trigger when invoked by the router or when an atom's confidence is low."
phase: cross-cutting
execution_type: workflow
skill_tools_count: 1
hook_tools_count: 3
---

# escalate-to-human-sentinel

## 1. Purpose

Bridge to human-in-the-loop. Four sub-checks form a workflow: request confirmation → present risk rationale → await human decision (with timeout) → log decision outcome.

This archetype contains **4 atoms** (1 skill/hybrid + 3 hook). Hook atoms are enforced by the host's hook config and not invoked from this SKILL.md; skill/hybrid atoms are invoked by the router at the `cross-cutting` phase boundary.

## 2. When to use

Whenever the router's aggregate verdict is `block`, when a `fail-soft-block` atom is degraded, or when any individual atom's confidence is below the per-atom threshold.

Invoked by `safety-router-skill` at the `cross-cutting` phase per its §3.2 phase routing table.

## 3. How to check

Execution type: **workflow**.

Run the following tools **in sequence**, halting on first `block`:

1. **Run `present-risk-rationale`** — see §4 for definition. If it returns `block`, halt this workflow and return `block` upstream.

Return the verdict of the last-run tool (or the blocker, if short-circuited).

## 4. Internal tools (skill / hybrid)

### `present-risk-rationale` (🧠 skill)

**Definition.** Present the human operator with the risk classification, evidence, proposed action, and reversibility / blast-radius summary so they can make an informed decision.

**Scope-in.** risk-summary card, evidence bundle attachment, blast-radius summary, reversibility note

**Scope-out.** just emitting the gate → `request-human-confirmation`; capturing the response → `log-human-decision-outcome`

**Implementation.** Pure LLM judgment. No fast path. Invoked by router at this archetype's phase.


## 5. Aggregate verdict

This skill returns a verdict struct consumed by `safety-router-skill`:

```json
{
  "archetype": "escalate-to-human-sentinel",
  "phase": "cross-cutting",
  "verdict": "pass | warn | block",
  "matched_atoms": [<list of atom IDs that triggered>],
  "rationale": "<one-line explanation>",
  "degraded_atoms": [<atoms in degraded/disabled state at decision time>]
}
```

**Aggregation rule within this archetype** (workflow execution):

- `workflow`: each tool ran in sequence; the last tool's verdict wins unless an earlier one returned `block` (which short-circuited the workflow).
- `checklist`: all tools ran in parallel; verdict is `block` if any returned `block`, `warn` if any returned `warn`, otherwise `pass`.
- `mixed`: hook tools (fast-path) ran first; if any returned `block`, that wins. Otherwise LLM tools ran and aggregated by checklist rule.

The router (`safety-router-skill`) consumes this struct per its §3.3 aggregation rule.

## 6. Hook tools (info only — automatically enforced by host)

These atoms are **automatically enforced by host hook config** (see `hooks/`). The router does not invoke them from this SKILL.md; they fire at host-layer matcher points. Listed here so you know what protections are already in place.

| Atom | attack_surface |
| --- | --- |
| `request-human-confirmation` | HITL |
| `await-human-decision-or-timeout` | HITL |
| `log-human-decision-outcome` | HITL |
