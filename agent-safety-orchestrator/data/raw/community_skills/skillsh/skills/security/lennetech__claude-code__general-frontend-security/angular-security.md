---
name: angular-security-reference
description: Angular-specific security best practices based on OWASP guidelines
---

# Angular Security Reference

Angular-specific security implementations based on OWASP Secure Coding Practices.

---

## 1. Built-in XSS Protection

### Angular's Automatic Sanitization

Angular automatically sanitizes values in templates:

```typescript
// Component
@Component({
  template: `
    <!-- ✅ SAFE: Automatically escaped -->
    <div>{{ userInput }}</div>

    <!-- ✅ SAFE: Attribute binding escaped -->
    <div [title]="userInput"></div>

    <!-- ⚠️ Angular sanitizes but logs warning -->
    <div [innerHTML]="userInput"></div>
  `
})
export class SafeComponent {
  userInput = '<script>alert("xss")</script>'
}
```

### DomSanitizer and Security Contexts

```typescript
import { DomSanitizer, SafeHtml, SafeUrl } from '@angular/platform-browser'

@Component({
  template: `
    <div [innerHTML]="trustedHtml"></div>
    <a [href]="trustedUrl">Link</a>
  `
})
export class SanitizerComponent {
  trustedHtml: SafeHtml
  trustedUrl: SafeUrl

  constructor(private sanitizer: DomSanitizer) {
    // ⚠️ ONLY use bypass when you KNOW the content is safe
    // For example: content from your own CMS, not user input!
    const htmlFromCms = '<strong>Trusted</strong>'
    this.trustedHtml = this.sanitizer.bypassSecurityTrustHtml(htmlFromCms)

    // Validate URLs before trusting
    const validatedUrl = this.validateUrl(userProvidedUrl)
    this.trustedUrl = this.sanitizer.bypassSecurityTrustUrl(validatedUrl)
  }

  private validateUrl(url: string): string {
    try {
      const parsed = new URL(url)
      if (!['http:', 'https:'].includes(parsed.protocol)) {
        return 'about:blank'  // Block javascript:, data:, etc.
      }
      return url
    } catch {
      return 'about:blank'
    }
  }
}
```

### bypassSecurityTrust* Risks

```typescript
// ❌ DANGEROUS: Never use with user input
@Component({
  template: `<div [innerHTML]="dangerousHtml"></div>`
})
export class DangerousComponent {
  constructor(private sanitizer: DomSanitizer) {
    // NEVER DO THIS with user input!
    const userInput = '<img src=x onerror=alert("xss")>'
    this.dangerousHtml = this.sanitizer.bypassSecurityTrustHtml(userInput)
  }
}

// ✅ SAFE: Only bypass for truly trusted content
@Component({
  template: `<div [innerHTML]="safeHtml"></div>`
})
export class SafeComponent {
  safeHtml: SafeHtml

  constructor(private sanitizer: DomSanitizer, private cmsService: CmsService) {
    // Content from internal CMS with admin-only editing
    this.cmsService.getTrustedContent().subscribe(content => {
      this.safeHtml = this.sanitizer.bypassSecurityTrustHtml(content)
    })
  }
}
```

---

## 2. HTTP Security

### HttpClient Interceptors

```typescript
// auth.interceptor.ts
@Injectable()
export class AuthInterceptor implements HttpInterceptor {
  constructor(private authService: AuthService) {}

  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    const token = this.authService.getAccessToken()

    if (token) {
      req = req.clone({
        setHeaders: {
          Authorization: `Bearer ${token}`
        }
      })
    }

    return next.handle(req).pipe(
      catchError((error: HttpErrorResponse) => {
        if (error.status === 401) {
          this.authService.logout()
          this.router.navigate(['/login'])
        }
        return throwError(() => error)
      })
    )
  }
}

// app.config.ts
export const appConfig: ApplicationConfig = {
  providers: [
    provideHttpClient(
      withInterceptors([authInterceptor])
    )
  ]
}
```

### XSRF/CSRF Protection (Built-in)

```typescript
// Angular's HttpClient automatically handles XSRF
// Configure cookie and header names if needed

// app.config.ts
import { provideHttpClient, withXsrfConfiguration } from '@angular/common/http'

export const appConfig: ApplicationConfig = {
  providers: [
    provideHttpClient(
      withXsrfConfiguration({
        cookieName: 'XSRF-TOKEN',  // Default
        headerName: 'X-XSRF-TOKEN'  // Default
      })
    )
  ]
}

// Server must set XSRF-TOKEN cookie
// Angular automatically sends X-XSRF-TOKEN header
```

### Secure HTTP Requests

