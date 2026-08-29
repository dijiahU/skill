---
name: "web-search-rules"
description: "搜尋網頁時的規則管理技能。支持多種知識庫平台（IMA、騰訊文檔、Obsidian、NotebookLM），自動管理搜尋網址庫（白名單、黑名單、未分類），暫存搜尋內容，並在用戶確認後整理歸檔。⚠️ 使用前請閱讀 SECURITY.md。"
agent_created: true
---

# Web Search Rules Skill

> **⚠️ 安全提醒**：本技能支援多平台整合，某些功能需要檔案系統存取和瀏覽器自動化權限。在使用前，請先閱讀 [`SECURITY.md`](./SECURITY.md) 了解安全注意事項。

搜尋網頁時的規則管理技能，實現智能的網址過濾和內容管理流程。支援多種知識庫平台，讓用戶自由選擇。

## 核心功能

1. **多平台支持**：支持 IMA 知識庫、騰訊文檔、或其他知識庫平台
2. **網址庫管理**：維護「搜尋網址庫」，記錄白名單、黑名單和未分類網址
3. **內容暫存**：使用「未整理搜尋內容」暫存搜尋結果
4. **智能過濾**：根據白名單/黑名單自動過濾搜尋結果
5. **用戶確認**：對新網址諮詢用戶意見後再決定分類
6. **內容歸檔**：將確認的內容整理並保存到目標知識庫

## 知識庫平台選擇

### 支持的平台

1. **IMA 知識庫** (`ima`)
   - 使用 `ima-skill` 進行操作
   - 適合：需要 AI 搜索、知識圖譜的場景
   - 功能：筆記管理、知識庫操作、文件上傳

2. **騰訊文檔** (`tencent-docs`)
   - 使用 `tencent-docs` skill 進行操作
   - 適合：需要協作編輯、在線預覽的場景
   - 功能：在線文檔、智能表格、思維導圖

3. **Obsidian** (`obsidian`)
   - 使用文件系統直接操作（推薦）或 Obsidian Local REST API 插件
   - 適合：本地化知識管理、Markdown 原生支持、雙向鏈接
   - 功能：Markdown 編輯、雙向鏈接、標籤系統、本地存儲
   - 操作方式：
     - **方案 A**：直接操作 Vault 文件夾（更簡單、無依賴）
     - **方案 B**：通過 Obsidian Local REST API 插件（需要安裝插件）

4. **NotebookLM** (`notebooklm`)
   - 使用瀏覽器自動化（`playwright-cli` 或 `agent-browser`）進行操作
   - 適合：需要 AI 輔助分析的場景、Google 生態系統用戶
   - 功能：AI 摘要、自動問答、來源管理、Google Drive 集成
   - 操作方式：
     - **方案 A**：瀏覽器自動化（推薦，使用 `playwright-cli` 或 `agent-browser`）
     - **方案 B**：通過 Google Drive API 間接集成（NotebookLM 可以導入 Drive 文件）

5. **其他平台** (`custom`)
   - 用戶自定義平台
   - 需要提供 API 或操作方式

### 平台選擇流程

在用戶首次使用時，詢問並記錄用戶的知識庫平台偏好：

```
詢問用戶：
「請問您想要使用哪個平台來管理搜尋規則和內容？」

選項：
1. IMA 知識庫（推薦）- 支持 AI 搜索和知識圖譜
2. 騰訊文檔 - 支持協作編輯和在線預覽
3. Obsidian - 本地化 Markdown 知識管理，支持雙向鏈接
4. NotebookLM - Google AI 輔助研究工具
5. 其他平台 - 請指定平台名稱和操作方式

用戶選擇後，將選擇記錄到配置文件：
`~/.workbuddy/skills/web-search-rules/config.json`
```

## 前置準備

### 檢查並創建必要知識庫

根據用戶選擇的平台，檢查並創建兩個知識庫：

1. **搜尋網址庫** (`search-url-library`)
   - 用途：記錄搜尋規則、網址的暫存名單（未分類白名單還是黑名單）、白名單和黑名單
   - 結構：
     ```
     白名單/
     ├── 網址1
     ├── 網址2
     └── ...
     黑名單/
     ├── 網址1
     ├── 網址2
     └── ...
     未分類/
     ├── 網址1
     ├── 網址2
     └── ...
     ```

