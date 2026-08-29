# Policy-as-Code Reference

This reference provides comprehensive guidance on policy-as-code tools including Open Policy Agent (OPA), Cerbos, and testing patterns.

## Open Policy Agent (OPA)

### Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                          OPA Server                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│  │   Policies  │   │    Data     │   │    Query Engine     │   │
│  │   (Rego)    │   │   (JSON)    │   │   (Evaluator)       │   │
│  └─────────────┘   └─────────────┘   └─────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                         REST API                                 │
│  POST /v1/data/{path}  - Query policies                         │
│  PUT /v1/policies/{id} - Upload policies                        │
│  PUT /v1/data/{path}   - Upload data                            │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │   API    │   │ Kubernetes│   │Terraform │
        │ Gateway  │   │ Admission │   │ Planning │
        └──────────┘   └──────────┘   └──────────┘
```

### Rego Language Basics

```rego
# policy.rego
package authz

import future.keywords.if
import future.keywords.in
import future.keywords.contains
import future.keywords.every

# Default deny - explicit is better than implicit
default allow := false

# Simple rule - user is admin
allow if {
    input.user.role == "admin"
}

# Rule with multiple conditions (all must be true)
allow if {
    input.action == "read"
    input.resource.public == true
}

# Rule using comprehension
allow if {
    some role in input.user.roles
    role == "editor"
    input.action in ["read", "write"]
}

# Negation
allow if {
    not is_blocked_user
    input.action == "read"
}

is_blocked_user if {
    input.user.id in data.blocked_users
}
```

### Advanced Rego Patterns

```rego
# advanced_policy.rego
package authz

import future.keywords

# Role hierarchy with transitive permissions
role_permissions := {
    "admin": ["read", "write", "delete", "admin"],
    "editor": ["read", "write"],
    "viewer": ["read"],
}

# Get all permissions for a role (including inherited)
user_permissions[permission] if {
    some role in input.user.roles
    some permission in role_permissions[role]
}

# Check permission using computed set
allow if {
    input.action in user_permissions
}

# Resource ownership check
allow if {
    input.action in ["read", "write", "delete"]
    input.resource.owner == input.user.id
}

# Department-based access with hierarchy
allow if {
    input.action == "read"
    department_has_access(input.user.department, input.resource.department)
}

department_hierarchy := {
    "engineering": ["engineering", "frontend", "backend", "devops"],
    "frontend": ["frontend"],
    "backend": ["backend"],
    "devops": ["devops"],
}

department_has_access(user_dept, resource_dept) if {
    resource_dept in department_hierarchy[user_dept]
}

# Time-based rules
allow if {
    input.action == "deploy"
    is_business_hours
    is_weekday
}

is_business_hours if {
    time.clock(time.now_ns())[0] >= 9
    time.clock(time.now_ns())[0] < 17
}

is_weekday if {
    day := time.weekday(time.now_ns())
    day != "Saturday"
    day != "Sunday"
}

# IP allowlist
allow if {
    input.action == "admin_access"
    ip_in_allowlist(input.source_ip)
}

ip_in_allowlist(ip) if {
    some allowed in data.ip_allowlist
    net.cidr_contains(allowed, ip)
}

# Rate limiting check (using external data)
allow if {
    input.action == "api_call"
    count(data.rate_limits[input.user.id]) < 100
}

# Complex resource matching
allow if {
    input.action == "read"
    glob.match("projects/*/documents/*", [], input.resource.path)
    can_access_project(input.user, input.resource)
}

can_access_project(user, resource) if {
    project_id := split(resource.path, "/")[1]
    project_id in data.user_projects[user.id]
}
```

### OPA Data and External Data

```rego
# Using external data loaded into OPA
# data.json:
# {
#   "roles": {
#     "admin": {"permissions": ["*"]},
#     "editor": {"permissions": ["read", "write"]}
#   },
#   "user_roles": {
#     "alice": ["admin"],
#     "bob": ["editor"]
#   }
# }

package authz

import future.keywords

