# Atomic Safety Capability Archetypes (Draft v2)

> **状态：v2 整合用户对 v1 的复审反馈，待二次复审**（2026-05-08）
> 版本：v2（v0→v1→v2 changelog 见下方 §0）
> 用途：Stage 3 embedding 相关性排序的 anchor set；后续 Module 1.4 atomic skill 库的 taxonomy 骨架雏形

## 0. Changelog

### v1 → v2（2026-05-08，基于用户对 v1 的复审）

Archetype 列表本身**不动**（用户明确建议不增删）；本轮全部是 Stage 3 实施契约层面的细化。

| 改动 | 类型 | 原因 |
| --- | --- | --- |
| 选择规则加 **per-anchor min threshold**（默认 0.55）| 必改 | 防止低质量 anchor 强行补满 top-N，避免引入弱相关样本 |
| τ=0.65 改写为"初始值，需抽样校准"，附校准流程 | 必改 | 不同 embedding 模型 / 文本长度 / 候选来源会让分数分布偏移，硬编码风险大 |
| Anchor 送入 embedding 的文本规范化为 `embed_text + Keywords: example_cues` | 必改 | 短描述 MCP/skill（如 "OPA policy checker"）依赖关键词召回，纯长文本 anchor 在短候选空间召回弱 |
| 候选文本拆成 `relevance_text` + `dedup_text` 两份 | 必改 | 完整 README 含大量 installation/badge/license/changelog 噪声，会稀释 safety 信号 |
| `threat-model-task` embed_text 加一句限定到"具体可执行流程"，远离纯模板文档 | 微调 | 降低对泛化威胁建模模板的误召 |
| `detect-supply-chain-risk` embed_text 加 "Focuses on third-party packages and dependencies rather than the agent skill manifest itself" | 微调 | 与 `validate-agent-tool-trust` 划清边界 |
| `detect-malicious-payload-in-tool-output` 重写：减弱 "hidden instructions" 权重，加 HTML/script payload、binary blob、archive bomb、MIME、YARA | 微调 | 跟 `detect-prompt-injection` 区分明确，做成 tool-output firewall 而非 prompt-injection 重复 |
| `incident-response-handler` embed_text 加 "Designed for security events arising during autonomous agent execution, tool use, or skill invocation" | 微调 | 与企业 SIEM/SOAR 运维工具拉开距离 |
| Stage 3 manifest 输出加 `top3_anchors` + `kept_by` 字段 | 必改 | 后续审计/去重需要看到候选在多个 anchor 上的命中分布与"被哪条规则选中" |

### v0 → v1（2026-05-08，基于用户对 v0 的审计反馈）

| 改动 | 原因 |
| --- | --- |
| **替换** `scan-tool-args-for-secrets` → `validate-tool-argument-safety` | v0 anchor 只覆盖 secret leakage；项目书"检查参数安全"实际包含 shell/SQL injection、path traversal、destructive flag、unsafe URL、wildcard misuse、wrong recipient/repo 等 |
| **替换** `validate-mcp-server-trust` → `validate-agent-tool-trust` | v0 仅覆盖 MCP；需要更通用的 anchor 同时召回 tool poisoning / skill poisoning / plugin vetting |
| **重写** `enforce-output-content-policy` 的 `embed_text` | v0 容易召回普通内容审核工具（toxicity / NSFW / hate speech），v1 锚定到 agent 输出语境 |
| **新增设计原则**：Stage 3 选择规则改为 **per-anchor top-N cap ∪ 全局阈值** | 防止宽泛 anchor 单独吞掉残量预算 |

## 1. 这份清单干什么用

漏斗 Stage 3（详见 [PROJECT_OVERVIEW.md §4 子任务 1.1.5](PROJECT_OVERVIEW.md)）需要把 8053 个候选（4136 SKILL.md + 3917 MCP server）按"安全相关性"打分排序，目标残量 1500-3000。

### 1.1 Anchor 文本构造（送给 embedding 模型的字符串）

注意：**实际送给 embedding-3 的 anchor 文本不只是 §3 列出的 `embed_text`**，而是拼了 `example_cues` 的版本：

```python
anchor_text_for_embedding = embed_text + "\nKeywords: " + ", ".join(example_cues)
```

