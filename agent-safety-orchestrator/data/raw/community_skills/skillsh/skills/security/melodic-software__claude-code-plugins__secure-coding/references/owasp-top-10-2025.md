# OWASP Top 10 2025 Detailed Reference

This reference provides detailed mitigations and examples for each OWASP Top 10 2025 vulnerability category.

## A01:2025 - Broken Access Control

**Description:** Access control enforces policy such that users cannot act outside of their intended permissions. Failures typically lead to unauthorized information disclosure, modification, or destruction of data.

### Common Vulnerabilities

- Bypassing access control checks by modifying URLs, application state, or HTML pages
- Insecure Direct Object References (IDOR)
- Missing access control for API endpoints
- CORS misconfiguration allowing unauthorized API access
- Privilege escalation (acting as admin without authorization)
- Server-Side Request Forgery (SSRF) - now included in this category

### Mitigation Strategies

```csharp
// Good: Server-side access control check
public async Task<Document> GetDocumentAsync(string documentId, ClaimsPrincipal user)
{
    var document = await _context.Documents.FindAsync(documentId)
        ?? throw new NotFoundException("Document not found");

    var userId = user.FindFirstValue(ClaimTypes.NameIdentifier);

    // Verify ownership before returning
    if (document.OwnerId != userId && !user.IsInRole("Admin"))
        throw new ForbiddenException("Access denied");

    return document;
}

// Bad: No authorization check
public async Task<Document> GetDocumentAsync(string documentId)
{
    return await _context.Documents.FindAsync(documentId);  // VULNERABLE
}
```

**Key Controls:**

- Implement server-side access control with deny by default
- Use rate limiting to prevent automated attacks
- Log and alert on access control failures
- Invalidate sessions on logout
- Use indirect object references where appropriate

### SSRF Prevention

```csharp
using System.Net;

// Good: Validate and restrict URLs
public sealed class SsrfProtectedHttpClient(HttpClient httpClient)
{
    private static readonly HashSet<string> AllowedHosts = ["api.example.com", "cdn.example.com"];

    public async Task<HttpResponseMessage> FetchUrlAsync(string url, CancellationToken ct = default)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri))
            throw new ArgumentException("Invalid URL format");

        // Check against allowlist
        if (!AllowedHosts.Contains(uri.Host))
            throw new SecurityException("URL not in allowlist");

        // Block internal IPs
        if (IPAddress.TryParse(uri.Host, out var ip))
        {
            if (IsPrivateOrLoopback(ip))
                throw new SecurityException("Internal addresses not allowed");
        }
        else
        {
            // Resolve hostname and check IPs
            var addresses = await Dns.GetHostAddressesAsync(uri.Host, ct);
            if (addresses.Any(IsPrivateOrLoopback))
                throw new SecurityException("Hostname resolves to internal address");
        }

        return await httpClient.GetAsync(uri, ct);
    }

    private static bool IsPrivateOrLoopback(IPAddress ip) =>
        IPAddress.IsLoopback(ip) ||
        ip.ToString().StartsWith("10.") ||
        ip.ToString().StartsWith("192.168.") ||
        ip.ToString().StartsWith("172.16.");
}
```

---

## A02:2025 - Security Misconfiguration

**Description:** Security misconfiguration is the most common issue, often resulting from insecure default configurations, incomplete configurations, or ad hoc configurations.

### Common Vulnerabilities

- Default credentials not changed
- Unnecessary features enabled (ports, services, pages, accounts)
- Error messages exposing sensitive information
- Missing security headers
- Outdated software or security patches
- Misconfigured cloud storage permissions

### Mitigation Strategies

```yaml
# Good: Security headers in nginx
server {
    # Remove server version
    server_tokens off;

    # Security headers
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
}
```

**Key Controls:**

- Implement repeatable hardening processes
- Use minimal platforms without unnecessary features
- Review and update configurations regularly
- Implement automated security configuration verification

---

## A03:2025 - Software Supply Chain Failures

