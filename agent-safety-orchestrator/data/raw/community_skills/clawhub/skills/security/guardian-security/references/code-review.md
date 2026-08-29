# Code Review (Security) — Reference Guide

Security-focused code review, injection risks, data exposure, and the vulnerabilities
most likely to affect a small digital business.

---

## TABLE OF CONTENTS
1. Security Code Review Methodology
2. The OWASP Top 10 for Small Business
3. Injection Vulnerabilities
4. Authentication & Session Security
5. Data Exposure Risks
6. Dependency Security
7. Security Review Checklist
8. Code Patterns: Safe vs. Unsafe

---

## 1. SECURITY CODE REVIEW METHODOLOGY

### The Review Order
```
1. CREDENTIALS FIRST (< 2 minutes)
   Scan entire codebase for hardcoded secrets
   If found: STOP, treat as incident, don't continue

2. INPUT VALIDATION (5-10 minutes)
   Every place external input enters the system
   Is it validated before use?
   Is it sanitized before going into SQL, file paths, or commands?

3. DATA EXPOSURE (5 minutes)
   What sensitive data touches this code?
   Where does it get logged?
   Where does it get transmitted?

4. AUTHENTICATION & AUTHORIZATION (5 minutes)
   Who is allowed to call this code?
   Is that checked before the operation executes?
   Are errors handled securely?

5. DEPENDENCIES (2 minutes)
   Are all dependencies known and current?
   Any with known critical vulnerabilities?
```

---

## 2. THE OWASP TOP 10 (SMALL BUSINESS EDITION)

The vulnerabilities most likely to affect TLC systems:

### A1: Broken Access Control
```
What it is: Users can do things they shouldn't be allowed to do.

In our context:
  - Webhook endpoints accepting requests without signature verification
  - API endpoints callable without authentication
  - Admin functions accessible without authorization check

CODE PATTERN TO CATCH:
  BAD (no auth check):
    @app.route('/admin/delete-product', methods=['POST'])
    def delete_product():
        product_id = request.json['id']
        db.delete_product(product_id)
        return {'success': True}
  
  GOOD (with auth check):
    @app.route('/admin/delete-product', methods=['POST'])
    @require_auth  # decorator that verifies authorization
    def delete_product():
        ...
```

### A3: Injection
```
What it is: Untrusted data sent to an interpreter as a command.

SQL Injection — the most common:
  BAD:
    query = f"SELECT * FROM users WHERE email = '{user_email}'"
    db.execute(query)
  
  GOOD (parameterized):
    db.execute("SELECT * FROM users WHERE email = ?", (user_email,))

Command Injection:
  BAD:
    subprocess.run(f"convert {user_filename} output.pdf", shell=True)
  
  GOOD (argument list, not shell string):
    subprocess.run(["convert", user_filename, "output.pdf"])
```

### A2: Cryptographic Failures
```
What it is: Sensitive data transmitted or stored without proper protection.

In our context:
  - Webhook secrets compared with == instead of hmac.compare_digest()
  - Passwords stored in plain text (if we ever store passwords)
  - Sensitive data in URLs (visible in logs and browser history)

CODE PATTERN:
  BAD (timing-vulnerable):
    if signature == expected_signature:
  
  GOOD (timing-safe):
    if hmac.compare_digest(signature, expected_signature):
```

### A6: Vulnerable Components
```
What it is: Using components (libraries) with known security vulnerabilities.

Check:
  pip install pip-audit
  pip-audit  # Reports known vulnerabilities in installed packages

Remediation:
  Update vulnerable packages promptly
  Monitor for new CVEs in dependencies
```

---

## 3. INJECTION VULNERABILITY DEEP DIVE

### SQL Injection Prevention
```python
# BAD — vulnerable to SQL injection
def get_user_by_email(email: str) -> dict:
    query = f"SELECT * FROM users WHERE email = '{email}'"
    return db.execute(query).fetchone()
    # If email = "'; DROP TABLE users; --" → disaster

# GOOD — parameterized queries
def get_user_by_email(email: str) -> dict:
    return db.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    ).fetchone()
```

### Path Traversal Prevention
```python
# BAD — allows file reading outside intended directory
@app.route('/download/<filename>')
def download_file(filename):
    return send_file(f'/data/{filename}')
    # If filename = "../../etc/passwd" → system file exposed!

# GOOD — sanitize and validate path
import os
from pathlib import Path

@app.route('/download/<filename>')
def download_file(filename):
    # Get the absolute path and verify it's inside our data directory
    data_dir = Path('/data').resolve()
    requested_path = (data_dir / filename).resolve()
    
    # Verify the requested path is inside our data directory
    if not str(requested_path).startswith(str(data_dir)):
        abort(403, "Access denied")
    
    if not requested_path.exists():
        abort(404)
    
    return send_file(requested_path)
```

---

## 4. DATA EXPOSURE RISKS

### What Should Never Appear in Logs
```python
# Items that should NEVER be logged:
NEVER_LOG = [
    'password',
    'api_key', 'api_secret',
    'access_token', 'refresh_token',
    'credit_card', 'card_number',
    'ssn', 'social_security',
    'webhook_secret',
    'customer_email',    # PII
    'customer_phone',    # PII
    'stripe_secret_key',
]

# Safe logging pattern
def safe_log(data: dict) -> dict:
    """Remove sensitive fields before logging."""
    return {
        k: '[REDACTED]' if any(sensitive in k.lower() for sensitive in NEVER_LOG) else v
        for k, v in data.items()
    }

# Usage:
logger.debug(f"Processing request: {safe_log(request_data)}")
```

---

## 5. SECURITY REVIEW CHECKLIST

### Pre-Deployment Security Checklist
```
CREDENTIALS:
- [ ] No hardcoded credentials anywhere in code (grep verified)
- [ ] .env is in .gitignore
- [ ] .env.example exists with no real values
- [ ] All secrets loaded from environment variables
- [ ] No secrets logged or printed

INPUT HANDLING:
- [ ] All user inputs validated before processing
- [ ] All SQL queries use parameterized statements
- [ ] File paths validated against allowed directories
- [ ] External data parsed safely (JSON decode errors caught)

AUTHENTICATION:
- [ ] Webhook signatures verified before processing
- [ ] Admin routes require authentication
- [ ] Authentication failures return 401, not 200

ERROR HANDLING:
- [ ] Error messages don't expose internal details
- [ ] Stack traces not visible to end users
- [ ] Failures logged with context (without sensitive data)

DEPENDENCIES:
- [ ] pip-audit run (no critical vulnerabilities)
- [ ] No packages installed from unknown sources
- [ ] requirements.txt has pinned versions

DATA:
- [ ] Sensitive data not logged
- [ ] PII handled per privacy standards
- [ ] Customer data only accessible to authorized code paths
```

---

## 6. CODE PATTERNS: SAFE VS. UNSAFE

### Quick Reference
```
UNSAFE → SAFE

SQL: f"SELECT * FROM t WHERE id = {id}"
   → db.execute("SELECT * FROM t WHERE id = ?", (id,))

LOG: logger.info(f"Auth with key: {api_key}")
   → logger.info("Auth: [key_present=True]")

COMPARE: if token == expected:
   → if hmac.compare_digest(token, expected):

FILE: open(f"/data/{user_input}", 'r')
   → validate_path_is_in_data_dir(user_input); open(safe_path)

SUBPROCESS: subprocess.run(f"cmd {user_input}", shell=True)
   → subprocess.run(["cmd", user_input])

RANDOM: import random; token = random.randint(...)
   → import secrets; token = secrets.token_urlsafe(32)
```