**为什么**：很多真实候选（特别是 MCP server description）描述非常短，例如 "OPA policy checker"、"YARA scanner"、"SBOM audit"，它们主要靠关键词匹配召回。把 `example_cues` 拼到 `embed_text` 末尾能让 anchor 在短候选空间也保持召回力，否则纯长段落 anchor 跟短候选算 cosine 容易低估。

### 1.2 候选文本构造（避免 README 噪声稀释 safety 信号）

完整 README 容易被 installation 说明 / badge / license / changelog / benchmark 等无关章节污染 embedding。Stage 3 脚本对每个候选构造**两份**文本：

| 字段 | 用途 | 组成 |
| --- | --- | --- |
| `relevance_text` | safety 评分（送给 embedding-3 算 vector） | `name + short_description + safety sections（## Security / ## Threat Model / ## Permissions 等）+ tool descriptions + permission declarations + core usage 段首` |
| `dedup_text` | 后续如需更严格 dedup（Module 1.3 / 1.4） | `name + normalized purpose + core capability + I/O + permissions` |

**`relevance_text` fallback 逻辑**：很多 SKILL.md 没有显式 `## Security` 这种章节。fallback 到 SKILL.md 全文，但**剥离常见 boilerplate 段落**：License、Installation、Contributors、Changelog、Build Status、Sponsors、徽章块。最终截断到 6000 chars。

MCP server 的 `relevance_text` 用 `name + description + (readme 的前 2000 char 去掉常见 markdown 表头/徽章)`。

### 1.3 评分

1. 用智谱 embedding-3 给每个 archetype 的 `anchor_text_for_embedding` 算 vector（共 20 个）
2. 给每个候选的 `relevance_text` 算 vector
3. 对每个候选记录跟 20 个 archetype 的**全部** cosine 值（不只取 max）

### 1.4 选择规则（per-anchor cap + per-anchor min threshold ∪ 全局阈值）

```
per_anchor_kept = ⋃_{a ∈ archetypes} { top-N from {c : cosine(c, a) >= anchor_min_threshold} }
global_kept     = { c : max-cosine(c, *) >= global_threshold }
Stage 3 残量    = per_anchor_kept ∪ global_kept
```

**默认参数（首跑用，τ 与 anchor_min_threshold 必须校准）**：

| 参数 | 默认 | 含义 |
| --- | --- | --- |
| `per_anchor_cap` (N) | 150 | 每个 anchor 最多贡献多少候选 |
| `anchor_min_threshold` | 0.55 | 候选 cosine 低于这个值时**不进** per_anchor_kept，哪怕在该 anchor 排名前 N（防止低质量 anchor 强行补满） |
| `global_threshold` (τ) | 0.65 | 候选只要在任何一个 anchor 上 cosine ≥ τ，无条件保留 |

#### 1.4.1 关于 τ / anchor_min_threshold 不能拍脑袋定

不同 embedding 模型 / 文本长度 / 候选来源会让分数分布偏移，硬编码 0.65 / 0.55 可能过严或过松。**首跑后必须做抽样校准**：

1. 全量 cosine 跑出来后，每个 anchor 抽样：
   - top 30
   - 落在 0.65 附近 ±0.02 的 30 条
   - 落在 0.55–0.65 区间的 30 条
2. 人工标注 safety-relevant / not-relevant
3. 按精度-召回权衡校准 τ 和 anchor_min_threshold（可能某些 anchor 需要单独定阈值）
4. 第二轮 Stage 3 选数才用校准后的阈值

**首次跑出来的 manifest 同时保留所有候选的全 20 个 cosine 值**，方便阈值调整后**不重新调 API**重新选数。

### 1.5 这套规则相对"全局 top-K + 阈值"的优势

- **保证每个 archetype 都有充分代表**：避免 `threat-model-task` 这类宽泛 anchor 因为容易匹配大量"安全咨询模板"而吞掉残量预算
- **小众但重要的 anchor（如 `escalate-to-human-sentinel`）也能拿到自己的名额**，不会被宽泛 anchor 挤掉
- **加了 `anchor_min_threshold` 之后**，弱 anchor 不会因为"凑足 top-150"而拉低残量整体质量
- 残量上限可估：20 anchor × 150 = 3000，去重后实际约 **2000-2800**，落在子任务 1.1.5 的目标 1500-3000 区间

### 1.6 Stage 3 manifest 输出格式

每个候选在 manifest 里记录：