2. **未整理搜尋內容** (`unorganized-search-content`)
   - 用途：暫存搜尋後的網頁內容
   - 結構：按搜尋日期組織
     ```
     2026-05-05/
     ├── 網頁標題1.md
     ├── 網頁標題2.md
     └── ...
     ```

**平台特定操作**：

- **IMA 知識庫**：使用 `ima-skill` 檢查並創建
- **騰訊文檔**：使用 `tencent-docs` skill 檢查並創建
- **Obsidian**：
  - **方案 A（推薦）**：直接在 Vault 文件夾中創建文件夾和文件
    - 檢查 Vault 路徑（從配置文件或環境變量讀取）
    - 創建 `search-url-library/` 和 `unorganized-search-content/` 文件夾
    - 使用 Markdown 格式存儲數據
  - **方案 B**：通過 Obsidian Local REST API 插件操作
    - 需要先安裝並啟用 Obsidian Local REST API 插件
    - 使用 HTTP API 創建、讀取、更新筆記
- **NotebookLM**：
  - **方案 A（推薦）**：使用瀏覽器自動化（`playwright-cli` 或 `agent-browser`）
    - 自動登錄 Google 帳號
    - 上傳文件或添加網頁鏈接
    - 等待 AI 處理完成
  - **方案 B**：通過 Google Drive API 間接集成
    - 將文件上傳到 Google Drive
    - 在 NotebookLM 中導入 Drive 文件
- **其他平台**：根據用戶提供的操作方式進行

## 搜尋工作流程

### 步驟 1：解析搜尋請求

從用戶請求中提取：
- 搜尋關鍵詞
- 目標知識庫（內容最終要保存到的知識庫）
- 知識庫平台（從配置文件讀取或用戶指定）
- 其他搜尋參數（時間範圍、來源等）

### 步驟 2：載入網址庫

根據用戶選擇的平台，從「搜尋網址庫」中讀取：
- 白名單列表
- 黑名單列表
- 未分類列表

如果無法讀取或文件不存在，提示用戶並協助創建。

### 步驟 3：執行搜尋

使用適當的搜尋工具（如 `wechat-article-search`、`web_search`、`web_fetch` 等）執行搜尋。

### 步驟 4：過濾搜尋結果

對每個搜尋結果進行分類：

```
對於每個搜尋結果：
  1. 提取網址
  2. 如果網址在白名單中：
     → 標記為「自動通過」
  3. 如果網址在黑名單中：
     → 標記為「自動過濾」，跳過
  4. 如果網址在未分類中或不在任何列表中：
     → 標記為「待確認」
```

### 步驟 5：暫存待確認內容

將所有「待確認」和「自動通過」的網頁內容暫存到「未整理搜尋內容」：

**平台特定操作**：

- **IMA 知識庫**：使用 `ima-skill` 上傳文件
- **騰訊文檔**：使用 `tencent-docs` skill 創建文檔
- **Obsidian**：
  - **方案 A（推薦）**：直接在 Vault 中創建 Markdown 文件
    - 文件路徑：`{vault_path}/unorganized-search-content/{date}/{title}.md`
    - 使用 Markdown 格式編寫內容
  - **方案 B**：通過 Obsidian Local REST API 創建筆記
- **NotebookLM**：
  - **方案 A（推薦）**：使用瀏覽器自動化上傳
    - 使用 `playwright-cli` 或 `agent-browser` 打開 NotebookLM
    - 上傳文件或添加網頁鏈接
    - 等待 AI 處理完成
  - **方案 B**：上傳到 Google Drive，然後在 NotebookLM 中導入
- **其他平台**：根據用戶提供的操作方式進行

```
文件格式：
# 網頁標題

- 網址：<url>
- 發布時間：<date>
- 來源：<source>
- 狀態：待確認 / 自動通過
- 搜尋關鍵詞：<keywords>

## 內容摘要

<content_summary>

## 完整內容

<full_content>
```

### 步驟 6：諮詢用戶

列出所有「待確認」的網頁，向用戶展示：

