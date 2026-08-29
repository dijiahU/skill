# CWE Top 25 Most Dangerous Software Weaknesses

This reference covers the CWE (Common Weakness Enumeration) Top 25 most dangerous software weaknesses with examples and mitigations.

## Overview

The CWE Top 25 represents the most common and impactful security weaknesses. Understanding these helps prioritize security efforts during development and code review.

## Critical Weaknesses (Top 10)

### CWE-787: Out-of-bounds Write

**Description:** Writing data past the boundaries of allocated memory.

**Languages Affected:** C, C++, Assembly

```c
// Vulnerable: Buffer overflow
char buffer[10];
strcpy(buffer, userInput);  // No bounds checking

// Secure: Use bounded functions
char buffer[10];
strncpy(buffer, userInput, sizeof(buffer) - 1);
buffer[sizeof(buffer) - 1] = '\0';
```

**Mitigation:** Use memory-safe languages or bounded memory functions.

---

### CWE-79: Cross-site Scripting (XSS)

**Description:** Improper neutralization of input during web page generation.

**Languages Affected:** All web frameworks

```javascript
// Vulnerable: Direct DOM insertion
element.innerHTML = userInput;

// Secure: Use textContent or sanitization
element.textContent = userInput;
// OR
element.innerHTML = DOMPurify.sanitize(userInput);
```

**Mitigation:**

- Context-aware output encoding
- Content Security Policy (CSP)
- Use frameworks with auto-escaping

---

### CWE-89: SQL Injection

**Description:** Improper neutralization of special elements in SQL commands.

```csharp
// Vulnerable: String interpolation
var query = $"SELECT * FROM users WHERE id = {userId}";  // SQL INJECTION

// Secure: Parameterized query with SqlCommand
using var cmd = new SqlCommand("SELECT * FROM users WHERE id = @id", connection);
cmd.Parameters.AddWithValue("@id", userId);

// Secure: Parameterized query with EF Core
var user = await context.Users.FirstOrDefaultAsync(u => u.Id == userId);
```

**Mitigation:**

- Use parameterized queries
- Use ORMs
- Input validation
- Stored procedures

---

### CWE-416: Use After Free

**Description:** Referencing memory after it has been freed.

**Languages Affected:** C, C++

```c
// Vulnerable
char *ptr = malloc(SIZE);
free(ptr);
strcpy(ptr, "data");  // Use after free

// Secure: Set pointer to NULL after free
free(ptr);
ptr = NULL;
```

**Mitigation:** Use smart pointers (C++), set freed pointers to NULL.

---

### CWE-78: OS Command Injection

**Description:** Improper neutralization of special elements in OS commands.

```csharp
// Vulnerable: Shell command with user input
Process.Start("cmd", $"/c dir {directory}");  // COMMAND INJECTION

// Secure: Use Process with ArgumentList (no shell interpretation)
using var process = new Process
{
    StartInfo = new ProcessStartInfo
    {
        FileName = "ls",  // or "cmd" on Windows
        UseShellExecute = false,
        RedirectStandardOutput = true
    }
};
process.StartInfo.ArgumentList.Add(directory);  // Safe: ArgumentList escapes properly
process.Start();
```

**Mitigation:**

- Avoid shell commands when possible
- Use parameterized APIs
- Strict input validation

---

### CWE-20: Improper Input Validation

**Description:** Not validating or incorrectly validating input.

```csharp
using System.Text.RegularExpressions;

// Vulnerable: No validation
public string GetFile(string filename)
{
    return File.ReadAllText($"/data/{filename}");  // PATH TRAVERSAL
}

// Secure: Validate and sanitize
public partial class FileService
{
    [GeneratedRegex(@"^[a-zA-Z0-9_-]+\.txt$")]
    private static partial Regex SafeFilenameRegex();

    public string GetFile(string filename)
    {
        if (!SafeFilenameRegex().IsMatch(filename))
            throw new ArgumentException("Invalid filename");

        var basePath = Path.GetFullPath("/data");
        var filePath = Path.GetFullPath(Path.Combine("/data", filename));

        if (!filePath.StartsWith(basePath, StringComparison.OrdinalIgnoreCase))
            throw new SecurityException("Path traversal detected");

        return File.ReadAllText(filePath);
    }
}
```

**Mitigation:**

- Validate all inputs server-side
- Use allowlist validation
- Check types, ranges, lengths, and formats

---

### CWE-125: Out-of-bounds Read

**Description:** Reading data from outside allocated memory bounds.

**Languages Affected:** C, C++

```c
// Vulnerable
int array[10];
int value = array[index];  // index not checked

// Secure
if (index >= 0 && index < 10) {
    int value = array[index];
}
```

**Mitigation:** Bounds checking, use safe alternatives.

---

### CWE-22: Path Traversal

**Description:** Improper limitation of pathname to restricted directory.

```csharp
// Vulnerable
[HttpGet("download")]
public IActionResult Download(string filename)
{
    return PhysicalFile($"/uploads/{filename}", "application/octet-stream");  // PATH TRAVERSAL
}

// Secure
[HttpGet("download")]
public IActionResult Download(string filename)
{
    var basePath = Path.GetFullPath("/uploads");
    var filePath = Path.GetFullPath(Path.Combine("/uploads", filename));

    if (!filePath.StartsWith(basePath, StringComparison.OrdinalIgnoreCase))
        return Forbid();

    if (!System.IO.File.Exists(filePath))
        return NotFound();

    return PhysicalFile(filePath, "application/octet-stream");
}
```

