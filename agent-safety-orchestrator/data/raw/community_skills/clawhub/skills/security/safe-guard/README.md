# Skill Guard v2 — 全能安全防护

一款面向 Claude Code / OpenClaw 的 Skill 安全防护工具，提供三重保护能力。

## 三大能力

### 1. 始终生效的高危拦截（Hook）

安装后自动生效，无需手动调用。通过 PreToolUse Hook 在每次工具执行前拦截危险操作：

- 破坏性文件删除、数据库销毁等不可逆命令 <!-- noscan -->
- 远程代码下载并执行模式 <!-- noscan -->
- 写入凭证目录、Shell 配置文件等敏感路径 <!-- noscan -->
- 反向连接、进程耗尽等攻击模式 <!-- noscan -->

被拦截时会提示用户确认，同一 session 内确认过的操作不会重复拦截。

### 2. Skill 安全扫描（静态 + LLM 语义审计）

采用两阶段管道：

1. **正则扫描**（毫秒级）：38 条规则 + 行为组合检测 + 熵分析
2. **LLM 语义审计**：大模型阅读全部源码，按 8 维清单逐项评估

扫描器会自动判断哪些发现可以直接定性（`auto_block`），哪些需要 LLM 介入判断（`needsLlm`），避免浪费推理资源。

### 3. 沙盒模拟运行

在受限环境中执行 Skill 的脚本，监控其行为：

- macOS 使用 `sandbox-exec` + Seatbelt Profile（禁网络、限文件访问）
- Linux 使用受限 PATH + 隔离 HOME 目录
- 自动分析：是否尝试访问网络、是否尝试读取凭证目录等敏感文件 <!-- noscan -->

## 使用方式

以下命令直接在对话中输入即可：ß

```
扫描 pdf skill              → 对 pdf skill 做完整安全审计
scan skill xlsx             → 审计 xlsx skill
安全运行 pdf skill 合并a.pdf  → 审计通过后自动调用 pdf skill
沙盒测试 ai-skill-scanner    → 仅做沙盒行为测试
扫描 /path/to/some-skill     → 扫描指定路径的 skill
扫描 https://github.com/x/y  → 拉取远程仓库后扫描
拦截状态                     → 查看 Hook 拦截规则说明
```

## 审计报告示例

```
╔══════════════════════════════════════════════════╗
║          Skill Guard v2 Security Audit           ║
╠══════════════════════════════════════════════════╣
║ Target: pdf                                      ║
║ Files:  12  |  Lines: ~1849                      ║
╠══════════════════════════════════════════════════╣
║ 🟢 Rating: SAFE                                  ║
╠══════════════════════════════════════════════════╣
║ ▸ Static Scan: CLEAN — 无恶意模式                 ║
║ ▸ Sandbox:     CLEAN — 无可疑行为                 ║
║ 1. 意图一致性:  ✅ MATCH                          ║
║ 2. 权限分析:    ✅ JUSTIFIED                      ║
║ 3. 数据流:      ✅ LOCAL_ONLY                     ║
║ 4. 隐藏行为:    ✅ NONE_FOUND                     ║
║ 5. Prompt安全:  ✅ CLEAN                          ║
║ 6. 依赖风险:    ✅ LOW_RISK                       ║
║ 7. 代码质量:    ✅ READABLE                       ║
║ 建议: 安全，可以运行                               ║
╚══════════════════════════════════════════════════╝
```

## 评级说明

| 评级 | 含义 | safe-run 行为 |
|------|------|--------------|
| 🟢 SAFE | 无风险 | 自动执行目标 skill |
| 🟡 REVIEW | 有轻微疑点 | 询问用户是否继续 |
| 🟠 SUSPICIOUS | 有高危发现 | 建议不运行 |
| 🔴 DANGEROUS | 几乎确定恶意 | 拒绝运行 |

## 文件结构

```
skill-guard/
├── SKILL.md                    主指令（审计流程）
├── hooks/
│   ├── hooks.json              Hook 注册配置
│   └── danger_guard.py         高危行为拦截脚本
├── scripts/
│   ├── quick_scan.py           静态正则扫描器
│   └── sandbox_run.py          沙盒执行器
└── references/
    ├── checklist.md            LLM 8维审计清单
    ├── known_threats.md        已知威胁模式库
    ├── dangerous_commands.md   Hook 高危命令参考
    └── openclaw_adapter.md     OpenClaw 平台适配指南
```

## 平台兼容

- **Claude Code**：Hook 通过 `hooks/hooks.json` 自动注册，开箱即用
- **OpenClaw**：参考 `references/openclaw_adapter.md` 中的 TypeScript 适配模板
- 扫描和沙盒功能为纯 Python 实现，两个平台通用
