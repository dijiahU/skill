---
name: detect-supply-chain-risk
description: "Detect supply-chain risks in package installs: typosquats, known CVEs, dependency confusion, malicious postinstall scripts, recency anomalies, hallucinated (non-existent) packages, and CI/CD workflow misconfigurations. Trigger when the agent runs npm install, pip install, cargo add, or modifies CI/CD config. Uses helpers/cache_snapshot.py for cached/offline lookups."
phase: tool-invocation
execution_type: checklist
skill_tools_count: 3
hook_tools_count: 5
---

# detect-supply-chain-risk

## 1. Purpose

Stop adversarial packages and CI/CD misconfigurations from being installed by the agent. Eight sub-checks cover the supply chain from name (typosquat, hallucinated) → metadata (recency, dependency confusion) → content (CVE, postinstall script, CI workflow audit).

This archetype contains **8 atoms** (3 skill/hybrid + 5 hook). Hook atoms are enforced by the host's hook config and not invoked from this SKILL.md; skill/hybrid atoms are invoked by the router at the `tool-invocation` phase boundary.

## 2. When to use

Before any package-install command (`npm install`, `pip install`, `cargo add`, `go get`) and before committing changes to CI workflow files. Consult `helpers/health_status.py` first — several atoms here are `requires_network: true` and may be degraded.

Invoked by `safety-router-skill` at the `tool-invocation` phase per its §3.2 phase routing table.

## 3. How to check

Execution type: **checklist**.

Run **all** of the following tools **in parallel**, aggregate by checklist rule (`block` wins, then `warn`, else `pass`):

- `audit-install-hook` (see §4)
- `detect-malicious-postinstall-script` (see §4)
- `audit-ci-workflow-security` (see §4)

Do not skip any tool unless its `helpers/health_status.py` reports the atom as `disabled`.

## 4. Internal tools (skill / hybrid)

### `audit-install-hook` (⚡ hybrid)

**Definition.** Audit npm `postinstall` / pip `setup.py` / cargo build scripts / Makefile install targets for malicious behavior before allowing install.

**Scope-in.** npm postinstall script content audit, pip setup.py exec inspection, cargo build script audit, install-script-source review, Docker image tag-pinning audit

**Scope-out.** detected malicious script content match → `detect-malicious-postinstall-script` (more specific); install-time loader exploit → `detect-tool-loader-exploit`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.

### `detect-malicious-postinstall-script` (⚡ hybrid)

**Definition.** Detect concrete malicious patterns inside postinstall scripts (cred exfil, reverse shell, crypto miner install, persistence write).

**Scope-in.** reverse-shell pattern, base64-decoded payload exec, env-var exfil, miner-binary download

**Scope-out.** just auditing the hook exists / runs → `audit-install-hook`; reverse-shell at runtime → covered separately by sandbox detection

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.

### `audit-ci-workflow-security` (⚡ hybrid)

**Definition.** Audit CI/CD workflow files (GitHub Actions, GitLab CI, Jenkins, CircleCI) for supply-chain risks including action-version pinning, trigger safety (pull_request_target), secret exposure, and dependency injection points.

**Scope-in.** GitHub Actions YAML audit, action-version SHA pinning check, dangerous-trigger detection (`pull_request_target`), workflow-permissions audit

**Scope-out.** package CVE scanning → `check-package-cve`; install-hook content → `audit-install-hook`; SAST scan of source → `run-sast-scan`

**Implementation.** Fast-path regex/static rule + LLM fallback for ambiguous cases. Fast path lives in `hooks/scripts/`; LLM fallback is invoked from this SKILL.md.


## 5. Aggregate verdict

This skill returns a verdict struct consumed by `safety-router-skill`:

```json
{
  "archetype": "detect-supply-chain-risk",
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
| `check-package-typosquat` | OWASP LLM03.typosquat |
| `check-package-cve` | OWASP LLM03.cve |
| `check-dependency-confusion` | dep-confusion |
| `check-package-recency-anomaly` | supply-chain.recency |
| `detect-hallucinated-package` | slopsquatting / LLM-induced supply chain |
