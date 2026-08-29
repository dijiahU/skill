# Safety Orchestrator — Full atom catalog

> **Generated from `agent-safety-orchestrator/atoms.json`** by `scripts/gen_router_atom_catalog.py`. Regenerate whenever the vocabulary changes:
> ```bash
> python3 scripts/gen_router_atom_catalog.py
> ```
>
> **This is an on-demand reference file** — loaded by the agent only when explicitly fetched from Router §7. It is not part of session-start context.

**Coverage**: 95 atoms / 19 archetypes / 5 phases / 60 hook + 21 hybrid + 14 skill. fail_policy and requires_network columns reflect v1.1 deployment metadata.

Atoms are sorted by phase → parent archetype → atom_id (matches Router §3.2 routing order).

| atom_id | parent archetype | phase | mode | fail_policy | requires_network |
| --- | --- | --- | --- | --- | --- |
| `classify-request-ambiguity-level` | `classify-input-intent-ambiguity` | input-understanding | 🧠 skill | — | — |
| `detect-destructive-action-keyword` | `classify-input-intent-ambiguity` | input-understanding | 🔒 hook | — | — |
| `elicit-clarification-before-act` | `classify-input-intent-ambiguity` | input-understanding | 🧠 skill | — | — |
| `detect-direct-prompt-injection` | `detect-prompt-injection` | input-understanding | 🧠 skill | — | — |
| `detect-jailbreak-template` | `detect-prompt-injection` | input-understanding | ⚡ hybrid | — | — |
| `detect-roleplay-escape` | `detect-prompt-injection` | input-understanding | 🧠 skill | — | — |
| `detect-system-prompt-extraction` | `detect-prompt-injection` | input-understanding | 🧠 skill | — | — |
| `detect-credential-in-input` | `scan-input-for-pii-and-secrets` | input-understanding | ⚡ hybrid | — | — |
| `detect-payment-card-data` | `scan-input-for-pii-and-secrets` | input-understanding | 🔒 hook | — | — |
| `detect-pii-in-input` | `scan-input-for-pii-and-secrets` | input-understanding | ⚡ hybrid | — | — |
| `detect-private-key-input` | `scan-input-for-pii-and-secrets` | input-understanding | 🔒 hook | — | — |
| `redact-input-pii` | `scan-input-for-pii-and-secrets` | input-understanding | 🔒 hook | — | — |
| `detect-delayed-payload-pattern` | `validate-agent-tool-trust` | input-understanding | 🧠 skill | — | — |
| `check-rbac-role` | `check-tool-permission-scope` | planning | 🔒 hook | — | — |
| `verify-allowed-tool-list` | `check-tool-permission-scope` | planning | 🔒 hook | — | — |
| `verify-capability-token` | `check-tool-permission-scope` | planning | 🔒 hook | — | — |
| `verify-resource-namespace-scope` | `check-tool-permission-scope` | planning | 🔒 hook | — | — |
| `compare-plan-vs-stated-intent` | `detect-task-overreach` | planning | 🧠 skill | — | — |
| `detect-autonomy-budget-exceeded` | `detect-task-overreach` | planning | 🔒 hook | — | — |
| `enumerate-task-side-effects` | `detect-task-overreach` | planning | 🧠 skill | — | — |
| `flag-unjustified-side-effect` | `detect-task-overreach` | planning | 🧠 skill | — | — |
| `evaluate-content-moderation-rule` | `enforce-policy-as-code` | planning | ⚡ hybrid | — | — |
| `evaluate-opa-rego-rule` | `enforce-policy-as-code` | planning | 🔒 hook | — | — |
| `detect-sandbox-escape-attempt` | `constrain-workspace-boundary` | tool-invocation | 🔒 hook | — | — |
| `enforce-filesystem-sandbox` | `constrain-workspace-boundary` | tool-invocation | 🔒 hook | — | — |
| `enforce-network-egress-allowlist` | `constrain-workspace-boundary` | tool-invocation | 🔒 hook | — | — |
| `enforce-process-sandbox` | `constrain-workspace-boundary` | tool-invocation | 🔒 hook | — | — |
| `enforce-subagent-scope-isolation` | `constrain-workspace-boundary` | tool-invocation | 🔒 hook | — | — |
| `enforce-swarm-race-condition-safety` | `constrain-workspace-boundary` | tool-invocation | 🔒 hook | — | — |
| `detect-covert-channel-in-tool-call` | `detect-data-exfiltration` | tool-invocation | ⚡ hybrid | — | — |
| `detect-dns-exfiltration-pattern` | `detect-data-exfiltration` | tool-invocation | 🔒 hook | — | — |
| `check-malware-hash-ioc` | `detect-malicious-payload-in-tool-output` | tool-invocation | 🔒 hook | `fail-open-warn` | ✅ |
| `detect-archive-bomb` | `detect-malicious-payload-in-tool-output` | tool-invocation | 🔒 hook | — | — |
| `detect-suspicious-mime-type` | `detect-malicious-payload-in-tool-output` | tool-invocation | 🔒 hook | — | — |
| `match-yara-rule` | `detect-malicious-payload-in-tool-output` | tool-invocation | 🔒 hook | — | — |
| `strip-active-html-script` | `detect-malicious-payload-in-tool-output` | tool-invocation | 🔒 hook | — | — |
| `detect-indirect-prompt-injection` | `detect-prompt-injection` | tool-invocation | 🧠 skill | — | — |
| `audit-ci-workflow-security` | `detect-supply-chain-risk` | tool-invocation | ⚡ hybrid | — | — |
| `audit-install-hook` | `detect-supply-chain-risk` | tool-invocation | ⚡ hybrid | — | — |
| `check-dependency-confusion` | `detect-supply-chain-risk` | tool-invocation | 🔒 hook | `fail-closed` | ✅ |
| `check-package-cve` | `detect-supply-chain-risk` | tool-invocation | 🔒 hook | `fail-soft-block` | ✅ |
| `check-package-recency-anomaly` | `detect-supply-chain-risk` | tool-invocation | 🔒 hook | `fail-open-warn` | ✅ |
| `check-package-typosquat` | `detect-supply-chain-risk` | tool-invocation | 🔒 hook | `fail-closed` | ❌ |
| `detect-hallucinated-package` | `detect-supply-chain-risk` | tool-invocation | 🔒 hook | `fail-open-warn` | ✅ |
| `detect-malicious-postinstall-script` | `detect-supply-chain-risk` | tool-invocation | ⚡ hybrid | — | — |
| `detect-runaway-loop` | `enforce-rate-and-quota-limits` | tool-invocation | ⚡ hybrid | — | — |
| `enforce-cost-cap-per-task` | `enforce-rate-and-quota-limits` | tool-invocation | 🔒 hook | — | — |
| `enforce-token-budget-cap` | `enforce-rate-and-quota-limits` | tool-invocation | 🔒 hook | — | — |
| `enforce-tool-call-rate-limit` | `enforce-rate-and-quota-limits` | tool-invocation | 🔒 hook | — | — |
| `detect-hardcoded-secret-in-code` | `scan-code-for-vulnerabilities` | tool-invocation | 🔒 hook | — | — |
| `detect-injection-flaw` | `scan-code-for-vulnerabilities` | tool-invocation | 🔒 hook | — | — |
| `detect-insecure-cryptography` | `scan-code-for-vulnerabilities` | tool-invocation | 🔒 hook | — | — |
| `detect-unsafe-deserialization` | `scan-code-for-vulnerabilities` | tool-invocation | 🔒 hook | — | — |
| `run-sast-scan` | `scan-code-for-vulnerabilities` | tool-invocation | 🔒 hook | — | — |
| `check-tool-typosquat-name` | `validate-agent-tool-trust` | tool-invocation | 🔒 hook | — | — |
| `detect-hidden-instruction-in-tool-description` | `validate-agent-tool-trust` | tool-invocation | ⚡ hybrid | — | — |
| `detect-mcp-confused-deputy` | `validate-agent-tool-trust` | tool-invocation | ⚡ hybrid | — | — |
| `detect-mcp-session-hijacking` | `validate-agent-tool-trust` | tool-invocation | 🔒 hook | — | — |
| `detect-mcp-ssrf` | `validate-agent-tool-trust` | tool-invocation | 🔒 hook | — | — |
| `detect-mcp-token-passthrough` | `validate-agent-tool-trust` | tool-invocation | 🔒 hook | — | — |
| `detect-skill-permission-overrequest` | `validate-agent-tool-trust` | tool-invocation | ⚡ hybrid | — | — |
| `detect-tool-loader-exploit` | `validate-agent-tool-trust` | tool-invocation | ⚡ hybrid | — | — |
| `verify-skill-signature` | `validate-agent-tool-trust` | tool-invocation | 🔒 hook | `fail-closed` | ❌ |
| `verify-tool-publisher-identity` | `validate-agent-tool-trust` | tool-invocation | 🔒 hook | `fail-closed` | ❌ |
| `detect-destructive-flag` | `validate-tool-argument-safety` | tool-invocation | 🔒 hook | — | — |
| `detect-overbroad-resource-selector` | `validate-tool-argument-safety` | tool-invocation | 🔒 hook | — | — |
| `detect-path-traversal` | `validate-tool-argument-safety` | tool-invocation | 🔒 hook | — | — |
| `detect-secret-in-args` | `validate-tool-argument-safety` | tool-invocation | 🔒 hook | — | — |
| `detect-shell-command-injection` | `validate-tool-argument-safety` | tool-invocation | ⚡ hybrid | — | — |
| `detect-sql-injection` | `validate-tool-argument-safety` | tool-invocation | ⚡ hybrid | — | — |
| `detect-unsafe-url` | `validate-tool-argument-safety` | tool-invocation | 🔒 hook | — | — |
| `validate-tool-argument-schema` | `validate-tool-argument-safety` | tool-invocation | 🔒 hook | — | — |
| `detect-base64-payload-in-output` | `detect-data-exfiltration` | output-generation | ⚡ hybrid | — | — |
| `detect-markdown-image-beacon` | `detect-data-exfiltration` | output-generation | 🔒 hook | — | — |
| `detect-dangerous-instruction-in-output` | `enforce-output-content-policy` | output-generation | 🧠 skill | — | — |
| `enforce-disallowed-content-rule` | `enforce-output-content-policy` | output-generation | ⚡ hybrid | — | — |
| `review-generated-code-output` | `enforce-output-content-policy` | output-generation | ⚡ hybrid | — | — |
| `review-generated-file-write` | `enforce-output-content-policy` | output-generation | 🧠 skill | — | — |
| `review-generated-message-output` | `enforce-output-content-policy` | output-generation | 🧠 skill | — | — |
| `redact-output-internal-infra` | `redact-sensitive-output` | output-generation | ⚡ hybrid | — | — |
| `redact-output-pii` | `redact-sensitive-output` | output-generation | 🔒 hook | — | — |
| `redact-output-secret` | `redact-sensitive-output` | output-generation | 🔒 hook | — | — |
| `redact-output-system-prompt` | `redact-sensitive-output` | output-generation | ⚡ hybrid | — | — |
| `record-decision-trace` | `audit-trail-recording` | cross-cutting | 🔒 hook | — | — |
| `record-prompt-and-context-snapshot` | `audit-trail-recording` | cross-cutting | 🔒 hook | — | — |
| `record-tool-invocation-trace` | `audit-trail-recording` | cross-cutting | 🔒 hook | — | — |
| `await-human-decision-or-timeout` | `escalate-to-human-sentinel` | cross-cutting | 🔒 hook | — | — |
| `log-human-decision-outcome` | `escalate-to-human-sentinel` | cross-cutting | 🔒 hook | — | — |
| `present-risk-rationale` | `escalate-to-human-sentinel` | cross-cutting | 🧠 skill | — | — |
| `request-human-confirmation` | `escalate-to-human-sentinel` | cross-cutting | 🔒 hook | — | — |
| `execute-recovery-playbook` | `incident-response-handler` | cross-cutting | ⚡ hybrid | — | — |
| `halt-in-flight-action` | `incident-response-handler` | cross-cutting | 🔒 hook | — | — |
| `isolate-affected-resource` | `incident-response-handler` | cross-cutting | 🔒 hook | — | — |
| `notify-oncall-and-open-ticket` | `incident-response-handler` | cross-cutting | 🔒 hook | — | — |
| `snapshot-agent-state` | `incident-response-handler` | cross-cutting | 🔒 hook | — | — |

