# OWASP Top 10:2025 — Audit Check Reference

This document maps each OWASP Top 10:2025 category to concrete, searchable patterns
in web application code (React, Next.js, NestJS). Use this as a checklist during audit.

---

## A01:2025 — Broken Access Control

The #1 risk. Includes SSRF (merged from former standalone category). Focus on
authorization enforcement at every layer.

### What to check

**Server-side (NestJS / Next.js API routes)**:
- Controllers or route handlers missing auth guards (`@UseGuards()`, middleware checks)
- Endpoints accepting user-supplied IDs without ownership validation (IDOR):
  ```
  // BAD: uses param ID without checking ownership
  @Get(':id')
  findOne(@Param('id') id: string) { return this.service.findOne(id); }

  // GOOD: validates ownership
  @Get(':id')
  findOne(@Param('id') id: string, @Req() req) {
    return this.service.findOneForUser(id, req.user.id);
  }
  ```
- Role/permission checks missing or implemented only on frontend
- `@Public()` decorator on sensitive endpoints
- Missing `@Roles()` or equivalent on admin-only operations
- CORS set to `origin: '*'` or `origin: true` without restriction
- SSRF: user input used in HTTP requests (`axios.get(userInput)`, `fetch(userInput)`)
- Path traversal: user input in file paths (`fs.readFile(req.query.path)`)

**Client-side (React / Next.js)**:
- Route protection implemented only via UI hiding (no server enforcement)
- Admin panels accessible by URL without server-side gate
- Auth tokens stored in localStorage (accessible via XSS)
- Missing redirect-to-login for protected routes

### Search patterns
```bash
grep -rn "@Public()" src/ --include="*.ts"
grep -rn "origin.*\*\|origin.*true" src/ --include="*.ts"
grep -rn "req\.param\|req\.query\|req\.body" src/ --include="*.ts" | grep -v "validate\|guard\|auth"
grep -rn "fetch(\|axios\.\|http\.\|request(" src/ --include="*.ts" | grep -i "req\.\|param\.\|query\.\|body\."
grep -rn "readFile\|readFileSync\|createReadStream" src/ --include="*.ts"
grep -rn "localStorage" src/ --include="*.ts" --include="*.tsx" | grep -i "token\|auth\|session\|jwt"
```

---

## A02:2025 — Security Misconfiguration

Moved from #5 to #2. Covers default configs, missing hardening, exposed debug info.

### What to check

- Missing `helmet()` middleware in NestJS `main.ts`
- Debug mode enabled in production (`NODE_ENV !== 'production'` not checked)
- Default credentials or example secrets in config files
- `.env` files committed to git (check `.gitignore`)
- Exposed error details in responses (stack traces, internal paths)
- Missing security headers: `Strict-Transport-Security`, `X-Content-Type-Options`,
  `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`
- Next.js config: `poweredBy` header not disabled, missing security headers in `next.config.js`
- Docker: running as root, exposing unnecessary ports
- TypeScript `strict: false` or missing strict mode
- Unnecessary packages in production dependencies

### Search patterns
```bash
grep -rn "helmet" src/ --include="*.ts" -l
grep -rn "enableCors\|cors(" src/ --include="*.ts"
grep -rn "DEBUG\|debug.*true\|verbose.*true" src/ --include="*.ts" --include="*.env*"
find . -name ".env*" -not -path "*/node_modules/*" | xargs ls -la
grep -rn "\.env" .gitignore
grep -rn "stack\|stackTrace\|err\.message" src/ --include="*.ts" | grep -i "res\.\|response\.\|send\|json"
grep -rn "poweredBy\|x-powered-by" next.config* --include="*.js" --include="*.mjs" --include="*.ts"
cat tsconfig.json | grep -i "strict"
```

---

## A03:2025 — Software Supply Chain Failures

New expansion of "Vulnerable and Outdated Components." Covers dependencies, build
pipeline integrity, third-party risk.

### What to check

- Outdated dependencies with known CVEs (check `npm audit` output or lockfile dates)
- No lockfile committed (missing `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`)
- Use of `*` or overly broad version ranges in `package.json`
- Scripts in `package.json` that download or execute remote code
- No `npm audit` or equivalent in CI/CD pipeline
- Missing Subresource Integrity (SRI) for externally loaded scripts
- Postinstall scripts from dependencies that run arbitrary code
- Importing from CDNs without integrity checks in HTML

### Search patterns
```bash
cat package.json | grep -E '"\*"|">=|"latest"'
cat package.json | grep -i "postinstall\|preinstall\|prepare"
grep -rn "script.*src.*http" public/ --include="*.html" | grep -v "integrity"
ls package-lock.json yarn.lock pnpm-lock.yaml 2>/dev/null
grep -rn "cdn\|unpkg\|jsdelivr\|cdnjs" src/ --include="*.tsx" --include="*.html" --include="*.jsx"
```

