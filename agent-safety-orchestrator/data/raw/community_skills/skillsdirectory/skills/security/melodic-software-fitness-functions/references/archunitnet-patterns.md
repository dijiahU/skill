# ArchUnitNET Patterns

## Overview

ArchUnitNET is a .NET port of the Java ArchUnit library. It provides powerful, expressive rules for testing architectural constraints with a fluent API.

## Installation

```bash
dotnet add package ArchUnitNET
dotnet add package ArchUnitNET.xUnit  # or ArchUnitNET.NUnit
```

## Architecture Setup

### Loading the Architecture

```csharp
using ArchUnitNET.Domain;
using ArchUnitNET.Loader;
using ArchUnitNET.Fluent;
using static ArchUnitNET.Fluent.ArchRuleDefinition;

public class ArchitectureTests
{
    // Load all assemblies once (expensive operation)
    private static readonly Architecture Architecture = new ArchLoader()
        .LoadAssemblies(
            typeof(Order).Assembly,           // Domain
            typeof(OrderHandler).Assembly,     // Application
            typeof(OrderRepository).Assembly,  // Infrastructure
            typeof(OrdersController).Assembly  // API
        )
        .Build();

    // Define layers as reusable predicates
    private static readonly IObjectProvider<IType> DomainLayer =
        Types().That().ResideInNamespace(".*Domain.*", true).As("Domain Layer");

    private static readonly IObjectProvider<IType> ApplicationLayer =
        Types().That().ResideInNamespace(".*Application.*", true).As("Application Layer");

    private static readonly IObjectProvider<IType> InfrastructureLayer =
        Types().That().ResideInNamespace(".*Infrastructure.*", true).As("Infrastructure Layer");

    private static readonly IObjectProvider<IType> ApiLayer =
        Types().That().ResideInNamespace(".*Api.*", true).As("API Layer");
}
```

## Layer Dependency Rules

### Basic Layer Constraints

```csharp
[Fact]
public void DomainLayer_ShouldNotDependOn_OtherLayers()
{
    IArchRule rule = Types().That().Are(DomainLayer)
        .Should().NotDependOnAny(ApplicationLayer)
        .AndShould().NotDependOnAny(InfrastructureLayer)
        .AndShould().NotDependOnAny(ApiLayer);

    rule.Check(Architecture);
}

[Fact]
public void ApplicationLayer_ShouldNotDependOn_Infrastructure()
{
    IArchRule rule = Types().That().Are(ApplicationLayer)
        .Should().NotDependOnAny(InfrastructureLayer)
        .AndShould().NotDependOnAny(ApiLayer);

    rule.Check(Architecture);
}
```

### Layered Architecture Definition

```csharp
[Fact]
public void LayeredArchitecture_ShouldBeRespected()
{
    IArchRule rule = Types().That().Are(DomainLayer)
        .Should().OnlyDependOn(
            Types().That().Are(DomainLayer)
            .Or().ResideInNamespace("System.*", true)
        );

    rule.Check(Architecture);
}
```

## Module Isolation Rules

### Cross-Module Prevention

```csharp
private static readonly IObjectProvider<IType> OrderingModule =
    Types().That().ResideInNamespace(".*Ordering.*", true).As("Ordering Module");

private static readonly IObjectProvider<IType> InventoryModule =
    Types().That().ResideInNamespace(".*Inventory.*", true).As("Inventory Module");

private static readonly IObjectProvider<IType> ShippingModule =
    Types().That().ResideInNamespace(".*Shipping.*", true).As("Shipping Module");

[Fact]
public void OrderingModule_ShouldNotDependOn_OtherModules()
{
    IArchRule rule = Types().That().Are(OrderingModule)
        .And().ResideInNamespace(".*Core.*", true)  // Only Core project
        .Should().NotDependOnAny(InventoryModule)
        .AndShould().NotDependOnAny(ShippingModule);

    rule.Check(Architecture);
}
```

### DataTransfer Exception

```csharp
[Fact]
public void Modules_CanDependOn_DataTransferProjects()
{
    var dataTransferTypes = Types()
        .That().ResideInNamespace(".*DataTransfer.*", true)
        .As("DataTransfer Projects");

    // This rule should pass - modules CAN use DataTransfer
    IArchRule rule = Types().That().Are(OrderingModule)
        .Should().NotDependOnAny(
            Types().That().Are(InventoryModule)
            .And().DoNotResideInNamespace(".*DataTransfer.*", true)
        );

    rule.Check(Architecture);
}
```

## Naming Convention Rules

### Handler Naming

```csharp
[Fact]
public void CommandHandlers_ShouldBeNamedCorrectly()
{
    IArchRule rule = Classes()
        .That().ImplementInterface(typeof(IRequestHandler<,>))
        .Should().HaveNameEndingWith("Handler");

    rule.Check(Architecture);
}
```

### Repository Naming

```csharp
[Fact]
public void Repositories_ShouldFollowNamingConvention()
{
    IArchRule rule = Classes()
        .That().ImplementInterface(typeof(IRepository<>))
        .Should().HaveNameEndingWith("Repository")
        .AndShould().ResideInNamespace(".*Infrastructure.*", true);

    rule.Check(Architecture);
}
```

## Interface Rules

### Interface Implementation

