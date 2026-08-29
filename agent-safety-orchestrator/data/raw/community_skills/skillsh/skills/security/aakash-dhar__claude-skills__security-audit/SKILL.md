---
name: security-audit
description: Scans code for security vulnerabilities including injection attacks, authentication flaws, exposed secrets, insecure dependencies, and data exposure. Use when the user says "security review", "is this secure?", "check for vulnerabilities", "audit this", or before deploying to production.
allowed-tools: Read, Grep, Glob, Bash
---

# Security Audit Skill

When auditing code for security, follow this structured process. Treat every finding seriously — a single vulnerability can compromise an entire system.

## 1. Secrets & Credentials

Scan the entire codebase for exposed secrets:

- **Hardcoded API keys, tokens, passwords** in source code
- **Secrets in config files** committed to Git (.env, config.json, settings.py)
- **Secrets in logs** — sensitive data printed in console.log, logger.info, etc.
- **Secrets in error messages** — stack traces or error responses leaking internals
- **Secrets in comments** — old credentials left in TODO or commented-out code
- **Secrets in Git history** — check if secrets were committed and later removed (still in history)

Check commands:
```bash
# Search for common secret patterns
grep -rn "password\|secret\|api_key\|apikey\|token\|private_key\|AWS_SECRET\|DATABASE_URL" --include="*.ts" --include="*.js" --include="*.py" --include="*.env" --include="*.json" --include="*.yaml" --include="*.yml" .

# Check for .env files committed
git ls-files | grep -i "\.env"

# Check git history for secrets
git log --all --diff-filter=D -- "*.env" "*.pem" "*.key"
```

Verify:
- Is a `.gitignore` in place with `.env`, `*.pem`, `*.key`, `*.p12`?
- Are secrets loaded from environment variables or a vault (not files)?
- Is there a `.env.example` with placeholder values (not real secrets)?

## 2. Injection Attacks

### SQL Injection
```
// 🔴 VULNERABLE — string concatenation in query
const user = await db.query(`SELECT * FROM users WHERE id = '${req.params.id}'`);

// ✅ SAFE — parameterized query
const user = await db.query('SELECT * FROM users WHERE id = $1', [req.params.id]);
```

### NoSQL Injection
```
// 🔴 VULNERABLE — user input directly in query object
const user = await User.find({ username: req.body.username });

// ✅ SAFE — explicitly cast to string
const user = await User.find({ username: String(req.body.username) });
```

### Command Injection
```
// 🔴 VULNERABLE — user input in shell command
exec(`convert ${req.body.filename} output.png`);

// ✅ SAFE — use execFile with arguments array
execFile('convert', [sanitizedFilename, 'output.png']);
```

### XSS (Cross-Site Scripting)
```
// 🔴 VULNERABLE — unsanitized HTML rendering
element.innerHTML = userInput;
// React: dangerouslySetInnerHTML={{ __html: userInput }}

// ✅ SAFE — use textContent or sanitize
element.textContent = userInput;
// React: use DOMPurify.sanitize() before dangerouslySetInnerHTML
```

### Path Traversal
```
// 🔴 VULNERABLE — user controls file path
const file = fs.readFileSync(`./uploads/${req.params.filename}`);

// ✅ SAFE — resolve and validate path stays within allowed directory
const safePath = path.resolve('./uploads', req.params.filename);
if (!safePath.startsWith(path.resolve('./uploads'))) throw new Error('Invalid path');
```

### Template Injection
- Check for user input passed directly into template engines (Jinja2, EJS, Handlebars)
- Verify auto-escaping is enabled

## 3. Authentication & Authorization

### Authentication Flaws
- **Weak password requirements** — no minimum length, complexity, or breach checking
- **Missing rate limiting** on login endpoints (brute force risk)
- **Missing account lockout** after failed attempts
- **Insecure password storage** — plaintext, MD5, SHA1 (use bcrypt/argon2 with proper cost)
- **Missing MFA** on sensitive operations
- **Session tokens in URLs** — tokens should be in headers or httpOnly cookies
- **No session expiration** — tokens that never expire

