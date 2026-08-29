# Security Documentation

## Pre-Installation Checklist

Before installing this skill, review the following:

- [ ] **Understand Monitoring Scope**: This skill intercepts web_fetch, web_search, browser, and file_download operations
- [ ] **Review Log Location**: Logs will be written to `~/.openclaw/logs/security-monitor.log`
- [ ] **Check File Permissions**: Ensure log directory has appropriate permissions (see File Permissions section)
- [ ] **API Key Storage**: Decide whether to use `SECURITY_MONITOR_API_KEY` environment variable (recommended) or config.json
- [ ] **Sensitive Paths**: Identify any sensitive file paths that should be whitelisted
- [ ] **hs-ti Dependency**: If hs-ti is installed, verify its trustworthiness as this skill may call its functions
- [ ] **Test in Sandbox**: Consider testing in an isolated environment first (see tests/test_security_monitor.py)

## Security Best Practices

### 1. API Key Management

**Recommended Approach:**
- Use environment variables for API keys (recommended)
  ```bash
  export SECURITY_MONITOR_API_KEY="your-api-key-here"
  ```
- Ensure environment variables are not logged to history
  ```bash
  # In bash
  export HISTCONTROL=ignorespace
  export SECURITY_MONITOR_API_KEY="your-api-key-here"
  
  # In PowerShell
  $env:SECURITY_MONITOR_API_KEY="your-api-key-here"
  ```

**Configuration File Approach:**
- If configuration file must be used, ensure:
  - File permissions are set to owner-only read: `chmod 600 config.json`
  - Configuration file is not committed to version control
  - Configuration file is added to `.gitignore`

### 2. Logging Security

**⚠️ Important Privacy Notice:**
This skill logs monitored network activity and file operations. Before installing, understand:
- All URLs accessed through monitored tools will be logged
- File paths passed to monitored operations will be logged
- File hashes may be calculated (requires reading file contents)

**Log File Location:**
- Default location: `~/.openclaw/logs/security-monitor.log`
- Logs contain:
  - Monitored URLs (web_fetch, web_search, browser operations)
  - File paths (file_download operations)
  - Threat types and levels
  - Timestamps and action taken (blocked/warned/logged)

**Sensitive Information Protection:**
- This skill implements automatic masking; logs will not display:
  - API keys (replaced with `[REDACTED]`)
  - Authentication tokens
  - Long key strings
- **Note**: While masking is implemented, treat logs as potentially sensitive as regex patterns may not catch all formats

**Logging Configuration Recommendations:**
```json
{
  "logging": {
    "enabled": true,
    "log_file": "~/.openclaw/logs/security-monitor.log",
    "log_blocked": true,
    "log_warned": true,
    "log_logged": true,
    "log_benign": false
  }
}
```

**Log Rotation:**
- Recommend regular cleanup or archiving of log files
- Use log rotation tools (e.g., `logrotate`)
- Ensure log files are not accessible to unauthorized users

### 3. File Permissions

**Configuration File:**
```bash
# Set configuration file permissions
chmod 600 ~/.openclaw/skills/security-monitor/config.json

# Ensure directory permissions are correct
chmod 700 ~/.openclaw/skills/security-monitor/
```

**Log File:**
```bash
# Set log file permissions
chmod 600 ~/.openclaw/logs/security-monitor.log

# Ensure log directory permissions are correct
chmod 700 ~/.openclaw/logs/
```

### 4. Network Security

**Threat Intelligence API:**
- Use HTTPS connections to threat intelligence APIs
- Verify API certificates
- Do not log complete API requests

**Whitelist and Blacklist:**
- Regularly review whitelist and blacklist
- Remove entries that are no longer needed
- Use specific domains/IPs, avoid wildcards

### 5. Auditing and Monitoring

**Regular Checks:**
- Review log files for unusual activity
- Check statistics for abnormal patterns
- Verify cache hit rates are reasonable

**Statistics:**
- Use `--stats` command to view statistics
- Use `--api-stats` command to view API call statistics
- Use `--cache-info` command to view cache information

---

## Security Features

### Implemented Security Measures

#### 1. Environment Variable Support
- ✅ API keys can be stored in environment variables
- ✅ Environment variables take precedence over config files
- ✅ Reduces risk of API key exposure in configuration files

#### 2. Log Masking
- ✅ Automatic masking of sensitive information in logs
- ✅ API keys are replaced with `[REDACTED]`
- ✅ Authentication tokens are masked
- ✅ Long key strings are automatically detected and masked

#### 3. Secure Defaults
- ✅ API key defaults to empty string
- ✅ Logging of benign events is disabled by default
- ✅ Whitelist includes trusted domains by default

#### 4. Cache Security
- ✅ Cache entries have TTL (time-to-live)
- ✅ Expired cache entries are automatically removed
- ✅ Cache size is limited to prevent memory issues

---

## Incident Response

### When Security Events are Detected

1. **Immediate Actions:**
   - Review log files for detailed information
   - Check statistics for abnormal patterns
   - If necessary, suspend related network access

2. **Investigation:**
   - Determine threat type and source
   - Review whitelist and blacklist configuration
   - Verify threat intelligence API responses

3. **Mitigation:**
   - Add malicious domains/IPs to blacklist
   - Update security policies
   - Notify affected users

4. **Documentation:**
   - Document event details
   - Document actions taken
   - Update security policy documentation

---

## Compliance

### Data Protection

- This skill does not collect or store personally identifiable information (PII)
- Log files may contain network access records and should be handled according to organizational data retention policies
- Recommend regular cleanup of log files

### Security Audits

- Recommend regular security audits
- Check log files for unusual activity
- Verify configuration file permissions
- Review whitelist and blacklist validity

---

## Contact

**Security Issues:**
- Report security vulnerabilities: https://github.com/your-repo/security
- General inquiries: https://clawhub.ai/maxjia/network-security-monitor

**Version:** 1.1.3  
**Last Updated:** 2026-04-02
