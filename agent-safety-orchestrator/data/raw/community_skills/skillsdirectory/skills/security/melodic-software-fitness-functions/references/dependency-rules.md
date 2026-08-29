# Dependency Rules Catalog

## Overview

This catalog provides ready-to-use dependency rules for common architectural patterns. Copy and adapt these rules for your projects.

## Layer Architecture Rules

### Clean Architecture Layers

```csharp
public class CleanArchitectureTests
{
    private readonly Assembly _domain = typeof(Entity).Assembly;
    private readonly Assembly _application = typeof(IMediator).Assembly;
    private readonly Assembly _infrastructure = typeof(DbContext).Assembly;
    private readonly Assembly _api = typeof(ControllerBase).Assembly;

    [Fact]
    public void Domain_ShouldHaveNo_OutwardDependencies()
    {
        var result = Types.InAssembly(_domain)
            .ShouldNot()
            .HaveDependencyOnAny(
                "Application",
                "Infrastructure",
                "Api",
                "Microsoft.EntityFrameworkCore",
                "Microsoft.AspNetCore"
            )
            .GetResult();

        Assert.True(result.IsSuccessful);
    }

    [Fact]
    public void Application_ShouldNotDependOn_Infrastructure()
    {
        var result = Types.InAssembly(_application)
            .ShouldNot()
            .HaveDependencyOnAny(
                "Infrastructure",
                "Api",
                "Microsoft.EntityFrameworkCore"
            )
            .GetResult();

        Assert.True(result.IsSuccessful);
    }

    [Fact]
    public void Infrastructure_ShouldNotDependOn_Api()
    {
        var result = Types.InAssembly(_infrastructure)
            .ShouldNot()
            .HaveDependencyOn("Api")
            .GetResult();

        Assert.True(result.IsSuccessful);
    }
}
```

### Hexagonal Architecture Layers

```csharp
public class HexagonalArchitectureTests
{
    [Fact]
    public void Core_ShouldNotDependOn_Adapters()
    {
        var core = Types.InNamespace("*.Core");

        var result = core
            .ShouldNot()
            .HaveDependencyOnAny(
                "*.Adapters.*",
                "Microsoft.EntityFrameworkCore",
                "Microsoft.AspNetCore"
            )
            .GetResult();

        Assert.True(result.IsSuccessful);
    }

    [Fact]
    public void DrivingAdapters_ShouldDependOn_Ports()
    {
        // API controllers should use port interfaces, not implementations
        var controllers = Types.InNamespace("*.Api.Controllers")
            .That()
            .HaveNameEndingWith("Controller");

        // This is a structural check - verify manually
    }
}
```

## Modular Monolith Rules

### Module Isolation

```csharp
public class ModuleIsolationTests
{
    // Define modules
    private readonly Assembly _orderingCore = typeof(Order).Assembly;
    private readonly Assembly _inventoryCore = typeof(Product).Assembly;
    private readonly Assembly _shippingCore = typeof(Shipment).Assembly;
    private readonly Assembly _customerCore = typeof(Customer).Assembly;

    [Theory]
    [MemberData(nameof(ModulePairs))]
    public void ModuleCores_ShouldNotReference_EachOther(
        Assembly module1, string module1Name,
        Assembly module2, string module2Name)
    {
        var result = Types.InAssembly(module1)
            .ShouldNot()
            .HaveDependencyOn(module2Name)
            .GetResult();

        Assert.True(result.IsSuccessful,
            $"{module1Name} should not depend on {module2Name}");
    }

    public static IEnumerable<object[]> ModulePairs()
    {
        var modules = new[]
        {
            (typeof(Order).Assembly, "Ordering.Core"),
            (typeof(Product).Assembly, "Inventory.Core"),
            (typeof(Shipment).Assembly, "Shipping.Core"),
            (typeof(Customer).Assembly, "Customer.Core")
        };

        foreach (var m1 in modules)
        foreach (var m2 in modules.Where(m => m != m1))
        {
            yield return new object[] { m1.Item1, m1.Item2, m2.Item1, m2.Item2 };
        }
    }
}
```

### DataTransfer Project Rules

```csharp
[Fact]
public void DataTransferProjects_ShouldOnlyContain_DTOs()
{
    var dataTransfer = Types.InNamespace("*.DataTransfer");

    var result = dataTransfer
        .That()
        .AreClasses()
        .Should()
        .BeSealed()
        .GetResult();

    Assert.True(result.IsSuccessful, "DTOs should be sealed");
}

[Fact]
public void DataTransferProjects_ShouldNotReference_CoreProjects()
{
    var dataTransfer = Types.InNamespace("*.DataTransfer");

    var result = dataTransfer
        .ShouldNot()
        .HaveDependencyOnAny(
            "*.Core",
            "*.Domain",
            "*.Application"
        )
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

### Shared Kernel Rules

```csharp
[Fact]
public void SharedKernel_ShouldNotDependOn_AnyModule()
{
    var sharedKernel = Types.InNamespace("SharedKernel");

    var result = sharedKernel
        .ShouldNot()
        .HaveDependencyOnAny(
            "Ordering",
            "Inventory",
            "Shipping",
            "Customer"
        )
        .GetResult();

    Assert.True(result.IsSuccessful);
}

