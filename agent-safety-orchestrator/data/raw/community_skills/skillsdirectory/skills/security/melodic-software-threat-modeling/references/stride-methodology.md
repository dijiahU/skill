# STRIDE Methodology Deep Dive

Comprehensive guide to applying STRIDE threat modeling with real-world examples and mitigations.

## STRIDE Categories Detailed

### Spoofing (Authentication)

**Definition:** Impersonating something or someone else.

**Security Property Violated:** Authentication

**Common Attack Vectors:**

| Attack | Description | Example |
|--------|-------------|---------|
| Credential Theft | Stealing usernames/passwords | Phishing, keyloggers, breach data |
| Session Hijacking | Taking over active sessions | Cookie theft, session fixation |
| Token Forgery | Creating fake authentication tokens | JWT manipulation, token prediction |
| Identity Impersonation | Pretending to be another user/system | Spoofed headers, forged certificates |

**Mitigations:**

```csharp
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using Microsoft.IdentityModel.Tokens;

/// <summary>Comprehensive spoofing prevention.</summary>
public static class SpoofingMitigations
{
    /// <summary>Hash password using Argon2id (via ASP.NET Core Identity's PasswordHasher).</summary>
    public static string HashPassword(string password)
    {
        // Use ASP.NET Core Identity's PasswordHasher which uses PBKDF2 by default
        // For Argon2id, use Konscious.Security.Cryptography.Argon2 NuGet package
        using var argon2 = new Konscious.Security.Cryptography.Argon2id(
            System.Text.Encoding.UTF8.GetBytes(password))
        {
            DegreeOfParallelism = 4,
            MemorySize = 65536,
            Iterations = 3,
            Salt = RandomNumberGenerator.GetBytes(16)
        };

        var hash = argon2.GetBytes(32);
        return Convert.ToBase64String(hash);
    }

    /// <summary>Generate cryptographically secure session token.</summary>
    public static string GenerateSecureSessionToken() =>
        Convert.ToBase64String(RandomNumberGenerator.GetBytes(32));

    /// <summary>Validate JWT with explicit algorithm restriction.</summary>
    public static ClaimsPrincipal? ValidateJwtSignature(
        string token,
        string secret,
        string[]? allowedAlgorithms = null)
    {
        allowedAlgorithms ??= [SecurityAlgorithms.HmacSha256];

        var tokenHandler = new JwtSecurityTokenHandler();
        var key = System.Text.Encoding.UTF8.GetBytes(secret);

        var validationParameters = new TokenValidationParameters
        {
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(key),
            ValidateIssuer = false,  // Configure as needed
            ValidateAudience = false,  // Configure as needed
            ValidateLifetime = true,
            RequireExpirationTime = true,
            ClockSkew = TimeSpan.Zero,
            // CRITICAL: Explicitly specify allowed algorithms - never allow 'none'
            ValidAlgorithms = allowedAlgorithms
        };

        try
        {
            return tokenHandler.ValidateToken(token, validationParameters, out _);
        }
        catch (SecurityTokenException)
        {
            return null;
        }
    }

    /// <summary>Configure mutual TLS for service-to-service auth.</summary>
    public static HttpClientHandler CreateMtlsHandler(
        string clientCertPath,
        string? clientCertPassword = null)
    {
        var handler = new HttpClientHandler
        {
            ClientCertificateOptions = ClientCertificateOption.Manual,
            ServerCertificateCustomValidationCallback = (message, cert, chain, errors) =>
            {
                // Validate server certificate - in production, check against CA
                return errors == System.Net.Security.SslPolicyErrors.None;
            }
        };

        var clientCert = new System.Security.Cryptography.X509Certificates.X509Certificate2(
            clientCertPath,
            clientCertPassword);
        handler.ClientCertificates.Add(clientCert);

        return handler;
    }
}
```

**Checklist:**

- [ ] Multi-factor authentication enabled
- [ ] Passwords hashed with Argon2id/bcrypt
- [ ] Session tokens cryptographically random
- [ ] JWT algorithms explicitly specified (no 'none')
- [ ] Certificate validation for TLS
- [ ] Service-to-service authentication (mTLS)

---

### Tampering (Integrity)

**Definition:** Modifying data or code without authorization.

**Security Property Violated:** Integrity

**Common Attack Vectors:**

