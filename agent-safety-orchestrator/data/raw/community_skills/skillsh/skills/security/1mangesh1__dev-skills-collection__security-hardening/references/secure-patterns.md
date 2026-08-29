# Secure Coding Patterns

## Defense in Depth

Implement multiple layers of security:

```
User Input
    ↓
Validation (Whitelist allowed chars)
    ↓
Parameterized Query (Prevent injection)
    ↓
Rate Limiting (Prevent brute force)
    ↓
Logging (Audit trail)
    ↓
Response Filtering (Don't leak info)
```

## Secure API Design

### Authentication Every Request
```python
@app.route('/api/users')
@require_auth  # Check on every endpoint
def list_users():
    return get_users()
```

### Rate Limiting
```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    ...
```

### Minimal Permission Principle
```python
# Only request needed permissions
scope = "user:email"  # Not "user:*"
```

## Secrets Management Best Practices

1. **Never commit secrets**
   ```bash
   # .gitignore
   .env
   secrets/
   ```

2. **Use dedicated services**
   - AWS Secrets Manager
   - HashiCorp Vault
   - Azure Key Vault

3. **Rotate secrets regularly**
   - API keys: every 90 days
   - Passwords: every 60 days
   - Tokens: automatic refresh

4. **Audit secret access**
   - Log who accessed what
   - Alert on unusual access

## Network Security

- Use VPN for database access
- Private subnets for internal services
- WAF (Web Application Firewall) for APIs
- DDoS protection
- Network segmentation
