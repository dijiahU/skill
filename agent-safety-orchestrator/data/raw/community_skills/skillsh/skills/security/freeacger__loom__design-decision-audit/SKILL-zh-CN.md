---
name: design-decision-audit
description: "在实现前审计设计文档（design document），找出缺失决策、兼容性风险、发布缺口与可观测性遗漏。当用户要求评审（review）设计稿、架构提案、面向实现的设计（implementation-facing design）、计划，或其他设计相关 Markdown 文档，并希望检查完整性、迁移策略、回滚、数据处理或建议补充内容，而不是直接改文档时使用。像 `review <file>.md`、`audit <file>.md` 这种简短请求，只要目标看起来像设计、计划、架构、提案或决策文档，也要触发。"
---

# 设计决策审计 (Design Decision Audit)

## 概览 (Overview)

这个技能用于在实现前审计一份设计文档。
它的职责是找出缺失或薄弱的设计决策，解释风险，并提出有针对性的补充内容。

除非用户在后续步骤明确要求，否则本技能**不直接修改**设计文档。

## 输入 (Inputs)

必需输入：

- 设计文档路径
- 设计文档内容
- 或两者兼有

可选输入：

- 其他上下文路径，例如相关设计文档、实现计划、需求说明

## 语言策略 (Language Strategy)

审计输出语言与用户指令语言保持一致。

优先级如下：

1. 用户显式要求的输出语言
2. 当前用户指令的主导自然语言
3. 同一任务里最近用户指令的主导自然语言
4. 如果信号弱或含糊，则使用 English

规则：

- 聊天回复与保存的报告文件使用同一种语言
- 小节标题翻译成选定输出语言
- 文件路径、代码标识符和字面量配置键保持不变
- 除非用户明确要求双语输出，否则不要混用语言

默认标题示例：

- `Executive Summary`
- `Triggered Modules`
- `Findings`
- `Suggested Additions`
- `Open Questions`
- `Report Path`

如果输出为中文，这些标题应翻译，但逻辑结构必须保持不变。

## 最小提示处理 (Minimal Prompt Handling)

不要要求用户显式把审计范围说得很完整。

如果用户只给出很短的指令，例如：

- `review <file>.md`
- `audit <file>.md`
- `check <file>.md`

只要目标看起来像以下文档之一，就推断为完整的设计决策审计（design-decision audit）：

- 设计文档（design doc）
- 架构提案（architecture proposal）
- 实现计划（implementation plan）
- 带检查清单（checklist）的评审文档（review doc）
- 提案 / 决策记录（proposal / decision record）

强信号包括：

- 文件名里有 `design`、`review`、`plan`、`proposal`、`architecture`、`decision`
- 仓库路径位于 `docs/`、`design-docs/`、`exec-plans/`、`proposals/`
- 文档内容讨论发布切换（rollout）、模式（schema）、兼容性（compatibility）、迁移（migration）、状态（states）、作业（jobs）、可观测性（observability）

如果用户只给了一个 Markdown 文件，但文档类型仍不清楚：

- 先打开文件
- 如果它读起来像设计、计划或架构文档，就直接审计
- 只有在文件明显不是设计相关文档，且误用本技能风险很大时，才提一个澄清问题

## 上下文策略 (Context Strategy)

在形成结论前，始终先读目标设计文档。

如果用户提供了额外文档路径，只要它们影响兼容性（compatibility）、迁移（migration）或设计意图（design intent），就要一起读。

如果用户显式限制了审计范围，要优先遵守，而不是默认继承仓库环境。例如：

- “Treat this as a standalone doc”
- “Do not use the current repo rules”
- “Use only the checklist I provided”

当用户显式缩小规则来源时：

- 只使用用户点名的文件与指令
- 不要因为仓库里还有别的标准就把它们一并继承
- 除非用户要求保存报告，否则不要根据当前仓库擅自推断报告目录

如果文档显式标为 draft / WIP / incomplete：

