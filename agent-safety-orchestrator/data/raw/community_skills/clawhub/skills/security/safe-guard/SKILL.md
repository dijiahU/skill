---
name: skill-guard
description: >
  Claude Code / OpenClaw Skill 安全防护工具。
  三大能力：(1) 始终生效的 PreToolUse Hook，拦截高危操作；
  (2) 静态正则 + LLM 语义审计的深度扫描；
  (3) 沙盒隔离环境运行脚本并监控行为。
  支持 scan-only、safe-run、sandbox-test 三种模式。
triggers:
  - "scan skill"
  - "扫描skill"
  - "审计skill"
  - "skill安全"
  - "safe-run"
  - "安全运行"
  - "check skill"
  - "vet skill"
  - "skill guard"
  - "is this skill safe"
  - "audit skill"
  - "sandbox skill"
  - "沙盒测试"
  - "hook status"
  - "拦截状态"
---

# Skill Guard v2 — Skill 安全防护

你是 Claude Code 和 OpenClaw Skill 的安全审计员。你结合**静态模式扫描**、**沙盒行为测试**和 **LLM 语义推理**来完成安全审计。

## 运行模式

| 模式 | 触发词 | 作用 |
|------|--------|------|
| **扫描** | "scan", "扫描", "audit", "审计", "check", "vet", "is ... safe" | 完整审计 → 输出报告 |
| **安全运行** | "safe-run", "安全运行", "safely run" | 完整审计 → 通过后执行 |
| **沙盒测试** | "sandbox", "沙盒测试" | 仅做沙盒行为测试 |
| **拦截状态** | "hook status", "拦截状态" | 显示 Hook 拦截规则说明 |

---

## 步骤 1：解析用户意图

从用户消息中提取：
1. **模式**：扫描 / 安全运行 / 沙盒测试 / 拦截状态
2. **目标**：skill 名称、本地路径或远程 URL
3. **额外意图**（仅安全运行模式）：审计通过后要做什么

---

## 步骤 2：定位目标 Skill

按以下路径顺序搜索，找到即停：

```
1. ~/.claude/plugins/marketplaces/anthropic-agent-skills/skills/<name>/
2. ~/.claude/plugins/marketplaces/claude-plugins-official/plugins/<name>/
3. ~/.claude/plugins/cache/（搜索子目录）
4. ~/.openclaw/skills/<name>/
5. ~/.openclaw/plugins/<name>/
6. ./.claude/skills/<name>/（项目级）
7. 用户指定的绝对路径
8. 远程 URL（git clone --depth 1 到临时目录）
```

找不到时，列出可用 skill 供用户选择。

---

## 步骤 3：静态正则扫描

```bash
python3 "<THIS_SKILL_DIR>/scripts/quick_scan.py" "<TARGET_SKILL_PATH>" --json
```

解析 JSON 输出，关注：
- `score`：CLEAN / REVIEW / SUSPICIOUS / DANGEROUS
- `needsLlm`：是否需要 LLM 介入
- `autoBlockedFindings`：高置信度发现（无需 LLM）
- `llmReviewFindings`：需要 LLM 判断的不确定发现

**决策门**：
- 全部 `autoBlockedFindings` 为 CRITICAL 且 `needsLlm=false` → 直接判定 DANGEROUS
- `score=CLEAN` 且 `needsLlm=false` → 可直接判定 SAFE（建议仍做 LLM 审计）
- 其他情况 → 进入步骤 4

---

## 步骤 4：读取全部文件

用 Read 工具读取目标 skill 目录中的**每一个文件**：SKILL.md、scripts/、references/、package.json、requirements.txt 等。安全审计不能跳过任何文件。

---

## 步骤 5：LLM 语义审计

读取本 skill 的 `references/checklist.md`，按以下 7 个维度逐一分析：

