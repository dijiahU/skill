# 设计决策审计对外分享检查清单 (Design Decision Audit External Sharing Checklist)

范围：本清单只覆盖 `.agents/skills/design-decision-audit`。
本清单**不包含**：

- `.agents/skills/design-decision-audit-workspace`
- `docs/reports`
- 技能目录之外的其他仓库文件

## 当前结论 (Current Conclusion)

这个技能目录已经比较接近“可以对外分享”的状态，至少足够用于指令评审与技能设计讨论。

但它还**不是完全独立于仓库**的：

- 技能仍引用仓库约定，例如 `AGENTS.md`、`CONTRIBUTING.md`、`docs/design-docs/design-decision-checklist.md`、`docs/reports/`
- eval 集仍默认目标仓库中存在匹配的相对路径

## 已完成的脱敏 (Already Desensitized)

- 已移除本地绝对文件系统路径
  - 该目录内不再保留机器特定的绝对路径
- 已移除本地用户名暴露
- eval 文件引用改为仓库相对路径
  - 例如：
    - `.agents/skills/design-decision-audit/evals/files/...`
    - `AGENTS.md`
    - `docs/design-docs/design-decision-checklist.md`
- 该目录中未发现明显 secret pattern
  - 没有 API key
  - 没有 access token
  - 没有 private key
  - 没有类似密码赋值
- 该目录中未发现明显真实用户标识
  - 没有测试 UID
  - 没有订单 ID
  - 没有业务邮箱
  - 没有余额快照

## 有意保留的内容 (Intentionally Retained)

- 技能行为与 review contract 设计
  - triggered modules
  - findings format
  - report-path logic
  - standalone override rules
  - conflicting-checklist priority rules
- 仓库集成假设
  - `AGENTS.md`
  - `CONTRIBUTING.md`
  - `docs/design-docs/design-decision-checklist.md`
  - `docs/reports/`
- 保证审计质量所需的 eval 语义
  - migration strategy
  - rollback
  - backward compatibility
  - observability
  - state machine
  - concurrency
  - async job isolation
  - semi-structured payload
  - conflicting checklist selection
- eval 中面向项目的文件布局假设
  - `docs/exec-plans/completed/...`
  - `.agents/skills/design-decision-audit/evals/files/...`

## 剩余对外分享风险 (Residual External Sharing Risks)

- 仍然与项目耦合
  - 仓库外部读者可能没有这些被引用的文件或目录
- eval prompt 仍会暴露仓库结构
  - 虽然不再暴露本机路径，但仍暴露内部 repo layout
- 术语仍带领域特征
  - 部分示例文档使用了项目风格的字段名与 review 预期

## 对外分发前的建议 (Recommended Before External Distribution)

- 以下情况可以原样分享：
  - 接收方只需要技能逻辑
  - 接收方能把 repo-relative 示例当作示例阅读
  - 接收方不需要在其他仓库中直接运行 evals

- 以下情况应先调整后再分享：
  - 接收方需要 repo-agnostic 的技能包
  - 接收方不应看到内部仓库结构
  - evals 需要在另一个仓库中直接运行

## 若需要，最小额外清理 (Minimal Additional Cleanup If Needed)

- 用中性占位符替换仓库特定引用
  - `AGENTS.md` -> `project review guide`
  - `docs/design-docs/design-decision-checklist.md` -> `project design checklist`
  - `docs/reports/` -> `project report directory`
- 把 eval 中那条真实 repo 计划路径替换成合成样例文件
  - `docs/exec-plans/completed/2026-03-09-user-language-field-remediation-implementation-plan.md`
- 保留当前设计语义
  - 不要移除 migration、compatibility、state、observability 等信号
  - 这些信号是该技能保持有意义所必需的

## 验证快照 (Verification Snapshot)

- 已检查文件：
  - `SKILL.md`
  - `agents/openai.yaml`
  - `evals/evals.json`
  - `evals/files/*`
- 扫描结果：
  - 无本地绝对路径
  - 无明显 secret token pattern
  - 无明显 business identifier pattern