### Authorization Flaws
- **Missing authorization checks** — endpoints accessible without verifying user permissions
- **IDOR (Insecure Direct Object Reference)** — accessing other users' data by changing an ID
- **Privilege escalation** — regular user can access admin endpoints
- **Missing resource ownership checks** — user A can modify user B's data
```
// 🔴 VULNERABLE — IDOR: no ownership check
app.get('/api/orders/:id', async (req, res) => {
  const order = await Order.findById(req.params.id);
  res.json(order);
});

// ✅ SAFE — verify ownership
app.get('/api/orders/:id', async (req, res) => {
  const order = await Order.findById(req.params.id);
  if (order.userId !== req.user.id) return res.status(403).json({ error: 'Forbidden' });
  res.json(order);
});
```

## 4. Data Exposure

- **Sensitive data in API responses** — returning passwords, tokens, SSNs, full credit card numbers
- **Verbose error messages** in production — stack traces, database details, internal paths
- **Missing field filtering** — returning entire database objects instead of specific fields
- **Sensitive data in client-side storage** — tokens in localStorage (use httpOnly cookies)
- **PII in logs** — names, emails, IPs logged without redaction
- **Missing data encryption** — sensitive data stored unencrypted at rest
- **CORS misconfiguration** — `Access-Control-Allow-Origin: *` on authenticated endpoints
```
// 🔴 VULNERABLE — leaking sensitive fields
res.json(user);

// ✅ SAFE — explicit field selection
res.json({
  id: user.id,
  name: user.name,
  email: user.email,
});
```

## 5. Input Validation

- **Missing validation** — no checks on request body, params, query strings
- **Type confusion** — expecting a number but accepting a string
- **Missing length limits** — unbounded input that could cause DoS
- **Missing file upload validation** — no checks on file type, size, or content
- **Regex DoS (ReDoS)** — catastrophic backtracking on malicious input
- **Missing content-type validation** — accepting unexpected content types

Verify:
- Is there a validation library in use (Zod, Joi, class-validator, Pydantic)?
- Are all API endpoints validating input before processing?
- Are file uploads restricted by type, size, and scanned for malware?

## 6. Dependencies

Run these checks:
```bash
# Node.js
npm audit
# or
npx better-npm-audit audit

# Python
pip audit
# or
safety check

# Check for outdated packages
npm outdated
pip list --outdated
```

Look for:
- **Known CVEs** in dependencies
- **Outdated packages** with known vulnerabilities
- **Abandoned packages** — no updates in 2+ years
- **Typosquatting risk** — verify package names are correct
- **Excessive permissions** — packages requesting more access than needed
- **Lockfile present** — package-lock.json or yarn.lock committed

## 7. HTTP Security Headers

Check if these headers are set:
- `Content-Security-Policy` — prevents XSS and data injection
- `Strict-Transport-Security` — enforces HTTPS
- `X-Content-Type-Options: nosniff` — prevents MIME type sniffing
- `X-Frame-Options: DENY` — prevents clickjacking
- `Referrer-Policy` — controls referrer information
- `Permissions-Policy` — restricts browser features
```bash
# Check response headers
curl -I https://your-app.com
```

## 8. Cryptography

- **Weak hashing** — MD5 or SHA1 for passwords (use bcrypt, scrypt, or argon2)
- **Weak encryption** — DES, RC4, ECB mode (use AES-256-GCM)
- **Hardcoded encryption keys** — keys should be in environment variables or a vault
- **Missing TLS** — HTTP connections for sensitive data
- **Weak JWT** — using `alg: none` or HS256 with a short secret
- **Predictable random values** — using Math.random() for tokens (use crypto.randomBytes)
```
// 🔴 VULNERABLE — predictable token
const token = Math.random().toString(36);

// ✅ SAFE — cryptographically secure
const token = crypto.randomBytes(32).toString('hex');
```

## 9. Infrastructure & Configuration