# Reference external data
user_has_permission(user_id, permission) if {
    some role in data.user_roles[user_id]
    role_def := data.roles[role]
    permission in role_def.permissions
}

user_has_permission(user_id, permission) if {
    some role in data.user_roles[user_id]
    "*" in data.roles[role].permissions
}
```

### OPA Integration Patterns

```csharp
using System.Text.Json;
using System.Text.Json.Serialization;

/// <summary>
/// Production-ready OPA client for .NET applications.
/// </summary>
public sealed class OpaClient(HttpClient httpClient, string baseUrl = "http://localhost:8181")
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    /// <summary>
    /// Query OPA for a decision.
    /// </summary>
    public async Task<JsonElement> QueryAsync(
        string path,
        object inputData,
        CancellationToken cancellationToken = default)
    {
        var request = new { input = inputData };
        var response = await httpClient.PostAsJsonAsync(
            $"{baseUrl}/v1/data/{path}",
            request,
            JsonOptions,
            cancellationToken);

        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<JsonElement>(cancellationToken);
        return result;
    }

    /// <summary>
    /// Check if access is allowed.
    /// </summary>
    public async Task<bool> CheckAsync(
        string policyPath,
        object inputData,
        CancellationToken cancellationToken = default)
    {
        var result = await QueryAsync(policyPath, inputData, cancellationToken);
        return result.TryGetProperty("result", out var value) &&
               value.ValueKind == JsonValueKind.True;
    }

    /// <summary>
    /// Upload a Rego policy.
    /// </summary>
    public async Task UploadPolicyAsync(
        string policyId,
        string policyContent,
        CancellationToken cancellationToken = default)
    {
        using var content = new StringContent(policyContent, System.Text.Encoding.UTF8, "text/plain");
        var response = await httpClient.PutAsync(
            $"{baseUrl}/v1/policies/{policyId}",
            content,
            cancellationToken);

        response.EnsureSuccessStatusCode();
    }

    /// <summary>
    /// Upload data to OPA.
    /// </summary>
    public async Task UploadDataAsync(
        string path,
        object data,
        CancellationToken cancellationToken = default)
    {
        var response = await httpClient.PutAsJsonAsync(
            $"{baseUrl}/v1/data/{path}",
            data,
            JsonOptions,
            cancellationToken);

        response.EnsureSuccessStatusCode();
    }
}

// ASP.NET Core authorization filter
public sealed class OpaAuthorizationAttribute(string action) : ActionFilterAttribute
{
    public override async Task OnActionExecutionAsync(
        ActionExecutingContext context,
        ActionExecutionDelegate next)
    {
        var opaClient = context.HttpContext.RequestServices.GetRequiredService<OpaClient>();
        var resourceService = context.HttpContext.RequestServices.GetRequiredService<IResourceService>();

        var user = context.HttpContext.User;
        context.RouteData.Values.TryGetValue("resourceId", out var resourceIdObj);
        var resourceId = resourceIdObj?.ToString();

        var inputData = new
        {
            user = new
            {
                id = user.Identity?.Name,
                roles = user.Claims.Where(c => c.Type == "role").Select(c => c.Value).ToList(),
                department = user.FindFirst("department")?.Value
            },
            action,
            resource = new
            {
                type = context.RouteData.Values["controller"]?.ToString()?.ToLowerInvariant(),
                id = resourceId,
                owner = resourceId is not null ? await resourceService.GetOwnerAsync(resourceId) : null
            },
            context = new
            {
                ip = context.HttpContext.Connection.RemoteIpAddress?.ToString(),
                timestamp = DateTime.UtcNow.ToString("O")
            }
        };

        if (!await opaClient.CheckAsync("authz/allow", inputData))
        {
            context.Result = new ForbidResult();
            return;
        }

        await next();
    }
}

// Usage in ASP.NET Core controller
[ApiController]
[Route("[controller]")]
public sealed class DocumentsController : ControllerBase
{
    [HttpGet("{resourceId}")]
    [OpaAuthorization("read")]
    public IActionResult GetDocument(string resourceId)
    {
        return Ok(new { id = resourceId });
    }
}

