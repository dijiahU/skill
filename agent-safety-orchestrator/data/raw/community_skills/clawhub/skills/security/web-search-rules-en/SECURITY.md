# Web Search Rules Skill - Security Guide

## ⚠️ Security Statement

This skill supports multi-platform knowledge base integration. **Some features require file system access and browser automation permissions**. Please read this security guide carefully before use.

---

## 🔒 Permission Requirements

### Required Permissions
1. **Configuration File Read/Write** (`~/.skill-config/web-search-rules-en/config.json`)
   - Purpose: Store user platform preference
   - Risk: Low
   - Protection: Only stores non-sensitive configuration

2. **Search Results Staging** (`~/.skill-config/web-search-rules-en/temp/`)
   - Purpose: Temporarily store search results
   - Risk: Medium (may contain sensitive information)
   - Protection: Regular cleanup, no cloud upload

### Optional Permissions (by platform)
1. **Obsidian Support**
   - Permission: Read/write Obsidian Vault directory
   - Risk: Medium-High (can access all Vault files)
   - Protection: **Restrict operations to user-specified Vault directory only**

2. **NotebookLM Support**
   - Permission: Browser automation (Playwright), Google Account access
   - Risk: High (requires Google Account authentication)
   - Protection: **Do not store Google Account credentials**, manual login each time

3. **Web Search**
   - Permission: Access external search APIs
   - Risk: Low
   - Protection: Only search user-specified keywords

---

## 🛡️ Security Measures

### 1. Path Validation
All file path operations are validated. **Arbitrary path writing is not allowed**:

```python
import os
import re

# Allowed path whitelist
ALLOWED_PATHS = [
    os.path.expanduser("~/.skill-config/web-search-rules-en/"),
    os.path.expanduser("~/Documents/ObsidianVault/"),  # Requires user confirmation
]

def validate_path(path):
    """Validate if path is within whitelist"""
    abs_path = os.path.abspath(path)
    for allowed in ALLOWED_PATHS:
        if abs_path.startswith(os.path.abspath(allowed)):
            return True
    raise SecurityError(f"Path {path} is not allowed!")

# Validate before use
validate_path(user_specified_path)
```

### 2. User Confirmation
All sensitive operations (file writing, browser automation, API calls) require **explicit user confirmation**:

```python
# Ask user before execution
if not user_confirmed:
    ask_user("Do you want to save this content to Obsidian Vault?")
    if not user_response:
        abort_operation()
```

### 3. Credential Management
- **Do not store** Google Account credentials
- **Do not store** Obsidian Local REST API Key to disk
- **Only store** non-sensitive configuration (platform selection, Vault path, etc.)
- Sensitive credentials stored in user environment variables or keychain

### 4. Data Cleanup
- Temporary files are **automatically deleted** after task completion
- Search results staging directory is cleaned regularly (default 7 days)
- Sensitive data is not uploaded to the cloud

---

## 🚨 Potential Risks

### 1. Prompt Injection
**Risk**: Malicious webpage content may contain special instructions that affect AI decisions  
**Mitigation**:
- Sanitize webpage content, remove special markers
- Do not execute code in webpages
- All decisions require user confirmation

### 2. Path Traversal Attack
**Risk**: Malicious paths may lead to arbitrary file read/write  
**Mitigation**:
- Strictly validate all file paths
- Use path whitelist
- Do not allow users to specify arbitrary paths

### 3. Credential Leakage
**Risk**: Google Account credentials may be leaked  
**Mitigation**:
- Do not store credentials to disk
- Use OAuth 2.0 authentication flow
- Regularly remind users to check authorized applications

### 4. Data Privacy
**Risk**: Search results may contain sensitive information  
**Mitigation**:
- Temporary files stored locally, not uploaded to cloud
- Regularly clean up temporary files
- Remind users to pay attention to sensitive information

---

## 📋 Security Checklist

Before using this skill, please confirm:

- [ ] I have read and understood this security guide
- [ ] I confirm the Obsidian Vault path is set correctly
- [ ] I understand NotebookLM requires Google Account authentication
- [ ] I confirm that I will not process sensitive or confidential information
- [ ] I agree to store temporary files on local disk
- [ ] I understand how to report and respond to security issues

---

## 📞 Security Reports

If you discover any security vulnerabilities or potential risks, please:

1. **Do not** disclose vulnerability details in public
2. Contact the developer through secure channels
3. Provide detailed reproduction steps
4. Wait for official fix before public disclosure

---

## 🔄 Update History

- **v2.0.1** (2026-05-06): Added security guide, reduced permission requests
- **v2.0.0** (2026-05-05): Initial version, supports Obsidian and NotebookLM

---

## 📚 References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Prompt Injection Attacks](https://genai.owasp.org/llm-top-10-overview/)
- [Google API Security Best Practices](https://developers.google.com/drive/api/v3/about/auth)
- [Obsidian Security Guide](https://help.obsidian.md/)

---

**Last Updated**: 2026-05-06  
**Version**: v2.0.1
