# OWASP Top 10 and Security Best Practices

## OWASP Top 10 Vulnerabilities (2023)

### 1. Broken Access Control
**Problem:** Users can access resources they shouldn't have access to.

**Examples:**
- Horizontal escalation: User A viewing User B's data
- Vertical escalation: Regular user accessing admin functions
- Direct object reference: Guessing IDs like `/api/users/1`, `/api/users/2`

**Solutions:**
```python
# WRONG: Direct parameter access
@app.route('/users/<user_id>')
def get_user(user_id):
    return User.query.get(user_id)

# CORRECT: Check authorization
@app.route('/users/<user_id>')
@auth_required
def get_user(user_id):
    if current_user.id != user_id and not current_user.is_admin:
        abort(403)
    return User.query.get(user_id)
```

### 2. Cryptographic Failures
**Problem:** Sensitive data is exposed due to weak or missing encryption.

**Common Issues:**
- Storing passwords in plaintext
- Unencrypted sensitive data in transit
- Weak encryption algorithms
- No HTTPS

**Solutions:**
```python
# Use bcrypt for passwords
from bcrypt import hashpw, gensalt

password_hash = hashpw(password.encode(), gensalt())

# Use strong encryption for data at rest
from cryptography.fernet import Fernet
cipher = Fernet(encryption_key)
encrypted = cipher.encrypt(sensitive_data)

# Always use HTTPS
# Set HSTS header: Strict-Transport-Security: max-age=31536000
```

### 3. Injection (SQL, Command, LDAP)
**Problem:** Untrusted data is sent to interpreters as code.

**SQL Injection Example:**
```python
# WRONG
query = f"SELECT * FROM users WHERE email = '{email}'"
db.execute(query)

# CORRECT - Use parameterized queries
query = "SELECT * FROM users WHERE email = %s"
db.execute(query, (email,))
```

**Command Injection:**
```python
# WRONG
os.system(f"convert {user_input} output.jpg")

# CORRECT
subprocess.run(['convert', user_input, 'output.jpg'], check=True)
```

### 4. Insecure Design
**Problem:** Missing security controls in application design.

**Mitigation:**
- Threat modeling during design
- Attack surface analysis
- Define security requirements
- Security acceptance criteria
- Apply defense in depth

### 5. Security Misconfiguration
**Problem:** Using default configurations, exposed errors, outdated dependencies.

**Common Issues:**
- Default credentials still enabled
- Debug mode on in production
- Security headers missing
- Outdated software versions

**Checklist:**
- [ ] Remove default accounts
- [ ] Disable unnecessary services
- [ ] Set security headers (HSTS, CSP, etc.)
- [ ] Update all dependencies
- [ ] Run automated security scans

### 6. Vulnerable and Outdated Components
**Problem:** Using libraries with known vulnerabilities.

**Prevention:**
```bash
# Python - Check for vulnerabilities
pip-audit
safety check

# Node.js
npm audit
npm audit fix

# General - Software Composition Analysis (SCA)
# Use tools like Snyk, OWASP Dependency-Check
```

### 7. Identification and Authentication Failures
**Problem:** Credential compromise, weak password policies.

**Solutions:**
```
Password Requirements:
  ✓ Minimum 12-14 characters
  ✓ Must include: uppercase, lowercase, numbers, symbols
  ✓ Expire every 90 days
  ✓ No reuse of last 5 passwords
  
MFA/2FA:
  ✓ TOTP (Time-based One-Time Password)
  ✓ SMS codes (less secure, use as backup)
  ✓ Security keys (FIDO2, U2F)
  
JWT Best Practices:
  ✓ Short expiration time (15 mins)
  ✓ Use HTTPS only
  ✓ Include signature verification
  ✓ Implement token refresh mechanism
```

### 8. Software and Data Integrity Failures
**Problem:** CI/CD pipeline is compromised or updates are insecure.

**Security Measures:**
- Sign releases cryptographically
- Verify checksums/signatures
- Use secure CI/CD with limited access
- Monitor for unauthorized changes
- Pin dependency versions

### 9. Logging and Monitoring Failures
**Problem:** Security incidents go undetected.

**What to Log:**
```
✓ Authentication attempts (successes and failures)
✓ Authorization failures
✓ Data access
✓ Configuration changes
✓ System errors
✗ Don't log: passwords, credit cards, API keys
```

**Monitoring:**
- Alert on repeated failed logins
- Alert on privilege escalations
- Monitor error rates
- Track unusual access patterns

### 10. Server-Side Request Forgery (SSRF)
**Problem:** Application fetches resources from attacker-controlled URLs.

**Prevention:**
```python
# WRONG
import requests
url = request.args.get('url')
data = requests.get(url)

# CORRECT - Validate URL
from urllib.parse import urlparse
url = request.args.get('url')
parsed = urlparse(url)

# Only allow specific domains
ALLOWED_DOMAINS = ['example.com', 'trusted-api.com']
if parsed.hostname not in ALLOWED_DOMAINS:
    return "URL not allowed", 403

data = requests.get(url, timeout=5)
```

## Security Checklist for Every Application

- [ ] HTTPS/TLS for all communication
- [ ] Authentication and authorization
- [ ] Input validation on all user inputs
- [ ] CSRF protection for state-changing operations
- [ ] Content Security Policy headers
- [ ] No sensitive data in logs
- [ ] Secure password storage (bcrypt, PBKDF2, Argon2)
- [ ] Rate limiting on login/API endpoints
- [ ] SQL injection protection (parameterized queries)
- [ ] XSS protection (output encoding)
- [ ] Security headers configured
- [ ] Dependencies regularly scanned for vulnerabilities
- [ ] Error handling doesn't expose sensitive info
- [ ] Secrets managed securely (not in code/logs)
- [ ] Regular security testing (SAST, DAST, penetration testing)