| Attack | Description | Example |
|--------|-------------|---------|
| Parameter Manipulation | Modifying request parameters | Price changes, privilege escalation |
| SQL Injection | Injecting malicious SQL | Data modification, deletion |
| Code Injection | Injecting executable code | XSS, command injection |
| Man-in-the-Middle | Intercepting and modifying traffic | TLS stripping, ARP spoofing |
| File Tampering | Modifying files on disk | Config files, executables |

**Mitigations:**

```csharp
using System.ComponentModel.DataAnnotations;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using Microsoft.Data.SqlClient;

/// <summary>Comprehensive tampering prevention.</summary>
public static partial class TamperingMitigations
{
    /// <summary>Use parameterized queries - NEVER string concatenation.</summary>
    public static async Task<object?> ExecuteParameterizedQueryAsync(
        SqlConnection connection,
        string userId,
        CancellationToken ct = default)
    {
        // WRONG: $"SELECT * FROM users WHERE id = '{userId}'"
        // RIGHT: Parameterized query
        const string query = "SELECT * FROM users WHERE id = @UserId";

        await using var cmd = new SqlCommand(query, connection);
        cmd.Parameters.AddWithValue("@UserId", userId);

        return await cmd.ExecuteScalarAsync(ct);
    }

    /// <summary>Generate HMAC for data integrity verification.</summary>
    public static string ComputeIntegrityHash(ReadOnlySpan<byte> data, ReadOnlySpan<byte> key)
    {
        Span<byte> hash = stackalloc byte[32];
        HMACSHA256.HashData(key, data, hash);
        return Convert.ToHexString(hash);
    }

    /// <summary>Verify data integrity using HMAC with timing-safe comparison.</summary>
    public static bool VerifyIntegrity(
        ReadOnlySpan<byte> data,
        string signature,
        ReadOnlySpan<byte> key)
    {
        var expected = ComputeIntegrityHash(data, key);
        return CryptographicOperations.FixedTimeEquals(
            System.Text.Encoding.UTF8.GetBytes(signature),
            System.Text.Encoding.UTF8.GetBytes(expected));
    }

    /// <summary>CSP headers to prevent XSS/injection.</summary>
    public static IReadOnlyDictionary<string, string> GetContentSecurityPolicyHeaders() =>
        new Dictionary<string, string>
        {
            ["Content-Security-Policy"] = string.Join(" ",
                "default-src 'self';",
                "script-src 'self' 'strict-dynamic';",
                "style-src 'self' 'unsafe-inline';",
                "img-src 'self' data: https:;",
                "font-src 'self';",
                "connect-src 'self';",
                "frame-ancestors 'none';",
                "base-uri 'self';",
                "form-action 'self';")
        };
}

/// <summary>Input validation using Data Annotations.</summary>
public sealed record UserInput : IValidatableObject
{
    [Required]
    [StringLength(20, MinimumLength = 3)]
    [RegularExpression(@"^[a-zA-Z0-9_]+$", ErrorMessage = "Invalid username format")]
    public required string Username { get; init; }

    [Required]
    [EmailAddress]
    [StringLength(254)]
    public required string Email { get; init; }

    [Range(0, 150)]
    public int? Age { get; init; }

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        // Additional custom validation logic
        if (Username.Contains("admin", StringComparison.OrdinalIgnoreCase) &&
            !validationContext.Items.ContainsKey("IsAdmin"))
        {
            yield return new ValidationResult(
                "Username cannot contain 'admin'",
                [nameof(Username)]);
        }
    }
}

/// <summary>Validator helper for input objects.</summary>
public static class InputValidator
{
    public static bool TryValidate<T>(T input, out IReadOnlyList<ValidationResult> errors)
        where T : class
    {
        var results = new List<ValidationResult>();
        var context = new ValidationContext(input);
        var isValid = Validator.TryValidateObject(input, context, results, validateAllProperties: true);
        errors = results;
        return isValid;
    }
}
```

**Checklist:**

- [ ] All database queries parameterized
- [ ] Input validation at all entry points
- [ ] Output encoding for context (HTML, JS, SQL)
- [ ] HMAC signatures for sensitive data
- [ ] CSP headers configured
- [ ] TLS for all data in transit

---

### Repudiation (Non-repudiation)

**Definition:** Claiming to not have performed an action.

**Security Property Violated:** Non-repudiation

**Common Attack Vectors:**

