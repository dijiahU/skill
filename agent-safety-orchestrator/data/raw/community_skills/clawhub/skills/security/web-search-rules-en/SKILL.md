---
name: "web-search-rules-en"
description: "Web search rules management skill with multi-platform support (IMA, Tencent Docs, Obsidian, NotebookLM). Automatically manages search URL library (whitelist, blacklist, uncategorized), temporarily stores search content, and organizes/archives after user confirmation. ⚠️ Please read SECURITY.md before use."
agent_created: true
---

# Web Search Rules Skill

> **⚠️ Security Notice**: This skill supports multi-platform integration. Some features require file system access and browser automation permissions. Before using, please read [`SECURITY.md`](./SECURITY.md) for security considerations.

A web search rules management skill that implements intelligent URL filtering and content management workflows. Supports multiple knowledge base platforms, allowing users to choose freely.

## Core Features

1. **Multi-platform Support**: Supports IMA Knowledge Base, Tencent Docs, Obsidian, NotebookLM, and other platforms
2. **URL Library Management**: Maintains "Search URL Library", recording whitelist, blacklist, and uncategorized URLs
3. **Content Staging**: Uses "Unorganized Search Content" to temporarily store search results
4. **Intelligent Filtering**: Automatically filters search results based on whitelist/blacklist
5. **User Confirmation**: Asks for user input on new URLs before deciding categorization
6. **Content Archiving**: Organizes and saves confirmed content to target knowledge base

## Knowledge Base Platform Selection

### Supported Platforms

1. **IMA Knowledge Base** (`ima`)
   - Uses `ima-skill` for operations.
   - Suitable for: Scenarios requiring AI search and knowledge graphs
   - Features: Note management, knowledge base operations, file uploads

2. **Tencent Docs** (`tencent-docs`)
   - Uses `tencent-docs` skill for operations.
   - Suitable for: Scenarios requiring collaborative editing and online preview
   - Features: Online documents, smart tables, mind maps

3. **Obsidian** (`obsidian`)
   - Uses file system operations (Recommended) or Obsidian Local REST API plugin
   - Suitable for: Local knowledge management, Markdown native support, bidirectional links
   - Features: Markdown editing, bidirectional links, tag system, local storage
   - Operation methods:
     - **Method A**: Direct Vault file system operation (Simpler, no dependencies)
     - **Method B**: Through Obsidian Local REST API plugin (Requires plugin installation)

4. **NotebookLM** (`notebooklm`)
   - Uses browser automation (`playwright-cli` or `agent-browser`) for operations
   - Suitable for: Scenarios requiring AI-assisted analysis, Google ecosystem users
   - Features: AI summary, automatic Q&A, source management, Google Drive integration
   - Operation methods:
     - **Method A (Recommended)**: Browser automation (using `playwright-cli` or `agent-browser`)
     - **Method B**: Through Google Drive API indirect integration (NotebookLM can import Drive files)

5. **Other Platforms** (`custom`)
   - User-defined platforms
   - Requires API or operation methods to be provided

### Platform Selection Workflow

⚠️ **Security Notice**: After selecting a platform, the system will save configuration to `~/.workbuddy/skills/web-search-rules-en/config.json`. Please ensure your Vault path is set correctly to avoid unauthorized file access.

When user uses for the first time, ask and record user's knowledge base platform preference:

```
Ask user:
"Which platform would you like to use to manage search rules and content?"

Options:
1. IMA Knowledge Base (Recommended) - Supports AI search and knowledge graphs
2. Tencent Docs - Supports collaborative editing and online preview
3. Obsidian - Local Markdown knowledge management, supports bidirectional links
4. NotebookLM - Google AI-assisted research tool
5. Other platform - Please specify platform name

After user selects, record the selection to configuration file:
`~/.workbuddy/skills/web-search-rules-en/config.json`

⚠️ Security verification:
- Obsidian: System will verify Vault path is valid and allowed
- NotebookLM: Requires manual login to Google Account, system does not store credentials
```