```json
{
  "path": "data/raw/community_skills/clawhub/skills/security/secret-detector",
  "kind": "skill",
  "max_score": 0.72,
  "top1_anchor": "validate-tool-argument-safety",
  "top1_score": 0.72,
  "top3_anchors": [
    ["validate-tool-argument-safety", 0.72],
    ["scan-input-for-pii-and-secrets", 0.68],
    ["redact-sensitive-output", 0.61]
  ],
  "all_scores": {  
    "detect-prompt-injection": 0.31,
    "validate-tool-argument-safety": 0.72,
    "...": "..."
  },
  "kept": true,
  "kept_by": ["per_anchor", "global_threshold"]
}
```

- `top3_anchors`：候选最相近的 3 个 anchor，方便 Module 1.4 做主题归类
- `all_scores`：全 20 个分数（约 2KB / 候选）—— 阈值调整后不重新调 API 直接重选
- `kept_by`：是被 `per_anchor`、`global_threshold`、还是两者同时选中。后续审计很有用

### 1.7 这份清单跟最终原子库的区别

**Archetype 的 embed 文本是唯一被 embedding 模型看到的字符串**，所以它的写法直接决定召回质量。这份清单写得越像"一个真实 SKILL.md 在自我描述某个安全能力"，相似度匹配就越准。

这份清单**不是最终原子库**，只是 anchor set。最终原子库要在 Module 1.4 通过对 Stage 3 残量做 LLM 审计 + 语义对齐才能产出。原型可能膨胀到 50-200 个原子。

## 2. 原型字段格式

| 字段 | 含义 |
| --- | --- |
| `id` | slug，全小写连字符。后续脚本和 manifest 的 join key |
| `name_zh` / `name_en` | 人类可读名 |
| `phase` | 项目书的 4 个 agent 执行阶段之一 + `cross-cutting`（全周期） |
| `attack_surface` | 主要对应的攻击面（OWASP LLM Top 10 编号 / MITRE ATLAS tactic / 自定义） |
| `embed_text` | **送给 embedding-3 的自然语言描述**，模仿真实 SKILL.md 风格 |
| `example_cues` | 在 SKILL.md / MCP description 里出现这些词大概率属于这个 archetype |

## 3. 原型清单（按 agent 执行阶段分组）

### 3.1 输入理解阶段（Input understanding）

#### `detect-prompt-injection`
- **name**: 检测提示注入 / Detect Prompt Injection
- **phase**: input-understanding
- **attack_surface**: OWASP LLM01 (Prompt Injection) · MITRE ATLAS AML.T0051
- **embed_text**: Detect prompt injection attempts in user input or in retrieved external content. Identify direct injection (user instructions overriding the system prompt), indirect injection (malicious instructions hidden in fetched documents, web pages, file contents, or tool outputs), jailbreak templates, and role-play escapes. Returns a risk verdict and a sanitized version of the input where instructions are quoted as data rather than executed.
- **example_cues**: prompt injection, jailbreak, indirect injection, system prompt override, role-play escape, instruction smuggling

#### `classify-input-intent-ambiguity`
- **name**: 识别意图歧义 / Classify Input Intent Ambiguity
- **phase**: input-understanding
- **attack_surface**: 自定义（intent-ambiguity，对应项目书 §1 模块 1 列举的"检测意图歧义"）
- **embed_text**: Classify whether a user request is sufficiently unambiguous to act on autonomously, or whether it admits multiple plausible interpretations with materially different safety profiles. Use bounded non-mutating discovery to resolve missing context before asking, and pause only at the first side-effect boundary if material ambiguity remains. Distinguish benign ambiguity (e.g. typos, missing parameters) from safety-critical ambiguity (e.g. "delete the old files" — which files? where?). Returns the ambiguity class and recommended clarification.
- **example_cues**: intent ambiguity, request clarification, underspecified, scope clarification, intent classification

#### `scan-input-for-pii-and-secrets`
- **name**: 输入侧敏感信息检测 / Scan Input for PII and Secrets
- **phase**: input-understanding
- **attack_surface**: OWASP LLM02 (Sensitive Information Disclosure) · GDPR/PII
- **embed_text**: Scan user-supplied input for personally identifiable information (PII), payment card data, government IDs, authentication tokens, API keys, private keys, or other regulated/sensitive content that the agent should not transmit, log, or include in downstream calls. Returns the inventory of detected items and a redacted version safe for further processing.
- **example_cues**: PII detection, secret scanning, credential detection, GDPR, HIPAA, regex secret scanner, redaction