| Attack | Description | Example |
|--------|-------------|---------|
| Log Tampering | Modifying or deleting logs | Covering tracks after breach |
| Missing Audit Trail | No record of actions | Unprovable transactions |
| Timestamp Manipulation | Altering event times | Alibi creation |
| Identity Denial | Denying being the actor | Shared accounts, no auth |

**Mitigations:**

```csharp
using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

/// <summary>Immutable audit log entry.</summary>
public sealed record AuditEvent
{
    public string EventId { get; init; } = Guid.NewGuid().ToString();
    public DateTimeOffset Timestamp { get; init; } = DateTimeOffset.UtcNow;
    public required string ActorId { get; init; }
    public required string ActorIp { get; init; }
    public required string Action { get; init; }
    public required string ResourceType { get; init; }
    public required string ResourceId { get; init; }
    public required string Outcome { get; init; }
    public IReadOnlyDictionary<string, object> Details { get; init; } =
        new Dictionary<string, object>();
    public string PreviousHash { get; init; } = "";
    public string EventHash { get; private set; } = "";

    /// <summary>Compute hash for tamper detection (blockchain-style).</summary>
    public string ComputeHash()
    {
        var data = new
        {
            EventId,
            Timestamp = Timestamp.ToString("O"),
            ActorId,
            Action,
            ResourceType,
            ResourceId,
            Outcome,
            PreviousHash
        };

        var json = JsonSerializer.Serialize(data, new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            WriteIndented = false
        });

        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(json));
        return Convert.ToHexString(hash);
    }

    public AuditEvent WithComputedHash()
    {
        var hash = ComputeHash();
        return this with { EventHash = hash };
    }
}

/// <summary>Tamper-evident audit logging.</summary>
public sealed class AuditLogger(IAuditStorage storage)
{
    private string _lastHash = new string('0', 64);  // Genesis hash
    private readonly object _lock = new();

    public AuditEvent Log(
        string actorId,
        string actorIp,
        string action,
        string resourceType,
        string resourceId,
        string outcome,
        IReadOnlyDictionary<string, object>? details = null)
    {
        lock (_lock)
        {
            var auditEvent = new AuditEvent
            {
                ActorId = actorId,
                ActorIp = actorIp,
                Action = action,
                ResourceType = resourceType,
                ResourceId = resourceId,
                Outcome = outcome,
                Details = details ?? new Dictionary<string, object>(),
                PreviousHash = _lastHash
            }.WithComputedHash();

            _lastHash = auditEvent.EventHash;

            // Write to immutable storage (append-only)
            storage.Append(auditEvent);

            // Also forward to SIEM for real-time monitoring
            ForwardToSiem(auditEvent);

            return auditEvent;
        }
    }

    public (bool IsValid, string? Error) VerifyChain()
    {
        var events = storage.GetAll();
        var previousHash = new string('0', 64);

        foreach (var auditEvent in events)
        {
            // Verify hash chain
            if (auditEvent.PreviousHash != previousHash)
            {
                return (false, $"Chain break at {auditEvent.EventId}");
            }

            // Verify event hash
            var computed = auditEvent.ComputeHash();
            if (computed != auditEvent.EventHash)
            {
                return (false, $"Hash mismatch at {auditEvent.EventId}");
            }

            previousHash = auditEvent.EventHash;
        }

        return (true, null);
    }

    private static void ForwardToSiem(AuditEvent auditEvent)
    {
        // Implementation depends on SIEM (Splunk, ELK, Azure Sentinel, etc.)
    }
}

/// <summary>Storage interface for audit events.</summary>
public interface IAuditStorage
{
    void Append(AuditEvent auditEvent);
    IReadOnlyList<AuditEvent> GetAll();
}

// Usage example
public static class PaymentProcessor
{
    public static void ProcessPayment(
        AuditLogger audit,
        string userId,
        string ip,
        decimal amount)
    {
        string result;
        Dictionary<string, object> details;

        try
        {
            // ... payment processing logic ...
            result = "success";
            details = new() { ["amount"] = amount, ["currency"] = "USD" };
        }
        catch (Exception ex)
        {
            result = "failure";
            details = new() { ["error"] = ex.Message, ["amount"] = amount };
        }

        // Always log - success or failure
        audit.Log(
            actorId: userId,
            actorIp: ip,
            action: "payment.process",
            resourceType: "payment",
            resourceId: "pay_12345",
            outcome: result,
            details: details);
    }
}
```