```
找到 <N> 個新網址需要確認：

1. [網頁標題1](網址1)
   - 來源：<source>
   - 摘要：<brief_summary>

2. [網頁標題2](網址2)
   - 來源：<source>
   - 摘要：<brief_summary>

...

請問：
- 哪些網址應該加入白名單？（可以直接保存內容）
- 哪些網址應該加入黑名單？（以後搜尋時自動過濾）
- 哪些網址的內容需要保存？（保存到目標知識庫）
```

### 步驟 7：更新網址庫

根據用戶的反饋，更新「搜尋網址庫」：

- 將用戶確認的白名單網址添加到白名單文件
- 將用戶確認的黑名單網址添加到黑名單文件
- 將用戶未決定的網址添加到未分類文件

**平台特定操作**：

- **IMA 知識庫**：使用 `ima-skill` 更新文件
- **騰訊文檔**：使用 `tencent-docs` skill 更新文檔
- **Obsidian**：
  - **方案 A（推薦）**：直接操作 Vault 中的 Markdown 文件
    - 文件路徑：`{vault_path}/search-url-library/{category}/{url}.md`
    - 使用 Markdown 格式記錄網址信息
  - **方案 B**：通過 Obsidian Local REST API 更新筆記
- **NotebookLM**：
  - **方案 A（推薦）**：使用瀏覽器自動化更新
    - 使用 `playwright-cli` 或 `agent-browser` 打開 NotebookLM
    - 更新來源列表
  - **方案 B**：通過 Google Drive API 更新文件
- **其他平台**：根據用戶提供的操作方式進行

格式：
```
# 白名單

## 添加時間 | 網址 | 添加原因

2026-05-05 19:30 | https://example.com/article1 | 用戶確認，內容優質
```

### 步驟 8：整理並歸檔內容

⚠️ **安全提醒**：
1. **刪除前需要用戶顯式確認**
2. **建議啟用備份/版本歷史**
3. **避免批量清理，除非用戶明確批准**

將用戶確認需要保存的網頁內容：

1. 從「未整理搜尋內容」中讀取
2. 根據目標知識庫的格式要求整理內容
3. 保存到目標知識庫
4. **⚠️ 刪除前需要用戶確認**：從「未整理搜尋內容」中刪除已處理的內容

**平台特定操作**：

- **IMA 知識庫**：使用 `ima-skill` 操作
- **騰訊文檔**：使用 `tencent-docs` skill 操作
- **Obsidian**：
  - **方案 A（推薦）**：直接操作 Vault 中的 Markdown 文件
    - 從 `unorganized-search-content/` 讀取 Markdown 文件
    - 處理後移動到目標知識庫文件夾
    - 使用 Markdown 格式，支持雙向鏈接
  - **方案 B**：通過 Obsidian Local REST API 操作
- **NotebookLM**：
  - **方案 A（推薦）**：使用瀏覽器自動化上傳
    - 使用 `playwright-cli` 或 `agent-browser` 打開 NotebookLM
    - 上傳文件或添加網頁鏈接
    - AI 自動處理並生成摘要
  - **方案 B**：上傳到 Google Drive，然後在 NotebookLM 中導入
- **其他平台**：根據用戶提供的操作方式進行

### 步驟 9：生成搜尋報告

向用戶提供搜尋結果摘要：

```
搜尋完成報告
====================

搜尋關鍵詞：<keywords>
搜尋時間：<timestamp>
使用平台：<platform>

結果統計：
- 總共找到：<total> 個結果
- 白名單自動通過：<whitelist_count> 個
- 黑名單自動過濾：<blacklist_count> 個
- 用戶確認保存：<saved_count> 個
- 用戶放棄：<discarded_count> 個

網址庫更新：
- 新增白名單：<new_whitelist_count> 個
- 新增黑名單：<new_blacklist_count> 個

已保存內容位置：
- 知識庫平台：<platform>
- 知識庫：<target_knowledge_base>
- 文件數量：<folder_path>
```

## 配置文件

### config.json

在用戶首次選擇平台後，創建配置文件以記錄用戶偏好：

```json
{
  "platform": "ima",
  "search_url_library": "搜尋網址庫",
  "unorganized_content": "未整理搜尋內容",
  "auto_create": true,
  "last_used": "2026-05-05 22:30:00"
}
```

