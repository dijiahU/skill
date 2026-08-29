# OAuth 2.0 and OpenID Connect Flows

This reference provides detailed implementation guidance for OAuth 2.0 and OIDC flows.

## Flow Selection Guide

| Client Type | Recommended Flow | Notes |
|-------------|-----------------|-------|
| SPA (JavaScript) | Authorization Code + PKCE | No client secret |
| Mobile App | Authorization Code + PKCE | Deep linking for redirect |
| Traditional Web App | Authorization Code + PKCE | Can use client secret |
| Service/Backend | Client Credentials | No user interaction |
| CLI/Smart TV | Device Authorization | User authenticates on separate device |
| First-party Mobile | Authorization Code + PKCE | Same as third-party |

## Authorization Code Flow with PKCE

PKCE (Proof Key for Code Exchange) prevents authorization code interception attacks.

### Step 1: Generate PKCE Values

```javascript
// Generate code verifier (43-128 characters)
function generateCodeVerifier() {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    return base64URLEncode(array);
}

// Generate code challenge from verifier
async function generateCodeChallenge(verifier) {
    const encoder = new TextEncoder();
    const data = encoder.encode(verifier);
    const hash = await crypto.subtle.digest('SHA-256', data);
    return base64URLEncode(new Uint8Array(hash));
}

function base64URLEncode(buffer) {
    return btoa(String.fromCharCode(...buffer))
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=/g, '');
}
```

### Step 2: Authorization Request

```javascript
const codeVerifier = generateCodeVerifier();
const codeChallenge = await generateCodeChallenge(codeVerifier);
const state = generateRandomString(32);  // CSRF protection

// Store these securely
sessionStorage.setItem('code_verifier', codeVerifier);
sessionStorage.setItem('oauth_state', state);

const params = new URLSearchParams({
    response_type: 'code',
    client_id: 'your-client-id',
    redirect_uri: 'https://app.example.com/callback',
    scope: 'openid profile email',
    state: state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
    // OIDC-specific
    nonce: generateRandomString(32),  // Replay protection
});

window.location.href = `https://auth.example.com/authorize?${params}`;
```

### Step 3: Handle Callback

```javascript
async function handleCallback() {
    const params = new URLSearchParams(window.location.search);

    // Validate state (CSRF protection)
    const state = params.get('state');
    const storedState = sessionStorage.getItem('oauth_state');
    if (state !== storedState) {
        throw new Error('Invalid state - possible CSRF attack');
    }

    // Check for errors
    if (params.has('error')) {
        throw new Error(`OAuth error: ${params.get('error_description')}`);
    }

    // Exchange code for tokens
    const code = params.get('code');
    const codeVerifier = sessionStorage.getItem('code_verifier');

    const tokenResponse = await fetch('https://auth.example.com/token', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            grant_type: 'authorization_code',
            code: code,
            redirect_uri: 'https://app.example.com/callback',
            client_id: 'your-client-id',
            code_verifier: codeVerifier,
        }),
    });

    const tokens = await tokenResponse.json();

    // Validate ID token if using OIDC
    if (tokens.id_token) {
        validateIdToken(tokens.id_token);
    }

    // Clean up
    sessionStorage.removeItem('code_verifier');
    sessionStorage.removeItem('oauth_state');

    return tokens;
}
```

### Step 4: Token Validation (OIDC)

```javascript
async function validateIdToken(idToken) {
    // Decode without verification first to get header
    const [headerB64, payloadB64, signature] = idToken.split('.');
    const header = JSON.parse(atob(headerB64));
    const payload = JSON.parse(atob(payloadB64));

    // Fetch JWKS from authorization server
    const jwks = await fetch('https://auth.example.com/.well-known/jwks.json')
        .then(r => r.json());

    // Find matching key
    const key = jwks.keys.find(k => k.kid === header.kid);
    if (!key) {
        throw new Error('No matching key found');
    }

    // Verify signature using Web Crypto API or library
    // ... signature verification code ...

    // Validate claims
    const now = Math.floor(Date.now() / 1000);

    if (payload.iss !== 'https://auth.example.com') {
        throw new Error('Invalid issuer');
    }
    if (payload.aud !== 'your-client-id') {
        throw new Error('Invalid audience');
    }
    if (payload.exp < now) {
        throw new Error('Token expired');
    }
    if (payload.iat > now + 60) {  // Allow 60s clock skew
        throw new Error('Token issued in future');
    }
    // Validate nonce matches what was sent
    if (payload.nonce !== sessionStorage.getItem('oauth_nonce')) {
        throw new Error('Invalid nonce - possible replay attack');
    }

    return payload;
}
```

## Client Credentials Flow

For service-to-service authentication (no user involvement).

```csharp
using System.Net.Http.Headers;
using System.Text.Json;