public interface IResourceService
{
    Task<string?> GetOwnerAsync(string resourceId);
}
```

### OPA Bundle Server

```csharp
using System.IO.Compression;
using System.Text.Json;

// ASP.NET Core minimal API for serving OPA bundles
public static class OpaBundleEndpoints
{
    public static void MapOpaBundleEndpoints(this WebApplication app)
    {
        app.MapGet("/bundles/authz.tar.gz", ServeBundle)
            .Produces(200, contentType: "application/gzip");
    }

    /// <summary>
    /// Serve OPA bundle as gzipped tar archive.
    /// </summary>
    private static async Task<IResult> ServeBundle(IWebHostEnvironment env)
    {
        var buffer = new MemoryStream();

        // Create tar.gz archive
        await using (var gzipStream = new GZipStream(buffer, CompressionLevel.Optimal, leaveOpen: true))
        await using (var tarWriter = new TarWriter(gzipStream))
        {
            // Add policy files
            var policyPath = Path.Combine(env.ContentRootPath, "policies", "authz.rego");
            if (File.Exists(policyPath))
            {
                var policyContent = await File.ReadAllBytesAsync(policyPath);
                await AddFileToTarAsync(tarWriter, "authz.rego", policyContent);
            }

            // Add data files
            var dataContent = JsonSerializer.SerializeToUtf8Bytes(new
            {
                roles = new Dictionary<string, object>
                {
                    ["admin"] = new { permissions = new[] { "*" } },
                    ["editor"] = new { permissions = new[] { "read", "write" } }
                }
            });
            await AddFileToTarAsync(tarWriter, "data.json", dataContent);

            // Add manifest
            var manifest = JsonSerializer.SerializeToUtf8Bytes(new
            {
                revision = "v1.0.0",
                roots = new[] { "authz" }
            });
            await AddFileToTarAsync(tarWriter, ".manifest", manifest);
        }

        buffer.Position = 0;
        return Results.File(buffer, "application/gzip", "authz.tar.gz");
    }

    private static async Task AddFileToTarAsync(TarWriter tar, string name, byte[] content)
    {
        var entry = new PaxTarEntry(TarEntryType.RegularFile, name)
        {
            DataStream = new MemoryStream(content)
        };
        await tar.WriteEntryAsync(entry);
    }
}

// Usage in Program.cs
// var app = builder.Build();
// app.MapOpaBundleEndpoints();
```

## Cerbos

### Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                        Cerbos PDP                                │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐   ┌─────────────────┐   ┌───────────────┐  │
│  │ Resource Policy │   │  Principal Pol. │   │ Derived Roles │  │
│  │     (YAML)      │   │     (YAML)      │   │    (YAML)     │  │
│  └─────────────────┘   └─────────────────┘   └───────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│           gRPC API  /  REST API  /  SDK                          │
└─────────────────────────────────────────────────────────────────┘
```

### Resource Policies

```yaml
# policies/resource/document.yaml
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  version: default
  resource: document
  rules:
    # Owners have full access
    - actions: ["*"]
      effect: EFFECT_ALLOW
      roles: ["owner"]
      condition:
        match:
          expr: request.resource.attr.owner == request.principal.id

    # Editors can read and update
    - actions: ["read", "update"]
      effect: EFFECT_ALLOW
      roles: ["editor"]

    # Viewers can only read
    - actions: ["read"]
      effect: EFFECT_ALLOW
      roles: ["viewer"]

    # Public documents readable by all
    - actions: ["read"]
      effect: EFFECT_ALLOW
      roles: ["*"]
      condition:
        match:
          expr: request.resource.attr.public == true

    # Department access
    - actions: ["read"]
      effect: EFFECT_ALLOW
      roles: ["employee"]
      condition:
        match:
          expr: request.resource.attr.department == request.principal.attr.department
```

### Principal Policies