**Description:** Vulnerabilities related to untrusted dependencies, compromised CI/CD pipelines, or insufficient verification of software components.

### Common Vulnerabilities

- Using components with known vulnerabilities
- Dependency confusion attacks
- Typosquatting in package managers
- Compromised CI/CD pipelines
- Unsigned or unverified updates

### Mitigation Strategies

```json
// package.json - Use lock files and verify integrity
{
  "dependencies": {
    "express": "4.18.2"
  },
  "scripts": {
    "audit": "npm audit --audit-level=high",
    "check-deps": "npm-check-updates"
  }
}
```

**Key Controls:**

- Generate and maintain SBOM (Software Bill of Materials)
- Use Software Composition Analysis (SCA) tools
- Verify package integrity with checksums
- Implement dependency review in CI/CD
- Pin dependencies to specific versions
- Use private package registries for internal packages

See `supply-chain-security` skill for comprehensive guidance.

---

## A04:2025 - Cryptographic Failures

**Description:** Failures related to cryptography which often leads to exposure of sensitive data.

### Common Vulnerabilities

- Data transmitted in clear text (HTTP, SMTP, FTP)
- Old or weak cryptographic algorithms (MD5, SHA1, DES)
- Default or weak encryption keys
- Improper certificate validation
- Missing encryption for sensitive data at rest

### Mitigation Strategies

```csharp
using System.Security.Cryptography;

/// <summary>
/// Derive encryption key from password using PBKDF2.
/// </summary>
public static byte[] DeriveKey(string password, byte[] salt, int keyLength = 32)
{
    using var pbkdf2 = new Rfc2898DeriveBytes(
        password,
        salt,
        iterations: 600000,  // OWASP 2023 recommendation
        HashAlgorithmName.SHA256);

    return pbkdf2.GetBytes(keyLength);
}

/// <summary>
/// Encrypt data with password-derived key using AES-GCM.
/// </summary>
public static (byte[] Ciphertext, byte[] Salt, byte[] Nonce, byte[] Tag) EncryptData(
    byte[] data, string password)
{
    var salt = RandomNumberGenerator.GetBytes(16);
    var key = DeriveKey(password, salt);
    var nonce = RandomNumberGenerator.GetBytes(12);
    var tag = new byte[16];
    var ciphertext = new byte[data.Length];

    using var aes = new AesGcm(key, tagSizeInBytes: 16);
    aes.Encrypt(nonce, data, ciphertext, tag);

    CryptographicOperations.ZeroMemory(key);  // Clean up key
    return (ciphertext, salt, nonce, tag);
}
```

**Key Controls:**

- Use TLS 1.2+ for all data in transit
- Encrypt sensitive data at rest with AES-256
- Use strong key derivation (Argon2id, PBKDF2)
- Implement proper key management and rotation
- Disable deprecated protocols and ciphers

See `cryptography` skill for comprehensive guidance.

---

## A05:2025 - Injection

**Description:** Injection flaws occur when untrusted data is sent to an interpreter as part of a command or query.

### Common Vulnerabilities

- SQL injection
- NoSQL injection
- OS command injection
- LDAP injection
- XPath injection
- Cross-site scripting (XSS)

### Mitigation Strategies

```java
// Good: Parameterized query
String query = "SELECT * FROM users WHERE username = ? AND password = ?";
PreparedStatement stmt = connection.prepareStatement(query);
stmt.setString(1, username);
stmt.setString(2, hashedPassword);
ResultSet rs = stmt.executeQuery();

// Bad: String concatenation
String query = "SELECT * FROM users WHERE username = '" + username + "'";  // VULNERABLE
```

**Key Controls:**

- Use parameterized queries or prepared statements
- Use ORMs with parameterized queries
- Implement strict input validation
- Escape special characters based on context
- Use Content Security Policy (CSP) for XSS prevention

---

## A06:2025 - Insecure Design

**Description:** Risks related to design and architectural flaws, calling for more use of threat modeling, secure design patterns, and reference architectures.

