---
name: enforce-rate-and-quota-limits
description: "Enforce per-session rate limits, token budgets, cost caps, and runaway-loop detection on the agent's tool calls. Trigger on every tool invocation. Hook tools enforce hard caps deterministically; LLM hybrid catches subtle loop patterns."
phase: tool-invocation
execution_type: mixed
skill_tools_count: 1
hook_tools_count: 3
---

# enforce-rate-and-quota-limits

## 1. Purpose

Bound the agent's runtime cost and prevent runaway loops. Four sub-checks: per-call rate limit, cumulative token budget, monetary cost cap, runaway-loop detection.

This archetype contains **4 atoms** (1 skill/hybrid + 3 hook). Hook atoms are enforced by the host's hook config and not invoked from this SKILL.md; skill/hybrid atoms are invoked by the router at the `tool-invocation` phase boundary.

## 2. When to use

Every tool call. Hook fast-path runs on every tool; LLM fallback is invoked when the loop-detection heuristic flags suspicious patterns.

Invoked by `safety-router-skill` at the `tool-invocation` phase per its §3.2 phase routing table.

## 3. How to check

Execution type: **mixed**.

**Step 1 — fast path.** Host hook config has already run the hook portion of any hybrid atom. Read recent tool results / hook events for `block` or `warn` markers from these atoms before invoking any LLM tools.

**Step 2 — LLM fallback.** For each of the following skill/hybrid LLM tools, invoke only if the fast path returned `pass` or `inconclusive`:

- `detect-runaway-loop`

Aggregate by: hook `block` wins; otherwise checklist rule over LLM tools.

## 4. Internal tools (skill / hybrid)

### `detect-runaway-loop` (⚡ hybrid)

**Definition.** Detect agent loops (same tool call N times, agent stuck oscillating, tool recursion) and break out before resource exhaustion.

**Scope-in.** same-call detection, oscillation detection, per-tool repeat-count gate, recursion-depth check

**Scope-out.** budget-only enforcement → `enforce-cost-cap-per-task`; archive-bomb → `detect-archive-bomb`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.


## 5. Aggregate verdict

This skill returns a verdict struct consumed by `safety-router-skill`:

```json
{
  "archetype": "enforce-rate-and-quota-limits",
  "phase": "tool-invocation",
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
| `enforce-tool-call-rate-limit` | DoS |
| `enforce-token-budget-cap` | OWASP LLM10.token-budget |
| `enforce-cost-cap-per-task` | cost-cap |
