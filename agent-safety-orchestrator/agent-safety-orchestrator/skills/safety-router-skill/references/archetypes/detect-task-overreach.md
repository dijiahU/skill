---
name: detect-task-overreach
description: "Compare the agent's proposed plan to the stated user intent and flag scope creep, unjustified side-effects, autonomy budget over-runs, or undeclared side-effects. Trigger in the planning phase. This is the primary defense against agents that 'helpfully' do more than asked."
phase: planning
execution_type: workflow
skill_tools_count: 3
hook_tools_count: 1
---

# detect-task-overreach

## 1. Purpose

Catch the agent doing more than the user asked for. Four sub-checks: plan-vs-intent comparison, unjustified-side-effect flag, autonomy-budget exceeded check, and side-effect enumeration.

This archetype contains **4 atoms** (3 skill/hybrid + 1 hook). Hook atoms are enforced by the host's hook config and not invoked from this SKILL.md; skill/hybrid atoms are invoked by the router at the `planning` phase boundary.

## 2. When to use

Planning phase, after the plan exists. Critical for autonomous / long-running tasks where scope creep compounds.

Invoked by `safety-router-skill` at the `planning` phase per its §3.2 phase routing table.

## 3. How to check

Execution type: **workflow**.

Run the following tools **in sequence**, halting on first `block`:

1. **Run `compare-plan-vs-stated-intent`** — see §4 for definition. If it returns `block`, halt this workflow and return `block` upstream.
2. **Run `flag-unjustified-side-effect`** — see §4 for definition. If it returns `block`, halt this workflow and return `block` upstream.
3. **Run `enumerate-task-side-effects`** — see §4 for definition. If it returns `block`, halt this workflow and return `block` upstream.

Return the verdict of the last-run tool (or the blocker, if short-circuited).

## 4. Internal tools (skill / hybrid)

### `compare-plan-vs-stated-intent` (🧠 skill)

**Definition.** Compare the agent's generated plan against the user's elicited intent and return a similarity / divergence score.

**Scope-in.** plan-intent embedding similarity, plan-step justification labeling, scope-divergence scoring

**Scope-out.** just listing side effects → `enumerate-task-side-effects`; flagging specific steps → `flag-unjustified-side-effect`

**Implementation.** Pure LLM judgment. No fast path. Invoked by router at this archetype's phase.

### `flag-unjustified-side-effect` (🧠 skill)

**Definition.** Identify individual planned steps whose side effects (writes / sends / spends) are not justified by the user-stated goal.

**Scope-in.** per-step justification check, "why is this step needed" annotation enforcement, unjustified-write detection

**Scope-out.** blanket plan/intent comparison → `compare-plan-vs-stated-intent`; budget-based limits → `detect-autonomy-budget-exceeded`

**Implementation.** Pure LLM judgment. No fast path. Invoked by router at this archetype's phase.

### `enumerate-task-side-effects` (🧠 skill)

**Definition.** Enumerate all observable side effects of a planned multi-step task (writes, network calls, money moves, message sends, state mutations) before any action is taken.

**Scope-in.** side-effect graph extraction from plan, write-set / read-set analysis, money-flow extraction, dry-run side-effect listing

**Scope-out.** comparing those side effects against user intent → `compare-plan-vs-stated-intent`; flagging unjustified ones → `flag-unjustified-side-effect`; per-call budget gate → `detect-autonomy-budget-exceeded`

**Implementation.** Pure LLM judgment. No fast path. Invoked by router at this archetype's phase.


## 5. Aggregate verdict

This skill returns a verdict struct consumed by `safety-router-skill`:

```json
{
  "archetype": "detect-task-overreach",
  "phase": "planning",
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
| `detect-autonomy-budget-exceeded` | OWASP LLM06.autonomy-budget |