### Common Vulnerabilities

- Missing security controls in design
- Lack of threat modeling
- Insufficient rate limiting
- Missing business logic validation
- Inadequate separation of concerns

### Mitigation Strategies

- Establish secure development lifecycle
- Use threat modeling (STRIDE, DREAD)
- Implement security requirements early
- Use secure design patterns
- Document and review security assumptions

See `threat-modeling` skill for comprehensive guidance.

---

## A07:2025 - Authentication Failures

**Description:** Confirmation of the user's identity, authentication, and session management is critical to protect against authentication-related attacks.

### Common Vulnerabilities

- Weak passwords allowed
- Missing brute force protection
- Credential stuffing vulnerability
- Session fixation
- Missing MFA
- Exposed session IDs in URLs

### Mitigation Strategies

```csharp
// Good: Rate limiting with account lockout
public sealed class AuthenticationService(AppDbContext context, IPasswordHasher passwordHasher)
{
    private const int MaxAttempts = 5;
    private static readonly TimeSpan LockoutDuration = TimeSpan.FromMinutes(15);

    public async Task<User> AuthenticateAsync(string username, string password, CancellationToken ct)
    {
        var user = await context.Users.FirstOrDefaultAsync(u => u.Username == username, ct);

        if (user?.LockedUntil > DateTime.UtcNow)
            throw new AccountLockedException("Account temporarily locked");

        if (user is null || !passwordHasher.Verify(password, user.PasswordHash))
        {
            if (user is not null)
            {
                user.FailedAttempts++;
                if (user.FailedAttempts >= MaxAttempts)
                    user.LockedUntil = DateTime.UtcNow + LockoutDuration;
                await context.SaveChangesAsync(ct);
            }
            throw new InvalidCredentialsException("Invalid username or password");
        }

        user.FailedAttempts = 0;
        user.LockedUntil = null;
        await context.SaveChangesAsync(ct);
        return user;
    }
}
```

**Key Controls:**

- Implement MFA for all users
- Use secure password hashing (Argon2id, bcrypt)
- Implement account lockout
- Generate random, unpredictable session tokens
- Invalidate sessions properly on logout

See `authentication-patterns` skill for comprehensive guidance.

---

## A08:2025 - Data Integrity Failures

**Description:** Code and infrastructure that does not protect against integrity violations, such as using untrusted sources for plugins, libraries, or modules.

### Common Vulnerabilities

- Insecure deserialization
- CI/CD pipeline integrity issues
- Auto-update without signature verification
- Data integrity not verified

### Mitigation Strategies

```csharp
using System.Security.Cryptography;

/// <summary>
/// Verify update integrity using HMAC.
/// </summary>
public static bool VerifyUpdate(byte[] updateData, string signature, byte[] secretKey)
{
    using var hmac = new HMACSHA256(secretKey);
    var computedHash = hmac.ComputeHash(updateData);
    var expectedSignature = Convert.ToHexString(computedHash).ToLowerInvariant();

    return CryptographicOperations.FixedTimeEquals(
        System.Text.Encoding.UTF8.GetBytes(expectedSignature),
        System.Text.Encoding.UTF8.GetBytes(signature));
}

public static void ApplyUpdate(byte[] updateData, string signature)
{
    if (!VerifyUpdate(updateData, signature, UpdateSecretKey))
        throw new IntegrityException("Update signature verification failed");
    // Apply update...
}
```

**Key Controls:**

- Use digital signatures for code and data
- Implement CI/CD pipeline security
- Verify integrity of all updates
- Avoid insecure deserialization

---

## A09:2025 - Logging & Alerting Failures

**Description:** Without logging and monitoring, breaches cannot be detected.

### Common Vulnerabilities

- Login, access control, and input validation failures not logged
- Warnings and errors generate no or inadequate log messages
- Logs not monitored for suspicious activity
- Logs only stored locally
- Alerting thresholds not set or ineffective

### Mitigation Strategies