## Preparations

### Check and Create Necessary Knowledge Bases

Based on user's selected platform, check and create two knowledge bases:

1. **Search URL Library** (`search-url-library`)
   - Purpose: Records search rules, URL staging list (uncategorized, whitelist, or blacklist), whitelist and blacklist
   - Structure:
     ```
     Whitelist/
     ├── URL1
     ├── URL2
     └── ...
     Blacklist/
     ├── URL1
     ├── URL2
     └── ...
     Uncategorized/
     ├── URL1
     ├── URL2
     └── ...
     ```

2. **Unorganized Search Content** (`unorganized-search-content`)
   - Purpose: Temporarily stores web content after search
   - Structure: Organized by search date
     ```
     2026-05-05/
     ├── Webpage Title 1.md
     ├── Webpage Title 2.md
     └── ...
     ```

**Platform-specific Operations**:

- **IMA Knowledge Base**: Use `ima-skill` to check and create
- **Tencent Docs**: Use `tencent-docs` skill to check and create
- **Obsidian**:
  - **Method A (Recommended)**: Directly create folders and files in Vault file system
    - Check Vault path (read from config file or environment variable)
    - Create `search-url-library/` and `unorganized-search-content/` folders
    - Use Markdown format to store data
  - **Method B**: Through Obsidian Local REST API plugin
    - Need to install and enable Obsidian Local REST API plugin first
    - Use HTTP API to create, read, update notes
- **NotebookLM**:
  - **Method A (Recommended)**: Use browser automation (`playwright-cli` or `agent-browser`)
    - Automatically log in to Google account
    - Upload files or add webpage links
    - Wait for AI processing to complete
  - **Method B**: Through Google Drive API indirect integration
    - Upload files to Google Drive
    - Import Drive files in NotebookLM
- **Other Platforms**: Based on operation methods provided by user

## Search Workflow

### Step 1: Parse Search Request

Extract from user request:
- Search keywords
- Target knowledge base (where content will be ultimately saved)
- Knowledge base platform (read from config file or user-specified)
- Other search parameters (time range, source, etc.)

### Step 2: Load URL Library

Based on user's selected platform, read from "Search URL Library":
- Whitelist
- Blacklist
- Uncategorized list

If unable to read or file doesn't exist, prompt user and assist in creation.

### Step 3: Execute Search

Use appropriate search tools (e.g., `wechat-article-search`, `web_search`, `web_fetch`, etc.) to execute search.

### Step 4: Filter Search Results

Classify each search result:

```
For each search result:
  1. Extract URL
  2. If URL is in whitelist:
     → Mark as "Auto-approved"
  3. If URL is in blacklist:
     → Mark as "Auto-filtered", skip
  4. If URL is in uncategorized or not in any list:
     → Mark as "Pending confirmation"
```

### Step 5: Stage Pending Content

Temporarily store all "Pending confirmation" and "Auto-approved" webpage content to "Unorganized Search Content":

**Platform-specific Operations**:

- **IMA Knowledge Base**: Use `ima-skill` to upload files
- **Tencent Docs**: Use `tencent-docs` skill to create documents
- **Obsidian**:
  - **Method A (Recommended)**: Directly create Markdown files in Vault
    - File path: `{vault_path}/unorganized-search-content/{date}/{title}.md`
    - Use Markdown format to write content
  - **Method B**: Create notes through Obsidian Local REST API
- **NotebookLM**:
  - **Method A (Recommended)**: Use browser automation to upload
    - Use `playwright-cli` or `agent-browser` to open NotebookLM
    - Upload files or add webpage links
    - Wait for AI processing to complete
  - **Method B**: Upload to Google Drive, then import in NotebookLM
- **Other Platforms**: Based on operation methods provided by user

```
File format:
# Webpage Title

- URL: <url>
- Publish time: <date>
- Source: <source>
- Status: Pending confirmation / Auto-approved
- Search keywords: <keywords>

## Content Summary

<content_summary>

## Full Content

<full_content>
```