- 在 `Executive Summary` 中注明草稿状态
- 所有 `[GAP]` 发现降一级优先级（`P1 → P2`、`P2 → P3`）
- 被降级的缺口类发现项（gap finding）前加 `[DRAFT]`
- `[RISK]` 与 `[ASSUME]` 不降级，因为错误决策即使在草稿里仍然是错误的

如果用户没有覆盖范围，且仓库中存在项目标准文件，则应继承它们，例如：

- `AGENTS.md`
- `CONTRIBUTING.md`
- `docs/design-docs/*checklist*.md`
- 其他用户显式引用的评审标准（review standard）或设计模板（design template）

规则优先级：

1. 当前任务里的显式用户指令
2. 用户显式提供的检查清单（checklist）或标准文件
3. 仓库级评审约定（review contract），例如 `AGENTS.md` / `CONTRIBUTING.md`
4. 明显属于设计评审的仓库检查清单 / 模板
5. 本技能的默认规则

## 核心目标 (Core Goal)

产出一份结构化审计，回答三个问题：

1. 哪些重要设计决策已经明确？
2. 哪些重要设计决策缺失、薄弱或相互矛盾？
3. 应具体补充哪些内容，才能让设计可审阅、实现更安全？

## 默认审计范围 (Default Review Scope)

如果仓库没有定义更严格的评审范围（review scope），则默认审计以下维度：

- 正确性与项目标准
- 性能瓶颈
- KISS 与 DRY
- 可观测性：日志（logs）、指标（metrics）、告警（alerts）
- 幂等性与数据一致性

然后再按以下检查清单（checklist）审计：

- 迁移与切换（Migration and cutover）
- 数据处理（Data handling）
- 模式与存储（Schema and storage）
- 向后兼容性（Backward compatibility）
- 可观测性（Observability）

只有当设计真正触发时，才附加条件模块。

## 默认条件模块 (Default Conditional Modules)

如果仓库已有检查清单（checklist），以仓库检查清单为准；否则使用以下模块触发规则。

只有当设计清晰命中某类信号时才触发相应模块。不要把每个模块都硬套进每次审计。

| 模块（Module） | 触发信号（Trigger signals） |
|--------|----------------|
| Semi-structured payloads | JSON 字段、动态列、灵活 schema、payload validation、可扩展属性、`interface{}` / `any` 类型存储 |
| Performance and indexing | 查询模式、索引设计、分页、批量读写、热路径延迟、大表扫描 |
| State machine or orchestration | 状态迁移、state enum、workflow steps、job scheduling、retry logic、FSM 图 |
| Concurrency and locking | mutex、row-level lock、optimistic lock、并发写入、race condition 缓解、distributed lock |
| Async jobs and failure isolation | 后台任务、队列、workers、dead-letter queue、retry with backoff、at-least-once delivery |
| Human review | 手工审批、升级路径、review SLA、operator action |
| Audit and compliance | 审计日志、PII 处理、数据保留、GDPR/CCPA、监管要求、不可变记录 |
| Scan and alert design | 定时扫描、异常检测、告警阈值、on-call 路由、runbook |

## 默认发现契约 (Default Finding Contract)

如果仓库定义了发现项格式（finding format）、优先级方案（priority scheme）或评审约定（review contract），优先遵循仓库规则；否则使用以下默认规则。

### 发现项标准 (Findings Standard)

规则：

- 每条发现项（finding）必须有线程内唯一 ID
- 默认格式：`CR01 [P1] [GAP]`
- 按优先级从高到低排序
- `P0` 与 `P1` 默认视为 merge-blocking
- 不允许只有结论、没有论证的发现项
- 如果存在多条发现项，使用平铺 bullet list，并在每条上保留完整前缀
- 如果没有发现项，使用已验证清单（Verified Checklist）格式，而不是一句 `No findings identified.`

默认优先级：

- `P0`：合并或上线**必然**导致数据损坏、服务不可用、安全漏洞，或完全没有回滚路径
- `P1`：有真实伤害风险，或设计缺口已经足以阻止实现安全推进
- `P2`：会显著影响正确性或运维质量，但不太可能立刻出事故
- `P3`：真实但较轻的改进项，不构成生产风险

