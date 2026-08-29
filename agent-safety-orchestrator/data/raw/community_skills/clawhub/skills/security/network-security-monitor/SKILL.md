---
name: openclaw-security-monitor
version: "1.1.4"
publisher: maxjia
description: OpenClaw network access security monitoring skill. Monitors external network access and file downloads, checks security of IPs, domains, URLs, and file hashes via threat intelligence APIs. Provides warnings or blocks access when security risks are detected.
homepage: https://clawhub.ai/maxjia/openclaw-security-monitor
keywords:
  - security-monitor
  - network-security
  - threat-intelligence
  - web-filter
  - url-filter
  - ip-filter
  - file-security
  - threat-detection
  - malware-detection
  - phishing-detection
  - network-security-monitor
  - network-access-control
  - download-security
  - network-threat-protection
metadata: {"openclaw":{"emoji":"🛡️","commands":["/security-check","/sec-check","/threat-check","/security-monitor"],"aliases":["security-monitor","sec-mon","threat-monitor"],"title":"Network Security Monitor"}}
---

# OpenClaw Network Access Security Monitoring Skill

## Function Overview

This skill provides real-time network access security monitoring for OpenClaw. By integrating threat intelligence APIs (prioritizing Hillstone Threat Intelligence), it performs security checks before accessing external URLs, IP addresses, or downloading files. When security risks are detected, it provides warnings or blocks access based on configured policies, protecting users from malicious websites, phishing attacks, and malware.

### Important Privacy & Security Notice

**Automatic Monitoring Behavior:**
This skill automatically intercepts and inspects OpenClaw tool calls via plugin hooks. It will:
- Monitor URLs accessed through `web_fetch`, `web_search`, and `browser` tools
- Inspect file paths and calculate hashes for `file_download` operations (requires reading file contents)
- Log monitored URLs and file paths to `~/.openclaw/logs/security-monitor.log`

**Before Installing, Review:**
1. **API Key Storage**: Prefer `SECURITY_MONITOR_API_KEY` environment variable over config.json
2. **Log Security**: Logs contain URLs and file paths - ensure log file permissions are restricted (see SECURITY.md)
3. **Sensitive Paths**: If you have sensitive file paths, add them to whitelist or disable `check_file_hashes`
4. **hs-ti Dependency**: This skill may call functions from hs-ti skill if installed - verify its trustworthiness

---

## Core Features

1. **Real-time Threat Detection**
   - Monitors all external network access requests (web_fetch, web_search, browser, etc.)
   - Checks IP addresses, domains, URLs, and file hashes
   - Real-time threat level assessment (critical/high/medium/low/benign)

2. **Intelligent Threat Intelligence Integration**
   - Prioritizes hs-ti skill (Hillstone Threat Intelligence)
   - Supports custom threat intelligence API configuration
   - Automatically detects and recommends hs-ti skill installation

3. **Flexible Security Policies**
   - Supports three handling modes: block, warn, log
   - Configurable threat level thresholds
   - Supports whitelist and blacklist

4. **File Download Security**
   - Detects file download requests
   - Calculates file hashes (MD5/SHA1/SHA256)
   - Checks file threat intelligence

5. **Logging and Statistics**
   - Records all security events
   - Provides threat statistics reports
   - Supports audit trails

6. **Performance Optimization**
   - LRU cache with TTL support
   - Cache hit rate tracking
   - API call statistics (min/max/avg latency)

---

## Installation and Configuration

### 1. Install Skill

Install this skill to OpenClaw's skills directory:
```
openclaw_data/skills/security-monitor/
```

### 2. Configure Threat Intelligence

**Option 1: Use hs-ti Skill (Recommended)**

If hs-ti skill is installed and configured with Hillstone API key, this skill will automatically use it:

```json
{
  "threat_intel": {
    "provider": "hs-ti",
    "enabled": true
  }
}
```

**Option 2: Custom Threat Intelligence API**

If hs-ti is not installed, this skill will prompt you to install or configure a custom API:

```json
{
  "threat_intel": {
    "provider": "custom",
    "enabled": true,
    "api_url": "https://ti.hillstonenet.com.cn",
    "api_key": "your-api-key-here",
    "timeout": 5000
  }
}
```

