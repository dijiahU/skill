# OWASP Frontend Security Reference

## OWASP Top 10 for Frontend

### 1. Cross-Site Scripting (XSS)

**Prevention:**

```javascript
// ❌ DANGEROUS: innerHTML with user input
element.innerHTML = userInput

// ✅ SAFE: textContent for plain text
element.textContent = userInput

// ✅ SAFE: Sanitize if HTML needed
import DOMPurify from 'dompurify'
element.innerHTML = DOMPurify.sanitize(userInput)
```

**Types of XSS:**
- **Stored XSS:** Malicious script stored in database, served to users
- **Reflected XSS:** Script in URL parameters reflected in response
- **DOM-based XSS:** Script manipulates DOM directly

### 2. Broken Authentication

**Prevention:**
- Use httpOnly cookies for session tokens
- Implement token refresh with short-lived access tokens
- Never store sensitive tokens in localStorage
- Implement proper logout (server-side token invalidation)

### 3. Sensitive Data Exposure

**Prevention:**
- Never log passwords, tokens, or PII to console
- Don't store sensitive data in client-side state
- Use HTTPS for all API communication
- Mask sensitive input fields

### 4. Broken Access Control

**Prevention:**
- Client-side access control is UI-only (server must verify)
- Validate redirects against allowlist
- Don't expose admin features based on client-side flags

### 5. Security Misconfiguration

**Prevention:**
- Configure CSP headers properly
- Disable debug mode in production
- Remove development tools and console logs
- Use secure cookie flags

---

## Client-Side Storage Security

### localStorage/sessionStorage

```javascript
// ❌ NEVER store in localStorage:
// - Access tokens
// - Refresh tokens
// - Session IDs
// - Credit card numbers
// - Passwords

// localStorage is accessible to any script (XSS vulnerable)
localStorage.setItem('token', sensitiveToken)  // DANGEROUS

// ⚠️ Use only for non-sensitive data
localStorage.setItem('theme', 'dark')  // OK
localStorage.setItem('language', 'de')  // OK
```

### Secure Token Storage Options

| Method | XSS Risk | CSRF Risk | Recommendation |
|--------|----------|-----------|----------------|
| localStorage | HIGH | None | Never for tokens |
| sessionStorage | HIGH | None | Never for tokens |
| httpOnly Cookie | None | Medium | Best for refresh tokens |
| Memory (JS variable) | Low | None | Good for access tokens |
| Secure Cookie (non-httpOnly) | Medium | Medium | Avoid |

### Best Practice: Memory + httpOnly Cookie

```javascript
// Access token: Store in memory (cleared on page refresh)
let accessToken = null

function setAccessToken(token) {
  accessToken = token
}

function getAccessToken() {
  return accessToken
}

// Refresh token: httpOnly cookie (set by server)
// Frontend never sees it, automatically sent with requests
async function refreshAccessToken() {
  const response = await fetch('/api/auth/refresh', {
    method: 'POST',
    credentials: 'include'  // Send httpOnly cookie
  })
  const { accessToken } = await response.json()
  setAccessToken(accessToken)
}
```

---

## Browser Security Features

### Content Security Policy (CSP)

```html
<!-- HTTP Header (recommended) or meta tag -->
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  script-src 'self' 'nonce-abc123';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  connect-src 'self' https://api.example.com;
  font-src 'self';
  object-src 'none';
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
">
```

**Key Directives:**

| Directive | Purpose | Recommendation |
|-----------|---------|----------------|
| `default-src` | Fallback for all | `'self'` |
| `script-src` | JavaScript sources | `'self'` + nonces |
| `style-src` | CSS sources | `'self'` (avoid `'unsafe-inline'`) |
| `img-src` | Image sources | `'self' data: https:` |
| `connect-src` | XHR/Fetch/WebSocket | Explicit API origins |
| `frame-ancestors` | Who can embed | `'none'` (prevent clickjacking) |

### Subresource Integrity (SRI)

```html
<!-- Always use SRI for external scripts/styles -->
<script
  src="https://cdn.example.com/lib.js"
  integrity="sha384-oqVuAfXRKap7fdgcCY5uykM6+R9GqQ8K/uxy9rx7HNQlGYl1kPzQho1wx4JwY8wC"
  crossorigin="anonymous"
></script>
```

### Security Headers

```
# Prevent clickjacking
X-Frame-Options: DENY

# Prevent MIME sniffing
X-Content-Type-Options: nosniff

# Enforce HTTPS
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload

# Control referrer information
Referrer-Policy: strict-origin-when-cross-origin

# Restrict feature access
Permissions-Policy: geolocation=(), camera=(), microphone=()
```

---

## Secure Cookie Configuration

### Cookie Flags