---

## A04:2025 — Cryptographic Failures

Dropped from #2 to #4. Weak crypto, exposed secrets, insecure transport.

### What to check

- Hardcoded secrets, API keys, passwords, JWT secrets in source code
- Weak hashing algorithms (`md5`, `sha1` for passwords)
- Missing encryption for sensitive data at rest
- JWT with `algorithm: 'none'` or weak signing
- HTTP used instead of HTTPS for API calls or redirects
- Sensitive data in URL parameters (tokens, passwords)
- Missing `secure` and `httpOnly` flags on cookies
- Weak random number generation (`Math.random()` for security purposes)
- Private keys or certificates committed to repository

### Search patterns
```bash
grep -rn "password\|secret\|apikey\|api_key\|token\|private_key" src/ --include="*.ts" --include="*.tsx" | grep -v "\.d\.ts\|node_modules\|test\|spec\|mock"
grep -rn "md5\|sha1" src/ --include="*.ts" | grep -v "node_modules"
grep -rn "algorithm.*none" src/ --include="*.ts"
grep -rn "Math\.random" src/ --include="*.ts" --include="*.tsx" | grep -iv "test\|spec\|mock"
grep -rn "http://" src/ --include="*.ts" --include="*.tsx" | grep -v "localhost\|127\.0\.0\.1\|node_modules"
grep -rn "secure.*false\|httpOnly.*false" src/ --include="*.ts"
find . -name "*.pem" -o -name "*.key" -o -name "*.p12" -not -path "*/node_modules/*"
```

---

## A05:2025 — Injection

Dropped from #3 to #5. Covers SQL/NoSQL injection, XSS, command injection, LDAP, template injection.

### What to check

**SQL/NoSQL Injection**:
- Raw SQL queries with string concatenation or template literals containing user input
- TypeORM `createQueryBuilder` with `.where("column = '" + input + "'")`
- Mongoose queries with `$where` or unsanitized `$regex`
- Missing parameterized queries

**XSS**:
- `dangerouslySetInnerHTML` with unsanitized content
- `innerHTML` assignments
- Template literal injection in HTML contexts
- Missing output encoding

**Command Injection**:
- `exec()`, `spawn()`, `execSync()` with user-supplied arguments
- `eval()`, `Function()`, `setTimeout(string)`, `setInterval(string)`

**Other Injection**:
- LDAP injection in directory queries
- Template injection (Handlebars, EJS with user input)
- Header injection (user input in response headers)
- Log injection (unsanitized user input in logs)

### Search patterns
```bash
grep -rn "dangerouslySetInnerHTML" src/ --include="*.tsx" --include="*.jsx"
grep -rn "innerHTML" src/ --include="*.ts" --include="*.tsx"
grep -rn "eval(\|new Function(" src/ --include="*.ts" --include="*.tsx"
grep -rn "exec(\|execSync(\|spawn(\|spawnSync(" src/ --include="*.ts" | grep -v "node_modules"
grep -rn "createQueryBuilder" src/ --include="*.ts" | grep -v "node_modules"
grep -rn "\$where\|\$regex" src/ --include="*.ts"
grep -rn "query.*\+.*req\.\|query.*\${.*req\." src/ --include="*.ts"
grep -rn "setHeader\|writeHead" src/ --include="*.ts" | grep "req\.\|param\.\|query\."
```

---

## A06:2025 — Insecure Design

Moved from #4 to #6. Architecture and design-level flaws, not implementation bugs.

### What to check

- Missing threat model (no evidence of security design thinking)
- No rate limiting on critical flows (login, registration, password reset, OTP)
- Missing account lockout after failed login attempts
- No abuse prevention on public endpoints (signup, contact forms)
- Business logic flaws (e.g., negative quantities in cart, skipping payment steps)
- Missing CAPTCHA or bot protection on public forms
- Lack of defense-in-depth (single layer of security)
- No input validation strategy (DTOs without decorators in NestJS)
- Missing global validation pipe in NestJS

### Search patterns
```bash
grep -rn "throttle\|rateLimit\|rate-limit\|ThrottlerGuard" src/ --include="*.ts" -l
grep -rn "ValidationPipe\|class-validator" src/ --include="*.ts" -l
grep -rn "@IsEmail\|@IsString\|@IsNumber\|@MinLength\|@MaxLength" src/ --include="*.ts" -l
grep -rn "captcha\|recaptcha\|turnstile\|hcaptcha" src/ --include="*.ts" --include="*.tsx" -l
grep -rn "lockout\|maxAttempts\|failedAttempts\|loginAttempts" src/ --include="*.ts" -l
```

---

## A07:2025 — Authentication Failures

Holds at #7. Renamed from "Identification and Authentication Failures."

### What to check

