# OWASP Top 10 Prevention Techniques

## 1. SQL Injection Prevention

### ❌ Vulnerable Code
```python
query = f"SELECT * FROM users WHERE email = '{email}'"
```

### ✓ Safe Code
```python
cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
```

## 2. XSS (Cross-Site Scripting) Prevention

### ❌ Vulnerable
```html
<div>{{ user.name }}</div>  <!-- If user.name = "<script>alert('xss')</script>" -->
```

### ✓ Safe
```html
<!-- Most frameworks auto-escape by default -->
<div>{{ user.name | escape }}</div>
```

## 3. CSRF (Cross-Site Request Forgery) Prevention

### ❌ Vulnerable
```html
<form action="/transfer-money" method="POST">
  <input name="amount" value="1000">
  <button>Transfer</button>
</form>
```

### ✓ Safe
```html
<form action="/transfer-money" method="POST">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <input name="amount" value="1000">
  <button>Transfer</button>
</form>
```

## 4. Authentication & Session Security

**Do:**
- Use HTTPS only
- HttpOnly + Secure cookies
- Implement timeout
- Rotate session IDs
- Use MFA

## 5. Input Validation

### ❌ Trust Everything
```python
user_id = request.args.get('id')  # Any value accepted
```

### ✓ Validate Input
```python
user_id = int(request.args.get('id', 0))
if user_id < 1:
    raise ValueError("Invalid user ID")
```

## 6. Secrets Management

### ❌ Hardcoded
```python
DB_PASSWORD = "super_secret_123"
```

### ✓ Environment Variables
```python
DB_PASSWORD = os.environ.get('DB_PASSWORD')
```

## 7. Dependency Security

```bash
# Check for vulnerable packages
npm audit
pip check
cargo audit

# Keep dependencies updated
npm update
pip install --upgrade -r requirements.txt
```

## 8. Error Handling

### ❌ Leaks Information
```python
except Exception as e:
    return {"error": str(e)}  # Shows internal details
```

### ✓ Generic Error
```python
except Exception as e:
    logger.error(f"Error: {e}")  # Log internally
    return {"error": "Internal server error"}  # Generic to user
```