发现项类型标签，每条都必须带一个：

- `[GAP]`：文档里缺少一个必要决策
- `[RISK]`：已有决策，但它错误、矛盾或危险地不完整
- `[ASSUME]`：设计隐含了一个从未显式做出的决策，需要把这个隐藏假设指出来

每条发现项解释时遵循这个顺序：

1. 问题是什么
2. 当前设计如何触发它
3. 一个具体例子
4. 为什么它对这次变更重要

必要时，用“预期行为 vs 当前行为”来增强说明力。

## 输出校准 (Output Calibration)

修复建议（remediation）的详略程度要随文档复杂度调整。

对于很短或很简单的文档（例如低于 300 词、触发模块少于 3 个、或全部发现项都是 `P3`）：

- 把三选项表收缩成“一个推荐方案 + 一句取舍说明（trade-off）”
- 不要抑制发现项，只压缩修复说明文字

对于复杂文档（例如触发模块 ≥ 5、存在任意 `P0`、或发现项总数 > 6）：

- 对每个 `P0` 到 `P2` 发现项使用完整的三选项表
- 不要省略方案分析（option analysis）

如果复杂度不清楚，默认用完整格式。

## 输出格式 (Output Format)

聊天回复始终使用以下结构：

```markdown
# Design Audit
## Executive Summary
## Triggered Modules
## Findings
## Suggested Additions
## Open Questions
## Report Path
```

各小节（section）规则：

- `Executive Summary`：2 到 5 句，概述整体审计姿态
- `Triggered Modules`：只列真正触发的模块；如果没有，写 `- None`
- `Findings`：列出 `CRXX [P#]` 发现项，或使用 Verified Checklist
- `Suggested Additions`：按小节标题（section heading）或主题（topic）分组
- `Open Questions`：只保留真正阻碍可靠审计的问题
- `Report Path`：必须始终存在
- 如果写了报告文件，填入真实保存路径
- 如果只是聊天输出且未要求文件，则写 `- Chat only (not requested)`

输出语言可变，但逻辑结构不能变。

对于每个适用发现项，内部还要有这些子结构：

- 发现项陈述（finding statement，带 `[GAP]` / `[RISK]` / `[ASSUME]`）
- `Options`
- `Recommended Option`
- `Why Not Others`

能用 Markdown 表格表达 `Options` 时，优先用表格。

`Suggested Additions` 必须是**可直接复制进文档的句子**，而不是提醒事项。

## 报告文件 (Report File)

只有在以下情况之一成立时才写报告文件：

- 用户显式要求保存报告
- 仓库存在明显的既有报告目录，且任务语义暗示应持久化

路径优先级：

1. 用户显式指定路径
2. 使用仓库既有报告目录，例如 `docs/reports/`
3. 如果明显需要保存但无法推断路径，就问用户
4. 否则只在聊天里输出

如果写报告文件：

- 使用仓库时区下的当前本地日期
- 尽量从设计文档文件名派生 `<topic>`
- 若无法派生，则使用稳定短名，例如 `design-audit`
- 文件内 section 与聊天输出保持一致

绝不能在文件没有真的写出时声称某个报告路径（report path）。

## 工作流 (Workflow)

### 阶段 A：上下文准备 (Phase A: Context Preparation)

目标：构建完整上下文包，并完成默认检查清单审计。

1. 读取设计文档
2. 根据用户指令确定输出语言
3. 读取相关仓库标准文件（repo standard files）
4. 读取用户提供的额外上下文文件
5. 判断用户是否显式限制为独立模式（standalone mode）或只用点名文件
6. 按优先级解析评审约定（review contract）、发现项格式（finding format）、检查清单（checklist）和报告路径（report path）约定
7. 判断哪些条件模块被触发
8. 先跑默认检查清单审计，记录初步发现项（preliminary findings）
9. 组装结构化上下文包（context package），供 Phase B 使用