**Checklist:**

- [ ] All security-relevant actions logged
- [ ] Logs include who, what, when, where, outcome
- [ ] Log integrity protected (hash chains, signing)
- [ ] Logs sent to central, append-only storage
- [ ] Timestamp from trusted source (NTP)
- [ ] User acknowledgment for critical actions

---

### Information Disclosure (Confidentiality)

**Definition:** Exposing information to unauthorized parties.

**Security Property Violated:** Confidentiality

**Common Attack Vectors:**

| Attack | Description | Example |
|--------|-------------|---------|
| Data Breach | Unauthorized data access | Database dump, backup exposure |
| Verbose Errors | Error messages reveal details | Stack traces, SQL errors |
| Metadata Leakage | Hidden data exposure | EXIF data, HTTP headers |
| Side-Channel | Indirect information leakage | Timing attacks, cache attacks |
| Insecure Storage | Unprotected sensitive data | Unencrypted passwords, logs |

**Mitigations:**

```csharp
using System.Collections.Frozen;
using System.Security.Cryptography;
using System.Text.RegularExpressions;

/// <summary>Comprehensive information disclosure prevention.</summary>
public static partial class InfoDisclosureMitigations
{
    // Patterns for sensitive data detection
    private static readonly FrozenDictionary<string, Regex> SensitivePatterns =
        new Dictionary<string, Regex>
        {
            ["EMAIL"] = EmailRegex(),
            ["SSN"] = SsnRegex(),
            ["CREDIT_CARD"] = CreditCardRegex(),
            ["PASSWORD"] = PasswordRegex(),
            ["API_KEY"] = ApiKeyRegex(),
            ["JWT"] = JwtRegex()
        }.ToFrozenDictionary();

    [GeneratedRegex(@"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", RegexOptions.IgnoreCase)]
    private static partial Regex EmailRegex();

    [GeneratedRegex(@"\b\d{3}-\d{2}-\d{4}\b")]
    private static partial Regex SsnRegex();

    [GeneratedRegex(@"\b\d{16}\b")]
    private static partial Regex CreditCardRegex();

    [GeneratedRegex(@"password[""']?\s*[:=]\s*[""']?[^""']+", RegexOptions.IgnoreCase)]
    private static partial Regex PasswordRegex();

    [GeneratedRegex(@"api[_-]?key[""']?\s*[:=]\s*[""']?[A-Za-z0-9]+", RegexOptions.IgnoreCase)]
    private static partial Regex ApiKeyRegex();

    [GeneratedRegex(@"bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+", RegexOptions.IgnoreCase)]
    private static partial Regex JwtRegex();

    /// <summary>Return safe error response without internal details.</summary>
    public static object SanitizeError(Exception error)
    {
        // Map internal errors to safe external messages
        var safeMessage = error switch
        {
            Microsoft.Data.SqlClient.SqlException => "A database error occurred",
            System.ComponentModel.DataAnnotations.ValidationException => "Invalid input provided",
            UnauthorizedAccessException => "Authentication failed",
            InvalidOperationException when error.Message.Contains("permission") => "Access denied",
            _ => "An error occurred"
        };

        return new
        {
            Error = safeMessage,
            ErrorId = GenerateErrorId()
            // Log full details internally, return safe message externally
        };
    }

    /// <summary>Redact sensitive patterns from logs/output.</summary>
    public static string RedactSensitiveData(string text)
    {
        var redacted = text;
        foreach (var (dataType, regex) in SensitivePatterns)
        {
            redacted = regex.Replace(redacted, $"[REDACTED_{dataType}]");
        }
        return redacted;
    }

    /// <summary>Security headers to prevent information leakage.</summary>
    public static IReadOnlyDictionary<string, string> GetSecureHeaders() =>
        new Dictionary<string, string>
        {
            ["X-Content-Type-Options"] = "nosniff",
            ["X-Frame-Options"] = "DENY",
            ["X-XSS-Protection"] = "0",  // Disabled - use CSP instead
            ["Referrer-Policy"] = "strict-origin-when-cross-origin",
            ["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
            // Remove revealing headers via middleware: Server, X-Powered-By
        };

    /// <summary>Encrypt data at rest using AES-256-GCM.</summary>
    public static byte[] EncryptAtRest(ReadOnlySpan<byte> plaintext, ReadOnlySpan<byte> key)
    {
        var nonce = RandomNumberGenerator.GetBytes(12);
        var ciphertext = new byte[plaintext.Length];
        var tag = new byte[16];

        using var aes = new AesGcm(key, 16);
        aes.Encrypt(nonce, plaintext, ciphertext, tag);

        // Return nonce + ciphertext + tag
        var result = new byte[nonce.Length + ciphertext.Length + tag.Length];
        nonce.CopyTo(result.AsSpan());
        ciphertext.CopyTo(result.AsSpan(nonce.Length));
        tag.CopyTo(result.AsSpan(nonce.Length + ciphertext.Length));

        return result;
    }

    private static string GenerateErrorId() => Guid.NewGuid().ToString()[..8];
}

/// <summary>Data classification for appropriate handling.</summary>
public sealed record DataClassificationRequirements
{
    public required bool EncryptionRequired { get; init; }
    public required bool AccessLogging { get; init; }
    public required int RetentionDays { get; init; }
    public bool ApprovalRequired { get; init; }
    public bool MfaRequired { get; init; }
}

public static class DataClassification
{
    private static readonly FrozenDictionary<string, DataClassificationRequirements> Levels =
        new Dictionary<string, DataClassificationRequirements>
        {
            ["public"] = new()
            {
                EncryptionRequired = false,
                AccessLogging = false,
                RetentionDays = 365
            },
            ["internal"] = new()
            {
                EncryptionRequired = true,
                AccessLogging = true,
                RetentionDays = 180
            },
            ["confidential"] = new()
            {
                EncryptionRequired = true,
                AccessLogging = true,
                RetentionDays = 90,
                ApprovalRequired = true
            },
            ["restricted"] = new()
            {
                EncryptionRequired = true,
                AccessLogging = true,
                RetentionDays = 30,
                ApprovalRequired = true,
                MfaRequired = true
            }
        }.ToFrozenDictionary();

    public static DataClassificationRequirements GetRequirements(string level) =>
        Levels.GetValueOrDefault(level, Levels["restricted"]);
}
```

