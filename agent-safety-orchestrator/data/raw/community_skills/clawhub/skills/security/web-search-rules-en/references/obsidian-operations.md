# Obsidian Operations Details

This document explains in detail how to use Obsidian as a knowledge base platform.

## Overview

Obsidian is a Markdown-based knowledge base tool that supports bidirectional links, tag system, plugin ecosystem, and other features. This skill supports two operation methods:

1. **Method A (Recommended)**: Direct operation of Vault file system
2. **Method B**: Through Obsidian Local REST API plugin

---

## Method A: Direct Operation of Vault File System (Recommended)

### Advantages
- ✅ No additional dependencies
- ✅ Simple and efficient
- ✅ Supports offline operation
- ✅ Full data control

### Disadvantages
- ❌ Cannot trigger Obsidian real-time updates (manual refresh needed)
- ❌ Does not support complex Obsidian-specific features (such as automatic bidirectional link creation)

### Configuration

Set in `config.json`:

```json
{
  "platform": "obsidian",
  "vault_path": "C:/Users/engla/Documents/ObsidianVault",
  "search_url_library": "search-url-library",
  "unorganized_content": "unorganized-search-content",
  "method": "filesystem"
}
```

### File Structure

```
{Vault Path}/
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

### Operation Examples

#### 1. Create/Check Knowledge Base

```python
import os

# Read configuration
vault_path = config["vault_path"]
search_url_library = config["search_url_library"]
unorganized_content = config["unorganized_content"]

# Create directories
os.makedirs(os.path.join(vault_path, search_url_library, "whitelist"), exist_ok=True)
os.makedirs(os.path.join(vault_path, search_url_library, "blacklist"), exist_ok=True)
os.makedirs(os.path.join(vault_path, search_url_library, "uncategorized"), exist_ok=True)
os.makedirs(os.path.join(vault_path, unorganized_content, "2026-05-05"), exist_ok=True)
```

#### 2. Add URL to Whitelist

```python
import os
from datetime import datetime

# Generate filename (using URL domain)
url = "https://example.com/article1"
domain = url.split("/")[2].replace(".", "-")
filename = f"{domain}.md"
filepath = os.path.join(vault_path, search_url_library, "whitelist", filename)

# Write content
content = f"""---
added: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
category: whitelist
---

# {url}

## Addition Information

- **Addition Time**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **Addition Reason**: User confirmed, high-quality content
- **URL**: {url}

## Related Notes

- [[search-rules]]
"""

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
```

#### 3. Stage Search Content

```python
import os
from datetime import datetime

# Generate filename (using webpage title)
title = "Webpage Title 1"
date = datetime.now().strftime("%Y-%m-%d")
filename = f"{title.replace(' ', '-')}.md"
filepath = os.path.join(vault_path, unorganized_content, date, filename)

# Write content
content = f"""---
title: {title}
url: https://example.com/article1
date: {date}
status: pending
keywords: AI, Machine Learning
---

# {title}

## Basic Information

- **URL**: https://example.com/article1
- **Publish Time**: 2026-05-05
- **Source**: Example Source
- **Status**: Pending confirmation
- **Search Keywords**: AI, Machine Learning

## Content Summary

This is an article about AI and machine learning...

## Full Content

This is the full content of the article...

## Tags

#AI #MachineLearning #PendingConfirmation
"""

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
```

#### 4. Read URL Library

```python
import os

# Read whitelist
whitelist_dir = os.path.join(vault_path, search_url_library, "whitelist")
whitelist_files = os.listdir(whitelist_dir)

