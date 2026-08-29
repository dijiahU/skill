# Passkeys Implementation Guide

This reference provides comprehensive guidance for implementing Passkeys (WebAuthn/FIDO2) authentication.

## Overview

Passkeys use public key cryptography for phishing-resistant, passwordless authentication:

- **Private key**: Stored securely on user's device (never leaves device)
- **Public key**: Stored on your server
- **Authentication**: Device signs challenge with private key, server verifies with public key

## Benefits

| Feature | Passwords | Passkeys |
|---------|-----------|----------|
| Phishing resistant | ❌ | ✅ |
| No shared secrets | ❌ | ✅ |
| Replay attack protection | ❌ | ✅ |
| User experience | Poor | Excellent |
| Breach impact | High | Minimal |

## Browser Support

```javascript
// Check WebAuthn support
function isWebAuthnSupported() {
    return window.PublicKeyCredential !== undefined;
}

// Check platform authenticator availability (Face ID, Touch ID, Windows Hello)
async function isPlatformAuthenticatorAvailable() {
    if (!isWebAuthnSupported()) return false;
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
}

// Check conditional UI support (autofill)
async function isConditionalUIAvailable() {
    if (!isWebAuthnSupported()) return false;
    return await PublicKeyCredential.isConditionalMediationAvailable?.() ?? false;
}
```

## Registration Flow

### Server: Generate Registration Options

```csharp
using System.Security.Cryptography;
using Fido2NetLib;
using Fido2NetLib.Objects;

/// <summary>
/// WebAuthn/Passkeys registration options generator.
/// </summary>
public sealed class PasskeyRegistrationService(
    IFido2 fido2,
    IChallengeStore challengeStore,
    IPasskeyStore passkeyStore)
{
    /// <summary>
    /// Generate WebAuthn registration options for a user.
    /// </summary>
    public async Task<CredentialCreateOptions> GenerateRegistrationOptionsAsync(User user)
    {
        // Get existing credentials to exclude (prevent duplicate registration)
        var existingCredentials = await passkeyStore.GetCredentialsForUserAsync(user.Id);
        var excludeCredentials = existingCredentials
            .Select(c => new PublicKeyCredentialDescriptor(c.CredentialId))
            .ToList();

        var fido2User = new Fido2User
        {
            Id = System.Text.Encoding.UTF8.GetBytes(user.Id),
            Name = user.Email,
            DisplayName = user.DisplayName
        };

        var authenticatorSelection = new AuthenticatorSelection
        {
            // "platform" = device built-in (Face ID, Windows Hello)
            // "cross-platform" = security keys
            // null = allow both
            AuthenticatorAttachment = AuthenticatorAttachment.Platform,
            // Require discoverable credential (for username-less login)
            ResidentKey = ResidentKeyRequirement.Required,
            // Require user verification (biometric/PIN)
            UserVerification = UserVerificationRequirement.Required
        };

        var options = fido2.RequestNewCredential(
            fido2User,
            excludeCredentials,
            authenticatorSelection,
            AttestationConveyancePreference.None,
            new AuthenticationExtensionsClientInputs());

        // Store challenge for verification (expires in 5 minutes)
        await challengeStore.StoreAsync(user.Id, options.Challenge, TimeSpan.FromMinutes(5));

        return options;
    }
}
```

### Client: Create Credential

```javascript
async function registerPasskey() {
    // 1. Get options from server
    const optionsResponse = await fetch('/api/webauthn/register/options', {
        method: 'POST',
        credentials: 'include',
    });
    const options = await optionsResponse.json();

    // 2. Convert base64url strings to ArrayBuffers
    const publicKeyOptions = {
        challenge: base64URLToBuffer(options.challenge),
        rp: options.rp,
        user: {
            id: base64URLToBuffer(options.user.id),
            name: options.user.name,
            displayName: options.user.displayName,
        },
        pubKeyCredParams: options.pubKeyCredParams,
        authenticatorSelection: options.authenticatorSelection,
        excludeCredentials: options.excludeCredentials?.map(cred => ({
            type: cred.type,
            id: base64URLToBuffer(cred.id),
        })),
        timeout: options.timeout,
    };

    // 3. Create credential (triggers biometric prompt)
    let credential;
    try {
        credential = await navigator.credentials.create({
            publicKey: publicKeyOptions,
        });
    } catch (error) {
        if (error.name === 'InvalidStateError') {
            throw new Error('Passkey already registered for this device');
        }
        if (error.name === 'NotAllowedError') {
            throw new Error('User cancelled or timed out');
        }
        throw error;
    }

    // 4. Send credential to server
    const verifyResponse = await fetch('/api/webauthn/register/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
            id: credential.id,
            rawId: bufferToBase64URL(credential.rawId),
            type: credential.type,
            response: {
                clientDataJSON: bufferToBase64URL(credential.response.clientDataJSON),
                attestationObject: bufferToBase64URL(credential.response.attestationObject),
            },
        }),
    });

    if (!verifyResponse.ok) {
        const error = await verifyResponse.json();
        throw new Error(error.message);
    }

    return await verifyResponse.json();
}

// Helper functions
function base64URLToBuffer(base64url) {
    const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
    const padding = '='.repeat((4 - base64.length % 4) % 4);
    const binary = atob(base64 + padding);
    return Uint8Array.from(binary, c => c.charCodeAt(0)).buffer;
}

function bufferToBase64URL(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (const byte of bytes) {
        binary += String.fromCharCode(byte);
    }
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}
```

