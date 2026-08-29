# Web Hardening Checklist

Use this reference when the user needs concrete control families or a quick
review checklist after the trust boundary is already clear.

## Transport and browser policy

- HTTPS end to end in production
- HSTS where the deployment model supports it
- sensible `Content-Security-Policy`
- `X-Frame-Options` or `frame-ancestors`
- `Referrer-Policy`
- `Permissions-Policy`
- cookie flags: `Secure`, `HttpOnly`, `SameSite`

## Input and output handling

- validate all untrusted request input at boundaries
- use parameterized queries or ORM-safe query paths
- encode or sanitize output only where raw HTML or rich content is truly needed
- constrain file uploads by size, type, and storage path
- validate outbound URLs and network targets when SSRF risk exists

## Session and request integrity

- CSRF protection for cookie-authenticated state-changing requests
- session rotation on privilege change or login
- logout invalidation or token revocation where session semantics require it
- replay-aware handling for refresh or one-time flows

## Abuse controls

- rate limits by endpoint risk, not only one global default
- stronger throttles on login, password reset, invite, and verification flows
- lockout or challenge policy that does not permanently trap valid users
- audit logging for auth failures and suspicious actions

## Secret handling

- no committed secrets
- runtime secret loading from env, vault, or platform secret store
- secret rotation path documented for high-value credentials
- avoid leaking secrets through logs, error messages, or client bundles

## Dependency and config hygiene

- patch vulnerable dependencies on a defined cadence
- do not ship default credentials or open admin surfaces
- keep production/debug settings clearly separated
- verify CORS is narrowed to the real callers

## Quick anti-patterns

- wildcard CORS with credentials
- user-controlled HTML rendered directly without a trusted sanitization plan
- raw SQL string interpolation
- missing rate limits on auth and reset flows
- security headers present in docs but absent in the real deployment