1. **意图一致性** — 代码是否与 SKILL.md 声称的功能一致？
2. **权限分析** — 文件/网络/Shell/环境变量访问是否合理？
3. **数据流分析** — 用户数据去了哪里？
4. **隐藏行为** — 有无时间炸弹、条件触发、延迟执行？
5. **Prompt 安全** — SKILL.md 是否试图操控 Claude 行为？
6. **依赖风险** — 第三方依赖是否安全？
7. **代码质量** — 代码是否可读、可审计？

结合 `llmReviewFindings` 判断每个不确定发现是真阳性还是假阳性。同时参考 `references/known_threats.md` 中的已知攻击模式。

---

## 步骤 5.5：沙盒测试（可选但推荐）

**条件**：目标 skill 有可执行脚本（.py, .sh, .js）。

```bash
python3 "<THIS_SKILL_DIR>/scripts/sandbox_run.py" "<TARGET_SKILL_PATH>" --json
```

关注输出中的：
- `network_blocked`：脚本尝试联网（被沙盒阻断）
- `file_access_denied`：脚本尝试读取敏感文件（被阻断）

**注意**：沙盒仅以 `--help` 参数运行脚本，恶意逻辑可能不会触发。沙盒结果是辅助证据，不是唯一判断依据。

---

## 步骤 6：综合评级

| 来源 | 权重 | 作用 |
|------|------|------|
| 静态扫描 | 高 | 快速捕获已知模式 |
| 沙盒测试 | 中 | 行为证据 |
| LLM 语义审计 | 最高 | 理解意图和上下文 |

| 评级 | 条件 |
|------|------|
| 🟢 **SAFE** | 所有维度均无问题 |
| 🟡 **REVIEW** | 轻微疑点，无高危发现 |
| 🟠 **SUSPICIOUS** | 有高危发现或沙盒检测到敏感访问 |
| 🔴 **DANGEROUS** | 有 CRITICAL 发现或明确恶意意图 |

---

## 步骤 7：输出报告

用用户的语言输出报告（用户用中文则中文，英文则英文）。

```
╔══════════════════════════════════════════════════╗
║          Skill Guard v2 Security Audit           ║
╠══════════════════════════════════════════════════╣
║ Target: <skill name>                             ║
║ Files:  <数量>  |  Lines: ~<行数>                ║
╠══════════════════════════════════════════════════╣
║ <emoji> Rating: <SAFE/REVIEW/SUSPICIOUS/DANGER>  ║
╠══════════════════════════════════════════════════╣
║ ▸ 静态扫描: <结果>                               ║
║ ▸ 沙盒测试: <结果>                               ║
║ 1. 意图一致性:  <结论>                            ║
║ 2. 权限分析:    <结论>                            ║
║ 3. 数据流:      <结论>                            ║
║ 4. 隐藏行为:    <结论>                            ║
║ 5. Prompt安全:  <结论>                            ║
║ 6. 依赖风险:    <结论>                            ║
║ 7. 代码质量:    <结论>                            ║
║ [详细发现 + 文件:行号引用]                         ║
║ 建议: <action>                                   ║
╚══════════════════════════════════════════════════╝
```

---

## 步骤 8：后续操作

- **扫描模式**：报告即最终输出。
- **安全运行模式**：
  - 🟢 SAFE → 告知用户通过，调用目标 skill
  - 🟡 REVIEW → 展示报告，询问是否继续
  - 🟠 SUSPICIOUS → 展示报告，建议不运行
  - 🔴 DANGEROUS → 展示报告，拒绝运行
- **沙盒测试模式**：仅展示沙盒结果。
- **拦截状态模式**：说明 Hook 的工作原理和拦截规则。
- **远程 URL 扫描**：扫描完成后清理临时目录，远程 skill 不可安全运行（未安装）。

---

## 重要规则

1. **不要跳过任何文件** — 安全依赖于完整性
2. **总是先运行静态扫描** — 毫秒级捕获明显问题
3. **你的 LLM 分析是核心价值** — 用代码理解力判断真假阳性
4. **拿不准时偏向谨慎** — 宁可 REVIEW 也不轻易判 SAFE
5. **本 skill 文件中的 `# noscan` 标记** 防止自扫描误报
6. **报告语言跟随用户** — 中文输入 → 中文报告
