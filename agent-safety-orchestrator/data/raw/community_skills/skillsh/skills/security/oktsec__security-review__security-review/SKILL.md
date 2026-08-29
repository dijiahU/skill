---
name: security-review
description: Security review for AI-built projects. Covers OWASP Top 10. Auto-detects stack, runs 130+ checks for secrets, injection, auth, SSRF, database access (Supabase RLS, Firebase rules), Next.js NEXT_PUBLIC_ exposure, Clerk, AI/LLM prompt injection, deserialization, logging gaps, file uploads, OAuth, webhooks, dependencies. Report with exact fixes. Use when user says "review my code", "is this secure", "security check", "audit my project", or "I built this with AI".
metadata:
  author: oktsec
  version: 3.0.0
  license: Apache-2.0
---

# Security Review

Security review for code built with LLMs. Auto-detects the stack, runs checks organized by severity, produces a graded report with exact fixes.

No questions. No setup. Read the project and review it.

## Instructions

### Phase 1: Detect

Read the project root. Detect everything automatically. Do NOT ask the user questions.

**Stack detection** - check for these files:
- `package.json` → Node.js. Read it: check for next, express, fastify, hono, koa, nuxt, svelte, remix
- `requirements.txt` / `pyproject.toml` / `Pipfile` → Python. Check for flask, django, fastapi, starlette
- `go.mod` → Go. Check for gin, echo, chi, fiber, net/http
- `Cargo.toml` → Rust
- `Gemfile` → Ruby / Rails
- `composer.json` → PHP / Laravel

**Database** - check deps and imports for: prisma, drizzle, knex, sequelize, typeorm, mongoose, sqlalchemy, gorm, diesel, ent

**BaaS** - check for: `@supabase/supabase-js`, `firebase`, `firebase-admin`, `convex`, `appwrite`. These have their own auth and access control rules that need separate checks

**Auth** - check deps for: next-auth, @auth/core, `@clerk/nextjs`, `@clerk/clerk-sdk-node`, `better-auth`, supabase, passport, lucia, jwt, bcrypt, argon2

**OAuth providers** - check for: passport-google, passport-github, @auth/google, next-auth providers, oauth2 client libraries

**AI/LLM** - check for: `openai`, `@anthropic-ai/sdk`, `ai` (Vercel AI SDK), `langchain`, `llamaindex`, `@google/generative-ai`, `cohere-ai`, `replicate`. Almost every SaaS has AI features now - these need their own security checks

**Payments** - check deps and code for: stripe, paddle, lemonsqueezy, paypal

**File uploads** - check for: multer, formidable, busboy, express-fileupload, python-multipart, uploadthing

**Infra** - check for: `Dockerfile`, `docker-compose.yml`, `vercel.json`, `netlify.toml`, `fly.toml`, `wrangler.toml`, `railway.json`, `.github/workflows/`

**MCP** - check for MCP config files in the project

Report a one-line summary of what you detected, then start scanning. Example:
> **Detected:** Next.js 14 + Prisma + PostgreSQL, Stripe payments, NextAuth, Docker, GitHub Actions

### Phase 2: Scan

Run these checks using Grep and Glob tools with the exact patterns below. Exclude `node_modules`, `.git`, `vendor`, `dist`, `build`, `.next`, `__pycache__`, `venv`, `.venv` from all searches.

---

#### CRITICAL: Secrets in code

Search for each pattern. Report file and line number for every match.

**IMPORTANT: Credential redaction rule.** When reporting secret findings, NEVER reproduce the full secret value in the output. Always redact: show only the first 4 characters followed by `****` (e.g., `sk-pr****`, `AKIA****`, `ghp_x****`). In Before/After code blocks for secret findings, use the redacted form. This prevents accidental exfiltration of credentials through the report itself.

**API keys:**

