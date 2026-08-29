# JWT Security Deep Dive

This reference provides comprehensive guidance on secure JWT implementation.

## JWT Structure

```text
xxxxx.yyyyy.zzzzz
  │      │      │
  │      │      └── Signature (verified with secret/public key)
  │      └── Payload (claims - base64url encoded, NOT encrypted)
  └── Header (algorithm & type - base64url encoded)
```

**Critical Understanding:** JWT payload is NOT encrypted - it's only base64url encoded. Anyone can decode and read the payload. Never put sensitive data in JWTs.

## Algorithm Security

### Recommended Algorithms

| Algorithm | Type | Use Case | Key Size |
|-----------|------|----------|----------|
| RS256 | Asymmetric (RSA) | Distributed verification | 2048+ bits |
| RS384 | Asymmetric (RSA) | Higher security | 3072+ bits |
| RS512 | Asymmetric (RSA) | Maximum RSA security | 4096 bits |
| ES256 | Asymmetric (ECDSA) | Smaller tokens, mobile | P-256 curve |
| ES384 | Asymmetric (ECDSA) | Higher security | P-384 curve |
| ES512 | Asymmetric (ECDSA) | Maximum ECDSA security | P-521 curve |
| EdDSA | Asymmetric (Ed25519) | Modern, fast | Ed25519 |
| HS256 | Symmetric (HMAC) | Same-party only | 256+ bits |

### Algorithm Attacks and Mitigations

#### Algorithm Confusion Attack

```csharp
// VULNERABLE: Accepting algorithm from token header
var handler = new JwtSecurityTokenHandler();
var unverifiedToken = handler.ReadJwtToken(token);
var algorithm = unverifiedToken.Header.Alg;  // NEVER trust this!

// SECURE: Explicitly specify allowed algorithms in validation parameters
var validationParameters = new TokenValidationParameters
{
    ValidAlgorithms = new[] { SecurityAlgorithms.RsaSha256 },  // Explicit allowlist
    ValidateIssuerSigningKey = true,
    IssuerSigningKey = publicKey
};
```

#### None Algorithm Attack

```csharp
// VULNERABLE: Configuration that could allow 'none' algorithm
var validationParameters = new TokenValidationParameters
{
    RequireSignedTokens = false  // NEVER do this!
};

// SECURE: Always require signed tokens (default behavior)
var validationParameters = new TokenValidationParameters
{
    RequireSignedTokens = true,  // Default is true
    ValidAlgorithms = new[] { SecurityAlgorithms.RsaSha256 }
};
```

#### Key Confusion (RS256 to HS256)

An attacker might try to trick the server into using the public key as an HMAC secret:

```csharp
// SECURE: Use TokenValidationParameters with explicit key type
var validationParameters = new TokenValidationParameters
{
    // For asymmetric algorithms, use IssuerSigningKey with RSA/ECDSA key
    IssuerSigningKey = new RsaSecurityKey(rsaParameters),

    // Never set both symmetric and asymmetric keys unless you have a good reason
    // The library will match the algorithm to the appropriate key type

    ValidAlgorithms = new[] { SecurityAlgorithms.RsaSha256 }  // Explicit algorithm
};

// For validation with multiple key types, use explicit resolver
validationParameters.IssuerSigningKeyResolver = (token, securityToken, kid, parameters) =>
{
    var jwt = securityToken as JwtSecurityToken;
    return jwt?.Header.Alg switch
    {
        SecurityAlgorithms.RsaSha256 => new[] { asymmetricKey },
        SecurityAlgorithms.HmacSha256 => new[] { symmetricKey },
        _ => throw new SecurityTokenInvalidAlgorithmException("Unsupported algorithm")
    };
};
```

## Claim Validation

### Required Validations

