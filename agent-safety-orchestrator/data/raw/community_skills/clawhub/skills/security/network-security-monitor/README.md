# OpenClaw Security Monitor

## Overview

OpenClaw Security Monitor plugin provides real-time network access security monitoring for OpenClaw. By integrating threat intelligence APIs (prioritizing Hillstone Threat Intelligence), it performs security checks before accessing external URLs, IP addresses, or downloading files. When security risks are detected, it provides warnings or blocks access based on configured policies, protecting users from malicious websites, phishing attacks, and malware.

---

## Features

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

## Installation

1. **Copy skill files**
   ```bash
   cp -r security-monitor ~/.openclaw_data/skills/
   ```

2. **Configure threat intelligence**
   ```bash
   cd ~/.openclaw_data/skills/security-monitor
   cp config.example.json config.json
   ```

3. **Edit configuration file**
   ```bash
   # Edit config.json to configure threat intelligence and security policies
   ```

4. **Restart OpenClaw**
   ```bash
   openclaw restart
   ```

---

## Configuration

### Threat Intelligence Configuration

```json
{
  "threat_intel": {
    "provider": "hs-ti",
    "enabled": true,
    "cache_ttl": 3600,
    "timeout": 5000
  }
}
```

**Recommendation:** Prioritize hs-ti skill and Hillstone Threat Intelligence API

### Security Policy Configuration

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

### Whitelist Configuration

```json
{
  "whitelist": {
    "enabled": true,
    "domains": [
      "github.com",
      "openclaw.ai",
      "hillstonenet.com.cn"
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

### View Statistics

```
/security-stats
```

---

## Testing

Run tests:

```bash
cd ~/.openclaw_data/skills/security-monitor
python3 tests/test_security_monitor.py
```

---

## Troubleshooting

### Issue 1: hs-ti Skill Not Detected

**Solution:**
1. Install hs-ti skill: https://clawhub.ai/maxjia/hs-ti
2. Configure Hillstone API key
3. Restart OpenClaw Gateway

### Issue 2: Frequent False Positives

**Solution:**
1. Add trusted domains to whitelist
2. Adjust threat level thresholds
3. Check threat intelligence source accuracy

---

## Related Resources

- **hs-ti Skill**: https://clawhub.ai/maxjia/hs-ti
- **Hillstone Threat Intelligence**: https://ti.hillstonenet.com.cn
- **OpenClaw Documentation**: https://openclaw.ai/docs

---

## License

MIT License

---

## Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.