| Pattern | What |
|---------|------|
| `AKIA[0-9A-Z]{16}` | AWS access key |
| `sk_live_[a-zA-Z0-9]{24,}` | Stripe live key |
| `rk_live_[a-zA-Z0-9]{24,}` | Stripe restricted key |
| `sk-proj-[a-zA-Z0-9\-_]{20,}` | OpenAI project key |
| `sk-ant-[a-zA-Z0-9\-_]{80,}` | Anthropic key |
| `sk-[a-zA-Z0-9]{48,}` | OpenAI legacy key (long format) |
| `ghp_[a-zA-Z0-9]{36}` | GitHub PAT |
| `gho_[a-zA-Z0-9]{36}` | GitHub OAuth |
| `github_pat_[a-zA-Z0-9_]{80,}` | GitHub fine-grained PAT |
| `glpat-[a-zA-Z0-9\-_]{20,}` | GitLab PAT |
| `xoxb-[0-9]{10,}-[a-zA-Z0-9]+` | Slack bot token |
| `xoxp-[0-9]{10,}-[a-zA-Z0-9]+` | Slack user token |
| `SG\.[a-zA-Z0-9\-_]{22}\.[a-zA-Z0-9\-_]{22}` | SendGrid key |
| `sq0atp-[a-zA-Z0-9\-_]{22}` | Square access token |
| `AC[a-z0-9]{32}` | Twilio account SID (confirm: near `auth_token` or `twilio` import) |
| `key-[a-zA-Z0-9]{32}` | Mailgun key (confirm: near `mailgun` import or config) |

**Private keys:**

| Pattern | What |
|---------|------|
| `-----BEGIN (RSA\|EC\|DSA\|OPENSSH) PRIVATE KEY` | Private key in code |
| `-----BEGIN PGP PRIVATE KEY` | PGP private key |

**Connection strings with credentials:**

| Pattern | What |
|---------|------|
| `(postgres\|postgresql\|mysql\|mongodb\+srv\|mongodb):\/\/[^:\s]+:[^@\s]+@` | Database connection string with embedded password |
| `redis:\/\/:[^@\s]+@` | Redis with password |
| `amqps?:\/\/[^:\s]+:[^@\s]+@` | RabbitMQ with password |

**Hardcoded secrets in assignments:**

| Pattern | What |
|---------|------|
| `(password\|passwd\|secret\|api_key\|apiKey\|api_secret\|token\|auth_token)\s*[:=]\s*['"][A-Za-z0-9\-_./+]{12,}['"]` | Hardcoded secret value (12+ chars, not a placeholder) |

**Context rules - adjust severity based on location:**
- In `*.test.*`, `*.spec.*`, `__tests__/`, `test/`, `fixtures/`, `testdata/`, `mock/`: downgrade to INFO
- In `*.example`, `*.sample`, `*.template`, `README*`, `docs/`: downgrade to INFO
- If the value contains `xxx`, `your-`, `TODO`, `CHANGE`, `example`, `placeholder`, `dummy`, `test`, `fake`: downgrade to INFO
- In `.env` that IS in `.gitignore`: downgrade to INFO (correctly handled)
- In `.env` that is NOT in `.gitignore`: keep CRITICAL
- In committed source code with real-looking values: keep CRITICAL

**Then check .gitignore:**

Read `.gitignore`. Verify these entries exist:
```
.env
.env.local
.env.*.local
*.pem
*.key
```
If `.env` is missing from `.gitignore`: CRITICAL finding on its own.

**Then check git history for leaked secrets:**
```bash
git log --all --oneline -- '.env' '.env.local' '*.pem' '*.key' 2>/dev/null | head -10
```
If any results: secrets may be in git history even if currently gitignored. CRITICAL. Tell the user they need to rotate those credentials - removing a file from git does not remove it from history.

---

#### HIGH: Injection vulnerabilities

**SQL injection** - string interpolation in queries:

| Pattern | Language | Issue |
|---------|----------|-------|
| `query\(.*\$\{` | JS/TS | Template literal in SQL query |
| `query\(.*\+\s*(req\|params\|body\|query\|input\|args\|ctx)` | JS/TS | String concatenation with user input in SQL |
| `execute\(f["']` | Python | f-string in SQL execute |
| `execute\(["'].*%s.*%\s` | Python | Unsafe % formatting in SQL (tuple args are safe, flag only `% variable`) |
| `cursor\.execute\(.*\.format\(` | Python | str.format() in SQL |
| `\.Raw\(.*fmt\.Sprintf` | Go | Sprintf in raw SQL query |
| `\.Exec\(.*\+\s` | Go | String concat in Exec SQL call |
| `\.Query\(.*\+\s` | Go | String concat in Query SQL call |
| `\.Where\(.*fmt\.Sprintf` | Go (GORM) | Sprintf in GORM Where |

**XSS** - unescaped user content in HTML:

| Pattern | Framework | Issue |
|---------|-----------|-------|
| `dangerouslySetInnerHTML` | React | Direct HTML injection. Verify the source is sanitized (DOMPurify). If it renders user input: HIGH |
| `innerHTML\s*=` | Vanilla JS | DOM-based XSS |
| `\.html\(` | jQuery | HTML injection (verify source is user-controlled) |
| `v-html=` | Vue | Unescaped HTML binding |
| `\|safe` | Django/Jinja2 | Auto-escaping disabled |
| `\{\{\{.*\}\}\}` | Handlebars/Mustache | Unescaped output |
| `<%[-]?=` | EJS | Unescaped output (verify source is sanitized) |

**Command injection:**

| Pattern | Language | Issue |
|---------|----------|-------|
| `exec\(.*\$\{` | JS/TS | Template literal in shell exec |
| `exec\(.*\+` | JS/TS | String concat in shell exec |
| `child_process.*exec\(` | Node.js | Shell exec (`exec` runs via shell; use `execFile` or `spawn` instead) |
| `os\.system\(` | Python | os.system always runs via shell (use subprocess with shell=False) |
| `subprocess\.(call\|run\|Popen)\(.*shell=True` | Python | Shell=True enables injection |
| `exec\.Command\(.*\+` | Go | String concat in command args |

**Path traversal:**

| Pattern | Language | Issue |
|---------|----------|-------|
| `path\.join\(.*req\.(params\|query\|body)` | Node.js | User input in file path without validation |
| `os\.path\.join\(.*request\.(GET\|POST\|args\|form)` | Python | User input in file path |
| `filepath\.Join\(.*r\.(URL\|Form\|PathValue)` | Go | User input in file path |
| `sendFile\(.*req\.` | Express | Serving file based on user input |
| `send_file\(.*request\.` | Flask | Serving file based on user input |

**SSRF (Server-Side Request Forgery)** - AI generates code that fetches user-provided URLs without validation. Attacker can read internal services, cloud metadata (169.254.169.254), or scan your network:

| Pattern | Language | Issue |
|---------|----------|-------|
| `fetch\(.*req\.(params\|query\|body)` | JS/TS | User-controlled URL in fetch |
| `axios\(.*req\.(params\|query\|body)` | JS/TS | User-controlled URL in axios |
| `axios\.get\(.*req\.` | JS/TS | User-controlled URL in axios.get |
| `requests\.(get\|post)\(.*request\.(GET\|POST\|args\|form\|json)` | Python | User-controlled URL in requests |
| `urllib\.request\.urlopen\(.*request\.` | Python | User-controlled URL in urllib |
| `http\.Get\(.*r\.(URL\|Form\|PathValue)` | Go | User-controlled URL in http.Get |

If any found: verify the URL is validated against an allowlist of domains. Blocklisting `localhost`/`127.0.0.1` alone is insufficient (bypassed with DNS rebinding, IPv6, decimal IPs).

**Unsafe deserialization** - AI uses serialization functions that execute arbitrary code when fed malicious input:

| Pattern | Language | Issue |
|---------|----------|-------|
| `pickle\.load\(` | Python | Executes arbitrary code during deserialization. Never use on untrusted data |
| `yaml\.load\(` without `Loader=SafeLoader` | Python | Can execute arbitrary Python. Use `yaml.safe_load()` |
| `eval\(.*req\.(body\|query\|params)` | JS/TS | Executes arbitrary code from user input |
| `eval\(.*request\.(GET\|POST\|json\|form)` | Python | Executes arbitrary code from user input |
| `new Function\(.*req\.` | JS/TS | Dynamic code execution from user input |
| `unserialize\(` | PHP | Object injection via deserialization |

**Open redirect** - AI generates redirect code using user input. Attacker uses your domain for phishing (`yourapp.com/redirect?url=evil.com`):

| Pattern | Language | Issue |
|---------|----------|-------|
| `res\.redirect\(.*req\.(params\|query\|body)` | Express | User-controlled redirect URL |
| `redirect\(.*request\.(GET\|POST\|args)` | Python | User-controlled redirect URL |
| `http\.Redirect\(.*r\.(URL\|Form)` | Go | User-controlled redirect URL |
| `window\.location\s*=\s*` | JS (client) | Client-side redirect (verify source) |

---

#### HIGH: Authentication and session security

**Weak password hashing:**