**Checklist:**

- [ ] Sensitive data encrypted at rest
- [ ] TLS 1.3 for data in transit
- [ ] Error messages sanitized (no stack traces)
- [ ] Logs scrubbed of sensitive data
- [ ] Debug endpoints disabled in production
- [ ] Security headers configured
- [ ] Data classified and handled appropriately

---

### Denial of Service (Availability)

**Definition:** Making a system unavailable or degraded.

**Security Property Violated:** Availability

**Common Attack Vectors:**

| Attack | Description | Example |
|--------|-------------|---------|
| Volume-based | Overwhelming with traffic | DDoS, amplification attacks |
| Protocol-based | Exploiting protocol weaknesses | SYN flood, Slowloris |
| Application-based | Resource exhaustion | Regex DoS, zip bombs |
| Logical | Triggering expensive operations | Complex queries, report generation |

**Mitigations:**

```csharp
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text.RegularExpressions;
using Polly;
using Polly.CircuitBreaker;

/// <summary>Token bucket rate limiter.</summary>
public sealed class RateLimiter(double rate, double capacity)
{
    private double _tokens = capacity;
    private long _lastUpdate = Stopwatch.GetTimestamp();
    private readonly object _lock = new();

    /// <summary>Try to acquire tokens, return success.</summary>
    public bool TryAcquire(double tokens = 1.0)
    {
        lock (_lock)
        {
            var now = Stopwatch.GetTimestamp();
            var elapsed = (now - _lastUpdate) / (double)Stopwatch.Frequency;
            _lastUpdate = now;

            // Add tokens based on elapsed time
            _tokens = Math.Min(capacity, _tokens + elapsed * rate);

            if (_tokens >= tokens)
            {
                _tokens -= tokens;
                return true;
            }
            return false;
        }
    }
}

/// <summary>Comprehensive DoS prevention.</summary>
public sealed class DoSMitigations
{
    // Per-IP rate limiters
    private readonly ConcurrentDictionary<string, RateLimiter> _ipLimiters = new();
    // Per-user rate limiters (more generous)
    private readonly ConcurrentDictionary<string, RateLimiter> _userLimiters = new();

    /// <summary>Check if request is within rate limits.</summary>
    public (bool Allowed, object? Error) CheckRateLimit(string ip, string? userId = null)
    {
        // Always check IP limit
        var ipLimiter = _ipLimiters.GetOrAdd(ip, _ => new RateLimiter(rate: 10, capacity: 100));
        if (!ipLimiter.TryAcquire())
        {
            return (false, new { Error = "Rate limit exceeded", RetryAfter = 60 });
        }

        // If authenticated, also check user limit
        if (userId is not null)
        {
            var userLimiter = _userLimiters.GetOrAdd(userId, _ => new RateLimiter(rate: 100, capacity: 1000));
            if (!userLimiter.TryAcquire())
            {
                return (false, new { Error = "User rate limit exceeded", RetryAfter = 60 });
            }
        }

        return (true, null);
    }

    /// <summary>Prevent resource exhaustion from large payloads.</summary>
    public static bool ValidateInputSize(ReadOnlySpan<byte> data, int maxSize = 10 * 1024 * 1024) =>
        data.Length <= maxSize;

    /// <summary>Execute regex with timeout to prevent ReDoS.</summary>
    public static IReadOnlyList<string>? SafeRegexWithTimeout(
        string pattern,
        string text,
        TimeSpan timeout)
    {
        try
        {
            // Use .NET's built-in regex timeout
            var regex = new Regex(pattern, RegexOptions.None, timeout);
            return regex.Matches(text).Select(m => m.Value).ToList();
        }
        catch (RegexMatchTimeoutException)
        {
            return null;
        }
    }
}

/// <summary>Circuit breaker using Polly.</summary>
public static class CircuitBreakerFactory
{
    /// <summary>Create a circuit breaker policy.</summary>
    public static AsyncCircuitBreakerPolicy CreateCircuitBreaker(
        int failureThreshold = 5,
        TimeSpan? recoveryTimeout = null)
    {
        return Policy
            .Handle<Exception>()
            .CircuitBreakerAsync(
                exceptionsAllowedBeforeBreaking: failureThreshold,
                durationOfBreak: recoveryTimeout ?? TimeSpan.FromSeconds(30),
                onBreak: (ex, breakDelay) =>
                {
                    // Log circuit opened
                },
                onReset: () =>
                {
                    // Log circuit reset
                },
                onHalfOpen: () =>
                {
                    // Log half-open state
                });
    }

    /// <summary>Create a typed circuit breaker.</summary>
    public static AsyncCircuitBreakerPolicy<T> CreateCircuitBreaker<T>(
        int failureThreshold = 5,
        TimeSpan? recoveryTimeout = null)
    {
        return Policy<T>
            .Handle<Exception>()
            .CircuitBreakerAsync(
                handledEventsAllowedBeforeBreaking: failureThreshold,
                durationOfBreak: recoveryTimeout ?? TimeSpan.FromSeconds(30));
    }
}

// Usage example with Polly
public sealed class ResilientHttpClient(HttpClient httpClient)
{
    private readonly AsyncCircuitBreakerPolicy _circuitBreaker =
        CircuitBreakerFactory.CreateCircuitBreaker(failureThreshold: 5);

    public async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken ct = default)
    {
        return await _circuitBreaker.ExecuteAsync(async () =>
            await httpClient.SendAsync(request, ct));
    }
}
```

