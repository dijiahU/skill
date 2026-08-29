"""Atomic Safety Capability Archetypes (v2) — Stage 3 anchor set.

Source of truth: docs/SAFETY_ATOMIC_ARCHETYPES.md (v2). When editing the
archetype list, edit the markdown FIRST (it is the design doc), then
re-sync this file. Schema and rationale are documented in the markdown.

Imported by: scripts/dedup_stage3_embedding.py.
"""

from __future__ import annotations

ARCHETYPE_LIST_VERSION = "v2"
ARCHETYPE_LIST_DATE = "2026-05-08"

# Each entry mirrors a "#### `id`" block in docs/SAFETY_ATOMIC_ARCHETYPES.md.
ARCHETYPES: tuple[dict, ...] = (
    # ---- 3.1 Input understanding ------------------------------------------
    {
        "id": "detect-prompt-injection",
        "name_zh": "检测提示注入",
        "name_en": "Detect Prompt Injection",
        "phase": "input-understanding",
        "attack_surface": "OWASP LLM01 (Prompt Injection) · MITRE ATLAS AML.T0051",
        "embed_text": (
            "Detect prompt injection attempts in user input or in retrieved "
            "external content. Identify direct injection (user instructions "
            "overriding the system prompt), indirect injection (malicious "
            "instructions hidden in fetched documents, web pages, file "
            "contents, or tool outputs), jailbreak templates, and role-play "
            "escapes. Returns a risk verdict and a sanitized version of the "
            "input where instructions are quoted as data rather than executed."
        ),
        "example_cues": [
            "prompt injection", "jailbreak", "indirect injection",
            "system prompt override", "role-play escape", "instruction smuggling",
        ],
    },
    {
        "id": "classify-input-intent-ambiguity",
        "name_zh": "识别意图歧义",
        "name_en": "Classify Input Intent Ambiguity",
        "phase": "input-understanding",
        "attack_surface": "intent-ambiguity (project book §1)",
        "embed_text": (
            "Classify whether a user request is sufficiently unambiguous to "
            "act on autonomously, or whether it admits multiple plausible "
            "interpretations with materially different safety profiles. "
            "Use bounded non-mutating discovery to resolve missing context "
            "before asking, and pause only at the first side-effect boundary "
            "if material ambiguity remains. "
            "Distinguish benign ambiguity (e.g. typos, missing parameters) "
            "from safety-critical ambiguity (e.g. \"delete the old files\" — "
            "which files? where?). Returns the ambiguity class and "
            "recommended clarification."
        ),
        "example_cues": [
            "intent ambiguity", "request clarification", "underspecified",
            "scope clarification", "intent classification",
        ],
    },
    {
        "id": "scan-input-for-pii-and-secrets",
        "name_zh": "输入侧敏感信息检测",
        "name_en": "Scan Input for PII and Secrets",
        "phase": "input-understanding",
        "attack_surface": "OWASP LLM02 (Sensitive Information Disclosure) · GDPR/PII",
        "embed_text": (
            "Scan user-supplied input for personally identifiable information "
            "(PII), payment card data, government IDs, authentication tokens, "
            "API keys, private keys, or other regulated/sensitive content "
            "that the agent should not transmit, log, or include in "
            "downstream calls. Returns the inventory of detected items and a "
            "redacted version safe for further processing."
        ),
        "example_cues": [
            "PII detection", "secret scanning", "credential detection",
            "GDPR", "HIPAA", "regex secret scanner", "redaction",
        ],
    },

    # ---- 3.2 Planning / decision -----------------------------------------
    {
        "id": "threat-model-task",
        "name_zh": "任务威胁建模",
        "name_en": "Threat-Model the Planned Task",
        "phase": "planning",
        "attack_surface": "cross-cutting (STRIDE, attack tree generation)",
        "embed_text": (
            "Generate a structured threat model for a planned task or "
            "workflow. Enumerate assets at risk, attacker goals, attack "
            "vectors, and likely exploitation paths. Often follows STRIDE or "
            "attack-tree formalism. Used by an agent before executing a "
            "multi-step plan involving sensitive data, external systems, or "
            "privileged operations. Used as an executable agent skill that "
            "analyzes a concrete planned workflow, not a generic "
            "documentation template."
        ),
        "example_cues": [
            "threat model", "STRIDE", "attack tree", "threat enumeration",
            "security review", "planned workflow",
        ],
    },
    {
        "id": "enforce-policy-as-code",
        "name_zh": "策略即代码执行",
        "name_en": "Enforce Policy-as-Code",
        "phase": "planning",
        "attack_surface": "OWASP LLM06 (Excessive Agency) · access control",
        "embed_text": (
            "Evaluate a planned action against an explicit policy rule set "
            "(RBAC roles, OPA/Rego policies, content moderation rules, "
            "regulatory compliance constraints). Return allow/deny with "
            "rule-level rationale. Used to gate agent decisions where rules "
            "are codified and machine-checkable."
        ),
        "example_cues": [
            "policy as code", "OPA", "Rego", "RBAC", "ABAC",
            "policy enforcement", "compliance check",
        ],
    },
    {
        "id": "check-tool-permission-scope",
        "name_zh": "工具权限范围检查",
        "name_en": "Check Tool Permission Scope",
        "phase": "planning",
        "attack_surface": "OWASP LLM06 (Excessive Agency) · least privilege",
        "embed_text": (
            "Verify that a planned tool call falls within the scope of "
            "permissions the agent (or its current task) has been granted. "
            "Reject tool calls that would access resources outside the "
            "allowed namespaces, accounts, file paths, or capability tokens. "
            "Implements least-privilege enforcement at the agent-runtime "
            "boundary."
        ),
        "example_cues": [
            "permission scope", "least privilege", "capability token",
            "scope check", "allowed tools",
        ],
    },
    {
        "id": "detect-task-overreach",
        "name_zh": "检测任务越权",
        "name_en": "Detect Task Overreach",
        "phase": "planning",
        "attack_surface": "OWASP LLM06 (Excessive Agency) · scope creep",
        "embed_text": (
            "Detect when an agent's plan exceeds the user's stated intent — "
            "e.g. the user asked to \"summarize this PR\" and the agent "
            "plans to also push commits, open issues, or modify "
            "configuration. Compare the plan's side-effect graph against the "
            "elicited user intent, flag steps that aren't justified by the "
            "stated goal."
        ),
        "example_cues": [
            "scope creep", "overreach", "plan validation",
            "intent vs plan mismatch", "autonomous action review",
        ],
    },

    # ---- 3.3 Tool invocation ---------------------------------------------
    {
        "id": "validate-tool-argument-safety",
        "name_zh": "工具参数安全校验",
        "name_en": "Validate Tool Argument Safety",
        "phase": "tool-invocation",
        "attack_surface": (
            "unsafe tool arguments · command injection · path traversal · secret leakage"
        ),
        "embed_text": (
            "Validate outgoing tool-call arguments before execution. Inspect "
            "HTTP requests, MCP calls, shell commands, database queries, "
            "file paths, URLs, recipients, and resource selectors for unsafe "
            "parameters. Detect embedded secrets, command or SQL injection "
            "payloads, path traversal, destructive flags, unintended "
            "wildcards, overbroad resource scopes, malformed arguments, and "
            "parameters that exceed the user's authorized task scope. Return "
            "allow, block, sanitize, or clarification-needed."
        ),
        "example_cues": [
            "argument validation", "parameter safety", "unsafe args",
            "command injection", "path traversal", "destructive flag",
            "secret leakage", "sanitize tool call",
        ],
    },
    {
        "id": "constrain-workspace-boundary",
        "name_zh": "工作区边界约束",
        "name_en": "Constrain Workspace Boundary",
        "phase": "tool-invocation",
        "attack_surface": "OWASP LLM06 · sandboxing",
        "embed_text": (
            "Restrict the agent's file system, network, and process "
            "operations to a declared workspace (project root, allowed "
            "hostnames, sandboxed container). Reject path traversal (../), "
            "absolute paths outside the workspace, network calls to "
            "disallowed hosts, and process spawns that escape the sandbox. "
            "Implements the agent equivalent of chroot + egress firewall."
        ),
        "example_cues": [
            "workspace boundary", "sandbox", "chroot", "path traversal",
            "egress firewall", "network allowlist",
        ],
    },
    {
        "id": "validate-agent-tool-trust",
        "name_zh": "Agent 工具与 Skill 可信度校验",
        "name_en": "Validate Agent Tool or Skill Trust",
        "phase": "tool-invocation",
        "attack_surface": "tool supply chain · skill poisoning · MCP trust",
        "embed_text": (
            "Verify the trustworthiness of an agent tool, skill package, MCP "
            "server, plugin, or external capability before installation or "
            "invocation. Check source provenance, registry membership, "
            "publisher identity, signatures, pinned hashes, version history, "
            "declared permissions, dependency behavior, and whether tool or "
            "skill descriptions contain hidden instructions targeting the "
            "LLM. Reject untrusted, modified, overprivileged, or "
            "instruction-laden tools."
        ),
        "example_cues": [
            "tool trust", "skill trust", "MCP trust", "registry verification",
            "signed tool", "tool poisoning", "skill poisoning", "provenance",
        ],
    },
    {
        "id": "detect-supply-chain-risk",
        "name_zh": "供应链风险识别",
        "name_en": "Detect Supply-Chain Risk",
        "phase": "tool-invocation",
        "attack_surface": "OWASP LLM03 (Supply Chain Vulnerabilities)",
        "embed_text": (
            "Identify supply-chain risks in dependencies the agent is about "
            "to install, import, or invoke: typosquatting package names, "
            "abandoned packages, packages with known CVEs, packages from "
            "unverified registries, dependency confusion, malicious "
            "transitive dependencies. Recommend pinning, alternative "
            "packages, or refusal. Focuses on third-party packages and "
            "dependencies rather than the agent skill manifest itself."
        ),
        "example_cues": [
            "supply chain", "dependency audit", "SBOM", "typosquatting",
            "dependency confusion", "CVE check", "transitive dependency",
            "package vulnerability",
        ],
    },
    {
        "id": "scan-code-for-vulnerabilities",
        "name_zh": "代码漏洞静态扫描",
        "name_en": "Scan Code for Vulnerabilities",
        "phase": "tool-invocation",
        "attack_surface": "SAST · OWASP general",
        "embed_text": (
            "Static analysis of source code (generated by the agent or "
            "supplied by the user) for security vulnerabilities: injection "
            "flaws, hardcoded secrets, insecure cryptography, unsafe "
            "deserialization, command/SQL injection, XSS, path traversal, "
            "race conditions. Returns findings with severity, location, and "
            "remediation guidance."
        ),
        "example_cues": [
            "SAST", "vulnerability scanner", "code audit",
            "secure code review", "semgrep", "security linter",
        ],
    },
    {
        "id": "detect-malicious-payload-in-tool-output",
        "name_zh": "工具输出恶意载荷检测",
        "name_en": "Detect Malicious Payload in Tool Output",
        "phase": "tool-invocation",
        "attack_surface": "OWASP LLM05 (Improper Output Handling) · payload-level filtering",
        "embed_text": (
            "Scan responses returned by external tools (web pages, file "
            "contents, MCP server responses, shell command output, "
            "downloaded files) for malicious payloads before exposing them "
            "to the agent. Inspect HTML/script payloads, file attachments, "
            "binary blobs, archive bombs (zip/gzip/tar with extreme "
            "expansion ratios), suspicious MIME types, encoded commands, "
            "oversized or abnormally structured responses, and known-bad "
            "signatures (YARA rules, malware hashes, IOC matches). Acts as a "
            "tool-output firewall: payload-level filtering distinct from "
            "prompt-injection text-content detection. Quarantine, decode, or "
            "strip before passing the response to the agent."
        ),
        "example_cues": [
            "output payload scanning", "YARA", "malware signature",
            "archive bomb", "zip bomb", "MIME sniffing", "binary blob",
            "IOC match", "tool output firewall",
        ],
    },
    {
        "id": "enforce-rate-and-quota-limits",
        "name_zh": "速率与配额限制",
        "name_en": "Enforce Rate and Quota Limits",
        "phase": "tool-invocation",
        "attack_surface": "DoS · resource abuse",
        "embed_text": (
            "Throttle or cap resource-intensive operations to prevent "
            "runaway costs, denial of wallet, denial of service against "
            "external APIs, or self-inflicted rate-limit bans. Track "
            "per-tool / per-task / per-session counters; trigger backoff or "
            "escalate when limits approach."
        ),
        "example_cues": [
            "rate limit", "quota", "denial of wallet", "throttling",
            "backoff", "cost cap",
        ],
    },

    # ---- 3.4 Output generation -------------------------------------------
    {
        "id": "redact-sensitive-output",
        "name_zh": "输出敏感信息脱敏",
        "name_en": "Redact Sensitive Output",
        "phase": "output-generation",
        "attack_surface": "OWASP LLM02 (Sensitive Information Disclosure)",
        "embed_text": (
            "Before returning an output to the user (or writing it to logs / "
            "files / external systems), detect and redact PII, secrets, "
            "internal infrastructure details, system prompts, or other "
            "content that violates the agent's confidentiality boundary. "
            "Also redact memorized training data leaks."
        ),
        "example_cues": [
            "output redaction", "PII redaction", "secrets in output",
            "log scrubbing", "training data leakage",
        ],
    },
    {
        "id": "detect-data-exfiltration",
        "name_zh": "数据外泄检测",
        "name_en": "Detect Data Exfiltration Attempts",
        "phase": "output-generation",
        "attack_surface": "OWASP LLM02 · MITRE ATLAS Exfiltration tactics",
        "embed_text": (
            "Detect attempts to exfiltrate sensitive data via the agent's "
            "output channels — including covert channels like markdown image "
            "URLs that beacon to attacker-controlled servers, base64-encoded "
            "payloads in code blocks, DNS-over-HTTPS lookups embedded in "
            "tool calls. Block outputs that would cause sensitive data to "
            "leave the trust boundary."
        ),
        "example_cues": [
            "data exfiltration", "covert channel", "beacon",
            "image URL exfiltration", "DNS exfiltration",
        ],
    },
    {
        "id": "enforce-output-content-policy",
        "name_zh": "输出内容策略",
        "name_en": "Enforce Output Content Policy",
        "phase": "output-generation",
        "attack_surface": "OWASP LLM09 (Misinformation) · agent output safety",
        "embed_text": (
            "Apply output safety policy to content generated by an "
            "autonomous agent after retrieval, tool use, code execution, or "
            "external system interaction. Check whether the final response, "
            "generated file, message, code block, or external write contains "
            "dangerous instructions, privacy violations, unauthorized "
            "disclosures, policy-prohibited content, or unsafe operational "
            "guidance. Return block, rewrite, redact, or escalate."
        ),
        "example_cues": [
            "agent output policy", "agent output safety",
            "post-tool-use content check", "generated content review",
            "escalation gate",
        ],
    },

    # ---- 3.5 Cross-cutting -----------------------------------------------
    {
        "id": "audit-trail-recording",
        "name_zh": "审计日志记录",
        "name_en": "Audit Trail Recording",
        "phase": "cross-cutting",
        "attack_surface": "forensics · compliance",
        "embed_text": (
            "Record a tamper-evident audit trail of agent decisions, tool "
            "invocations, prompt versions, retrieved context, and final "
            "outputs. Designed to support post-incident forensics, "
            "regulatory compliance evidence, and root-cause analysis. "
            "Storage may be append-only / cryptographically chained."
        ),
        "example_cues": [
            "audit log", "audit trail", "forensic logging",
            "decision log", "tamper-evident",
        ],
    },
    {
        "id": "incident-response-handler",
        "name_zh": "事件响应处置",
        "name_en": "Incident Response Handler",
        "phase": "cross-cutting",
        "attack_surface": "agent-execution incident response",
        "embed_text": (
            "Designed for security events arising during autonomous agent "
            "execution, tool use, or skill invocation. Triggered playbook "
            "executed when such an event is detected. Stops in-flight "
            "actions, snapshots state, isolates affected resources, notifies "
            "oncall, opens a tracking ticket, and records timeline. Brings "
            "the agent to a safe pause state pending human triage."
        ),
        "example_cues": [
            "agent incident response", "IR playbook", "agent kill-switch",
            "in-flight halt", "agent state snapshot", "security event handler",
        ],
    },
    {
        "id": "escalate-to-human-sentinel",
        "name_zh": "安全哨兵 — 升级到人类确认",
        "name_en": "Sentinel: Escalate to Human Confirmation",
        "phase": "cross-cutting",
        "attack_surface": "highest-priority atomic skill (per project book)",
        "embed_text": (
            "Highest-priority safety primitive. When risk cannot be "
            "auto-resolved or when an action's reversibility / blast radius "
            "/ sensitivity exceeds an autonomy threshold, halt autonomous "
            "execution and request explicit human confirmation before "
            "proceeding. Captures the current task state, risk rationale, "
            "and proposed action so the human can audit and approve / deny."
        ),
        "example_cues": [
            "human in the loop", "escalate", "confirmation",
            "approval gate", "human review", "kill switch", "sentinel",
        ],
    },
)


def anchor_text_for_embedding(arc: dict) -> str:
    """Construct the string actually sent to the embedding API for an
    archetype. See docs/SAFETY_ATOMIC_ARCHETYPES.md §1.1."""
    keywords = ", ".join(arc["example_cues"])
    return f"{arc['embed_text']}\nKeywords: {keywords}"


assert len(ARCHETYPES) == 20, f"Expected 20 archetypes, got {len(ARCHETYPES)}"
_ids = [a["id"] for a in ARCHETYPES]
assert len(_ids) == len(set(_ids)), "Duplicate archetype id detected"