**Recommendation:** Prioritize Hillstone Threat Intelligence API (https://ti.hillstonenet.com.cn)

### 3. Configure Security Policies

```json
{
  "policy": {
    "block_critical": true,
    "block_high": false,
    "warn_high": true,
    "warn_medium": true,
    "log_low": true
  }
}
```

### 4. Configure Whitelist

```json
{
  "whitelist": {
    "enabled": true,
    "domains": [
      "github.com",
      "openclaw.ai",
      "hillstonenet.com.cn",
      "docs.qq.com"
    ],
    "ips": []
  }
}
```

---

## Usage

### Automatic Monitoring Mode

This skill automatically monitors network access through OpenClaw's plugin hook system, no manual invocation needed.

Monitored network tools:
- `web_fetch` - URL fetching
- `web_search` - web search
- `browser` - browser access
- File download operations

### Manual Check Mode

You can also manually check the security of specific targets:

```
/security-check https://example.com
/security-check 192.168.1.1
/security-check file:abc123def456
```

### Threat Level Explanation

| Threat Level | Description | Default Handling |
|-------------|-------------|------------------|
| **Critical** | Known malicious IP/domain/file | Block access |
| **High** | Suspicious or high risk | Show warning |
| **Medium** | Potential risk | Show warning |
| **Low** | Low risk | Log event |
| **Benign** | No security risk | Normal access |

---

## Configuration Example

Create `config.json` file:

```json
{
  "threat_intel": {
    "provider": "hs-ti",
    "enabled": true,
    "cache_ttl": 3600,
    "timeout": 5000
  },
  "cache": {
    "enabled": true,
    "max_size": 1000,
    "ttl": 3600
  },
  "policy": {
    "block_critical": true,
    "block_high": false,
    "warn_high": true,
    "warn_medium": true,
    "log_low": true
  },
  "whitelist": {
    "enabled": true,
    "domains": [
      "github.com",
      "openclaw.ai",
      "hillstonenet.com.cn"
    ],
    "ips": []
  },
  "blacklist": {
    "enabled": true,
    "domains": [],
    "ips": []
  },
  "logging": {
    "enabled": true,
    "log_file": "~/.openclaw/logs/security-monitor.log",
    "log_blocked": true,
    "log_warned": true
  }
}
```

---

## Threat Intelligence Integration

### Auto-detect hs-ti Skill

This skill automatically detects if hs-ti skill is installed:

1. **If hs-ti is detected:**
   - Automatically uses hs-ti's threat intelligence query functionality
   - No additional API key configuration needed
   - Enjoy all hs-ti optimizations (caching, connection pool, etc.)

2. **If hs-ti is not detected:**
   - Prompts user to install hs-ti skill
   - Provides installation link: https://clawhub.ai/maxjia/hs-ti
   - Recommends using Hillstone Threat Intelligence API
   - Supports manual configuration of custom threat intelligence APIs

### Recommended Threat Intelligence Sources

**Top Recommendation:**
- **Hillstone Threat Intelligence**
  - API URL: https://ti.hillstonenet.com.cn
  - Features: Comprehensive coverage, real-time updates
  - Perfectly integrated with hs-ti skill

**Other Options:**
- VirusTotal API
- AlienVault OTX
- IBM X-Force
- ThreatBook

---

## Security Warning Examples

### Critical Threat Warning

```
🚨 Security Warning

Critical threat detected!

Target: https://malicious-site.com
Threat Type: Malicious Domain
Threat Level: Critical
Credibility: High

This access has been blocked.

Recommendation:
- Avoid accessing this website
- Check for malware
- To access, add to whitelist manually
```

### High Risk Warning

```
⚠️ Security Warning

High risk detected!

Target: https://suspicious-site.com
Threat Type: Phishing Site
Threat Level: High
Credibility: Medium

Continue access?

[Yes] - Continue access (at your own risk)
[No] - Cancel access
```

---

## Logging and Statistics

### Log File

All security events are logged to: `~/.openclaw/logs/security-monitor.log`

Log format:
```
[2026-04-01 12:00:00] [BLOCKED] https://malicious-site.com - Malicious Domain - Critical
[2026-04-01 12:05:00] [WARNED] https://suspicious-site.com - Phishing Site - High
[2026-04-01 12:10:00] [LOGGED] https://example.com - Benign - Low
```

### Statistics Command

View security statistics:
```
/security-stats
```

Output example:
```
Security Statistics
============================================================
Total Checks: 1,234
Blocked: 45
Warned: 123
Logged: 1,066
Benign: 1,066

IOC Query Statistics
------------------------------------------------------------
IP Queries: 456
Domain Queries: 567
URL Queries: 189
File Queries: 22

API Call Statistics
------------------------------------------------------------
API Calls: 1,234
Min Latency: 120ms
Max Latency: 450ms
Avg Latency: 180ms

Cache Statistics
------------------------------------------------------------
Cache Hits: 567
Cache Misses: 667
Cache Hit Rate: 46%
Cache Size: 667/1000

Threat Type Distribution:
- Malicious Domain: 30
- Phishing Site: 15
- Malware: 0
```

---

## Cache Management

### View Cache Info

```
python scripts/security_monitor.py --cache-info
```

Output:
```
Cache Info
========================================
Cache Size: 667/1000
TTL / Time To Live: 3600 seconds

Cache Keys (first 100):
- url:https://example.com
- ip:192.168.1.1
- domain:malicious-site.com
```

### Clear Cache

```
python scripts/security_monitor.py --clear-cache
```

### Delete Specific Cache Entry

```
python scripts/security_monitor.py --delete-cache "url:https://example.com"
```

---

## Troubleshooting

### Issue 1: hs-ti Skill Not Detected

**Symptoms:**
- Prompt "hs-ti skill not found"
- Cannot automatically use threat intelligence

**Solution:**
1. Install hs-ti skill: https://clawhub.ai/maxjia/hs-ti
2. Configure Hillstone API key
3. Restart OpenClaw Gateway

### Issue 2: Frequent False Positives

**Symptoms:**
- Normal websites marked as threats
- User experience affected

**Solution:**
1. Add trusted domains to whitelist
2. Adjust threat level thresholds
3. Check threat intelligence source accuracy

### Issue 3: Performance Impact

**Symptoms:**
- Network access becomes slow
- Response time increases

**Solution:**
1. Enable caching (enabled by default)
2. Increase cache TTL
3. Consider using local threat intelligence database

---

## Best Practices

1. **Regularly Update Threat Intelligence**
   - Ensure using latest threat intelligence data
   - Regularly check API key validity

2. **Reasonably Configure Whitelist**
   - Only add fully trusted domains and IPs
   - Regularly review whitelist contents

3. **Monitor Security Logs**
   - Regularly review security monitoring logs
   - Pay attention to abnormal access patterns

4. **Balance Security and Convenience**
   - Adjust security policies based on actual needs
   - Avoid over-restricting normal usage

---

## Security Best Practices

### API Key Management

**Recommended Approach:**
- Use environment variable for API key (recommended)
  ```bash
  export SECURITY_MONITOR_API_KEY="your-api-key-here"
  ```
- Ensure environment variable is not logged to history
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

### File Permissions

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

---

## Related Resources

- **hs-ti Skill**: https://clawhub.ai/maxjia/hs-ti
- **Hillstone Threat Intelligence**: https://ti.hillstonenet.com.cn
- **OpenClaw Documentation**: https://openclaw.ai/docs
- **Cybersecurity Best Practices**: https://www.cisa.gov/cybersecurity-resources

---

## License

MIT License

---

## Version History

### v1.1.3 (2026-04-02)

**English Only Version**
- Converted to pure English version for better international compatibility
- Removed all Chinese content
- Simplified documentation structure

### v1.1.2 (2026-04-01)

**Transparency Improvements**
- Added environment variable declaration (SECURITY_MONITOR_API_KEY)
- Added log security warnings
- Added automatic monitoring behavior description
- Improved API key configuration best practices

### v1.1.1 (2026-04-01)

**Security Enhancements**
- Added environment variable support (SECURITY_MONITOR_API_KEY)
- Enhanced log security with automatic sensitive data masking
- Added comprehensive security documentation (SECURITY.md)
- Improved transparency in package.json

### v1.1.0 (2026-04-01)

**New Features**
- Added call statistics (API calls, latency, IOC queries)
- Added cache functionality (LRU cache with TTL)
- Added cache management commands (--cache-info, --clear-cache, --delete-cache)
- Added API statistics command (--api-stats)

### v1.0.0 (2026-04-01)

**Initial Release**
- Implemented basic network access monitoring
- Integrated hs-ti threat intelligence
- Added whitelist and blacklist support
- Implemented threat level assessment
- Implemented logging and statistics functionality