```yaml
# policies/principal/admin.yaml
apiVersion: api.cerbos.dev/v1
principalPolicy:
  version: default
  principal: admin
  rules:
    # Admins can do everything
    - resource: "*"
      actions:
        - action: "*"
          effect: EFFECT_ALLOW

# policies/principal/service_account.yaml
apiVersion: api.cerbos.dev/v1
principalPolicy:
  version: default
  principal: service_account
  rules:
    # Service accounts limited to read operations
    - resource: "*"
      actions:
        - action: "read"
          effect: EFFECT_ALLOW
        - action: "list"
          effect: EFFECT_ALLOW
    # But can write to logs
    - resource: "audit_log"
      actions:
        - action: "write"
          effect: EFFECT_ALLOW
```

### Derived Roles

```yaml
# policies/derived_roles/project_roles.yaml
apiVersion: api.cerbos.dev/v1
derivedRoles:
  name: project_roles
  definitions:
    # Project owner if user is in project's owner list
    - name: project_owner
      parentRoles: ["user"]
      condition:
        match:
          expr: request.principal.id in request.resource.attr.owners

    # Project member if user is in project's member list
    - name: project_member
      parentRoles: ["user"]
      condition:
        match:
          expr: request.principal.id in request.resource.attr.members

    # Manager if user manages the resource owner
    - name: manager
      parentRoles: ["user"]
      condition:
        match:
          all:
            of:
              - expr: request.principal.attr.manages != null
              - expr: request.resource.attr.owner in request.principal.attr.manages

    # Senior editor if user is editor AND has seniority > 3
    - name: senior_editor
      parentRoles: ["editor"]
      condition:
        match:
          expr: request.principal.attr.years_experience > 3
```

### Cerbos Integration

```csharp
using Cerbos.Sdk;
using Cerbos.Sdk.Builder;
using Cerbos.Sdk.Response;

/// <summary>
/// Cerbos authorization service for .NET applications.
/// </summary>
public sealed class CerbosAuthorizationService(CerbosClient client)
{
    /// <summary>
    /// Check access using Cerbos.
    /// </summary>
    public async Task<bool> CheckAccessAsync(
        string userId,
        IEnumerable<string> userRoles,
        Dictionary<string, object>? userAttrs,
        string resourceType,
        string resourceId,
        Dictionary<string, object>? resourceAttrs,
        string action,
        CancellationToken cancellationToken = default)
    {
        var principal = Principal.NewInstance(userId)
            .WithRoles(userRoles.ToArray());

        if (userAttrs is not null)
        {
            foreach (var (key, value) in userAttrs)
            {
                principal = principal.WithAttribute(key, AttributeValue.FromObject(value));
            }
        }

        var resource = Resource.NewInstance(resourceType, resourceId);

        if (resourceAttrs is not null)
        {
            foreach (var (key, value) in resourceAttrs)
            {
                resource = resource.WithAttribute(key, AttributeValue.FromObject(value));
            }
        }

        var result = await client.CheckResourcesAsync(
            principal.Build(),
            resource.Build(),
            action);

        return result.IsAllowed(action);
    }

    /// <summary>
    /// Check access to multiple resources (batch).
    /// </summary>
    public async Task<Dictionary<string, bool>> CheckResourcesAsync(
        string userId,
        IEnumerable<string> userRoles,
        IEnumerable<ResourceInfo> resources,
        string action,
        CancellationToken cancellationToken = default)
    {
        var principal = Principal.NewInstance(userId)
            .WithRoles(userRoles.ToArray())
            .Build();

        var resourceEntries = resources.Select(r =>
            ResourceAction.NewInstance(r.Type, r.Id)
                .WithAttributes(r.Attrs ?? new Dictionary<string, object>())
                .WithActions(action)
                .Build()
        ).ToArray();

        var results = await client.CheckResourcesAsync(principal, resourceEntries);

        return resources.ToDictionary(
            r => r.Id,
            r => results.Find(r.Id)?.IsAllowed(action) ?? false
        );
    }
}

public sealed record ResourceInfo(string Id, string Type, Dictionary<string, object>? Attrs = null);

// ASP.NET Core authorization filter for Cerbos
public sealed class CerbosAuthorizationAttribute(string resourceType, string action)
    : ActionFilterAttribute
{
    public override async Task OnActionExecutionAsync(
        ActionExecutingContext context,
        ActionExecutionDelegate next)
    {
        var cerbosService = context.HttpContext.RequestServices
            .GetRequiredService<CerbosAuthorizationService>();
        var resourceService = context.HttpContext.RequestServices
            .GetRequiredService<IResourceAttributeService>();

        var user = context.HttpContext.User;
        context.RouteData.Values.TryGetValue("resourceId", out var resourceIdObj);
        var resourceId = resourceIdObj?.ToString() ?? string.Empty;

        var resourceAttrs = await resourceService.GetAttributesAsync(resourceType, resourceId);

        var isAllowed = await cerbosService.CheckAccessAsync(
            userId: user.Identity?.Name ?? string.Empty,
            userRoles: user.Claims.Where(c => c.Type == "role").Select(c => c.Value),
            userAttrs: new Dictionary<string, object>
            {
                ["department"] = user.FindFirst("department")?.Value ?? string.Empty
            },
            resourceType: resourceType,
            resourceId: resourceId,
            resourceAttrs: resourceAttrs,
            action: action
        );

        if (!isAllowed)
        {
            context.Result = new ForbidResult();
            return;
        }

        await next();
    }
}

public interface IResourceAttributeService
{
    Task<Dictionary<string, object>?> GetAttributesAsync(string resourceType, string resourceId);
}

// DI registration in Program.cs
// builder.Services.AddSingleton(new CerbosClientBuilder("localhost:3593").WithPlaintext().Build());
// builder.Services.AddScoped<CerbosAuthorizationService>();
```