### 3.2 规划决策阶段（Planning / decision）

#### `threat-model-task`  *(v2: appended one sentence to anchor on "executable agent skill on a concrete plan", not generic templates)*
- **name**: 任务威胁建模 / Threat-Model the Planned Task
- **phase**: planning
- **attack_surface**: cross-cutting (STRIDE, attack tree generation)
- **embed_text**: Generate a structured threat model for a planned task or workflow. Enumerate assets at risk, attacker goals, attack vectors, and likely exploitation paths. Often follows STRIDE or attack-tree formalism. Used by an agent before executing a multi-step plan involving sensitive data, external systems, or privileged operations. Used as an executable agent skill that analyzes a concrete planned workflow, not a generic documentation template.
- **example_cues**: threat model, STRIDE, attack tree, threat enumeration, security review, planned workflow

#### `enforce-policy-as-code`
- **name**: 策略即代码执行 / Enforce Policy-as-Code
- **phase**: planning
- **attack_surface**: OWASP LLM06 (Excessive Agency) · access control
- **embed_text**: Evaluate a planned action against an explicit policy rule set (RBAC roles, OPA/Rego policies, content moderation rules, regulatory compliance constraints). Return allow/deny with rule-level rationale. Used to gate agent decisions where rules are codified and machine-checkable.
- **example_cues**: policy as code, OPA, Rego, RBAC, ABAC, policy enforcement, compliance check

#### `check-tool-permission-scope`
- **name**: 工具权限范围检查 / Check Tool Permission Scope
- **phase**: planning
- **attack_surface**: OWASP LLM06 (Excessive Agency) · least privilege
- **embed_text**: Verify that a planned tool call falls within the scope of permissions the agent (or its current task) has been granted. Reject tool calls that would access resources outside the allowed namespaces, accounts, file paths, or capability tokens. Implements least-privilege enforcement at the agent-runtime boundary.
- **example_cues**: permission scope, least privilege, capability token, scope check, allowed tools

#### `detect-task-overreach`
- **name**: 检测任务越权 / Detect Task Overreach
- **phase**: planning
- **attack_surface**: OWASP LLM06 (Excessive Agency) · scope creep
- **embed_text**: Detect when an agent's plan exceeds the user's stated intent — e.g. the user asked to "summarize this PR" and the agent plans to also push commits, open issues, or modify configuration. Compare the plan's side-effect graph against the elicited user intent, flag steps that aren't justified by the stated goal.
- **example_cues**: scope creep, overreach, plan validation, intent vs plan mismatch, autonomous action review

### 3.3 工具调用阶段（Tool invocation）

#### `validate-tool-argument-safety`  *(v1: replaces v0's `scan-tool-args-for-secrets`)*
- **name**: 工具参数安全校验 / Validate Tool Argument Safety
- **phase**: tool-invocation
- **attack_surface**: unsafe tool arguments · command injection · path traversal · secret leakage
- **embed_text**: Validate outgoing tool-call arguments before execution. Inspect HTTP requests, MCP calls, shell commands, database queries, file paths, URLs, recipients, and resource selectors for unsafe parameters. Detect embedded secrets, command or SQL injection payloads, path traversal, destructive flags, unintended wildcards, overbroad resource scopes, malformed arguments, and parameters that exceed the user's authorized task scope. Return allow, block, sanitize, or clarification-needed.
- **example_cues**: argument validation, parameter safety, unsafe args, command injection, path traversal, destructive flag, secret leakage, sanitize tool call

#### `constrain-workspace-boundary`
- **name**: 工作区边界约束 / Constrain Workspace Boundary
- **phase**: tool-invocation
- **attack_surface**: OWASP LLM06 · sandboxing
- **embed_text**: Restrict the agent's file system, network, and process operations to a declared workspace (project root, allowed hostnames, sandboxed container). Reject path traversal (../), absolute paths outside the workspace, network calls to disallowed hosts, and process spawns that escape the sandbox. Implements the agent equivalent of chroot + egress firewall.
- **example_cues**: workspace boundary, sandbox, chroot, path traversal, egress firewall, network allowlist

