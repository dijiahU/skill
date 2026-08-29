# Tencent Docs Operations Reference#

## Knowledge Base Management#

### Check if Knowledge Base Exists#

Use `tencent-docs` skill to list all documents, check if target knowledge base exists.#

### Create Knowledge Base#

If knowledge base doesn't exist, use `tencent-docs` skill to create:#

```
Knowledge base name: Search URL Library#
Description: Records search rules, URL staging list (uncategorized, whitelist, or blacklist), whitelist and blacklist#

Knowledge base name: Unorganized Search Content#
Description: Temporarily stores webpage content after search, organized by search date#
```

## File Operations#

### Search URL Library Structure#

```
Search URL Library/#
├── Whitelist.md#
├── Blacklist.md#
└── Uncategorized.md#
```

#### Whitelist.md Format#

```markdown#
# Whitelist#

## Addition Time | URL | Addition Reason | Category Tags#

2026-05-05 19:30 | https://example.com/article1 | User confirmed, high-quality content | Tech, AI#
2026-05-05 19:35 | https://blog.example.org/post1 | Authoritative source | Academic#
```

#### Blacklist.md Format#

```markdown#
# Blacklist#

## Addition Time | URL | Block Reason#

2026-05-05 19:40 | https://spam.example.com | Low content quality#
2026-05-05 19:45 | https://ads.example.org | Advertising content#
```

#### Uncategorized.md Format#

```markdown#
# Uncategorized#

## Discovery Time | URL | Notes#

2026-05-05 19:50 | https://new.example.com/article | Pending user confirmation#
```

### Unorganized Search Content Structure#

```
Unorganized Search Content/#
└── 2026-05-05/#
    ├── Webpage Title 1.md#
    ├── Webpage Title 2.md#
    └── ...#
```

#### Webpage Content File Format#

```markdown#
# Webpage Title#

- URL: https://example.com/article#
- Publish time: 2026-05-05#
- Source: Source website name#
- Status: Pending confirmation / Auto-approved#
- Search keywords: AI, Machine Learning#
- Staging time: 2026-05-05 19:30#

## Content Summary#

This is an article about...#

## Full Content#

<article_content>#
```

## Tencent Docs Skill Call Examples#

### Search Documents#

```
Use tencent-docs skill to search "Search URL Library", query if URL exists#
```

### Create Document#

```
Use tencent-docs skill to create document to "Unorganized Search Content" knowledge base#
Document title: Webpage Title 1#
Document content: (Complete Markdown content)#
Target folder: 2026-05-05#
```

### Update Document#

```
Use tencent-docs skill to update "Search URL Library/Whitelist.md"#
Operation: Add new whitelist URL record at the end of document#
```

### Delete Document from Knowledge Base#

```
Use tencent-docs skill to delete processed document from "Unorganized Search Content"#
Document ID: xxx#
```

### List Folder Contents#

```
Use tencent-docs skill to list all documents in "Unorganized Search Content/2026-05-05/"#
```

## Tencent Docs Specific Features#

### Collaborative Editing#

Tencent Docs supports multi-person collaborative editing, suitable for team use:#

```
When creating "Search URL Library", you can set collaboration permissions:# 
- Can edit: Team members can add/modify URLs#
- Read-only: Team members can only view URL library#
```

### Online Preview#

Tencent Docs supports online preview, convenient for viewing staged webpage content:#

```
Use tencent-docs skill to get online preview link of document#
Document ID: xxx#
Return: Preview link (can be opened directly in browser)#
```

### Version History#

Tencent Docs automatically saves version history, can revert to previous versions:#

```
If you accidentally deleted a URL from whitelist, you can:# 
1. Use tencent-docs skill to view version history of document#
2. Find previous version#
3. Restore accidentally deleted content#
```

## Notes#

1. **Folder Structure**: Tencent Docs uses folders to organize documents, ensure organizing files by date for easy management and cleanup#
2. **URL Deduplication**: Check if URL already exists in whitelist or blacklist before adding#
3. **Regular Maintenance**: Recommend cleaning expired content from "Unorganized Search Content" monthly#
4. **Permission Management**: Ensure access permissions for knowledge base are set correctly to avoid sensitive information leakage#
5. **API Limitations**: Tencent Docs API may have rate limits, pay attention to control operation frequency#