## Policy Testing

### OPA Unit Tests

```rego
# authz_test.rego
package authz_test

import future.keywords
import data.authz

# Test admin access
test_admin_can_do_anything if {
    authz.allow with input as {
        "user": {"id": "alice", "roles": ["admin"]},
        "action": "delete",
        "resource": {"type": "document", "id": "doc-1"}
    }
}

# Test viewer cannot delete
test_viewer_cannot_delete if {
    not authz.allow with input as {
        "user": {"id": "bob", "roles": ["viewer"]},
        "action": "delete",
        "resource": {"type": "document", "id": "doc-1"}
    }
}

# Test owner can access their resource
test_owner_access if {
    authz.allow with input as {
        "user": {"id": "alice", "roles": ["user"]},
        "action": "read",
        "resource": {"type": "document", "id": "doc-1", "owner": "alice"}
    }
}

# Test non-owner cannot access private resource
test_non_owner_no_access if {
    not authz.allow with input as {
        "user": {"id": "bob", "roles": ["user"]},
        "action": "read",
        "resource": {"type": "document", "id": "doc-1", "owner": "alice", "public": false}
    }
}

# Test department isolation
test_same_department_access if {
    authz.allow with input as {
        "user": {"id": "alice", "department": "engineering"},
        "action": "read",
        "resource": {"department": "engineering"}
    }
}

test_different_department_no_access if {
    not authz.allow with input as {
        "user": {"id": "alice", "department": "engineering"},
        "action": "read",
        "resource": {"department": "finance", "public": false}
    }
}
```

### Running OPA Tests

```bash
# Run all tests
opa test policies/ -v

# Run specific tests
opa test policies/ -v --run "test_admin"

# Coverage report
opa test policies/ --coverage --format=json

# Format check
opa fmt --diff policies/

# Type check
opa check policies/
```

### Cerbos Policy Tests