#### `validate-agent-tool-trust`  *(v1: replaces v0's `validate-mcp-server-trust`, broadened beyond MCP)*
- **name**: Agent 工具与 Skill 可信度校验 / Validate Agent Tool or Skill Trust
- **phase**: tool-invocation
- **attack_surface**: tool supply chain · skill poisoning · MCP trust
- **embed_text**: Verify the trustworthiness of an agent tool, skill package, MCP server, plugin, or external capability before installation or invocation. Check source provenance, registry membership, publisher identity, signatures, pinned hashes, version history, declared permissions, dependency behavior, and whether tool or skill descriptions contain hidden instructions targeting the LLM. Reject untrusted, modified, overprivileged, or instruction-laden tools.
- **example_cues**: tool trust, skill trust, MCP trust, registry verification, signed tool, tool poisoning, skill poisoning, provenance

#### `detect-supply-chain-risk`  *(v2: added a focus-disambiguation sentence to separate from `validate-agent-tool-trust`)*
- **name**: 供应链风险识别 / Detect Supply-Chain Risk
- **phase**: tool-invocation
- **attack_surface**: OWASP LLM03 (Supply Chain Vulnerabilities)
- **embed_text**: Identify supply-chain risks in dependencies the agent is about to install, import, or invoke: typosquatting package names, abandoned packages, packages with known CVEs, packages from unverified registries, dependency confusion, malicious transitive dependencies. Recommend pinning, alternative packages, or refusal. Focuses on third-party packages and dependencies rather than the agent skill manifest itself.
- **example_cues**: supply chain, dependency audit, SBOM, typosquatting, dependency confusion, CVE check, transitive dependency, package vulnerability

#### `scan-code-for-vulnerabilities`
- **name**: 代码漏洞静态扫描 / Scan Code for Vulnerabilities
- **phase**: tool-invocation
- **attack_surface**: SAST · OWASP general
- **embed_text**: Static analysis of source code (generated by the agent or supplied by the user) for security vulnerabilities: injection flaws, hardcoded secrets, insecure cryptography, unsafe deserialization, command/SQL injection, XSS, path traversal, race conditions. Returns findings with severity, location, and remediation guidance.
- **example_cues**: SAST, vulnerability scanner, code audit, secure code review, semgrep, security linter

#### `detect-malicious-payload-in-tool-output`  *(v2: rewritten as a payload-level firewall — moved away from "hidden text instructions" overlap with `detect-prompt-injection`)*
- **name**: 工具输出恶意载荷检测 / Detect Malicious Payload in Tool Output
- **phase**: tool-invocation
- **attack_surface**: OWASP LLM05 (Improper Output Handling) · payload-level filtering
- **embed_text**: Scan responses returned by external tools (web pages, file contents, MCP server responses, shell command output, downloaded files) for malicious payloads before exposing them to the agent. Inspect HTML/script payloads, file attachments, binary blobs, archive bombs (zip/gzip/tar with extreme expansion ratios), suspicious MIME types, encoded commands, oversized or abnormally structured responses, and known-bad signatures (YARA rules, malware hashes, IOC matches). Acts as a tool-output firewall: payload-level filtering distinct from prompt-injection text-content detection. Quarantine, decode, or strip before passing the response to the agent.
- **example_cues**: output payload scanning, YARA, malware signature, archive bomb, zip bomb, MIME sniffing, binary blob, IOC match, tool output firewall

#### `enforce-rate-and-quota-limits`
- **name**: 速率与配额限制 / Enforce Rate and Quota Limits
- **phase**: tool-invocation
- **attack_surface**: DoS · resource abuse
- **embed_text**: Throttle or cap resource-intensive operations to prevent runaway costs, denial of wallet, denial of service against external APIs, or self-inflicted rate-limit bans. Track per-tool / per-task / per-session counters; trigger backoff or escalate when limits approach.
- **example_cues**: rate limit, quota, denial of wallet, throttling, backoff, cost cap

### 3.4 输出生成阶段（Output generation）

#### `redact-sensitive-output`
- **name**: 输出敏感信息脱敏 / Redact Sensitive Output
- **phase**: output-generation
- **attack_surface**: OWASP LLM02 (Sensitive Information Disclosure)
- **embed_text**: Before returning an output to the user (or writing it to logs / files / external systems), detect and redact PII, secrets, internal infrastructure details, system prompts, or other content that violates the agent's confidentiality boundary. Also redact memorized training data leaks.
- **example_cues**: output redaction, PII redaction, secrets in output, log scrubbing, training data leakage

