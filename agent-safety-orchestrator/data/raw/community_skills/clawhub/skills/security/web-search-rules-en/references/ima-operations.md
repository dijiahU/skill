# IMA Knowledge Base Operations Reference

## Knowledge Base Management

### Check if Knowledge Base Exists

Use `ima-skill` to list all knowledge bases, check if target knowledge base exists.

### Create Knowledge Base

If knowledge base doesn't exist, use `ima-skill` to create:

```
Knowledge base name: Search URL Library
Description: Records search rules, URL staging list (uncategorized, whitelist, or blacklist), whitelist and blacklist

Knowledge base name: Unorganized Search Content
Description: Temporarily stores webpage content after search, organized by search date
```

## File Operations

### Search URL Library Structure

```
Search URL Library/
├── Whitelist.md
├── Blacklist.md
└── Uncategorized.md
```

#### Whitelist.md Format

```markdown
# Whitelist

## Addition Time | URL | Addition Reason | Category Tags

2026-05-05 19:30 | https://example.com/article1 | User confirmed, high-quality content | Tech, AI
2026-05-05 19:35 | https://blog.example.org/post1 | Authoritative source | Academic
```

#### Blacklist.md Format

```markdown
# Blacklist

## Addition Time | URL | Block Reason

2026-05-05 19:40 | https://spam.example.com | Low content quality
2026-05-05 19:45 | https://ads.example.org | Advertising content
```

#### Uncategorized.md Format

```markdown
# Uncategorized

## Discovery Time | URL | Notes

2026-05-05 19:50 | https://new.example.com/article | Pending user confirmation
```

### Unorganized Search Content Structure

```
Unorganized Search Content/
└── 2026-05-05/
    ├── Webpage Title 1.md
    ├── Webpage Title 2.md
    └── ...
```

#### Webpage Content File Format

```markdown
# Webpage Title

- URL: https://example.com/article
- Publish time: 2026-05-05
- Source: Source website name
- Status: Pending confirmation / Auto-approved
- Search keywords: AI, Machine Learning
- Staging time: 2026-05-05 19:30

## Content Summary

This is an article about...

## Full Content

<article_content>
```

## IMA Skill Call Examples

### Search Knowledge Base

```
Use IMA skill to search "Search URL Library", query if URL exists
```

### Upload File to Knowledge Base

```
Use IMA skill to upload file to "Unorganized Search Content" knowledge base
File path: /tmp/search_result_1.md
Target folder: 2026-05-05
```

### Delete File from Knowledge Base

```
Use IMA skill to delete processed file from "Unorganized Search Content"
File ID: xxx
```

## Notes

1. **Folder Structure**: Ensure organizing files by date for easy management and cleanup
2. **URL Deduplication**: Check if URL already exists in whitelist or blacklist before adding
3. **Regular Maintenance**: Recommend cleaning expired content from "Unorganized Search Content" monthly
4. **Permission Management**: Ensure access permissions for knowledge base are set correctly to avoid sensitive information leakage
