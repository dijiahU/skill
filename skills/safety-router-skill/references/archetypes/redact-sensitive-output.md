---
name: redact-sensitive-output
description: "Redact PII, secrets, system-prompt fragments, and internal infrastructure details from the agent's output before it reaches the user or external systems. Trigger before every output_generation phase. Hook tools handle deterministic regex redaction (SSN, AWS keys); LLM hybrid catches contextual leaks."
phase: output-generation
execution_type: mixed
skill_tools_count: 2
hook_tools_count: 2
---

# redact-sensitive-output

## 1. Purpose

Block sensitive data from leaving the agent's output channel. Four sub-checks: PII redaction, secret redaction, system-prompt fragment redaction, internal-infrastructure detail redaction.

This archetype contains **4 atoms** (2 skill/hybrid + 2 hook). Hook atoms are enforced by the host's hook config and not invoked from this SKILL.md; skill/hybrid atoms are invoked by the router at the `output-generation` phase boundary.

## 2. When to use

Before sending any agent message, writing any file, or returning any tool result to the user. Especially aggressive on outputs destined for external systems (Slack, email, ticketing).

Invoked by `safety-router-skill` at the `output-generation` phase per its §3.2 phase routing table.

## 3. How to check

Execution type: **mixed**.

**Step 1 — fast path.** Host hook config has already run the hook portion of any hybrid atom. Read recent tool results / hook events for `block` or `warn` markers from these atoms before invoking any LLM tools.

**Step 2 — LLM fallback.** For each of the following skill/hybrid LLM tools, invoke only if the fast path returned `pass` or `inconclusive`:

- `redact-output-system-prompt`
- `redact-output-internal-infra`

Aggregate by: hook `block` wins; otherwise checklist rule over LLM tools.

## 4. Internal tools (skill / hybrid)

### `redact-output-system-prompt` (⚡ hybrid)

**Definition.** Detect and remove system-prompt / hidden-instruction / operator-context content from agent output before user sees it.

**Scope-in.** system-prompt fingerprint match in output, system-prompt fragment removal, operator-context strip

**Scope-out.** detecting **attempts** to extract system prompt → `detect-system-prompt-extraction`; general output policy → `enforce-output-content-policy`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.

### `redact-output-internal-infra` (⚡ hybrid)

**Definition.** Redact internal infrastructure details (internal hostnames, IP addresses, k8s namespace names, internal URL paths, file system layout) from agent output.

**Scope-in.** internal-host pattern match, IP-range scrubbing, internal-URL strip, FS-path obfuscation

**Scope-out.** PII / secret-specific redaction → respective siblings; SSRF mitigation → `enforce-network-egress-allowlist`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.


## 5. Aggregate verdict

This skill returns a verdict struct consumed by `safety-router-skill`:

```json
{
  "archetype": "redact-sensitive-output",
  "phase": "output-generation",
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
| `redact-output-pii` | OWASP LLM02.output-pii |
| `redact-output-secret` | OWASP LLM02.output-secret |