```csharp
using System.IdentityModel.Tokens.Jwt;
using Microsoft.IdentityModel.Tokens;

/// <summary>
/// Comprehensive JWT validation with all required claims.
/// </summary>
public sealed class JwtValidator(SecurityKey publicKey, string expectedAudience, string expectedIssuer)
{
    private readonly JwtSecurityTokenHandler _handler = new();
    private readonly TokenValidationParameters _validationParameters = new()
    {
        ValidateIssuerSigningKey = true,
        IssuerSigningKey = publicKey,

        ValidateIssuer = true,
        ValidIssuer = expectedIssuer,

        ValidateAudience = true,
        ValidAudience = expectedAudience,

        ValidateLifetime = true,
        ClockSkew = TimeSpan.FromSeconds(30),  // Allow 30s clock drift

        ValidAlgorithms = new[] { SecurityAlgorithms.RsaSha256 },

        // Require specific claims
        RequireExpirationTime = true,
        RequireSignedTokens = true
    };

    public ClaimsPrincipal ValidateToken(string token)
    {
        try
        {
            var principal = _handler.ValidateToken(token, _validationParameters, out var validatedToken);

            // Additional claim validation
            var jwt = validatedToken as JwtSecurityToken
                ?? throw new SecurityTokenValidationException("Invalid token type");

            // Verify required claims are present
            var requiredClaims = new[] { "sub", "iat", "jti" };
            foreach (var claim in requiredClaims)
            {
                if (!jwt.Payload.ContainsKey(claim))
                    throw new SecurityTokenValidationException($"Missing required claim: {claim}");
            }

            return principal;
        }
        catch (SecurityTokenExpiredException)
        {
            throw new AuthException("Token expired");
        }
        catch (SecurityTokenInvalidAudienceException)
        {
            throw new AuthException("Invalid audience");
        }
        catch (SecurityTokenInvalidIssuerException)
        {
            throw new AuthException("Invalid issuer");
        }
        catch (SecurityTokenException ex)
        {
            throw new AuthException($"Invalid token: {ex.Message}");
        }
    }
}
```

### Claim Reference

| Claim | Name | Purpose | Validation |
|-------|------|---------|------------|
| `iss` | Issuer | Who issued the token | Must match expected issuer |
| `sub` | Subject | User identifier | Use for user lookup |
| `aud` | Audience | Intended recipient | Must match your service |
| `exp` | Expiration | Token expiry time | Must be in future |
| `iat` | Issued At | Token creation time | Should be in past |
| `nbf` | Not Before | Token valid from | Should be in past |
| `jti` | JWT ID | Unique identifier | Use for revocation |

## Token Lifecycle

### Access Token Best Practices

```csharp
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using Microsoft.IdentityModel.Tokens;

/// <summary>
/// JWT token generation service for access and refresh tokens.
/// </summary>
public sealed class TokenService(RsaSecurityKey privateKey, string issuer, string audience)
{
    /// <summary>
    /// Create short-lived access token (15 minutes).
    /// </summary>
    public string CreateAccessToken(string userId, IEnumerable<string> scopes)
    {
        var now = DateTime.UtcNow;
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, userId),
            new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString()),  // For revocation
            new("scope", string.Join(" ", scopes)),
            new("type", "access")
        };

        var token = new JwtSecurityToken(
            issuer: issuer,
            audience: audience,
            claims: claims,
            notBefore: now,
            expires: now.AddMinutes(15),  // Short-lived!
            signingCredentials: new SigningCredentials(privateKey, SecurityAlgorithms.RsaSha256)
        );

        return new JwtSecurityTokenHandler().WriteToken(token);
    }
}
```

### Refresh Token Best Practices

```csharp
/// <summary>
/// Create refresh token with device binding (30 days).
/// </summary>
public string CreateRefreshToken(string userId, string deviceId)
{
    var now = DateTime.UtcNow;
    var claims = new List<Claim>
    {
        new(JwtRegisteredClaimNames.Sub, userId),
        new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString()),  // For revocation
        new("device_id", deviceId),  // Bind to device
        new("type", "refresh")
    };

    var token = new JwtSecurityToken(
        issuer: issuer,
        audience: issuer,  // Refresh tokens audience is the auth server itself
        claims: claims,
        notBefore: now,
        expires: now.AddDays(30),  // Longer-lived
        signingCredentials: new SigningCredentials(privateKey, SecurityAlgorithms.RsaSha256)
    );

    return new JwtSecurityTokenHandler().WriteToken(token);
}
```

### Token Refresh Flow

