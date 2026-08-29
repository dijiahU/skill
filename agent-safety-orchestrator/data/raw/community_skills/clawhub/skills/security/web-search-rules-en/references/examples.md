# Web Search Rules Skill Usage Examples#

## Example 1: Basic Search Workflow#

### User Request#
```
Please help me search for WeChat official account articles about "AI Agent" and save to "Technology" knowledge base#
```

### Execution Workflow#

1. **Check Knowledge Base**#
   - Check if "Search URL Library" exists → Doesn't exist, prompt user to create#
   - Check if "Unorganized Search Content" exists → Doesn't exist, prompt user to create#

2. **After User Confirms Creation**#
   - Create "Search URL Library" knowledge base, initialize Whitelist.md, Blacklist.md, Uncategorized.md#
   - Create "Unorganized Search Content" knowledge base#

3. **Load URL Library**#
   - Read Whitelist.md → Get 5 URLs#
   - Read Blacklist.md → Get 3 URLs#
   - Read Uncategorized.md → Get 2 URLs#

4. **Execute Search**#
   - Use `wechat-article-search` skill to search "AI Agent"#
   - Found 10 articles#

5. **Filter Search Results**#
   - Article 1: URL in whitelist → Mark "Auto-approved"#
   - Article 2: URL in blacklist → Mark "Auto-filtered", skip#
   - Articles 3-10: Not in any list → Mark "Pending confirmation"#

6. **Stage Content**#
   - Save content of Articles 1, 3-10 to "Unorganized Search Content/2026-05-05/"#

7. **Ask User**#
   ```
   Found 8 new URLs needing confirmation:#
   
   1. [Article Title 3](URL3)#
      - Source: WeChat Official Account A#
      - Summary: Introduces basic concepts of AI Agent...#
   
   2. [Article Title 4](URL4)#
      - Source: WeChat Official Account B#
      - Summary: Discusses application scenarios of AI Agent...#
   
   ...#
   
   Please specify:# 
   - Which URLs should be added to whitelist?#
   - Which URLs should be added to blacklist?#
   - Which articles' content needs to be saved to "Technology" knowledge base?#
   ```

8. **User Response**#
   ```
   - URLs 3, 4, 5 added to whitelist#
   - URL 6 added to blacklist#
   - Content of URLs 3, 4, 5, 7, 8 saved to "Technology" knowledge base#
   ```

9. **Update URL Library**#
   - Update "Search URL Library/Whitelist.md", add URLs 3, 4, 5#
   - Update "Search URL Library/Blacklist.md", add URL 6#

10. **Organize and Archive Content**#
    - Read content of URLs 3, 4, 5, 7, 8 from "Unorganized Search Content"#
    - Organize format, add tags#
    - Save to "Technology" knowledge base#
    - Delete these files from "Unorganized Search Content"#

11. **Generate Report**#
    ```
    Search Completion Report#
    ===================#

    Search keywords: AI Agent#
    Search time: 2026-05-05 20:15#

    Result statistics:#
    - Total found: 10 results#
    - Auto-approved by whitelist: 1 item#
    - Auto-filtered by blacklist: 1 item#
    - User confirmed to save: 5 items#
    - User discarded: 3 items#

    URL library updates:#
    - New whitelist: 3 items#
    - New blacklist: 1 item#

    Saved content location:#
    - Knowledge base: Technology#
    - Number of files: 5#
    ```

## Example 2: Rule Suggestions#

### User Request#
```
Search for articles related to "Blockchain Technology"#
```

### Execution Workflow#

1. Complete search and filtering#
2. Stage content#
3. Ask user#

### User Confirmation Mode#

After multiple user confirmations, system learns rules:#

```
Based on your historical decisions, the system suggests the following rules:#

1. Domain rule: All articles from `Blockchain Frontier` official account should be added to whitelist#
2. Keyword rule: Articles with titles containing "Technical Principles" are usually valuable#
3. Source rule: Articles published by `Technology Daily` have high quality#

Do you want to apply these rules?#
- Yes: Apply rules and automatically categorize similar content#
- No: Continue manual confirmation#
- Custom: Modify rules before applying#
```

## Example 3: Batch Operations#

### User Request#
```
Search for content related to "Investment and Finance"#
```

### Execution Result#
```
Found 20 results, among which:#
- 15 from the same domain (investment-news.com)#
- 5 from other sources#

Do you want to:# 
1. Add all webpages from investement-news.com to whitelist#
2. Add all webpages from investement-news.com to blacklist#
3. Confirm each webpage one by one#
```

## Example 4: Regular Maintenance#

### User Request#
```
Clean up content from last month in "Unorganized Search Content"#
```

### Execution Workflow#

1. List folders of last month (2026-04) in "Unorganized Search Content"#
2. Display file statistics (quantity, size)#
3. Ask user whether to:# 
   - Delete all content from last month#
   - Only delete processed content#
   - Keep certain specific content#
   - Cancel operation#

## Example 5: Using Tencent Docs as Knowledge Base Platform#

### User Request#
```
Please use Tencent Docs as the knowledge base platform, help me search for WeChat official account articles about "Machine Learning", and save to "Academic" knowledge base#
```

### Execution Workflow#