### Server: Verify Registration

```csharp
using Fido2NetLib;

/// <summary>
/// Verify and store new passkey registration.
/// </summary>
public async Task<Passkey> VerifyRegistrationAsync(User user, AuthenticatorAttestationRawResponse attestation)
{
    // Retrieve stored challenge
    var expectedChallenge = await challengeStore.GetAsync(user.Id);
    if (expectedChallenge is null)
        throw new InvalidOperationException("Challenge expired or not found");

    // Verify registration
    var options = CredentialCreateOptions.FromJson(expectedChallenge);

    var result = await fido2.MakeNewCredentialAsync(
        attestation,
        options,
        async (args, ct) =>
        {
            // Check if credential ID already exists (prevent duplicate)
            var existing = await passkeyStore.GetByCredentialIdAsync(args.CredentialId);
            return existing is null;
        });

    if (result.Status != "ok")
        throw new InvalidOperationException($"Registration failed: {result.ErrorMessage}");

    // Store passkey
    var passkey = new Passkey
    {
        UserId = user.Id,
        CredentialId = result.Result!.Id,
        PublicKey = result.Result.PublicKey,
        SignCount = result.Result.SignCount,
        DeviceType = result.Result.AttestationType,
        CreatedAt = DateTime.UtcNow
    };

    await passkeyStore.AddAsync(passkey);

    // Clear challenge
    await challengeStore.DeleteAsync(user.Id);

    return passkey;
}

public sealed record Passkey
{
    public required string UserId { get; init; }
    public required byte[] CredentialId { get; init; }
    public required byte[] PublicKey { get; init; }
    public uint SignCount { get; set; }
    public string? DeviceType { get; init; }
    public DateTime CreatedAt { get; init; }
    public DateTime? LastUsedAt { get; set; }
    public string? Name { get; set; }  // User-assigned name
}
```

## Authentication Flow

### Server: Generate Authentication Options

```csharp
/// <summary>
/// Generate WebAuthn authentication options.
/// </summary>
public async Task<AssertionOptions> GenerateAuthenticationOptionsAsync(string? userId = null)
{
    var allowCredentials = new List<PublicKeyCredentialDescriptor>();

    if (userId is not null)
    {
        // If user_id provided, only allow their credentials
        var userPasskeys = await passkeyStore.GetCredentialsForUserAsync(userId);
        allowCredentials = userPasskeys
            .Select(p => new PublicKeyCredentialDescriptor(p.CredentialId))
            .ToList();
    }
    // else: Discoverable credential flow (username-less) - empty list allows any

    var options = fido2.GetAssertionOptions(
        allowCredentials,
        UserVerificationRequirement.Required,
        new AuthenticationExtensionsClientInputs());

    // Store challenge for verification
    var challengeKey = userId ?? "anonymous";
    await challengeStore.StoreAsync(challengeKey, options.ToJson(), TimeSpan.FromMinutes(5));

    return options;
}
```

### Client: Get Credential