- **Debug mode in production** — verbose errors, stack traces, debug endpoints
- **Default credentials** — admin/admin, root/root still active
- **Unnecessary ports open** — database ports exposed to the internet
- **Missing rate limiting** — no protection against DoS
- **Missing request size limits** — large payloads causing OOM
- **Insecure CORS** — wildcard origins on authenticated endpoints
- **Missing CSRF protection** — state-changing endpoints without CSRF tokens

## 10. Stack-Specific Checks

### Node.js / Express
- Verify helmet middleware is installed and configured
- Check express.json() has a size limit: `express.json({ limit: '10kb' })`
- Verify cookie settings: httpOnly, secure, sameSite
- Check for prototype pollution in object merging (lodash.merge, Object.assign with user input)
- Verify child_process calls sanitize all inputs
- Check that express-rate-limit is applied to auth endpoints
- Look for event emitter memory leaks (missing removeListener)
- Verify no use of `eval()`, `Function()`, or `vm.runInNewContext()` with user input

### Python / Django
- Verify `DEBUG = False` in production settings
- Check `ALLOWED_HOSTS` is not `['*']`
- Verify CSRF middleware is enabled
- Check for raw SQL queries without parameterization
- Verify `SECRET_KEY` is loaded from environment, not hardcoded
- Check for pickle deserialization of user input (RCE risk)
- Verify django-cors-headers is configured with specific origins
- Check that `@login_required` or permission classes are on all protected views
- Look for unsafe YAML loading (`yaml.load()` without `Loader=SafeLoader`)
- Verify `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` are True in production

### Python / Flask
- Verify `app.secret_key` is not hardcoded
- Check for missing `@login_required` decorators on protected routes
- Verify Jinja2 auto-escaping is enabled (default in Flask, but check custom templates)
- Check that `flask-talisman` or similar is used for security headers
- Verify `flask-limiter` is applied to auth and sensitive endpoints
- Check for unsafe file uploads (missing `secure_filename()` from werkzeug)

### React / Next.js
- Check for `dangerouslySetInnerHTML` with unsanitized input
- Verify no tokens stored in localStorage (use httpOnly cookies)
- Check for sensitive data in client-side code or bundle
- Verify environment variables use `NEXT_PUBLIC_` prefix only for non-sensitive values
- Check for open redirects in URL parameters
- Verify API routes have proper authentication middleware
- Check that Server Actions validate input and check authorization
- Look for sensitive data in `getServerSideProps` that leaks to `pageProps`
- Verify `next.config.js` has proper security headers configured
- Check for exposed source maps in production

### Vue / Nuxt
- Check for `v-html` with unsanitized user input
- Verify no tokens stored in localStorage
- Check `nuxt.config` for exposed runtime config secrets
- Verify server middleware has authentication checks
- Check for sensitive data leaking from server to client via `useAsyncData` or `useFetch`

### Ruby on Rails
- Verify `config.force_ssl = true` in production
- Check for `html_safe` or `raw` on user-supplied content
- Verify `protect_from_forgery` is enabled
- Check for mass assignment vulnerabilities (missing `strong_parameters`)
- Verify `has_secure_password` uses bcrypt
- Check for unsafe `send()` or `constantize()` with user input
- Verify `config.filter_parameters` includes sensitive fields

### Go
- Check for SQL injection in `fmt.Sprintf` used in queries (use parameterized queries)
- Verify TLS configuration uses minimum TLS 1.2
- Check for path traversal in `http.ServeFile` or `os.Open`
- Verify proper error handling (no sensitive data in error responses)
- Check for race conditions on shared state (missing mutex)
- Verify `crypto/rand` is used instead of `math/rand` for security-sensitive values
- Check for unchecked type assertions that could cause panics