```csharp
using Microsoft.Extensions.Logging;

// Configure structured security logging
public sealed class SecurityLogger(ILogger<SecurityLogger> logger)
{
    /// <summary>
    /// Log security events in structured format.
    /// </summary>
    public void LogSecurityEvent(string eventType, string? userId, object details)
    {
        logger.LogWarning(
            "Security Event: {EventType} | User: {UserId} | Details: {@Details}",
            eventType, userId ?? "anonymous", details);
    }
}

// Log authentication events
public sealed class LoggingAuthenticationService(
    ICredentialVerifier verifier,
    SecurityLogger securityLogger,
    IHttpContextAccessor httpContext)
{
    public async Task<User> AuthenticateAsync(string username, string password)
    {
        var ip = httpContext.HttpContext?.Connection.RemoteIpAddress?.ToString();
        var userAgent = httpContext.HttpContext?.Request.Headers.UserAgent.ToString();

        try
        {
            var user = await verifier.VerifyAsync(username, password);
            securityLogger.LogSecurityEvent("login_success", user.Id, new { Ip = ip });
            return user;
        }
        catch (InvalidCredentialsException)
        {
            securityLogger.LogSecurityEvent("login_failure", null, new
            {
                Username = username,
                Ip = ip,
                UserAgent = userAgent
            });
            throw;
        }
    }
}
```

**Key Controls:**

- Log authentication and authorization events
- Implement centralized log management
- Set up alerting for security events
- Protect log integrity
- Retain logs for incident response

---

## A10:2025 - Mishandling of Exceptional Conditions

**Description:** NEW in 2025. Poor error and exception handling that leads to unpredictable or insecure behavior.

### Common Vulnerabilities

- Failing open instead of failing securely
- Incomplete error recovery
- Inconsistent exception handling
- Information leakage through error messages
- Resource exhaustion from unhandled exceptions

### Mitigation Strategies

```csharp
using Microsoft.Extensions.Logging;

/// <summary>
/// Process payment with secure error handling.
/// </summary>
public async Task<PaymentResult> ProcessPaymentAsync(PaymentData paymentData)
{
    try
    {
        ValidatePayment(paymentData);
        var result = await _paymentGateway.ProcessAsync(paymentData);
        return result;
    }
    catch (ValidationException ex)
    {
        _logger.LogWarning(ex, "Payment validation failed");
        throw new PaymentException("Invalid payment data");  // Generic message
    }
    catch (TimeoutException)
    {
        _logger.LogError("Payment gateway timeout");
        throw new PaymentException("Service temporarily unavailable");
    }
    catch (Exception ex)
    {
        _logger.LogError(ex, "Unexpected payment error");
        // Fail securely - don't process payment
        throw new PaymentException("Payment processing failed");
    }
    finally
    {
        // Always clean up sensitive data
        paymentData.CardNumber = null;
        paymentData.Cvv = null;
    }
}
```

**Key Controls:**

- Design for failure scenarios
- Implement complete error handling
- Fail securely (deny access on error)
- Use generic error messages for users
- Log detailed errors securely
- Test error paths thoroughly

---

## Summary Table

| Category | Primary Defense | Secondary Defense |
|----------|----------------|-------------------|
| A01 Broken Access Control | Server-side access checks | Rate limiting, logging |
| A02 Security Misconfiguration | Hardened configurations | Automated verification |
| A03 Supply Chain | SCA, SBOM | Code signing, integrity checks |
| A04 Cryptographic Failures | TLS 1.2+, AES-256 | Key management, rotation |
| A05 Injection | Parameterized queries | Input validation, encoding |
| A06 Insecure Design | Threat modeling | Secure design patterns |
| A07 Authentication Failures | MFA, strong hashing | Account lockout, monitoring |
| A08 Data Integrity | Digital signatures | Pipeline security |
| A09 Logging Failures | Centralized logging | Alerting, monitoring |
| A10 Exception Handling | Fail securely | Complete error handling |