### Step 6: Ask User

List all "Pending confirmation" webpages and display to user:

```
Found <N> new URLs needing confirmation:

1. [Webpage Title 1](URL1)
   - Source: <source>
   - Summary: <brief_summary>

2. [Webpage Title 2](URL2)
   - Source: <source>
   - Summary: <brief_summary>

...

Please specify:
- Which URLs should be added to whitelist? (Content can be saved directly)
- Which URLs should be added to blacklist? (Will be automatically filtered in future searches)
- Which URLs' content needs to be saved? (Save to target knowledge base)
```

### Step 7: Update URL Library

Based on user feedback, update "Search URL Library":

- Add user-confirmed whitelist URLs to whitelist file
- Add user-confirmed blacklist URLs to blacklist file
- Add user-undecided URLs to uncategorized file

**Platform-specific Operations**:

- **IMA Knowledge Base**: Use `ima-skill` to update files
- **Tencent Docs**: Use `tencent-docs` skill to update documents
- **Obsidian**:
  - **Method A (Recommended)**: Directly operate Markdown files in Vault
    - File path: `{vault_path}/search-url-library/{category}/{url}.md`
    - Use Markdown format to record URL information
  - **Method B**: Update notes through Obsidian Local REST API
- **NotebookLM**:
  - **Method A (Recommended)**: Use browser automation to update
    - Use `playwright-cli` or `agent-browser` to open NotebookLM
    - Update source list
  - **Method B**: Update files through Google Drive API
- **Other Platforms**: Based on operation methods provided by user

Format:
```
# Whitelist

## Addition Time | URL | Addition Reason

2026-05-05 19:30 | https://example.com/article1 | User confirmed, high-quality content
```

### Step 8: Organize and Archive Content

⚠️ **Security Notice**:
1. **User explicit confirmation required before deleting**
2. **Recommend to enable backup/version history**
3. **Avoid bulk cleanup unless user explicitly approves**

For webpage content that user confirmed to save:

1. Read from "Unorganized Search Content"
2. Organize content according to target knowledge base format requirements
3. Save to target knowledge base
4. **⚠️ User confirmation required before deleting**: Delete processed content from "Unorganized Search Content"

**Platform-specific Operations**:

- **IMA Knowledge Base**: Use `ima-skill` to operate
- **Tencent Docs**: Use `tencent-docs` skill to operate
- **Obsidian**:
  - **Method A (Recommended)**: Directly operate Markdown files in Vault
    - Read Markdown files from `unorganized-search-content/`
    - Move to target knowledge base folder after processing
    - Use Markdown format, supports bidirectional links
  - **Method B**: Operate through Obsidian Local REST API
- **NotebookLM**:
  - **Method A (Recommended)**: Use browser automation to upload
    - Use `playwright-cli` or `agent-browser` to open NotebookLM
    - Upload files or add webpage links
    - AI automatically processes and generates summary
  - **Method B**: Upload to Google Drive, then import in NotebookLM
- **Other Platforms**: Based on operation methods provided by user

### Step 9: Generate Search Report

Provide search result summary to user:

```
Search Completion Report
====================

Search keywords: <keywords>
Search time: <timestamp>
Platform used: <platform>

Result statistics:
- Total found: <total> results
- Auto-approved by whitelist: <whitelist_count> items
- Auto-filtered by blacklist: <blacklist_count> items
- User confirmed to save: <saved_count> items
- User discarded: <discarded_count> items

URL library updates:
- New whitelist: <new_whitelist_count> items
- New blacklist: <new_blacklist_count> items

Saved content location:
- Knowledge base platform: <platform>
- Knowledge base: <target_knowledge_base>
- Number of files: <folder_path>
```

## Configuration File

### config.json

After user selects platform for the first time, create configuration file to record user preferences:

```json
{
  "platform": "ima",
  "search_url_library": "Search URL Library",
  "unorganized_content": "Unorganized Search Content",
  "auto_create": true,
  "last_used": "2026-05-05 22:30:00"
}
```

