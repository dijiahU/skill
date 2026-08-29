# NotebookLM Operations Details

This document explains in detail how to use NotebookLM as a knowledge base platform.

## Overview

NotebookLM is an AI-assisted research tool launched by Google that can automatically summarize, Q&A, and analyze uploaded content. This skill supports two operation methods:

1. **Method A (Recommended)**: Using browser automation (`playwright-cli` or `agent-browser`)
2. **Method B**: Through Google Drive API indirect integration

---

## Method A: Browser Automation (Recommended)

### Advantages
- ✅ Directly operate NotebookLM Web interface
- ✅ Supports all NotebookLM features
- ✅ Does not require Google Drive API configuration
- ✅ Can process files in any format

### Disadvantages
- ❌ Requires stable network connection
- ❌ **Requires manual login to Google account (DO NOT store credentials!)**
- ❌ Browser automation may be slower

### Preparations

⚠️ **Security Notice**:
1. **DO NOT store Google account credentials**! Login manually each time.
2. **Use a separate browser profile** to avoid mixing with main browser.
3. **Limit OAuth scopes**, only authorize necessary permissions.

#### 1. Install Browser Automation Tool:

**Option 1**: `playwright-cli` (Recommended)

```bash
# ⚠️ Recommended: Use virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  (Windows)

# Install pinned versions (avoid supply chain attacks)
pip install playwright==1.44.0
playwright install chromium
```

**Option 2**: `agent-browser` skill
- Ensure `agent-browser` skill is installed
- Run in isolated environment

#### 2. Manual Login to Google Account:

⚠️ **Important**: **DO NOT** automate the login process in code!

```bash
# Manually open NotebookLM
# 1. Open browser
# 2. Visit https://notebooklm.google.com/
# 3. Manually login to Google account
# 4. Ensure you can upload files normally
```

#### 3. Configuration (DO NOT include credentials!):

Set in `config.json`:

```json
{
  "platform": "notebooklm",
  "method": "browser-automation",
  "notebook_name": "Search Results",
  "google_account": "your-email@gmail.com",  # Only for identification, NOT for login
  "browser_profile": "separate-profile"  # Use separate browser profile
}
```

### Operation Examples

#### 1. Create New Knowledge Base (Notebook)

Using `playwright-cli`:

```bash
# Launch browser and open NotebookLM
playwright-cli open "https://notebooklm.google.com/"

# ⚠️ Login manually (DO NOT automate login process!)

# Click "New" button
playwright-cli click "text=New"

# Input knowledge base name
playwright-cli type "input[placeholder='Enter name']" "Search Results"

# Click "Create" button
playwright-cli click "text=Create"
```

#### 2. Upload File

```bash
# ⚠️ Need user confirmation before uploading
if user_confirmed("Confirm to upload this file to NotebookLM?"):
    # Upload file
    playwright-cli upload "input[type='file']" "path/to/webpage-content.md"
    
    # Wait for AI processing to complete
    playwright-cli wait "text=Processing complete" --timeout 60000
```

#### 3. Add Webpage Link

```bash
# Click "Add source" button
playwright-cli click "text=Add source"

# Select "Webpage" option
playwright-cli click "text=Webpage"

# Input URL
playwright-cli type "input[placeholder='Enter URL']" "https://example.com/article1"

# Click "Add" button
playwright-cli click "text=Add"

# Wait for AI processing to complete
playwright-cli wait "text=Processing complete" --timeout 60000
```

#### 4. Ask Question (AI Q&A)

```bash
# Input question in Q&A box
playwright-cli type "textarea[placeholder='Ask anything...']" "What are the main points of this article?"

# Click "Send" button
playwright-cli click "button[aria-label='Send']"

# Wait for answer generation
playwright-cli wait "text=Answer complete" --timeout 30000

# Extract answer content
answer = playwright-cli extract "div.answer-content"
```

#### 5. Export Summary

```bash
# Click "Export" button
playwright-cli click "button[aria-label='Export']"

# Select "Export as Markdown"
playwright-cli click "text=Export as Markdown"

# Wait for download to complete
playwright-cli wait "text=Download complete" --timeout 30000
```

---

## Method B: Through Google Drive API Indirect Integration

### Advantages
- ✅ Does not require browser automation
- ✅ More stable and faster
- ✅ Can batch upload files

### Disadvantages
- ❌ Requires Google Drive API configuration
- ❌ Requires manually importing Drive files in NotebookLM
- ❌ Does not support real-time operation

### Preparations

⚠️ **Security Notice**:
1. **Pin package versions** to avoid supply chain attacks
2. **Use virtual environment** to isolate dependencies
3. **Limit OAuth scopes**, only request minimal necessary permissions

#### 1. Enable Google Drive API:

- Visit [Google Cloud Console](https://console.cloud.google.com/)
- Create project (or select existing project)
- Enable **Google Drive API**
- Create OAuth 2.0 credentials (Desktop App)
- Download `credentials.json`

#### 2. Install Google Client Library (Pinned versions!):

```bash
# ⚠️ Recommended: Use virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  (Windows)

# Install pinned versions (avoid supply chain attacks)
pip install --upgrade google-api-python-client==2.116.0 google-auth-httplib2==0.2.0 google-auth-oauthlib==1.2.0
```

#### 3. Configuration (DO NOT include sensitive information!):

Set in `config.json`:

```json
{
  "platform": "notebooklm",
  "method": "google-drive-api",
  "google_drive_folder_id": "your-folder-id",
  "credentials_file": "path/to/credentials.json",
  "token_file": "path/to/token.json",
  "oauth_scopes": [
    "https://www.googleapis.com/auth/drive.file"  # Minimal scope
  ]
}
```

### Operation Examples

#### 1. Upload File to Google Drive

```python
import os
import google.auth
from google.auth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Authentication (use minimal OAuth scope)
creds = Credentials.from_authorized_user_file(
    config["token_file"],
    scopes=config.get("oauth_scopes", ["https://www.googleapis.com/auth/drive.file"])
)

# Build Drive API client
service = build("drive", "v3", credentials=creds)

# Upload file
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

print(f"File uploaded: {file.get('webViewLink')}")
```

#### 2. Import Drive File in NotebookLM

**Note**: NotebookLM currently does not support automatic import of Drive files via API, requires manual operation:

1. Open [NotebookLM](https://notebooklm.google.com/)
2. Open target knowledge base (Notebook)
3. Click "Add source"
4. Select "Google Drive"
5. Select uploaded file
6. Click "Import"

**Automation solution**: Can use browser automation (Method A) to automate this process (but requires manual login).

---

## Complete Workflow Example

### Scenario: Search Webpages and Save to NotebookLM

```python
# ⚠️ Security Notice:
# 1. All upload operations need user confirmation
# 2. DO NOT upload sensitive information
# 3. Use separate browser profile

# 1. Search webpages
search_results = search_web("AI Machine Learning")

# 2. Filter results (according to whitelist/blacklist)
filtered_results = filter_results(search_results)

# 3. Stage webpage content
for result in filtered_results:
    # Download webpage content
    content = download_webpage(result["url"])
    
    # Save as Markdown file
    filename = f"temp/{result['title']}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    
    # ⚠️ Need user confirmation before uploading
    if user_confirmed(f"Confirm to upload {filename} to NotebookLM?"):
        # Upload to NotebookLM (using browser automation)
        upload_to_notebooklm(filename)
        
        # Wait for AI processing to complete
        wait_for_processing()

# 4. Extract AI summary
summary = ask_notebooklm("Please summarize the main points of all uploaded documents")

# 5. Save summary (need user confirmation)
if user_confirmed("Confirm to save this summary?"):
    save_summary(summary)
```

---

## Notes

⚠️ **Security Notice**:
1. **Credential Management**: This skill does **NOT** store Google Account credentials. Manual login is required each time.
2. **Data Privacy**: Uploaded content will be sent to Google servers. **DO NOT upload sensitive information**!
3. **Browser Automation Security**: When using Method A, ensure `playwright-cli` or `agent-browser` is from trusted source.
4. **API Quota**: Be aware of Google Drive API usage quotas to avoid service interruption.
5. **Network Security**: Ensure stable and secure network connection, use HTTPS when transmitting data.
6. **OAuth Scope Limitation**: Only request minimal necessary OAuth permissions (e.g., `drive.file` instead of `drive`).
7. **Separate Browser Profile**: Use a separate browser profile to avoid mixing with main browser.
8. **Virtual Environment**: Use virtual environment to install Python packages, avoid polluting system environment.
9. **Pinned Versions**: Pin versions of all dependency packages to avoid supply chain attacks.

## Security Best Practices

```python
# ✅ Recommended: Let user login manually, DO NOT store credentials
# Bad practice (DO NOT DO THIS):
config = {
    "google_username": "user@gmail.com",
    "google_password": "password123"  # NEVER store passwords!
}

# Good practice:
config = {
    "notebook_name": "Search Results",
    "method": "browser-automation"
    # No credentials stored
}

# User will manually login when browser opens
```

```python
# ✅ Recommended: Use minimal OAuth scope
# Bad practice (DO NOT DO THIS):
scopes = ["https://www.googleapis.com/auth/drive"]  # Too broad

# Good practice:
scopes = ["https://www.googleapis.com/auth/drive.file"]  # Minimal scope
```

```python
# ✅ Recommended: Need user confirmation before uploading
filename = "path/to/webpage-content.md"

# Bad practice (DO NOT DO THIS):
upload_to_notebooklm(filename)  # Upload without confirmation

# Good practice:
if user_confirmed(f"Confirm to upload {filename} to NotebookLM?"):
    upload_to_notebooklm(filename)
```

1. **Network Connection**: Ensure stable network connection
2. **Google Account**: Manual login to Google account (DO NOT store credentials)
3. **API Quotas**: Note Google Drive API usage quotas
4. **File Formats**: NotebookLM supports PDF, Markdown, plain text, Google Docs and other formats
5. **Privacy Protection**: Uploaded content will be sent to Google servers, please pay attention to sensitive information
6. **Browser Automation**: If using Method A, please ensure `playwright-cli` or `agent-browser` is correctly installed
7. **Waiting Time**: AI processing takes time, please ensure sufficient waiting time is set
8. **Regular Cleanup**: Regularly clean up temporary files and browser cache
9. **Use Local Alternative**: If processing sensitive information, please use local Obsidian storage instead

---

## Reference Resources

- [NotebookLM Official Website](https://notebooklm.google.com/)
- [NotebookLM Help Center](https://support.google.com/notebooklm/)
- [Google Drive API Documentation](https://developers.google.com/drive/api/v3/about)
- [Playwright CLI Documentation](https://playwright.dev/)
- [Agent Browser Skill](https://clawhub.ai/skills/agent-browser)
- [OAuth 2.0 Security Best Practices](https://oauth.net/2/security-considerations/)