**Nginx rate limiting configuration:**

```nginx
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=ip_limit:10m rate=10r/s;
limit_req_zone $http_authorization zone=user_limit:10m rate=100r/s;

# Connection limiting
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

server {
    # Apply rate limits
    limit_req zone=ip_limit burst=20 nodelay;
    limit_conn conn_limit 10;

    # Request size limits
    client_max_body_size 10m;
    client_body_timeout 10s;
    client_header_timeout 10s;

    # Response timeout
    send_timeout 10s;
}
```

**Checklist:**

- [ ] Rate limiting at network and application layers
- [ ] Input size limits enforced
- [ ] Timeouts on all external calls
- [ ] Circuit breakers for cascading failure prevention
- [ ] Resource quotas (CPU, memory, connections)
- [ ] CDN/DDoS protection (Cloudflare, AWS Shield)
- [ ] Graceful degradation under load

---

### Elevation of Privilege (Authorization)

**Definition:** Gaining capabilities beyond what was granted.

**Security Property Violated:** Authorization

**Common Attack Vectors:**

| Attack | Description | Example |
|--------|-------------|---------|
| IDOR | Direct object reference bypass | /api/users/123 -> /api/users/456 |
| Privilege Escalation | Gaining admin from user | Role manipulation, admin endpoints |
| JWT Manipulation | Modifying token claims | Changing role claim |
| Path Traversal | Accessing unauthorized files | ../../../etc/passwd |
| SSRF | Server-side request to internal | Accessing metadata service |

