---
name: incident-response-handler
description: "Coordinate response to detected safety incidents: halt in-flight action, snapshot agent state, isolate affected resource, notify oncall + open ticket, execute recovery playbook. Trigger when any other safety skill returns `block` verdict or when a `fail-closed` atom degrades."
phase: cross-cutting
execution_type: workflow
skill_tools_count: 1
hook_tools_count: 4
---

# incident-response-handler

## 1. Purpose

Coordinate the response to a detected safety incident. Five sub-checks form a workflow: halt → snapshot → isolate → notify → execute playbook.

This archetype contains **5 atoms** (1 skill/hybrid + 4 hook). Hook atoms are enforced by the host's hook config and not invoked from this SKILL.md; skill/hybrid atoms are invoked by the router at the `cross-cutting` phase boundary.

## 2. When to use

Event-driven. Invoked by the router when any archetype returns `block`, or when a `fail-closed` atom (e.g., signature verification, dependency confusion) fails.

Invoked by `safety-router-skill` at the `cross-cutting` phase per its §3.2 phase routing table.

## 3. How to check

Execution type: **workflow**.

Run the following tools **in sequence**, halting on first `block`:

1. **Run `execute-recovery-playbook`** — see §4 for definition. If it returns `block`, halt this workflow and return `block` upstream.

Return the verdict of the last-run tool (or the blocker, if short-circuited).

## 4. Internal tools (skill / hybrid)

### `execute-recovery-playbook` (⚡ hybrid)

**Definition.** Execute a predefined recovery playbook (restore from backup, roll back commit, rotate credentials, redeploy clean image) automatically or with one-click.

**Scope-in.** playbook executor, restore-from-backup runbook, credential-rotation runbook, redeploy runbook

**Scope-out.** snapshot capture → `snapshot-agent-state`; IR ticket → `notify-oncall-and-open-ticket`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.


## 5. Aggregate verdict

This skill returns a verdict struct consumed by `safety-router-skill`:

```json
{
  "archetype": "incident-response-handler",
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
| `halt-in-flight-action` | agent-IR |
| `snapshot-agent-state` | agent-IR |
| `isolate-affected-resource` | agent-IR |
| `notify-oncall-and-open-ticket` | agent-IR |
