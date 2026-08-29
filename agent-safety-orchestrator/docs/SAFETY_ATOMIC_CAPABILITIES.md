# Atomic Safety Capability Units — Reference Vocabulary (Draft v0)

> **状态**：v0 手起初稿（2026-05-09），**待用户审定**。
> **用途**：固化为 LLM 受控词表，给子任务 1.2 / 1.3（对 Stage 3 残量 1390 条做 LLM 审计 + 原子能力抽取）当输出标签集合。
> **来源**：v2 archetypes（粗骨架）+ 11 份 references（OWASP LLM Top 10、MITRE ATLAS、MCP best practices、Lakera prompt injection guide、SlowMist / UseAI-pro / ClawSec 实践指南、Anthropic RSP、NIST AI RMF）+ 项目书 §1.1 列举的能力关键词。

## 0. Changelog

- **v1.3**（2026-06-08）：**真层级（router-first hierarchy）重构——packaging-only，词表零改动**（仍 95 atoms / 19 archetypes / 5 phases / 60 hook + 21 hybrid + 14 skill）。① **14 个 archetype 从 top-level skill 降为 Router 的 reference 文档**：`skills/<archetype>/SKILL.md` → `skills/safety-router-skill/references/archetypes/<archetype>.md`。唯一 host-discovered skill = `safety-router-skill`。② **Router §3.2 路由表语义改变**：从"invoke archetype skill"改为"`Read references/archetypes/<name>.md` then apply"——archetype 不再是可独立调用的 skill，**结构性保证 router-first**（模型无法绕过 Router 直接碰子检查）。③ **被动 context 收缩**：session-start 只注入 1 条 Router description（旧版 15 条 skill description 全在 context）→ passive priming 面从 15 降到 1。④ **下游影响**：pilot 归因模型升级为 6 类 hierarchy-gated（skill-leg 信号 = `Skill=safety-router-skill` + `Read=archetypes/*`；新增 `passive-context-effect` 类，把"没调 Router 却被拦、vanilla 不复现"从误记 built-in 中拆出，算 bundle 软功劳）。⑤ **此条不改 §10 历史包装规范文本**（v0.7 的 `skills/<archetype-id>/SKILL.md` 描述保留作 traceability）；当前真实布局以本条 + PROJECT_OVERVIEW §3/§4.6 文件树为准。两个 installer（Claude plugin / Codex adapter）靠 `skills/*/` 枚举自动适配。plugin 版本 1.2 → **1.3**。
- **v1.1**（2026-05-12）：**部署元数据补全，atom 集合 + enforcement_mode 不变**（仍 95 / 19 archetypes / 60 hook + 21 hybrid + 14 skill）。① **8 个 hook-network atom 卡片加 `requires_network` + `fail_policy`**（+ 1 个加 `requires_api_key`）：check-package-cve / detect-hallucinated-package / check-package-recency-anomaly / check-malware-hash-ioc / check-package-typosquat / check-dependency-confusion / verify-skill-signature / verify-tool-publisher-identity。Packaging 时由共享 cache/health helper 统一执行外部 IO + 降级。② **新增 §12 部署配置与降级语义**：三层 config tier（零配置 / 单 `.env` / air-gap）、fail_policy 三态（fail-open-warn / fail-soft-block / fail-closed）、共享 helper 模块（cache + health）、8 atom 部署元数据汇总表。③ **出货文件 16 → 18**：加 2 个 helper（cache/snapshot + health/status）。④ **freeze 含义明确**：v1 freeze 指 atom 集合 + 定义性字段冻结（id / parent / phase / definition / scope_in / scope_out / signal_phrases / related），部署元数据（requires_network / requires_api_key / fail_policy / 未来字段）允许在 v1.x 继续补，不构成 v2 触发条件。⑤ **撤回**：v1.1 起草过程中，AI 协作者一度误判 `audit-ci-workflow-security` + `detect-malicious-postinstall-script` 当前是 hook 需重标 hybrid，**实际这两个原本已是 hybrid**，无修改——记录这个误读以警示后续读者：变 enforcement_mode 前必须直接 grep `ATOM_ENFORCEMENT_MODE` dict 确认现状，不要从 archetype 聚合反推。
- **v1**（2026-05-11）：🔒 **词表冻结**（freeze）。内容 = v0.7.1。**95 个原子 / 19 archetypes / 16 个出货文件**（1 Router meta + 14 SKILL.md + 1 hook config bundle）。enforcement_mode = 60 hook + 21 hybrid + 14 skill。下游 §4.6 archetype SKILL.md 包装、Module 2 Sentinel、Module 3 Router runtime 都以此为基准。词表迭代演化路径：95 (v0.3 理论起草) → 115 (v0.6 LLM 审计扩容) → 98 (v0.7 轻量化裁减) → **95 (v1 = v0.7.1, A2A 前瞻原子下架)**。
- **v0.7.1**（2026-05-11）：v0.7 当日补充裁减——`validate-agent-tool-trust` 内 3 个 planning-阶段 A2A trust 原子下架（`verify-delegation-chain` / `verify-agent-identity` / `evaluate-mcp-server-trustworthiness`），全部过于前瞻：A2A 委托协议 / agent identity 注册中心 / MCP server reputation registry 在 2025-2026 都还不是 agent 主流场景。validate-agent-tool-trust 14 → **11 atoms**；总量 98 → **95**；planning 阶段 13 → 10。enforcement_mode 更新为 **60 hook + 21 hybrid + 14 skill = 95**。
- **v0.7**（2026-05-11）：按"轻量化插件 / agent 运行时 skill"判据精简，把不符合 LLM agent 安全 guardrail 定位的原子下架。**判据**：(a) 运行时点 = 单 turn / tool-call / output（hook < 500ms，skill < 30s）；(b) 作用对象 = agent 自己的 input/plan/args/output；(c) 2025-2026 有现成实现路径；(d) 粒度适中（不是 SMT 形式化也不是 TCP packet）。**删 17 atoms**：研究级（`check-logic-consistency` / `evaluate-formal-policy-constraint`）、vapor-infra（`compute-agent-trust-score` / `query-agent-reputation` / `cryptographic-intent-binding` / `enable-tamper-evident-storage`）、离线分析（`build-threat-actor-profile` / `analyze-against-known-threat-checklist` / `validate-rules-of-engagement` / `check-sbom-completeness` / `evaluate-regulatory-compliance-rule`）、多调用统计（`detect-c2-beaconing-pattern`）、高 FP 框架特化 SAST（`detect-missing-authorization-check` / `detect-mass-assignment-vulnerability` / `audit-cors-configuration`）、agent-as-output deliverable（`generate-stride-threat-model` / `generate-attack-tree`）。**移 1 atom**：`enumerate-task-side-effects` 从 `threat-model-task` → `detect-task-overreach`（runtime side-effect 列表才是 guardrail）。**删 1 archetype**：`threat-model-task` 整组下架。词表 115 → **98**（archetype 20 → 19）。`scan-code-for-vulnerabilities` 5 个原子保留为 **PreToolUse matcher 限定到 Write\|Edit\|MultiEdit** 的 hook（只在改代码时触发；其他场景 0 开销）。enforcement_mode = **60 hook + 21 hybrid + 14 skill = 95**；archetype 打包 (5 pure-hook + 0 pure-skill + 14 mixed)，出货 = 1 Router meta + 14 SKILL.md + 1 hook config = **16 个文件**。
- **v0.6**（2026-05-11）：基于 1390 record LLM 审计的两块数据信号落地。① **wrong-parent 修正**：`check-rbac-role` 从 `enforce-policy-as-code` 搬到 `check-tool-permission-scope`——LLM 19 次错挂揭示 RBAC 本质是 per-call permission gate，和 `verify-allowed-tool-list`/`verify-resource-namespace-scope`/`verify-capability-token` 同构，不是 policy 引擎规则。② **新原子 + scope MERGE**：LLM 提议的 94 条 suggested_new_atoms 经聚类去重后保留 **20 条新原子**（多 agent 信任 / 委托链、A2A 身份、CI/CD 供应链、OWASP API、形式化策略、威胁情报清单、C2 beacon、子 agent 隔离…）+ **11 处 scope_in MERGE**（IBAN、MRN、unicode bidi、HTML 注释、container CVE、Trivy、Erlang 反序列化、GDPR 数据主体权利、phishing URL 等）。词表从 95 涨到 **115**（archetype 数仍 20）。enforcement_mode 分布更新为 **69 hook + 28 hybrid + 18 skill**；archetype 打包从 (5 pure-hook + 1 pure-skill + 14 mixed) 变为 (**4 pure-hook + 0 pure-skill + 16 mixed**)，最终出货 = 1 Router meta + 16 SKILL.md + 1 hook config bundle = **18 个文件**。
- **v0.5**（2026-05-10）：用户进一步拍板**引入 enforcement_mode 作为包装第一刀**——hook（host 硬强制）/ skill（agent LLM 决策）/ hybrid（hook fast + LLM fallback）。每个原子标 enforcement_mode；archetype 包装按内部 atoms 的 enforcement 分布走：5 个 pure-hook archetype 不出 SKILL.md（只出 hook config），1 个 pure-skill + 14 个 mixed-enforcement 出 SKILL.md。最终出货 = 1 个 Router meta-skill + 15 个 SKILL.md + 1 个 hook config bundle = **17 个文件**（比 v0.4 的 21 个再降）。execution_type 降级为次要维度，只对 SKILL.md 内部 skill/hybrid tools 有意义。详见 §10 重写。
- **v0.4**（2026-05-09）：用户拍板**包装模型从 "1 atom = 1 SKILL.md" 改为 "1 archetype = 1 SKILL.md"**。原子词表（95 个）不变，但作为 SKILL.md 内部的 tools / steps 存在；最终出货 = 1 个 Router meta-skill + **20 个** archetype 级 SKILL.md。每个 SKILL.md 标注 `execution_type`（workflow / checklist / mixed）告诉 agent 内部 tools 怎么协调。详见 §10 重写。
- **v0.3**（2026-05-09）：用户决定**接受 v0.1 原子集合用作 1.2/1.3 LLM 审计输入**（不在审计前做人工增删）；最终人工过滤推迟到 1.4 蒸馏期，依据实际审计结果决定。本版仅做一项 schema 微调：
  - §7 LLM 输出 schema 加 `suggested_new_atoms` 字段——结构化新原子建议，方便 1.4 按 `proposed_id` 直接聚类，不再依赖人肉解析 `free_form_notes`
- **v0.2**（2026-05-09）：用户审定 v0.1 阶段，落档两项架构决策：
  - 新增 **§10 原子 SKILL.md 包装标准**（每个 atom 最终落地为 SKILL.md 包，4 段固定结构 purpose / when_to_use / how_to_check / verdict_schema；代码型 atom 假设 host 给 Bash 权限；不做自反射，项目结束出一份 frozen 包）
  - 新增 **§11 Router 架构定位**——Router **不是独立程序**，而是一份 meta-skill SKILL.md；agent host 的主 LLM 读后即成 Router。附 §11.3 与传统 middleware 的延迟 / 成本权衡矩阵 + 4 条优化手段
- **v0.1**（2026-05-09）：根据用户反馈，**主审阅视图改为按 agent 执行阶段组织**（对齐项目书 §3 Safety Router 的"阶段-技能映射表"需求）。原子集合**未增删**（实际 95 个，v0 的 "94" 是统计笔误），仅重新分组 + 补充 cross-phase 复用矩阵。原 archetype 视图作为对照参考保留在 §5（子节编号沿用 4.X 不重排，方便 git diff 对照 v0）。
- **v0**（2026-05-09）：手起初稿，95 个原子能力分布在 20 个 archetype 下；定义了 LLM 输出 schema；尚未跑过任何审计

## 1. 这份文档干什么用

### 1.1 跟 v2 archetypes 的层级关系

```
v2 Archetypes (20)              ← 粗骨架，给 Stage 3 embedding 召回用
        │
        │ 每个 archetype 拆 2-10 条具体原子能力
        ▼
原子安全单元参考表 (~74)         ← 本文件，给 LLM 当输出词表
        │
        │ 1.2/1.3 LLM 给 1390 残量打标签；可能新增 / 合并 / 删除
        ▼
最终 Atomic Safety Skill 库     ← 1.4 后产出，每个原子下挂 1+ 个 skill 实现
```

**关键差异**：
- Archetype 写得像"一段 SKILL.md 自我描述"（embedding 友好的长段落）
- 原子能力写得像"LLM 可以快速判断该不该打这个标签"（紧凑、有 scope_in/scope_out 边界、有兄弟原子互斥提示）

### 1.2 跟最终原子库的关系

这份**不是**最终原子库。它只是 LLM 审计阶段的"封闭词表"，确保 1390 份 LLM 输出能彼此聚合。1.2 / 1.3 跑完后会有两类调整：
1. **支持太薄的原子合并**（某个原子在 1390 中只有 0-2 个 skill 命中 → 跟兄弟合并）
2. **free-form notes 反复出现的能力补进来**（说明词表漏了真实存在的能力类型）

**最终原子库的形态**：迭代后的每个原子落地为 **SKILL.md 包**（详见 §10）；整个项目最终出货 = 1 个 Router meta-skill + 14 个 archetype 级 SKILL.md + 1 个 hook config bundle（覆盖 95 个原子）= **16 个顶层文件**（v0.7），作为 frozen artifact。

### 1.3 主审阅入口

→ **§4 按 agent 执行阶段组织** 是主视图（紧凑 IDs + 一行定义，附 cross-phase 复用矩阵）。
→ §5 是按 archetype 组织的详细卡片（含 scope_in / scope_out / signal_phrases / related 等全字段），review 时用作对照。

### 1.4 LLM 输出契约

每条 stage3 残量审计输出固定 JSON（详见 §7 schema）。最关键的字段是：

```json
{
  "primary_atoms": ["validate-tool-argument-safety/detect-shell-command-injection"],
  "secondary_atoms": ["check-tool-permission-scope/verify-allowed-tool-list"],
  "free_form_notes": "..."
}
```

- `primary_atoms`：本 skill **核心承担**的原子能力（一般 1-3 个）
- `secondary_atoms`：附带能力（不是主功能但有覆盖）
- `free_form_notes`：兜底，描述本词表没收的能力，留给 1.4 迭代用

## 2. 字段 schema（每个原子单元的定义格式）

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | ✅ | 全小写连字符 slug。LLM 输出格式 = `<parent_archetype>/<atom_id>` |
| `parent` | ✅ | 归属的 v2 archetype id |
| `phase` | ✅ | `input-understanding` / `planning` / `tool-invocation` / `output-generation` / `cross-cutting`。**可以**跟 parent 不一致（原子可以更细化 phase） |
| `attack_surface` | ✅ | OWASP LLM Top 10 编号 / MITRE ATLAS tactic / MCP-spec 类别 / 自定义 |
| `definition` | ✅ | **一句话**精确边界，描述该原子做什么动作（不是"它有什么意义"） |
| `scope_in` | ✅ | 3-5 个显式包含场景，让 LLM 知道哪些 skill 文档明确属于本条 |
| `scope_out` | ✅ | 2-4 个显式排除场景 + 该去哪个兄弟原子，**防 LLM 误打** |
| `signal_phrases` | ✅ | 5-10 个候选 skill 文档里出现这些片段 → 大概率属于本条 |
| `related` | ✅ | 2-4 个易混淆兄弟原子的 id，LLM 选 primary 时用 |

## 3. 全局设计原则

1. **粒度**：一个原子 = 一个**独立可审计的动作**。同一原子下面可以挂多种实现（OPA、自定义 regex、LLM judge 都是 `evaluate-opa-rego-rule` 的实现，不再细分）。如果两个原子在 1390 残量里几乎总是同时被需要，1.4 阶段合并。
2. **跟 archetype 的 phase 关系**：默认继承，但允许更细。例：`detect-pii-in-input` 是 input phase（与 parent 一致）；`record-tool-invocation-trace` 是 cross-cutting（与 parent `audit-trail-recording` 一致）；但 `redact-output-system-prompt` 是 output phase（parent `redact-sensitive-output` 也是 output，一致）。一致性由 parent 强制时不写，需偏离时显式写。
3. **跟工具 / 算法解耦**：原子描述"能力"，不绑定算法。`run-sast-scan` 不区分 semgrep / codeql / bandit；`match-yara-rule` 不指定 YARA 版本。
4. **覆盖范围限定**：项目只蒸馏 **agent runtime safety** 相关的 skill，**不蒸馏** ML 模型训练阶段的攻击/防御（poisoning / evasion / membership-inference 等 NIST AI 100-2 范畴）。MITRE ATLAS 中跟训练相关的 tactic 不在词表内出现。
5. **OOS 显式标记**：词表外但反复看到的能力，由 LLM 写到 `free_form_notes`，1.4 迭代时决定是否新增。
6. **Phase-based 主组织**：每个原子声明一个 **primary phase**（项目书定义的 input-understanding / planning / tool-invocation / output-generation / cross-cutting 之一）。Router 在当前阶段查表时优先取 primary phase 匹配的原子。同一原子可在多个阶段被 Router 调用，**通过 §4.6 cross-phase 矩阵显式标记**（不为同一能力创建多个分阶段变体，避免 LLM 标签膨胀）。

## 4. 按 Agent 执行阶段组织（Safety Router 查表视图，主审阅入口）