#### `detect-data-exfiltration`
- **name**: 数据外泄检测 / Detect Data Exfiltration Attempts
- **phase**: output-generation
- **attack_surface**: OWASP LLM02 · MITRE ATLAS Exfiltration tactics
- **embed_text**: Detect attempts to exfiltrate sensitive data via the agent's output channels — including covert channels like markdown image URLs that beacon to attacker-controlled servers, base64-encoded payloads in code blocks, DNS-over-HTTPS lookups embedded in tool calls. Block outputs that would cause sensitive data to leave the trust boundary.
- **example_cues**: data exfiltration, covert channel, beacon, image URL exfiltration, DNS exfiltration

#### `enforce-output-content-policy`  *(v1: embed_text rewritten to be agent-specific, reduce noise from generic toxicity / NSFW classifiers)*
- **name**: 输出内容策略 / Enforce Output Content Policy
- **phase**: output-generation
- **attack_surface**: OWASP LLM09 (Misinformation) · agent output safety
- **embed_text**: Apply output safety policy to content generated by an autonomous agent after retrieval, tool use, code execution, or external system interaction. Check whether the final response, generated file, message, code block, or external write contains dangerous instructions, privacy violations, unauthorized disclosures, policy-prohibited content, or unsafe operational guidance. Return block, rewrite, redact, or escalate.
- **example_cues**: agent output policy, agent output safety, post-tool-use content check, generated content review, escalation gate

### 3.5 全周期 / 监控（Cross-cutting）

#### `audit-trail-recording`
- **name**: 审计日志记录 / Audit Trail Recording
- **phase**: cross-cutting
- **attack_surface**: forensics · compliance
- **embed_text**: Record a tamper-evident audit trail of agent decisions, tool invocations, prompt versions, retrieved context, and final outputs. Designed to support post-incident forensics, regulatory compliance evidence, and root-cause analysis. Storage may be append-only / cryptographically chained.
- **example_cues**: audit log, audit trail, forensic logging, decision log, tamper-evident

#### `incident-response-handler`  *(v2: prepended an agent-execution-context anchor sentence to reduce SIEM/SOAR enterprise-ops noise)*
- **name**: 事件响应处置 / Incident Response Handler
- **phase**: cross-cutting
- **attack_surface**: agent-execution incident response
- **embed_text**: Designed for security events arising during autonomous agent execution, tool use, or skill invocation. Triggered playbook executed when such an event is detected. Stops in-flight actions, snapshots state, isolates affected resources, notifies oncall, opens a tracking ticket, and records timeline. Brings the agent to a safe pause state pending human triage.
- **example_cues**: agent incident response, IR playbook, agent kill-switch, in-flight halt, agent state snapshot, security event handler

#### `escalate-to-human-sentinel`  ⭐
- **name**: 安全哨兵 — 升级到人类确认 / Sentinel: Escalate to Human Confirmation
- **phase**: cross-cutting (highest priority — terminates autonomous execution)
- **attack_surface**: cross-cutting (per project book this is the highest-priority atomic skill)
- **embed_text**: Highest-priority safety primitive. When risk cannot be auto-resolved or when an action's reversibility / blast radius / sensitivity exceeds an autonomy threshold, halt autonomous execution and request explicit human confirmation before proceeding. Captures the current task state, risk rationale, and proposed action so the human can audit and approve / deny.
- **example_cues**: human in the loop, escalate, confirmation, approval gate, human review, kill switch, sentinel

## 4. 设计取舍 / 待审计的事

1. **粒度**：每个 archetype 对应"一类原子能力"，不是"一个具体原子能力"。Stage 3 之后 Module 1.4 应该会从 Stage 3 残量里抽出每个 archetype 下面的 5-15 个具体原子。要不要在 v1 直接做更细一层？我倾向**不要**，否则 anchor 之间互相竞争 cosine 分数，反而模糊。

2. **数量是 20**：少于 15 容易漏召（罕见 niche 安全能力），多于 30 anchor 间相似度互相内卷（一个明显的 SAST skill 可能同时高匹配 `scan-code-for-vulnerabilities` 和 `detect-supply-chain-risk`）。20 是经验折中。