whitelist_urls = []
for filename in whitelist_files:
    filepath = os.path.join(whitelist_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        # Extract URL
        if "**URL**:" in content:
            url = content.split("**URL**:")[1].split("\n")[0].strip()
            whitelist_urls.append(url)
```

#### 5. Organize and Archive Content

```python
import os
import shutil

# From "Unorganized Search Content" move to target knowledge base
source_dir = os.path.join(vault_path, unorganized_content, "2026-05-05")
target_dir = os.path.join(vault_path, "knowledge-base", "AI")

# ⚠️ Security Notice: Need user confirmation before moving files
if user_confirmed("Confirm to move these files to knowledge base?"):
    # Move files
    for filename in os.listdir(source_dir):
        source_file = os.path.join(source_dir, filename)
        target_file = os.path.join(target_dir, filename)
        shutil.move(source_file, target_file)
        print(f"Moved: {filename}")
```

---

## Method B: Using Obsidian Local REST API Plugin

### Install Plugin

1. Open Obsidian
2. Go to **Settings** → **Community plugins**
3. Click **Browse**
4. Search **Local REST API**
5. Click **Install**
6. Click **Enable**

### Configure Plugin

1. Go to **Settings** → **Local REST API**
2. **Recommended: Do NOT set API Key** (leave it empty for simplicity and security)
3. Note down the **Port** (default: 27123)

### Configuration

⚠️ **Security Notice**: Do NOT store API Key in `config.json`! Use environment variables or keychain instead.

**Recommended Method: Do NOT use API Key (simplest and safest)**

Set in `config.json` (without API key):

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

**If you must use API Key authentication**, please use environment variable:

```bash
# Linux/Mac
export OBSIDIAN_API_KEY="your-api-key"

# Windows (PowerShell)
$env:OBSIDIAN_API_KEY="your-api-key"
```

Then read from code:

```python
import os

api_key = os.getenv("OBSIDIAN_API_KEY")  # Read from environment variable
```

### Operation Examples

#### 1. Create Note

```python
import requests
import os

api_url = config["obsidian_api_url"]
api_key = os.getenv("OBSIDIAN_API_KEY")  # Read from environment variable

headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"
headers["Content-Type"] = "application/json"

# Create note
data = {
    "content": "# Webpage Title\n\nThis is content...",
    "path": "unorganized-search-content/2026-05-05/webpage-title.md"
}

response = requests.post(f"{api_url}/vault/create", headers=headers, json=data)
```

#### 2. Read Note

```python
import requests
import os

api_url = config["obsidian_api_url"]
api_key = os.getenv("OBSIDIAN_API_KEY")  # Read from environment variable

headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

# Read note
response = requests.get(f"{api_url}/vault/unorganized-search-content/2026-05-05/webpage-title.md", headers=headers)
content = response.text
```

#### 3. Update Note

```python
import requests
import os

api_url = config["obsidian_api_url"]
api_key = os.getenv("OBSIDIAN_API_KEY")  # Read from environment variable

headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"
headers["Content-Type"] = "application/json"

# Update note
data = {
    "content": "# Updated title\n\nThis is updated content..."
}

response = requests.post(f"{api_url}/vault/update", headers=headers, json=data)
```

#### 4. Delete Note

⚠️ **Security Notice**: Delete operation requires explicit user confirmation!

```python
import requests
import os

api_url = config["obsidian_api_url"]
api_key = os.getenv("OBSIDIAN_API_KEY")  # Read from environment variable

headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

# ⚠️ Confirm before deleting
if user_confirmed("Confirm to delete this note?"):
    # Delete note
    response = requests.delete(f"{api_url}/vault/delete", headers=headers, params={"path": "unorganized-search-content/2026-05-05/webpage-title.md"})
    print("Note deleted")
```

---

## Bidirectional Links

One of Obsidian's powerful features is bidirectional links. Use `[[note name]]` in Markdown files to create links.

### Example

```markdown
# Webpage Title

## Related Notes

- [[AI Overview]]
- [[Machine Learning Basics]]
- [[search-rules]]
```

When you open the `[[AI Overview]]` note, Obsidian will automatically display all other notes that link to this note.

---

## Tag System

Obsidian supports using `#tag` to categorize notes.

### Example

```markdown
# Webpage Title

## Tags

#AI #MachineLearning #PendingConfirmation #Important
```

You can view all tags and corresponding notes in Obsidian's **Tags pane**.

---

## Notes

⚠️ **Security Notice**:
1. **Vault Path Verification**: Before use, ensure `vault_path` is set correctly to avoid unauthorized file access
2. **Path Whitelist**: All file operations will verify if the path is within the Vault directory
3. **User Confirmation**: Sensitive operations (e.g., deleting files) require explicit user confirmation
4. **Credential Protection**: Obsidian API Key is **NOT stored to disk**, only stored in memory (environment variable)
5. **File Backup**: Recommend regular backup of Vault directory

## Security Code Example

```python
import os
from pathlib import Path

# Path verification function
def validate_vault_path(vault_path, target_path):
    """Verify target path is within Vault directory"""
    vault_abs = Path(vault_path).resolve()
    target_abs = Path(target_path).resolve()
    
    # Check if target path is within Vault directory
    try:
        target_abs.relative_to(vault_abs)
        return True
    except ValueError:
        raise SecurityError(f"Path {target_path} is not within allowed Vault directory!")

# Verify before use
vault_path = config["vault_path"]
target_file = os.path.join(vault_path, "search-url-library", "whitelist", "example.com.md")

# Verify path
validate_vault_path(vault_path, target_file)

# Safe read file
with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()
```

1. **Vault Path**: Ensure `vault_path` is configured correctly
2. **File Encoding**: Always use UTF-8 encoding
3. **Special Characters in Filenames**: Avoid special characters (such as `/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`)
4. **Method A**: After modifying files, need to manually refresh Obsidian to see updates
5. **Method B**: Need to install and enable Obsidian Local REST API plugin in advance
6. **API Security**: If API Key is set, please keep it secure (but recommended to use environment variable, do not write in config.json)
7. **File Backup**: Recommend regular backup of Vault directory

---

## Reference Resources

- [Obsidian Official Documentation](https://help.obsidian.md/)
- [Obsidian Local REST API Plugin](https://github.com/coddingtonbear/obsidian-local-rest-api)
- [Obsidian Markdown Syntax](https://help.obsidian.md/Editing+and+formatting/Basic+formatting+syntax)
