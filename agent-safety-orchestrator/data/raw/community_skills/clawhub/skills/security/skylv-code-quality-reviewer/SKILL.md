---
name: "Code Reviewer"
slug: skylv-code-reviewer
version: 1.0.2
description: Code review assistant. Analyzes code quality, detects bugs and security issues, and suggests improvements. Triggers: code review, security audit, code quality, bug detection.
author: SKY-lv
license: MIT-0
tags: [openclaw, agent, code]
keywords: code-review, linting, security, quality
triggers: code reviewer
---

# CodeReview Agent Skill

> AI-powered code review and quality analysis agent

## 功能

- **代码质量分析** - 检测代码异味、复杂度问题
- **安全漏洞扫描** - SQL注入、XSS、敏感信息泄露
- **性能优化建议** - 识别性能瓶颈
- **最佳实践检查** - 符合语言规范和设计模式
- **自动修复建议** - 提供可执行的修复代码

## 使用场景

```
用户: 帮我审查这段Python代码的安全性
Agent: [调用code-reviewer skill分析代码，输出安全问题列表和修复建议]
```

## 工具函数

### `review_code(code, language, focus_areas)`

审查代码并返回分析报告。

**参数:**
- `code` (str): 要审查的代码
- `language` (str): 编程语言 (python/javascript/go/rust/java等)
- `focus_areas` (list): 关注点 ['security', 'performance', 'style', 'complexity']

**返回:**
```python
{
    "issues": [
        {
            "type": "security",
            "severity": "high",
            "line": 42,
            "message": "Potential SQL injection vulnerability",
            "suggestion": "Use parameterized queries"
        }
    ],
    "score": 75,
    "summary": "代码整体可读性良好，但存在安全风险"
}
```

### `analyze_complexity(code, language)`

分析代码复杂度（圈复杂度、认知复杂度）。

### `detect_patterns(code, language)`

检测代码中使用的设计模式。

## 配置

```json
{
    "rules": {
        "max_complexity": 10,
        "max_line_length": 120,
        "require_docstring": true,
        "security_checks": ["injection", "xss", "secrets"]
    }
}
```

## 示例

```python
# 审查Python代码
result = review_code('''
def get_user(id):
    query = f"SELECT * FROM users WHERE id = {id}"
    return db.execute(query)
''', 'python', ['security'])

# 输出:
# [HIGH] SQL Injection: Use parameterized queries
# Line 3: query = f"SELECT * FROM users WHERE id = {id}"
# Suggestion: query = "SELECT * FROM users WHERE id = ?"
```

## 安装

```bash
clawhub install SKY-lv/code-reviewer
```

## License

MIT

## Usage

1. Install the skill
2. Configure as needed
3. Run with OpenClaw
