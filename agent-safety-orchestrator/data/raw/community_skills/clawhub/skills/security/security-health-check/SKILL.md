---
name: security-health-check
version: "1.5.0"
description: "数字安全体检工具。检查邮箱泄露、密码强度，生成安全评分报告。纯命令行参数驱动，无交互式输入。"
metadata:
  openclaw:
    emoji: "🔒"
    category: security

## 功能
- 邮箱泄露检查（HIBP API，k-匿名查询）
- 密码强度分析（纯本地计算）
- 安全评分生成
- Markdown报告输出

## 使用方法
```
python3 scripts/security_check.py --email user@example.com
python3 scripts/security_check.py --email user@example.com --password YourPassword
```

## 参数
- `--email`（必填）：要检查的邮箱地址
- `--password`（可选）：要检查强度的密码，仅本地计算不外传

## 依赖
- Python 3.7+
- certifi

## 数据来源
- haveibeenpwned.com 公开API（k-匿名前缀查询，密码不离开本地）

## 隐私声明
- 邮箱查询通过HIBP公开API
- 密码检查使用k-匿名前缀查询，仅发送SHA1前5位，完整密码不离开本地
- 无任何数据收集或存储行为