**Mitigation:**

- Canonicalize paths
- Validate against base directory
- Remove path traversal sequences

---

### CWE-352: Cross-Site Request Forgery (CSRF)

**Description:** Forcing authenticated users to perform unintended actions.

```html
<!-- Vulnerable: No CSRF protection -->
<form action="/transfer" method="POST">
    <input name="amount" value="1000">
    <input name="to" value="attacker">
</form>

<!-- Secure: Include CSRF token -->
<form action="/transfer" method="POST">
    <input name="csrf_token" value="{{ csrf_token }}">
    <input name="amount" value="1000">
    <input name="to" value="recipient">
</form>
```

**Mitigation:**

- Anti-CSRF tokens
- SameSite cookie attribute
- Verify Origin/Referer headers

---

### CWE-434: Unrestricted Upload of Dangerous File Types

**Description:** Allowing upload of files that can be executed by the server.

```csharp
// Vulnerable: No validation
[HttpPost("upload")]
public async Task<IActionResult> Upload(IFormFile file)
{
    await using var stream = new FileStream($"/uploads/{file.FileName}", FileMode.Create);
    await file.CopyToAsync(stream);  // DANGEROUS: Arbitrary file upload
    return Ok();
}

// Secure: Validate file type and content
[HttpPost("upload")]
public async Task<IActionResult> Upload(IFormFile file)
{
    HashSet<string> allowedExtensions = [".png", ".jpg", ".gif"];
    HashSet<string> allowedMimeTypes = ["image/png", "image/jpeg", "image/gif"];

    // Check extension
    var ext = Path.GetExtension(file.FileName).ToLowerInvariant();
    if (!allowedExtensions.Contains(ext))
        return BadRequest("Invalid file type");

    // Check content type
    if (!allowedMimeTypes.Contains(file.ContentType))
        return BadRequest("Invalid content type");

    // Check magic bytes
    using var reader = new BinaryReader(file.OpenReadStream());
    var header = reader.ReadBytes(8);
    if (!IsValidImage(header))
        return BadRequest("Invalid file content");

    // Generate safe filename
    var safeName = $"{Guid.NewGuid()}{ext}";
    var filePath = Path.Combine("/uploads", safeName);

    await using var stream = new FileStream(filePath, FileMode.Create);
    file.OpenReadStream().Position = 0;
    await file.CopyToAsync(stream);

    return Ok(new { FileName = safeName });
}

private static bool IsValidImage(byte[] header) =>
    header.Length >= 8 &&
    (header[..3].SequenceEqual([0xFF, 0xD8, 0xFF]) ||  // JPEG
     header[..8].SequenceEqual([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) ||  // PNG
     header[..6].SequenceEqual("GIF89a"u8.ToArray()));  // GIF
```

**Mitigation:**

- Validate file extensions and MIME types
- Check file content/magic bytes
- Store outside web root
- Rename uploaded files

---

## Important Weaknesses (11-25)

### CWE-862: Missing Authorization

Server doesn't verify user is authorized to perform action.

### CWE-476: NULL Pointer Dereference

Dereferencing a NULL pointer, causing crashes.

### CWE-287: Improper Authentication

Not properly verifying claimed identity.

### CWE-190: Integer Overflow

Calculations exceeding integer bounds.

### CWE-502: Deserialization of Untrusted Data

Deserializing attacker-controlled data.

### CWE-77: Command Injection

Similar to CWE-78, broader command injection scope.

### CWE-119: Buffer Overflow

Improper restriction of operations within memory bounds.

### CWE-798: Hard-coded Credentials

Embedding credentials in source code.

### CWE-918: Server-Side Request Forgery (SSRF)

Server makes requests to attacker-specified URLs.

### CWE-306: Missing Authentication for Critical Function

Critical functions accessible without authentication.

### CWE-362: Race Condition

Time-of-check to time-of-use (TOCTOU) vulnerabilities.

### CWE-269: Improper Privilege Management

Not properly managing user privileges.

### CWE-94: Code Injection

Injecting code that gets executed by the application.

### CWE-863: Incorrect Authorization

Authorization check exists but is flawed.

### CWE-276: Incorrect Default Permissions

Overly permissive default settings.

---

## Quick Reference by Language

| Language | High-Risk CWEs | Primary Mitigations |
|----------|---------------|---------------------|
| C/C++ | CWE-787, CWE-125, CWE-416, CWE-476 | Bounds checking, smart pointers, ASAN |
| Java | CWE-89, CWE-79, CWE-502, CWE-78 | Prepared statements, encoding, input validation |
| Python | CWE-89, CWE-78, CWE-22, CWE-94 | Parameterized queries, subprocess lists, path validation |
| JavaScript | CWE-79, CWE-94, CWE-352 | DOMPurify, CSP, CSRF tokens |
| C# | CWE-89, CWE-79, CWE-502, CWE-78 | EF Core, Razor encoding, input validation |

---

## Resources

- [CWE Top 25 Official List](https://cwe.mitre.org/top25/)
- [MITRE CWE Database](https://cwe.mitre.org/)
- [OWASP Top 10 Mapping](https://owasp.org/www-project-top-ten/)