[Fact]
public void AllModules_ShouldOnlyUse_SharedKernel_ForSharedTypes()
{
    // Entities should inherit from SharedKernel.Entity
    var entities = Types.InNamespace("*.Domain.Entities")
        .That()
        .AreClasses();

    var result = entities
        .Should()
        .Inherit(typeof(SharedKernel.Entity))
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Technology Constraints

### Framework Isolation

```csharp
[Fact]
public void Domain_ShouldNotUse_EntityFramework()
{
    var result = Types.InNamespace("*.Domain")
        .ShouldNot()
        .HaveDependencyOnAny(
            "Microsoft.EntityFrameworkCore",
            "Microsoft.EntityFrameworkCore.Relational",
            "Npgsql.EntityFrameworkCore"
        )
        .GetResult();

    Assert.True(result.IsSuccessful);
}

[Fact]
public void Domain_ShouldNotUse_AspNetCore()
{
    var result = Types.InNamespace("*.Domain")
        .ShouldNot()
        .HaveDependencyOnAny(
            "Microsoft.AspNetCore",
            "Microsoft.AspNetCore.Mvc",
            "Microsoft.AspNetCore.Http"
        )
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

### Allowed Infrastructure Dependencies

```csharp
[Fact]
public void Infrastructure_ShouldOnlyUse_ApprovedLibraries()
{
    var infrastructure = Types.InNamespace("*.Infrastructure");

    var result = infrastructure
        .Should()
        .OnlyHaveDependenciesOn(
            // Core .NET
            "System",
            "Microsoft.Extensions",
            // Approved libraries
            "Microsoft.EntityFrameworkCore",
            "Npgsql",
            "Polly",
            "MediatR",
            // Internal namespaces
            "*.Core",
            "*.Domain",
            "*.Application"
        )
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## CQRS Rules

### Command and Query Separation

```csharp
[Fact]
public void Commands_ShouldNotReturn_Data()
{
    var commands = Types.InNamespace("*.Application.Commands")
        .That()
        .ImplementInterface(typeof(IRequest<>));

    // Commands should return Unit or void-like
    foreach (var command in commands.GetTypes())
    {
        var interfaces = command.GetInterfaces()
            .Where(i => i.IsGenericType &&
                        i.GetGenericTypeDefinition() == typeof(IRequest<>));

        foreach (var iface in interfaces)
        {
            var returnType = iface.GetGenericArguments()[0];
            Assert.True(
                returnType == typeof(Unit) ||
                returnType == typeof(Guid) ||  // Allow returning ID
                returnType.Name.EndsWith("Result"),  // Or Result types
                $"Command {command.Name} returns {returnType.Name}"
            );
        }
    }
}

[Fact]
public void Queries_ShouldNotModify_State()
{
    var queryHandlers = Types.InNamespace("*.Application.Queries")
        .That()
        .ImplementInterface(typeof(IRequestHandler<,>));

    var result = queryHandlers
        .ShouldNot()
        .HaveDependencyOnAny(
            "*.Repositories",  // Should use read models
            "*.IUnitOfWork"
        )
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Event Sourcing Rules

### Event Store Access

```csharp
[Fact]
public void OnlyAggregates_ShouldPublish_DomainEvents()
{
    var domainEventPublishers = Types.InNamespace("*.Domain")
        .That()
        .HaveDependencyOn("*.DomainEvents");

    var result = domainEventPublishers
        .Should()
        .Inherit(typeof(AggregateRoot))
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Anti-Corruption Layer Rules

```csharp
[Fact]
public void ExternalServiceClients_ShouldBeIsolated_InACL()
{
    var externalDependencies = Types.InAssembly(_infrastructure)
        .That()
        .HaveDependencyOnAny(
            "Stripe",
            "SendGrid",
            "Twilio"
        );

    var result = externalDependencies
        .Should()
        .ResideInNamespaceMatching("*.Infrastructure.External.*")
        .Or()
        .ResideInNamespaceMatching("*.Infrastructure.ACL.*")
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Usage Guidelines

1. **Start with core rules** - Domain isolation is most important
2. **Add incrementally** - Don't try to test everything at once
3. **Document exceptions** - When rules are intentionally broken
4. **Review violations** - Decide if architecture or rule needs change
5. **Automate in CI** - Fail builds on violations

---

**Related:** `netarchtest-patterns.md`, `archunitnet-patterns.md`