```javascript
// Server sets cookies with these flags
Set-Cookie: sessionId=abc123;
  HttpOnly;       // Not accessible via JavaScript (XSS protection)
  Secure;         // Only sent over HTTPS
  SameSite=Strict;  // Not sent with cross-site requests (CSRF protection)
  Path=/;         // Cookie scope
  Max-Age=86400   // Expiry (in seconds)
```

| Flag | Purpose | When to Use |
|------|---------|-------------|
| `HttpOnly` | Prevent JS access | Always for session/auth cookies |
| `Secure` | HTTPS only | Always in production |
| `SameSite=Strict` | No cross-site | Auth cookies, most secure |
| `SameSite=Lax` | Some cross-site | Default, allows GET navigation |
| `SameSite=None` | All cross-site | Third-party cookies (requires Secure) |

---

## Input Validation

### Client-Side Validation (UI Only)

```javascript
// Client validation improves UX but NEVER trust it for security
function validateEmail(email) {
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return regex.test(email)
}

function validatePassword(password) {
  return password.length >= 8 &&
         /[A-Z]/.test(password) &&
         /[a-z]/.test(password) &&
         /[0-9]/.test(password)
}

// Always validate on server too!
```

### URL Validation

```javascript
function isValidUrl(url) {
  try {
    const parsed = new URL(url)
    return ['http:', 'https:'].includes(parsed.protocol)
  } catch {
    return false
  }
}

function isSameOrigin(url) {
  try {
    const parsed = new URL(url, window.location.origin)
    return parsed.origin === window.location.origin
  } catch {
    return false
  }
}

// Redirect validation
function safeRedirect(url) {
  if (isSameOrigin(url) || ALLOWED_EXTERNAL_ORIGINS.includes(new URL(url).origin)) {
    window.location.href = url
  } else {
    window.location.href = '/dashboard'  // Fallback
  }
}
```

### File Upload Validation

```javascript
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'application/pdf']
const MAX_SIZE = 5 * 1024 * 1024  // 5MB

function validateFile(file) {
  const errors = []

  if (!ALLOWED_TYPES.includes(file.type)) {
    errors.push('Invalid file type')
  }

  if (file.size > MAX_SIZE) {
    errors.push('File too large (max 5MB)')
  }

  // Check file extension matches type
  const ext = file.name.split('.').pop()?.toLowerCase()
  const expectedExts = {
    'image/jpeg': ['jpg', 'jpeg'],
    'image/png': ['png'],
    'application/pdf': ['pdf']
  }

  if (expectedExts[file.type] && !expectedExts[file.type].includes(ext)) {
    errors.push('File extension mismatch')
  }

  return errors
}
```

---

## API Security

### Secure Fetch Wrapper

```javascript
async function secureFetch(url, options = {}) {
  const config = {
    ...options,
    credentials: 'include',  // Include cookies
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    }
  }

  // Add CSRF token for state-changing requests
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method)) {
    const csrfToken = getCsrfToken()  // From cookie or meta tag
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken
    }
  }

  try {
    const response = await fetch(url, config)

    if (response.status === 401) {
      // Token expired - try refresh or redirect to login
      await handleUnauthorized()
      return null
    }

    if (!response.ok) {
      // Don't expose error details to users
      console.error('API Error:', response.status)
      throw new Error('Request failed')
    }

    return response.json()
  } catch (error) {
    // Log for debugging, show generic message to user
    console.error('Fetch error:', error)
    throw new Error('Network error')
  }
}
```

### Rate Limiting Awareness

```javascript
class RateLimitedClient {
  private retryAfter = 0

  async request(url, options) {
    if (Date.now() < this.retryAfter) {
      throw new Error('Rate limited. Please wait.')
    }

    const response = await fetch(url, options)

    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After')
      this.retryAfter = Date.now() + (parseInt(retryAfter || '60') * 1000)
      throw new Error('Too many requests. Please try again later.')
    }

    return response
  }
}
```

---

## Third-Party Dependencies

### Audit Process

```bash
# Check for vulnerabilities
pnpm audit

# Auto-fix where safe
pnpm audit --fix

# Check outdated packages
pnpm outdated

# Update to latest (careful with major versions)
pnpm update
```

### Dependency Best Practices

1. **Lock versions**: Always commit `pnpm-lock.yaml`
2. **Regular audits**: Run `pnpm audit` in CI/CD
3. **Minimal dependencies**: Fewer deps = smaller attack surface
4. **Review before adding**: Check package popularity, maintenance, and security
5. **CDN integrity**: Always use SRI for CDN resources

---

## DevTools Security

### Production Safeguards

```javascript
// Remove console statements in production build
// Most bundlers support this via configuration

// Disable right-click (not a security measure, just UX)
// Don't rely on this for security!

// Detect DevTools (not reliable, just awareness)
// Not a security measure - determined attackers bypass this

// REAL security: Proper server-side validation and authentication
```
