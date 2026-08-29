# Security Scanning Skill - Example Usage

This document shows examples of how to use the security scanner skill.

## Quick Test

To test the scanner on this workspace:

```bash
cd /Users/shuk/projects/llm_plugin
bash skills/security-scanner/scripts/scan_secrets.sh
```

## What Gets Detected

### Example 1: API Keys

```python
# This would be flagged as HIGH severity
GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
AWS_ACCESS_KEY = "example"
STRIPE_KEY = "example"
```

### Example 2: Database Credentials

```javascript
// This would be flagged as HIGH severity
const dbUrl = "postgresql://admin:MyP@ssw0rd123@localhost:5432/mydb";
const mongoUri = "mongodb://user:secret123@cluster.mongodb.net/db";
```

### Example 3: Hardcoded Passwords

```java
// This would be flagged as HIGH severity
String password = "admin123";
String apiKey = "my-secret-api-key-2024";
```

## Using Through the Assistant

Simply ask the assistant:

- **"Run a security scan on my workspace"**
- **"Check for exposed secrets"**
- **"Scan for API keys and passwords"**
- **"Find any hardcoded credentials"**

The assistant will execute the scanner and provide a detailed report.

## Interpreting Results

### High Severity (RED ❌)

- Actual API keys, tokens, passwords detected
- **Action Required**: Immediate remediation

### Medium Severity (YELLOW ⚠️)

- Suspicious patterns that might be secrets
- **Action Required**: Review and verify

### Low Severity (YELLOW ℹ️)

- Test data or examples
- **Action Required**: Confirm if safe

## Best Practices

1. **Run before commits**: Always scan before pushing code
2. **Fix immediately**: Don't commit code with exposed secrets
3. **Use .env files**: Store secrets in environment variables
4. **Add to .gitignore**: Ensure .env is ignored
5. **Rotate exposed secrets**: If secrets are found, rotate them

## Integration with Workflow

Add to your workflow:

```bash
# Before committing
bash skills/security-scanner/scripts/scan_secrets.sh
if [ $? -eq 0 ]; then
    git commit -m "Your message"
else
    echo "Security issues detected! Fix before committing."
fi
```