```typescript
@Injectable({ providedIn: 'root' })
export class ApiService {
  private apiUrl = environment.apiUrl  // Always HTTPS in production

  constructor(private http: HttpClient) {}

  // Always use POST for sensitive data
  login(credentials: LoginDto): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/auth/login`, credentials, {
      withCredentials: true  // Include cookies
    })
  }

  // Never put sensitive data in URL
  // ❌ WRONG
  getUser(token: string): Observable<User> {
    return this.http.get(`${this.apiUrl}/user?token=${token}`)
  }

  // ✅ CORRECT
  getUser(): Observable<User> {
    // Token sent via Authorization header by interceptor
    return this.http.get<User>(`${this.apiUrl}/user`)
  }
}
```

---

## 3. Route Guards

### CanActivate for Authentication

```typescript
// auth.guard.ts
export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService)
  const router = inject(Router)

  if (authService.isAuthenticated()) {
    return true
  }

  // Store intended URL for redirect after login
  router.navigate(['/login'], {
    queryParams: { returnUrl: state.url }
  })
  return false
}

// routes.ts
export const routes: Routes = [
  { path: 'dashboard', component: DashboardComponent, canActivate: [authGuard] },
  { path: 'admin', component: AdminComponent, canActivate: [authGuard, adminGuard] }
]
```

### Role-based Access

```typescript
// role.guard.ts
export const roleGuard: CanActivateFn = (route) => {
  const authService = inject(AuthService)
  const router = inject(Router)

  const requiredRoles = route.data['roles'] as string[]
  const userRoles = authService.getCurrentUser()?.roles ?? []

  const hasRole = requiredRoles.some(role => userRoles.includes(role))

  if (!hasRole) {
    router.navigate(['/unauthorized'])
    return false
  }

  return true
}

// routes.ts
export const routes: Routes = [
  {
    path: 'admin',
    component: AdminComponent,
    canActivate: [authGuard, roleGuard],
    data: { roles: ['ADMIN'] }
  }
]
```

### CanLoad for Lazy Modules

```typescript
// Prevents unauthorized users from even downloading module code
export const canLoadAdmin: CanMatchFn = () => {
  const authService = inject(AuthService)
  return authService.hasRole('ADMIN')
}

// routes.ts
export const routes: Routes = [
  {
    path: 'admin',
    loadChildren: () => import('./admin/admin.routes'),
    canMatch: [canLoadAdmin]
  }
]
```

### Redirect Security

```typescript
// login.component.ts
@Component({ /* ... */ })
export class LoginComponent {
  private router = inject(Router)
  private route = inject(ActivatedRoute)

  onLoginSuccess(): void {
    const returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/dashboard'

    // ✅ VALIDATE redirect URL
    if (this.isValidRedirect(returnUrl)) {
      this.router.navigateByUrl(returnUrl)
    } else {
      this.router.navigate(['/dashboard'])
    }
  }

  private isValidRedirect(url: string): boolean {
    // Only allow internal URLs
    if (url.startsWith('/') && !url.startsWith('//')) {
      return true
    }

    try {
      const parsed = new URL(url, window.location.origin)
      return parsed.origin === window.location.origin
    } catch {
      return false
    }
  }
}
```

---

## 4. Content Security

### CSP Compatibility

```typescript
// For inline styles (Angular often uses them)
// Configure CSP to allow Angular's style handling

// In index.html or server configuration:
// Content-Security-Policy: style-src 'self' 'unsafe-inline';

// Better: Use nonces with Angular Universal/SSR
// Configure CSP header with nonce
```

### Strict Template Security

```typescript
// Enable strict template type checking in tsconfig.json
{
  "angularCompilerOptions": {
    "strictTemplates": true,
    "strictInjectionParameters": true,
    "strictInputAccessModifiers": true
  }
}
```

### AOT vs JIT Security

```typescript
// ALWAYS use AOT (Ahead-of-Time) compilation in production
// angular.json
{
  "projects": {
    "my-app": {
      "architect": {
        "build": {
          "configurations": {
            "production": {
              "aot": true,  // Default and required
              "buildOptimizer": true
            }
          }
        }
      }
    }
  }
}

// JIT allows dynamic template compilation - security risk!
// Never enable JIT in production
```

---

## 5. Form Security

### Reactive Forms Validation

```typescript
@Component({
  template: `
    <form [formGroup]="loginForm" (ngSubmit)="onSubmit()">
      <input formControlName="email" type="email" autocomplete="email">
      <input formControlName="password" type="password" autocomplete="current-password">
      <button type="submit" [disabled]="loginForm.invalid">Login</button>
    </form>
  `
})
export class LoginComponent {
  loginForm = new FormGroup({
    email: new FormControl('', [
      Validators.required,
      Validators.email,
      Validators.maxLength(254)
    ]),
    password: new FormControl('', [
      Validators.required,
      Validators.minLength(8),
      Validators.maxLength(128)
    ])
  })