```csharp
/// <summary>
/// Refresh token rotation pattern with theft detection.
/// </summary>
public sealed class TokenRefreshService(
    TokenService tokenService,
    ITokenRevocationStore revocationStore,
    IUserService userService)
{
    public async Task<(string AccessToken, string RefreshToken)> RefreshTokensAsync(string refreshToken)
    {
        // 1. Validate refresh token
        var principal = ValidateRefreshToken(refreshToken);
        var userId = principal.FindFirstValue(JwtRegisteredClaimNames.Sub)
            ?? throw new AuthException("Missing subject claim");
        var jti = principal.FindFirstValue(JwtRegisteredClaimNames.Jti)
            ?? throw new AuthException("Missing jti claim");
        var deviceId = principal.FindFirstValue("device_id")
            ?? throw new AuthException("Missing device_id claim");

        if (principal.FindFirstValue("type") != "refresh")
            throw new AuthException("Not a refresh token");

        // 2. Check if token is revoked (theft detection)
        if (await revocationStore.IsRevokedAsync(jti))
        {
            // Potential token theft - revoke all user tokens
            await revocationStore.RevokeAllUserTokensAsync(userId);
            throw new AuthException("Token revoked - potential theft detected");
        }

        // 3. Revoke old refresh token (rotation)
        await revocationStore.RevokeTokenAsync(jti);

        // 4. Issue new token pair
        var scopes = await userService.GetUserScopesAsync(userId);
        var newAccess = tokenService.CreateAccessToken(userId, scopes);
        var newRefresh = tokenService.CreateRefreshToken(userId, deviceId);

        return (newAccess, newRefresh);
    }
}
```

## Token Revocation

### Revocation Strategies

| Strategy | Pros | Cons |
|----------|------|------|
| Short expiry | Simple, no state | Can't revoke immediately |
| Blocklist | Immediate revocation | Requires state, storage |
| Token versioning | Per-user revocation | Requires DB lookup |
| Refresh token rotation | Detects theft | Complex implementation |

### Blocklist Implementation

```csharp
using StackExchange.Redis;

/// <summary>
/// Redis-based token revocation store with automatic TTL cleanup.
/// </summary>
public sealed class RedisTokenRevocationStore(IConnectionMultiplexer redis) : ITokenRevocationStore
{
    private readonly IDatabase _db = redis.GetDatabase();

    /// <summary>
    /// Add token to blocklist until it would expire anyway.
    /// </summary>
    public async Task RevokeTokenAsync(string jti, DateTime expiration)
    {
        var ttl = expiration - DateTime.UtcNow;
        if (ttl > TimeSpan.Zero)
        {
            await _db.StringSetAsync($"revoked:{jti}", "1", ttl);
        }
    }

    /// <summary>
    /// Check if token is revoked.
    /// </summary>
    public async Task<bool> IsRevokedAsync(string jti)
    {
        return await _db.KeyExistsAsync($"revoked:{jti}");
    }

    /// <summary>
    /// Revoke all tokens for a user (theft detection response).
    /// </summary>
    public async Task RevokeAllUserTokensAsync(string userId)
    {
        // Store user revocation timestamp - all tokens issued before this are invalid
        await _db.StringSetAsync($"user_revoked:{userId}", DateTime.UtcNow.Ticks.ToString());
    }
}
```

## Key Management

### Key Rotation

```csharp
using System.Security.Cryptography;
using Microsoft.IdentityModel.Tokens;

/// <summary>
/// RSA key rotation service for JWT signing.
/// </summary>
public sealed class KeyRotationService(IKeyStore keyStore)
{
    /// <summary>
    /// Generate new key pair and update JWKS.
    /// </summary>
    public async Task RotateKeysAsync()
    {
        // Generate new RSA key pair
        using var rsa = RSA.Create(2048);
        var rsaParameters = rsa.ExportParameters(includePrivateParameters: true);

        // Assign key ID (use timestamp or version)
        var newKid = $"key-{DateTimeOffset.UtcNow.ToUnixTimeSeconds()}";

        var newKey = new RsaSecurityKey(rsaParameters) { KeyId = newKid };

        // Add to JWKS (keep old keys for validation during transition)
        var currentKeys = await keyStore.GetSigningKeysAsync();
        var updatedKeys = currentKeys.Append(newKey).TakeLast(3).ToList();  // Keep last 3 keys

        await keyStore.UpdateSigningKeysAsync(updatedKeys);
        await keyStore.SetCurrentSigningKeyAsync(newKid, newKey);
    }

    /// <summary>
    /// Convert RSA key to JWK format for JWKS endpoint.
    /// </summary>
    public static JsonWebKey ToJsonWebKey(RsaSecurityKey key)
    {
        return JsonWebKeyConverter.ConvertFromRSASecurityKey(key);
    }
}
```

### JWKS Endpoint