```yaml
# tests/document_test.yaml
name: DocumentPolicyTests
description: Tests for document resource policies

principals:
  admin:
    id: admin_user
    roles: ["admin"]

  owner:
    id: alice
    roles: ["user"]

  viewer:
    id: bob
    roles: ["viewer"]

  outsider:
    id: charlie
    roles: ["user"]
    attr:
      department: finance

resources:
  alice_document:
    kind: document
    id: doc-123
    attr:
      owner: alice
      department: engineering
      public: false

  public_document:
    kind: document
    id: doc-456
    attr:
      owner: alice
      public: true

tests:
  - name: Admin can delete any document
    input:
      principal: admin
      resource: alice_document
      action: delete
    expected:
      - action: delete
        effect: EFFECT_ALLOW

  - name: Owner can read own document
    input:
      principal: owner
      resource: alice_document
      action: read
    expected:
      - action: read
        effect: EFFECT_ALLOW

  - name: Viewer cannot delete
    input:
      principal: viewer
      resource: alice_document
      action: delete
    expected:
      - action: delete
        effect: EFFECT_DENY

  - name: Anyone can read public document
    input:
      principal: outsider
      resource: public_document
      action: read
    expected:
      - action: read
        effect: EFFECT_ALLOW

  - name: Outsider cannot read private document
    input:
      principal: outsider
      resource: alice_document
      action: read
    expected:
      - action: read
        effect: EFFECT_DENY
```

### Integration Tests