**Mitigations:**

```csharp
using System.Collections.Frozen;
using System.Net;

/// <summary>Current user's authorization context.</summary>
public sealed record AuthorizationContext
{
    public required string UserId { get; init; }
    public required IReadOnlyList<string> Roles { get; init; }
    public required IReadOnlyList<string> Permissions { get; init; }
    public string? TenantId { get; init; }
}

/// <summary>Comprehensive elevation of privilege prevention.</summary>
public sealed class EoPMitigations
{
    private readonly Func<AuthorizationContext> _getAuthContext;
    private readonly Action<string, string>? _logAdminAccess;

    public EoPMitigations(
        Func<AuthorizationContext> getAuthContext,
        Action<string, string>? logAdminAccess = null)
    {
        _getAuthContext = getAuthContext;
        _logAdminAccess = logAdminAccess;
    }

    /// <summary>Check if current user has required permission.</summary>
    public bool RequirePermission(string permission)
    {
        var ctx = _getAuthContext();
        if (!ctx.Permissions.Contains(permission))
        {
            throw new UnauthorizedAccessException($"Missing permission: {permission}");
        }
        return true;
    }

    /// <summary>Verify user owns or has access to resource.</summary>
    public bool VerifyResourceOwnership(AuthorizationContext ctx, string resourceOwnerId)
    {
        // Owner check
        if (ctx.UserId == resourceOwnerId)
            return true;

        // Admin override (be careful with this)
        if (ctx.Roles.Contains("admin"))
        {
            // Log admin access for audit
            _logAdminAccess?.Invoke(ctx.UserId, resourceOwnerId);
            return true;
        }

        return false;
    }

    /// <summary>Prevent path traversal attacks.</summary>
    public static string? SanitizePath(string userPath, string baseDir)
    {
        // Resolve to absolute path
        var fullPath = Path.GetFullPath(Path.Combine(baseDir, userPath));
        var normalizedBase = Path.GetFullPath(baseDir);

        // Verify still within base directory
        if (!fullPath.StartsWith(normalizedBase, StringComparison.OrdinalIgnoreCase))
            return null;  // Path traversal attempt

        return fullPath;
    }

    /// <summary>Prevent SSRF by validating target URL.</summary>
    public static bool ValidateSsrfTarget(string url)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri))
            return false;

        // Block internal schemes
        if (uri.Scheme is not ("http" or "https"))
            return false;

        var hostname = uri.Host;

        // Block internal hostnames
        string[] blockedHosts =
        [
            "localhost", "127.0.0.1", "0.0.0.0",
            "metadata.google.internal",  // GCP metadata
            "169.254.169.254",  // AWS/Azure metadata
            "metadata.azure.com"
        ];

        if (blockedHosts.Contains(hostname, StringComparer.OrdinalIgnoreCase))
            return false;

        // Block private IP ranges
        if (IPAddress.TryParse(hostname, out var ip))
        {
            if (IsPrivateOrReserved(ip))
                return false;
        }

        return true;
    }

    private static bool IsPrivateOrReserved(IPAddress ip)
    {
        var bytes = ip.GetAddressBytes();

        return ip.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork &&
            (bytes[0] == 10 ||  // 10.0.0.0/8
             (bytes[0] == 172 && bytes[1] >= 16 && bytes[1] <= 31) ||  // 172.16.0.0/12
             (bytes[0] == 192 && bytes[1] == 168) ||  // 192.168.0.0/16
             bytes[0] == 127 ||  // Loopback
             (bytes[0] == 169 && bytes[1] == 254));  // Link-local
    }
}

/// <summary>Role-based access control with least privilege.</summary>
public sealed class RbacAuthorizer
{
    private static readonly FrozenDictionary<string, IReadOnlyList<string>> RolePermissions =
        new Dictionary<string, IReadOnlyList<string>>
        {
            ["viewer"] = ["read"],
            ["editor"] = ["read", "write"],
            ["admin"] = ["read", "write", "delete", "manage_users"],
            ["super_admin"] = ["*"]  // All permissions
        }.ToFrozenDictionary();

    private static readonly IReadOnlyList<string> RoleHierarchy =
        ["viewer", "editor", "admin", "super_admin"];

    private readonly Dictionary<string, List<string>> _userRoles = new();

    /// <summary>Check if user has required permission.</summary>
    public bool HasPermission(string userId, string requiredPermission)
    {
        if (!_userRoles.TryGetValue(userId, out var roles))
            return false;

        foreach (var role in roles)
        {
            if (!RolePermissions.TryGetValue(role, out var permissions))
                continue;

            if (permissions.Contains("*") || permissions.Contains(requiredPermission))
                return true;
        }

        return false;
    }

    /// <summary>Assign role with privilege escalation prevention.</summary>
    public void AssignRole(string userId, string role, string assignerId)
    {
        if (!_userRoles.TryGetValue(assignerId, out var assignerRoles))
            assignerRoles = [];

        // Check if assigner can grant this role (must have higher or equal privilege)
        if (!CanGrantRole(assignerRoles, role))
        {
            throw new UnauthorizedAccessException("Cannot assign role with higher privilege");
        }

        if (!_userRoles.ContainsKey(userId))
            _userRoles[userId] = [];

        _userRoles[userId].Add(role);
    }

    private static bool CanGrantRole(IReadOnlyList<string> assignerRoles, string targetRole)
    {
        var assignerLevel = assignerRoles
            .Where(r => RoleHierarchy.Contains(r))
            .Select(r => RoleHierarchy.IndexOf(r))
            .DefaultIfEmpty(-1)
            .Max();

        var targetLevel = RoleHierarchy.Contains(targetRole)
            ? RoleHierarchy.IndexOf(targetRole)
            : 999;

        return assignerLevel >= targetLevel;
    }
}
```

