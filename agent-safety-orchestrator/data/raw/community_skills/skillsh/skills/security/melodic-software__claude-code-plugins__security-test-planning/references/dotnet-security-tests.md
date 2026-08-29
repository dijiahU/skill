# .NET Security Testing Examples

## Integration Test for Authorization

```csharp
public class AuthorizationTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public AuthorizationTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task GetOrder_WithoutAuth_Returns401()
    {
        // Arrange - no auth token

        // Act
        var response = await _client.GetAsync("/api/orders/123");

        // Assert
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task GetOrder_WrongUser_Returns403()
    {
        // Arrange
        var token = await GetTokenForUser("user-a@test.com");
        _client.DefaultRequestHeaders.Authorization =
            new AuthenticationHeaderValue("Bearer", token);

        // Act - Try to access user-b's order
        var response = await _client.GetAsync("/api/orders/user-b-order-id");

        // Assert
        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Theory]
    [InlineData("/api/admin/users", "user")]
    [InlineData("/api/admin/settings", "user")]
    [InlineData("/api/admin/audit", "manager")]
    public async Task AdminEndpoints_InsufficientRole_Returns403(
        string endpoint, string role)
    {
        // Arrange
        var token = await GetTokenForRole(role);
        _client.DefaultRequestHeaders.Authorization =
            new AuthenticationHeaderValue("Bearer", token);

        // Act
        var response = await _client.GetAsync(endpoint);

        // Assert
        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }
}
```

---

## Input Validation Security Tests

```csharp
public class InputValidationSecurityTests : IClassFixture<WebApplicationFactory<Program>>
{
    [Theory]
    [InlineData("'; DROP TABLE users; --")]
    [InlineData("1 OR 1=1")]
    [InlineData("1; EXEC xp_cmdshell('dir')")]
    [InlineData("1 UNION SELECT * FROM users")]
    public async Task Search_SqlInjectionAttempt_IsBlocked(string maliciousInput)
    {
        // Arrange
        var request = new { query = maliciousInput };

        // Act
        var response = await _client.PostAsJsonAsync("/api/search", request);

        // Assert - Should not return data from other tables or error with SQL details
        Assert.True(response.IsSuccessStatusCode || response.StatusCode == HttpStatusCode.BadRequest);
        var content = await response.Content.ReadAsStringAsync();
        Assert.DoesNotContain("SQL", content);
        Assert.DoesNotContain("syntax", content, StringComparison.OrdinalIgnoreCase);
    }

    [Theory]
    [InlineData("<script>alert('xss')</script>")]
    [InlineData("<img src=x onerror=alert('xss')>")]
    [InlineData("javascript:alert('xss')")]
    [InlineData("<svg onload=alert('xss')>")]
    public async Task CreateComment_XssAttempt_IsSanitized(string maliciousInput)
    {
        // Arrange
        var request = new { content = maliciousInput };
        await AuthenticateAsUser();

        // Act
        var response = await _client.PostAsJsonAsync("/api/comments", request);
        var comment = await response.Content.ReadFromJsonAsync<CommentDto>();

        // Assert - XSS payloads should be escaped or removed
        Assert.DoesNotContain("<script>", comment.Content);
        Assert.DoesNotContain("javascript:", comment.Content);
        Assert.DoesNotContain("onerror=", comment.Content);
    }

    [Theory]
    [InlineData("../../../etc/passwd")]
    [InlineData("..\\..\\..\\windows\\system32\\config\\sam")]
    [InlineData("....//....//....//etc/passwd")]
    public async Task DownloadFile_PathTraversal_IsBlocked(string maliciousPath)
    {
        // Arrange
        await AuthenticateAsUser();

        // Act
        var response = await _client.GetAsync($"/api/files/{Uri.EscapeDataString(maliciousPath)}");

        // Assert
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }
}
```

---

## Rate Limiting Tests

```csharp
public class RateLimitingTests : IClassFixture<WebApplicationFactory<Program>>
{
    [Fact]
    public async Task Login_ExceedsRateLimit_Returns429()
    {
        // Arrange
        var loginRequest = new { email = "test@example.com", password = "wrong" };

        // Act - Attempt 20 rapid logins
        var responses = new List<HttpResponseMessage>();
        for (int i = 0; i < 20; i++)
        {
            responses.Add(await _client.PostAsJsonAsync("/api/auth/login", loginRequest));
        }

        // Assert - Should hit rate limit
        Assert.Contains(responses, r => r.StatusCode == HttpStatusCode.TooManyRequests);
    }

    [Fact]
    public async Task RateLimited_ReturnsRetryAfterHeader()
    {
        // Arrange & Act - Trigger rate limit
        HttpResponseMessage rateLimitedResponse = null;
        for (int i = 0; i < 100; i++)
        {
            var response = await _client.GetAsync("/api/search?q=test");
            if (response.StatusCode == HttpStatusCode.TooManyRequests)
            {
                rateLimitedResponse = response;
                break;
            }
        }

        // Assert
        Assert.NotNull(rateLimitedResponse);
        Assert.True(rateLimitedResponse.Headers.Contains("Retry-After"));
    }
}
```

---

## Key Patterns

### Test Categories

| Category | What to Test | Expected Result |
|----------|--------------|-----------------|
| Authentication | Missing/invalid tokens | 401 Unauthorized |
| Authorization | Wrong user/role access | 403 Forbidden |
| SQL Injection | Malicious SQL strings | Blocked/Sanitized |
| XSS | Script injection | Escaped/Removed |
| Path Traversal | Directory escape attempts | 400 Bad Request |
| Rate Limiting | Rapid requests | 429 Too Many Requests |

### Test Data Patterns

```csharp
// SQL Injection payloads
"'; DROP TABLE users; --"
"1 OR 1=1"
"1 UNION SELECT * FROM users"

// XSS payloads
"<script>alert('xss')</script>"
"<img src=x onerror=alert('xss')>"
"javascript:alert('xss')"

// Path traversal payloads
"../../../etc/passwd"
"..\\..\\windows\\system32"
"....//....//etc/passwd"
```
