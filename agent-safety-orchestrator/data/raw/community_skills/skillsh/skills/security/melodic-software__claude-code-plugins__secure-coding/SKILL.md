---
name: secure-coding
description: Provides guidance on secure coding practices including OWASP Top 10 2025, CWE Top 25, input validation, output encoding, and language-specific security patterns. Use when reviewing code for security vulnerabilities, implementing security controls, or learning secure development practices.
allowed-tools: Read, Glob, Grep, Task
---

# Secure Coding

Comprehensive guidance for writing secure code, covering OWASP Top 10 2025, CWE Top 25, and language-specific security patterns.

## When to Use This Skill

Use this skill when:

- Reviewing code for security vulnerabilities
- Implementing input validation or output encoding
- Learning about common security weaknesses (OWASP, CWE)
- Fixing identified security issues
- Writing security-sensitive code (authentication, authorization, data handling)
- Conducting security code reviews

## OWASP Top 10 2025 Quick Reference

| Rank | Vulnerability | Key Mitigation |
|------|--------------|----------------|
| A01 | Broken Access Control | Server-side access checks, deny by default, CORS restrictions |
| A02 | Security Misconfiguration | Hardened configs, remove defaults, disable unnecessary features |
| A03 | Software Supply Chain Failures | SCA, SBOM, verify dependencies, integrity checks |
| A04 | Cryptographic Failures | Strong encryption (AES-256), TLS 1.2+, no deprecated algorithms |
| A05 | Injection | Parameterized queries, input validation, context-aware encoding |
| A06 | Insecure Design | Threat modeling, secure design patterns, defense in depth |
| A07 | Authentication Failures | MFA, strong passwords, secure session management |
| A08 | Data Integrity Failures | Digital signatures, integrity verification, secure CI/CD |
| A09 | Logging & Alerting Failures | Centralized logging, anomaly detection, audit trails |
| A10 | Mishandling Exceptions | Fail securely, generic error messages, complete exception handling |

**For detailed mitigations:** See [OWASP Top 10 2025 Reference](references/owasp-top-10-2025.md)

## Core Secure Coding Principles

### 1. Input Validation

**Never trust user input.** Validate all inputs on the server side.

```csharp
using System.Text.RegularExpressions;

// Good: Server-side validation with allowlist
public static partial class InputValidation
{
    [GeneratedRegex(@"^[a-zA-Z0-9_]{3,20}$")]
    private static partial Regex UsernamePattern();

    /// <summary>
    /// Validate username against allowlist pattern.
    /// </summary>
    public static bool ValidateUsername(string username) =>
        !string.IsNullOrEmpty(username) && UsernamePattern().IsMatch(username);
}

// Bad: No validation
public string ProcessUsername(string username) => username;  // Dangerous!
```

**Validation strategies:**

- **Allowlist validation**: Define what IS allowed (preferred)
- **Blocklist validation**: Define what is NOT allowed (less secure)
- **Type checking**: Ensure correct data types
- **Range checking**: Verify values within expected bounds
- **Length limits**: Prevent buffer overflows and DoS

### 2. Output Encoding

Encode output based on context to prevent injection attacks.

| Context | Encoding Method | Example |
|---------|----------------|---------|
| HTML body | HTML entity encoding | `&lt;script&gt;` |
| HTML attributes | Attribute encoding | `&#x27;` for `'` |
| JavaScript | JavaScript encoding | `\x3Cscript\x3E` |
| URL parameters | URL encoding | `%3Cscript%3E` |
| CSS | CSS encoding | `\3C script\3E` |
| SQL | Parameterized queries | Use prepared statements |

### 3. Parameterized Queries (Injection Prevention)

**Always use parameterized queries for database operations.**

```csharp
// Good: Parameterized query with SqlCommand
using var cmd = new SqlCommand(
    "SELECT * FROM Users WHERE Username = @username AND Status = @status",
    connection);
cmd.Parameters.AddWithValue("@username", username);
cmd.Parameters.AddWithValue("@status", status);

// Good: Parameterized query with Dapper
var users = await connection.QueryAsync<User>(
    "SELECT * FROM Users WHERE Username = @Username AND Status = @Status",
    new { Username = username, Status = status });

// Bad: String interpolation (SQL Injection vulnerable)
var query = $"SELECT * FROM Users WHERE Username = '{username}'";  // VULNERABLE
```

### 4. Authentication Security

- **Use strong password hashing**: Argon2id, bcrypt, scrypt (see `cryptography` skill)
- **Implement MFA**: Time-based OTP, hardware keys, passkeys
- **Secure session management**: HttpOnly cookies, secure flag, short expiration
- **Account lockout**: Prevent brute force attacks
- **Credential storage**: Never store plaintext passwords

### 5. Authorization Security

- **Deny by default**: Require explicit permission grants
- **Server-side checks**: Never rely on client-side authorization
- **Verify object ownership**: Check user can access requested resource
- **Use indirect references**: Map internal IDs to user-specific references
- **Implement RBAC/ABAC**: Use structured access control models

### 6. Error Handling

```csharp
// Good: Generic error message to user, detailed logging
public async Task<IActionResult> ProcessData([FromBody] DataRequest request)
{
    try
    {
        await _dataService.ProcessSensitiveDataAsync(request.Data);
        return Ok();
    }
    catch (DbException ex)
    {
        _logger.LogError(ex, "Database error processing request for user {UserId}", User.GetUserId());
        return StatusCode(500, new { error = "An error occurred" });
    }
}

// Bad: Exposing internal details
catch (DbException ex)
{
    return StatusCode(500, new { error = ex.Message });  // VULNERABLE - exposes internals
}
```