**字段說明**：
- `platform`：知識庫平台（ima / tencent-docs / custom）
- `search_url_library`：搜尋網址庫的名稱或 ID
- `unorganized_content`：未整理搜尋內容的名稱或 ID
- `auto_create`：是否自動創建必要的知識庫
- `last_used`：最後使用時間

## 例外處理

### 知識庫不存在

1. 提示用戶「搜尋網址庫」不存在
2. 詢問是否要創建
3. 如果用戶同意，根據平台選擇使用相應的 skill 創建知識庫並初始化結構

### 搜尋工具失敗

1. 嘗試使用備用搜尋工具
2. 如果所有工具都失敗，提示用戶並建議替代方案

### 用戶長時間未回應

1. 將所有「待確認」的網頁保留在「未整理搜尋內容」中
2. 記錄搜尋狀態
3. 提示用戶可以稍後繼續

### 平台操作失敗

1. 根據錯誤消息判斷失敗原因
2. 提示用戶並建議解決方案
3. 如果平台不支持某些功能，建議用戶切換到其他平台

## 進階功能

### 規則建議

根據用戶的歷史決策，自動建議規則：

```
根據您的歷史決策，系統建議以下規則：

1. 網域規則：所有來自 <domain> 的網頁都應該加入白名單
2. 關鍵詞規則：標題包含 <keyword> 的網頁通常是有價值的
3. 作者規則：<author> 發布的文章質量較高

是否要應用這些規則？
```

### 批量操作

支持批量確認和批量操作：

```
找到 10 個來自同一網域的網頁，是否要：
1. 全部加入白名單
2. 全部加入黑名單
3. 逐個確認
```

### 平台切換

如果用戶想要切換知識庫平台：

```
詢問用戶：
「請問您想要切換到哪個知識庫平台？」

選項：
1. IMA 知識庫
2. 騰訊文檔
3. Obsidian
4. NotebookLM
5. 其他平台

切換後，需要：
1. 重新配置知識庫
2. 遷移現有的網址庫和暫存內容（可選）
3. 更新配置文件
```

## 注意事項

1. **隱私保護**：暫存的網頁內容可能包含敏感信息，確保「未整理搜尋內容」的訪問權限設置正確
2. **定期清理**：建議定期清理「未整理搜尋內容」中的過期內容
3. **網址庫維護**：定期檢查網址庫，移除失效的網址
4. **用戶確認**：始終在用戶確認後再更新網址庫和保存內容
5. **平台兼容性**：不同平台的功能可能有所差異，需要根據實際情況調整操作流程
6. **Obsidian 特定**：
   - 確保 Vault 路徑正確配置
   - 如果使用 Obsidian Local REST API，需要預先安裝並啟用插件
   - 建議使用方案 A（直接操作文件）以避免插件依賴
7. **NotebookLM 特定**：
   - 瀏覽器自動化需要穩定的網路連接
   - 需要預先登錄 Google 帳號
   - 考慮使用 Google Drive API 作為備用方案

## 參考資料

- IMA skill 使用說明
- 騰訊文檔 skill 使用說明
- Obsidian 使用說明（文件系統操作 / Local REST API）
- NotebookLM 使用說明（瀏覽器自動化 / Google Drive API）
- 網頁搜尋工具文檔
- 知識庫管理最佳實踐

## 附加參考文件

本 skill 包含以下參考文件，根據需要載入：

- `references/ima-operations.md` - IMA 知識庫操作詳解，包含文件結構、格式規範和操作示例
- `references/tencent-docs-operations.md` - 騰訊文檔操作詳解，包含文檔創建、編輯和管理的操作方法
- `references/obsidian-operations.md` - Obsidian 操作詳解，包含 Vault 文件系統操作和 Local REST API 操作方法
- `references/notebooklm-operations.md` - NotebookLM 操作詳解，包含瀏覽器自動化和 Google Drive API 集成方法
- `references/examples.md` - 完整的使用場景示例，包含基本搜尋、規則建議、批量操作和定期維護等情境
- `references/platform-comparison.md` - 各平台功能對比表，幫助用戶選擇適合的平台

當遇到複雜的平台操作時，請先讀取相應的參考文件以獲取詳細的操作指導。當需要向用戶說明工作流程時，可以參考 `references/examples.md` 中的示例。