  onSubmit(): void {
    if (this.loginForm.invalid) return

    // Form values are typed and validated
    const { email, password } = this.loginForm.value
    this.authService.login(email!, password!).subscribe()
  }
}
```

### File Upload Validation

```typescript
@Component({
  template: `
    <input type="file" (change)="onFileSelected($event)" accept=".pdf,.jpg,.png">
  `
})
export class FileUploadComponent {
  private readonly ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/png']
  private readonly MAX_SIZE = 5 * 1024 * 1024  // 5MB

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return

    // Validate type
    if (!this.ALLOWED_TYPES.includes(file.type)) {
      this.showError('Invalid file type')
      input.value = ''
      return
    }

    // Validate size
    if (file.size > this.MAX_SIZE) {
      this.showError('File too large (max 5MB)')
      input.value = ''
      return
    }

    this.uploadFile(file)
  }
}
```

---

## 6. Storage Security

### Token Storage Best Practices

```typescript
@Injectable({ providedIn: 'root' })
export class AuthService {
  // ❌ WRONG: localStorage vulnerable to XSS
  private saveTokenWrong(token: string): void {
    localStorage.setItem('token', token)
  }

  // ✅ BETTER: Memory storage (cleared on refresh)
  private accessToken: string | null = null

  setAccessToken(token: string): void {
    this.accessToken = token
  }

  getAccessToken(): string | null {
    return this.accessToken
  }

  // ✅ BEST: httpOnly cookies (handled by server)
  // Frontend never sees the token
  login(credentials: LoginDto): Observable<void> {
    return this.http.post<void>('/api/auth/login', credentials, {
      withCredentials: true  // Server sets httpOnly cookie
    })
  }
}
```

### Secure Session Management

```typescript
@Injectable({ providedIn: 'root' })
export class SessionService {
  private sessionTimeout: number | null = null
  private readonly SESSION_DURATION = 15 * 60 * 1000  // 15 minutes

  startSession(): void {
    this.resetTimeout()
    this.setupActivityListeners()
  }

  private resetTimeout(): void {
    if (this.sessionTimeout) {
      clearTimeout(this.sessionTimeout)
    }

    this.sessionTimeout = window.setTimeout(() => {
      this.logout()
    }, this.SESSION_DURATION)
  }

  private setupActivityListeners(): void {
    const events = ['mousedown', 'keydown', 'touchstart', 'scroll']
    events.forEach(event => {
      document.addEventListener(event, () => this.resetTimeout(), { passive: true })
    })
  }

  logout(): void {
    // Clear all sensitive data
    this.accessToken = null
    sessionStorage.clear()
    // Navigate to login
  }
}
```

---

## 7. Dependency Security

### NPM Audit

```bash
# Check for vulnerabilities
pnpm audit

# Auto-fix where possible
pnpm audit --fix

# In CI/CD
pnpm audit --audit-level=high || exit 1
```

### Angular Update

```bash
# Check for updates
ng update

# Update Angular packages
ng update @angular/core @angular/cli

# Always test after updates
pnpm test
pnpm run build
```

---

## Security Checklist

### Before Deployment

**XSS Prevention:**
- [ ] No `bypassSecurityTrust*` with user input
- [ ] All user content displayed via interpolation `{{ }}`
- [ ] URLs validated before use
- [ ] Template strict mode enabled

**Authentication:**
- [ ] Tokens stored securely (memory or httpOnly cookies)
- [ ] Auto logout on token expiry
- [ ] Session timeout implemented
- [ ] Interceptors handle 401 responses

**Authorization:**
- [ ] Route guards protect sensitive routes
- [ ] CanMatch prevents unauthorized module loading
- [ ] Role-based access enforced
- [ ] Return URLs validated

**HTTP Security:**
- [ ] HTTPS enforced in production
- [ ] XSRF configuration correct
- [ ] Sensitive data never in URLs
- [ ] Credentials included for cookies

**Forms:**
- [ ] All inputs validated (client + server)
- [ ] File uploads validated (type, size)
- [ ] Autocomplete attributes set correctly

**Build:**
- [ ] AOT compilation enabled
- [ ] Production mode enabled
- [ ] Source maps disabled in production
- [ ] pnpm audit clean

**CSP:**
- [ ] Content Security Policy configured
- [ ] X-Frame-Options: DENY
- [ ] Strict-Transport-Security header