> **设计依据**：项目书 §3 描述 Safety Router 维护"阶段-技能映射表"——按当前任务阶段（输入理解 / 规划决策 / 工具调用 / 输出生成）和风险类型路由到对应原子安全 skill。本节按这五个阶段（含全周期）重新切分所有 95 个原子，方便 Router 实现时一眼看到"在 phase X 我应该 load 哪些 atoms"。
>
> **Cross-phase 标记**：📌 表示该原子的 primary phase 在别处，但 Router 在本阶段也会查它。完整字段卡片在 §5（按 archetype 分组）。
>
> **格式**：每条原子一行，`atom-id` — 一句话定义。详细字段（scope_in / scope_out / related / signal_phrases）见 §5 对应 archetype。

### 4.1 输入理解阶段（input-understanding）

**Router 触发时机**：用户输入或外部输入刚到达，agent 尚未开始 plan
**主要回答**：注入？歧义？输入侧敏感信息？
**原子总数**：12 primary + 1 cross-listed

#### 4.1.1 detect-prompt-injection 系列（input-side variants）— 详 §5.1
- `detect-direct-prompt-injection` — 检测**用户输入本身**的指令覆写 / role swap / instruction smuggling
- `detect-jailbreak-template` — 匹配已知 jailbreak / red-team 模板
- `detect-system-prompt-extraction` — 检测企图提取 / 重复 system prompt 的请求
- `detect-roleplay-escape` — 检测通过 role-play / persona 切换绕过安全约束

#### 4.1.2 classify-input-intent-ambiguity 系列 — 详 §5.2
- `classify-request-ambiguity-level` — 给输入的歧义度（特别是 safety-critical 的歧义）打分
- `detect-destructive-action-keyword` — 用户输入中匹配破坏性动词 / 红线关键词
- `elicit-clarification-before-act` — 歧义阈值触发后向用户回问

#### 4.1.3 scan-input-for-pii-and-secrets 系列 — 详 §5.3
- `detect-pii-in-input` — PII / GDPR / HIPAA 类
- `detect-payment-card-data` — Luhn + 格式启发式检测信用卡号
- `detect-credential-in-input` — API key / OAuth / JWT / cloud key
- `detect-private-key-input` — RSA / EC / SSH / PGP / wallet seed
- `redact-input-pii` — 替换 / 脱敏后再喂下游

#### 4.1.4 Cross-phase 借用（primary 在别处但本阶段也查）
- 📌 `detect-indirect-prompt-injection`（primary: tool-invocation §4.3.8）— 用户**粘贴外部抓取内容**作为 input 时，input phase 也要查（不只是 tool 返回值场景）

---

### 4.2 规划决策阶段（planning）

**Router 触发时机**：input 已解析，agent 准备 plan / 选 tool / 选参数
**主要回答**：合规策略？权限范围？是否越权？
**原子总数**：13 primary（v0.7 删除了 threat-model-task 整组，回到 v0.3 之前的 planning 阶段焦点：policy / permission / overreach）

#### 4.2.1 enforce-policy-as-code 系列 — 详 §5.5
- `evaluate-opa-rego-rule` — OPA / Rego / Cedar 评估
- `evaluate-content-moderation-rule` — 内容策略作为 planning gate（不是 output review）

#### 4.2.2 check-tool-permission-scope 系列 — 详 §5.6
- `verify-allowed-tool-list` — tool allowlist
- `verify-resource-namespace-scope` — 资源命名空间（path / repo / account / S3 bucket）允许范围
- `verify-capability-token` — capability token / macaroon / biscuit
- `check-rbac-role` — RBAC / ABAC 角色 → action 矩阵（v0.6 从 enforce-policy-as-code 搬入）

#### 4.2.3 detect-task-overreach 系列 — 详 §5.7
- `compare-plan-vs-stated-intent` — plan 与 user intent 的 divergence 评分
- `flag-unjustified-side-effect` — 标记 plan 中无 user-intent 支持的 step
- `detect-autonomy-budget-exceeded` — 累计 action / 写 / 花 超出 autonomy budget
- `enumerate-task-side-effects` — 列举 plan 全部 side effects（v0.7 从已下架的 threat-model-task 搬入）

#### 4.2.5 Cross-phase 借用
- 📌 `detect-hidden-instruction-in-tool-description`（primary: tool-invocation §4.3.3）— agent 选 tool 时**读 tool description**，planning 阶段也要查（这是 skill poisoning 在 planning 路径上的入口）
- 📌 `detect-skill-permission-overrequest`（primary: tool-invocation §4.3.3）— 类似上面，agent 选 tool 时也要查"这个 tool 要求的权限是不是过宽"

---

### 4.3 工具调用阶段（tool-invocation）

**Router 触发时机**：每次 tool call 前 / 中 / 后（最重的阶段，49 个原子驻留在此）
**主要回答**：参数安全？工具可信？工作区边界？供应链？工具返回值有恶意 payload？速率合理？
**原子总数**：49 primary

#### 4.3.1 validate-tool-argument-safety 系列 (8) — 详 §5.8
- `detect-shell-command-injection`
- `detect-sql-injection`
- `detect-path-traversal`
- `detect-destructive-flag`
- `detect-unsafe-url`
- `detect-secret-in-args`
- `detect-overbroad-resource-selector`
- `validate-tool-argument-schema`

#### 4.3.2 constrain-workspace-boundary 系列 (4) — 详 §5.9
- `enforce-filesystem-sandbox`
- `enforce-network-egress-allowlist`
- `enforce-process-sandbox`
- `detect-sandbox-escape-attempt`

#### 4.3.3 validate-agent-tool-trust 系列 (10) — 详 §5.10
- `check-tool-typosquat-name`
- `verify-skill-signature`
- `verify-tool-publisher-identity`
- `detect-hidden-instruction-in-tool-description` *（也在 planning 借用，§4.2.5）*
- `detect-tool-loader-exploit`
- `detect-skill-permission-overrequest` *（也在 planning 借用，§4.2.5）*
- `detect-mcp-confused-deputy`
- `detect-mcp-token-passthrough`
- `detect-mcp-session-hijacking`
- `detect-mcp-ssrf`

#### 4.3.4 detect-supply-chain-risk 系列 (7) — 详 §5.11
- `check-package-typosquat`
- `check-package-cve`
- `check-dependency-confusion`
- `audit-install-hook`
- `check-sbom-completeness`
- `check-package-recency-anomaly`
- `detect-malicious-postinstall-script`

#### 4.3.5 scan-code-for-vulnerabilities 系列 (5) — 详 §5.12
- `run-sast-scan`
- `detect-hardcoded-secret-in-code`
- `detect-insecure-cryptography`
- `detect-unsafe-deserialization`
- `detect-injection-flaw`

#### 4.3.6 detect-malicious-payload-in-tool-output 系列 (5) — 详 §5.13
- `match-yara-rule`
- `check-malware-hash-ioc`
- `detect-archive-bomb`
- `detect-suspicious-mime-type`
- `strip-active-html-script`

#### 4.3.7 enforce-rate-and-quota-limits 系列 (4) — 详 §5.14
- `enforce-tool-call-rate-limit`
- `enforce-token-budget-cap`
- `enforce-cost-cap-per-task`
- `detect-runaway-loop`

#### 4.3.8 detect-prompt-injection 系列（tool-side variant，1）— 详 §5.1
- `detect-indirect-prompt-injection` — 检测 **tool 返回内容**（HTML/MCP response/file/RAG）里嵌入的指令文本 *（也在 input phase 借用，§4.1.4）*

#### 4.3.9 detect-data-exfiltration 系列（tool-side variants，2）— 详 §5.16
- `detect-dns-exfiltration-pattern` — DNS tunnel 长子域 / TXT 异常签名
- `detect-covert-channel-in-tool-call` — HTTP header / cookie / user-agent / webhook 字段暗道

---

### 4.4 输出生成阶段（output-generation）

**Router 触发时机**：agent 准备返回 response / 写文件 / 发消息 之前
**主要回答**：要不要脱敏？内容是否合规？是否带 exfil 信号？
**原子总数**：11 primary

#### 4.4.1 redact-sensitive-output 系列 (4) — 详 §5.15
- `redact-output-pii`
- `redact-output-secret`
- `redact-output-system-prompt`
- `redact-output-internal-infra`

#### 4.4.2 enforce-output-content-policy 系列 (5) — 详 §5.17
- `review-generated-code-output` — 输出 code block 里的危险 shell 模式 / curl|sh / fork bomb / backdoor
- `review-generated-message-output` — 自由文本消息（reply / email / Slack / PR comment）的 policy 与 hedging
- `review-generated-file-write` — 写文件前对 content 做 review
- `detect-dangerous-instruction-in-output` — agent 给 user 的危险 / 双用 / 不安全建议
- `enforce-disallowed-content-rule` — deployer disallowed-content 规则包应用到 output

#### 4.4.3 detect-data-exfiltration 系列（output-side variants，2）— 详 §5.16
- `detect-markdown-image-beacon` — markdown 图片 URL 把数据发到 attacker host
- `detect-base64-payload-in-output` — output 里的可疑长 base64 / hex blob

---

### 4.5 全生命周期（cross-cutting）

**Router 触发时机**：每个阶段都可能调用（不绑特定阶段）
**主要回答**：留 audit？发生 incident 怎么办？要不要请人裁决？
**原子总数**：13 primary

#### 4.5.1 audit-trail-recording 系列 (4) — 详 §5.18
- `record-decision-trace`
- `record-tool-invocation-trace`
- `record-prompt-and-context-snapshot`
- `enable-tamper-evident-storage`

#### 4.5.2 incident-response-handler 系列 (5) — 详 §5.19
- `halt-in-flight-action`
- `snapshot-agent-state`
- `isolate-affected-resource`
- `notify-oncall-and-open-ticket`
- `execute-recovery-playbook`

#### 4.5.3 escalate-to-human-sentinel ⭐ 系列 (4) — 详 §5.20
- `request-human-confirmation`
- `present-risk-rationale`
- `await-human-decision-or-timeout`
- `log-human-decision-outcome`

> ⭐ 这一组是项目书指定的"最高优先级原子能力"。**本项目 training-free**——不实现 ML Sentinel；本组 4 atoms 提供确定性 HITL 通道（pause + 用户确认）。Atom 接口已对齐 future Sentinel ML 预测器（separate downstream project），未来接入无需改 bundle。Router 在**任何阶段**判定 risk 不可自动消解时都会路由到这一组。

---

### 4.6 Cross-phase 复用矩阵

下表列出 Router 在多个阶段会查询的原子（● = primary phase，○ = secondary，○* = 关联原子但不是同一原子）。这是 Safety Router 实现"阶段-技能映射表"时的核心 lookup。

| Atom / 系列 | input | planning | tool-inv | output | cross-cut | 备注 |
| --- | :---: | :---: | :---: | :---: | :---: | --- |
| `detect-direct-prompt-injection` | ● | | | | | 仅 input-side |
| `detect-indirect-prompt-injection` | ○ | | ● | | | tool 返回值 + 用户粘贴外部内容都查 |
| `detect-jailbreak-template` | ● | | | | | |
| `detect-system-prompt-extraction` | ● | | | | | |
| `detect-roleplay-escape` | ● | | | | | |
| `detect-hidden-instruction-in-tool-description` | | ○ | ● | | | agent 选 tool 时也要查 description |
| `detect-skill-permission-overrequest` | | ○ | ● | | | agent 选 tool 时也要查权限 |
| `detect-credential-in-input` | ● | | ○* | | | tool-inv 用兄弟原子 `detect-secret-in-args` |
| `detect-data-exfiltration` 系列 | | | ●(2) | ●(2) | | tool-inv 抓 outbound channel；output 抓 markdown beacon / encoded blob |
| `redact-*` 系列 | ○* | | | ● | ○ | input-side 用兄弟 `redact-input-pii`；cross-cutting 是 log 写入时 |
| `audit-trail-recording` 系列 | ○ | ○ | ● | ○ | ● | Router 在每个 phase 后都写一笔 |
| `incident-response-handler` 系列 | | | ○ | | ● | tool-inv 是最常见的 trigger 点 |
| `escalate-to-human-sentinel` 系列 | ○ | ● | ● | ● | ● | 任何 phase 都可能升级 |

**实现提示**：
- Router 在 phase X 加载 atoms 时，应同时取所有 primary=X 的原子 + cross-phase 表里 X 列有 ○ 的原子
- Cross-cutting 的三组（audit / incident / sentinel）建议**始终常驻**，不依赖 phase
- ○* 标记的关系**不要由 Router 在运行时合并**，因为它们 scope_in/scope_out 不同；Router 只按 phase 取自己 phase 的那个

---

## 5. 按 Archetype 组织（详细原子卡片，对照参考）

> 子节编号沿用 v0 的 4.X 不重排，方便 git diff 对照。
>
> 此处是**完整字段卡片**——审阅时若需要看某个原子的 scope_in / scope_out / signal_phrases / related 等，从 §4 跳到这里对应的子节即可。

### 5.1 `detect-prompt-injection` 下属（5 个原子）

#### `detect-direct-prompt-injection`
- **parent**: `detect-prompt-injection` · **phase**: input-understanding · **attack_surface**: OWASP LLM01.direct
- **definition**: Detect injection attempts in the user-supplied input itself (not in fetched content), where the user tries to override the system prompt or operator instructions.
- **scope_in**: "ignore previous instructions"-style overrides, role swap requests in user message, system prompt overwrite attempts, instruction-as-data smuggling in user text, unicode Cf / bidi-override / zero-width characters hiding instructions
- **scope_out**: instructions hidden in tool/web/file output → `detect-indirect-prompt-injection`; jailbreak templates targeting safety policy → `detect-jailbreak-template`
- **signal_phrases**: prompt injection, direct injection, system prompt override, ignore previous, instruction smuggling, role swap
- **related**: `detect-indirect-prompt-injection`, `detect-jailbreak-template`, `detect-roleplay-escape`

#### `detect-indirect-prompt-injection`
- **parent**: `detect-prompt-injection` · **phase**: tool-invocation · **attack_surface**: OWASP LLM01.indirect
- **definition**: Detect injection instructions hidden in **content fetched from external sources** (web pages, file contents, MCP responses, API JSON, RAG documents) that target the LLM rather than the user.
- **scope_in**: HTML/markdown content with hidden instructions, instructions in fetched email/PR/issue bodies, RAG document poisoning, instructions in API JSON fields, HTML comment / `<!-- ... -->` with hidden instructions
- **scope_out**: payload-level malicious binaries → `detect-malicious-payload-in-tool-output`; user's own input → `detect-direct-prompt-injection`
- **signal_phrases**: indirect injection, fetched content injection, RAG poisoning, document instruction, hidden instruction in tool output
- **related**: `detect-direct-prompt-injection`, `detect-malicious-payload-in-tool-output`, `detect-hidden-instruction-in-tool-description`

#### `detect-jailbreak-template`
- **parent**: `detect-prompt-injection` · **phase**: input-understanding · **attack_surface**: OWASP LLM01.jailbreak
- **definition**: Detect prompts matching known jailbreak / red-team templates designed to elicit policy-violating responses.
- **scope_in**: DAN-style templates, fictional-framing escapes ("write a story where..."), prefix-suffix manipulation, well-known jailbreak corpora matches
- **scope_out**: zero-day jailbreaks discovered via behavior → `enforce-output-content-policy`; safety policy enforcement on output → `enforce-output-content-policy`
- **signal_phrases**: jailbreak, jailbreak detection, jailbreak template, DAN, red team prompt, anti-policy prompt
- **related**: `detect-direct-prompt-injection`, `detect-roleplay-escape`, `enforce-output-content-policy`

#### `detect-system-prompt-extraction`
- **parent**: `detect-prompt-injection` · **phase**: input-understanding · **attack_surface**: OWASP LLM07 (System Prompt Leakage)
- **definition**: Detect attempts to extract / dump / repeat back the agent's system prompt or hidden operator instructions.
- **scope_in**: "repeat the text above", "what are your instructions", base64/translation-based extraction, indirect leakage via summarization request
- **scope_out**: redacting system prompt **after** generation → `redact-output-system-prompt`; jailbreak that doesn't target prompt extraction → `detect-jailbreak-template`
- **signal_phrases**: system prompt leak, prompt extraction, instruction extraction, prompt dump, repeat instructions
- **related**: `redact-output-system-prompt`, `detect-jailbreak-template`

#### `detect-roleplay-escape`
- **parent**: `detect-prompt-injection` · **phase**: input-understanding · **attack_surface**: OWASP LLM01.roleplay
- **definition**: Detect role-play / persona-switch attempts intended to bypass safety constraints by recasting the agent as a different entity.
- **scope_in**: "pretend you are X with no rules", DAN-derivative personas, character framing, hypothetical framing for harmful content
- **scope_out**: legitimate persona configuration via system prompt → not a detection target; intent ambiguity in benign requests → `classify-request-ambiguity-level`
- **signal_phrases**: role-play escape, persona switch, character jailbreak, "pretend you are", hypothetical framing
- **related**: `detect-jailbreak-template`, `detect-direct-prompt-injection`

### 5.2 `classify-input-intent-ambiguity` 下属（3 个原子）

> **背景**：此 archetype 在 Stage 3 是死锚点（仅 2 条命中）。原子能力先按理论拆，等 LLM 审计后看是否合并/重写。