## How to use this catalog

- **Agents routed by Router** generally do NOT need this file — Router's §3.2 phase routing table is sufficient for everyday safety decisions.
- **Debug an unexpected verdict**: find the atom in the table → see which archetype owns it → open `references/archetypes/<archetype>.md` §4 for the atom's definition + implementation notes (these archetype docs sit beside this catalog under the Router skill; they are not top-level skills).
- **Audit which atoms are degraded**: cross-reference the `requires_network: ✅` rows against `~/.safety-orch/atom-status.json` (written by `helpers/health_status.py`).
- **Plan a fail_policy override**: `fail-closed` atoms cannot be overridden. `fail-soft-block` atoms require user `--accept-degraded` flag. `fail-open-warn` atoms log + proceed silently in the user-facing flow.

## Cross-references

- Vocabulary source of truth: [`docs/SAFETY_ATOMIC_CAPABILITIES.md`](../../../docs/SAFETY_ATOMIC_CAPABILITIES.md) §5
- enforcement_mode: each atom in [`atoms.json`](../../../atoms.json) carries an `enforcement_mode` field
- Deployment metadata (`requires_network` / `fail_policy`): SAFETY_ATOMIC_CAPABILITIES.md §12.2-12.3
- v1.1 changelog: SAFETY_ATOMIC_CAPABILITIES.md §0