```csharp
using Xunit;
using FluentAssertions;
using System.Diagnostics;

/// <summary>
/// Integration tests for OPA policies.
/// </summary>
public sealed class OpaAuthorizationTests : IClassFixture<OpaClientFixture>
{
    private readonly OpaClient _opaClient;

    public OpaAuthorizationTests(OpaClientFixture fixture)
    {
        _opaClient = fixture.Client;
    }

    [Fact]
    public async Task AdminHasFullAccess()
    {
        var result = await _opaClient.CheckAsync("authz/allow", new
        {
            user = new { id = "admin", roles = new[] { "admin" } },
            action = "delete",
            resource = new { type = "document", id = "doc-1" }
        });

        result.Should().BeTrue();
    }

    [Fact]
    public async Task ViewerCanOnlyRead()
    {
        // Can read
        var canRead = await _opaClient.CheckAsync("authz/allow", new
        {
            user = new { id = "viewer", roles = new[] { "viewer" } },
            action = "read",
            resource = new { type = "document", id = "doc-1" }
        });
        canRead.Should().BeTrue();

        // Cannot write
        var canWrite = await _opaClient.CheckAsync("authz/allow", new
        {
            user = new { id = "viewer", roles = new[] { "viewer" } },
            action = "write",
            resource = new { type = "document", id = "doc-1" }
        });
        canWrite.Should().BeFalse();
    }

    [Fact]
    public async Task OwnerCanAccessOwnResource()
    {
        // Owner can access own resource
        var ownerAccess = await _opaClient.CheckAsync("authz/allow", new
        {
            user = new { id = "alice", roles = new[] { "user" } },
            action = "delete",
            resource = new { type = "document", id = "doc-1", owner = "alice" }
        });
        ownerAccess.Should().BeTrue();

        // Non-owner cannot access
        var nonOwnerAccess = await _opaClient.CheckAsync("authz/allow", new
        {
            user = new { id = "bob", roles = new[] { "user" } },
            action = "delete",
            resource = new { type = "document", id = "doc-1", owner = "alice" }
        });
        nonOwnerAccess.Should().BeFalse();
    }

    [Theory]
    [InlineData("read", true)]
    [InlineData("write", true)]
    [InlineData("delete", false)]
    [InlineData("admin", false)]
    public async Task EditorPermissions(string action, bool expected)
    {
        var result = await _opaClient.CheckAsync("authz/allow", new
        {
            user = new { id = "editor", roles = new[] { "editor" } },
            action,
            resource = new { type = "document", id = "doc-1" }
        });

        result.Should().Be(expected);
    }
}

/// <summary>
/// Integration tests for Cerbos policies.
/// </summary>
public sealed class CerbosAuthorizationTests : IClassFixture<CerbosClientFixture>
{
    private readonly CerbosAuthorizationService _cerbosService;

    public CerbosAuthorizationTests(CerbosClientFixture fixture)
    {
        _cerbosService = fixture.Service;
    }

    [Fact]
    public async Task DerivedRoleProjectOwner()
    {
        // Alice is project owner via derived role
        var isAllowed = await _cerbosService.CheckAccessAsync(
            userId: "alice",
            userRoles: ["user"],
            userAttrs: null,
            resourceType: "project",
            resourceId: "project-1",
            resourceAttrs: new Dictionary<string, object>
            {
                ["owners"] = new[] { "alice", "bob" }
            },
            action: "admin"
        );

        isAllowed.Should().BeTrue();
    }

    [Fact]
    public async Task BatchCheckPerformance()
    {
        var resources = Enumerable.Range(0, 100)
            .Select(i => new ResourceInfo($"doc-{i}", "document"))
            .ToList();

        var stopwatch = Stopwatch.StartNew();

        var results = await _cerbosService.CheckResourcesAsync(
            userId: "alice",
            userRoles: ["admin"],
            resources: resources,
            action: "read"
        );

        stopwatch.Stop();

        // Batch check should be fast - less than 1 second for 100 resources
        stopwatch.Elapsed.Should().BeLessThan(TimeSpan.FromSeconds(1));
        results.Should().HaveCount(100);
    }
}

// Test fixtures
public sealed class OpaClientFixture : IAsyncLifetime
{
    public OpaClient Client { get; private set; } = null!;

    public Task InitializeAsync()
    {
        var httpClient = new HttpClient();
        Client = new OpaClient(httpClient, "http://localhost:8181");
        return Task.CompletedTask;
    }

    public Task DisposeAsync() => Task.CompletedTask;
}

public sealed class CerbosClientFixture : IAsyncLifetime
{
    public CerbosAuthorizationService Service { get; private set; } = null!;

    public Task InitializeAsync()
    {
        var client = new CerbosClientBuilder("localhost:3593")
            .WithPlaintext()
            .Build();
        Service = new CerbosAuthorizationService(client);
        return Task.CompletedTask;
    }

    public Task DisposeAsync() => Task.CompletedTask;
}
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/policy-test.yml
name: Policy Tests

on:
  push:
    paths:
      - 'policies/**'
  pull_request:
    paths:
      - 'policies/**'

jobs:
  opa-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Setup OPA
        uses: open-policy-agent/setup-opa@v2
        with:
          version: latest

      - name: Lint policies
        run: opa fmt --diff --fail policies/

      - name: Type check
        run: opa check policies/

      - name: Run tests
        run: opa test policies/ -v

      - name: Coverage
        run: |
          opa test policies/ --coverage --format=json > coverage.json
          opa test policies/ --coverage

  cerbos-tests:
    runs-on: ubuntu-latest
    services:
      cerbos:
        image: ghcr.io/cerbos/cerbos:latest
        ports:
          - 3593:3593
        options: >-
          --mount type=bind,source=${{ github.workspace }}/policies,target=/policies
    steps:
      - uses: actions/checkout@v5

      - name: Run Cerbos tests
        run: |
          cerbos compile policies/
          cerbos test tests/
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: opa-fmt
        name: OPA Format
        entry: opa fmt -w
        language: system
        files: \.rego$

      - id: opa-check
        name: OPA Type Check
        entry: opa check
        language: system
        files: \.rego$
        pass_filenames: false
        args: [policies/]

      - id: opa-test
        name: OPA Test
        entry: opa test policies/ -v
        language: system
        pass_filenames: false
        always_run: true
```

## Security Checklist

### Policy Management

- [ ] Policies version controlled
- [ ] Policy changes reviewed
- [ ] Policies tested before deployment
- [ ] Default deny policy in place

### Testing

- [ ] Unit tests for all policies
- [ ] Integration tests with application
- [ ] Performance tests for batch operations
- [ ] Edge cases covered

### Deployment

- [ ] Policy bundles signed
- [ ] Rollback mechanism in place
- [ ] Monitoring for policy failures
- [ ] Audit logging enabled

### Operations

- [ ] Policy evaluation metrics tracked
- [ ] Alert on evaluation errors
- [ ] Regular policy reviews scheduled
- [ ] Documentation maintained
