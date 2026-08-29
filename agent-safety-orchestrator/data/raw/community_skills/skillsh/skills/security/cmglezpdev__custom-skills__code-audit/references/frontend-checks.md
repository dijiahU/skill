# Frontend Audit Checks — React & Next.js

Patterns and anti-patterns specific to React and Next.js applications.
These supplement the OWASP checks with framework-specific concerns.

---

## Table of Contents

1. [Next.js Specific](#nextjs-specific)
2. [React General](#react-general)
3. [Client-Side Security](#client-side-security)
4. [Data Fetching & API Layer](#data-fetching--api-layer)
5. [Authentication & Session](#authentication--session)
6. [Build & Deploy](#build--deploy)

---

## Next.js Specific

### Server Actions (App Router)

- Server Actions must validate input independently. Never trust that the client form validated.
- Check for missing `"use server"` directive (function runs on client instead of server).
- Server Actions that mutate data should check auth and ownership:
  ```typescript
  // BAD: no auth check in server action
  async function deletePost(id: string) {
    "use server";
    await db.post.delete({ where: { id } });
  }

  // GOOD: validates session and ownership
  async function deletePost(id: string) {
    "use server";
    const session = await getServerSession();
    if (!session) throw new Error("Unauthorized");
    const post = await db.post.findUnique({ where: { id } });
    if (post.authorId !== session.user.id) throw new Error("Forbidden");
    await db.post.delete({ where: { id } });
  }
  ```

### Middleware (`middleware.ts`)

- Check that auth middleware covers all protected routes (not just a subset).
- Verify matcher config does not accidentally exclude API routes.
- Missing middleware entirely is a HIGH finding if the app has protected routes.

### Route Handlers (App Router API routes)

- Each route handler (`app/api/**/route.ts`) must independently verify auth.
- Check for missing HTTP method handlers (exported `GET` but no `POST` means POST returns 405 automatically, which is fine, but exporting `POST` without auth is a problem).
- Response headers: check for missing `Cache-Control: no-store` on auth-sensitive responses.

### `next.config.js` / `next.config.mjs`

Security-relevant settings to check:
```javascript
// Check these exist:
headers: async () => [
  {
    source: '/(.*)',
    headers: [
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'Content-Security-Policy', value: '...' },
      { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
    ],
  },
],
poweredBy: false,           // Should be false
images: { domains: [...] }, // Should be restrictive, not '*'
```

### Server Components vs Client Components

- Sensitive logic in Client Components (`"use client"`) is visible in the browser bundle.
- API keys or secrets in Client Components are exposed.
- Check for secrets in files marked with `"use client"`.

### Search patterns
```bash
grep -rn '"use server"' app/ --include="*.ts" --include="*.tsx"
grep -rn '"use client"' app/ src/ --include="*.ts" --include="*.tsx" | xargs grep -l "API_KEY\|SECRET\|PRIVATE\|password"
cat middleware.ts middleware.js 2>/dev/null
grep -rn "matcher" middleware.ts middleware.js 2>/dev/null
find app/api -name "route.ts" -o -name "route.js" 2>/dev/null
```

---

## React General

### XSS Vectors

- `dangerouslySetInnerHTML`: every usage must be audited for sanitization
  ```typescript
  // BAD: direct user input
  <div dangerouslySetInnerHTML={{ __html: userComment }} />

  // ACCEPTABLE: sanitized with DOMPurify
  import DOMPurify from 'dompurify';
  <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userComment) }} />
  ```
- URL-based XSS via `href={userInput}` (allows `javascript:` protocol)
  ```typescript
  // BAD
  <a href={userProvidedUrl}>Link</a>

  // GOOD: validate protocol
  const safeUrl = url.startsWith('http://') || url.startsWith('https://') ? url : '#';
  ```
- Event handler injection via dynamic props
- Rendering user content inside `<script>` tags

### State Management Security

- Sensitive data (tokens, PII) stored in Redux/Zustand state persisted to localStorage
- State not cleared on logout
- Redux DevTools enabled in production (leaks state)
  ```bash
  grep -rn "devTools\|__REDUX_DEVTOOLS" src/ --include="*.ts" --include="*.tsx"
  ```

### Error Boundaries

- Missing `ErrorBoundary` in component tree (no graceful degradation)
- Error boundary that renders error details in production:
  ```typescript
  // BAD
  componentDidCatch(error) { this.setState({ errorMsg: error.stack }); }
  ```

### Search patterns
```bash
grep -rn "dangerouslySetInnerHTML" src/ --include="*.tsx" --include="*.jsx"
grep -rn 'href={' src/ --include="*.tsx" --include="*.jsx" | grep -v "node_modules"
grep -rn "DOMPurify\|sanitize\|xss" src/ --include="*.ts" --include="*.tsx" -l
grep -rn "ErrorBoundary\|componentDidCatch\|error\.tsx" src/ app/ --include="*.tsx" --include="*.ts" -l
grep -rn "persist\|PERSIST\|localStorage\|sessionStorage" src/ --include="*.ts" --include="*.tsx"
```

---

## Client-Side Security

### Open Redirects

- Redirects using user-supplied URLs without validation:
  ```typescript
  // BAD: open redirect
  const redirect = searchParams.get('redirect');
  router.push(redirect);

  // GOOD: allowlist
  const ALLOWED = ['/dashboard', '/profile', '/settings'];
  if (ALLOWED.includes(redirect)) router.push(redirect);
  ```

### Sensitive Data Exposure

- PII displayed without masking (full SSN, credit card numbers, etc.)
- API responses containing more data than the UI needs (over-fetching)
- Source maps enabled in production (`GENERATE_SOURCEMAP=true`, `productionBrowserSourceMaps: true`)

### Third-Party Script Risks

- External scripts loaded without SRI (`integrity` attribute)
- Inline scripts violating CSP
- Analytics or tracking scripts with broad data collection

### Search patterns
```bash
grep -rn "router\.push\|router\.replace\|redirect\|navigate" src/ --include="*.ts" --include="*.tsx" | grep -i "param\|query\|search\|url\|req"
grep -rn "GENERATE_SOURCEMAP\|productionBrowserSourceMaps\|devtool.*source-map" . --include="*.env*" --include="*.js" --include="*.mjs" --include="*.ts"
grep -rn '<script.*src=' public/ --include="*.html" | grep -v "integrity"
```

---

## Data Fetching & API Layer

- API base URL hardcoded to HTTP instead of HTTPS
- Missing error handling on fetch calls (no try-catch, no `.catch()`)
- Auth token attached to every request including third-party APIs
- Missing request timeout configuration
- Caching sensitive data in service workers or browser cache
- API keys in client-side code (environment variables prefixed with `NEXT_PUBLIC_` or `REACT_APP_`)

### Search patterns
```bash
grep -rn "NEXT_PUBLIC_\|REACT_APP_" src/ app/ --include="*.ts" --include="*.tsx" | grep -i "key\|secret\|token\|password"
grep -rn "http://" src/ --include="*.ts" --include="*.tsx" | grep -i "api\|fetch\|axios" | grep -v "localhost"
grep -rn "Authorization\|Bearer" src/ --include="*.ts" --include="*.tsx" | head -20
```

---

## Authentication & Session

- Auth state only checked client-side (no server validation)
- Token refresh logic race conditions
- Missing PKCE in OAuth flows
- Social login without email verification
- Session not invalidated server-side on logout

---

## Build & Deploy

- `NODE_ENV` not set to `production` in build
- Bundle analyzer not used (potential for accidentally bundling sensitive modules)
- Missing CSP in deployment config
- No security scanning in CI/CD pipeline
- Source maps deployed to production

### Search patterns
```bash
grep -rn "NODE_ENV" . --include="*.env*" --include="Dockerfile" --include="*.yml" --include="*.yaml"
grep -rn "source-map\|sourcemap\|sourceMap" . --include="*.config.*" --include="*.json" --include="*.env*"
```