### Java / Spring Boot
- Verify Spring Security is configured and not using `permitAll()` on sensitive endpoints
- Check for SQL injection in `@Query` annotations with string concatenation
- Verify CSRF protection is enabled (default in Spring Security)
- Check for deserialization vulnerabilities (Jackson, Java serialization)
- Verify `@Valid` annotation is present on request body parameters
- Check for hardcoded credentials in `application.properties` or `application.yml`
- Verify actuator endpoints are secured and not exposed publicly
- Check for Log4j/Log4Shell vulnerability in dependencies

### PHP / Laravel
- Verify `APP_DEBUG=false` in production `.env`
- Check for raw SQL queries without parameter binding
- Verify CSRF middleware is applied to all POST/PUT/DELETE routes
- Check for `eval()`, `exec()`, `system()` with user input
- Verify file uploads use validation rules (mimes, max size)
- Check that `Auth::check()` or middleware guards protect sensitive routes
- Verify `mass assignment` protection via `$fillable` or `$guarded`
- Check for unsafe blade rendering with `{!! !!}` on user input

### Mobile (React Native / Flutter)
- Check for sensitive data stored in AsyncStorage/SharedPreferences (use encrypted storage)
- Verify API keys are not embedded in the app bundle
- Check for certificate pinning on sensitive API calls
- Verify deep link handlers validate input before navigation
- Check for sensitive data in app logs (visible via adb logcat / Console.app)
- Verify biometric authentication properly validates server-side
- Check for insecure WebView configurations (JavaScript enabled with untrusted content)

### Payment Security
- Verify PCI DSS compliance requirements are met
- Check that full credit card numbers are never stored or logged
- Verify payment processing uses tokenization
- Check that webhook endpoints validate signatures
- Verify refund endpoints have proper authorization and rate limiting
- Check that payment amounts are validated server-side (not trusted from client)
- Verify payment confirmation pages don't expose transaction details in URLs
- Check for race conditions in payment processing (double-charge risk)

### AWS / Cloud Infrastructure
- Check for overly permissive IAM policies (`"Action": "*"`, `"Resource": "*"`)
- Verify S3 buckets are not publicly accessible
- Check for unencrypted RDS instances or EBS volumes
- Verify security groups don't allow 0.0.0.0/0 on sensitive ports
- Check for hardcoded AWS credentials (use IAM roles instead)
- Verify CloudTrail logging is enabled
- Check for publicly accessible EC2 instances with sensitive services
- Verify secrets are stored in AWS Secrets Manager or Parameter Store

### Docker / Containers
- Check for containers running as root
- Verify base images are from trusted sources and pinned to specific versions
- Check for secrets baked into Docker images (use build secrets or runtime env)
- Verify `.dockerignore` excludes `.env`, `.git`, `node_modules`
- Check for unnecessary packages installed in production images
- Verify health checks are configured
- Check for exposed ports that shouldn't be public

## Output Format

For each vulnerability found:

**[SEVERITY] Category — File:Line**
- **Vulnerability**: What the issue is
- **Risk**: What an attacker could do with this
- **Proof**: How to exploit it (for internal team understanding)
- **Fix**: Exact code change to resolve it
- **Reference**: CWE or OWASP link if applicable
```
// vulnerable code
...

// fixed code
...
```

Severity levels:
- 🔴 **CRITICAL** — Actively exploitable. Data breach, RCE, or full system compromise. Fix immediately.
- 🟠 **HIGH** — Exploitable with some effort. Significant data exposure or privilege escalation. Fix before next deploy.
- 🟡 **MEDIUM** — Requires specific conditions to exploit. Fix within current sprint.
- 🟢 **LOW** — Minor issue or defense-in-depth improvement. Fix when convenient.

## Summary

End every audit with:
1. **Risk rating** — Overall security posture (Critical / High / Medium / Low risk)
2. **Critical findings count** — Number of issues that need immediate attention
3. **Top 3 most dangerous issues** — Ranked by exploitability and impact
4. **Quick wins** — Fixes that take <30 minutes and significantly reduce risk
5. **Recommendations** — Longer-term improvements (WAF, security headers, dependency scanning in CI, etc.)
6. **What's done well** — Security practices already in place that should be maintained