**Field Description**:
- `platform`: Knowledge base platform (ima / tencent-docs / obsidian / notebooklm / custom)
- `search_url_library`: Name or ID of Search URL Library
- `unorganized_content`: Name or ID of Unorganized Search Content
- `auto_create`: Whether to automatically create necessary knowledge bases
- `last_used`: Last used time

## Exception Handling

### Knowledge Base Does Not Exist

1. Prompt user "Search URL Library" does not exist
2. Ask whether to create
3. If user agrees, use corresponding skill to create knowledge base and initialize structure based on platform selection

### Search Tool Failure

1. Try using backup search tools
2. If all tools fail, prompt user and suggest alternative solutions

### User Long-time No Response

1. Keep all "Pending confirmation" webpages in "Unorganized Search Content"
2. Record search status
3. Prompt user can continue later

### Platform Operation Failure

1. Determine failure cause based on error message
2. Prompt user and suggest solutions
3. If platform does not support certain features, suggest user to switch to other platform

## Advanced Features

### Rule Suggestions

Automatically suggest rules based on user's historical decisions:

```
Based on your historical decisions, the system suggests the following rules:

1. Domain rule: All webpages from <domain> should be added to whitelist
2. Keyword rule: Webpages with title containing <keyword> are usually valuable
3. Author rule: Articles published by <author> are of high quality

Do you want to apply these rules?
```

### Batch Operations

Support batch confirmation and batch operations:

```
Found 10 webpages from the same domain, do you want to:
1. Add all to whitelist
2. Add all to blacklist
3. Confirm one by one
```

### Platform Switching

If user wants to switch knowledge base platform:

```
Ask user:
"Which knowledge base platform do you want to switch to?"

Options:
1. IMA Knowledge Base
2. Tencent Docs
3. Obsidian
4. NotebookLM
5. Other platform

After switching, need to:
1. Reconfigure knowledge base
2. Migrate existing URL library and staged content (optional)
3. Update configuration file
```

## Notes

1. **Privacy Protection**: Temporarily stored webpage content may contain sensitive information, ensure access permissions of "Unorganized Search Content" are set correctly
2. **Regular Cleaning**: Recommend regular cleaning of expired content in "Unorganized Search Content"
3. **URL Library Maintenance**: Regularly check URL library, remove invalid URLs
4. **User Confirmation**: Always ask for user confirmation before updating URL library and saving content
5. **Platform Compatibility**: Features may differ across platforms, need to adjust workflow according to actual situation
6. **Obsidian Specific**:
   - Ensure Vault path is configured correctly
   - If using Obsidian Local REST API, need to install and enable plugin in advance
   - Recommend using Method A (direct file operation) to avoid plugin dependency
7. **NotebookLM Specific**:
   - Browser automation requires stable network connection
   - Need to log in to Google account in advance
   - Consider using Google Drive API as backup solution

## References

- IMA skill usage instructions
- Tencent Docs skill usage instructions
- Obsidian usage instructions (File system operation / Local REST API)
- NotebookLM usage instructions (Browser automation / Google Drive API)
- Web search tool documentation
- Knowledge base management best practices

## Additional Reference Files

This skill includes the following reference files, load as needed:

- `references/ima-operations.md` - IMA Knowledge Base operation details, including file structure, format specifications, and operation examples
- `references/tencent-docs-operations.md` - Tencent Docs operation details, including document creation, editing, and management methods
- `references/obsidian-operations.md` - Obsidian operation details, including Vault file system operations and Local REST API operation methods
- `references/notebooklm-operations.md` - NotebookLM operation details, including browser automation and Google Drive API integration methods
- `references/examples.md` - Complete usage scenario examples, including basic search, rule suggestions, batch operations, and regular maintenance
- `references/platform-comparison.md` - Platform feature comparison table to help users choose suitable platform

When encountering complex platform operations, please read the corresponding reference file first to get detailed operation guidance. When need to explain workflow to user, can refer to examples in `references/examples.md`.
