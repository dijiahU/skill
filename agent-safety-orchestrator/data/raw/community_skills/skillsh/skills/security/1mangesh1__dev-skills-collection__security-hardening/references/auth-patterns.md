# Authentication and Authorization Patterns

## Authentication Methods

### 1. Basic Authentication
```
Authorization: Basic base64(username:password)
```
- Pros: Simple
- Cons: Credentials in every request, must use HTTPS
- Use Case: Simplistic APIs, internal services only

### 2. Bearer Tokens (JWT)
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**JWT Structure:**
```
Header.Payload.Signature

Header: {"alg": "HS256", "typ": "JWT"}
Payload: {"sub": "user123", "exp": 1234567890, "iat": 1234567800}
Signature: HMACSHA256(Header.Payload, secret_key)
```

**Best Practices:**
- Short expiration (15-60 minutes)
- Refresh token for getting new JWT
- Verify signature on every request
- HTTPS only
- Store in httpOnly cookie or secure storage

### 3. OAuth 2.0
**For delegated access to third-party services.**

```
1. User clicks "Login with Google"
2. Redirect to Google authorization endpoint
3. User grants permission
4. Google redirects back with authorization code
5. Exchange code for access token
6. Use token to access user's Google resources
```

**Flows:**
- Authorization Code: Web apps, server-to-server
- Implicit: Single-page apps (deprecated)
- Resource Owner Password: Legacy apps
- Client Credentials: Service-to-service

### 4. SAML
**Enterprise single sign-on.**

- XML-based
- Used in corporate environments
- Supports federated identity

### 5. OpenID Connect
**OAuth 2.0 + authentication.**

- Built on OAuth 2.0
- Adds ID tokens
- User information endpoint

## Authorization Strategies

### 1. Role-Based Access Control (RBAC)
```python
roles = {
    'user': ['read'],
    'moderator': ['read', 'delete_comments'],
    'admin': ['read', 'write', 'delete', 'manage_users']
}

@app.route('/admin')
@auth_required
def admin_panel():
    if 'admin' not in current_user.roles:
        abort(403)
    return render_template('admin.html')
```

**Typical Roles:**
- Admin: Full access
- Moderator: Can moderate content
- User: Limited write access
- Guest: Read-only

### 2. Attribute-Based Access Control (ABAC)
More granular control based on attributes.

```python
def has_permission(user, resource, action):
    # Check multiple attributes
    conditions = [
        user.department == resource.department,
        user.level >= resource.required_level,
        user.created_at < (now - timedelta(days=30)),
        resource.status != 'archived'
    ]
    return all(conditions)
```

### 3. Access Control Lists (ACL)
Define who can do what with a resource.

```python
# User-specific permissions for a document
document.permissions = {
    'user123': ['read', 'write'],
    'user456': ['read'],
    'user789': ['read', 'write', 'share']
}
```

### 4. Policy-Based Access Control
```yaml
policy:
  - resource: "posts"
    action: "create"
    effect: "allow"
    conditions:
      - user.verified == true
      - user.created_at < now - 7days
  
  - resource: "posts"
    action: "delete"
    effect: "allow"
    principals: ["admin", "post_author"]
```

## Session Management

### Token-Based vs Session-Based

**Session-Based:**
```
1. User logs in → Server creates session
2. Session ID in cookie/localStorage
3. Server validates session on each request
4. Pros: Easy to revoke, server-controlled
5. Cons: Requires sticky sessions in distributed systems
```

**Token-Based:**
```
1. User logs in → Get token (JWT)
2. Send token with each request
3. Server validates signature (no database lookup)
4. Pros: Stateless, scalable, works with microservices
5. Cons: Can't revoke immediately (need blacklist)
```

### Token Revocation

```python
# Maintain revocation list (for JWTs)
class TokenBlacklist:
    def __init__(self):
        self.blacklist = set()
    
    def revoke(self, token_jti):
        """Mark token as revoked."""
        self.blacklist.add(token_jti)
    
    def is_revoked(self, token_jti):
        return token_jti in self.blacklist

# Clean up old revoked tokens
def cleanup_expired_tokens():
    now = datetime.utcnow()
    self.blacklist = {
        token for token in self.blacklist
        if token.expiry > now
    }
```

## Password Storage

### Hashing Algorithms (Ordered by Security)

1. **Argon2** (Best choice)
   - Memory-hard function
   - Resistant to GPU attacks
   - Tunable complexity

2. **bcrypt**
   - Good security
   - Slow computation time
   - Built-in salt generation

3. **PBKDF2**
   - Acceptable
   - Requires high iteration count (100k+)
   - Less resistant to GPU attacks

4. **scrypt**
   - Memory-hard like Argon2
   - Less standard than bcrypt

### Implementation

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

# Hashing
password_hash = ph.hash("user_password")

# Verification
try:
    ph.verify(password_hash, "user_password")
    print("Password correct!")
except VerifyMismatchError:
    print("Password incorrect!")

# Check if needs rehashing (due to parameters change)
if ph.check_needs_rehash(password_hash):
    new_hash = ph.hash(password)
    save_to_database(new_hash)
```

## Multi-Factor Authentication (MFA)

### TOTP (Time-based One-Time Password)

```python
import pyotp

# Generate secret
secret = pyotp.random_base32()
# Share QR code with user: pyotp.totp.TOTP(secret).provisioning_uri(...)

# Verify code
totp = pyotp.TOTP(secret)
if totp.verify(user_input_code):
    # Code is valid
    pass

# Recovery codes (backup)
backup_codes = [generate_random_code() for _ in range(10)]
```

### FIDO2/WebAuthn (Passwordless)

Most secure - hardware security keys or biometric.

```javascript
// Registration
const credential = await navigator.credentials.create({
    publicKey: {
        challenge: new Uint8Array(32),
        rp: { name: "Example Corp" },
        user: {
            id: new Uint8Array(16),
            name: "user@example.com",
            displayName: "User Name"
        },
        pubKeyCredParams: [{ alg: -7, type: "public-key" }]
    }
});

// Authentication
const assertion = await navigator.credentials.get({
    publicKey: {
        challenge: new Uint8Array(32),
        timeout: 60000,
        userVerification: "preferred"
    }
});
```