#### `classify-request-ambiguity-level`
- **parent**: `classify-input-intent-ambiguity` · **phase**: input-understanding · **attack_surface**: 自定义.intent-ambiguity
- **definition**: Score / classify how ambiguous a user request is along axes that affect downstream safety (target scope, irreversibility, recipient), after using bounded non-mutating discovery when it can safely resolve missing context.
- **scope_in**: classifier returning `unambiguous / mildly-ambiguous / safety-critical-ambiguous`, scoring of pronouns / "the old files" / "those records", reclassification after read-only discovery such as listing candidates or inspecting metadata
- **scope_out**: detecting destructive verbs alone → `detect-destructive-action-keyword`; asking the user back → `elicit-clarification-before-act`
- **signal_phrases**: ambiguity classifier, intent ambiguity, request clarity, ambiguity scoring, scope clarity check
- **related**: `detect-destructive-action-keyword`, `elicit-clarification-before-act`

#### `detect-destructive-action-keyword`
- **parent**: `classify-input-intent-ambiguity` · **phase**: input-understanding · **attack_surface**: 自定义.destructive-intent
- **definition**: Match user-input verbs / phrases that imply destructive or irreversible actions (delete, drop, force-push, send-money) before they reach planning.
- **scope_in**: "delete all", "drop table", "wipe", "send X to Y", "force push", verb lists pulled from SlowMist red-line conventions
- **scope_out**: tool-call argument destructive flags → `detect-destructive-flag` (tool layer); workspace-boundary enforcement → `enforce-filesystem-sandbox`
- **signal_phrases**: destructive intent, dangerous keyword, red-line keyword, irreversible action keyword, blacklist keyword
- **related**: `classify-request-ambiguity-level`, `detect-destructive-flag`, `request-human-confirmation`

#### `elicit-clarification-before-act`
- **parent**: `classify-input-intent-ambiguity` · **phase**: input-understanding · **attack_surface**: 自定义.clarification-gating
- **definition**: Generate a clarification question and pause before the first side effect when material safety ambiguity remains after any available bounded, non-mutating discovery.
- **scope_in**: clarification-prompt generation, "did you mean X or Y" gating, hold-and-ask flow at the mutation boundary when multiple materially different targets remain
- **scope_out**: safe read-only discovery that can reduce ambiguity → perform it first; human approval for high-risk actions → `request-human-confirmation`; pure scoring → `classify-request-ambiguity-level`
- **signal_phrases**: clarification, ask user back, disambiguate, gating clarification, "did you mean"
- **related**: `classify-request-ambiguity-level`, `request-human-confirmation`

### 5.3 `scan-input-for-pii-and-secrets` 下属（5 个原子）

#### `detect-pii-in-input`
- **parent**: `scan-input-for-pii-and-secrets` · **phase**: input-understanding · **attack_surface**: OWASP LLM02 · GDPR
- **definition**: Detect PII (names, addresses, emails, phone numbers, SSN/government IDs, biometrics) in user-supplied input before it gets logged / forwarded to external tools.
- **scope_in**: regex / NER PII detection on user message, GDPR / HIPAA category classification, government ID format validation, medical record numbers (MRN / NHS), crypto-wallet address (BTC / ETH / etc.)
- **scope_out**: PII in agent **output** → `redact-output-pii`; payment card specifically → `detect-payment-card-data`; auth tokens → `detect-credential-in-input`
- **signal_phrases**: PII detection, GDPR detector, NER, sensitive entity, personal data scanner, HIPAA detector
- **related**: `detect-payment-card-data`, `detect-credential-in-input`, `redact-output-pii`, `redact-input-pii`

#### `detect-payment-card-data`
- **parent**: `scan-input-for-pii-and-secrets` · **phase**: input-understanding · **attack_surface**: PCI DSS
- **definition**: Detect payment card numbers (PAN, CVV, expiry, magstripe data) using Luhn validation + format heuristics.
- **scope_in**: Luhn-validated card numbers, magstripe parses, BIN range matching, PAN truncation enforcement, IBAN / SWIFT BIC
- **scope_out**: PII generally → `detect-pii-in-input`; outbound output redaction → `redact-output-pii`
- **signal_phrases**: PAN, payment card, PCI DSS, Luhn, credit card detector
- **related**: `detect-pii-in-input`, `redact-input-pii`

#### `detect-credential-in-input`
- **parent**: `scan-input-for-pii-and-secrets` · **phase**: input-understanding · **attack_surface**: OWASP LLM02.credential
- **definition**: Detect API keys, OAuth tokens, JWT, session cookies, cloud access keys, database connection strings in user input or pasted content.
- **scope_in**: AWS/GCP/Azure key patterns, OpenAI/Anthropic key prefixes, JWT structure, generic high-entropy string detection, .env content paste
- **scope_out**: private signing keys → `detect-private-key-input`; secrets in code repositories → `detect-hardcoded-secret-in-code`; secrets in tool **arguments** → `detect-secret-in-args`
- **signal_phrases**: API key detection, secret scanner, token detection, credential leakage scanner, .env detector
- **related**: `detect-private-key-input`, `detect-hardcoded-secret-in-code`, `detect-secret-in-args`

#### `detect-private-key-input`
- **parent**: `scan-input-for-pii-and-secrets` · **phase**: input-understanding · **attack_surface**: OWASP LLM02.crypto
- **definition**: Detect private cryptographic keys (RSA / EC / SSH / PGP / wallet seed phrases / mnemonic) in input.
- **scope_in**: PEM-encoded private key, OpenSSH key block, BIP39 seed phrases, PGP private key, X.509 private key
- **scope_out**: API keys/tokens (not asymmetric crypto) → `detect-credential-in-input`; key inside source code → `detect-hardcoded-secret-in-code`
- **signal_phrases**: private key detector, PEM private key, BIP39 seed, mnemonic phrase, PGP key block
- **related**: `detect-credential-in-input`, `detect-hardcoded-secret-in-code`

#### `redact-input-pii`
- **parent**: `scan-input-for-pii-and-secrets` · **phase**: input-understanding · **attack_surface**: OWASP LLM02.preprocess
- **definition**: Replace detected PII / secrets / credentials in user input with redaction tokens before passing to downstream prompts or logs.
- **scope_in**: format-preserving tokenization, "[REDACTED-EMAIL]"-style placeholder, hashed pseudonyms, full erasure
- **scope_out**: redaction of agent's **output** → `redact-output-pii` / `redact-output-secret`; detection only (no replacement) → the corresponding `detect-*` atoms
- **signal_phrases**: input redaction, tokenization, PII replacement, redaction placeholder, pre-redact
- **related**: `detect-pii-in-input`, `detect-credential-in-input`, `redact-output-pii`

### 5.5 `enforce-policy-as-code` 下属（2 个原子）

#### `evaluate-opa-rego-rule`
- **parent**: `enforce-policy-as-code` · **phase**: planning · **attack_surface**: policy-as-code
- **definition**: Evaluate a planned action against an OPA / Rego / Cedar / similar policy engine and return allow/deny + matching rule ids.
- **scope_in**: OPA evaluation, Rego rule packs, Cedar policies, AWS IAM-style policy decisions
- **scope_out**: RBAC-only role checks → `check-rbac-role`; tool-permission scope (not policy engine) → `verify-allowed-tool-list`
- **signal_phrases**: OPA, Rego, Cedar, policy engine, policy-as-code, policy decision point
- **related**: `check-rbac-role`, `evaluate-content-moderation-rule`, `evaluate-regulatory-compliance-rule`

#### `evaluate-content-moderation-rule`
- **parent**: `enforce-policy-as-code` · **phase**: planning · **attack_surface**: content-policy · OWASP LLM09
- **definition**: Apply explicit content moderation rules (toxicity / hate speech / NSFW / disinformation flags) as a planning gate, not just on output.
- **scope_in**: classifier-as-policy, content moderation API gate, planning-time content rejection
- **scope_out**: post-generation output review → `enforce-disallowed-content-rule`; agent-output safety more generally → archetype `enforce-output-content-policy`
- **signal_phrases**: content policy, moderation rule, toxicity gate, NSFW gate
- **related**: `evaluate-regulatory-compliance-rule`, `enforce-disallowed-content-rule`

### 5.6 `check-tool-permission-scope` 下属（4 个原子）

#### `verify-allowed-tool-list`
- **parent**: `check-tool-permission-scope` · **phase**: planning · **attack_surface**: OWASP LLM06.least-privilege
- **definition**: Reject tool invocations not in the explicit allowlist for the agent / task / session.
- **scope_in**: allowed-tools enum check, tool-allowlist policy, per-task tool denylist, ephemeral allowlist by session
- **scope_out**: resource-level scope (e.g., which file path) → `verify-resource-namespace-scope`; capability tokens → `verify-capability-token`
- **signal_phrases**: tool allowlist, allowed tools, tool whitelist, tool denylist, tool gating
- **related**: `verify-resource-namespace-scope`, `verify-capability-token`, `check-rbac-role`

#### `verify-resource-namespace-scope`
- **parent**: `check-tool-permission-scope` · **phase**: planning · **attack_surface**: OWASP LLM06.resource-scope
- **definition**: Verify the resource (file path, DB schema, repo, account, S3 bucket, project ID) targeted by a tool call is within the namespace authorized for the current task.
- **scope_in**: path-namespace check, repo-allowlist check, AWS account/project allowlist, DB schema allowlist
- **scope_out**: filesystem sandbox enforcement (chroot-style) → `enforce-filesystem-sandbox`; tool allowlist → `verify-allowed-tool-list`
- **signal_phrases**: resource scope, namespace check, path allowlist, repo allowlist, project scope
- **related**: `verify-allowed-tool-list`, `enforce-filesystem-sandbox`, `enforce-network-egress-allowlist`

#### `verify-capability-token`
- **parent**: `check-tool-permission-scope` · **phase**: planning · **attack_surface**: capability-security
- **definition**: Validate a presented capability token (macaroon, biscuit, signed grant, sealed object reference) and bind it to the planned operation's scope.
- **scope_in**: macaroon verification, biscuit verification, capability URL validation, signed grant binding
- **scope_out**: API key auth (bearer-style) → `verify-allowed-tool-list` if it just gates tool use; RBAC role check → `check-rbac-role`
- **signal_phrases**: capability token, macaroon, biscuit, capability-based security, sealed reference
- **related**: `verify-allowed-tool-list`, `check-rbac-role`

#### `check-rbac-role`
- **parent**: `check-tool-permission-scope` · **phase**: planning · **attack_surface**: access-control · OWASP LLM06
- **definition**: Verify the agent / current task / current user holds an RBAC or ABAC role authorized for the planned action.
- **scope_in**: role lookup, role-action matrix, attribute-based check, RBAC enforcement gate
- **scope_out**: capability tokens (not role-based) → `verify-capability-token`; tool allowlist → `verify-allowed-tool-list`; full policy engine evaluation (OPA / Rego, including RBAC-as-policy) → `evaluate-opa-rego-rule`
- **signal_phrases**: RBAC, ABAC, role check, role-based access, authorization gate
- **related**: `verify-allowed-tool-list`, `verify-capability-token`, `verify-resource-namespace-scope`, `evaluate-opa-rego-rule`

### 5.7 `detect-task-overreach` 下属（4 个原子）

#### `compare-plan-vs-stated-intent`
- **parent**: `detect-task-overreach` · **phase**: planning · **attack_surface**: OWASP LLM06.scope-creep
- **definition**: Compare the agent's generated plan against the user's elicited intent and return a similarity / divergence score.
- **scope_in**: plan-intent embedding similarity, plan-step justification labeling, scope-divergence scoring
- **scope_out**: just listing side effects → `enumerate-task-side-effects`; flagging specific steps → `flag-unjustified-side-effect`
- **signal_phrases**: plan vs intent, intent alignment, scope divergence, plan validation against intent
- **related**: `enumerate-task-side-effects`, `flag-unjustified-side-effect`, `detect-autonomy-budget-exceeded`

#### `flag-unjustified-side-effect`
- **parent**: `detect-task-overreach` · **phase**: planning · **attack_surface**: OWASP LLM06
- **definition**: Identify individual planned steps whose side effects (writes / sends / spends) are not justified by the user-stated goal.
- **scope_in**: per-step justification check, "why is this step needed" annotation enforcement, unjustified-write detection
- **scope_out**: blanket plan/intent comparison → `compare-plan-vs-stated-intent`; budget-based limits → `detect-autonomy-budget-exceeded`
- **signal_phrases**: unjustified step, unnecessary side effect, scope creep flag, step-level justification
- **related**: `compare-plan-vs-stated-intent`, `enumerate-task-side-effects`

#### `detect-autonomy-budget-exceeded`
- **parent**: `detect-task-overreach` · **phase**: planning · **attack_surface**: OWASP LLM06.autonomy-budget
- **definition**: Detect when the cumulative scope (number of writes, money spent, external messages, irreversible actions) exceeds the autonomy budget set for this task.
- **scope_in**: per-task action quota, per-session write quota, per-session spend cap, action-counter gate
- **scope_out**: per-tool rate limit (latency/cost) → `enforce-tool-call-rate-limit`; cost cap on $ → `enforce-cost-cap-per-task`
- **signal_phrases**: autonomy budget, action budget, scope budget, autonomy quota, irreversible action quota
- **related**: `enforce-tool-call-rate-limit`, `enforce-cost-cap-per-task`, `request-human-confirmation`

#### `enumerate-task-side-effects`
- **parent**: `detect-task-overreach` · **phase**: planning · **attack_surface**: 自定义.side-effect-graph
- **definition**: Enumerate all observable side effects of a planned multi-step task (writes, network calls, money moves, message sends, state mutations) before any action is taken.
- **scope_in**: side-effect graph extraction from plan, write-set / read-set analysis, money-flow extraction, dry-run side-effect listing
- **scope_out**: comparing those side effects against user intent → `compare-plan-vs-stated-intent`; flagging unjustified ones → `flag-unjustified-side-effect`; per-call budget gate → `detect-autonomy-budget-exceeded`
- **signal_phrases**: side-effect graph, write-set extraction, dry-run plan, plan side-effect inventory
- **related**: `compare-plan-vs-stated-intent`, `flag-unjustified-side-effect`, `detect-autonomy-budget-exceeded`

### 5.8 `validate-tool-argument-safety` 下属（8 个原子）

#### `detect-shell-command-injection`
- **parent**: `validate-tool-argument-safety` · **phase**: tool-invocation · **attack_surface**: cmd-injection
- **definition**: Detect shell metacharacters / argument escapes / unsafe quoting that introduce an executable payload in commands the agent is about to run via shell, exec, or subprocess.
- **scope_in**: dangerous command substitution such as `$(curl ...)`, pipe-to-shell execution, `/dev/tcp`, untrusted argument interpolation in bash/sh, `subprocess.run(shell=True)`, makefile targets, or container `cmd`
- **scope_out**: SQL queries → `detect-sql-injection`; HTTP request body content → `detect-unsafe-url` (if URL) or `enforce-output-content-policy`; OS-level sandbox → `enforce-process-sandbox`
- **signal_phrases**: shell injection, command injection, shell metacharacter, $(), backtick, exec injection, popen safety
- **related**: `detect-sql-injection`, `detect-path-traversal`, `detect-destructive-flag`, `enforce-process-sandbox`

#### `detect-sql-injection`
- **parent**: `validate-tool-argument-safety` · **phase**: tool-invocation · **attack_surface**: OWASP A03 (Injection) / SQLi
- **definition**: Detect SQL injection patterns / unparameterized query construction in DB calls the agent is about to execute.
- **scope_in**: string-concat SQL, missing parameterization, ORM raw query inspection, NoSQL operator injection
- **scope_out**: shell calls → `detect-shell-command-injection`; SAST on stored code → `detect-injection-flaw`
- **signal_phrases**: SQL injection, NoSQL injection, parameterized query enforcement, query sanitization
- **related**: `detect-shell-command-injection`, `detect-injection-flaw`, `validate-tool-argument-schema`

#### `detect-path-traversal`
- **parent**: `validate-tool-argument-safety` · **phase**: tool-invocation · **attack_surface**: path-traversal
- **definition**: Detect `..`, absolute paths escaping workspace, symlink traversal, encoded traversal sequences in file path arguments.
- **scope_in**: `../` detection, absolute-path-outside-workspace check, encoded path (`%2e%2e/`) detection, symlink-target follow
- **scope_out**: enforcing the workspace at OS level → `enforce-filesystem-sandbox`; workspace boundary archetype itself → use `enforce-filesystem-sandbox`
- **signal_phrases**: path traversal, ../, directory traversal, symlink escape, path canonicalization
- **related**: `enforce-filesystem-sandbox`, `verify-resource-namespace-scope`

#### `detect-destructive-flag`
- **parent**: `validate-tool-argument-safety` · **phase**: tool-invocation · **attack_surface**: destructive-args
- **definition**: Detect destructive flags / parameters in tool calls (`rm -rf`, `--force`, `DROP TABLE`, `git push --force`, `chmod 777`, `kubectl delete --all`) and destructive resource replacement such as overwriting an existing database file.
- **scope_in**: command-flag denylist, destructive-arg pattern match, irreversible-flag detection, force-flag check, `mv`/`cp` replacement of a `.db`/`.sqlite` destination
- **scope_out**: input keyword detection (before tool layer) → `detect-destructive-action-keyword`; user-intent ambiguity → `classify-request-ambiguity-level`
- **signal_phrases**: destructive flag, force flag, --force, rm -rf, kubectl delete, drop table, database replacement, destructive-arg detector
- **related**: `detect-destructive-action-keyword`, `detect-shell-command-injection`, `request-human-confirmation`

