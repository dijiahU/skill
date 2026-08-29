# Web Search Rules Skill - Security Guide

## ⚠️ 安全声明

本 skill 支持多平台知识库集成，**某些功能需要文件系统访问和浏览器自动化权限**。在使用前，请仔细阅读本安全指南。

---

## 🔒 权限需求说明

### 必需的权限
1. **配置文件读写** (`~/.skill-config/web-search-rules/config.json`)
   - 用途：存储用户平台选择偏好
   - 风险：低
   - 保护：仅存储非敏感配置信息

2. **搜索结果暂存** (`~/.skill-config/web-search-rules/temp/`)
   - 用途：临时存储搜索结果
   - 风险：中（可能包含敏感信息）
   - 保护：定期清理，不上传到云端

### 可选权限（按平台）
1. **Obsidian 支持**
   - 权限：读写 Obsidian Vault 目录
   - 风险：中高（可以访问所有 Vault 文件）
   - 保护：**限制操作仅在用户指定的 Vault 目录内**

2. **NotebookLM 支持**
   - 权限：浏览器自动化（Playwright），Google Account 访问
   - 风险：高（需要 Google Account 认证）
   - 保护：**不存储 Google Account 凭证**，每次手动登录

3. **网络搜索**
   - 权限：访问外部搜索 API
   - 风险：低
   - 保护：仅搜索用户指定的关键词

---

## 🛡️ 安全措施

### 1. 路径验证
所有文件路径操作都经过验证，**不允许任意路径写入**：

```python
import os
import re

# 允许的路径白名单
ALLOWED_PATHS = [
    os.path.expanduser("~/.skill-config/web-search-rules/"),
    os.path.expanduser("~/Documents/ObsidianVault/"),  # 需要用户确认
]

def validate_path(path):
    """验证路径是否在白名单内"""
    abs_path = os.path.abspath(path)
    for allowed in ALLOWED_PATHS:
        if abs_path.startswith(os.path.abspath(allowed)):
            return True
    raise SecurityError(f"Path {path} is not allowed!")

# 使用前验证
validate_path(user_specified_path)
```

### 2. 用户确认
所有敏感操作（文件写入、浏览器自动化、API 调用）都需要**用户显式确认**：

```python
# 在执行前询问用户
if not user_confirmed:
    ask_user("是否要将此内容保存到 Obsidian Vault？")
    if not user_response:
        abort_operation()
```

### 3. 凭证管理
- **不存储** Google Account 凭证
- **不存储** Obsidian Local REST API Key 到磁盘
- **仅存储**非敏感配置（平台选择、Vault 路径等）
- 敏感凭证存储在用户环境变量或密钥管理器中

### 4. 数据清理
- 临时文件在任务完成后**自动删除**
- 搜索结果暂存目录定期清理（默认 7 天）
- 不将敏感数据上传到云端

---

## 🚨 潜在风险

### 1. Prompt 注入
**风险**：恶意网页内容可能包含特殊指令，影响 AI 决策  
**缓解措施**：
- 对网页内容进行清理，移除特殊标记
- 不执行网页中的代码
- 所有决策需要用户确认

### 2. 路径遍历攻击
**风险**：恶意路径可能导致任意文件读写  
**缓解措施**：
- 严格验证所有文件路径
- 使用路径白名单
- 不允许用户指定任意路径

### 3. 凭证泄露
**风险**：Google Account 凭证可能被泄露  
**缓解措施**：
- 不存储凭证到磁盘
- 使用 OAuth 2.0 认证流程
- 定期提醒用户检查已授权的应用

### 4. 数据隐私
**风险**：搜索结果可能包含敏感信息  
**缓解措施**：
- 临时文件本地存储，不上传云端
- 定期清理临时文件
- 提醒用户注意敏感信息

---

## 📋 安全检查清单

在使用本 skill 前，请确认：

- [ ] 我已阅读并理解本安全指南
- [ ] 我确认 Obsidian Vault 路径设置正确
- [ ] 我了解 NotebookLM 需要 Google Account 认证
- [ ] 我确认不处理敏感或机密信息
- [ ] 我同意临时文件存储在本地磁盘
- [ ] 我了解如何报告和应对安全问题

---

## 📞 安全报告

如果你发现任何安全漏洞或潜在风险，请：

1. **不要**在公开场合披露漏洞详情
2. 通过安全渠道联系开发者
3. 提供详细的复现步骤
4. 等待官方修复后再公开披露

---

## 🔄 更新历史

- **v2.0.1** (2026-05-06): 添加安全指南，降低权限请求
- **v2.0.0** (2026-05-05): 初始版本，支持 Obsidian 和 NotebookLM

---

## 📚 参考资料

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Prompt Injection Attacks](https://genai.owasp.org/llm-top-10-overview/)
- [Google API Security Best Practices](https://developers.google.com/drive/api/v3/about/auth)
- [Obsidian Security Guide](https://help.obsidian.md/)

---

**最后更新**: 2026-05-06  
**版本**: v2.0.1