/// <summary>
/// Service-to-service authentication using Client Credentials flow.
/// </summary>
public sealed class ServiceAuthClient : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly string _clientId;
    private readonly string _clientSecret;
    private readonly string _tokenEndpoint;
    private string? _cachedToken;
    private DateTime _tokenExpiry;

    public ServiceAuthClient(
        IHttpClientFactory httpClientFactory,
        string clientId,
        string clientSecret,
        string tokenEndpoint = "https://auth.example.com/token")
    {
        _httpClient = httpClientFactory.CreateClient();
        _clientId = clientId;
        _clientSecret = clientSecret;
        _tokenEndpoint = tokenEndpoint;
    }

    /// <summary>
    /// Get access token with automatic caching and refresh.
    /// </summary>
    public async Task<string> GetTokenAsync(CancellationToken cancellationToken = default)
    {
        // Return cached token if still valid (with 60s buffer)
        if (_cachedToken is not null && DateTime.UtcNow < _tokenExpiry.AddSeconds(-60))
        {
            return _cachedToken;
        }

        // Request new token using Basic auth
        var credentials = Convert.ToBase64String(
            System.Text.Encoding.UTF8.GetBytes($"{_clientId}:{_clientSecret}"));

        using var request = new HttpRequestMessage(HttpMethod.Post, _tokenEndpoint);
        request.Headers.Authorization = new AuthenticationHeaderValue("Basic", credentials);
        request.Content = new FormUrlEncodedContent(new Dictionary<string, string>
        {
            ["grant_type"] = "client_credentials",
            ["scope"] = "api:read api:write"
        });

        var response = await _httpClient.SendAsync(request, cancellationToken);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadFromJsonAsync<TokenResponse>(cancellationToken: cancellationToken);

        _cachedToken = json!.AccessToken;
        _tokenExpiry = DateTime.UtcNow.AddSeconds(json.ExpiresIn);

        return _cachedToken;
    }

    public void Dispose() => _httpClient.Dispose();

    private sealed record TokenResponse(
        [property: JsonPropertyName("access_token")] string AccessToken,
        [property: JsonPropertyName("expires_in")] int ExpiresIn);
}
```

## Device Authorization Flow

For devices without browsers (Smart TVs, CLI tools, game consoles).

```csharp
using System.Text.Json.Serialization;

/// <summary>
/// Device Authorization flow for devices without browsers (Smart TVs, CLI tools, game consoles).
/// </summary>
public sealed class DeviceAuthorizationFlow(HttpClient httpClient, string clientId)
{
    private const string DeviceCodeEndpoint = "https://auth.example.com/device/code";
    private const string TokenEndpoint = "https://auth.example.com/token";