```javascript
async function authenticateWithPasskey(username = null) {
    // 1. Get options from server
    const optionsResponse = await fetch('/api/webauthn/authenticate/options', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username }),
    });
    const options = await optionsResponse.json();

    // 2. Build credential request options
    const publicKeyOptions = {
        challenge: base64URLToBuffer(options.challenge),
        rpId: options.rpId,
        userVerification: options.userVerification,
        timeout: options.timeout,
    };

    // Include allowCredentials if specified (non-discoverable flow)
    if (options.allowCredentials?.length > 0) {
        publicKeyOptions.allowCredentials = options.allowCredentials.map(cred => ({
            type: cred.type,
            id: base64URLToBuffer(cred.id),
        }));
    }

    // 3. Get credential (triggers biometric prompt)
    let credential;
    try {
        credential = await navigator.credentials.get({
            publicKey: publicKeyOptions,
        });
    } catch (error) {
        if (error.name === 'NotAllowedError') {
            throw new Error('User cancelled or timed out');
        }
        throw error;
    }

    // 4. Send to server for verification
    const verifyResponse = await fetch('/api/webauthn/authenticate/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            id: credential.id,
            rawId: bufferToBase64URL(credential.rawId),
            type: credential.type,
            response: {
                clientDataJSON: bufferToBase64URL(credential.response.clientDataJSON),
                authenticatorData: bufferToBase64URL(credential.response.authenticatorData),
                signature: bufferToBase64URL(credential.response.signature),
                userHandle: credential.response.userHandle
                    ? bufferToBase64URL(credential.response.userHandle)
                    : null,
            },
        }),
    });

    if (!verifyResponse.ok) {
        throw new Error('Authentication failed');
    }

    return await verifyResponse.json();
}
```

### Server: Verify Authentication

```csharp
/// <summary>
/// Verify passkey authentication and return authenticated user.
/// </summary>
public async Task<User> VerifyAuthenticationAsync(AuthenticatorAssertionRawResponse assertion)
{
    // Find passkey by credential ID
    var passkey = await passkeyStore.GetByCredentialIdAsync(assertion.Id);
    if (passkey is null)
        throw new InvalidOperationException("Unknown credential");

    // Get stored challenge
    string challengeKey;
    if (assertion.Response.UserHandle is { Length: > 0 })
    {
        // Discoverable credential - user identified by userHandle
        challengeKey = System.Text.Encoding.UTF8.GetString(assertion.Response.UserHandle);
    }
    else
    {
        challengeKey = passkey.UserId;
    }

    var storedOptions = await challengeStore.GetAsync(challengeKey)
        ?? await challengeStore.GetAsync("anonymous");

    if (storedOptions is null)
        throw new InvalidOperationException("Challenge expired");

    var options = AssertionOptions.FromJson(storedOptions);

    // Verify authentication
    var result = await fido2.MakeAssertionAsync(
        assertion,
        options,
        passkey.PublicKey,
        passkey.SignCount,
        async (args, ct) =>
        {
            // Verify credential belongs to expected user
            var cred = await passkeyStore.GetByCredentialIdAsync(args.CredentialId);
            return cred?.UserId == passkey.UserId;
        });

    if (result.Status != "ok")
        throw new InvalidOperationException($"Authentication failed: {result.ErrorMessage}");

    // Update sign count (replay protection)
    if (result.SignCount > passkey.SignCount)
    {
        passkey.SignCount = result.SignCount;
        passkey.LastUsedAt = DateTime.UtcNow;
        await passkeyStore.UpdateAsync(passkey);
    }
    else if (result.SignCount > 0)
    {
        // Sign count didn't increase - possible cloned authenticator
        await securityLogger.LogEventAsync("sign_count_not_increased", passkey.CredentialId);
    }

    // Clear challenge
    await challengeStore.DeleteAsync(challengeKey);

    return await userService.GetByIdAsync(passkey.UserId);
}
```

## Conditional UI (Autofill)

Allow passkey authentication via the browser's autofill dropdown:

```javascript
// Initialize conditional UI on page load
async function initConditionalUI() {
    if (!await isConditionalUIAvailable()) {
        return;
    }

    // Get options (no specific user - discoverable credentials only)
    const options = await fetch('/api/webauthn/authenticate/options', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    }).then(r => r.json());

    try {
        // This will show passkeys in the autofill dropdown
        const credential = await navigator.credentials.get({
            publicKey: {
                challenge: base64URLToBuffer(options.challenge),
                rpId: options.rpId,
                userVerification: options.userVerification,
                timeout: options.timeout,
            },
            mediation: 'conditional',  // Key for autofill integration
        });

        // User selected a passkey from autofill
        await verifyAndLogin(credential);
    } catch (error) {
        // User didn't select a passkey, they might type password instead
        console.log('Conditional UI cancelled or not used');
    }
}

// HTML: Add autocomplete="webauthn" to trigger passkey autofill
// <input type="text" name="username" autocomplete="username webauthn">
```