1. **Select Platform**#
   ```
   Ask user: "Which platform would you like to use to manage search rules and content?"#
   
   User selects: "Tencent Docs"#
   
   Create configuration file `~/.workbuddy/skills/web-search-rules-en/config.json`:#
   ```json
   {
     "platform": "tencent-docs",
     "search-url-library": "Search URL Library",
     "unorganized-content": "Unorganized Search Content",
     "auto_create": true,
     "last_used": "2026-05-05 22:30:00"
   }
   ```
   
2. **Check Knowledge Base**#
   - Use `tencent-docs` skill to check if "Search URL Library" exists → Doesn't exist, prompt user to create#
   - Use `tencent-docs` skill to check if "Unorganized Search Content" exists → Doesn't exist, prompt user to create#
   
3. **After User Confirms Creation**#
   - Use `tencent-docs` skill to create "Search URL Library" knowledge base#
     - Create files "Whitelist.md", "Blacklist.md", "Uncategorized.md"#
   - Use `tencent-docs` skill to create "Unorganized Search Content" knowledge base#
   
4. **Load URL Library**#
   - Use `tencent-docs` skill to read "Whitelist.md" → Get 3 URLs#
   - Use `tencent-docs` skill to read "Blacklist.md" → Get 2 URLs#
   - Use `tencent-docs` skill to read "Uncategorized.md" → Get 1 URL#
   
5. **Execute Search**#
   - Use `wechat-article-search` skill to search "Machine Learning"#
   - Found 8 articles#
   
6. **Filter Search Results**#
   - Article 1: URL in whitelist → Mark "Auto-approved"#
   - Article 2: URL in blacklist → Mark "Auto-filtered", skip#
   - Articles 3-8: Not in any list → Mark "Pending confirmation"#
   
7. **Stage Content**#
   - Use `tencent-docs` skill to create files in "Unorganized Search Content/2026-05-05/"#
   - Save content of Articles 1, 3-8 as Markdown files#
   
8. **Ask User**#
   ```
   Found 6 new URLs needing confirmation:# 
   
   1. [Article Title 3](URL3)#
      - Source: WeChat Official Account C#
      - Summary: Introduces basic concepts of machine learning...#
   
   2. [Article Title 4](URL4)#
      - Source: WeChat Official Account D#
      - Summary: Discusses application scenarios of machine learning...#
   
   ...#
   
   Please specify:# 
   - Which URLs should be added to whitelist?#
   - Which URLs should be added to blacklist?#
   - Which articles' content needs to be saved to "Academic" knowledge base?#
   ```

9. **User Response**#
   ```
   - URLs 3, 4, 5 added to whitelist#
   - URL 6 added to blacklist#
   - Content of URLs 3, 4, 5, 7 saved to "Academic" knowledge base#
   ```

10. **Update URL Library**#
    - Use `tencent-docs` skill to update "Search URL Library/Whitelist.md", add URLs 3, 4, 5#
    - Use `tencent-docs` skill to update "Search URL Library/Blacklist.md", add URL 6#
    
11. **Organize and Archive Content**#
    - Use `tencent-docs` skill to read files in "Unorganized Search Content/2026-05-05/"#
    - Organize format, add tags#
    - Use `tencent-docs` skill to save to "Academic" knowledge base#
    - Use `tencent-docs` skill to delete these files from "Unorganized Search Content"#
    
12. **Generate Report**#
    ```
    Search Completion Report#
    ===================#

    Search keywords: Machine Learning#
    Search time: 2026-05-05 23:00#
    Platform used: Tencent Docs#

    Result statistics:#
    - Total found: 8 results#
    - Auto-approved by whitelist: 1 item#
    - Auto-filtered by blacklist: 1 item#
    - User confirmed to save: 4 items#
    - User discarded: 2 items#

    URL library updates:#
    - New whitelist: 3 items#
    - New blacklist: 1 item#

    Saved content location:#
    - Knowledge base platform: Tencent Docs#
    - Knowledge base: Academic#
    - Number of files: 4#
    ```

## Example 6: Platform Switching#

### User Request#
```
I want to switch from IMA Knowledge Base to Tencent Docs#
```

### Execution Workflow#

1. **Confirm Switch**#
   ```
   Ask user: "Are you sure you want to switch from IMA Knowledge Base to Tencent Docs?"#
   
   Note: Switching platforms may require manual data migration.#
   ```
   
2. **After User Confirmation**#
   ```
   Provide options:# 
   1. Migrate existing URL library and staged content#
   2. Don't migrate data, start fresh#
   
   User selects: "Migrate existing URL library and staged content"#
   ```
   
3. **Export IMA Data**#
   - Use IMA skill to export whitelist, blacklist, uncategorized data from "Search URL Library"#
   - Use IMA skill to export webpage content from "Unorganized Search Content"#
   
4. **Import to Tencent Docs**#
   - Use `tencent-docs` skill to create "Search URL Library" knowledge base#
   - Use `tencent-docs` skill to create "Whitelist.md", "Blacklist.md", "Uncategorized.md"#
   - Import exported data to these files#
   - Use `tencent-docs` skill to create "Unorganized Search Content" knowledge base#
   - Import exported webpage content#
   
5. **Update Configuration**#
   - Update `config.json`, change `platform` field to `tencent-docs`#
   - Update `search-url-library` and `unorganized-content` fields#
   
6. **Complete Switch**#
   ```
   Platform switch completed!#
   
   Original platform: IMA Knowledge Base#
   New platform: Tencent Docs#
   
   Migrated data:# 
   - Whitelist: 5 URLs#
   - Blacklist: 3 URLs#
   - Uncategorized: 2 URLs#
   - Staged content: 8 webpages#
   
   Future search operations will use Tencent Docs as the knowledge base platform.#
   ```

## Platform Feature Comparison Reference#

When helping users select a platform, you can refer to the detailed comparison table in `references/platform-comparison.md`.#

**Quick Suggestions**:#

- Choose **IMA Knowledge Base**, if:# 
  - Need AI search and intelligent recommendations#
  - Mainly store textual content#
  - Personal use#

- Choose **Tencent Docs**, if:# 
  - Need multi-person collaborative editing#
  - Need rich format support#
  - Need strong permission management#
