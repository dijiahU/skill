# Security Checklist

Use this reference to harden an auth design or to review an existing
implementation for obvious failures.

## Non-negotiables

- never store plaintext passwords
- never hardcode JWT, session, OAuth, or reset secrets in source
- never put passwords, reset links, or raw tokens into logs
- keep access tokens short-lived
- make refresh tokens or sessions revocable
- default privileged routes to deny unless a permission check passes

## Transport and browser safety

- require HTTPS in production
- use `HttpOnly` and `Secure` cookies for session auth
- set `SameSite` deliberately instead of leaving cookie policy implicit
- add CSRF protection for cookie-backed browser flows
- restrict CORS origins or OAuth redirect allowlists to trusted hosts only

## Credential and token hygiene

- hash passwords with a proven algorithm such as bcrypt or argon2
- rotate refresh tokens or session identifiers on login, refresh, and privilege changes when practical
- keep JWT payloads minimal
- treat refresh tokens as server-managed state, not as permanent user credentials
- expire password-reset and verification tokens quickly

## Authorization review

Check these explicitly:

- route or service-level role checks exist
- multi-tenant boundaries are enforced, not implied
- admin or support tooling has stricter controls than end-user flows
- account linking cannot silently escalate privileges

## Operational defenses

- rate-limit login, reset, MFA, and callback abuse points
- alert on repeated auth failures or suspicious refresh activity
- record enough audit context to investigate auth incidents
- avoid revealing whether a specific email exists unless the product requires it

## Common auth failures

### Invalid signature or token verification mismatch

Usually caused by:

- wrong secret or key
- using the access-token verifier against refresh tokens
- environment variables not loaded consistently across services

Check secret source, token type, issuer, audience, and clock skew handling.

### Browser login fails because of cookies or CORS

Usually caused by:

- missing `credentials` handling
- incorrect cookie flags
- cross-site cookie behavior blocked by `SameSite`
- frontend origin missing from the allowlist

Verify browser transport rules before rewriting the auth model.

### Refresh flow works once, then starts failing

Usually caused by:

- refresh token not stored or revoked correctly
- token expiry mismatch
- rotation logic issuing a new token without invalidating the old record

Inspect persistence and rotation order before touching JWT code.

## Release checklist

Before calling an auth change done, confirm:

- login success path
- invalid credentials path
- unauthorized path
- forbidden path for the wrong role
- logout or revocation path
- refresh or session renewal path if present
- OAuth callback validation if present
- one recovery path if password reset or verification flow exists