- Weak password requirements (no minimum length, no complexity rules)
- Missing multi-factor authentication (MFA) on sensitive operations
- Session tokens not rotated after login
- Missing session timeout / idle timeout
- JWT stored in localStorage instead of httpOnly cookies
- Refresh token reuse not prevented
- Password reset tokens that don't expire or are predictable
- No brute-force protection on login endpoints
- Missing `bcrypt` or `argon2` for password hashing (using SHA/MD5 instead)
- Default or weak JWT secret (e.g., `secret`, `123456`, `jwt_secret`)

### Search patterns
```bash
grep -rn "bcrypt\|argon2\|scrypt" src/ --include="*.ts" -l
grep -rn "sign(\|verify(" src/ --include="*.ts" | grep -i "jwt\|jsonwebtoken"
grep -rn "expiresIn\|maxAge\|ttl" src/ --include="*.ts" | grep -i "jwt\|session\|token\|cookie"
grep -rn "secret.*=.*['\"]" src/ --include="*.ts" | grep -v "node_modules\|\.d\.ts"
grep -rn "password.*length\|minLength\|MinLength" src/ --include="*.ts"
grep -rn "refreshToken\|refresh_token" src/ --include="*.ts"
```

---

## A08:2025 — Software or Data Integrity Failures

Covers CI/CD pipeline security, insecure deserialization, unsigned updates.

### What to check

- CI/CD pipelines without integrity checks on artifacts
- Deserialization of untrusted data (`JSON.parse` on unvalidated external input is lower risk;
  `deserialize`, `pickle`, `unserialize` on user input is high risk)
- Missing integrity checks on auto-updated dependencies
- GitHub Actions using `pull_request_target` with checkout of PR code
- Workflow files allowing arbitrary code execution from external contributors
- Missing code review requirements on protected branches

### Search patterns
```bash
grep -rn "deserialize\|unserialize\|fromJSON\|parse(" src/ --include="*.ts" | grep -i "body\|req\.\|input\|external"
find .github/workflows -name "*.yml" -o -name "*.yaml" 2>/dev/null | xargs grep -l "pull_request_target" 2>/dev/null
find .github/workflows -name "*.yml" -o -name "*.yaml" 2>/dev/null | xargs grep -l "run:.*\$\{" 2>/dev/null
```

---

## A09:2025 — Logging & Alerting Failures

Renamed from "Security Logging and Monitoring Failures." Expanded scope.

### What to check

- No structured logging framework (just `console.log`)
- Authentication events not logged (login success/failure, password changes)
- Authorization failures not logged
- Sensitive data in logs (passwords, tokens, PII, credit cards)
- No log level management (everything at the same level)
- Missing audit trail for critical operations (payments, data changes, admin actions)
- No error alerting integration
- Log injection vulnerability (user input written to logs unsanitized)

### Search patterns
```bash
grep -rn "console\.log\|console\.error\|console\.warn" src/ --include="*.ts" --include="*.tsx" | wc -l
grep -rn "Logger\|winston\|pino\|bunyan\|morgan" src/ --include="*.ts" -l
grep -rn "password\|token\|secret\|authorization" src/ --include="*.ts" | grep -i "log\.\|logger\.\|console\."
grep -rn "audit\|auditLog\|audit_log" src/ --include="*.ts" -l
```

---

## A10:2025 — Mishandling of Exceptional Conditions

New category in 2025. Poor error/exception handling that leads to security failures.

### What to check

- Empty catch blocks that swallow errors silently
- Catch blocks that expose internal details in responses
- Missing global exception filter in NestJS
- Missing error boundary in React
- Fail-open logic (granting access when an auth check throws an error)
- Unhandled promise rejections
- Missing try-catch around critical operations (DB queries, external API calls, file I/O)
- NULL/undefined dereference without checks
- Resource exhaustion from uncapped loops, missing pagination, unbounded queries
- Missing timeout on external HTTP calls

### Search patterns
```bash
grep -rn "catch.*{}" src/ --include="*.ts" --include="*.tsx"
grep -rn "catch\s*(\s*\w*\s*)\s*{\s*}" src/ --include="*.ts" --include="*.tsx"
grep -rn "AllExceptionsFilter\|ExceptionFilter\|APP_FILTER" src/ --include="*.ts" -l
grep -rn "ErrorBoundary\|errorBoundary\|error\.tsx\|error\.jsx" src/ --include="*.tsx" --include="*.jsx" --include="*.ts" -l
grep -rn "unhandledRejection\|uncaughtException" src/ --include="*.ts" -l
grep -rn "timeout\|AbortController\|signal" src/ --include="*.ts" | grep -i "fetch\|axios\|http"
grep -rn "\.findAll()\|\.find({})\|SELECT \*" src/ --include="*.ts" | grep -v "limit\|take\|paginate\|skip"
```