### 阶段 B：并行模块审计 (Phase B: Parallel Module Audit)

目标：对每个触发模块使用专用子智能体（subagent）并行审计。

当**没有任何模块触发**时：

- 整个 Phase B 跳过
- 只使用阶段 A 的初步发现项

当**存在一个或多个触发模块**时：

10. 为每个触发模块启动一个并行 Sonnet 子智能体（subagent）：
    - 读取 `skills/design-decision-audit/agents/module-auditor.md`
    - 填入：
      - `{{MODULE_NAME}}`
      - `{{TRIGGER_SIGNALS}}`
      - `{{DESIGN_DOC}}`
      - `{{REPO_STANDARDS}}`
      - `{{REVIEW_CONTRACT_SECTION}}`
    - 每个子智能体独立运行，不共享状态
11. 收集全部子智能体发现项

**回退方案：** 如果子智能体失败或超时，主智能体（main agent）用同样 rubric 内联审计该模块。

### 阶段 C：综合与产出 (Phase C: Synthesis)

目标：合并、去重、排序并格式化所有发现项。

12. 合并阶段 A 和阶段 B 的发现项
13. 按根因（root cause）与位置（location）做去重；重合但不完全相同的发现项要互相交叉引用
14. 最终按优先级编号为 `CR01`、`CR02` ...
15. 如果发现项文本过长，保留全部 `P0/P1` 细节，压缩 `P2/P3`
16. 对每个 `P0` 到 `P2` 发现项生成 3 个修复选项，并推荐最佳方案
17. 基于推荐方案写出 `Suggested Additions`
18. 如果文档是 draft/WIP，对 `[GAP]` 发现项做优先级下调和 `[DRAFT]` 前缀处理
19. 按六段结构组装最终输出
20. 如果任务要求保存，则写报告文件；如果路径不明，问用户
21. 返回结构化审计结果，并在所选语言中给出 `Report Path`

## 边界 (Boundaries)

应该做：

- 审计设计文档
- 指出缺失或薄弱决策
- 给出具体补充内容
- 对重要发现项比较修复方案并推荐最佳选项
- 在任务要求或仓库约定存在时保存报告文件
- 显式说明触发了哪些检查清单范围（checklist scope）
- 让结果不需要额外解释也可被人类审阅

不应该做：

- 直接编辑设计文档
- 在用户没要求时生成 implementation plan
- 扩展成 code review
- 在明知缺失信息本身就是设计 gap 的情况下问多余问题
- 把结构化审计压成随意 prose
- 省略 `Report Path` 或 `Triggered Modules`

## 升级提问规则 (Escalation Rules)

只有在以下情况才问一个简短阻塞问题：

- 目标设计文档无法识别
- 仓库里有多个候选文档，且正确目标不明确
- 缺失某个上下文文件会大概率导致错误结论
- 多个同级标准冲突，且选择不同会改变审计结论
- 任务要求保存报告，但你无法从用户请求或仓库约定中推断路径

其他情况继续审计，并把不确定性写进 `Open Questions`。

## 质量门 (Quality Bar)

结束前确认：

- 回应含有 6 个必需 section
- `Triggered Modules` 是显式的，即使为空
- 发现项遵循仓库格式；如无仓库格式，则使用 `CRXX [P#] [TYPE]`
- 每条发现项都带 `[GAP]`、`[RISK]` 或 `[ASSUME]`
- 没有结论式空发现项；每条都说明 what / how / example / why
- 每条 `P0` 到 `P2` 发现项都有 options、recommendation 和简短的 rejection reasons
- `Suggested Additions` 反映的是推荐方案，而不是把所有选项再抄一遍
- 如果没有发现项，使用 Verified Checklist 格式
- 如果文档是 draft/WIP，`[GAP]` 发现项已降级并带 `[DRAFT]`
- 聊天输出与保存报告语言一致
- 建议内容是 copy-ready 的
- 显式用户覆盖优先于仓库环境规则
- 如果任务要求保存，要么文件真的写出来了，要么路径已被显式确认
