# Obsidian 操作详解

本文档详细说明如何使用 Obsidian 作为知识库平台。

## 概述

Obsidian 是一款基于 Markdown 的知识库工具，支持双向链接、标签系统、插件生态等功能。本 skill 支持两种操作方式：

1. **方案 A（推荐）**：直接操作 Vault 文件系统
2. **方案 B**：通过 Obsidian Local REST API 插件操作

---

## 方案 A：直接操作 Vault 文件系统（推荐）

### 优点
- ✅ 无需额外依赖
- ✅ 简单高效
- ✅ 支持离线操作
- ✅ 完全掌控数据

### 缺点
- ❌ 无法触发 Obsidian 的实时更新（需要手动刷新）
- ❌ 不支持复杂的 Obsidian 特定功能（如双向链接自动创建）

### 配置

在 `config.json` 中设置：

```json
{
  "platform": "obsidian",
  "vault_path": "C:/Users/engla/Documents/ObsidianVault",
  "search_url_library": "search-url-library",
  "unorganized_content": "unorganized-search-content",
  "method": "filesystem"
}
```

### 文件结构

```
{Vault 路径}/
├── search-url-library/
│   ├── whitelist/
│   │   ├── example-com.md
│   │   └── ...
│   ├── blacklist/
│   │   ├── spam-site.md
│   │   └── ...
│   └── uncategorized/
│       ├── new-site-1.md
│       └── ...
└── unorganized-search-content/
    ├── 2026-05-05/
    │   ├── webpage-title-1.md
    │   └── ...
    └── ...
```

### 操作示例

#### 1. 创建/检查知识库

```python
import os

# 读取配置
vault_path = config["vault_path"]
search_url_library = config["search_url_library"]
unorganized_content = config["unorganized_content"]

# 创建目录
os.makedirs(os.path.join(vault_path, search_url_library, "whitelist"), exist_ok=True)
os.makedirs(os.path.join(vault_path, search_url_library, "blacklist"), exist_ok=True)
os.makedirs(os.path.join(vault_path, search_url_library, "uncategorized"), exist_ok=True)
os.makedirs(os.path.join(vault_path, unorganized_content, "2026-05-05"), exist_ok=True)
```

#### 2. 添加网址到白名单

```python
import os
from datetime import datetime

# 生成文件名（使用网址的域名）
url = "https://example.com/article1"
domain = url.split("/")[2].replace(".", "-")
filename = f"{domain}.md"
filepath = os.path.join(vault_path, search_url_library, "whitelist", filename)

# 写入内容
content = f"""---
added: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
category: whitelist
---

# {url}

## 添加信息

- **添加时间**：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **添加原因**：用户确认，内容优质
- **网址**：{url}

## 相关笔记

- [[search-rules]]
"""

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
```

#### 3. 暂存搜索内容

```python
import os
from datetime import datetime

# 生成文件名（使用网页标题）
title = "网页标题1"
date = datetime.now().strftime("%Y-%m-%d")
filename = f"{title.replace(' ', '-')}.md"
filepath = os.path.join(vault_path, unorganized_content, date, filename)

# 写入内容
content = f"""---
title: {title}
url: https://example.com/article1
date: {date}
status: pending
keywords: AI, 机器学习
---

# {title}

## 基本信息

- **网址**：https://example.com/article1
- **发布时间**：2026-05-05
- **来源**：Example Source
- **状态**：待确认
- **搜索关键词**：AI, 机器学习

## 内容摘要

这是一篇关于 AI 和机器学习的文章...

## 完整内容

这是文章的完整内容...

## 标签

#AI #机器学习 #待确认
"""

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
```

#### 4. 读取网址库

```python
import os

# 读取白名单
whitelist_dir = os.path.join(vault_path, search_url_library, "whitelist")
whitelist_files = os.listdir(whitelist_dir)

whitelist_urls = []
for filename in whitelist_files:
    filepath = os.path.join(whitelist_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        # 提取网址
        if "网址**：" in content:
            url = content.split("网址**：")[1].split("\n")[0].strip()
            whitelist_urls.append(url)
```

#### 5. 整理并归档内容

```python
import os
import shutil

# 从「未整理搜索内容」移动到目标知识库
source_dir = os.path.join(vault_path, unorganized_content, "2026-05-05")
target_dir = os.path.join(vault_path, "knowledge-base", "AI")

# ⚠️ 安全提醒：移动文件前需要用户确认
if user_confirmed("确认要移动这些文件到知识库吗？"):
    # 移动文件
    for filename in os.listdir(source_dir):
        source_file = os.path.join(source_dir, filename)
        target_file = os.path.join(target_dir, filename)
        shutil.move(source_file, target_file)
        print(f"已移动：{filename}")
```

---

## 方案 B：使用 Obsidian Local REST API 插件

### 安装插件

1. 打开 Obsidian
2. 进入 **设置** → **第三方插件**
3. 点击 **浏览社区插件**
4. 搜索 **Local REST API**
5. 点击 **安装**
6. 点击 **启用**

### 配置插件

1. 进入 **设置** → **Local REST API**
2. **不建议设置 API Key**（留空更安全）
3. 记下 **Port**（默认：27123）

### 配置

⚠️ **安全提醒**：请不要将 API Key 存储在 `config.json` 中！应该使用环境变量或密钥管理工具。

**推荐方法：不使用 API Key（最简单安全）**

在 `config.json` 中设置（不包含 API key）：