#### `detect-unsafe-url`
- **parent**: `validate-tool-argument-safety` · **phase**: tool-invocation · **attack_surface**: SSRF · phishing
- **definition**: Detect URLs targeting metadata endpoints (169.254.169.254, link-local), private networks, malicious hosts, or with embedded credentials.
- **scope_in**: SSRF target detection, internal-IP allowlist enforcement, malicious-host blocklist, suspicious-URL signature
- **scope_out**: network egress allowlist enforcement → `enforce-network-egress-allowlist`; MCP-specific SSRF → `detect-mcp-ssrf`
- **signal_phrases**: SSRF, unsafe URL, metadata endpoint, link-local IP, malicious host, URL allowlist
- **related**: `enforce-network-egress-allowlist`, `detect-mcp-ssrf`

#### `detect-secret-in-args`
- **parent**: `validate-tool-argument-safety` · **phase**: tool-invocation · **attack_surface**: OWASP LLM02 (output-side leak via tool args)
- **definition**: Detect API keys / tokens / passwords being passed in tool call arguments where they shouldn't be (URL query params, log message fields, bug-report bodies).
- **scope_in**: secret in HTTP query string, secret in webhook body, secret in third-party-API arg field, secret in log line
- **scope_out**: secret in user input → `detect-credential-in-input`; secret in code → `detect-hardcoded-secret-in-code`; secret in agent output to user → `redact-output-secret`
- **signal_phrases**: secret in tool call, credential leakage to tool, secret in URL, secret in argument, leaking key to webhook
- **related**: `detect-credential-in-input`, `redact-output-secret`, `detect-data-exfiltration`

#### `detect-overbroad-resource-selector`
- **parent**: `validate-tool-argument-safety` · **phase**: tool-invocation · **attack_surface**: OWASP LLM06.overbroad-scope
- **definition**: Detect wildcards / bulk selectors / "all" semantics in tool args that affect more resources than the task requires (`*`, `all`, `--recursive`, no `WHERE` clause, repo `*`, label `*`).
- **scope_in**: wildcard arg detection, missing WHERE/scope filter, recursive-flag without justification, "all-instances" selector
- **scope_out**: resource-namespace scope (which is allowed at all) → `verify-resource-namespace-scope`; rate limit → `enforce-tool-call-rate-limit`
- **signal_phrases**: overbroad selector, wildcard arg, missing where clause, --recursive risk, all-instances flag
- **related**: `verify-resource-namespace-scope`, `detect-destructive-flag`

#### `validate-tool-argument-schema`
- **parent**: `validate-tool-argument-safety` · **phase**: tool-invocation · **attack_surface**: schema-violation
- **definition**: Validate tool-call arguments against the tool's declared JSON Schema / OpenAPI / function signature, rejecting type mismatches / missing required / extra fields.
- **scope_in**: JSON Schema validation, OpenAPI request validation, MCP tool-call schema check, type coercion safety check
- **scope_out**: semantic safety of values (injection, secrets) → other `validate-tool-argument-safety/*`; tool-trust → `validate-agent-tool-trust`
- **signal_phrases**: argument schema validation, JSON Schema validator, tool-call schema check, OpenAPI validator
- **related**: `detect-shell-command-injection`, `detect-overbroad-resource-selector`

### 5.9 `constrain-workspace-boundary` 下属（6 个原子）

#### `enforce-filesystem-sandbox`
- **parent**: `constrain-workspace-boundary` · **phase**: tool-invocation · **attack_surface**: sandbox-fs
- **definition**: Restrict the agent's file read/write operations to a declared workspace via OS-level mechanisms (chroot, bind-mount, container FS, capability-based FS).
- **scope_in**: chroot, Docker volume mount, namespace-isolated FS, AppArmor/SELinux FS profile, jailbird FS
- **scope_out**: `..` detection in args → `detect-path-traversal`; resource-namespace policy decision → `verify-resource-namespace-scope`
- **signal_phrases**: filesystem sandbox, chroot, FS jail, container FS isolation, AppArmor profile, mount namespace
- **related**: `detect-path-traversal`, `enforce-process-sandbox`, `verify-resource-namespace-scope`

#### `enforce-network-egress-allowlist`
- **parent**: `constrain-workspace-boundary` · **phase**: tool-invocation · **attack_surface**: egress-firewall
- **definition**: Restrict outbound network calls to an allowlist of hostnames / IP ranges / ports at the network or proxy layer.
- **scope_in**: egress firewall rule, HTTP proxy allowlist, DNS allowlist, container network policy
- **scope_out**: arg-level URL safety check → `detect-unsafe-url`; data exfiltration content detection → `detect-data-exfiltration`
- **signal_phrases**: egress firewall, network allowlist, outbound allowlist, HTTP proxy filter, DNS sinkhole
- **related**: `detect-unsafe-url`, `detect-data-exfiltration`, `enforce-process-sandbox`

#### `enforce-process-sandbox`
- **parent**: `constrain-workspace-boundary` · **phase**: tool-invocation · **attack_surface**: sandbox-proc
- **definition**: Restrict the agent's process / subprocess capabilities (seccomp, capabilities drop, gVisor, Firecracker, container with no-new-privileges).
- **scope_in**: seccomp profile, container with `--security-opt no-new-privileges`, gVisor, Firecracker, capability drop, syscall allowlist
- **scope_out**: filesystem-only isolation → `enforce-filesystem-sandbox`; network-only isolation → `enforce-network-egress-allowlist`
- **signal_phrases**: seccomp, syscall filter, gVisor, Firecracker, no-new-privileges, capability drop, process sandbox
- **related**: `enforce-filesystem-sandbox`, `enforce-network-egress-allowlist`, `detect-sandbox-escape-attempt`

#### `detect-sandbox-escape-attempt`
- **parent**: `constrain-workspace-boundary` · **phase**: tool-invocation · **attack_surface**: sandbox-escape
- **definition**: Detect runtime indicators that the agent or its tools are trying to escape the sandbox (mount manipulation, ptrace, kernel-module load, escape-via-shared-volume).
- **scope_in**: ptrace / module-load detection, mount-syscall anomaly, container-breakout signature, suspicious socket-to-host
- **scope_out**: pre-execution permission check → `verify-allowed-tool-list`; arg-level destructive flag → `detect-destructive-flag`
- **signal_phrases**: sandbox escape, container breakout, ptrace abuse, module load, mount escape, escape detector
- **related**: `enforce-process-sandbox`, `enforce-filesystem-sandbox`, `incident-response-handler` (parent)

#### `enforce-subagent-scope-isolation`
- **parent**: `constrain-workspace-boundary` · **phase**: tool-invocation · **attack_surface**: multi-agent privilege escalation
- **definition**: Isolate a subagent's workspace, capability scope, and resource access so it cannot escalate beyond what the parent delegated to it.
- **scope_in**: per-subagent FS namespace, scoped-down capability token issuance, parent-permission strict subset enforcement, separate execution sandbox
- **scope_out**: filesystem sandbox in general → `enforce-filesystem-sandbox`; race-condition / shared-state safety → `enforce-swarm-race-condition-safety`
- **signal_phrases**: subagent isolation, delegated scope, child-agent sandbox, scope-reduction enforcement
- **related**: `enforce-filesystem-sandbox`, `enforce-process-sandbox`, `verify-delegation-chain`

#### `enforce-swarm-race-condition-safety`
- **parent**: `constrain-workspace-boundary` · **phase**: tool-invocation · **attack_surface**: multi-agent shared state
- **definition**: Prevent race conditions and state-corruption in multi-agent shared-blackboard or shared-workspace environments via locking, transactional updates, or CRDT-based coordination.
- **scope_in**: shared-blackboard mutex, CRDT-based merge, optimistic-concurrency check, multi-agent lock acquisition + timeout
- **scope_out**: per-subagent isolation → `enforce-subagent-scope-isolation`; rate limit on shared resource → `enforce-tool-call-rate-limit`
- **signal_phrases**: swarm race condition, multi-agent lock, shared blackboard safety, CRDT coordination
- **related**: `enforce-subagent-scope-isolation`, `enforce-tool-call-rate-limit`

### 5.10 `validate-agent-tool-trust` 下属（11 个原子）

#### `check-tool-typosquat-name`
- **parent**: `validate-agent-tool-trust` · **phase**: tool-invocation · **attack_surface**: typosquatting (UseAI-pro T1)
- **definition**: Detect tool / skill / package names that look-alike a known popular package (homoglyph, near-edit-distance, brandjack).
- **scope_in**: levenshtein-distance to known-good list, homoglyph detection (l→1, o→0, Cyrillic look-alikes), brandjack name-similarity check
- **scope_out**: package CVE check → `check-package-cve`; install hook audit → `audit-install-hook`
- **signal_phrases**: typosquat, typosquatting, name similarity, homoglyph, brandjack, near-clone name
- **related**: `verify-tool-publisher-identity`, `check-package-typosquat`

#### `verify-skill-signature`
- **parent**: `validate-agent-tool-trust` · **phase**: tool-invocation · **attack_surface**: skill-supply-chain
- **definition**: Verify cryptographic signature / SHA256 checksum / sigstore attestation of a skill / tool / MCP server before installation or invocation.
- **scope_in**: GPG signature check, sigstore / cosign verification, SHA256 manifest check, signed-feed verification (ClawSec-style), model-artifact signature (weights / configs / containers)
- **scope_out**: package-registry signature → `check-package-cve` (covers CVE feed integrity); signature on agent output → `enable-tamper-evident-storage`
- **signal_phrases**: skill signature, signed skill, sigstore, cosign, checksum verification, signed feed
- **related**: `verify-tool-publisher-identity`, `check-package-cve`
- **requires_network**: false (bundled pubkey; optional online revocation via `SKILL_REVOCATION_URL`)
- **fail_policy**: fail-closed

#### `verify-tool-publisher-identity`
- **parent**: `validate-agent-tool-trust` · **phase**: tool-invocation · **attack_surface**: provenance
- **definition**: Verify the publisher / maintainer / org of a tool / skill against a curated allowlist or reputation source.
- **scope_in**: org-allowlist enforcement, GitHub-org provenance check, npm-publisher reputation, reputation-score lookup
- **scope_out**: signature verification → `verify-skill-signature`; install-hook content audit → `audit-install-hook`
- **signal_phrases**: publisher allowlist, maintainer reputation, org provenance, publisher identity, reputation score
- **related**: `verify-skill-signature`, `check-tool-typosquat-name`
- **requires_network**: false (local publisher allowlist by default; optional online reputation via user-configured endpoint)
- **fail_policy**: fail-closed

#### `detect-hidden-instruction-in-tool-description`
- **parent**: `validate-agent-tool-trust` · **phase**: tool-invocation · **attack_surface**: tool-poisoning · skill-poisoning
- **definition**: Scan a tool / skill description / SKILL.md / MCP `tool.description` for instructions targeting the LLM (rather than the human reader).
- **scope_in**: hidden "always do X"-style instruction in tool description, invisible-character payloads, "instructions for assistant" sections, white-on-white text
- **scope_out**: prompt injection in fetched runtime content → `detect-indirect-prompt-injection`; YARA-style binary payload → `detect-malicious-payload-in-tool-output`
- **signal_phrases**: tool poisoning, skill poisoning, hidden instruction, hidden prompt in description, instruction-in-description scanner
- **related**: `detect-indirect-prompt-injection`, `detect-tool-loader-exploit`

#### `detect-tool-loader-exploit`
- **parent**: `validate-agent-tool-trust` · **phase**: tool-invocation · **attack_surface**: skill-loader-exploit (UseAI-pro T6)
- **definition**: Detect skills / tools that exploit the host's loader behavior (auto-execute on install, sideload via `npx` post-install, hijack global config).
- **scope_in**: install-time auto-exec detection, package post-install hook audit, agent-startup-config hijack
- **scope_out**: install-script content malicious-pattern → `audit-install-hook` / `detect-malicious-postinstall-script`; permission overrequest → `detect-skill-permission-overrequest`
- **signal_phrases**: skill loader exploit, install-time exec, post-install hijack, loader abuse, autoload exploit
- **related**: `audit-install-hook`, `detect-malicious-postinstall-script`, `detect-skill-permission-overrequest`

#### `detect-skill-permission-overrequest`
- **parent**: `validate-agent-tool-trust` · **phase**: tool-invocation · **attack_surface**: OWASP LLM06.overprivilege (UseAI-pro T11)
- **definition**: Detect skills / tools requesting a permission combination broader than their stated functionality justifies (e.g., a markdown formatter requesting network + shell).
- **scope_in**: permission-vs-functionality mismatch, "shell + network" combo flag, broad-FS-write request, dangerous-perm combo detection
- **scope_out**: at-runtime permission scope → `check-tool-permission-scope` archetype; least-priv enforcement → `verify-allowed-tool-list`
- **signal_phrases**: over-privilege, over-permission, perm combo flag, dangerous permissions, permission audit
- **related**: `verify-allowed-tool-list`, `detect-tool-loader-exploit`

#### `detect-mcp-confused-deputy`
- **parent**: `validate-agent-tool-trust` · **phase**: tool-invocation · **attack_surface**: MCP-spec.confused-deputy
- **definition**: Detect / prevent the MCP "confused deputy" pattern where a server uses its higher privileges on behalf of a less-privileged caller without scope check.
- **scope_in**: MCP server caller-vs-resource scope check, MCP token re-binding, principal propagation enforcement
- **scope_out**: token passthrough specifically → `detect-mcp-token-passthrough`; SSRF specifically → `detect-mcp-ssrf`
- **signal_phrases**: confused deputy, MCP confused deputy, deputy attack, principal propagation, MCP scope check
- **related**: `detect-mcp-token-passthrough`, `detect-mcp-session-hijacking`, `detect-mcp-ssrf`

#### `detect-mcp-token-passthrough`
- **parent**: `validate-agent-tool-trust` · **phase**: tool-invocation · **attack_surface**: MCP-spec.token-passthrough
- **definition**: Detect MCP servers that pass an upstream token to downstream services without rebinding scope or validating audience.
- **scope_in**: token forwarded to backend without scope reduction, audience claim not validated, OAuth token reuse beyond scope
- **scope_out**: confused-deputy pattern (broader) → `detect-mcp-confused-deputy`; non-MCP credential leakage → `detect-secret-in-args`
- **signal_phrases**: token passthrough, MCP token leak, audience validation, OAuth scope misuse, token rebinding
- **related**: `detect-mcp-confused-deputy`, `detect-secret-in-args`

#### `detect-mcp-session-hijacking`
- **parent**: `validate-agent-tool-trust` · **phase**: tool-invocation · **attack_surface**: MCP-spec.session-hijack
- **definition**: Detect MCP session hijacking vectors — session ID prediction / fixation, prompt injection across sessions, impersonation via stolen session IDs.
- **scope_in**: predictable session ID detection, session-fixation check, cross-session prompt-injection vector, session-impersonation indicator
- **scope_out**: prompt injection in general → `detect-prompt-injection` archetype; SSRF → `detect-mcp-ssrf`
- **signal_phrases**: MCP session hijack, session fixation, session prediction, MCP impersonation
- **related**: `detect-mcp-confused-deputy`, `detect-indirect-prompt-injection`

#### `detect-mcp-ssrf`
- **parent**: `validate-agent-tool-trust` · **phase**: tool-invocation · **attack_surface**: MCP-spec.SSRF
- **definition**: Detect SSRF vectors specific to MCP servers: server fetching attacker-controlled URLs, internal-network enumeration via MCP resource fetch.
- **scope_in**: MCP `resource.fetch` with attacker URL, MCP server internal-IP fetch, link-local fetch from MCP context
- **scope_out**: general unsafe URL in any tool arg → `detect-unsafe-url`; egress firewall enforcement → `enforce-network-egress-allowlist`
- **signal_phrases**: MCP SSRF, MCP server SSRF, server-side request forgery in MCP, MCP resource fetch SSRF
- **related**: `detect-unsafe-url`, `enforce-network-egress-allowlist`

#### `detect-delayed-payload-pattern`
- **parent**: `validate-agent-tool-trust` · **phase**: input-understanding · **attack_surface**: time-bomb / dormant-payload
- **definition**: Detect patterns in skill code or agent configuration that indicate delayed activation of malicious behavior — triggers based on usage count, date, environment, or specific user.
- **scope_in**: usage-count counter check, time-bomb date comparison, environment-specific branch (prod-only logic), targeted-user trigger
- **scope_out**: install-time auto-exec → `detect-tool-loader-exploit`; hidden instructions in description → `detect-hidden-instruction-in-tool-description`
- **signal_phrases**: time bomb, dormant payload, delayed activation, conditional malware, environment trigger
- **related**: `detect-tool-loader-exploit`, `detect-hidden-instruction-in-tool-description`, `match-yara-rule`

### 5.11 `detect-supply-chain-risk` 下属（8 个原子）

#### `check-package-typosquat`
- **parent**: `detect-supply-chain-risk` · **phase**: tool-invocation · **attack_surface**: OWASP LLM03.typosquat
- **definition**: Detect typosquat / brandjack package names in dependency manifests (npm / pip / cargo / go.mod) before install.
- **scope_in**: npm/pip/cargo/go.mod dependency name fuzzy-match to top-N popular packages, brandjack near-clone name detection
- **scope_out**: tool-name typosquat (not a package) → `check-tool-typosquat-name`; transitive dep audit → `check-dependency-confusion`
- **signal_phrases**: package typosquat, dependency typosquat, npm squatting, pip typosquat, name-similarity scanner
- **related**: `check-tool-typosquat-name`, `check-package-cve`, `check-dependency-confusion`
- **requires_network**: false (bundled top-N popular package name DB; refresh via `safety-orch refresh-db`)
- **fail_policy**: fail-closed

