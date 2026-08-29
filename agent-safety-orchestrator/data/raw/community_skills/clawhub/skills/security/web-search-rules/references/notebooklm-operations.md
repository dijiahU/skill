# NotebookLM 操作详解

本文档详细说明如何使用 NotebookLM 作为知识库平台。

## 概述

NotebookLM 是 Google 推出的 AI 辅助研究工具，可以自动摘要、问答、分析上传的内容。本 skill 支持两种操作方式：

1. **方案 A（推荐）**：使用浏览器自动化（`playwright-cli` 或 `agent-browser`）
2. **方案 B**：通过 Google Drive API 间接集成

---

## 方案 A：浏览器自动化（推荐）

### 优点
- ✅ 直接操作 NotebookLM Web 界面
- ✅ 支持所有 NotebookLM 功能
- ✅ 不需要 Google Drive API 配置
- ✅ 可以处理任意格式的文件

### 缺点
- ❌ 需要稳定的网络连接
- ❌ **需要手动登录 Google 账号（不要存储凭证！）**
- ❌ 浏览器自动化可能较慢

### 前置准备

⚠️ **安全提醒**：
1. **不要存储 Google 账号凭证**！每次手动登录。
2. **使用单独的浏览器 profile**，避免与主浏览器混淆。
3. **限制 OAuth scopes**，只授权必要的权限。

#### 1. 安装浏览器自动化工具：

**选项 1**：`playwright-cli`（推荐）

```bash
# ⚠️ 推荐使用虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  (Windows)

# 安装固定版本（避免供应链攻击）
pip install playwright==1.44.0
playwright install chromium
```

**选项 2**：`agent-browser` skill
- 确保 `agent-browser` skill 已安装
- 使用独立的环境运行

#### 2. 手动登录 Google 账号：

⚠️ **重要**：**不要**在代码中硬编码凭证！

```bash
# 手动打开 NotebookLM
# 1. 打开浏览器
# 2. 访问 https://notebooklm.google.com/
# 3. 手动登录 Google 账号
# 4. 确保可以正常上传文件
```

#### 3. 配置（不包含凭证！）：

在 `config.json` 中设置：

```json
{
  "platform": "notebooklm",
  "method": "browser-automation",
  "notebook_name": "Search Results",
  "google_account": "your-email@gmail.com",  # 仅用于标识，不用于登录
  "browser_profile": "separate-profile"  # 使用单独的浏览器 profile
}
```

### 操作示例

#### 1. 创建新知识库（Notebook）

使用 `playwright-cli`：

```bash
# 启动浏览器并打开 NotebookLM
playwright-cli open "https://notebooklm.google.com/"

# ⚠️ 手动登录（不要自动化登录过程！）

# 点击「新建」按钮
playwright-cli click "text=新建"

# 输入知识库名称
playwright-cli type "input[placeholder='输入名称']" "Search Results"

# 点击「创建」按钮
playwright-cli click "text=创建"
```

#### 2. 上传文件

```bash
# ⚠️ 上传前需要用户确认
if user_confirmed("确认要上传这个文件到 NotebookLM 吗？"):
    # 上传文件
    playwright-cli upload "input[type='file']" "path/to/webpage-content.md"
    
    # 等待 AI 处理完成
    playwright-cli wait "text=处理完成" --timeout 60000
```

#### 3. 添加网页链接

```bash
# 点击「添加来源」按钮
playwright-cli click "text=添加来源"

# 选择「网页」选项
playwright-cli click "text=网页"

# 输入网址
playwright-cli type "input[placeholder='输入网址']" "https://example.com/article1"

# 点击「添加」按钮
playwright-cli click "text=添加"

# 等待 AI 处理完成
playwright-cli wait "text=处理完成" --timeout 60000
```

#### 4. 提问（AI 问答）

```bash
# 在提问框中输入问题
playwright-cli type "textarea[placeholder='询问任何问题...']" "这篇文章的主要观点是什么？"

# 点击「发送」按钮
playwright-cli click "button[aria-label='发送']"

# 等待回答生成
playwright-cli wait "text=回答完成" --timeout 30000

# 提取回答内容
answer = playwright-cli extract "div.answer-content"
```

