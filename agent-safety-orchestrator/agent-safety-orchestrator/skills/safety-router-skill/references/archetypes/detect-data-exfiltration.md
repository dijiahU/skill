---
name: detect-data-exfiltration
description: "Detect covert exfiltration channels in agent output or tool calls: markdown image beacons (img tags pointing to attacker-controlled URLs with payload in path), base64-encoded payloads, DNS-exfiltration patterns, and covert channels embedded in tool call arguments. Trigger before output_generation and on every tool call."
phase: output-generation
execution_type: checklist
skill_tools_count: 2
hook_tools_count: 2
---

# detect-data-exfiltration

## 1. Purpose

Block agent-mediated data leakage via covert channels. Four sub-checks cover markdown-image beacons, base64 payloads in output, DNS-exfiltration domain patterns, and covert channels in tool call arguments.

This archetype contains **4 atoms** (2 skill/hybrid + 2 hook). Hook atoms are enforced by the host's hook config and not invoked from this SKILL.md; skill/hybrid atoms are invoked by the router at the `output-generation` phase boundary.

## 2. When to use

Output-generation phase for markdown/HTML outputs (especially with embedded images), and tool-invocation phase for any tool call that constructs a URL or arbitrary string argument.

Invoked by `safety-router-skill` at the `output-generation` phase per its §3.2 phase routing table.

## 3. How to check

Execution type: **checklist**.

Run **all** of the following tools **in parallel**, aggregate by checklist rule (`block` wins, then `warn`, else `pass`):

- `detect-base64-payload-in-output` (see §4)
- `detect-covert-channel-in-tool-call` (see §4)

Do not skip any tool unless its `helpers/health_status.py` reports the atom as `disabled`.

## 4. Internal tools (skill / hybrid)

### `detect-base64-payload-in-output` (⚡ hybrid)

**Definition.** Detect long base64 / hex / URL-encoded blobs in agent output that could carry exfiltrated data.

**Scope-in.** long-base64 detection in output, hex/url-encoded long-string detection, suspicious-encoding pattern

**Scope-out.** detected secret strings → `redact-output-secret`; image beacon URLs → `detect-markdown-image-beacon`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.

### `detect-covert-channel-in-tool-call` (⚡ hybrid)

**Definition.** Detect covert exfiltration in legitimate-looking tool calls (data hidden in HTTP headers, in user-agent, in cookie values, in webhook fields the user didn't ask about).

**Scope-in.** HTTP header content inspection, user-agent abuse, cookie-content leak, webhook-field exfil

**Scope-out.** arg-level secret leak → `detect-secret-in-args`; URL beacon → `detect-markdown-image-beacon`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.


## 5. Aggregate verdict

This skill returns a verdict struct consumed by `safety-router-skill`:

```json
{
  "archetype": "detect-data-exfiltration",
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

These atoms are **automatically enforced by host hook config** (see `hooks/`). The router does not invoke them from this SKILL.md; they fire at host-layer matcher points. Listed here so you know what protections are already in place.

| Atom | attack_surface |
| --- | --- |
| `detect-markdown-image-beacon` | OWASP LLM02.exfil |
| `detect-dns-exfiltration-pattern` | dns-tunnel |