#### `check-package-cve`
- **parent**: `detect-supply-chain-risk` · **phase**: tool-invocation · **attack_surface**: OWASP LLM03.cve · CVE
- **definition**: Look up packages / versions against CVE / advisory feeds (NVD, GitHub Advisory, OSV, RustSec) and surface vulnerable matches.
- **scope_in**: NVD / OSV / GHSA lookup, version-range CVE match, advisory-feed integration, CVSS-score gating, container-image CVE scan (Trivy / Grype)
- **scope_out**: SAST on the package source → `run-sast-scan`; SBOM completeness → `check-sbom-completeness`
- **signal_phrases**: CVE check, vulnerability database lookup, NVD scanner, OSV lookup, advisory feed, CVSS gate
- **related**: `check-package-typosquat`, `check-sbom-completeness`, `run-sast-scan`
- **requires_network**: true (default endpoints: osv.dev `/v1/querybatch`, GHSA, NVD; supports offline `osv-export` snapshot fallback)
- **fail_policy**: fail-soft-block

#### `check-dependency-confusion`
- **parent**: `detect-supply-chain-risk` · **phase**: tool-invocation · **attack_surface**: dep-confusion
- **definition**: Detect dependency-confusion risk: an internal-package name being satisfiable from a public registry with higher version.
- **scope_in**: internal/public registry shadow check, scope-jacking detection, namespace-overshadow detection
- **scope_out**: typosquat (similar but distinct name) → `check-package-typosquat`; install-hook abuse → `audit-install-hook`
- **signal_phrases**: dependency confusion, registry shadowing, scope jacking, namespace shadow, internal-vs-public dep
- **related**: `check-package-typosquat`, `audit-install-hook`
- **requires_network**: false (local config: `INTERNAL_REGISTRY_HOSTS` env var lists private registries to cross-check)
- **fail_policy**: fail-closed

#### `audit-install-hook`
- **parent**: `detect-supply-chain-risk` · **phase**: tool-invocation · **attack_surface**: postinstall-hook · UseAI-pro T8
- **definition**: Audit npm `postinstall` / pip `setup.py` / cargo build scripts / Makefile install targets for malicious behavior before allowing install.
- **scope_in**: npm postinstall script content audit, pip setup.py exec inspection, cargo build script audit, install-script-source review, Docker image tag-pinning audit
- **scope_out**: detected malicious script content match → `detect-malicious-postinstall-script` (more specific); install-time loader exploit → `detect-tool-loader-exploit`
- **signal_phrases**: postinstall audit, install hook check, setup.py audit, install-script review, build-script audit
- **related**: `detect-malicious-postinstall-script`, `detect-tool-loader-exploit`

#### `check-package-recency-anomaly`
- **parent**: `detect-supply-chain-risk` · **phase**: tool-invocation · **attack_surface**: supply-chain.recency
- **definition**: Flag packages with anomalous publish patterns (very recent first publish, single-maintainer, sudden ownership change, version skip, abandoned).
- **scope_in**: first-publish < N days check, sole-maintainer flag, ownership-change detection, abandoned-package detection
- **scope_out**: known CVE → `check-package-cve`; typosquat → `check-package-typosquat`
- **signal_phrases**: package recency anomaly, ownership change, recently published, abandoned package, sole maintainer flag
- **related**: `check-package-typosquat`, `verify-tool-publisher-identity`
- **requires_network**: true (registry.npmjs.org / pypi.org / crates.io package metadata endpoints; ETag-cached)
- **fail_policy**: fail-open-warn

#### `detect-malicious-postinstall-script`
- **parent**: `detect-supply-chain-risk` · **phase**: tool-invocation · **attack_surface**: postinstall-malicious · UseAI-pro T8
- **definition**: Detect concrete malicious patterns inside postinstall scripts (cred exfil, reverse shell, crypto miner install, persistence write).
- **scope_in**: reverse-shell pattern, base64-decoded payload exec, env-var exfil, miner-binary download
- **scope_out**: just auditing the hook exists / runs → `audit-install-hook`; reverse-shell at runtime → covered separately by sandbox detection
- **signal_phrases**: malicious postinstall, reverse shell in install, install-time miner, install exfil, malicious build script
- **related**: `audit-install-hook`, `detect-tool-loader-exploit`

#### `detect-hallucinated-package`
- **parent**: `detect-supply-chain-risk` · **phase**: tool-invocation · **attack_surface**: slopsquatting / LLM-induced supply chain
- **definition**: Detect package names in generated code or import statements that do not exist in any known registry, preventing slopsquatting attacks where attackers pre-register hallucinated names.
- **scope_in**: registry-existence lookup (npm / PyPI / crates.io / Maven Central / Go modules), missing-package check on LLM-generated imports, slopsquatting susceptibility check
- **scope_out**: typosquatted real packages → `check-package-typosquat`; dependency confusion → `check-dependency-confusion`
- **signal_phrases**: hallucinated package, slopsquatting, non-existent dependency, LLM-suggested fake package, import-validation
- **related**: `check-package-typosquat`, `check-dependency-confusion`
- **requires_network**: true (npm / PyPI / crates.io / Maven Central / Go modules registry existence check)
- **fail_policy**: fail-open-warn

#### `audit-ci-workflow-security`
- **parent**: `detect-supply-chain-risk` · **phase**: tool-invocation · **attack_surface**: CI/CD supply chain
- **definition**: Audit CI/CD workflow files (GitHub Actions, GitLab CI, Jenkins, CircleCI) for supply-chain risks including action-version pinning, trigger safety (pull_request_target), secret exposure, and dependency injection points.
- **scope_in**: GitHub Actions YAML audit, action-version SHA pinning check, dangerous-trigger detection (`pull_request_target`), workflow-permissions audit
- **scope_out**: package CVE scanning → `check-package-cve`; install-hook content → `audit-install-hook`; SAST scan of source → `run-sast-scan`
- **signal_phrases**: CI pipeline audit, GitHub Actions audit, workflow security, action pinning, pull_request_target risk
- **related**: `check-package-cve`, `audit-install-hook`, `run-sast-scan`

### 5.12 `scan-code-for-vulnerabilities` 下属（5 个原子）

#### `run-sast-scan`
- **parent**: `scan-code-for-vulnerabilities` · **phase**: tool-invocation · **attack_surface**: SAST
- **definition**: Run a static analysis tool over agent-generated or user-supplied source and produce findings with location + severity.
- **scope_in**: semgrep / codeql / bandit / gosec runs, language-specific lint with security rules
- **scope_out**: secret in code → `detect-hardcoded-secret-in-code`; specific injection class → `detect-injection-flaw`; arg-level shell injection → `detect-shell-command-injection`
- **signal_phrases**: SAST, semgrep, codeql, bandit, gosec, security linter, static analysis
- **related**: `detect-hardcoded-secret-in-code`, `detect-injection-flaw`, `detect-insecure-cryptography`

#### `detect-hardcoded-secret-in-code`
- **parent**: `scan-code-for-vulnerabilities` · **phase**: tool-invocation · **attack_surface**: OWASP LLM02.code-secret
- **definition**: Detect secrets / API keys / private keys hardcoded in source files (vs in user input or tool args).
- **scope_in**: source-file secret scan, gitleaks / trufflehog-style scan, repo history secret scan
- **scope_out**: secret in user input → `detect-credential-in-input`; secret in tool args → `detect-secret-in-args`; secret in agent output → `redact-output-secret`
- **signal_phrases**: hardcoded secret, gitleaks, trufflehog, repo secret scan, source secret detection
- **related**: `detect-credential-in-input`, `detect-secret-in-args`, `redact-output-secret`

#### `detect-insecure-cryptography`
- **parent**: `scan-code-for-vulnerabilities` · **phase**: tool-invocation · **attack_surface**: weak-crypto
- **definition**: Detect use of weak / deprecated crypto primitives (MD5, SHA1, DES, RC4, ECB mode, weak RSA modulus, hardcoded IV).
- **scope_in**: weak-cipher detection, deprecated-mode use, weak-modulus check, hardcoded-IV / hardcoded-salt
- **scope_out**: misuse of TLS at runtime → covered by SAST or runtime check; private key leak in code → `detect-hardcoded-secret-in-code`
- **signal_phrases**: weak crypto, MD5 use, SHA1 use, DES, ECB mode, hardcoded IV, weak cipher
- **related**: `run-sast-scan`, `detect-hardcoded-secret-in-code`

#### `detect-unsafe-deserialization`
- **parent**: `scan-code-for-vulnerabilities` · **phase**: tool-invocation · **attack_surface**: deserialization
- **definition**: Detect use of unsafe deserialization (Python pickle, Java serializable, Ruby Marshal, PHP unserialize) on attacker-controlled data.
- **scope_in**: pickle.load on untrusted input, Java ObjectInputStream on untrusted input, YAML.unsafe_load, Erlang `:erlang.binary_to_term/1` on untrusted
- **scope_out**: schema validation → `validate-tool-argument-schema`; SAST find of any deserialization → `run-sast-scan` (deser is a sub-class)
- **signal_phrases**: unsafe deserialization, pickle injection, Java deserialization, yaml.unsafe_load
- **related**: `run-sast-scan`, `detect-injection-flaw`

#### `detect-injection-flaw`
- **parent**: `scan-code-for-vulnerabilities` · **phase**: tool-invocation · **attack_surface**: OWASP A03 (Injection)
- **definition**: Detect injection-class flaws (XSS, LDAP, XPath, template injection, SSTI) in source code beyond shell/SQL.
- **scope_in**: XSS sink detection, template injection (Jinja2, ERB), SSTI patterns, LDAP/XPath injection
- **scope_out**: SQL injection in tool arg → `detect-sql-injection`; shell injection in tool arg → `detect-shell-command-injection`
- **signal_phrases**: XSS, SSTI, template injection, LDAP injection, XPath injection, injection sink
- **related**: `run-sast-scan`, `detect-sql-injection`, `detect-shell-command-injection`

### 5.13 `detect-malicious-payload-in-tool-output` 下属（5 个原子）

#### `match-yara-rule`
- **parent**: `detect-malicious-payload-in-tool-output` · **phase**: tool-invocation · **attack_surface**: signature-match
- **definition**: Run YARA rules against tool-returned files / blobs / strings for malware family signatures.
- **scope_in**: YARA rule execution, YARA rule pack management, YARA-X scanning
- **scope_out**: hash-based IOC match → `check-malware-hash-ioc`; archive bomb → `detect-archive-bomb`
- **signal_phrases**: YARA, YARA rule, malware signature, YARA-X, signature scan
- **related**: `check-malware-hash-ioc`, `strip-active-html-script`

#### `check-malware-hash-ioc`
- **parent**: `detect-malicious-payload-in-tool-output` · **phase**: tool-invocation · **attack_surface**: IOC
- **definition**: Compare file hashes / URL / domain / IP IOCs from tool responses against threat-intel feeds (VirusTotal, AlienVault OTX, MISP).
- **scope_in**: VT hash lookup, OTX/MISP IOC match, domain blocklist match, IP reputation check, phishing-URL feed lookup (PhishTank / OpenPhish)
- **scope_out**: pattern-based content match → `match-yara-rule`; URL allowlist (egress, not IOC) → `enforce-network-egress-allowlist`
- **signal_phrases**: IOC match, hash IOC, threat intel feed, VirusTotal, MISP, OTX
- **related**: `match-yara-rule`, `enforce-network-egress-allowlist`
- **requires_network**: true (VirusTotal / AlienVault OTX / MISP; rate-limited public APIs)
- **requires_api_key**: VIRUSTOTAL_API_KEY (atom auto-disabled and Router status shows "待激活" if missing)
- **fail_policy**: fail-open-warn

#### `detect-archive-bomb`
- **parent**: `detect-malicious-payload-in-tool-output` · **phase**: tool-invocation · **attack_surface**: zip-bomb · DoS
- **definition**: Detect zip / tar / gzip archives with abnormal expansion ratio or recursive nesting that would exhaust resources on extraction.
- **scope_in**: zip-bomb expansion-ratio check, nested-archive depth limit, decompressed-size cap, quine-zip detection
- **scope_out**: rate-limit / quota exhaustion (general) → `enforce-rate-and-quota-limits` archetype; OOM-targeting payload → `detect-runaway-loop`
- **signal_phrases**: zip bomb, archive bomb, decompression bomb, gzip bomb, expansion ratio
- **related**: `detect-suspicious-mime-type`, `enforce-tool-call-rate-limit`

#### `detect-suspicious-mime-type`
- **parent**: `detect-malicious-payload-in-tool-output` · **phase**: tool-invocation · **attack_surface**: MIME-mismatch
- **definition**: Detect MIME-type / declared-extension mismatch (executable masquerading as image, polyglot files, MIME sniffing risk).
- **scope_in**: magic-byte vs declared-extension check, polyglot file detection, MIME-type whitelist enforcement
- **scope_out**: full malware scan → `match-yara-rule`; HTML active content → `strip-active-html-script`
- **signal_phrases**: MIME mismatch, MIME sniffing, polyglot file, magic byte check, file-type spoof
- **related**: `match-yara-rule`, `strip-active-html-script`

#### `strip-active-html-script`
- **parent**: `detect-malicious-payload-in-tool-output` · **phase**: tool-invocation · **attack_surface**: HTML-active-content
- **definition**: Strip / sanitize active content (script tags, on* event handlers, iframe, javascript: URLs) from HTML returned by tools before rendering or feeding to LLM.
- **scope_in**: DOMPurify-style sanitization, script-tag strip, event-handler-attr removal, javascript: URL strip
- **scope_out**: hidden text instructions to LLM → `detect-indirect-prompt-injection`; YARA on HTML → `match-yara-rule`
- **signal_phrases**: HTML sanitization, DOMPurify, script tag strip, on-attribute strip, active content strip
- **related**: `detect-indirect-prompt-injection`, `detect-suspicious-mime-type`

### 5.14 `enforce-rate-and-quota-limits` 下属（4 个原子）

#### `enforce-tool-call-rate-limit`
- **parent**: `enforce-rate-and-quota-limits` · **phase**: tool-invocation · **attack_surface**: DoS · OWASP LLM10
- **definition**: Throttle / cap tool invocations per second / per minute / per task to prevent runaway loops or DoS against external APIs.
- **scope_in**: per-tool rate limit, per-task call cap, sliding-window throttle, exponential backoff on 429
- **scope_out**: $ cost cap → `enforce-cost-cap-per-task`; token budget → `enforce-token-budget-cap`; runaway-loop detection → `detect-runaway-loop`
- **signal_phrases**: tool rate limit, call throttle, sliding-window limit, backoff on 429, per-tool quota
- **related**: `enforce-token-budget-cap`, `enforce-cost-cap-per-task`, `detect-runaway-loop`

#### `enforce-token-budget-cap`
- **parent**: `enforce-rate-and-quota-limits` · **phase**: tool-invocation · **attack_surface**: OWASP LLM10.token-budget
- **definition**: Cap LLM token usage per task / per session / per user to prevent budget exhaustion or "denial of wallet".
- **scope_in**: per-task token budget, prompt + completion accounting, budget-enforcement gate
- **scope_out**: $ cost (different unit) → `enforce-cost-cap-per-task`; tool API rate → `enforce-tool-call-rate-limit`
- **signal_phrases**: token budget, token cap, token quota, denial of wallet, token accounting
- **related**: `enforce-cost-cap-per-task`, `enforce-tool-call-rate-limit`

#### `enforce-cost-cap-per-task`
- **parent**: `enforce-rate-and-quota-limits` · **phase**: tool-invocation · **attack_surface**: cost-cap · denial-of-wallet
- **definition**: Cap monetary cost ($) per task / session / day across all paid tool/API calls.
- **scope_in**: per-task $ budget, per-day spend cap, paid-API spend tracker, cost-aware throttle, per-transaction spend cap (single-call max)
- **scope_out**: token-only budget → `enforce-token-budget-cap`; per-tool rate → `enforce-tool-call-rate-limit`
- **signal_phrases**: cost cap, $ budget, denial of wallet, spend cap, cost-aware throttle
- **related**: `enforce-token-budget-cap`, `enforce-tool-call-rate-limit`

#### `detect-runaway-loop`
- **parent**: `enforce-rate-and-quota-limits` · **phase**: tool-invocation · **attack_surface**: runaway-loop
- **definition**: Detect agent loops (same tool call N times, agent stuck oscillating, tool recursion) and break out before resource exhaustion.
- **scope_in**: same-call detection, oscillation detection, per-tool repeat-count gate, recursion-depth check
- **scope_out**: budget-only enforcement → `enforce-cost-cap-per-task`; archive-bomb → `detect-archive-bomb`
- **signal_phrases**: runaway loop, agent loop detection, infinite loop break, oscillation detection, recursion limit
- **related**: `enforce-tool-call-rate-limit`, `enforce-cost-cap-per-task`

### 5.15 `redact-sensitive-output` 下属（4 个原子）