#### 5. 导出摘要

```bash
# 点击「导出」按钮
playwright-cli click "button[aria-label='导出']"

# 选择「导出为 Markdown」
playwright-cli click "text=导出为 Markdown"

# 等待下载完成
playwright-cli wait "text=下载完成" --timeout 30000
```

---

## 方案 B：通过 Google Drive API 间接集成

### 优点
- ✅ 不需要浏览器自动化
- ✅ 更稳定、更快速
- ✅ 可以批量上传文件

### 缺点
- ❌ 需要配置 Google Drive API
- ❌ 需要手动在 NotebookLM 中导入 Drive 文件
- ❌ 不支持实时操作

### 前置准备

⚠️ **安全提醒**：
1. **固定包版本**，避免供应链攻击
2. **使用虚拟环境**，隔离依赖
3. **限制 OAuth scopes**，只申请最小必要权限

#### 1. 启用 Google Drive API：

- 访问 [Google Cloud Console](https://console.cloud.google.com/)
- 创建项目（或选择现有项目）
- 启用 **Google Drive API**
- 创建 OAuth 2.0 凭证（Desktop App）
- 下载 `credentials.json`

#### 2. 安装 Google Client Library（固定版本！）：

```bash
# ⚠️ 推荐使用虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  (Windows)

# 安装固定版本（避免供应链攻击）
pip install --upgrade google-api-python-client==2.116.0 google-auth-httplib2==0.2.0 google-auth-oauthlib==1.2.0
```

#### 3. 配置（不包含敏感信息！）：

在 `config.json` 中设置：

```json
{
  "platform": "notebooklm",
  "method": "google-drive-api",
  "google_drive_folder_id": "your-folder-id",
  "credentials_file": "path/to/credentials.json",
  "token_file": "path/to/token.json",
  "oauth_scopes": [
    "https://www.googleapis.com/auth/drive.file"  # 最小权限
  ]
}
```

### 操作示例

#### 1. 上传文件到 Google Drive

```python
import os
import google.auth
from google.auth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 认证（使用最小 OAuth scope）
creds = Credentials.from_authorized_user_file(
    config["token_file"],
    scopes=config.get("oauth_scopes", ["https://www.googleapis.com/auth/drive.file"])
)

# 构建 Drive API 客户端
service = build("drive", "v3", credentials=creds)

# 上传文件
file_metadata = {
    "name": "webpage-content.md",
    "parents": [config["google_drive_folder_id"]]
}

media = MediaFileUpload(
    "path/to/webpage-content.md",
    mimetype="text/markdown"
)

file = service.files().create(
    body=file_metadata,
    media_body=media,
    fields="id, webViewLink"
).execute()

print(f"文件已上传：{file.get('webViewLink')}")
```

#### 2. 在 NotebookLM 中导入 Drive 文件

**注意**：NotebookLM 目前不支持通过 API 自动导入 Drive 文件，需要手动操作：

1. 打开 [NotebookLM](https://notebooklm.google.com/)
2. 打开目标知识库（Notebook）
3. 点击「添加来源」
4. 选择「Google Drive」
5. 选择上传的文件
6. 点击「导入」

**自动化方案**：可以使用浏览器自动化（方案 A）来自动化这个过程（但需要手动登录）。

---

## 完整工作流程示例

### 场景：搜索网页并保存到 NotebookLM

```python
# ⚠️ 安全提醒：
# 1. 所有上传操作需要用户确认
# 2. 不要上传敏感信息
# 3. 使用单独的浏览器 profile

# 1. 搜索网页
search_results = search_web("AI 机器学习")

# 2. 过滤结果（根据白名单/黑名单）
filtered_results = filter_results(search_results)

# 3. 暂存网页内容
for result in filtered_results:
    # 下载网页内容
    content = download_webpage(result["url"])
    
    # 保存为 Markdown 文件
    filename = f"temp/{result['title']}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    
    # ⚠️ 上传前需要用户确认
    if user_confirmed(f"确认要上传 {filename} 到 NotebookLM 吗？"):
        # 上传到 NotebookLM（使用浏览器自动化）
        upload_to_notebooklm(filename)
        
        # 等待 AI 处理完成
        wait_for_processing()

# 4. 提取 AI 摘要
summary = ask_notebooklm("请总结所有上传文档的主要观点")

# 5. 保存摘要（需要用户确认）
if user_confirmed("确认要保存这个摘要吗？"):
    save_summary(summary)
```

---

## 注意事项

⚠️ **安全提醒**：
1. **凭证管理**：本 skill **不存储** Google 账号凭证。每次手动登录。
2. **数据隐私**：上传的内容会被发送到 Google 服务器。**请勿上传敏感信息**！
3. **浏览器自动化安全**：如果使用方案 A，请确保 `playwright-cli` 或 `agent-browser` 来自可信源。
4. **API 配额**：注意 Google Drive API 使用配额，避免服务中断。
5. **网络安全**：确保稳定且安全的网络连接，传输数据时使用 HTTPS。
6. **OAuth Scope 限制**：只申请最小必要的 OAuth 权限（如 `drive.file` 而不是 `drive`）。
7. **单独浏览器 Profile**：使用单独的浏览器 profile，避免与主浏览器混淆。
8. **虚拟环境**：使用虚拟环境安装 Python 包，避免污染系统环境。
9. **固定版本**：固定所有依赖包的版本，避免供应链攻击。

## 安全最佳实践

```python
# ✅ 推荐：让用户手动登录，DO NOT 存储凭证
# 错误示例 (DO NOT DO THIS):
config = {
    "google_username": "user@gmail.com",
    "google_password": "password123"  # 永远不要存储密码！
}

# 正确示例:
config = {
    "notebook_name": "Search Results",
    "method": "browser-automation"
    # 没有存储凭证
}

# 用户会在浏览器中手动登录
```

```python
# ✅ 推荐：使用最小 OAuth scope
# 错误示例 (DO NOT DO THIS):
scopes = ["https://www.googleapis.com/auth/drive"]  # 权限太大

# 正确示例:
scopes = ["https://www.googleapis.com/auth/drive.file"]  # 最小权限
```

```python
# ✅ 推荐：上传前需要用户确认
filename = "path/to/webpage-content.md"

# 错误示例 (DO NOT DO THIS):
upload_to_notebooklm(filename)  # 没有确认就上传

# 正确示例:
if user_confirmed(f"确认要上传 {filename} 到 NotebookLM 吗？"):
    upload_to_notebooklm(filename)
```

1. **网络连接**：确保稳定的网络连接
2. **Google 账号**：手动登录 Google 账号（不存储凭证）
3. **API 配额**：注意 Google Drive API 使用配额
4. **文件格式**：NotebookLM 支持 PDF、Markdown、纯文本、Google Docs 等格式
5. **隐私保护**：上传的内容会被发送到 Google 服务器，请注意敏感信息
6. **浏览器自动化**：如果使用方案 A，请确保 `playwright-cli` 或 `agent-browser` 已正确安装
7. **等待时间**：AI 处理需要时间，请确保设置足够的等待时间
8. **定期清理**：定期清理临时文件和浏览器缓存
9. **使用本地替代方案**：如果需要处理敏感信息，请使用本地 Obsidian 存储

---

## 参考资源

- [NotebookLM 官方网站](https://notebooklm.google.com/)
- [NotebookLM 帮助中心](https://support.google.com/notebooklm/)
- [Google Drive API 文档](https://developers.google.com/drive/api/v3/about)
- [Playwright CLI 文档](https://playwright.dev/)
- [Agent Browser Skill](https://clawhub.ai/skills/agent-browser)
- [OAuth 2.0 Security Best Practices](https://oauth.net/2/security-considerations/)