```csharp
[Fact]
public void Entities_ShouldImplement_IEntity()
{
    IArchRule rule = Classes()
        .That().ResideInNamespace(".*Domain.Entities.*", true)
        .Should().ImplementInterface(typeof(IEntity));

    rule.Check(Architecture);
}

[Fact]
public void ValueObjects_ShouldInheritFrom_ValueObjectBase()
{
    IArchRule rule = Classes()
        .That().HaveNameEndingWith("ValueObject")
        .Or().ResideInNamespace(".*Domain.ValueObjects.*", true)
        .Should().BeAssignableTo(typeof(ValueObject));

    rule.Check(Architecture);
}
```

## Attribute Rules

### Required Attributes

```csharp
[Fact]
public void Controllers_ShouldHave_ApiControllerAttribute()
{
    IArchRule rule = Classes()
        .That().HaveNameEndingWith("Controller")
        .Should().HaveAnyAttributes(typeof(ApiControllerAttribute));

    rule.Check(Architecture);
}

[Fact]
public void Commands_ShouldNotHave_SerializableAttribute()
{
    IArchRule rule = Classes()
        .That().HaveNameEndingWith("Command")
        .Should().NotHaveAnyAttributes(typeof(SerializableAttribute));

    rule.Check(Architecture);
}
```

## Visibility Rules

### Sealing Requirements

```csharp
[Fact]
public void DTOs_ShouldBeSealed()
{
    IArchRule rule = Classes()
        .That().HaveNameEndingWith("Dto")
        .Should().BeSealed();

    rule.Check(Architecture);
}

[Fact]
public void Handlers_ShouldNotBePublic()
{
    IArchRule rule = Classes()
        .That().ImplementInterface(typeof(IRequestHandler<,>))
        .Should().NotBePublic();

    rule.Check(Architecture);
}
```

## Dependency Direction

### Ports and Adapters Validation

```csharp
// Define port interfaces
private static readonly IObjectProvider<IType> Ports =
    Types().That().ResideInNamespace(".*Ports.*", true).As("Ports");

// Define adapters
private static readonly IObjectProvider<IType> Adapters =
    Types().That().ResideInNamespace(".*Adapters.*", true).As("Adapters");

[Fact]
public void Adapters_ShouldDependOn_Ports()
{
    // Adapters should implement port interfaces
    IArchRule rule = Classes().That().Are(Adapters)
        .Should().ImplementInterface(
            Interfaces().That().Are(Ports)
        );

    rule.Check(Architecture);
}

[Fact]
public void Core_ShouldNotDependOn_Adapters()
{
    IArchRule rule = Types().That().ResideInNamespace(".*Core.*", true)
        .Should().NotDependOnAny(Adapters);

    rule.Check(Architecture);
}
```

## Complex Rule Combinations

### Multiple Constraints

```csharp
[Fact]
public void DomainEvents_ShouldFollowConventions()
{
    IArchRule rule = Classes()
        .That().ImplementInterface(typeof(IDomainEvent))
        .Should().BeSealed()
        .AndShould().HaveNameEndingWith("Event")
        .AndShould().ResideInNamespace(".*Domain.Events.*", true)
        .AndShould().NotBePublic();

    rule.Check(Architecture);
}
```

### Conditional Rules

```csharp
[Fact]
public void IfHandler_ThenMustBeInternal()
{
    // If a class ends with "Handler", it should be internal
    IArchRule rule = Classes()
        .That().HaveNameEndingWith("Handler")
        .Should().NotBePublic()
        .Because("handlers are implementation details");

    rule.Check(Architecture);
}
```

## Cycle Detection

### No Circular Dependencies

```csharp
[Fact]
public void Layers_ShouldHaveNoCycles()
{
    IArchRule rule = Slices()
        .Matching("YourSolution.(*)..")
        .Should().BeFreeOfCycles();

    rule.Check(Architecture);
}

[Fact]
public void Modules_ShouldHaveNoCycles()
{
    IArchRule rule = Slices()
        .Matching("YourSolution.Modules.(*)..")
        .Should().BeFreeOfCycles();

    rule.Check(Architecture);
}
```

## Custom Conditions

### Extending with Custom Rules

```csharp
public static class CustomConditions
{
    public static ICondition<Class> HavePrivateConstructor()
    {
        return new SimpleCondition<Class>(
            cls => cls.GetConstructors().Any(c => !c.IsPublic),
            "have a private constructor",
            "does not have a private constructor"
        );
    }
}

[Fact]
public void ValueObjects_ShouldHave_PrivateConstructor()
{
    IArchRule rule = Classes()
        .That().Inherit(typeof(ValueObject))
        .Should().HavePrivateConstructor();

    rule.Check(Architecture);
}
```

## Best Practices

1. **Cache Architecture** - Build architecture once as static field
2. **Name providers descriptively** - .As("Domain Layer") improves error messages
3. **Use Because()** - Document why rules exist
4. **Group related rules** - Organize into focused test classes
5. **Start strict, loosen if needed** - Easier to relax than tighten

## Performance Considerations

- Loading architecture is expensive - do it once per test class
- Use namespaces filters to reduce scope when possible
- Consider running architecture tests in a separate test category

---

**Related:** `netarchtest-patterns.md`, `dependency-rules.md`