    /// <summary>
    /// Execute interactive device authorization flow.
    /// </summary>
    public async Task<TokenResponse> AuthorizeAsync(
        Action<DeviceCodeInfo> displayInstructions,
        CancellationToken cancellationToken = default)
    {
        // Step 1: Request device and user codes
        var deviceCodeResponse = await httpClient.PostAsync(DeviceCodeEndpoint,
            new FormUrlEncodedContent(new Dictionary<string, string>
            {
                ["client_id"] = clientId,
                ["scope"] = "openid profile"
            }), cancellationToken);

        deviceCodeResponse.EnsureSuccessStatusCode();
        var deviceCode = await deviceCodeResponse.Content.ReadFromJsonAsync<DeviceCodeResponse>(
            cancellationToken: cancellationToken);

        // Step 2: Display instructions to user (via callback)
        displayInstructions(new DeviceCodeInfo(
            deviceCode!.UserCode,
            deviceCode.VerificationUri,
            deviceCode.VerificationUriComplete));

        // Step 3: Poll for token
        var interval = TimeSpan.FromSeconds(deviceCode.Interval ?? 5);

        while (!cancellationToken.IsCancellationRequested)
        {
            await Task.Delay(interval, cancellationToken);

            var tokenResponse = await httpClient.PostAsync(TokenEndpoint,
                new FormUrlEncodedContent(new Dictionary<string, string>
                {
                    ["grant_type"] = "urn:ietf:params:oauth:grant-type:device_code",
                    ["device_code"] = deviceCode.DeviceCode,
                    ["client_id"] = clientId
                }), cancellationToken);

            if (tokenResponse.IsSuccessStatusCode)
            {
                return (await tokenResponse.Content.ReadFromJsonAsync<TokenResponse>(
                    cancellationToken: cancellationToken))!;
            }

            var error = await tokenResponse.Content.ReadFromJsonAsync<ErrorResponse>(
                cancellationToken: cancellationToken);

            switch (error?.Error)
            {
                case "authorization_pending":
                    continue;  // Keep polling
                case "slow_down":
                    interval += TimeSpan.FromSeconds(5);
                    break;
                case "expired_token":
                    throw new InvalidOperationException("Device code expired - restart flow");
                case "access_denied":
                    throw new UnauthorizedAccessException("User denied authorization");
                default:
                    throw new InvalidOperationException($"OAuth error: {error?.Error}");
            }
        }

        throw new OperationCanceledException();
    }

    public sealed record DeviceCodeInfo(string UserCode, string VerificationUri, string? VerificationUriComplete);

    private sealed record DeviceCodeResponse(
        [property: JsonPropertyName("device_code")] string DeviceCode,
        [property: JsonPropertyName("user_code")] string UserCode,
        [property: JsonPropertyName("verification_uri")] string VerificationUri,
        [property: JsonPropertyName("verification_uri_complete")] string? VerificationUriComplete,
        [property: JsonPropertyName("interval")] int? Interval);

    private sealed record ErrorResponse([property: JsonPropertyName("error")] string? Error);

    public sealed record TokenResponse(
        [property: JsonPropertyName("access_token")] string AccessToken,
        [property: JsonPropertyName("refresh_token")] string? RefreshToken,
        [property: JsonPropertyName("expires_in")] int ExpiresIn);
}
```

## Refresh Token Flow

```csharp
/// <summary>
/// Exchange refresh token for new access token.
/// </summary>
public sealed class TokenRefreshClient(HttpClient httpClient, string clientId, string? clientSecret = null)
{
    public async Task<TokenResponse> RefreshAccessTokenAsync(
        string refreshToken,
        CancellationToken cancellationToken = default)
    {
        var formData = new Dictionary<string, string>
        {
            ["grant_type"] = "refresh_token",
            ["refresh_token"] = refreshToken,
            ["client_id"] = clientId
        };

        // Include client_secret if confidential client
        if (!string.IsNullOrEmpty(clientSecret))
        {
            formData["client_secret"] = clientSecret;
        }

        var response = await httpClient.PostAsync(
            "https://auth.example.com/token",
            new FormUrlEncodedContent(formData),
            cancellationToken);

        if (response.StatusCode == System.Net.HttpStatusCode.BadRequest)
        {
            var error = await response.Content.ReadFromJsonAsync<ErrorResponse>(
                cancellationToken: cancellationToken);

            if (error?.Error == "invalid_grant")
            {
                // Refresh token expired or revoked
                throw new SessionExpiredException("Please log in again");
            }
        }

        response.EnsureSuccessStatusCode();
        return (await response.Content.ReadFromJsonAsync<TokenResponse>(
            cancellationToken: cancellationToken))!;
    }

    private sealed record ErrorResponse([property: JsonPropertyName("error")] string? Error);

    public sealed record TokenResponse(
        [property: JsonPropertyName("access_token")] string AccessToken,
        [property: JsonPropertyName("refresh_token")] string? RefreshToken,
        [property: JsonPropertyName("expires_in")] int ExpiresIn);
}

public class SessionExpiredException(string message) : Exception(message);
```

## Security Considerations

### Redirect URI Validation

```csharp
using System.Security.Cryptography;