## Cross-Device Authentication

Allow users to authenticate with a passkey from another device:

```javascript
async function authenticateWithCrossDevice() {
    const options = await getAuthenticationOptions();

    const credential = await navigator.credentials.get({
        publicKey: {
            challenge: base64URLToBuffer(options.challenge),
            rpId: options.rpId,
            userVerification: options.userVerification,
            // Don't restrict to specific credentials - allow any
            allowCredentials: [],
            timeout: 120000,  // Longer timeout for cross-device
        },
    });

    // Credential might be from a phone using QR code
    return await verifyAndLogin(credential);
}
```

## Passkey Management UI

```csharp
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

/// <summary>
/// Passkey management API endpoints.
/// </summary>
[Authorize]
[ApiController]
[Route("api/passkeys")]
public sealed class PasskeysController(IPasskeyStore passkeyStore, IUserService userService) : ControllerBase
{
    /// <summary>
    /// List user's registered passkeys.
    /// </summary>
    [HttpGet]
    public async Task<IActionResult> ListPasskeys()
    {
        var userId = User.FindFirstValue(ClaimTypes.NameIdentifier)!;
        var passkeys = await passkeyStore.GetCredentialsForUserAsync(userId);

        var result = passkeys.Select(p => new
        {
            Id = Convert.ToBase64String(p.CredentialId),
            CreatedAt = p.CreatedAt,
            LastUsedAt = p.LastUsedAt,
            DeviceType = p.DeviceType,
            Name = p.Name  // User-assigned name
        });

        return Ok(result);
    }

    /// <summary>
    /// Delete a passkey (require re-authentication first).
    /// </summary>
    [HttpDelete("{passkeyId}")]
    public async Task<IActionResult> DeletePasskey(string passkeyId)
    {
        var userId = User.FindFirstValue(ClaimTypes.NameIdentifier)!;
        var credentialId = Convert.FromBase64String(passkeyId);

        var passkey = await passkeyStore.GetByCredentialIdAsync(credentialId);
        if (passkey is null || passkey.UserId != userId)
            return NotFound();

        // Ensure user has at least one other authentication method
        var allPasskeys = await passkeyStore.GetCredentialsForUserAsync(userId);
        var user = await userService.GetByIdAsync(userId);

        if (allPasskeys.Count == 1 && !user.HasPassword)
            return BadRequest("Cannot delete last passkey without password set");

        await passkeyStore.DeleteAsync(credentialId);
        return Ok(new { Success = true });
    }
}
```

## Security Considerations

### Sign Count Verification

```csharp
/// <summary>
/// Verify sign count to detect cloned authenticators.
/// </summary>
public sealed class SignCountVerifier(ISecurityLogger securityLogger)
{
    public async Task<bool> VerifySignCountAsync(Passkey passkey, uint newSignCount)
    {
        if (newSignCount == 0)
        {
            // Some authenticators don't track sign count
            return true;
        }

        if (newSignCount > passkey.SignCount)
        {
            return true;
        }

        // Sign count went backwards or stayed same - possible clone
        await securityLogger.LogEventAsync(new SecurityEvent
        {
            EventType = "possible_cloned_authenticator",
            UserId = passkey.UserId,
            PasskeyId = Convert.ToBase64String(passkey.CredentialId),
            Details = new Dictionary<string, object>
            {
                ["expected_count"] = passkey.SignCount,
                ["received_count"] = newSignCount
            }
        });

        return false;  // Consider failing or requiring additional verification
    }
}
```

### Origin Validation

```csharp
/// <summary>
/// Strict origin validation - no wildcards.
/// </summary>
public sealed class OriginValidator
{
    private static readonly HashSet<string> AllowedOrigins = new(StringComparer.Ordinal)
    {
        "https://example.com",
        "https://www.example.com"
    };

    public static bool ValidateOrigin(string origin)
    {
        return AllowedOrigins.Contains(origin);
    }
}
```

## Security Checklist

- [ ] Use HTTPS only
- [ ] Generate cryptographically random challenges
- [ ] Store challenges server-side with short TTL
- [ ] Validate RP ID matches your domain
- [ ] Validate origin strictly (no wildcards)
- [ ] Require user verification
- [ ] Check and update sign count
- [ ] Implement credential management UI
- [ ] Log security-relevant events
- [ ] Have fallback authentication method
- [ ] Support cross-device authentication
- [ ] Consider conditional UI for best UX
