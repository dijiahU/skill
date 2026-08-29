---
name: general-frontend-security
description: Framework-agnostic frontend security guide based on OWASP Secure Coding Practices. Covers XSS prevention, CSRF protection, Content Security Policy (CSP), secure cookie configuration, client-side authentication patterns, input validation, secure storage, and security headers. Activates for security audits, vulnerability reviews, XSS, CSRF, CSP, injection, security headers, or browser security questions in any web application. NOT for backend/NestJS security (use generating-nest-servers). NOT for Nuxt-specific implementation (use developing-lt-frontend).
user-invocable: false
---

# General Frontend Security

Framework-agnostic security practices for web applications based on OWASP guidelines.

## When to Use This Skill

- Reviewing frontend code for security vulnerabilities
- Implementing client-side authentication flows
- Setting up secure cookie handling
- Configuring Content Security Policy
- Auditing third-party dependencies
- General frontend security questions

## Skill Boundaries

| User Intent | Correct Skill |
|------------|---------------|
| "XSS prevention best practices" | **THIS SKILL** |
| "Security audit of frontend" | **THIS SKILL** |
| "Configure CSP headers" | **THIS SKILL** |
| "Build a secure login page in Nuxt" | developing-lt-frontend |
| "Fix @Restricted decorator in NestJS" | generating-nest-servers |
| "Run npm audit fix" | maintaining-npm-packages |

## Related Skills & Commands

| Command | Purpose |
|---------|---------|
| `/lt-dev:review` | General security review of branch diff (framework-agnostic) |
| `/lt-dev:backend:sec-review` | Security review of backend code changes (auth, decorators, models) |
| `/lt-dev:backend:sec-audit` | Full OWASP security audit (dependencies, config, code) |

## Framework-Specific References

| Framework | Reference File |
|-----------|---------------|
| Nuxt/Vue | See `developing-lt-frontend` skill (reference/security.md) |
| Angular | [angular-security.md](${CLAUDE_SKILL_DIR}/angular-security.md) |

## Key Principles

1. **Never trust client-side validation** - Server must always verify
2. **Store tokens securely** - Memory for access tokens, httpOnly cookies for refresh tokens
3. **Prevent XSS** - Never use `innerHTML` with user input; use `textContent` or DOMPurify
4. **Protect against CSRF** - Use CSRF tokens for state-changing requests + `SameSite` cookies
5. **Configure CSP** - Restrict script/style sources, use nonces, block framing
6. **Minimize dependencies** - Fewer deps = smaller attack surface; always run `pnpm audit`

**Complete OWASP reference with code examples: [owasp-reference.md](${CLAUDE_SKILL_DIR}/owasp-reference.md)**

## Security Checklist

### Development

- [ ] No sensitive data in client-side code
- [ ] Environment variables separated (public vs private)
- [ ] Input validation on all user inputs
- [ ] XSS prevention (no innerHTML with user data)
- [ ] CSRF tokens for state-changing requests

### Authentication

- [ ] Tokens stored securely (memory + httpOnly cookies)
- [ ] Token refresh mechanism implemented
- [ ] Proper logout (clear all client state)
- [ ] Session timeout configured

### Configuration

- [ ] HTTPS enforced
- [ ] CSP headers configured
- [ ] Security headers set (X-Frame-Options, etc.)
- [ ] Cookies configured with secure flags
- [ ] CORS properly restricted

### Dependencies

- [ ] pnpm audit clean (or accepted risks)
- [ ] pnpm-lock.yaml committed
- [ ] SRI for external resources
- [ ] Regular dependency updates

### Build & Deploy

- [ ] Debug mode disabled
- [ ] Console logs removed
- [ ] Source maps disabled or restricted
- [ ] Error messages generic (no stack traces)