| Pattern | Issue | Fix |
|---------|-------|-----|
| `createHash\(['"]md5['"]\)` | MD5 is crackable in seconds | Use bcrypt or argon2 |
| `md5\(.*password` | MD5 on password input | Use bcrypt or argon2 |
| `createHash\(['"]sha(1\|256\|512)['"]\)` | SHA is fast, not a password hash (verify: used near password/user context) | Use bcrypt or argon2 |
| `hashlib\.(md5\|sha1\|sha256)\(.*password` | Python: not a password hash | Use bcrypt or argon2 |
| `MessageDigest.*(MD5\|SHA)` | Java: not a password hash (verify: used near password context) | Use BCrypt |

Look for the CORRECT patterns too (bcrypt, argon2, scrypt, pbkdf2). If none found and the app has auth: HIGH.

**Insecure randomness** - AI uses `Math.random()` for things that need to be unpredictable:

| Pattern | Language | Issue |
|---------|----------|-------|
| `Math\.random\(\)` near token, session, id, key, secret, nonce | JS/TS | Predictable output. Use `crypto.randomUUID()` or `crypto.getRandomValues()` |
| `random\.(random\|randint\|choice)\(` near token, secret, password, key | Python | Predictable. Use `secrets.token_hex()` or `secrets.token_urlsafe()` |

**JWT issues:**

| Pattern | Issue |
|---------|-------|
| `jwt\.sign\(` | Search for all sign calls. If none include `expiresIn` or `exp` in payload: token never expires |
| `algorithm.*['"]none['"]` | Algorithm none attack - accepts unsigned tokens |
| `algorithms.*\[.*['"]none['"]` | Algorithm none in allowed list |
| `verify.*false` | Signature verification disabled (confirm: in JWT/auth context) |

If `jsonwebtoken` is in deps, also grep for `expiresIn`. If zero matches in the entire codebase: HIGH (tokens never expire).

**Cookie security:**

Search for cookie-setting code. Check for:
| Flag | Required | Risk if missing |
|------|----------|----------------|
| `httpOnly: true` | Yes | JavaScript can steal session cookies via XSS |
| `secure: true` | Yes in production | Cookies sent over HTTP in cleartext |
| `sameSite: 'strict'` or `'lax'` | Yes | CSRF attacks |

**Rate limiting:**

Check if any rate limiting exists on auth endpoints:
- Node.js: search for `express-rate-limit`, `rate-limit`, `@fastify/rate-limit` in `package.json`
- Python: search for `slowapi`, `django-ratelimit`, `flask-limiter` in deps
- Go: search for rate limit middleware in router setup

If no rate limiting AND auth endpoints exist: HIGH. A login endpoint without rate limiting can be brute-forced.

---

#### HIGH: Database access control

**Supabase without Row Level Security (RLS):**

If Supabase detected, check for RLS:
- Search for `supabase.from(` calls. If the app queries tables directly from the client, RLS must be enabled or any authenticated user can read/modify all rows
- Check if a `migrations/` or `supabase/` directory exists with SQL files. Search for `ALTER TABLE.*ENABLE ROW LEVEL SECURITY` and `CREATE POLICY`. If tables exist without RLS policies: CRITICAL
- Search for `service_role` key usage. The service role bypasses RLS - it must NEVER be exposed to the client/frontend

| Pattern | Issue |
|---------|-------|
| `service_role` | Supabase service role key (bypasses all RLS - must only be in server-side code, never in client bundle) |
| `SUPABASE_SERVICE_ROLE` | Service role in env (verify: only used server-side) |
| `supabase\.auth\.admin` | Admin auth API (verify: only in server-side code) |

**Firebase without security rules:**

If Firebase detected:
- Check for `firestore.rules` or `database.rules.json`. If missing: CRITICAL (defaults may allow public read/write)
- Search rules files for `allow read, write: if true` or `allow read, write: if request.auth != null` without further conditions (any authenticated user can access everything)

| Pattern | Issue |
|---------|-------|
| `allow read, write: if true` | Firebase rule allows public access - no auth required |
| `allow read, write: if request.auth != null` | Any logged-in user can read/write all documents (need per-document rules with `resource.data`) |

**Mass assignment** - AI passes raw request body to database create/update. User adds `isAdmin: true` or `role: admin` to the request:

| Pattern | Language | Issue |
|---------|----------|-------|
| `\.create\(req\.body` | JS/TS (ORM) | Raw request body in create - user controls all fields |
| `\.create\(\*\*request\.(json\|form\|data)` | Python (ORM) | Raw request data in create |
| `\.update\(req\.body` | JS/TS (ORM) | Raw request body in update |
| `Object\.assign\(.*req\.body` | JS/TS | Merging raw request into object |
| `\{\.\.\.req\.body\}` | JS/TS | Spreading raw request body |