**Checklist:**

- [ ] All endpoints require authentication
- [ ] Authorization checked on every request
- [ ] Resource ownership verified (no IDOR)
- [ ] Path traversal prevented
- [ ] SSRF protection for external requests
- [ ] Least privilege for service accounts
- [ ] Role assignments audited

## STRIDE per Interaction

For data flows, analyze the interaction rather than individual elements:

```csharp
/// <summary>STRIDE threat categories.</summary>
public enum StrideCategory
{
    Spoofing,
    Tampering,
    Repudiation,
    InformationDisclosure,
    DenialOfService,
    ElevationOfPrivilege
}

/// <summary>Data flow representation for interaction analysis.</summary>
public sealed record DataFlow
{
    public required string Id { get; init; }
    public required string Source { get; init; }
    public required string Destination { get; init; }
    public required string DataType { get; init; }
    public bool Encrypted { get; init; }
    public bool Authenticated { get; init; }
}

/// <summary>Threat specific to element interaction.</summary>
public sealed record InteractionThreat
{
    public required string SourceElement { get; init; }
    public required string TargetElement { get; init; }
    public required string DataFlow { get; init; }
    public required StrideCategory Category { get; init; }
    public required string Threat { get; init; }
    public required string Mitigation { get; init; }
}

/// <summary>STRIDE per Interaction analyzer for data flows.</summary>
public static class InteractionAnalyzer
{
    /// <summary>Analyze threats specific to data flow interactions.</summary>
    public static IReadOnlyList<InteractionThreat> AnalyzeInteraction(DataFlow flow)
    {
        var threats = new List<InteractionThreat>();

        // Unencrypted flow - Information Disclosure
        if (!flow.Encrypted)
        {
            threats.Add(new InteractionThreat
            {
                SourceElement = flow.Source,
                TargetElement = flow.Destination,
                DataFlow = flow.Id,
                Category = StrideCategory.InformationDisclosure,
                Threat = "Data exposed in transit",
                Mitigation = "Enable TLS encryption"
            });
        }

        // Unauthenticated flow - Spoofing
        if (!flow.Authenticated)
        {
            threats.Add(new InteractionThreat
            {
                SourceElement = flow.Source,
                TargetElement = flow.Destination,
                DataFlow = flow.Id,
                Category = StrideCategory.Spoofing,
                Threat = "Source cannot be verified",
                Mitigation = "Implement mutual authentication"
            });
        }

        return threats;
    }
}
```

## Version History

- **v1.0.0** (2025-12-26): Initial release with all STRIDE categories

---

**Last Updated:** 2025-12-26