**Error handling rules:**

- Return generic error messages to users
- Log detailed errors server-side
- Never expose stack traces, database errors, or internal paths
- Fail securely (deny access on error)

## Language-Specific Patterns

### JavaScript/TypeScript

```typescript
// XSS Prevention - use textContent, not innerHTML
element.textContent = userInput;  // Safe
element.innerHTML = userInput;    // VULNERABLE

// Use DOMPurify for HTML that must be rendered
import DOMPurify from 'dompurify';
element.innerHTML = DOMPurify.sanitize(userInput);

// Avoid eval() and Function()
eval(userInput);           // VULNERABLE
new Function(userInput)(); // VULNERABLE

// Use strict mode
'use strict';
```

### C# / .NET

```csharp
// Safe process execution - use argument list, avoid shell
using System.Diagnostics;

public static async Task<string> SafeExecuteAsync(string command, params string[] args)
{
    using var process = new Process
    {
        StartInfo = new ProcessStartInfo
        {
            FileName = command,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,  // Safe: no shell interpretation
            CreateNoWindow = true
        }
    };

    foreach (var arg in args)
        process.StartInfo.ArgumentList.Add(arg);  // Safe: no shell escaping needed

    process.Start();
    var output = await process.StandardOutput.ReadToEndAsync();
    await process.WaitForExitAsync();
    return output;
}

// Bad: Shell injection vulnerable
Process.Start("cmd", $"/c dir {userInput}");  // VULNERABLE

// Safe file operations - prevent path traversal
public static class SafeFileAccess
{
    /// <summary>
    /// Safely read a file, preventing path traversal attacks.
    /// </summary>
    public static string SafeReadFile(string baseDir, string filename)
    {
        var basePath = Path.GetFullPath(baseDir);
        var filePath = Path.GetFullPath(Path.Combine(baseDir, filename));

        if (!filePath.StartsWith(basePath, StringComparison.OrdinalIgnoreCase))
            throw new UnauthorizedAccessException("Path traversal detected");

        return File.ReadAllText(filePath);
    }
}

// Use parameterized queries with Entity Framework
var users = context.Users
    .Where(u => u.Username == username)  // Safe - parameterized
    .ToList();

// Avoid raw SQL when possible, use parameters if needed
var users = context.Users
    .FromSqlRaw("SELECT * FROM Users WHERE Username = {0}", username)
    .ToList();

// Anti-forgery tokens for CSRF protection
[ValidateAntiForgeryToken]
public IActionResult UpdateProfile(ProfileModel model)
{
    // Process update
}

// Input validation with data annotations
public sealed class UserInput
{
    [Required]
    [StringLength(100, MinimumLength = 3)]
    [RegularExpression(@"^[a-zA-Z0-9_]+$")]
    public required string Username { get; init; }
}
```

## Security Code Review Checklist

### Input Handling

- [ ] All inputs validated on server side
- [ ] Allowlist validation used where possible
- [ ] Length limits enforced
- [ ] Type checking performed
- [ ] File uploads validated (type, size, content)

### Output Encoding

- [ ] Context-appropriate encoding applied
- [ ] No raw user input in HTML/JS/SQL
- [ ] Content-Type headers set correctly
- [ ] X-Content-Type-Options: nosniff

### Authentication

- [ ] Strong password hashing (Argon2id/bcrypt)
- [ ] Session tokens are random and unpredictable
- [ ] Session invalidation on logout
- [ ] Account lockout after failed attempts
- [ ] Credentials transmitted over HTTPS only

### Authorization

- [ ] Access control on every request
- [ ] Deny by default policy
- [ ] Object-level authorization checks
- [ ] No direct object references exposed

### Data Protection

- [ ] Sensitive data encrypted at rest
- [ ] TLS 1.2+ for data in transit
- [ ] No sensitive data in URLs or logs
- [ ] Proper key management

### Error Handling

- [ ] Generic error messages to users
- [ ] Detailed errors logged securely
- [ ] No stack traces exposed
- [ ] Fail securely (deny on error)

## Quick Decision Tree

**What security concern are you addressing?**

1. **SQL/NoSQL injection** → Use parameterized queries, ORMs
2. **XSS (Cross-Site Scripting)** → Context-aware output encoding, CSP
3. **CSRF** → Anti-forgery tokens, SameSite cookies
4. **Authentication** → See `authentication-patterns` skill
5. **Authorization** → See `authorization-models` skill
6. **Cryptography** → See `cryptography` skill
7. **Secrets/Credentials** → See `secrets-management` skill
8. **API Security** → See `api-security` skill

## References

- [OWASP Top 10 2025 Detailed Reference](references/owasp-top-10-2025.md) - Complete mitigations and examples
- [CWE Top 25 Reference](references/cwe-top-25.md) - Most dangerous software weaknesses
- [Language-Specific Patterns](references/language-specific/) - Per-language security guides

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `authentication-patterns` | Auth implementation details (JWT, OAuth, Passkeys) |
| `authorization-models` | Access control (RBAC, ABAC) |
| `cryptography` | Encryption, hashing, TLS |
| `api-security` | API-specific security patterns |
| `secrets-management` | Credential and secret handling |

## Version History

- v1.0.0 (2025-12-26): Initial release with OWASP Top 10 2025, core principles

---

**Last Updated:** 2025-12-26