---

#### CONDITIONAL: Next.js + Vercel (skip if not detected)

**`NEXT_PUBLIC_` env var exposure** - Variables prefixed with `NEXT_PUBLIC_` are bundled into the client JavaScript. AI frequently puts server-side secrets here:

| Pattern | Issue |
|---------|-------|
| `NEXT_PUBLIC_.*SECRET` | Secret exposed to browser |
| `NEXT_PUBLIC_.*KEY` that isn't a publishable key | Verify: Supabase `anon` key is OK, but `service_role` key is not |
| `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE` | Service role key shipped to every browser |
| `NEXT_PUBLIC_STRIPE_SECRET` | Stripe secret key in client bundle |
| `NEXT_PUBLIC_DATABASE` | Database credentials in client |
| `NEXT_PUBLIC_.*TOKEN` | Token exposed to browser (verify: is this a public token?) |

Check `.env*` files and `next.config.*` for any `NEXT_PUBLIC_` variable that holds a secret.

**Server Actions and API routes without auth:**

| Pattern | Issue |
|---------|-------|
| `"use server"` | Search all Server Action files. Verify each exported function checks auth before mutating data |
| `app/api/.*route\.(ts\|js)` | Check each API route for auth middleware. AI often creates API routes without `getServerSession` or equivalent |
| `export async function (GET\|POST\|PUT\|DELETE)` | Next.js route handler - verify auth check exists |

**Vercel deployment:**
- Check `vercel.json` for env vars in plaintext (should use Vercel dashboard, not config file)
- Check if preview deployments have access to production secrets (common misconfiguration)

---

#### CONDITIONAL: Clerk auth (skip if not detected)

| Pattern | Issue |
|---------|-------|
| `CLERK_SECRET_KEY` with `NEXT_PUBLIC_` prefix | Secret key exposed to client - CRITICAL |
| `clerkMiddleware\(\)` without `createRouteMatcher` | Middleware doesn't protect any routes by default. Must define protected routes |
| `auth\(\)` | Search Server Components and Actions. Verify `auth()` is called before data access/mutations |
| API routes without `auth()` or `getAuth()` | Unprotected API endpoint |

If Clerk is detected: verify `middleware.ts` exists and uses `createRouteMatcher` to protect routes. Default Clerk middleware without route matching protects nothing.

---

#### CONDITIONAL: AI/LLM integration (skip if no AI deps detected)

**API key exposure:**

| Pattern | Issue |
|---------|-------|
| `NEXT_PUBLIC_OPENAI` | OpenAI key in client bundle |
| `NEXT_PUBLIC_ANTHROPIC` | Anthropic key in client bundle |
| `openai.*api_key.*=.*['"]sk-` | Hardcoded OpenAI key |
| `new OpenAI\(\{` without `apiKey: process.env` | Possible hardcoded key in constructor |

**Prompt injection via user input** - AI passes user input directly to LLM without sanitization:

| Pattern | Issue |
|---------|-------|
| `messages.*role.*user.*content.*req\.(body\|query\|params)` | Raw user input in LLM message |
| `prompt.*\$\{.*req\.` | User input interpolated into prompt template |
| `prompt.*\+.*req\.` | User input concatenated into prompt |
| `generateText\(.*\$\{` | Vercel AI SDK with interpolated user input |

If AI features exist: check that user input is never directly interpolated into system prompts. User input should go in the `user` message role, not concatenated into system/instruction text.

**Missing rate limiting on AI endpoints:**
- AI endpoints are expensive. Search for rate limiting on routes that call LLM APIs
- If no rate limiting on `/api/ai`, `/api/chat`, `/api/generate`, or similar: HIGH (attacker can run up your API bill)

---

#### CONDITIONAL: MongoDB Atlas (skip if not detected)

| Pattern | Issue |
|---------|-------|
| `mongodb\+srv://` with password in connection string | Embedded credentials (use env var) |
| `0\.0\.0\.0/0` in any MongoDB config or comments | Network access open to the entire internet |
| `mongoose\.connect\(` without auth options | Verify auth is configured |
| No `mongoose\.set\('strictQuery'` | May return unexpected fields |

---

#### HIGH: Overly permissive configs

**CORS wildcard:**

