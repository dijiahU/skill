# Safety Orchestrator Skill — 项目总览

本文档基于 `SafetyRouter.pdf`（项目书）整理，用于跟踪当前实现进度。
任何与项目书冲突的描述以项目书为准；本文随实现演进而更新。

首次了解整个仓库请从根目录 [`README.md`](../README.md) 开始；本文保留完整的实施记录、实验结果与设计决策。

> **结构约定**：§2 系统架构 + §3 预期产出 是稳定的项目愿景；§4 是**唯一实施模块**，按工作顺序线性展开（数据收集 → 漏斗预筛 → 词表 → LLM 审计 → 词表迭代 → SKILL.md 包装 → pilot）。**项目 training-free**——只交付一个 Claude Code skill 包，不训练任何 ML 模型。§5 是当前下一步（pilot 验证），§6 是仓库布局。

## 2. 系统架构

```
                 ┌────────────────────────────────────┐
任务执行阶段 ─→  │           Safety Router             │
（输入理解 /     │  (轻量、低延迟，按阶段-技能映射决策)  │
 规划决策 /      │  ↑ 阅读 Atomic Safety Skill 描述文件  │
 工具调用 /      └───────────────┬────────────────────┘
 输出生成）                      │ 路由
                                 ▼
                  ┌─────────────────────────────────────┐
                  │      Atomic Safety Skill 库         │
                  │  ┌──────────┬──────────┬─────────┐  │
                  │  │ 意图歧义  │ 参数安全 │  ……      │  │
                  │  │ 检测      │ 检查     │          │  │
                  │  └──────────┴──────────┴─────────┘  │
                  │  ┌────────────────────────────────┐  │
                  │  │ escalate-to-human-sentinel     │  │
                  │  │ archetype (最高优先级)          │  │
                  │  │  → pause + HITL (training-free) │  │
                  │  └────────────────────────────────┘  │
                  └─────────────────────────────────────┘
```

### 2.1 Atomic Safety Skill 库

对现有各类安全能力进行拆解与标准化，形成可复用的原子能力单元。
建设流程：