#### `redact-output-pii`
- **parent**: `redact-sensitive-output` · **phase**: output-generation · **attack_surface**: OWASP LLM02.output-pii
- **definition**: Redact PII / regulated personal data from agent output before returning to user, writing to logs, or sending to downstream systems.
- **scope_in**: output-side PII detector + replacement, log scrubbing, downstream-write redaction, GDPR-aware output filter
- **scope_out**: input-side redaction → `redact-input-pii`; secrets specifically → `redact-output-secret`
- **signal_phrases**: output PII redaction, log scrubbing, GDPR output redaction, output redaction
- **related**: `redact-input-pii`, `redact-output-secret`, `detect-pii-in-input`

#### `redact-output-secret`
- **parent**: `redact-sensitive-output` · **phase**: output-generation · **attack_surface**: OWASP LLM02.output-secret
- **definition**: Redact API keys / tokens / private keys / connection strings from agent output / logs / outbound messages.
- **scope_in**: output-side secret pattern match + redaction, log token scrubbing, outbound-message secret strip
- **scope_out**: secret in input → `detect-credential-in-input`; secret in tool args → `detect-secret-in-args`
- **signal_phrases**: output secret redaction, token scrubbing, key redaction, secrets-in-output filter
- **related**: `detect-credential-in-input`, `detect-secret-in-args`, `redact-output-pii`

#### `redact-output-system-prompt`
- **parent**: `redact-sensitive-output` · **phase**: output-generation · **attack_surface**: OWASP LLM07.system-prompt
- **definition**: Detect and remove system-prompt / hidden-instruction / operator-context content from agent output before user sees it.
- **scope_in**: system-prompt fingerprint match in output, system-prompt fragment removal, operator-context strip
- **scope_out**: detecting **attempts** to extract system prompt → `detect-system-prompt-extraction`; general output policy → `enforce-output-content-policy`
- **signal_phrases**: system prompt redaction, prompt leak filter, operator-context strip, hidden instruction strip
- **related**: `detect-system-prompt-extraction`, `enforce-output-content-policy`

#### `redact-output-internal-infra`
- **parent**: `redact-sensitive-output` · **phase**: output-generation · **attack_surface**: infra-disclosure
- **definition**: Redact internal infrastructure details (internal hostnames, IP addresses, k8s namespace names, internal URL paths, file system layout) from agent output.
- **scope_in**: internal-host pattern match, IP-range scrubbing, internal-URL strip, FS-path obfuscation
- **scope_out**: PII / secret-specific redaction → respective siblings; SSRF mitigation → `enforce-network-egress-allowlist`
- **signal_phrases**: internal infra redaction, hostname scrub, IP scrub, internal URL strip, infra-detail filter
- **related**: `redact-output-pii`, `redact-output-secret`

### 5.16 `detect-data-exfiltration` 下属（4 个原子）

#### `detect-markdown-image-beacon`
- **parent**: `detect-data-exfiltration` · **phase**: output-generation · **attack_surface**: OWASP LLM02.exfil · MITRE ATLAS Exfiltration
- **definition**: Detect markdown image references / inline images whose URL contains user data and points to an attacker-controlled host (beacon).
- **scope_in**: `![](attacker.com/?data=...)` detection, image-URL parameter inspection, image-host allowlist
- **scope_out**: general unsafe URL → `detect-unsafe-url`; egress firewall → `enforce-network-egress-allowlist`
- **signal_phrases**: image beacon, markdown image exfil, image URL data leak, beacon URL detection
- **related**: `detect-base64-payload-in-output`, `detect-covert-channel-in-tool-call`, `enforce-network-egress-allowlist`

#### `detect-base64-payload-in-output`
- **parent**: `detect-data-exfiltration` · **phase**: output-generation · **attack_surface**: covert-channel
- **definition**: Detect long base64 / hex / URL-encoded blobs in agent output that could carry exfiltrated data.
- **scope_in**: long-base64 detection in output, hex/url-encoded long-string detection, suspicious-encoding pattern
- **scope_out**: detected secret strings → `redact-output-secret`; image beacon URLs → `detect-markdown-image-beacon`
- **signal_phrases**: base64 in output, encoded payload exfil, hex-encoded leak, suspicious encoding
- **related**: `detect-markdown-image-beacon`, `detect-covert-channel-in-tool-call`

#### `detect-dns-exfiltration-pattern`
- **parent**: `detect-data-exfiltration` · **phase**: tool-invocation · **attack_surface**: dns-tunnel
- **definition**: Detect DNS-tunneling patterns in DNS lookups initiated by the agent (long subdomain encoding, high-entropy labels, abnormal TXT-record query frequency).
- **scope_in**: long-subdomain entropy check, TXT-record query count anomaly, DNS-tunnel signature
- **scope_out**: HTTP exfil → `detect-markdown-image-beacon`; egress allowlist enforcement → `enforce-network-egress-allowlist`
- **signal_phrases**: DNS exfiltration, DNS tunnel, DNS exfil, long subdomain leak, dnscat
- **related**: `enforce-network-egress-allowlist`, `detect-covert-channel-in-tool-call`