| Pattern | Framework | Issue |
|---------|-----------|-------|
| `cors\(\)` | Express | Defaults to `origin: *` if called with no config object |
| `Access-Control-Allow-Origin.*\*` | Any | Wildcard CORS header |
| `CORS\(app\)` | Flask-CORS | Allows all origins if no `origins=` param |
| `AllowAllOrigins:\s*true` | Go gin-cors | Allows all origins |
| `allowedOrigins.*\*` | Spring | Allows all origins |
| `allowedOriginPatterns.*\*` | Spring | Allows all origin patterns |
| `CORS_ALLOW_ALL_ORIGINS\s*=\s*True` | Django | Allows all origins |

If CORS wildcard found, check if it's only in development config. If it's in production or the default config: HIGH.

**Dangerous network binding:**

| Pattern | Issue |
|---------|-------|
| `listen\(.*['"]0\.0\.0\.0['"]` | Binding to all interfaces (ok inside Docker, risky on bare metal) |
| `host.*['"]0\.0\.0\.0['"]` | Service exposed to network (verify: intentional in container?) |
| `bind.*['"]0\.0\.0\.0['"]` | Accessible from network |

**Debug mode in production:**

| Pattern | Framework | Issue |
|---------|-----------|-------|
| `DEBUG\s*=\s*True` | Django | Full stack traces exposed (skip if in `settings/dev.py` or `local_settings.py`) |
| `app\.debug\s*=\s*True` | Flask | Debug mode with interactive debugger |
| `NODE_ENV.*development` | Node.js | Flag only in Dockerfile or docker-compose (dev mode in container) |
| `enableDevTools.*true` | Various | Dev tools accessible in production |
| `devtool.*true` | Various | Source maps or debug tools enabled |

**Missing security headers:**

Check if security headers are set. Search for `helmet` (Node.js), `django-csp` / `django.middleware.security` (Django), `secure` (Go).

If no security header middleware found and the app serves HTTP responses: MEDIUM.

Key headers to verify:
| Header | Risk if missing |
|--------|----------------|
| `Strict-Transport-Security` | Browser allows HTTP connections (credentials sent in cleartext) |
| `X-Frame-Options` or `frame-ancestors` in CSP | Clickjacking - attacker embeds your app in an iframe |
| `X-Content-Type-Options: nosniff` | Browser MIME-sniffs responses (can execute uploaded files as scripts) |
| `Content-Security-Policy` | No XSS mitigation at browser level |

**Exposed internals** (manual checks, not pattern-based):

1. Check if the static file server config serves dotfiles (`.git` exposure = full source code leak)
2. Search error handlers for stack trace leaks: look for `err.stack`, `traceback.format_exc()`, `debug.PrintStack()` in response bodies
3. Check if `/api/` routes apply auth middleware. Search for route definitions without `auth`, `protect`, `requireAuth`, `isAuthenticated` middleware

---

#### MEDIUM: Dependencies

**Run audit** (only if the tool is available):
```bash
# Node.js (human-readable summary, not JSON)
npm audit --omit=dev 2>/dev/null

# Python
pip audit 2>/dev/null || pip-audit 2>/dev/null

# Go
govulncheck ./... 2>/dev/null
```

Report summary: X critical, Y high, Z moderate vulnerabilities.

**Version pinning:**

Check `package.json` dependencies (not devDependencies) for:
| Pattern | Issue |
|---------|-------|
| `"*"` | Completely unpinned - any version |
| `"latest"` | Unpinned - resolves at install time |
| `">="` | Open-ended range - no upper bound |

Note: `^` and `~` in npm are normal (semver ranges). Only flag `*`, `latest`, and `>=`.

For `requirements.txt`: lines without `==` are unpinned. Flag them.

---

#### MEDIUM: Logging and monitoring