/// <summary>
/// Server-side redirect URI validation.
/// </summary>
public sealed class RedirectUriValidator(IOAuthClientStore clientStore)
{
    /// <summary>
    /// Strict redirect URI validation - exact match only, no wildcards or partial matching.
    /// </summary>
    public async Task<bool> ValidateRedirectUriAsync(string redirectUri, string clientId)
    {
        var client = await clientStore.GetClientAsync(clientId);
        if (client is null) return false;

        // Must be exact match - no wildcards or partial matching
        return client.AllowedRedirectUris.Contains(redirectUri, StringComparer.Ordinal);
    }
}

public interface IOAuthClientStore
{
    Task<OAuthClient?> GetClientAsync(string clientId);
}

public sealed record OAuthClient(
    string ClientId,
    IReadOnlyList<string> AllowedRedirectUris);
```

### State Parameter

```csharp
using System.Security.Cryptography;

/// <summary>
/// CSRF protection via state parameter.
/// </summary>
public static class OAuthStateGenerator
{
    /// <summary>
    /// Generate cryptographically secure state parameter.
    /// </summary>
    public static string GenerateState(string sessionId)
    {
        var randomBytes = RandomNumberGenerator.GetBytes(32);
        // Optionally bind to session for additional security
        var combined = System.Text.Encoding.UTF8.GetBytes(
            Convert.ToHexString(randomBytes) + sessionId);
        var hash = SHA256.HashData(combined);
        return Convert.ToHexString(hash);
    }

    /// <summary>
    /// Constant-time state comparison to prevent timing attacks.
    /// </summary>
    public static bool ValidateState(string state, string storedState)
    {
        return CryptographicOperations.FixedTimeEquals(
            System.Text.Encoding.UTF8.GetBytes(state),
            System.Text.Encoding.UTF8.GetBytes(storedState));
    }
}
```

### Token Storage and Transmission

```javascript
// SPA: Store access token in memory, refresh token in HttpOnly cookie
class TokenManager {
    constructor() {
        this.accessToken = null;
    }

    setTokens(accessToken) {
        // Access token in memory only
        this.accessToken = accessToken;
        // Refresh token should be set as HttpOnly cookie by server
    }

    async getAccessToken() {
        if (this.accessToken && !this.isExpired(this.accessToken)) {
            return this.accessToken;
        }

        // Refresh using HttpOnly cookie
        const response = await fetch('/api/auth/refresh', {
            method: 'POST',
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Token refresh failed');
        }

        const data = await response.json();
        this.accessToken = data.access_token;
        return this.accessToken;
    }
}
```

## OpenID Connect Specifics

### Discovery Document

```javascript
// Fetch OIDC configuration
const config = await fetch('https://auth.example.com/.well-known/openid-configuration')
    .then(r => r.json());

// config contains:
// - authorization_endpoint

// - token_endpoint
// - userinfo_endpoint
// - jwks_uri
// - supported scopes
// - supported response types
```

### Standard Scopes

| Scope | Claims Returned |
|-------|----------------|
| `openid` | Required for OIDC - returns `sub` |
| `profile` | `name`, `family_name`, `given_name`, `picture`, etc. |

| `email` | `email`, `email_verified` |
| `address` | `address` (structured) |
| `phone` | `phone_number`, `phone_number_verified` |

### UserInfo Endpoint

```javascript
async function getUserInfo(accessToken) {
    const response = await fetch('https://auth.example.com/userinfo', {
        headers: {
            'Authorization': `Bearer ${accessToken}`
        }
    });
    return response.json();
}
```

## Security Checklist

### Authorization Request

- [ ] Use PKCE for all public clients
- [ ] Generate cryptographically random state
- [ ] Generate cryptographically random nonce (OIDC)
- [ ] Use exact redirect_uri matching
- [ ] Request minimum necessary scopes

### Token Exchange

- [ ] Validate state matches stored value
- [ ] Use HTTPS for all token requests
- [ ] Validate code_verifier matches code_challenge
- [ ] Handle errors appropriately

### Token Validation

- [ ] Verify signature using JWKS
- [ ] Validate issuer claim
- [ ] Validate audience claim
- [ ] Check token expiration
- [ ] Validate nonce (OIDC)

### Token Storage

- [ ] Access tokens in memory only (SPAs)
- [ ] Refresh tokens in HttpOnly cookies
- [ ] Never store tokens in localStorage
- [ ] Implement token refresh before expiry

### Refresh Flow

- [ ] Implement refresh token rotation
- [ ] Revoke old refresh tokens
- [ ] Handle refresh failures gracefully
- [ ] Clear all tokens on logout