#### `detect-covert-channel-in-tool-call`
- **parent**: `detect-data-exfiltration` · **phase**: tool-invocation · **attack_surface**: covert-channel
- **definition**: Detect covert exfiltration in legitimate-looking tool calls (data hidden in HTTP headers, in user-agent, in cookie values, in webhook fields the user didn't ask about).
- **scope_in**: HTTP header content inspection, user-agent abuse, cookie-content leak, webhook-field exfil
- **scope_out**: arg-level secret leak → `detect-secret-in-args`; URL beacon → `detect-markdown-image-beacon`
- **signal_phrases**: covert channel, HTTP header leak, user-agent exfil, cookie exfil, webhook exfil
- **related**: `detect-secret-in-args`, `detect-markdown-image-beacon`, `detect-dns-exfiltration-pattern`

### 5.17 `enforce-output-content-policy` 下属（5 个原子）

#### `review-generated-code-output`
- **parent**: `enforce-output-content-policy` · **phase**: output-generation · **attack_surface**: OWASP LLM05.code-output
- **definition**: Review code blocks / scripts in agent output for dangerous instructions (rm -rf, curl|bash, fork bomb, hardcoded backdoor) before showing to user.
- **scope_in**: dangerous-shell-pattern in code block, suspicious `curl ... | sh`, fork-bomb pattern, backdoor-pattern in generated code
- **scope_out**: SAST on user-supplied code → `run-sast-scan`; tool-arg shell injection → `detect-shell-command-injection`
- **signal_phrases**: generated code review, output code danger filter, curl-pipe-sh detector, output-code firewall
- **related**: `review-generated-message-output`, `enforce-disallowed-content-rule`

#### `review-generated-message-output`
- **parent**: `enforce-output-content-policy` · **phase**: output-generation · **attack_surface**: OWASP LLM09 / LLM05
- **definition**: Review free-text agent messages (replies / emails / Slack / PR comments) for policy-prohibited content, false claims with high confidence, or operator-impersonation.
- **scope_in**: outgoing-message review, false-claim hedging enforcement, impersonation gate, persuasion-tactic flag
- **scope_out**: code-block review → `review-generated-code-output`; secret in message → `redact-output-secret`
- **signal_phrases**: message review, output-message policy, hedging enforcement, impersonation filter
- **related**: `review-generated-code-output`, `enforce-disallowed-content-rule`, `redact-output-secret`

#### `review-generated-file-write`
- **parent**: `enforce-output-content-policy` · **phase**: output-generation · **attack_surface**: OWASP LLM05.file-write
- **definition**: Review the content the agent is about to write to a file before the write commits (config files, code files, env files).
- **scope_in**: pre-write content scan, env-file write gate, config-write content review, drop-into-prod gate
- **scope_out**: filesystem boundary → `enforce-filesystem-sandbox`; SAST on the new code → `run-sast-scan`
- **signal_phrases**: pre-write review, file-write content gate, config-drop review, env-file write gate
- **related**: `enforce-filesystem-sandbox`, `run-sast-scan`

#### `detect-dangerous-instruction-in-output`
- **parent**: `enforce-output-content-policy` · **phase**: output-generation · **attack_surface**: OWASP LLM05.harmful-output
- **definition**: Detect dangerous operational instructions in agent output (instructions to user that could harm them or third parties: malware-write, unsafe medical/legal advice, financial-fraud guidance).
- **scope_in**: harmful-instruction classifier, dual-use-output filter, dangerous-advice gating
- **scope_out**: pure toxicity / NSFW (planning-side) → `evaluate-content-moderation-rule`; code-block scan → `review-generated-code-output`
- **signal_phrases**: dangerous instruction filter, harmful output detector, dual-use output filter
- **related**: `enforce-disallowed-content-rule`, `review-generated-code-output`

#### `enforce-disallowed-content-rule`
- **parent**: `enforce-output-content-policy` · **phase**: output-generation · **attack_surface**: OWASP LLM09 · agent-output-policy
- **definition**: Apply the deployer's disallowed-content rule pack to agent output post-generation (block / rewrite / escalate / redact).
- **scope_in**: output-side content rule pack, classifier-as-policy on output, post-gen rewrite, post-gen escalation
- **scope_out**: pre-planning content moderation → `evaluate-content-moderation-rule`; system-prompt redaction → `redact-output-system-prompt`
- **signal_phrases**: output content policy, post-gen rule, output rewrite, content-policy enforcement on output
- **related**: `evaluate-content-moderation-rule`, `review-generated-message-output`, `redact-output-system-prompt`

### 5.18 `audit-trail-recording` 下属（3 个原子）

#### `record-decision-trace`
- **parent**: `audit-trail-recording` · **phase**: cross-cutting · **attack_surface**: forensics
- **definition**: Record the agent's decision points (which tool, which args, which rationale, which model, which temperature) for forensic replay.
- **scope_in**: decision-log writer, rationale capture, per-decision metadata persistence, forensic-replay-friendly format
- **scope_out**: tool-call invocation logs (specific) → `record-tool-invocation-trace`; prompt+context snapshot → `record-prompt-and-context-snapshot`
- **signal_phrases**: decision trace, decision log, rationale capture, agent decision audit
- **related**: `record-tool-invocation-trace`, `record-prompt-and-context-snapshot`, `enable-tamper-evident-storage`

#### `record-tool-invocation-trace`
- **parent**: `audit-trail-recording` · **phase**: cross-cutting · **attack_surface**: forensics
- **definition**: Record every tool invocation (timestamp, tool, args, response, side-effect summary) to an append-only log.
- **scope_in**: per-tool-call log entry, append-only invocation store, structured invocation event
- **scope_out**: prompt snapshot → `record-prompt-and-context-snapshot`; tamper-evidence on the log itself → `enable-tamper-evident-storage`
- **signal_phrases**: tool invocation log, tool call audit, invocation trace, append-only tool log
- **related**: `record-decision-trace`, `enable-tamper-evident-storage`

#### `record-prompt-and-context-snapshot`
- **parent**: `audit-trail-recording` · **phase**: cross-cutting · **attack_surface**: forensics · OWASP LLM07
- **definition**: Snapshot the full prompt + context (system prompt, retrieved context, RAG chunks, tool outputs in context) at each decision boundary.
- **scope_in**: full-context snapshot writer, RAG-chunk retention with provenance, prompt-version tracking
- **scope_out**: tool-only invocation log → `record-tool-invocation-trace`; tamper-evidence → `enable-tamper-evident-storage`
- **signal_phrases**: prompt snapshot, context snapshot, RAG chunk capture, prompt-version log
- **related**: `record-decision-trace`, `enable-tamper-evident-storage`

### 5.19 `incident-response-handler` 下属（5 个原子）

#### `halt-in-flight-action`
- **parent**: `incident-response-handler` · **phase**: cross-cutting · **attack_surface**: agent-IR
- **definition**: Stop in-flight tool calls / generations / writes the moment a security event is detected.
- **scope_in**: agent-kill-switch, in-flight-call interrupt, generation-stop signal, atomic-rollback hook
- **scope_out**: longer-term resource isolation → `isolate-affected-resource`; human escalation → archetype `escalate-to-human-sentinel`
- **signal_phrases**: agent kill switch, halt agent, in-flight halt, generation interrupt, immediate stop
- **related**: `snapshot-agent-state`, `isolate-affected-resource`, `request-human-confirmation`

#### `snapshot-agent-state`
- **parent**: `incident-response-handler` · **phase**: cross-cutting · **attack_surface**: agent-IR
- **definition**: Capture full agent state (working memory, plan, context, recent tool calls, env vars) at incident time for triage.
- **scope_in**: state-dump writer, memory snapshot, plan capture, env capture, IR-time triage bundle
- **scope_out**: routine audit logging → `record-prompt-and-context-snapshot`; tamper-evidence → `enable-tamper-evident-storage`
- **signal_phrases**: state snapshot, agent state dump, IR snapshot, triage bundle, incident memory dump
- **related**: `halt-in-flight-action`, `record-prompt-and-context-snapshot`

#### `isolate-affected-resource`
- **parent**: `incident-response-handler` · **phase**: cross-cutting · **attack_surface**: agent-IR
- **definition**: Quarantine resources touched by the suspect actions (revoke tokens, isolate file outputs, network-fence the affected scope).
- **scope_in**: token-revocation on incident, file-quarantine, network-isolate, downstream-system fence
- **scope_out**: pre-incident network policy → `enforce-network-egress-allowlist`; pre-incident permission scope → `verify-allowed-tool-list`
- **signal_phrases**: resource isolation, token revoke, quarantine, IR isolation, network fence on incident
- **related**: `halt-in-flight-action`, `enforce-network-egress-allowlist`

#### `notify-oncall-and-open-ticket`
- **parent**: `incident-response-handler` · **phase**: cross-cutting · **attack_surface**: agent-IR
- **definition**: Page on-call / open a tracking ticket (PagerDuty, Opsgenie, Jira, Linear) with incident metadata when triggered.
- **scope_in**: pager integration, ticket auto-open, IR-context attachment, severity-based routing
- **scope_out**: human-confirmation gate (per-action) → archetype `escalate-to-human-sentinel`; routine audit log → `record-decision-trace`
- **signal_phrases**: oncall notify, ticket open on incident, pager integration, IR ticket auto-open
- **related**: `request-human-confirmation`, `execute-recovery-playbook`

#### `execute-recovery-playbook`
- **parent**: `incident-response-handler` · **phase**: cross-cutting · **attack_surface**: agent-IR · SOAR
- **definition**: Execute a predefined recovery playbook (restore from backup, roll back commit, rotate credentials, redeploy clean image) automatically or with one-click.
- **scope_in**: playbook executor, restore-from-backup runbook, credential-rotation runbook, redeploy runbook
- **scope_out**: snapshot capture → `snapshot-agent-state`; IR ticket → `notify-oncall-and-open-ticket`
- **signal_phrases**: recovery playbook, IR runbook, automated rollback, credential rotation runbook
- **related**: `isolate-affected-resource`, `notify-oncall-and-open-ticket`

### 5.20 `escalate-to-human-sentinel` ⭐ 下属（4 个原子）

> **背景**：项目书指定为最高优先级 atomic skill。**本项目 training-free**——本组 4 atoms 提供确定性 HITL 通道（rule-based，无 ML）；ML Sentinel 预测器划归 separate downstream project，本组 atom 接口已对齐其输入/输出契约，未来接入无需改 bundle。

#### `request-human-confirmation`
- **parent**: `escalate-to-human-sentinel` · **phase**: cross-cutting (highest priority) · **attack_surface**: HITL
- **definition**: Pause autonomous execution and emit an explicit confirmation request to the human operator before proceeding with a flagged action.
- **scope_in**: confirmation-request emit, pause-and-await flow, irreversibility-triggered confirmation, blast-radius-triggered confirmation
- **scope_out**: clarification (intent-ambiguity, not risk-driven) → `elicit-clarification-before-act`; routine notification → `notify-oncall-and-open-ticket`
- **signal_phrases**: human in the loop, confirmation gate, approval gate, pause for confirmation, kill switch
- **related**: `present-risk-rationale`, `await-human-decision-or-timeout`, `log-human-decision-outcome`

#### `present-risk-rationale`
- **parent**: `escalate-to-human-sentinel` · **phase**: cross-cutting · **attack_surface**: HITL
- **definition**: Present the human operator with the risk classification, evidence, proposed action, and reversibility / blast-radius summary so they can make an informed decision.
- **scope_in**: risk-summary card, evidence bundle attachment, blast-radius summary, reversibility note
- **scope_out**: just emitting the gate → `request-human-confirmation`; capturing the response → `log-human-decision-outcome`
- **signal_phrases**: risk rationale, risk-summary card, blast-radius summary, evidence card, decision context
- **related**: `request-human-confirmation`, `log-human-decision-outcome`

#### `await-human-decision-or-timeout`
- **parent**: `escalate-to-human-sentinel` · **phase**: cross-cutting · **attack_surface**: HITL
- **definition**: Wait for human decision; on timeout default to fail-safe (block by default, never auto-allow).
- **scope_in**: blocking wait with timeout, fail-safe-default-deny, deadline-driven escalation, timeout-policy gate
- **scope_out**: emitting the gate → `request-human-confirmation`; recording the outcome → `log-human-decision-outcome`
- **signal_phrases**: await human decision, fail-safe default, timeout-on-confirm, default-deny on timeout
- **related**: `request-human-confirmation`, `log-human-decision-outcome`

#### `log-human-decision-outcome`
- **parent**: `escalate-to-human-sentinel` · **phase**: cross-cutting · **attack_surface**: HITL · forensics
- **definition**: Persist the human decision (allow / deny / modify) along with rationale + identity for later audit and Sentinel-model training-data feedback.
- **scope_in**: decision-outcome log entry, identity binding, rationale capture, training-data export hook
- **scope_out**: general decision trace → `record-decision-trace`; tamper-evident storage → `enable-tamper-evident-storage`
- **signal_phrases**: human decision log, HITL outcome log, approval log, decision-feedback capture
- **related**: `record-decision-trace`, `enable-tamper-evident-storage`

## 6. 计数与分布（按阶段 + 按 archetype 双视图）

### 6.1 按阶段（primary-phase 计数；不含 cross-phase 借用）

| Phase | 原子数 | 占比 |
| --- | ---: | ---: |
| input-understanding | 13 | 13.7% |
| planning | 10 | 10.5% |
| tool-invocation | 49 | 51.6% |
| output-generation | 11 | 11.6% |
| cross-cutting | 12 | 12.6% |
| **合计** | **95\*** | 100% |

\* §4 主 phase 总计 95（unique atoms）+ 1 个跨双 phase 显示（`detect-indirect-prompt-injection` primary 是 tool-invocation 但 §4.1.4 借用一次显示）。Atom 集合 unique = 95。

**观察**：v0.7 把 v0.6 涨到 22% 的 planning 阶段精简回 13%——因为 SMT 形式化方法、OWASP API SAST、agent reputation 等"研究 / 离线 / vapor-infra"原子已下架。tool-invocation 仍是最大头（50%），符合"agent 安全核心战场是工具调用边界"的预期。Router 实现时 tool phase 的原子加载策略要重点设计。

### 6.2 按 archetype（与 §5 子节对应）

| Archetype | 原子数 | 跨 phase？ |
| --- | ---: | --- |
| detect-prompt-injection | 5 | ✅ input + tool-inv |
| classify-input-intent-ambiguity | 3 | input only |
| scan-input-for-pii-and-secrets | 5 | input only |
| enforce-policy-as-code | 2 | planning only |
| check-tool-permission-scope | 4 | planning only |
| detect-task-overreach | 4 | planning only |
| validate-tool-argument-safety | 8 | tool-inv only |
| constrain-workspace-boundary | 6 | tool-inv only |
| validate-agent-tool-trust | 11 | ✅ input + planning + tool-inv（A2A 信任原子拉宽 phase 覆盖）|
| detect-supply-chain-risk | 8 | tool-inv only |
| scan-code-for-vulnerabilities | 5 | tool-inv only（PreToolUse matcher 限定 Write\|Edit\|MultiEdit）|
| detect-malicious-payload-in-tool-output | 5 | tool-inv only |
| enforce-rate-and-quota-limits | 4 | tool-inv only |
| redact-sensitive-output | 4 | output only |
| detect-data-exfiltration | 4 | ✅ tool-inv + output |
| enforce-output-content-policy | 5 | output only |
| audit-trail-recording | 3 | cross-cutting |
| incident-response-handler | 5 | cross-cutting |
| escalate-to-human-sentinel | 4 | cross-cutting |
| **合计** | **95** | |

最重 archetype 是 `validate-agent-tool-trust`（**14**，v0.7 -2 from v0.6），覆盖 MCP 4 类原生威胁 + skill poisoning + typosquat + signature + publisher + loader + **A2A 信任**（agent identity / delegation chain / MCP server trustworthiness）+ **time-bomb / dormant-payload**。`compute-agent-trust-score` 和 `query-agent-reputation` 已下架（依赖不存在的全局信任 infra）。

**3 个跨 phase 的 archetype**（`detect-prompt-injection`、`validate-agent-tool-trust`、`detect-data-exfiltration`）是 Router 实现"阶段-技能映射表"时的关键复用点。v0.7 中 `scan-code-for-vulnerabilities` 因下架 3 个 OWASP API 类 SAST，重新收敛到 tool-inv only。

**v0.7 删除的 `threat-model-task` archetype**：原 6 atoms 中 STRIDE / attack-tree 是 agent 作为输出**产出**的 deliverable（不是约束 agent 的 guardrail），threat-actor / OWASP 清单 / RoE 是离线分析师工作。仅 `enumerate-task-side-effects` 是真正的 planning 期 runtime 检查 → 已搬到 `detect-task-overreach`。

## 7. LLM 输出 schema（受控词表的使用契约）

每个 Stage 3 残量候选（path: 1390 records）经 LLM 审计后产出**一行** JSON：

```json
{
  "record_id": "<absolute path of the record>",
  "kind": "skill | mcp",
  "is_safety_relevant": true,
  "skip_reason": null,
  "covered_phases": ["input-understanding", "tool-invocation"],
  "primary_atoms": [
    "validate-tool-argument-safety/detect-shell-command-injection",
    "validate-tool-argument-safety/detect-path-traversal"
  ],
  "secondary_atoms": [
    "constrain-workspace-boundary/enforce-filesystem-sandbox"
  ],
  "self_risk_flags": [
    "asks-for-broad-fs-write",
    "executes-shell-on-install"
  ],
  "suggested_new_atoms": [
    {
      "proposed_id": "verify-oauth-flow-security",
      "suggested_parent_archetype": "validate-tool-argument-safety",
      "evidence_from_this_record": "Skill specifically validates OAuth state parameter, PKCE, redirect_uri allowlist enforcement",
      "rough_definition": "Validate OAuth flow components (state, PKCE, redirect_uri, audience) for the agent's outbound auth flows"
    }
  ],
  "free_form_notes": "Skill bundles a custom shell-arg sanitizer + a mini OPA policy bundle. Sanitizer logic looks domain-specific; OPA is generic.",
  "confidence": 0.85
}
```

字段说明：

| 字段 | 必填 | 取值 |
| --- | --- | --- |
| `record_id` | ✅ | 候选的绝对路径（与 Stage 3 manifest 对齐） |
| `kind` | ✅ | `skill` \| `mcp` |
| `is_safety_relevant` | ✅ | bool。`false` 时其余字段允许为空，但必须填 `skip_reason` |
| `skip_reason` | 条件 | 例如 `"boilerplate-only"` / `"non-security"` / `"placeholder-only"` / `"duplicate-of:<path>"` |
| `covered_phases` | ✅ | 该 skill 跨越的执行阶段（多选）|
| `primary_atoms` | ✅ | 1-3 个，格式 `<archetype_id>/<atom_id>`。空数组 = LLM 认为词表不够覆盖，必须在 `free_form_notes` 解释 |
| `secondary_atoms` | ⚪ | 0-5 个 |
| `self_risk_flags` | ⚪ | 该 skill 自身**带来**的风险（不只是 mitigated 的风险）。短标签即可 |
| `suggested_new_atoms` | ⚪ | 候选明显承担词表中不存在的能力时填。每条含 `proposed_id` / `suggested_parent_archetype` / `evidence_from_this_record` / `rough_definition`。**保守填**：只在能力清晰且词表确实漏了时才提；模糊情况写到 `free_form_notes` 即可。1.4 阶段会按 `proposed_id` 聚类决定是否真的新增 |
| `free_form_notes` | ⚪ | 兜底，词表外的模糊 / 边界 / 尚未结构化的描述。比 `suggested_new_atoms` 自由度高 |
| `confidence` | ⚪ | LLM 自评（用于挑可疑样本做 spot-check）|

## 8. 复审 checklist（请用户审 v0.1 时对照）

### 8.1 阶段维度（v0.1 新增的核心审阅项）

1. **Phase 切分是否符合 Router 实际查表方式？**——五个 phase（input-understanding / planning / tool-invocation / output-generation / cross-cutting）跟项目书 §3 一致，但实际 Router 实现可能想细分（比如 tool-invocation 拆成 pre-call / response-handling）。要不要现在就拆？
2. **每个 phase 装的原子数量平衡吗？**——tool-invocation 46 个偏重，input/output/planning/cross-cutting 各 11-13 个偏轻。要不要把 tool-invocation 内部进一步分组（pre-call validation / call-time enforcement / post-call output handling）？
3. **Cross-phase 复用矩阵（§4.6）是不是 Router 真正需要的 lookup 形式？**——目前 13 个原子 / 系列被标 cross-phase。Router 实现时建议常驻的 audit/incident/sentinel 三组是否确认？
4. **是否漏标 cross-phase 关系？**——例如 `enforce-token-budget-cap` 应不应该也算 cross-cutting（任何 phase 都消 token）？`enforce-rate-and-quota-limits` 系列是不是应该跟 `incident-response-handler` 一样常驻？
5. **要不要给某些原子拆成"分阶段变体"而不是用 cross-phase 标记？**——典型问题：`detect-prompt-injection` 是 input-side / tool-output-side 一个原子两阶段（cross-listed），还是拆成 `detect-direct-prompt-injection-input` 和 `detect-prompt-injection-in-tool-output` 两个原子？目前选了前者（避免标签膨胀），但 Router 实现可能更想要后者。

### 8.2 原子集合维度（v0 已有的复审项，未变）

6. **粒度**：95 个是否合适？（少于 50 = 跟 archetype 区别不大；多于 150 = LLM 选项太多容易乱标）
7. **覆盖**：项目书 §1.1 列举的 7 类示例能力（"检测意图歧义、检查参数安全、约束工作区边界、检查敏感信息外泄……"）是否全部映射到至少一个原子？
8. **重叠**：有没有原子之间边界不清、scope_in/scope_out 写得不够互斥的？特别留意：
   - `detect-direct-prompt-injection` vs `detect-jailbreak-template`（input phase 内部）
   - `detect-shell-command-injection`（tool-arg 层）vs `detect-injection-flaw`（源码层）
   - `evaluate-content-moderation-rule`（planning 层）vs `enforce-disallowed-content-rule`（output 层）vs `detect-dangerous-instruction-in-output`（output 层）
9. **死锚点处理**：`classify-input-intent-ambiguity` 在 Stage 3 是死锚（仅 2 命中）。这里给了 3 个原子，是不是太多？要不要先合并成 1 个等 1.2 跑完再决定？
10. **MCP 专用原子**：`validate-agent-tool-trust` 下塞了 4 个 MCP-specific 原子（confused-deputy / token-passthrough / session-hijack / SSRF）。这跟"原子能力描述能力，不绑定平台"的原则有冲突吗？还是 MCP 这几类是规范层的独立威胁、必须独立列？
11. **OOS 边界**：训练阶段攻击（poisoning, evasion, membership inference）显式不在词表内。OK 还是需要至少留 1-2 个原子兜底？
12. **LLM 输出 schema**：§7 那份 JSON 是否就是 1.2/1.3 最终想要的格式？字段够不够 / 多不多？是否需要让 LLM **同时**输出 `phase` 字段（已有 `covered_phases`）来跟 §4 对齐？

## 9. 已知 v1 待办（审定后的执行项）

- [ ] 用户复审 v0.1 → 给出增/删/合并/重写意见
- [ ] 应用复审意见出 v1
- [ ] 把词表序列化成 Python config（`scripts/_atomic_capabilities.py`）供后续 LLM 审计脚本和 manifest validator 使用
- [ ] 在 1.2 LLM prompt 里嵌入此词表 + §7 schema
- [ ] 1.2/1.3 跑完后回看 §8 第 1、4 条做 v1 → v2 迭代

---

## 10. 包装标准（v0.5：enforcement_mode + archetype-as-skill 双维度）

> ⚠️ **v1.3（2026-06-08）真层级更新**：本节下文把 archetype 描述为 `skills/<archetype-id>/SKILL.md`（top-level skill）——这是 v1.2 及之前的布局，保留作 traceability。**v1.3 起 14 个 archetype 已降为 Router 的 reference 文档** `skills/safety-router-skill/references/archetypes/<archetype>.md`，唯一 top-level skill = `safety-router-skill`，Router 路由后由模型 `Read` 加载。"archetype = 包装边界"这一刀不变，变的只是 archetype 的物理落地（独立 skill → Router 子文档）。当前真实布局见 §0 v1.3 条目 + PROJECT_OVERVIEW §3/§4.6。
>
> **架构演进**：
> - **v0.4**（2026-05-09）确定 archetype = SKILL.md 的包装边界（不是 atom）
> - **v0.5**（2026-05-10）进一步引入 **enforcement_mode** 作为更上一层的"包装方式"分流——hook 和 skill 走完全不同的部署形态，不应该混在 SKILL.md 里

### 10.0 两个独立维度

| 维度 | 取值 | 决定 |
| --- | --- | --- |
| **enforcement_mode**（每个 atom）| `hook` / `skill` / `hybrid` | 这个 atom 是 host 硬强制（settings.json hook config）还是 agent 通过 SKILL.md tool 调用 |
| **execution_type**（每个 archetype 内的 skill/hybrid 部分）| `workflow` / `checklist` / `mixed` | SKILL.md 内部 tools 怎么协调（仅对 skill/hybrid mode 的 atoms 有意义；hook mode 不适用）|

### 10.1 enforcement_mode 详细定义

| Mode | 实现形态 | host 触发点 | 典型 atom |
| --- | --- | --- | --- |
| 🔒 **hook** | 注册到 host 的 hook config（如 Claude Code `.claude/settings.json` 的 PreToolUse / PostToolUse / Stop / UserPromptSubmit hooks），调一段确定性 script / regex / engine call | install-time + 各 hook 触发点 | `verify-allowed-tool-list` / `enforce-filesystem-sandbox` / `redact-output-pii` / `record-tool-invocation-trace` |
| 🧠 **skill** | 在 archetype-level SKILL.md 里作为 tool 描述；agent 顺着 SKILL.md 走时调用（LLM judge / 推理 / 上下文判断）| 由 Router meta-skill 在合适 phase 触发 | `detect-direct-prompt-injection` / `classify-request-ambiguity-level` / `generate-stride-threat-model` |
| ⚡ **hybrid** | 同时有 hook fast path + skill semantic fallback | hook 跑 + 不确定时升给 LLM | `detect-pii-in-input`（regex hook + LLM 上下文）/ `detect-shell-command-injection`（regex + LLM）/ `evaluate-opa-rego-rule`（OPA + LLM 边界 case）|

**95 个原子的 enforcement_mode 分布**（v0.7）：60 hook (63%) · 21 hybrid (22%) · 14 skill (15%)。完整 per-atom 映射见 [scripts/build_review_dashboard.py](../scripts/build_review_dashboard.py) `ATOM_ENFORCEMENT_MODE` 字典。

### 10.2 包装单元（按 enforcement_mode 分流）

```
agent-safety-orchestrator/
├── hooks/                           ← 所有 enforcement_mode=hook 的 atoms
│   ├── hooks.json                   ← 自动发现的 plugin hook 条目（命令路径用 ${CLAUDE_PLUGIN_ROOT}）
│   ├── scripts/                     ← 各 hook 调用的脚本
│   │   ├── verify-allowed-tool-list.sh
│   │   ├── enforce-filesystem-sandbox.sh
│   │   ├── redact-output-pii.py
│   │   └── ...                       (~80 个 hook script，含 hybrid 的 hook 部分)
│   └── install.sh                   ← merge 进 host settings
│
├── skills/                          ← enforcement_mode=skill / hybrid 的 atoms（按 archetype 分组，自动发现）
│   ├── detect-prompt-injection/     ← 5 atoms (4 skill + 1 hybrid 的 LLM 部分)
│   │   ├── SKILL.md
│   │   └── tools/
│   ├── classify-input-intent-ambiguity/  ← 2 skill atoms (排除 1 hook atom)
│   │   ├── SKILL.md
│   │   └── tools/
│   ├── detect-task-overreach/       ← 3 skill + 1 hook（含 v0.7 搬入的 enumerate-task-side-effects）
│   │   ├── SKILL.md
│   │   └── tools/
│   ├── ... (共 14 个 SKILL.md)
│   │
│   └── safety-router-skill/SKILL.md  ← Router meta-skill
│
└── README.md
```

**最终出货 = 1 hook config bundle + 14 archetype SKILL.md + 1 Router meta-skill = 16 个顶层文件**（v0.7）。

> **5 个 pure-hook archetype 不出 SKILL.md**（它们的所有 atoms 都是 hook，agent 不需要"决策"调用谁——host 自动强制）：
> - `check-tool-permission-scope` (4/4 hook)
> - `constrain-workspace-boundary` (6/6 hook)
> - `detect-malicious-payload-in-tool-output` (5/5 hook)
> - `audit-trail-recording` (3/3 hook) — v0.7 精简后回到 pure-hook
> - `scan-code-for-vulnerabilities` (5/5 hook) — v0.7 精简后回到 pure-hook，**matcher 限定 Write\|Edit\|MultiEdit**
>
> 这 5 个 archetype 的 23 个 hook atoms 直接进 hooks/。Router meta-skill 不路由它们（hook 自己就在 host 层强制了），Router 路由表只列 **14 个** skill / hybrid archetype（v0.7 下架 `threat-model-task` 整个 archetype；`scan-code-for-vulnerabilities` 因 v0.6 高 FP SAST 下架后回归 pure-hook）。

### 10.3 SKILL.md 结构（仅对 skill / hybrid 包装；5 段固定 + frontmatter）

````markdown
---
name: classify-input-intent-ambiguity
phase: input-understanding
execution_type: workflow      # workflow | checklist | mixed
skill_tools_count: 2          # 不含 hook tools，只数 skill / hybrid
hook_tools_count: 1           # 这些不在本 SKILL.md 调用，由 hook config 强制；仅作信息
---

## 1. Purpose
本 skill 处理什么类别的安全问题（复用 §5 archetype 描述）

## 2. When to use
Phase 触发 / scope_in / scope_out

## 3. How to check
按 §10.4 三种 execution_type 模板之一，**只协调 skill/hybrid mode 的 tools**；
hook tools 在 host 层已自动强制，本节不需要重复

## 4. Internal tools (skill / hybrid 部分)
列出本 archetype 中 enforcement_mode ∈ {skill, hybrid} 的 tools；
hook tools 单独在 §5 跨链一行说明它们由 hook config 强制

## 5. Aggregate verdict
本 skill 整体产出给 Router meta-skill 的 verdict
````

### 10.4 execution_type 模板（仅对 SKILL.md 内部 skill/hybrid tools 适用）

**🔄 workflow / ☑ checklist / 🔀 mixed** 三种模板内容跟 v0.4 §10.3 一致，不复述。**对 hook-only 的 atom 这三种类型都不适用**（hook 是 host 层并行触发，不需要 agent 协调）。

### 10.5 archetype 双维度分类（v1 freeze，95 原子 / 19 archetypes / 18 文件）

> **v0.7 包装变动**：① `threat-model-task` 整个 archetype 下架（STRIDE / attack-tree 是 agent-as-output deliverable；threat-actor / OWASP 清单 / RoE 是离线分析；side-effects 搬到 detect-task-overreach）。② `scan-code-for-vulnerabilities` 删 v0.6 加的 3 个高 FP SAST → 重回 pure-hook（**关键约束：matcher 限定 Write\|Edit\|MultiEdit，只在改代码时触发**）。③ `audit-trail-recording` 删 tamper-evident-storage + crypto-intent-binding。④ `enforce-policy-as-code` 删 formal-policy + regulatory-compliance。⑤ `validate-agent-tool-trust` 删 trust-score + reputation-query。⑥ 其他 vapor-infra / multi-call 统计原子下架。最终 **5 pure-hook + 0 pure-skill + 14 mixed-enforce = 14 SKILL.md + 1 hook config + 1 Router meta = 16 个文件**。

| Archetype | atoms | enforcement breakdown | 出货方式 |
| --- | ---: | --- | --- |
| `audit-trail-recording` | 3 | 3 hook | 🔒 pure-hook（仅 hook config）|
| `check-tool-permission-scope` | 4 | 4 hook | 🔒 pure-hook（仅 hook config）|
| `constrain-workspace-boundary` | 6 | 6 hook | 🔒 pure-hook（仅 hook config）|
| `detect-malicious-payload-in-tool-output` | 5 | 5 hook | 🔒 pure-hook（仅 hook config）|
| `scan-code-for-vulnerabilities` | 5 | 5 hook | 🔒 pure-hook（仅 hook config，matcher 限定 Write\|Edit\|MultiEdit）|
| `classify-input-intent-ambiguity` | 3 | 1 hook + 2 skill | mixed-enforce SKILL.md (execution: workflow) |
| `detect-prompt-injection` | 5 | 1 hybrid + 4 skill | mixed-enforce SKILL.md (execution: checklist) |
| `scan-input-for-pii-and-secrets` | 5 | 3 hook + 2 hybrid | mixed-enforce SKILL.md (execution: mixed) |
| `enforce-policy-as-code` | 2 | 1 hook + 1 hybrid | mixed-enforce SKILL.md (execution: checklist) |
| `detect-task-overreach` | 4 | 1 hook + 3 skill | mixed-enforce SKILL.md (execution: workflow) |
| `validate-tool-argument-safety` | 8 | 6 hook + 2 hybrid | mixed-enforce SKILL.md (execution: checklist) |
| `validate-agent-tool-trust` | 11 | 6 hook + 4 hybrid + 1 skill | mixed-enforce SKILL.md (execution: checklist) |
| `detect-supply-chain-risk` | 8 | 5 hook + 3 hybrid | mixed-enforce SKILL.md (execution: checklist) |
| `enforce-rate-and-quota-limits` | 4 | 3 hook + 1 hybrid | mixed-enforce SKILL.md (execution: mixed) |
| `redact-sensitive-output` | 4 | 2 hook + 2 hybrid | mixed-enforce SKILL.md (execution: mixed) |
| `detect-data-exfiltration` | 4 | 2 hook + 2 hybrid | mixed-enforce SKILL.md (execution: checklist) |
| `enforce-output-content-policy` | 5 | 2 hybrid + 3 skill | mixed-enforce SKILL.md (execution: checklist) |
| `incident-response-handler` | 5 | 4 hook + 1 hybrid | mixed-enforce SKILL.md (execution: workflow) |
| `escalate-to-human-sentinel` ⭐ | 4 | 3 hook + 1 skill | mixed-enforce SKILL.md (execution: workflow) |
| **合计** | **95** | **60 hook + 21 hybrid + 14 skill** | **14 SKILL.md + 1 hook config + 1 Router meta + 2 helper = 18 文件**（v1.1，加 cache + health helper）|

### 10.6 执行权限

代码型 hook（hook 类与 hybrid 的 hook 部分）通过 host 的 PreToolUse / PostToolUse / Stop 等 hook 机制 + Bash 执行权限触发。SKILL.md 内的 skill/hybrid tools 通过 agent host 的 Bash / shell 工具调用。**默认假设 host 支持 hook 机制 + Bash 权限**（Claude Code 完整支持；OpenClaw / Codex CLI 部分支持详见 hook config bundle 的 `host-adapter/` 目录）。Host 不支持 hook 时，相关 atoms 降级到 skill 模式（仍可用，但失去硬强制）。

### 10.7 不做自反射 / 自动发现

Router meta-skill 硬编码 14 个 skill / hybrid skill 的列表 + 5 个 phase 的路由表；hook config 硬编码 ~81 个 hook 条目（60 pure-hook + 21 hybrid fast path）。**项目结束时定版，作为 frozen artifact 出**。新增 atom = 重发包。

## 11. Router 架构定位（meta-skill 路径）

> **架构决策**（2026-05-09 与用户对齐）：项目书 §3 的 "Safety Router" **不是独立程序 / middleware**，而是一份 **meta-skill SKILL.md**——agent host 的主 LLM 读这份 meta-skill 就成了 Router 本身。

### 11.1 模型分工

```
agent host LLM (Claude / Opus / GLM / ...)        ← Router 本体（无新进程）
    │
    │ system context loads
    ▼
safety-router-skill/SKILL.md (meta-skill)         ← Router 路由表
    "你在 phase X 时：调以下 skills [...]
     skill 返回 block → 停 + 调 escalate-to-human-sentinel
     skill 返回 yellow → 调 present-risk-rationale ..."
    │
    │ agent 自主调用（同一 host LLM 顺着 meta-skill 走）
    ▼
skills/<archetype-id>/SKILL.md  (14 个 skill / hybrid archetype)
    每个 skill 内部按 §10.4 execution_type 协调 skill/hybrid tools
    （hook tools 不在此处协调——已由 hook config 在 host 层硬强制）

并行存在（不被 Router 路由，host 层自动触发）：
hooks/  ← ~81 个 hook 条目（5 个 pure-hook archetype + 14 mixed-enforce 中的 hook + hybrid fast path）
    settings.json hook 注入 → host 在 PreToolUse / PostToolUse / Stop 等触发点自动执行
```

### 11.2 跟项目书"Router 轻量化"的对齐

| 项目书原文 | meta-skill 模型对应 |
| --- | --- |
| "内部维护一张阶段-技能映射表" | meta-skill SKILL.md 的某一节是这张表（自然语言形式）|
| "通过阅读原子技能描述文件做路由决策（避免重模型调用）" | atom 描述在 system context 里**预加载**，路由决策不额外调外部 LLM；agent 主 LLM 顺着上下文里的描述决定调谁 |
| "轻量化、低延迟、低算力" | 没有独立中间件 = 部署轻；但 **agent 推理本身的延迟是固有的**（见 §11.3） |

实际上 agent 调 atom 时**会有 LLM 推理参与**——SKILL.md 是给 LLM 看的，而非纯文本配置。这是 meta-skill 模型固有的成本。

### 11.3 延迟 / 成本权衡（vs 独立 middleware Router）

| 维度 | meta-skill 模型（本项目）| 独立 middleware 模型 |
| --- | --- | --- |
| 部署复杂度 | 极低（放 SKILL.md 进 host 即可）| 高（部署中间件 + 适配每个 host）|
| Host 兼容 | 任意（Claude Code / OpenClaw / Codex CLI / Cursor / ...）| 每个 host 单独适配 |
| Phase 边界延迟（粗算）| ~1-2s（含 LLM routing turn）| ~200-500ms（纯并行 fan-out）|
| Token 成本 | 每 phase 边界 +5-15k tokens（meta + atom desc + verdicts）| 0 |
| 合规强制力 | best-effort（agent 可能不严格 follow）| 强（中间件代码层硬拦截）|
| 路由逻辑可读 / 可改 | 自然语言路由表，运营友好 | 代码 + config，工程友好 |
| Audit 可解释 | LLM 推理链可审 | 中间件结构化日志可审 |

**4 条降延迟 / 降成本的优化手段**（meta-skill 撰写时可吸纳；§4.6 meta-skill 实施时已落 #2 #4 为默认，#1 #3 为 opt-in；最终值留 pilot 阶段调校）：

1. **Atom 描述全量预加载**——session 启动时把 95 个 atom 描述全部塞进 system context，避免 per-phase 现读。95 × ~200 tokens ≈ 19k tokens，对 200k+ context 占比可接受
2. **并行 tool call**——现代 agent host 普遍支持单 turn 多 tool call。Meta-skill 应明确写 "在 phase X **并行 fire** 以下 atoms"，避免 agent 串行调
3. **Code-atom 批量执行**——把同一 phase 的所有 code-type atom 包成一个 wrapper script（如 `python checks/run_phase.py --phase=input --input="$INPUT"`），1 次 Bash 调用跑完所有 code atoms，省 N-1 次 round-trip
4. **Phase mapping 写死**——meta-skill 的 phase→atom 映射表写成"在 phase X **必跑** [a, b, c]"硬规则，不让 agent 自由发挥决定调哪些。省一个"thinking" turn

应用 4 条优化后，realistic 延迟可降到 **~600ms-1.5s per phase**，跟 middleware 的 ~200-500ms 差距缩小到 2-3×。这个差距对人机交互场景可接受；对 agent 高频自动 tool call 场景需要重点关注。

### 11.4 这次决策的边界

- ✅ 已决：Router 模型用 meta-skill 路径
- ✅ 已决：Atom 包装标准用 §10
- ✅ §4.6 已落地：[`agent-safety-orchestrator/skills/safety-router-skill/SKILL.md`](../agent-safety-orchestrator/skills/safety-router-skill/SKILL.md)。**原"留 Module 3 实现期"的工作已合并到 §4.6 + pilot 阶段**（参 `docs/PROJECT_OVERVIEW.md` §6 模块 3 dissolution 说明）。
- ⚪ 未决（留 pilot 阶段）：§11.3 4 条优化手段的默认 vs opt-in 切换（如 `SAFETY_ORCH_PRELOAD_ARCHETYPES=1` 是否升为默认）、是否给 host 提供"严格模式"中间件 hook 强制 atom 调用

## 12. 部署配置与降级语义（v1.1 新增）

> **设计目标**：让非工程背景的用户能"装上即用"——纯本地 hook 零配置，需要外部 IO 的 hook 通过单个 `.env` 渐进开启；网络抖动 / 端点失效不能静默降级，必须在 session 启动 banner 上**显式**列出受影响 atom。

### 12.1 三层配置 tier

| Tier | 用户操作 | 启用的 atom 范围 |
| --- | --- | --- |
| **Tier 0**（零配置）| 装包即可 | 所有 pure-local hook（~52）+ 所有 SKILL.md（14 archetypes）+ 公开免费端点的网络 hook：`check-package-cve` (osv.dev) / `detect-hallucinated-package` (npm/PyPI registry) / `check-package-recency-anomaly` (registry metadata) |
| **Tier 1**（单 `.env`）| 复制 `.env.example` → `.env`，按需填 key | `check-malware-hash-ioc` (VIRUSTOTAL_API_KEY) / `check-dependency-confusion` (INTERNAL_REGISTRY_HOSTS) / `verify-skill-signature` 在线吊销 (SKILL_REVOCATION_URL) |
| **Tier 2**（air-gap / enterprise）| 自定义 endpoint URL + bundled offline snapshot + 周期性 `safety-orch refresh-db` | 内网部署 / 隔离环境；所有公网 endpoint 替换为内网 mirror，CVE 数据通过离线 osv-export snapshot 提供 |

未配置 / 未启用的 atom 进入"待激活"状态，**Router 启动 banner 显式列出**——不会静默忽略。

### 12.2 fail_policy 三态语义

每个 hook-network atom（以及任何高 stakes 的本地 hook）的卡片新增 `fail_policy` 字段，决定外部依赖 / 本地资源失败时的行为：

| fail_policy | 失败时行为 | 适用判据 |
| --- | --- | --- |
| `fail-open-warn` | 放行 + 写 audit log + Router status 标 degraded | 误漏短窗口可接受的低 stakes atom（recency anomaly、IOC 查询、hallucinated package） |
| `fail-soft-block` | 阻断 + 需用户显式 `--accept-degraded` 才能继续 | 高 stakes 信息型 atom——漏掉一次就是真实危险（critical CVE 检查） |
| `fail-closed` | 默认阻断，不可绕过 | 安全语义不可降级（签名验证、publisher allowlist、typosquat 检查、dependency confusion） |

**选择原则**：能 `fail-open-warn` 的尽量 `fail-open-warn`（不阻塞 agent 工作流），但凡漏检会让用户**暴露在真实攻击下**的就用 `fail-soft-block` 或 `fail-closed`。**Audit log 必须保留**，事后可统计 degraded 占比。

### 12.3 8 个 hook-network atom 的部署元数据汇总

| Atom | requires_network | requires_api_key | fail_policy |
| --- | :---: | --- | --- |
| `check-package-cve` | ✅ | — | `fail-soft-block` |
| `detect-hallucinated-package` | ✅ | — | `fail-open-warn` |
| `check-package-recency-anomaly` | ✅ | — | `fail-open-warn` |
| `check-malware-hash-ioc` | ✅ | `VIRUSTOTAL_API_KEY` | `fail-open-warn` |
| `check-package-typosquat` | ❌（bundled DB）| — | `fail-closed` |
| `check-dependency-confusion` | ❌（local config）| `INTERNAL_REGISTRY_HOSTS` | `fail-closed` |
| `verify-skill-signature` | ❌（bundled pubkey）| `SKILL_REVOCATION_URL`（可选）| `fail-closed` |
| `verify-tool-publisher-identity` | ❌（local allowlist）| — | `fail-closed` |

**观察**：8 个 atom 里只有 1 个（`check-malware-hash-ioc`）需要付费 / 认证 API key。其它 7 个都是公开免费端点或本地配置，零配置友好度高于初观感。

### 12.4 两块共享 helper（出货文件 16 → 18）

不让 14 个 SKILL.md 各自实现外部 IO + 健康检查——packaging 阶段加 2 个 helper 模块，统一吃所有 hook-network atom 的 IO + 降级逻辑：

1. **`cache-snapshot-helper/`** —— SQLite 本地缓存（`~/.cache/safety-orch/cache.db`）+ bundled osv.dev snapshot + `safety-orch refresh-db` CLI。所有 hook-network atom 经它访问外部端点。
   - TTL：CVE 24h / package metadata 7d / malware IOC 1h
   - 支持 osv.dev `/v1/querybatch` 批查（50 包 = 1 HTTP 请求）
   - npm registry 用 ETag → 304 不消耗 quota
   - Soft circuit breaker：单 atom hit 429 → 60s 退避 + 该 atom 标 degraded

2. **`health-status-helper/`** —— Router 启动时并行 ping 每个 network endpoint（<1s），维护 `~/.safety-orch/atom-status.json`，session 启动 banner 输出健康状态：
   ```
   Safety Orchestrator: 14/16 atoms active
   ⚠️ Degraded: check-package-cve (osv.dev unreachable, snapshot age 8d)
   ⚠️ Disabled: check-malware-hash-ioc (VIRUSTOTAL_API_KEY missing)
   ```
   每次 fail-open 写入 `record-decision-trace` 结构化日志，事后可查 / 可统计。

**出货文件清单**（v1.1 修订）：
- 1 Router meta-skill
- 14 SKILL.md
- 1 hook config bundle
- **1 cache/snapshot helper**（新增）
- **1 health/status helper**（新增）
- **= 18 个出货文件**

### 12.5 v1 "freeze" 含义的明确

v1 freeze 指 **atom 集合冻结**（95 atoms / 19 archetypes 不再增删）+ **定义性字段冻结**（id / parent / phase / definition / scope_in / scope_out / signal_phrases / related）。**部署元数据**——本节加的 `requires_network` / `requires_api_key` / `fail_policy`，及未来可能加的 `endpoint_strategy` / `hook_ordering_dependency` / `shared_helper_id` 等——**允许在 v1.x 里继续补**。

packaging 阶段（§4.6）和后续 pilot 阶段会在实现期发现新的元数据需求（原文档把 pilot 这部分工作归在"Module 3 Router runtime"，2026-05-13 dissolve 后归入 pilot；参 `docs/PROJECT_OVERVIEW.md` §6）；这些不构成 v2 触发条件。**v2 触发条件**：atom id 改名 / atom 增删 / parent 重挂 / phase 重分。