Check if the app has any security-relevant logging:
- Search for login/auth event logging. If auth exists but zero log statements on failed logins: MEDIUM (can't detect brute force)
- Search for error monitoring: `sentry`, `bugsnag`, `datadog`, `newrelic`, `logtail` in deps. If none and the app is production-ready: MEDIUM
- If error handlers use `console.log` only (no structured logging, no external service): note as improvement

---

#### MEDIUM: Data exposure

| Pattern | Issue |
|---------|-------|
| `console\.log\(.*req\.body` | Logging full request body (may contain passwords) |
| `console\.log\(.*request\.body` | Logging full request body (Python/Express) |
| `console\.log\(.*password` | Explicitly logging passwords |
| `print\(.*password` | Explicitly logging passwords (Python) |
| `logger\.\w+\(.*password` | Logging passwords via logger |
| `SELECT\s+\*` | Over-fetching (skip matches in migrations, seeds, and test files) |
| `JSON\.stringify\(user\)` | May serialize password hash, internal fields to response |
| `res\.json\(user\)` | Full user object in API response (should select specific fields) |

---

#### CONDITIONAL: Third-party integrations (skip if no OAuth or external APIs detected)

**OAuth state parameter** - Without the `state` parameter, an attacker can trick a user into linking the attacker's account (CSRF on OAuth flow):

| Pattern | Issue |
|---------|-------|
| `passport\.authenticate\(` | Check if `state: true` or a custom state parameter is set. If not: HIGH |
| `authorization_url` | Python OAuth: check if `state` is generated and verified on callback |
| `signIn\(` | NextAuth/Auth.js: verify CSRF protection is not disabled |

For any OAuth flow: search for `state` near the authorization URL construction. If the word `state` does not appear near OAuth redirect logic: HIGH.

**Webhook verification** - Any incoming webhook (not just Stripe) must verify the sender's signature. Without it, anyone can POST fake events to your endpoint:

- Search for webhook route handlers (`/webhook`, `/api/webhook`, `/hook`)
- For each webhook endpoint, check if the handler verifies a signature header before processing
- Common verification patterns: `constructEvent`, `verify_signature`, `hmac`, `createHmac`, `webhook_secret`
- If a webhook endpoint processes data without ANY signature check: HIGH

**External API calls without timeout** - AI generates HTTP calls to external APIs without timeouts. A slow or dead API hangs your server.

Search for these call patterns, then check if a timeout is configured nearby:

| Call pattern | Language | Timeout to look for |
|-------------|----------|-------------------|
| `fetch\(` | JS/TS | `AbortSignal.timeout` or `signal:` in the options |
| `axios\(` | JS/TS | `timeout:` in the config object |
| `requests\.(get\|post)\(` | Python | `timeout=` parameter |
| `http\.Get\(` | Go | `context.WithTimeout` or `client.Timeout` |

If external API calls exist without any timeout: MEDIUM. One slow third-party API can take down your entire server.

---

#### CONDITIONAL: Payments (skip if no payment integration detected)

| Check | What to search for |
|-------|-------------------|
| Webhook signature verification | Search for `constructEvent`, `webhook_construct_event`, `Webhook.construct_event`. If Stripe is in deps but no webhook verification found: HIGH |
| Client-side amount | Search for amount/price in frontend POST requests to payment endpoints. Amount must be set server-side |
| Idempotency keys | Search for `idempotencyKey`, `Idempotency-Key` in payment creation. Missing = potential double charges |

---

#### CONDITIONAL: File uploads (skip if no upload handling detected)

| Check | What to look for | Issue |
|-------|-----------------|-------|
| File size limit | Search multer/formidable/busboy config for `limits`, `maxFileSize`, `fileSizeLimit`. If no limit set: HIGH | Attacker uploads 10GB file, fills your disk |
| File type validation | Search for `mimetype`, `fileFilter`, `content_type`, `allowed_extensions`. If no type check: HIGH | Attacker uploads executable, PHP shell, or HTML file (stored XSS) |
| Filename sanitization | Search for `path.basename`, `sanitize`, `originalname` used directly in `path.join`. If original filename used as-is in file path: HIGH | Path traversal via filename (`../../etc/passwd`) |
| Storage location | Check if uploads go to a publicly accessible directory (`public/`, `static/`, `uploads/` served by web server) without access control | Direct URL access to any uploaded file |

---

#### CONDITIONAL: Docker (skip if no Dockerfile)

| Check | Pattern | Issue |
|-------|---------|-------|
| Running as root | Dockerfile without `USER` instruction | Container runs as root |
| Secrets in build | `ARG.*SECRET\|PASSWORD\|KEY\|TOKEN` in Dockerfile | Secrets visible in image layers |
| Latest tag | `FROM.*:latest` | Unpinned base image |
| No .dockerignore | Missing `.dockerignore` file | `.env`, `.git`, `node_modules` may be copied into image |

---

### Phase 3: Report

Output this exact structure. Be specific - reference actual files and line numbers.

```
## Security Report

**Project:** [name from package.json/go.mod/pyproject.toml]
**Stack:** [detected stack]
**Scanned:** [N files across M directories]
**Date:** [today]

### Score: [letter]

[One sentence explaining the score]
```

**Scoring criteria (strict):**
- **A**: 0 critical, 0 high, ≤3 medium
- **B**: 0 critical, 1-2 high, any medium
- **C**: 0 critical, 3+ high
- **D**: 1-2 critical findings
- **F**: 3+ critical findings, or any active credential exposure in committed code

Then list findings grouped by severity. For EACH finding:

```
**[N]. [Title]** `[SEVERITY]`
📍 `file/path.js:42`
[One sentence: what it is and what an attacker can do with it]

Before:
‎```[lang]
[insecure code from their file - REDACT any secret values: show first 4 chars + ****]
‎```

After:
‎```[lang]
[secure replacement - use environment variable references, never actual secret values]
‎```
```

**Redaction reminder:** In Before/After blocks, never reproduce real API keys, passwords, tokens, or connection string credentials. Always redact secret values (e.g., `"sk-pr****"` or `process.env.API_KEY`). The goal is to show the code pattern, not expose the secret.

If the fix needs a package install, include the install command before the code fix.

After all findings, add:

```
### What's solid
- [2-3 specific things the codebase does well. Be genuine, not filler.]

### Top 3 actions
1. [Highest impact fix. One sentence + the command or code change.]
2. [Second priority.]
3. [Third priority.]
```

### Examples

**Example 1: "I built this SaaS with Cursor, is it secure?"**
1. Detect: Next.js 14 + Supabase + Stripe + Vercel
2. Scan all categories. Focus on: Supabase RLS, Stripe webhook verification, secrets in `.env`
3. Report: Score D - service_role key in client code, no RLS on 3 tables, Stripe webhook unverified
4. Top 3: move service_role to server, enable RLS, add webhook signature check

**Example 2: "Security review before launch"**
1. Detect stack, prioritize: secrets first, auth second, payments third
2. Scan production config vs dev config - verify debug is off, CORS is scoped, security headers exist
3. Report with quick wins section first for pre-launch fixes

**Example 3: Clean project**
1. Detect and scan all categories
2. Report: Score A - no findings. List what the codebase does well

### Common Issues

**Large codebases:** Prioritize by severity - secrets first (biggest immediate risk), then auth, then payments. Don't try to scan everything in one pass. Skip `node_modules`, `vendor`, build artifacts.

**Many false positives on hardcoded secrets:** Apply context rules strictly. Test files, example configs, and placeholder values are INFO, not CRITICAL. If unsure, include the finding but mark it as "verify manually".

**npm audit / pip audit not available:** Skip the dependency audit command. Report that the tool wasn't available and recommend the user run it manually.

**Project uses a framework not listed:** Apply the general patterns (secrets, injection, auth) even if framework-specific patterns don't match. The core checks work across any stack.

**Re-runs after fixes:** When the user runs the skill again after applying fixes, scan the CURRENT filesystem state (not git history). Specifically:
1. Read the actual files on disk, not cached or previous results. The user may have fixed issues without committing.
2. For each check, verify the fix is actually applied by reading the current file content.
3. Do NOT report the same finding if the code has been changed. If the vulnerable pattern is no longer present in the file, it's fixed.
4. DO report findings in OTHER files or endpoints that weren't covered in the previous run. Be explicit: "This is a new finding not reported in the previous run."
5. If the score improved, say so: "Score improved from D to B. 3 issues remain."

**Consistency across runs:** The goal is deterministic results. To achieve this:
1. Always scan ALL files matching the patterns, not a sample. Don't stop after finding N issues.
2. Report ALL findings, not just the first N. The user needs to know the full scope.
3. When reporting, group by file so the user can work through fixes file by file.
4. If the project is too large to scan completely in one pass, say so and recommend scanning by directory: `/security-review src/api/` then `/security-review src/components/`

### Phase 4: Fix mode

After presenting the report, ask the user:

"Want me to fix these issues? I can go through them one by one."

If the user says yes:

1. Work through findings from highest severity to lowest
2. For each finding, show what you're about to change and apply the fix
3. Skip findings that require external action (e.g., rotating leaked keys, enabling RLS in Supabase dashboard)
4. After all fixes are applied, re-run the checks on the modified files to confirm the issues are resolved
5. Report what was fixed and what still needs manual attention

If the user says no or doesn't respond, end with the report.

### Phase 5: Next steps

If the project uses MCP servers or AI agents, suggest the user look into auditing those configurations separately.