3. **embed 用文本写得长（80-150 词）**：故意写得像一段 SKILL.md 描述，提高跨候选的召回鲁棒性。短标签风格的 anchor 在 cosine 上会偏向其他短描述，跟长 SKILL.md 算分容易低估。

4. **Per-anchor top-N cap ∪ 全局阈值（v1 新增）+ per-anchor min threshold（v2 增强）**：v0 的"全局 top-K + 阈值"规则会让宽泛 anchor 吞掉残量预算；v1 加了 per-anchor cap 让每个 anchor 各取 top-N，但仍有"低质量 anchor 强行补满 top-N"的风险（top-150 里可能含大量 cosine 0.30 级别的弱相关样本）。**v2 在 per-anchor 上又加了 `anchor_min_threshold = 0.55`**：候选必须 cosine ≥ 0.55 才参与该 anchor 的 top-N 抽样。具体规则见 §1.4。

5. **τ 与 anchor_min_threshold 必须校准（v2 新增）**：默认 0.65 / 0.55 只是首跑初始值。不同 embedding 模型 / 文本长度 / 候选来源会让分数分布偏移，硬编码风险大。首跑后必须用"top 30 + 0.65 附近 30 + 0.55-0.65 区间 30"的抽样做人工标注，按精度-召回权衡再调阈值。**首次 manifest 保留全 20 个 cosine**，阈值调整后不重新调 API。详见 §1.4.1。

6. **Anchor 文本与候选文本的工程化构造（v2 新增）**：embed 输入不是直接拍到 anchor 的 `embed_text` 或候选的 SKILL.md。Anchor 拼接 `example_cues` 提升对短描述的召回（§1.1）；候选剥离 boilerplate 段落避免 README 噪声稀释 safety 信号（§1.2）。这两个工程决策同等重要，不做的话 cosine 分数对短候选与有重型 README 的候选都会偏离真实相关性。

7. **没单独建 MCP-only archetype**：v1 的 `validate-agent-tool-trust` 已经把 MCP trust + skill trust + plugin vetting 合在一起覆盖；不需要再单建 MCP-specific anchor。

8. **缺什么可能**：
   - 模型层面（Adversarial ML 类）—— 没建专项，因为我们的原始数据基本不涉及模型攻击（NIST 100-2 是 reference 但不在 skill 库里）
   - 模型供应链 / weight tampering —— 罕见，没建
   - Web3 / 智能合约审计 —— 有大量 trailofbits 类 skill，但语义上能被 `scan-code-for-vulnerabilities` 召回
   - **LLM 输出毒性专用 detector**（不是 enforce-output-content-policy 这种 enforcement，而是单独的 detection）—— 没建独立项；如果审计发现召回不够再加

## 5. 你审计完想反馈什么

- **要不要加 / 删 / 合并 archetype？**（最影响召回质量）
- **embed 文本要不要重写**？某些写得过 generic 的可以更具体（比如 `detect-task-overreach`、`enforce-policy-as-code`）
- **phase / attack_surface 字段值是否准确**？这俩字段后续会用在 Module 1.4 + Module 3 的阶段-技能映射表
- **有没有项目书里提到但这里漏掉的能力**？

## 6. 下一步

- 你复审 v2（重点看 §0 v1→v2 changelog 的 9 条改动是否都对、§1.1-1.6 的 Stage 3 实施契约是否完整、§3 4 个 archetype 的 embed_text 微调是否到位）
- 复审通过后我会：
  1. 把 archetype 列表序列化成 Python config（`scripts/_archetypes.py`，含 `embed_text + example_cues` 拼接逻辑）
  2. 写 Stage 3 脚本（`scripts/dedup_stage3_embedding.py`），实现：
     - 智谱 embedding-3 调用（API key 走 `ZHIPU_API_KEY` 环境变量）
     - 本地 vector 缓存（`data/cache/embeddings/`）+ batching + 429 退避
     - 候选 `relevance_text` 构造（含 boilerplate 剥离）
     - per-anchor top-N + anchor_min_threshold ∪ global threshold 选择规则
     - manifest 输出含 `top3_anchors` + `all_scores` + `kept_by`（§1.6 schema）
  3. 跑一次得 Stage 3 残量并落 manifest 到 `reports/dedup_stage3_embedding_<date>.json`
  4. 抽样校准 τ / anchor_min_threshold（§1.4.1 的流程）
  5. 按记忆规则刷新 [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) 的进度表