```csharp
using Microsoft.AspNetCore.Mvc;
using Microsoft.IdentityModel.Tokens;

/// <summary>
/// Minimal API endpoint for serving JWKS.
/// </summary>
public static class JwksEndpoint
{
    public static void MapJwks(this IEndpointRouteBuilder app, IKeyStore keyStore)
    {
        app.MapGet("/.well-known/jwks.json", async () =>
        {
            var keys = await keyStore.GetPublicKeysAsync();

            var jwks = new JsonWebKeySet();
            foreach (var key in keys)
            {
                var jwk = JsonWebKeyConverter.ConvertFromRSASecurityKey(key);
                jwk.Use = "sig";
                jwk.Alg = SecurityAlgorithms.RsaSha256;
                jwks.Keys.Add(jwk);
            }

            return Results.Json(jwks, new JsonSerializerOptions
            {
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase
            });
        })
        .AllowAnonymous()
        .WithName("GetJwks");
    }
}
```

## Storage Guidelines

### Client-Side Storage

| Storage | Use For | Security |
|---------|---------|----------|
| Memory (variable) | Access tokens | ✅ Best - cleared on tab close |
| HttpOnly cookie | Refresh tokens | ✅ Good - XSS protected |
| localStorage | Never for tokens | ❌ XSS vulnerable |
| sessionStorage | Access tokens (if needed) | ⚠️ XSS vulnerable |

### Secure Token Storage Pattern

```javascript
// In-memory storage for access token (SPA)
let accessToken = null;

async function getAccessToken() {
    if (accessToken && !isExpired(accessToken)) {
        return accessToken;
    }

    // Refresh token is in HttpOnly cookie, sent automatically
    const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include'  // Include cookies
    });

    if (response.ok) {
        const data = await response.json();
        accessToken = data.access_token;
        return accessToken;
    }

    // Refresh failed - user needs to re-authenticate
    throw new AuthError('Session expired');
}
```

## Common Vulnerabilities

### 1. Sensitive Data in Payload

```csharp
// WRONG: Sensitive data in JWT
var claims = new List<Claim>
{
    new(JwtRegisteredClaimNames.Sub, userId),
    new(JwtRegisteredClaimNames.Email, "user@example.com"),
    new("ssn", "123-45-6789"),      // NEVER do this!
    new("credit_card", "4111...")   // NEVER do this!
};

// CORRECT: Only identifiers, look up sensitive data server-side
var claims = new List<Claim>
{
    new(JwtRegisteredClaimNames.Sub, userId),
    new("scope", "read write")
};
```

### 2. Missing Expiration

```csharp
// WRONG: No expiration
var token = new JwtSecurityToken(
    claims: new[] { new Claim(JwtRegisteredClaimNames.Sub, userId) }
    // Missing expires parameter!
);

// CORRECT: Always set expiration
var token = new JwtSecurityToken(
    issuer: issuer,
    audience: audience,
    claims: new[] { new Claim(JwtRegisteredClaimNames.Sub, userId) },
    expires: DateTime.UtcNow.AddMinutes(15),  // Always set!
    signingCredentials: credentials
);
```

### 3. Weak Secret Keys

```csharp
// WRONG: Weak/predictable secret
var secret = "secret";
var secret = "password123";
var secret = Environment.GetEnvironmentVariable("JWT_SECRET") ?? "default";  // Default fallback!

// CORRECT: Strong, random secret (for HMAC - 256 bits minimum)
var secretBytes = RandomNumberGenerator.GetBytes(32);  // 256 bits
var secret = new SymmetricSecurityKey(secretBytes);

// Even better: Load from secure configuration (Azure Key Vault, etc.)
var secretFromVault = await keyVaultClient.GetSecretAsync("jwt-secret");
```

## Security Checklist

- [ ] Use asymmetric algorithms (RS256, ES256) for distributed systems
- [ ] Explicitly specify allowed algorithms in verification
- [ ] Validate all required claims (iss, sub, aud, exp)
- [ ] Keep access tokens short-lived (5-15 minutes)
- [ ] Implement refresh token rotation
- [ ] Store access tokens in memory only
- [ ] Store refresh tokens in HttpOnly cookies
- [ ] Implement token revocation mechanism
- [ ] Never store sensitive data in JWT payload
- [ ] Implement key rotation
- [ ] Serve public keys via JWKS endpoint
- [ ] Use strong secrets (256+ bits for HMAC)
