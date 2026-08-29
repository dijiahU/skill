---
name: validate-tool-argument-safety
description: "Validate the safety of a tool call's arguments before the call fires. Covers shell-command injection, SQL injection, path traversal, destructive flags (rm -rf, --force, DROP), unsafe URLs, secrets-in-args, overbroad resource selectors, and argument-schema validation. Trigger on every tool-invocation phase, before the call."
phase: tool-invocation
execution_type: checklist
skill_tools_count: 2
hook_tools_count: 6
---

# validate-tool-argument-safety

## 1. Purpose

Catch dangerous tool arguments before the tool runs. Eight sub-checks span shell-injection, SQL-injection, path traversal, destructive flags, unsafe URLs, secret-in-args leakage, overbroad resource selectors, and JSON-schema validity.

This archetype contains **8 atoms** (2 skill/hybrid + 6 hook). Hook atoms are enforced by the host's hook config and not invoked from this SKILL.md; skill/hybrid atoms are invoked by the router at the `tool-invocation` phase boundary.

## 2. When to use

Every tool call. Argument validation is the densest single defense layer — a `Bash` call can match 8+ atoms here.

Invoked by `safety-router-skill` at the `tool-invocation` phase per its §3.2 phase routing table.

## 3. How to check

Execution type: **checklist**.

Run **all** of the following tools **in parallel**, aggregate by checklist rule (`block` wins, then `warn`, else `pass`):

- `detect-shell-command-injection` (see §4)
- `detect-sql-injection` (see §4)

Do not skip any tool unless its `helpers/health_status.py` reports the atom as `disabled`.

## 4. Internal tools (skill / hybrid)

### `detect-shell-command-injection` (⚡ hybrid)

**Definition.** Detect shell metacharacters / argument escapes / unsafe quoting that introduce an executable payload in commands the agent is about to run via shell, exec, or subprocess.

**Scope-in.** dangerous command substitution such as `$(curl ...)`, pipe-to-shell execution, `/dev/tcp`, untrusted argument interpolation in bash/sh, `subprocess.run(shell=True)`, makefile targets, or container `cmd`

**Scope-out.** SQL queries → `detect-sql-injection`; HTTP request body content → `detect-unsafe-url` (if URL) or `enforce-output-content-policy`; OS-level sandbox → `enforce-process-sandbox`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.

### `detect-sql-injection` (⚡ hybrid)

**Definition.** Detect SQL injection patterns / unparameterized query construction in DB calls the agent is about to execute.

**Scope-in.** string-concat SQL, missing parameterization, ORM raw query inspection, NoSQL operator injection

**Scope-out.** shell calls → `detect-shell-command-injection`; SAST on stored code → `detect-injection-flaw`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.


## 5. Aggregate verdict

This skill returns a verdict struct consumed by `safety-router-skill`:

```json
{
  "archetype": "validate-tool-argument-safety",
  "phase": "tool-invocation",
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
| `detect-path-traversal` | path-traversal |
| `detect-destructive-flag` | destructive-args |
| `detect-unsafe-url` | SSRF |
| `detect-secret-in-args` | OWASP LLM02 (output-side leak via tool args) |
| `detect-overbroad-resource-selector` | OWASP LLM06.overbroad-scope |
| `validate-tool-argument-schema` | schema-violation |
