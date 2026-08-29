# NetArchTest Patterns

## Overview

NetArchTest is a .NET library for creating tests that enforce architectural conventions. It provides a fluent API for defining rules about types, dependencies, and naming conventions.

## Installation

```bash
dotnet add package NetArchTest.Rules
```

## Basic Structure

```csharp
using NetArchTest.Rules;

public class ArchitectureTests
{
    private readonly Assembly _domainAssembly = typeof(Order).Assembly;
    private readonly Assembly _applicationAssembly = typeof(OrderHandler).Assembly;
    private readonly Assembly _infrastructureAssembly = typeof(OrderRepository).Assembly;

    [Fact]
    public void Example_Rule()
    {
        var result = Types.InAssembly(_domainAssembly)
            .That()        // Optional filter
            .Should()      // Define expectation
            .GetResult();  // Execute and get result

        Assert.True(result.IsSuccessful,
            string.Join(", ", result.FailingTypeNames ?? Array.Empty<string>()));
    }
}
```

## Dependency Rules

### No Dependency On Specific Assembly

```csharp
[Fact]
public void Domain_ShouldNotDependOn_EntityFramework()
{
    var result = Types.InAssembly(_domainAssembly)
        .ShouldNot()
        .HaveDependencyOn("Microsoft.EntityFrameworkCore")
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

### No Dependency On Multiple Assemblies

```csharp
[Fact]
public void Domain_ShouldNotDependOn_InfrastructureConcerns()
{
    var result = Types.InAssembly(_domainAssembly)
        .ShouldNot()
        .HaveDependencyOnAny(
            "Microsoft.EntityFrameworkCore",
            "Microsoft.Extensions.Logging",
            "System.Net.Http",
            "Newtonsoft.Json"
        )
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

### Only Depend On Specific Assemblies

```csharp
[Fact]
public void Domain_ShouldOnlyDependOn_CoreFramework()
{
    var result = Types.InAssembly(_domainAssembly)
        .Should()
        .OnlyHaveDependenciesOn(
            "System",
            "YourSolution.SharedKernel"
        )
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Namespace Rules

### Types In Namespace Should Follow Rules

```csharp
[Fact]
public void DomainLayer_ShouldNotReference_ApplicationLayer()
{
    var result = Types.InAssembly(_domainAssembly)
        .That()
        .ResideInNamespace("YourSolution.Domain")
        .ShouldNot()
        .HaveDependencyOn("YourSolution.Application")
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

### Namespace Containment

```csharp
[Fact]
public void AllTypes_ShouldResideIn_CorrectNamespace()
{
    var result = Types.InAssembly(_domainAssembly)
        .Should()
        .ResideInNamespaceStartingWith("YourSolution.Domain")
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Naming Convention Rules

### Class Name Endings

```csharp
[Fact]
public void Handlers_ShouldEndWith_Handler()
{
    var result = Types.InAssembly(_applicationAssembly)
        .That()
        .ImplementInterface(typeof(IRequestHandler<,>))
        .Should()
        .HaveNameEndingWith("Handler")
        .GetResult();

    Assert.True(result.IsSuccessful);
}

[Fact]
public void Repositories_ShouldEndWith_Repository()
{
    var result = Types.InAssembly(_infrastructureAssembly)
        .That()
        .ImplementInterface(typeof(IRepository<>))
        .Should()
        .HaveNameEndingWith("Repository")
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

### Class Name Patterns

```csharp
[Fact]
public void Commands_ShouldEndWith_Command()
{
    var result = Types.InAssembly(_applicationAssembly)
        .That()
        .ImplementInterface(typeof(IRequest<>))
        .And()
        .AreNotInterfaces()
        .Should()
        .HaveNameEndingWith("Command")
        .Or()
        .HaveNameEndingWith("Query")
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Interface Implementation Rules

### Must Implement Interface

```csharp
[Fact]
public void Entities_ShouldImplement_IEntity()
{
    var result = Types.InAssembly(_domainAssembly)
        .That()
        .ResideInNamespace("YourSolution.Domain.Entities")
        .And()
        .AreClasses()
        .Should()
        .ImplementInterface(typeof(IEntity))
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

### Should Not Implement Interface

```csharp
[Fact]
public void ValueObjects_ShouldNotImplement_IEntity()
{
    var result = Types.InAssembly(_domainAssembly)
        .That()
        .Inherit(typeof(ValueObject))
        .ShouldNot()
        .ImplementInterface(typeof(IEntity))
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Inheritance Rules

### Must Inherit From Base Class

```csharp
[Fact]
public void Aggregates_ShouldInheritFrom_AggregateRoot()
{
    var result = Types.InAssembly(_domainAssembly)
        .That()
        .HaveNameEndingWith("Aggregate")
        .Should()
        .Inherit(typeof(AggregateRoot))
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Attribute Rules

### Must Have Attribute

```csharp
[Fact]
public void Controllers_ShouldHave_ApiControllerAttribute()
{
    var result = Types.InAssembly(_apiAssembly)
        .That()
        .Inherit(typeof(ControllerBase))
        .Should()
        .HaveCustomAttribute(typeof(ApiControllerAttribute))
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Visibility Rules

### Should Be Sealed

```csharp
[Fact]
public void ValueObjects_ShouldBeSealed()
{
    var result = Types.InAssembly(_domainAssembly)
        .That()
        .Inherit(typeof(ValueObject))
        .Should()
        .BeSealed()
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

### Should Not Be Public

```csharp
[Fact]
public void InternalServices_ShouldNotBePublic()
{
    var result = Types.InAssembly(_infrastructureAssembly)
        .That()
        .HaveNameEndingWith("Internal")
        .ShouldNot()
        .BePublic()
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Module Isolation Rules

### Cross-Module Dependency Prevention

```csharp
[Theory]
[InlineData(typeof(Order), "Inventory.Core")]
[InlineData(typeof(Order), "Shipping.Core")]
[InlineData(typeof(Product), "Ordering.Core")]
[InlineData(typeof(Product), "Shipping.Core")]
public void Modules_ShouldNotCrossReference(Type moduleType, string forbiddenNamespace)
{
    var result = Types.InAssembly(moduleType.Assembly)
        .ShouldNot()
        .HaveDependencyOn(forbiddenNamespace)
        .GetResult();

    Assert.True(result.IsSuccessful,
        $"{moduleType.Assembly.GetName().Name} depends on {forbiddenNamespace}");
}
```

### DataTransfer Project Rules

```csharp
[Fact]
public void DataTransfer_ShouldOnlyContain_DTOs()
{
    var result = Types.InAssembly(typeof(OrderDto).Assembly)
        .That()
        .AreClasses()
        .And()
        .AreNotNested()
        .Should()
        .BeSealed()
        .And()
        .HaveNameEndingWith("Dto")
        .Or()
        .HaveNameEndingWith("Event")
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Combining Rules

### Complex Rule Combinations

```csharp
[Fact]
public void ApplicationServices_ShouldFollowConventions()
{
    var result = Types.InAssembly(_applicationAssembly)
        .That()
        .ResideInNamespace("YourSolution.Application.Services")
        .And()
        .AreClasses()
        .Should()
        .BePublic()
        .And()
        .HaveNameEndingWith("Service")
        .And()
        .ImplementInterface(typeof(IService))
        .GetResult();

    Assert.True(result.IsSuccessful);
}
```

## Custom Predicates

### Using Custom Logic

```csharp
[Fact]
public void Handlers_ShouldHave_SinglePublicMethod()
{
    var handlers = Types.InAssembly(_applicationAssembly)
        .That()
        .ImplementInterface(typeof(IRequestHandler<,>))
        .GetTypes();

    foreach (var handler in handlers)
    {
        var publicMethods = handler.GetMethods(BindingFlags.Public | BindingFlags.Instance)
            .Where(m => !m.IsSpecialName && m.DeclaringType == handler)
            .ToList();

        Assert.Single(publicMethods, $"{handler.Name} should have exactly one public method");
    }
}
```

## Best Practices

1. **Organize by concern** - Group related rules in test classes
2. **Use Theory for variations** - Test multiple modules with same rule
3. **Clear failure messages** - Include type names in assertions
4. **Assembly references** - Store assemblies as class fields
5. **Combine strategically** - Don't over-complicate single rules

## Common Pitfalls

- **Forgetting .GetResult()** - Rules don't execute without it
- **Overly broad rules** - Filter types appropriately with .That()
- **Missing assembly references** - Ensure test project references all needed assemblies

---

**Related:** `archunitnet-patterns.md`, `dependency-rules.md`