```json
{
  "platform": "obsidian",
  "vault_path": "C:/Users/engla/Documents/ObsidianVault",
  "search_url_library": "search-url-library",
  "unorganized_content": "unorganized-search-content",
  "method": "rest-api",
  "obsidian_api_url": "http://localhost:27123"
}
```

**如果需要 API Key 认证**，请使用环境变量：

```bash
# Linux/Mac
export OBSIDIAN_API_KEY="your-api-key"

# Windows (PowerShell)
$env:OBSIDIAN_API_KEY="your-api-key"
```

然后在代码中读取：

```python
import os

api_key = os.getenv("OBSIDIAN_API_KEY")  # 从环境变量读取
```

### 操作示例

#### 1. 创建笔记

```python
import requests
import os

api_url = config["obsidian_api_url"]
api_key = os.getenv("OBSIDIAN_API_KEY")  # 从环境变量读取

headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"
headers["Content-Type"] = "application/json"

# 创建笔记
data = {
    "content": "# 网页标题\n\n这是内容...",
    "path": "unorganized-search-content/2026-05-05/webpage-title.md"
}

response = requests.post(f"{api_url}/vault/create", headers=headers, json=data)
```

#### 2. 读取笔记

```python
import requests
import os

api_url = config["obsidian_api_url"]
api_key = os.getenv("OBSIDIAN_API_KEY")  # 从环境变量读取

headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

# 读取笔记
response = requests.get(f"{api_url}/vault/unorganized-search-content/2026-05-05/webpage-title.md", headers=headers)
content = response.text
```

#### 3. 更新笔记

```python
import requests
import os

api_url = config["obsidian_api_url"]
api_key = os.getenv("OBSIDIAN_API_KEY")  # 从环境变量读取

headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"
headers["Content-Type"] = "application/json"

# 更新笔记
data = {
    "content": "# 更新后的标题\n\n这是更新后的内容..."
}

response = requests.post(f"{api_url}/vault/update", headers=headers, json=data)
```

#### 4. 删除笔记

⚠️ **安全提醒**：删除操作需要用户显式确认！

```python
import requests
import os

api_url = config["obsidian_api_url"]
api_key = os.getenv("OBSIDIAN_API_KEY")  # 从环境变量读取

headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

# ⚠️ 删除前需要用户确认
if user_confirmed("确认要删除这个笔记吗？"):
    # 删除笔记
    response = requests.delete(f"{api_url}/vault/delete", headers=headers, params={"path": "unorganized-search-content/2026-05-05/webpage-title.md"})
    print("笔记已删除")
```

---

## 双向链接

Obsidian 的强大功能之一是双向链接。在 Markdown 文件中使用 `[[笔记名称]]` 来创建链接。

### 示例

```markdown
# 网页标题

## 相关笔记

- [[AI 概述]]
- [[机器学习基础]]
- [[search-rules]]
```

当你打开 `[[AI 概述]]` 这个笔记时，Obsidian 会自动显示所有链接到这个笔记的其他笔记。

---

## 标签系统

Obsidian 支持使用 `#标签` 来分类笔记。

### 示例

```markdown
# 网页标题

## 标签

#AI #机器学习 #待确认 #重要
```

你可以在 Obsidian 的 **标签页面** 中查看所有标签和对应的笔记。

---

## 注意事项

⚠️ **安全提醒**：
1. **Vault 路径验证**：使用前请确保 `vault_path` 设置正确，避免未授权的文件存取
2. **路径白名单**：所有文件操作都会验证路径是否在 Vault 目录内
3. **用户确认**：敏感操作（如删除文件）需要用户显式确认
4. **凭证保护**：Obsidian API Key **不存储到磁盘**，仅存储在内存中（环境变量）
5. **文件备份**：建议定期备份 Vault 目录

## 安全代码示例

```python
import os
from pathlib import Path

# 路径验证函数
def validate_vault_path(vault_path, target_path):
    """验证目标路径是否在 Vault 目录内"""
    vault_abs = Path(vault_path).resolve()
    target_abs = Path(target_path).resolve()
    
    # 检查目标路径是否在 Vault 目录内
    try:
        target_abs.relative_to(vault_abs)
        return True
    except ValueError:
        raise SecurityError(f"路径 {target_path} 不在允许的 Vault 目录内！")

# 使用前验证
vault_path = config["vault_path"]
target_file = os.path.join(vault_path, "search-url-library", "whitelist", "example.com.md")

# 验证路径
validate_vault_path(vault_path, target_file)

# 安全读取文件
with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()
```

1. **Vault 路径**：确保 `vault_path` 配置正确
2. **文件编码**：始终使用 UTF-8 编码
3. **文件名特殊字符**：避免使用特殊字符（如 `/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`）
4. **方案 A**：修改文件后，需要手动刷新 Obsidian 才能看到更新
5. **方案 B**：需要预先安装并启用 Obsidian Local REST API 插件
6. **API 安全性**：如果设置了 API Key，请确保保密（但推荐使用环境变量，不要写在 config.json 中）
7. **文件备份**：建议定期备份 Vault 目录

---

## 参考资源

- [Obsidian 官方文档](https://help.obsidian.md/)
- [Obsidian Local REST API 插件](https://github.com/coddingtonbear/obsidian-local-rest-api)
- [Obsidian Markdown 语法](https://help.obsidian.md/Editing+and+formatting/Basic+formatting+syntax)