1. 收集公开 skill（5 类来源，详见 [§4.1](#41-数据收集项目书-11)）
2. 三层预筛漏斗剪枝至 LLM 可负担的规模（[§4.2](#42-三层预筛漏斗10223--1390我们引入)）
3. 起草受控词表（**v1 freeze = 95 个原子**；演化路径 v0.3 95 → v0.6 115 → v0.7 98 → v1 95；[§4.3](#43-原子能力词表-v03我们引入-为-llm-审计提供受控标签集)）
4. LLM 审计 + 原子抽取（[§4.4](#44-llm-审计--原子抽取项目书-12--13)）
5. 语义对齐 / 词表迭代 → v1 ([§4.5](#45-词表迭代-v03--v1项目书-14))
6. 每个原子落地为 SKILL.md 包（[§4.6](#46-原子-skillmd-包装-项目产出-2)）

### 2.2 Safety Router

**架构定位**：Router **不是独立程序 / middleware**，而是一份 **meta-skill SKILL.md**——agent host 的主 LLM 读这份 meta-skill 就成了 Router 本身。详见 [SAFETY_ATOMIC_CAPABILITIES.md §11](SAFETY_ATOMIC_CAPABILITIES.md#11-router-架构定位meta-skill-路径)。

- meta-skill SKILL.md 内含**阶段-技能映射表**（自然语言形式）
- agent 在执行任务时按 meta-skill 走：判断当前阶段（输入理解 / 规划决策 /
  工具调用 / 输出生成）→ 调用映射表里对应的原子技能进行检查与约束
- atom 描述文件预加载进 agent 的 system context，路由决策不额外调外部 LLM
- 路由到 `escalate-to-human-sentinel` archetype 时，agent 暂停自动化、向人类发送确认请求、等待反馈
- **延迟权衡**：相比传统 middleware，meta-skill 模型每 phase 边界 ~1-2s（vs 200-500ms），换来部署轻量 + host 兼容；详见 [SAFETY_ATOMIC_CAPABILITIES.md §11.3](SAFETY_ATOMIC_CAPABILITIES.md#113-延迟--成本权衡vs-独立-middleware-router)

## 3. 预期产出

**唯一交付物：Safety Orchestrator Skill 包**（training-free）。**18 个出货文件**（参 [`agent-safety-orchestrator/`](../agent-safety-orchestrator/)）= 1 Router meta-skill SKILL.md + 14 archetype reference docs + 1 hook config（8 matcher 脚本 + 1 lib + `hooks/hooks.json`）+ 2 helper（`cache_snapshot.py` + `health_status.py`）。**v1.3 起真层级**：唯一 top-level skill 是 `safety-router-skill`，14 个 archetype 改挂在它的 `references/archetypes/*.md`（Router 路由后模型 `Read` 加载，不再是独立 skill）——保证 router-first + session-start 只 1 条 description 进 context。**v1.1 起已打包为标准 Claude Code plugin**（`.claude-plugin/{plugin.json,marketplace.json}`，`/plugin install` 一键装）。

词表层 = v1 freeze 95 atoms / 19 archetypes / 5 phases + v1.1 部署元数据，详 [SAFETY_ATOMIC_CAPABILITIES.md §10](SAFETY_ATOMIC_CAPABILITIES.md#10-包装标准v05enforcement_mode--archetype-as-skill-双维度) 包装规范 + §12 部署元数据。HITL 通道通过 `escalate-to-human-sentinel` archetype（4 atoms）确定性触发，无 ML。

---

## 4. 实施进度 — Safety Orchestrator Skill 包构建（进行中）

> **唯一实施模块**。原"模块 2 Sentinel 训练" + "模块 3 Router runtime" 已分别 dissolve；本节是项目所有实质性实施工作。

### 4.0 进度概览

| 子任务 | 状态 | 详见 |
| --- | --- | --- |
| 4.1 数据收集 | ✅ 完成（2026-05-08）| [§4.1](#41-数据收集项目书-11) |
| 4.2 三层预筛漏斗 | ✅ 完成（2026-05-08）| [§4.2](#42-三层预筛漏斗10223--1390我们引入) |
| 4.3 原子能力词表 v0.3 | ✅ 接受用作审计输入（2026-05-09）| [§4.3](#43-原子能力词表-v03我们引入-为-llm-审计提供受控标签集) |
| 4.4 LLM 审计 + 原子抽取 | ✅ 完成（2026-05-09，DeepSeek，$2.51）| [§4.4](#44-llm-审计--原子抽取项目书-12--13) |
| 4.5 人工 review v0.3 词表（基于审计实证）→ freeze v1 + v1.1 部署元数据 | ✅ 完成（2026-05-11 v1；2026-05-12 v1.1 加 `requires_network` / `fail_policy` / 2 helper）| [§4.5](#45-人工-review-原子词表对照-llm-审计实证--freeze-v1项目书-14) |
| 4.6 原子 SKILL.md 包装 | ✅ 完成（2026-05-12，`agent-safety-orchestrator/`，18 文件 / ~3300 行；pilot 验证 + 精修挪到 §4.7）| [§4.6](#46-原子-skillmd-包装-项目产出-2) |
| 4.7 Pilot 验证（隔离环境 `pilot/`，podman rootless）| 🟡 进行中（2026-05-31）—— **4.7.1 ✅ 全部完成**（bring-up 7 步全过；end-to-end block 用 `detect-credential-in-input` 在 UserPromptSubmit 阶段拦下 dummy AWS key prompt，BUNDLE-only 归因）；**归因仪表盘已补齐**（`verdict-log.jsonl` bundle 决策账本 + transcript 持久化 + Claude Code pin 2.1.158）；4.7.2 数据采集 / 4.7.3 ⚪ | [§4.7](#47-pilot-验证当前主线) |

---

### 4.1 数据收集（项目书 1.1）

**状态：✅ 完成**（2026-05-08）。共抓取 **10223 条**候选：4798 条 SKILL.md skill + 5425 条 MCP server + 11 份 reference 文档。

#### 4.1.1 来源边界判定规则

项目书 §1 列了 5 类来源，但它们并不完全互斥（一个 GitHub 仓库可能既是"官方"也是"安全专项"）。按以下两个维度同时分类：

**(A) 制品类型**（决定蒸馏 pipeline 分支）：

| 制品类型 | 落盘根目录 | 蒸馏路径 | 来自项目书来源 |
| --- | --- | --- | --- |
| SKILL.md skill | `data/raw/{official,community}_skills/` | 读 markdown 正文 → 拆原子能力 | 来源 1, 2 |
| MCP server 元数据 | `data/raw/mcp_servers/` | 读 `metadata.json` + tools 列表 + 访问范围 → 拆原子能力 | 来源 3 |
| Taxonomy / 实践规范文档 | `data/raw/references/` | 读文档 → 提取攻击面 / 阶段定义，用于建 taxonomy 而不是直接进原子库 | 来源 5 |

**(B) 收录路径**（决定 fetcher 风格）：
- 上游官方仓库（hand-picked，commit 钉死）
- 第三方聚合 / 注册表（API + 关键词检索 + 内容过滤）
- 单一 GitHub 仓库（按需点对点抓）

**关于来源 4 的归并**：项目书例子（prompt-security/clawsec、UseAI-pro/openclaw-skills-security、slowmist/openclaw-security-practice-guide）经验证后分别属于以上两类：前两者本质是 SKILL.md 套件，已被来源 2 的 aggregator 部分捕获；slowmist 那种 practice-guide 本质是 taxonomy reference 文档而非 skill，应归入来源 5。**因此来源 4 不再独立存在**，相关条目按制品类型分别走来源 1/2/5。

#### 4.1.2 来源矩阵

| # | 来源类别 | 项目书示例 | 当前覆盖 |
| --- | --- | --- | --- |
| 1 | 官方 skill 仓库 | OpenAI、Anthropic、OpenClaw/ClawHub | ✅ OpenAI（3）；✅ Anthropic（确认 `anthropics/skills` 主仓不含独立 security 类 skill）；✅ ClawHub（598） |
| 2 | 综合 skill 聚合站 | Official Agent Skills Directory；VoltAgent/awesome-agent-skills | ✅ skills.sh（2901）；✅ skillsdirectory.com（1271）；✅ dmgrok/agent_skills_directory（25，仅 native security 子集） |
| 3 | MCP 扫描/审计工具与注册表 | modelcontextprotocol/registry；Smithery；Glama；MCP.so；PulseMCP | ✅ 5 个 registry 全部抓完：modelcontextprotocol-registry（763）；Smithery（352）；Glama（2366）；MCP.so（18，URL 预筛默认模式）；PulseMCP（1926） |
| ~~4~~ | ~~GitHub 安全专项项目~~ | ~~prompt-security/clawsec；UseAI-pro/openclaw-skills-security；slowmist/openclaw-security-practice-guide~~ | ⛔ **归并：** SKILL.md 套件部分由来源 2 覆盖；practice-guide 类移交来源 5。详见 §4.1.1 |
| 5 | 标准、博客、论文与 practice guide | OWASP Agentic Skills Top 10；Snyk ToxicSkills；MCP 安全研究 / 行业博客；slowmist 等 GitHub practice guide | ✅ 11 份精选 reference 落盘（共 5.7MB）：standard 5（OWASP 2、NIST 2、MITRE ATLAS）、spec 1（MCP best practices）、research 2（Anthropic RSP、Lakera prompt-injection）、practice-guide 3（slowmist、prompt-security、useai-pro）。**不进原子库**，仅供建 taxonomy 参考 |

#### 4.1.3 落盘清单

| 来源 | 路径 | Skill 数 |
| --- | --- | --- |
| OpenAI（official） | `data/raw/official_skills/openai/curated/security/` | 3 |
| ClawHub | `data/raw/community_skills/clawhub/skills/security/` | 598 |
| skills.sh | `data/raw/community_skills/skillsh/skills/security/` | 2901 |
| skillsdirectory.com | `data/raw/community_skills/skillsdirectory/skills/security/` | 1271 |
| dmgrok/agent_skills_directory | `data/raw/community_skills/agent-skills-directory/skills/security/` | 25 |
| modelcontextprotocol-registry（MCP server） | `data/raw/mcp_servers/modelcontextprotocol-registry/security/` | 763 |
| Smithery（MCP server） | `data/raw/mcp_servers/smithery/security/` | 352 |
| Glama（MCP server） | `data/raw/mcp_servers/glama/security/` | 2366 |
| MCP.so（MCP server） | `data/raw/mcp_servers/mcp-so/security/` | 18 |
| PulseMCP（MCP server） | `data/raw/mcp_servers/pulsemcp/security/` | 1926 |
| **合计 SKILL.md + MCP** | | **10223** |
| references（不进原子库） | `data/raw/references/<source>/security/` | 11 份文档 |

> 其中 SKILL.md 类（前 5 行）共 4798；MCP server 元数据（后 5 行）共 5425。两类后续蒸馏路径不同：前者按 SKILL.md 内容拆分原子能力；后者按 server 暴露的工具集合 + 访问范围识别原子能力。

数据存储约定参见 [docs/SKILL_STORAGE_LAYOUT.md](SKILL_STORAGE_LAYOUT.md).

---

### 4.2 三层预筛漏斗（10223 → 1390，我们引入）

**状态：✅ 完成**。10223 直接喂 LLM 成本不现实（粗算 Sonnet 数千 USD、Haiku 数百 USD）。三层漏斗按"从免费到便宜"剪枝，每层完成后看残量决定是否进下一层：

| 阶段 | 做法 | 实际收益 | 成本 | 状态 |
| --- | --- | --- | --- | --- |
| **Stage 1** 硬去重 | SKILL.md 正文 hash + MCP `name+description` hash；同指纹只留一份代表（按来源优先级 official > curated > 其他） | 砍 4.35% (skill, 210/4824) / 0.13% (mcp, 7/5425)；远低于预期 | 免费、确定性 | ✅ 完成（[reports/dedup_stage1_hash_2026-05-08.json](../reports/dedup_stage1_hash_2026-05-08.json)）|
| **Stage 2** 近似去重 + 规则过滤 | (1) skillsdirectory branding-only-match 过滤；(2) MCP 跨 registry 用 normalized GitHub repo URL 匹配；(3) MinHash/LSH 找近似 SKILL.md 副本（Jaccard ≥ 0.85，64 hashes / 16 bands × 4 rows）；(4) 短内容过滤（SKILL.md < 200 字符；MCP description+readme < 100 字符）| 砍 10.36% (skill, 478) / 27.7% (mcp, 1501)；总残量 10032 → **8053** | 免费、确定性 | ✅ 完成（[reports/dedup_stage2_filter_2026-05-08.json](../reports/dedup_stage2_filter_2026-05-08.json)）|
| **Stage 3** Embedding 相关性排序 | 智谱 `embedding-3`（2048 维）算每条 vector，跟 v2 的 20 个 archetype（[SAFETY_ATOMIC_ARCHETYPES.md](SAFETY_ATOMIC_ARCHETYPES.md)）算 cosine；选择规则 = per-anchor top-150 (cosine ≥ 0.55) ∪ 全局 max-cosine ≥ 0.65。脚本 [`scripts/dedup_stage3_embedding.py`](../scripts/dedup_stage3_embedding.py) | **残量 1390**（1046 skill + 344 mcp），从 8053 砍 82.7% | 智谱 API ~¥2.5 | ✅ 完成（[reports/dedup_stage3_embedding_2026-05-08.json](../reports/dedup_stage3_embedding_2026-05-08.json)）|

#### 4.2.1 Stage 2 结果分析

残量 8053（4136 skill + 3917 mcp）。各规则单独贡献：

- MCP `short-content` **1163** —— 最大单条增益。registry 里大量"占位"条目，描述+README 不到 100 字符，没有可供 LLM 蒸馏的实质内容
- MCP `mcp-repo-url-dedup` **338** —— 同一 GitHub 项目跨 3-4 家 registry 重复（top cluster 4 份）
- SKILL.md `branding-only-match` **246** —— skillsdirectory boilerplate 假阳性
- SKILL.md `minhash-near-dup` **206** —— 真近似副本，最大 cluster 25 份（同用户在 skillsdirectory 反复上传同一 skill 的变体）
- SKILL.md `short-content` 26

**关于 Stage 3 必要性**：残量 8053 仍超出"<3000 跳过 Stage 3"的阈值，因此 Stage 3 必做。

#### 4.2.2 Stage 3 首跑分析

**总览**：8051 候选（其中 2 条 MCP 因 metadata 为空被丢） → per-anchor 1390 ∪ global 209 → 残量 **1390**（去重后两条规则合一，global 209 全部已被 per-anchor 包含）。

**Per-anchor 分布**（按 kept 数量从大到小）：

| Anchor | kept | skill | mcp | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| detect-prompt-injection | 150 | 125 | 25 | 0.571 | 0.746 |
| scan-input-for-pii-and-secrets | 150 | 129 | 21 | 0.583 | 0.693 |
| threat-model-task | 150 | 142 | 8 | 0.590 | 0.751 |
| enforce-policy-as-code | 150 | 117 | 33 | 0.578 | 0.709 |
| detect-task-overreach | 150 | 139 | 11 | 0.572 | 0.663 |
| validate-tool-argument-safety | 150 | 145 | 5 | 0.603 | 0.682 |
| validate-agent-tool-trust | 150 | 112 | 38 | 0.589 | 0.668 |
| detect-supply-chain-risk | 150 | 128 | 22 | 0.607 | 0.734 |
| scan-code-for-vulnerabilities | 150 | 131 | 19 | 0.649 | 0.754 |
| detect-malicious-payload-in-tool-output | 150 | 96 | 54 | 0.581 | 0.652 |
| detect-data-exfiltration | 150 | 130 | 20 | 0.569 | 0.700 |
| audit-trail-recording | 150 | 59 | 91 | 0.578 | 0.735 |
| enforce-output-content-policy | 148 | 130 | 18 | 0.565 | 0.632 |
| constrain-workspace-boundary | 141 | 57 | 84 | 0.564 | 0.699 |
| escalate-to-human-sentinel | 137 | 105 | 32 | 0.562 | 0.658 |
| check-tool-permission-scope | 136 | 109 | 27 | 0.564 | 0.663 |
| incident-response-handler | 99 | 68 | 31 | 0.555 | 0.643 |
| redact-sensitive-output | 70 | 63 | 7 | 0.547 | 0.750 |
| enforce-rate-and-quota-limits | 23 | 17 | 6 | 0.514 | 0.705 |
| classify-input-intent-ambiguity | **2** | 2 | 0 | 0.460 | 0.609 |

**关键观察**（用户已审定，决定不再调整阈值；下面 5 条作为后续 1.4 语义对齐时的提醒留底）：

1. **`classify-input-intent-ambiguity` anchor 几乎死透**（仅 2 条命中 0.55 阈值，max=0.609）。v0.3 词表保留了该 archetype 下 3 个原子，1.4 阶段决定是否合并 / 删除（LLM 审计后续也确认这个 archetype 下的 `detect-destructive-action-keyword` 是 0-命中原子）
2. **MCP 占比偏低**（344 / 3917 = 8.8% vs skill 25.3%）。少数 MCP-heavy anchor（`audit-trail-recording`、`constrain-workspace-boundary`、`detect-malicious-payload-in-tool-output`）吸走了 MCP 候选名额；344 已经是合理浓度（MCP 总量本来就大量是占位条目）
3. **Global threshold τ=0.65 没起独立作用**（209 全部被 per-anchor 包含）。说明 per-anchor 选择规则已经足够；τ 可作为安全网保留
4. **Anchor min_threshold=0.55 是有效的"剪枝线"**：14 个 anchor 在这条线之上仍能装满 150 名额，4 个 anchor（`enforce-rate-and-quota-limits` / `classify-input-intent-ambiguity` / `redact-sensitive-output` / `incident-response-handler`）受这条线限制低于 150
5. **Score 分布偏低**：所有 anchor 的 max < 0.76；p99 普遍 < 0.61。说明 embedding-3 在中英混合 skill 文本上 cosine 偏保守，绝对值不能直接照搬其他 embedding 模型的经验阈值

#### 4.2.3 Stage 3 校准入口（保留供后续追溯）

manifest 的 `calibrationSamples` 区段为每个 anchor 提供 3 个采样桶（top30 + 0.65 附近 30 + [0.55, 0.65) 30）。如果后续发现某个 anchor 召回不够或 dead anchor 真的需要救，可回头读这个区段，用 `python scripts/dedup_stage3_embedding.py --reselect-only --global-threshold X --anchor-min-threshold Y` 不重调 API 直接重选（缓存 8071 条 vector 已在 `data/cache/embeddings/zhipu_embedding3.pkl`，~64MB）。

---

### 4.3 原子能力词表 v0.3（我们引入，为 LLM 审计提供受控标签集）

**状态：✅ 接受用作审计输入**（2026-05-09）。完整定义见 [docs/SAFETY_ATOMIC_CAPABILITIES.md](SAFETY_ATOMIC_CAPABILITIES.md).

| 维度 | 数值 / 内容 |
| --- | --- |
| 规模 | **95 个原子**（**v1 freeze**，v0.3 95 → v0.6 115 → v0.7 98 → v1 95 经"轻量化 LLM agent guardrail"判据精简），分布在 5 个 phase × **19 个** archetype 下 |
| 起草来源 | v2 archetypes（粗骨架）+ 11 份 references（OWASP LLM Top 10 / MITRE ATLAS / MCP best practices / Lakera / SlowMist / UseAI-pro / ClawSec）+ 项目书 §1.1 |
| 主审阅入口 | [§4 按 phase 组织](SAFETY_ATOMIC_CAPABILITIES.md#4-按-agent-执行阶段组织safety-router-查表视图主审阅入口)（input-understanding 13 / planning 10 / tool-invocation 49 / output-generation 11 / cross-cutting 12；v1 = 95）|
| 详细字段 | [§5 按 archetype 卡片](SAFETY_ATOMIC_CAPABILITIES.md#5-按-archetype-组织详细原子卡片对照参考)（每条原子含 definition / scope_in / scope_out / signal_phrases / related）|
| LLM 输出 schema | [§7](SAFETY_ATOMIC_CAPABILITIES.md#7-llm-输出-schema受控词表的使用契约) 定义 `primary_atoms` / `secondary_atoms` / `suggested_new_atoms` / `self_risk_flags` / `free_form_notes` 等字段 |
| SKILL.md 包装标准 | [§10](SAFETY_ATOMIC_CAPABILITIES.md#10-原子-skillmd-包装标准14-蒸馏期落地约定) 4 段固定结构 purpose / when_to_use / how_to_check / verdict_schema |
| Router 架构定位 | [§11](SAFETY_ATOMIC_CAPABILITIES.md#11-router-架构定位meta-skill-路径) meta-skill 路径，agent host LLM 即 Router |

**为什么不在 LLM 审计前做人工增删**：用户决定使用 v0.3 直接进 LLM 审计，依据实际审计输出的覆盖度分布、`suggested_new_atoms` 分布、`self_risk_flags` 分布等数据再决定 v1 怎么调。详见 §4.5。

---

### 4.4 LLM 审计 + 原子抽取（项目书 1.2 + 1.3）

**状态：✅ 完成**（2026-05-09）。1390 残量按 v0.3 词表打 `primary_atoms` / `secondary_atoms` 标签，单次 LLM pass 同时输出 `is_safety_relevant` / `self_risk_flags` / `suggested_new_atoms` / `free_form_notes`。

**配置**：
- 模型：DeepSeek `deepseek-chat`（V3.2，OpenAI-compatible API）
- 主脚本：[scripts/llm_audit_stage1_classify.py](../scripts/llm_audit_stage1_classify.py)
- 词表 loader：[scripts/_atomic_capabilities.py](../scripts/_atomic_capabilities.py)（解析 capabilities §5 卡片为 prompt-ready dict）
- API key：`.env` 文件（[scripts/_env.py](../scripts/_env.py) loader）
- Manifest：[reports/llm_audit_classify_2026-05-09.jsonl](../reports/llm_audit_classify_2026-05-09.jsonl) + 同名 `_cache/` 目录（per-record JSON，resume 友好）

**结果摘要**：

| 指标 | 数值 | 评估 |
| --- | --- | --- |
| 处理总数 | 1390 / 1390 | ✅ 全跑完 |
| 失败 | 0 | ✅ |
| 是 safety-relevant | 1211 (87%) | 合理 |
| 非 safety-relevant | 179 (13%) | Stage 3 假阳性，sample 验证 LLM 判得对 |
| skip_reason 分布 | 136 non-security / 25 placeholder-only / 18 boilerplate-only | |
| 空 primary_atoms | 0 | 词表覆盖度 100% |
| 0-命中 atoms | 1：`classify-input-intent-ambiguity/detect-destructive-action-keyword` | Stage 3 早就预言（dead anchor 下属）|
| Confidence 中位数 / 均值 | 0.75 / 0.795 | 标定合理 |
| 低 confidence (< 0.7) | 249 (17.9%) | spot-check 候选 |
| Schema 校验警告 | 45 (3.2%)，全部 atom_id 挂错 parent | 可一键修，不需要重审 |
| 共提出新原子建议 | 94 个 `suggested_new_atoms` | 但**全部各自只出现 1 次**（无共识 → v0.3 覆盖度高，无系统性 gap）|

**Token / 成本**：

| 指标 | 数值 |
| --- | ---: |
| 总输入 tokens | 24.4M |
| Prompt cache 命中率 | **92.8%** ← 在 1390 规模下 cache warm-up 后表现优秀 |
| 总输出 tokens | 405k |
| **总成本** | **$2.51**（远低于预估 $4-6）|

**Top 10 primary_atoms 命中分布**：

| 排名 | Atom | 命中数 |
| --- | --- | ---: |
| 1 | scan-code-for-vulnerabilities/run-sast-scan | 266 |
| 2 | detect-supply-chain-risk/check-package-cve | 202 |
| 3 | scan-code-for-vulnerabilities/detect-hardcoded-secret-in-code | 155 |
| 4 | detect-supply-chain-risk/check-package-typosquat | 101 |
| 5 | validate-tool-argument-safety/detect-shell-command-injection | 99 |
| 6 | threat-model-task/generate-stride-threat-model | 91 |
| 7 | enforce-policy-as-code/evaluate-opa-rego-rule | 90 |
| 8 | detect-prompt-injection/detect-direct-prompt-injection | 85 |
| 9 | audit-trail-recording/record-tool-invocation-trace | 79 |
| 10 | audit-trail-recording/record-decision-trace | 74 |

**Top 5 self_risk_flags 分布**：

| 标签 | 出现次数 |
| --- | ---: |
| requires-network-egress | 627 |
| executes-shell-on-install | 265 |
| stores-secrets-in-plaintext | 177 |
| executes-shell-commands | 79 |
| asks-for-broad-fs-write | 26 |

**covered_phases 分布**（多选）：

| Phase | 出现次数 |
| --- | ---: |
| tool-invocation | 953 |
| planning | 373 |
| output-generation | 308 |
| cross-cutting | 275 |
| input-understanding | 203 |

---

### 4.5 人工 review 原子词表（对照 LLM 审计实证）→ freeze v1（项目书 1.4）

**状态：✅ 完成**（2026-05-11 v1 freeze；2026-05-12 v1.1 加 `requires_network` / `fail_policy` / 2 helper）。

**这一步审的是词表本身的划分是否合理，不是审 LLM 判得准不准**。v0.3 的 95 个原子是 [§4.3](#43-原子能力词表-v03我们引入为-llm-审计提供受控标签集) 基于理论起草（v2 archetypes + 11 份 references）；LLM 审计 [§4.4](#44-llm-审计-原子抽取项目书-12-13) 把它套到 1,390 条真实候选上提供实证信号。**v0.6 → v0.7 → v1**（同一天连续 3 次迭代）：v0.6 先按 LLM 审计数据加 20 新原子 + 1 搬家 + 11 处 scope MERGE → 115；v0.7 用"轻量化 LLM agent guardrail"判据（运行时点 / 作用对象 / 现成实现 / 粒度适中）精筛掉 17 个不符合的原子（研究级 SMT、vapor-infra 信任评分、离线 SAST 分析、agent-as-output deliverable）+ 删整个 `threat-model-task` archetype → 98；最后下架 `validate-agent-tool-trust` 内 3 个 planning-阶段 A2A trust 原子（前瞻、无主流场景）→ **v1 freeze = 95**。词表演化路径：95 → 115 → 98 → 95。

#### 4.5.1 你要做的核心判断（针对每个 archetype × 原子）

| 决策类型 | 词表设计层面的问题 | 来自审计数据的信号 |
| --- | --- | --- |
| **保留** | 这个原子的 carving 经得起实证 | `primary_atoms` 命中数 ≥ 阈值（先用 5 试） |
| **删除** | 这个原子本来就不该单独存在 | 0 命中 / 极少命中 + 概念跟兄弟原子高度重叠 |
| **合并兄弟原子** | 两个或多个原子区分不出来 | sibling 原子频繁共现（同一 record 同时打两个）；或 LLM 反复在兄弟之间挂错 parent |
| **新增** | 词表漏了真实存在的能力类别 | `suggested_new_atoms` 按 `proposed_id` 聚类后的桶大小 ≥ 阈值 |
| **重写 scope_in / scope_out** | 原子定义边界写得不够清楚 | (a) 该原子的 wrong-parent 率高（atom_id 被反复挂到错的 archetype）；(b) 该原子上的 LLM confidence 中位数显著低于全局；(c) `free_form_notes` 反复说"勉强映射到 X" |

> 关键：**这 5 类决策都是 vocabulary-level 的判断**——你不需要也不应该去逐条检查"LLM 给某个 record 打的标签对不对"。LLM 标签的总体噪声水平在审计层已经控制得不错（0 失败、92.8% cache hit、median confidence 0.75），单条噪声对词表设计的影响可以忽略。

#### 4.5.2 自动化辅助（先跑，给用户做 §4.5.1 判断提供数据）

| 顺序 | 工作 | 调 LLM？ | 输出（针对 §4.5.1 的哪类决策）|
| --- | --- | --- | --- |
| 1 | **Cleanup pass** | ❌ 确定性 | 用 `atom_id → 正确 parent` 表批改 §4.4 的 43 条 wrong-parent + 5 条 no-slash。修完后 wrong-parent 率才能反映真实的"原子边界混淆"信号（vs 单纯 LLM 拼写错误）|
| 2 | **数据洞察脚本** `scripts/llm_audit_summary.py`（待写）| ❌ 纯统计 | 针对每个原子产出：① 命中数（→ 保留 / 删除）② sibling 共现矩阵（→ 合并）③ wrong-parent 率（→ 重写 scope）④ confidence 分布（→ 重写 scope）⑤ `suggested_new_atoms` 按 `proposed_id` 聚类（→ 新增）⑥ `free_form_notes` 关键词词频（→ 新增 / 重写）|

跑完 1 + 2 之后，用户就有了做 §4.5.1 5 类决策所需要的全部聚合数据。

#### 4.5.3 人工 review 步骤

1. 读 §4.5.2 的 summary 输出，**逐 archetype 对照 [SAFETY_ATOMIC_CAPABILITIES.md §5](SAFETY_ATOMIC_CAPABILITIES.md) 的原子定义看**
2. 对每个有疑问的原子（0-hit / 低命中 / 高 wrong-parent / 低 confidence 的）：**从它命中的 records 里抽 5-10 条快速扫一眼，确认这些 records 是不是真的属于一个内聚的能力类别**——这是验证 atom carving 的合理性，不是给 LLM 打分
3. 按 §4.5.1 的 5 类决策做判断，把改动 commit 到 [SAFETY_ATOMIC_CAPABILITIES.md](SAFETY_ATOMIC_CAPABILITIES.md)（增 / 删 / 合并 / 重写 scope_in/out / 重写 definition）+ 打 v1 changelog

#### 4.5.4 可选增量重审

v1 freeze 后，对以下两类**少数**候选做增量重审：
- v0.3 标空 `primary_atoms` 但 v1 加了对应原子的（94 条 suggested 中通过 review 的）
- v0.3 标了已合并 / 删除原子的（重新分配到 v1 下的原子）

预估 << 1,390，成本 << $1。**不需要重审整库**——绝大部分 LLM 审计输出在 v1 下仍有效。

---

### 4.6 双维度包装：hook config + archetype SKILL.md

**状态：✅ 完成**（2026-05-12；**2026-06-08 v1.3 真层级重构**）。Bundle 在 [`agent-safety-orchestrator/`](../agent-safety-orchestrator/)：18 个出货文件 / JSON 配置有效 / health banner 已跑通（93/95 atom active，2 个按预期 degraded/disabled）。8 个 matcher 脚本覆盖 60 hook + 21 hybrid fast-path = 81 个 atom；2 个 helper（cache_snapshot + health_status）实现完整；1 Router meta + 14 archetype doc 全部按 §10.3 spec 出齐。**v1.3 真层级**：14 archetype 从 `skills/<archetype>/SKILL.md` 移到 `skills/safety-router-skill/references/archetypes/<archetype>.md`，唯一 top-level skill = `safety-router-skill`，Router §3.2 路由表改为指示模型 `Read` 对应 archetype doc（不再让模型直接调 archetype skill）——保证 router-first + 被动 context 只剩 1 条 Router description。词表未动（仍 95 atoms），是纯 packaging/层级变化；两个 installer（Claude plugin + Codex adapter）都靠 `skills/*/` 枚举，自动适配新布局。**Hook script 内部 atom check 实现是 representative 而非 exhaustive**（如 `run-sast-scan` 是轻量 regex，production 应外接 semgrep；`check-package-cve` 通过 helper 真接 osv.dev/v1/querybatch 但 snapshot fallback 是 stub）——pilot 阶段精修在 §4.7.3。

按 [SAFETY_ATOMIC_CAPABILITIES.md §10](SAFETY_ATOMIC_CAPABILITIES.md#10-包装标准v05enforcement_mode--archetype-as-skill-双维度) 标准（v0.5 双维度模型）把 v1 词表分流：

**第一刀：enforcement_mode**（每个原子标 hook / skill / hybrid）
- 60 hook (63%) — 确定性，host 硬强制（regex / OS config / signature / log）
- 21 hybrid (22%) — hook fast path + LLM semantic fallback
- 14 skill (15%) — 需要 agent LLM 推理

**第二刀：按 archetype 把 skill / hybrid atoms 打成 SKILL.md**
- 5 个 pure-hook archetype（`check-tool-permission-scope` / `constrain-workspace-boundary` / `detect-malicious-payload-in-tool-output` / `audit-trail-recording` / `scan-code-for-vulnerabilities` — 最后一个 v0.7 精简后回归 pure-hook，matcher 限定 Write\|Edit\|MultiEdit）→ **不出 SKILL.md**，只进 hook config
- 0 个 pure-skill archetype（v0.7 `threat-model-task` 整个 archetype 下架）
- 14 个 mixed-enforce archetype → archetype doc（v1.3 起在 Router 的 `references/archetypes/*.md`，含 skill/hybrid tools）+ hook config（含 hook tools）

```
agent-safety-orchestrator/           ← Claude Code plugin（其自身即单-plugin marketplace）
├── .claude-plugin/
│   ├── plugin.json                  ← plugin manifest（name/version/license/keywords）
│   └── marketplace.json             ← 单-plugin marketplace（source: "./"）
├── hooks/                           ← ~81 个 hook 条目（60 pure-hook + 21 hybrid fast path）
│   ├── hooks.json                   ← 自动发现；命令路径用 ${CLAUDE_PLUGIN_ROOT}
│   └── scripts/                     ← 各 hook 调用的 matcher 脚本 + lib_common
├── skills/                          ← v1.3 真层级：唯一 1 个 top-level skill（自动发现）
│   └── safety-router-skill/           ← Router meta-skill = 唯一入口
│       ├── SKILL.md                   ← Router 正文（§3.2 路由表指示模型 Read 下面的 archetype doc）
│       └── references/
│           ├── archetypes/*.md        ← 14 个 archetype reference docs（Read-on-route，不再是独立 skill）
│           └── atoms-catalog.md       ← 95-atom 全表（on-demand）
├── helpers/                         ← cache_snapshot.py + health_status.py   ┐ 共享核心
├── atoms.json                       ←                                        ┘（双 host 共用）
├── install.sh                       ← 统一安装调度器（--host claude|codex|both|auto）
├── adapters/                        ← per-host adapter（复用上面的共享核心，零拷贝）
│   ├── claude/install.sh            ← Claude 手动/非-plugin 安装路径
│   └── codex/                       ← Codex hook 桥 codex_hook.py + hooks.json + config.backstop.toml + install.sh + README
├── LICENSE · README.md · CHANGELOG.md · .gitignore · .env.example · .github/workflows/validate.yml
```

> 注：`skills/` + `hooks/scripts/` + `helpers/` + `atoms.json` 是**唯一一份**核心，Claude Code plugin 与 Codex adapter 共用；Codex 安装时由 `adapters/codex/install.sh` 从仓库根**组装**进 `$CODEX_HOME`，源码不重复。

最终出货 = **18 个顶层文件**（1 hook config bundle + 14 SKILL.md + 1 Router meta-skill + **2 helper**：`cache-snapshot-helper` + `health-status-helper`，v1.1 加；详见 [SAFETY_ATOMIC_CAPABILITIES.md §12.4](SAFETY_ATOMIC_CAPABILITIES.md#124-两块共享-helper出货文件-16--18)）。v0.7 把 `threat-model-task` 整个 archetype 下架（STRIDE / attack-tree 是 agent-as-output deliverable，不是 guardrail），同时 `scan-code-for-vulnerabilities` 删 3 个高 FP SAST 后回归 pure-hook（matcher 限定 Write\|Edit\|MultiEdit）。pure-hook 共 5 个：`audit-trail-recording` / `check-tool-permission-scope` / `constrain-workspace-boundary` / `detect-malicious-payload-in-tool-output` / `scan-code-for-vulnerabilities`。**v1.1 部署元数据**：8 个 hook-network atom 加 `requires_network` + `fail_policy` 字段；2 个 helper 模块统一执行外部 IO + 降级逻辑（cache + bundled snapshot + health-ping + degraded banner）。

> **2026-06-04 — plugin 打包**：bundle 原地重构为标准 Claude Code plugin（`skill-packages/`→`skills/`、`hook-config/settings.json.snippet`→`hooks/hooks.json`、`${HOOK_BUNDLE_ROOT}`→`${CLAUDE_PLUGIN_ROOT}`，加 `.claude-plugin/{plugin.json,marketplace.json}` + MIT `LICENSE` + `.gitignore`）。用户一键装两层：`/plugin marketplace add <owner>/<repo>` → `/plugin install agent-safety-orchestrator@safety-tools`（marketplace 名 `safety-tools`；hook 路径用 `${CLAUDE_PLUGIN_ROOT}` 可重定位、随更新存活）。`install.sh` 保留为手动/非-plugin 路径。两个生成器输出路径 + pilot 脚本（`entrypoint.sh`/`run.sh`）已同步；`claude plugin validate` ✅；matcher 编译 + hook 拦截 + verdict-log + `helpers` import 重定位后冒烟全过。**已发布**至 https://github.com/tychenn/agent-safety-orchestrator （2026-06-05，commit `e63fce8`，marketplace 名 `safety-tools`）：占位符已填（tychen / tychenn）、营销版 README + CHANGELOG + 自包含 CI（`.github/workflows/validate.yml`）齐全；词表 vendored 为面向用户子集（`scripts/vendor_plugin_docs.py` 提取，1164 行）。**待验**：干净环境 `/plugin marketplace add tychenn/agent-safety-orchestrator` → `/plugin install ...@safety-tools` 确认 `source:"./"` 远端可解析。

> **2026-06-05 — Codex adapter（pilot，多 agent 适配 track）**：跨 agent 适配第一步，落在 [`adapters/codex/`](../agent-safety-orchestrator/adapters/codex/)（注：当日稍后并入发布仓库，见下条）。research 确认 **Codex / OpenClaw / Hermes Agent 三个目标都有 host 层 tool-call 拦截（PreToolUse 等价）+ 都吃 agentskills.io SKILL.md** → 结论是**不该砍 hook**，而是把"两层"在每个 host 重新表达（确定性是"执行点"的属性，不是 atom 的属性）。Codex adapter = 薄 I/O 桥 `codex_hook.py`（Codex 事件 ⇄ **复用 vendored matcher**（event-in/verdict-out）⇄ Codex `permissionDecision:deny`/exit2）+ Codex `hooks.json` + 15 SKILL.md 直接复用 + `config.backstop.toml`（sandbox+approval，补 Codex PreToolUse 对 unified_exec 流式 shell / WebSearch 的覆盖缺口）。规格用本机 codex-cli 0.64.0 + 官方文档双向核实；隔离 `CODEX_HOME` 端到端验证通过（`rm -rf` / `curl\|sh` 注入 / prompt 里 AWS key / apply_patch 藏密钥 全 deny）。**已知限制**：apply_patch→content 映射有损（path-traversal 弱，secret 检测仍有效）。**下一步建议**：vendored `core/` 已构成重复——先抽共享 `agent-safety-core` 库，再复制到 OpenClaw/Hermes（否则 4 份副本）。

> **2026-06-05 — Claude Code + Codex 统一（合并进发布仓库，单核心双 host）**：把 Codex adapter 从 monorepo 挪进**发布仓库** [`agent-safety-orchestrator/adapters/codex/`](../agent-safety-orchestrator/adapters/codex/)，并**删掉 vendored `core/` + `skills/`**（与插件根 byte-identical 重复，已 `diff -rq` 核实）。bridge 改为按优先级解析共享核心（`$SAFETY_ORCH_CORE` → 装机后的 `core/hooks/scripts` → 仓库内 `../../hooks/scripts`），插件与 Codex adapter 自此**共用同一份 matcher / helpers / atoms.json / skills**，零源码重复。新增**仓库根 `install.sh` 调度器**（`--host claude|codex|both|auto`，自动探测 `claude`/`codex` binary + `~/.claude`/`~/.codex`）；原 Claude 手动安装器挪到 [`adapters/claude/install.sh`](../agent-safety-orchestrator/adapters/claude/install.sh)（`BUNDLE_ROOT` 上移两级）。Codex 安装器改为**装机时从仓库根组装** `core/`（拷 `hooks/scripts`+`helpers`+`atoms.json`）——部署仍自包含，源码单副本。**验证**：dispatcher 把两个 host 装进隔离 home 全过（installed bridge 对 `rm -rf` / apply_patch 藏密钥 → deny + exit2；benign `ls` 放行；未装的 in-repo bridge 走 `../..` 解析也 deny）；Claude 手动装把 `${CLAUDE_PLUGIN_ROOT}` 渲成仓库根、health banner 93/95；三个 drift-guard `--check` + 结构计数（15 skill / 8 matcher / 95 atom）全绿；CI 加两步（adapter 编译 / TOML 解析 / `bash -n` 三个 installer + **"Dual-host proof"** 喂 `rm -rf` 断言 `deny`+`exit2`）。**取代上一条的"下一步建议"**——共享核心已落地，同仓库内直接共用，无需再抽独立 `agent-safety-core` 库。**下一步**：复制 adapter 模式到 OpenClaw / Hermes（各加一个 `adapters/<host>/` 薄桥即可，核心零拷贝）。**未推**：改动留在本地，等 maintainer 批准再 commit + push。

---

### 4.7 Pilot 验证（当前主线）

**状态：🟡 进行中**（4.7.1 ✅ 全部完成 2026-05-15；4.7.2 / 4.7.3 ⚪）。隔离测试环境 ship 在 [`pilot/`](../pilot/)（**podman rootless container**；不污染 host `~/.claude/`）。本节维护**让 pilot 真正跑起来 + 收集数据 + 反馈精修**的全套 todo。每项打 ⚪/🟡/✅ 跟 §4.0 一致。

> **Runtime 选定**：测试机 Rocky Linux 9.3 自带 podman 4.6.1 rootless（无需 sudo / 无 daemon），CLI 与 docker 兼容；`pilot/run.sh` 默认走 podman，docker 兼容路径保留但不验证。下文 §4.7.1 / §4.7.2 都以 podman 为准。
>
> **Pilot 网络 / 用户映射的两个坑（2026-05-14 修正）**：
> - **`--userns=keep-id:uid=1001,gid=1001`**：rootless podman 默认 host uid → 同号容器 uid 映射，但 node:20-slim base image 让 Dockerfile `useradd pilot` 拿到 uid 1001，而 host cty 是 1114——错位导致容器写 `.audit-bundle/atom-status.json` 报 EPERM。`run.sh` 显式映射 cty(1114) → pilot(1001) 后通。
> - **runtime `--network=host`**：默认开。host 有 `http_proxy=127.0.0.1:NNNN` 时，bridge 模式下容器内 127.0.0.1 ≠ host loopback，3 个 network atom (`check-package-cve` / `detect-hallucinated-package` / `check-package-recency-anomaly`) `[Errno 111] Connection refused` → 退到 fallback 路径。4.7.2 要验证 atom **设计本身**就必须让它跑 active 路径，所以 default host。设 `CONTAINER_NET_MODE=bridge` 可专门测 fallback。

> **归因仪表盘补齐（2026-05-31）**——4.7.2 的 Bundle-only / Built-in-only 归因此前无法落盘，本次补三处：
> - **`verdict-log.jsonl`（bundle hook 决策账本）**：[`lib_common.py`](../agent-safety-orchestrator/hooks/scripts/lib_common.py) 的 `aggregate()` 现在把每个 block/warn verdict 落盘，打 `source:"bundle"` + `phase` + `atom_id`。此前 block/warn 只走 stdout/stderr 当场回 Claude Code、不留痕，`decision-trace.jsonl` 只记 Stop 事件（名字误导）。⚠️ **它只记 hook（确定性）这一层，不是 bundle 全部**：bundle 另有 skill（model-invoked）层，skill 不发 exit-2 verdict，只在 `tool-invocations.jsonl` 留 `Skill` 调用（`detail` 含 skill 名）+ transcript 里的后续行为。**hook 和 skill 都是 bundle 的层，归因只有 bundle vs Claude Code 一条线。**
> - **归因模型（Router-gated，2026-05-31 与 maintainer 敲定）**：skill 层的归因闸门是 **meta safety skill `safety-router-skill` 调没调**；hook 层常开、永远算我们。按序判定 5 类：① **bundle-hook**（hook 有 verdict）= ✅ 我们 → ② 无 hook、调了 Router 且安全问题被拦下 = ✅ **bundle-skill** 我们 → ③ 无 hook、调了 Router 但没拦下 = ❌ **detection-miss** 我们失败 → ④ 无 hook、**没调 Router 且漏过** = 🟠 **routing-miss** 我们的弱点（Router description 没在该触发时吸引模型，单独记，喂 4.7.3.b 调 description）→ ⑤ 无 hook、没调 Router 但仍被拦 = ⚪ **built-in** Claude Code（不归我们）。核心规则：**hook 开火 OR (Router 进场且抓住) = 我们功劳**；Router 没进场却被拦 = built-in；Router 进场没抓住 = detection 失败；Router 压根没进场又漏 = routing 失败。`--vanilla`（无 hook 无 skill）从"每条 scenario 必跑"降为**校准 built-in 基线 + 检验 bundle 在场是否影响非路由轮行为**的 baseline 跑（category-5 的拦截应能在 vanilla 复现）。
> - **transcript 持久化**：`run.sh` 把容器 `~/.claude/projects/` 挂到 host `.audit-<mode>/transcript/`。容器 `--rm` 本会焚毁会话记录，而 transcript 是 model-invoked skill 调用链 + Claude Code 自拒的 ground truth。`tool-invocations.jsonl` 也补了 `detail` 字段（Skill→哪个 skill / Bash→command / Task→subagent_type），解决"看得见调了 skill 但看不出调哪个"。
> - **Claude Code pin 2.1.158**：[`Dockerfile`](../pilot/Dockerfile) 原 `npm install` 不锁版本（build 那天的 latest，已漂到旧的 2.1.140）。built-in safety 行为随版本变、而 A/B 衡量的就是 built-in 这条线 → 必须 pin 死可审计。`CLAUDE_CODE_VERSION=2.1.149 ./pilot/run.sh --rebuild` 可换版本。
> - **state-dir 统一**：`matcher_pretool_generic` / `matcher_stop` 此前硬编码 `~/.safety-orch` 不认 `SAFETY_ORCH_STATUS_DIR`（与 health_status 不一致）→ 已改走共享 `_state_dir()`，所有 audit 流落同一目录。

⚠️ 4.7.1 全部 ✅ 才能开始 4.7.2；4.7.2 完成后再做 4.7.3。每完成一项请 maintainer 在本表手动改 status。

#### 4.7.1 Pilot 环境 bring-up（前置）

每项需要在用户自己的 podman host 上手动验证；失败会暴露 Dockerfile / entrypoint / Claude Code 集成的 bug，所以这一阶段**有可能需要回头改 `pilot/` 文件**。

| Step | 任务 | 状态 | 失败的可能原因 / 修复入口 |
|---|---|---|---|
| 4.7.1.a | 测试机有可用 podman rootless | ✅ | 2026-05-13: Rocky Linux 9.3 自带 podman 4.6.1 rootless；rootless hello-world 跑通；无 sudo |
| 4.7.1.b | `./pilot/run.sh` 首次 build 通过 | ✅ | 2026-05-13: podman build 通过；image `localhost/safety-orch-pilot:latest` 602MB；含 Claude Code 2.1.140 (`/usr/local/bin/claude`) + python 3.11 + git 2.39。Build 必须用 `--network=host`（脚本已默认）解决容器内代理 / DNS / NOSPLIT 问题 |
| 4.7.1.c | 容器 entrypoint banner 三段都出现：`[BUNDLE MODE]` header + `Bundle health check` 段 + `Top-level skills: 1`（**v1.3 真层级**；旧记录是 v1.2 前的 `Linked skills: 15 directories`）+ `Hook entries: 8 total` + Claude Code 模型确认 | ✅ | 2026-05-14 完成：banner 输出 `Safety Orchestrator: 95/95 atoms active` + `✓ All atoms active.`。过程踩 3 个坑都已修在 [`pilot/run.sh`](../pilot/run.sh) / [`pilot/entrypoint.sh`](../pilot/entrypoint.sh)：(1) rootless podman uid 映射错位 → `--userns=keep-id:uid=1001,gid=1001`；(2) container 默认 bridge 网络 → host 代理 `127.0.0.1:NNNN` 不通 → 改 `--network=host`；(3) `check-package-cve` 缺 offline snapshot → entrypoint 自动 `python3 -m helpers.cache_snapshot refresh-db`；(4) VIRUSTOTAL_API_KEY 在 .env → run.sh `set -a; . .env; set +a` 自动 source |
| 4.7.1.d | `claude` 命令在容器内可用 + 完成 auth | ✅ | 2026-05-15 完成。挂载的 host credentials.json 没被容器 Claude Code 自动识别（版本错位 / format），fallback 到容器内 `claude login` 走 OAuth device-code 流：浏览器开 `claude.com/cai/oauth/authorize?...` → Anthropic 自家 `platform.claude.com/oauth/code/callback` 显示 code → 贴回 TUI。**关键坑**：OAuth state 是一次性的，URL 复制时终端换行容易漏字符——必须全选合一行；state 错就要重 `claude` 拿新 URL。容器 `~/.claude/` ro 挂载，token 只在本 session 内有效，下次进容器要重 OAuth |
| 4.7.1.e | Claude Code session 启动后列出 safety skill（**v1.3 真层级：应只见 `safety-router-skill` 一个**——14 archetype 不再是 top-level skill；追问 Router routes-to 才列 14 archetype。旧记录是 v1.2 前列 15 个的结果，需在 v1.3 下重跑） | ✅(待 v1.3 重跑) | 2026-05-15（v1.2 布局）完成。agent 列出 15 个 safety skill 全部正确（`classify-input-intent-ambiguity` / `detect-data-exfiltration` / `detect-prompt-injection` / `detect-supply-chain-risk` / `detect-task-overreach` / `enforce-output-content-policy` / `enforce-policy-as-code` / `enforce-rate-and-quota-limits` / `escalate-to-human-sentinel` / `incident-response-handler` / `redact-sensitive-output` / `safety-router-skill` / `scan-input-for-pii-and-secrets` / `validate-agent-tool-trust` / `validate-tool-argument-safety`）。注：agent 通过 session 启动时的 available-skills manifest 列出（filesystem 路径用 Bash 列因 EACCES 失败——见 4.7.1.f 修复）|
| 4.7.1.f | 触发 1 个 Bash tool 调用后，`pilot/.audit/tool-invocations.jsonl` 出现新条目 | ✅ | 2026-05-15 完成。`pilot/.audit-bundle/` 长出全套文件：`tool-invocations.jsonl`（15 行，3 个 session）+ `decision-trace.jsonl` + `session-counters.json` + `atom-status.json` + 历史 snapshot。3 种 tool（Bash / Read / Agent）都被 hook 捕获——8 个 matcher 全部正确 wire-up。**关键修复**：4.7.1.f 之前 Bash 报 EACCES（podman 单文件 bind mount 让 `/home/pilot/.claude/` 被自动建为 root-owned）；Dockerfile 提前 `mkdir -p /home/pilot/.claude /home/pilot/.cache /home/pilot/.config && chown -R pilot:pilot` 修掉 |
| 4.7.1.g | 单条对抗 prompt 端到端 block（bundle hook 真开火 + audit 留痕） | ✅ | 2026-05-15 完成。**关键发现 1**：原拟用 `ignore previous instructions` 这种经典 PI prompt 不 work——Claude sonnet 4.6 alignment 自己就拒，bundle 没机会开火（典型 BUILT-IN-only 归因）。**关键发现 2**：换成"为 CI 写 dummy AWS test fixture"这种 alignment-bypass 任务后，`UserPromptSubmit` hook 在 prompt 进 LLM 前就 block 了——`matcher_user_prompt.py` 调用 `detect-credential-in-input` atom 匹配出 `aws_access_key + aws_secret` 双模式，BUNDLE-only 归因干净。**Pilot 启示**：alignment 强度直接决定 bundle 边际价值；4.7.2 必须用 benchmark 而非 hand-crafted scenario（否则大多数 attack 会落到 BUILT-IN-only 类，bundle 净增价值被严重低估）|

#### 4.7.2 Pilot 数据采集（4.7.1 全 ✅ 后启动）

> ⚠️ **A/B 协议是 mandatory**：每条 scenario 必须在 **vanilla 模式**（`./pilot/run.sh --vanilla`，无 bundle）和 **bundle 模式**（`./pilot/run.sh`，full bundle）各跑一遍。不做对照单跑 bundle 无法证明 bundle 是否真起作用——Claude Code built-in safety 可能已经挡住了。详 [`pilot/scenarios.md`](../pilot/scenarios.md) §A/B 方法论。

| 任务 | 状态 | 产出（建议落地路径）|
|---|---|---|
| 4.7.2.a 写 scenario list（A/B 对照版）：5 happy-path + 10 attack + 3 边界路由 | ✅ | [`pilot/scenarios.md`](../pilot/scenarios.md)（2026-05-13，A/B 版）|
| 4.7.2.b 双模式跑全部场景：vanilla + bundle 各 18 scenarios，每 attack 至少 3 次 | ⚪ | audit 自动留在 `pilot/.audit-vanilla/` 和 `pilot/.audit-bundle/`（含 `verdict-log.jsonl` bundle 决策 + `transcript/` 会话记录）|
| 4.7.2.c 整理 Router-gated 归因表（bundle-hook / bundle-skill / detection-miss / routing-miss / built-in 5 类）+ 算汇总指标 | ⚪ | `pilot/atom-tpfp-2026-XX-XX.md`（含 Bundle 净增价值 / hook vs skill 层贡献 / detection-miss vs routing-miss / 误报率）。**数据源**：hook 层取 `.audit-bundle/verdict-log.jsonl`；skill 层的 Router/子 skill 调用取 `tool-invocations.jsonl` 的 `Skill`+`detail`；最终拦没拦下取 `transcript/`。归因 joiner 脚本待 4.7.2.b 跑出真实 transcript 后按其 JSONL 结构再写（判定逻辑见上方 §4.7 归因模型）|
| 4.7.2.d Archetype description 边界测试（易混 pair；只 bundle 模式）| ⚪ | `pilot/description-boundary-report.md` |
| 4.7.2.e 5 个 phase 边界延迟基准 + 模型对照（sonnet / opus / haiku）| ⚪ | `pilot/latency-bench.md`；模型对照看 bundle ROI 跟模型能力的关系 |

#### 4.7.3 反馈精修（4.7.2 后，可能多轮）

每轮：根据 4.7.2 数据改一组 atom / SKILL.md / hook script → 重 build pilot 容器 → 重跑 4.7.2 验证修复。

| 任务 | 状态 | 入口文件 |
|---|---|---|
| 4.7.3.a 列 representative → production 替换清单（按数据优先级排序）| ⚪ | matcher script regex → semgrep / 真 osv-export snapshot / LLM prompt templates |
| 4.7.3.b 修 description 边界错位的 archetype | ⚪ | [`scripts/gen_archetype_skill_md.py`](../scripts/gen_archetype_skill_md.py) `ARCHETYPE_META[...]["description"]`，改完跑 `--only <archetype-id>` 单独重生成 |
| 4.7.3.c 给 skill/hybrid atom 补 LLM prompt template | ⚪ | 14 个 archetype doc（`references/archetypes/*.md`）的 §4 Internal tools 段——目前只有 atom 描述，没有给 LLM 的具体 prompt 模板 |
| 4.7.3.d 重新跑 4.7.2 验证修复 | ⚪ | 回 4.7.2 重测；记录 round-by-round 数据收敛情况 |
| 4.7.3.e（预备选项，待用户拍板）**Router description 回填 archetype 触发摘要** | ⚪ 待定 | **触发条件**：若 4.7.2 数据显示 v1.3 真层级后 routing-miss 率显著高于层级化之前——根因假设是旧版 14 条 archetype description 常驻 context 起了 14 个"安全检查存在"的提示作用，层级化后只剩 1 条 Router description 把这提示价值丢了。**修法**：把 14 个 archetype 的触发场景**摘要回填进 Router 的 description / §3.2 表**（等于把提示价值搬进唯一入口，既保留提示又不破坏 router-first 层级），入口在 [`agent-safety-orchestrator/skills/safety-router-skill/SKILL.md`](../agent-safety-orchestrator/skills/safety-router-skill/SKILL.md) §3.2 + frontmatter description。**先看数据再决定做不做**——别在没有 routing-miss 升高证据前提前 over-engineer description。 |

> **Pilot 阶段结束的判据**：4.7.2.c 里 TP/FP 表全部 atom 的 FP rate < 10% 且没有 critical TN（漏检高 severity）。达到判据 → 项目 ready to ship。

---

## 5. 下一步（按优先级）

1. **§4.7 Pilot 验证**（**当前主线**）：跑 pilot 验证 bundle 在真实 Claude Code 里能用，收集 per-atom TP/FP 数据，反馈精修。**详细 todo 清单 + 各项状态见 [§4.7](#47-pilot-验证当前主线)**——分三个阶段（4.7.1 bring-up / 4.7.2 数据采集 / 4.7.3 反馈精修），每项打 ⚪🟡✅ markers 跟 §4.0 一致。**最早一步**是 `./pilot/run.sh`（podman rootless）build + run，看 4.7.1.c-g 是否都过；过不去 → 回头改 `pilot/` 的 Dockerfile / entrypoint。
2. **可选 §4.5 增量重审**（不阻塞主线）：用 v1 词表对 1390 record 子样本（如 200 条）重跑 LLM 审计，验证新词表对应的命中分布是否更干净（v0.3 时有 wrong-parent 错挂、suggested_new_atoms 多；v1 应该都收敛）

> 原"启动模块 2 Sentinel 数据准备 + 训练"已从本项目移除（项目 training-free，ML 模型训练归 separate downstream project）。如果你想推进 ML Sentinel，跟本 bundle 通过 `escalate-to-human-sentinel` archetype 的 atom 接口对接，不需要改本仓库。

## 6. 仓库布局

```
distill_skill/
├── README.md                                  # 整个 monorepo 的入口、快速开始与复现实验指南
├── data/raw/                                  # 上游原始一字不改
│   ├── official_skills/<provider>/<collection>/<category>/<skill>/
│   ├── community_skills/<marketplace>/<collection>/<category>/<skill>/
│   ├── mcp_servers/<registry>/<category>/<server>/   # MCP 服务器元数据
│   └── references/<source>/<category>/<doc>/         # taxonomy / 实践规范
├── data/cache/                                # 计算缓存（可重建）
│   └── embeddings/zhipu_embedding3.pkl        # Stage 3 vector cache (~64MB, 8071 条)
├── docs/                                      # 稳定的设计与参考文档
│   ├── PROJECT_OVERVIEW.md                    # 本文件
│   ├── SKILL_STORAGE_LAYOUT.md
│   ├── SAFETY_ATOMIC_ARCHETYPES.md            # Stage 3 anchor set（v2，已 freeze）
│   └── SAFETY_ATOMIC_CAPABILITIES.md          # 原子能力词表 v0.3
├── reports/                                   # 时序工作产出（蒸馏报告 / 审计快照）
│   ├── dedup_stage1_hash_2026-05-08.json
│   ├── dedup_stage2_filter_2026-05-08.json
│   ├── dedup_stage3_embedding_2026-05-08.json
│   ├── llm_audit_classify_2026-05-09.jsonl    # LLM 审计输出（每行 1 record）
│   ├── llm_audit_classify_2026-05-09_cache/   # per-record cache（resume 友好）
│   └── llm_audit_classify_2026-05-09_failures.jsonl
├── scripts/                                   # fetcher + 漏斗 + 审计
│   ├── fetch_openai_security_skills.py
│   ├── fetch_anthropic_security_skills.py
│   ├── fetch_clawhub_security_skills.py
│   ├── fetch_skillsh_security_skills.py
│   ├── fetch_skillsdirectory_security_skills.py
│   ├── fetch_agent_skills_directory_security_skills.py
│   ├── fetch_mcp_registry_security_servers.py # MCP source 3 fetchers ↓
│   ├── fetch_smithery_security_servers.py
│   ├── fetch_glama_security_servers.py
│   ├── fetch_mcpso_security_servers.py
│   ├── fetch_pulsemcp_security_servers.py
│   ├── fetch_security_references.py           # source 5 references (curated)
│   ├── dedup_stage1_hash.py                   # §4.2 三层漏斗 ↓
│   ├── dedup_stage2_filter.py
│   ├── dedup_stage3_embedding.py
│   ├── _archetypes.py                         # Stage 3 anchor config
│   ├── _atomic_capabilities.py                # §4.3 词表 loader
│   ├── llm_audit_stage1_classify.py           # §4.4 DeepSeek 审计
│   └── _env.py                                # .env 文件 loader（无依赖）
├── agent-safety-orchestrator/                 # 交付物：单核心 + Claude Code plugin + Codex adapter（布局详见 §4.6 树）
├── pilot/                                      # §4.7 隔离测试环境（podman rootless）
├── .env.example                               # 环境变量模板（commit 进 git）
├── .env                                       # 真值（gitignored）
└── .gitignore
```
