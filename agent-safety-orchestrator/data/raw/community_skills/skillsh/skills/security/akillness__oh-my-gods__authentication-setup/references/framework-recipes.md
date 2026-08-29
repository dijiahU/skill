# Framework Recipes

Use this reference when the main skill has already selected an auth model and
you need concrete implementation structure.

## Triage checklist

Capture these facts before writing code:

- product shape: SPA, server-rendered app, mobile backend, internal admin tool
- auth method: session, JWT, OAuth, SSO, MFA, or hybrid
- backend stack: framework, language, ORM, DB, cache
- user model: local password, external identity, or both
- revocation model: session store, refresh-token table, provider logout, device list

## Minimal data model

Use the smallest schema that still supports revocation and permissions.

Typical fields:

- `users`: `id`, `email`, `password_hash` if local passwords exist, `role`, `is_verified`, timestamps
- `sessions` or `refresh_tokens`: opaque or hashed token identifier, `user_id`, `expires_at`, optional `revoked_at`
- `oauth_accounts` when external identity exists: provider, provider subject, local user id
- `mfa_enrollments` only when MFA is actually in scope

Prefer hashed or opaque refresh-token storage over storing reusable secrets in
plaintext.

## Node or TypeScript JWT recipe

Use when the client really needs bearer tokens:

1. hash passwords with `bcrypt` or `argon2`
2. issue short-lived access tokens
3. persist refresh tokens or refresh-token identifiers for revocation
4. keep token payloads minimal, such as `userId`, `role`, and tenant claims only if necessary
5. gate privileged routes with a separate authorization layer

Recommended modules:

- `auth/password.ts`
- `auth/tokens.ts`
- `auth/middleware.ts`
- `auth/routes.ts`
- `auth/service.ts`

## Python or FastAPI JWT recipe

Use when the product is Python-first and token auth is still the right fit:

1. hash passwords with `argon2` or `bcrypt` via a maintained library
2. issue short-lived access tokens and persist revocable refresh-token state
3. keep token verification and role checks in shared dependencies, not inline in every route
4. centralize token issuance, rotation, and revocation in one service layer
5. prefer framework-native session auth instead when the app is server-rendered and same-origin

Recommended modules:

- `auth/password.py`
- `auth/tokens.py`
- `auth/dependencies.py`
- `auth/routes.py`
- `auth/service.py`

## Session-based recipe

Prefer this for same-origin or server-rendered applications:

- store sessions in Redis or another shared store, not process memory in production
- set `HttpOnly`, `Secure`, and appropriate `SameSite` cookie flags
- rotate session identifiers on login and privilege changes
- pair cookie auth with CSRF protection when the browser auto-sends credentials

## OAuth or SSO recipe

When adding Google, GitHub, OIDC, or enterprise SSO:

- validate redirect URIs and allowed callback hosts
- persist provider subject identifiers separately from local user ids
- define an explicit account-linking policy for existing local accounts
- fail closed on missing email verification or missing required org or tenant claims
- record what local authorization model still applies after identity proof succeeds

## Endpoint checklist

Only create endpoints the product needs. Common set:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/refresh`
- `GET /auth/me`
- provider callback endpoint when OAuth or SSO exists

For each endpoint, verify:

- input validation
- rate limiting where abuse risk exists
- uniform auth failure behavior
- revocation or persistence updates
- structured logging without secrets

## Environment and secret checklist

Typical runtime secrets:

- access-token secret or signing key
- refresh-token secret if separate
- session secret
- OAuth client id and secret
- database and cache URLs

Keep them in environment variables or a managed secret store. Provide an
`.env.example` or equivalent contract, but never commit real values.
