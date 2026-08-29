# Security Review Checklist

Comprehensive security checklist for multi-AI code review.

## OWASP Top 10 (2024)

### A01: Broken Access Control

**Check For**:
- [ ] Missing authorization checks on endpoints
- [ ] IDOR (Insecure Direct Object References)
- [ ] Path traversal vulnerabilities
- [ ] CORS misconfiguration
- [ ] JWT validation bypasses

**Detection Patterns**:
```python
# BAD: No authorization check
@app.route('/user/<id>')
def get_user(id):
    return User.query.get(id)  # Anyone can access any user!

# GOOD: Authorization check
@app.route('/user/<id>')
@login_required
def get_user(id):
    if current_user.id != id and not current_user.is_admin:
        abort(403)
    return User.query.get(id)
```

### A02: Cryptographic Failures

**Check For**:
- [ ] Plaintext passwords
- [ ] Weak hashing algorithms (MD5, SHA1)
- [ ] Hardcoded encryption keys
- [ ] Missing TLS/HTTPS
- [ ] Sensitive data in logs

**Detection Patterns**:
```python
# BAD: Plaintext password storage
user.password = request.form['password']

# BAD: Weak hashing
import hashlib
user.password = hashlib.md5(password.encode()).hexdigest()

# GOOD: Strong password hashing
import bcrypt
user.password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
```

### A03: Injection

**Check For**:
- [ ] SQL injection
- [ ] NoSQL injection
- [ ] Command injection
- [ ] LDAP injection
- [ ] XPath injection

**Detection Patterns**:
```python
# BAD: SQL injection
query = f"SELECT * FROM users WHERE id = {user_id}"
cursor.execute(query)

# GOOD: Parameterized query
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# BAD: Command injection
os.system(f"ping {hostname}")

# GOOD: Safe subprocess
subprocess.run(["ping", hostname], capture_output=True)
```

### A04: Insecure Design

**Check For**:
- [ ] Missing rate limiting
- [ ] No account lockout
- [ ] Insecure password reset
- [ ] Trust boundary violations
- [ ] Missing input validation at design level

### A05: Security Misconfiguration

**Check For**:
- [ ] Debug mode in production
- [ ] Default credentials
- [ ] Unnecessary features enabled
- [ ] Missing security headers
- [ ] Verbose error messages

**Detection Patterns**:
```python
# BAD: Debug in production
app.run(debug=True)

# BAD: Default secret key
SECRET_KEY = 'development-key'

# GOOD: Environment-based config
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY must be set")
```

### A06: Vulnerable Components

**Check For**:
- [ ] Outdated dependencies
- [ ] Known CVEs in packages
- [ ] Unmaintained libraries
- [ ] Missing security patches

**Tools**:
```bash
# Python
pip-audit
safety check

# JavaScript
npm audit
snyk test

# General
dependabot alerts
```

### A07: Authentication Failures

**Check For**:
- [ ] Weak password requirements
- [ ] Missing MFA
- [ ] Session fixation
- [ ] Credential stuffing vulnerabilities
- [ ] Brute force susceptibility

### A08: Software & Data Integrity Failures

**Check For**:
- [ ] Unsigned updates
- [ ] Unverified CI/CD pipelines
- [ ] Deserialization vulnerabilities
- [ ] Missing integrity checks

**Detection Patterns**:
```python
# BAD: Unsafe deserialization
import pickle
data = pickle.loads(user_input)  # Remote code execution risk!

# GOOD: Safe deserialization
import json
data = json.loads(user_input)
```

### A09: Logging & Monitoring Failures

**Check For**:
- [ ] Missing audit logs
- [ ] Sensitive data in logs
- [ ] No alerting for security events
- [ ] Insufficient log retention

**Detection Patterns**:
```python
# BAD: Logging sensitive data
logger.info(f"User login: {username}, password: {password}")

# GOOD: Safe logging
logger.info(f"User login: {username}")
```

### A10: Server-Side Request Forgery (SSRF)

**Check For**:
- [ ] Unvalidated URLs
- [ ] Internal service access
- [ ] Cloud metadata access
- [ ] File:// protocol abuse

**Detection Patterns**:
```python
# BAD: SSRF vulnerability
url = request.args.get('url')
response = requests.get(url)  # Can access internal services!

# GOOD: URL validation
from urllib.parse import urlparse

def is_safe_url(url):
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https') and \
           parsed.netloc not in ('localhost', '127.0.0.1', '169.254.169.254')
```

---

## Secret Detection Patterns

### Patterns to Search

```regex
# API Keys
(?i)(api[_-]?key|apikey)['":\s]*[=:]\s*['"]?[a-z0-9]{20,}

# AWS Keys
AKIA[0-9A-Z]{16}
[a-zA-Z0-9/+]{40}

# GitHub Tokens
ghp_[a-zA-Z0-9]{36}
github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}

# JWT
eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*

# Private Keys
-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----

# Database URLs
(mysql|postgres|mongodb)://[^:]+:[^@]+@

# Generic Passwords
(?i)(password|passwd|pwd)['":\s]*[=:]\s*['"][^'"]{8,}['"]
```

### Files to Check

```
.env
*.env
config.json
secrets.yaml
credentials.*
**/settings.py
**/config.py
docker-compose.yml
.aws/credentials
```

---

## Language-Specific Checks

### Python

```python
# Check for eval() usage
eval(user_input)  # Code injection!

# Check for exec() usage
exec(user_input)  # Code injection!

# Check for __import__ usage
__import__(module_name)  # Module injection!

# Check for subprocess with shell=True
subprocess.run(cmd, shell=True)  # Command injection!
```

### JavaScript/TypeScript

```javascript
// Check for eval()
eval(userInput);  // Code injection!

// Check for innerHTML
element.innerHTML = userInput;  // XSS!

// Check for dangerouslySetInnerHTML
<div dangerouslySetInnerHTML={{__html: userInput}} />  // XSS!

// Check for document.write
document.write(userInput);  // XSS!
```

### SQL

```sql
-- Check for dynamic SQL
EXECUTE 'SELECT * FROM users WHERE id = ' || user_id;  -- Injection!

-- Check for missing prepared statements
-- Always use parameterized queries
```

---

## Review Workflow

### Quick Scan (2 min)

1. Search for hardcoded secrets
2. Check for eval/exec usage
3. Verify input validation exists
4. Check authentication on endpoints

### Standard Review (10 min)

1. All quick scan checks
2. OWASP Top 10 review
3. Dependency vulnerability check
4. Authentication/authorization review

### Deep Audit (30+ min)

1. All standard review checks
2. Business logic review
3. Data flow analysis
4. Penetration test scenarios
5. Compliance verification
