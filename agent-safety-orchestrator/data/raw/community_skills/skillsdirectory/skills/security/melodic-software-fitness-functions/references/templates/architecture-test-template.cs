// Architecture Test Template
// Generated scaffold for architecture fitness functions
// Customize namespace, assemblies, and rules for your project

using System.Reflection;
using NetArchTest.Rules;
using Xunit;

namespace YourSolution.ArchitectureTests;

/// <summary>
/// Architecture fitness functions to enforce architectural constraints.
/// Run these tests in CI/CD to catch violations early.
/// </summary>
[Trait("Category", "Architecture")]
public class ArchitectureTests
{
    #region Assembly References

    // TODO: Replace with your actual type references
    private static readonly Assembly DomainAssembly = typeof(Domain.Entity).Assembly;
    private static readonly Assembly ApplicationAssembly = typeof(Application.ICommand).Assembly;
    private static readonly Assembly InfrastructureAssembly = typeof(Infrastructure.DbContext).Assembly;
    private static readonly Assembly ApiAssembly = typeof(Api.Controllers.BaseController).Assembly;

    #endregion

    #region Layer Dependency Rules

    [Fact]
    public void Domain_ShouldNotDependOn_Application()
    {
        var result = Types.InAssembly(DomainAssembly)
            .ShouldNot()
            .HaveDependencyOn("YourSolution.Application")
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Domain depends on Application", result));
    }

    [Fact]
    public void Domain_ShouldNotDependOn_Infrastructure()
    {
        var result = Types.InAssembly(DomainAssembly)
            .ShouldNot()
            .HaveDependencyOn("YourSolution.Infrastructure")
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Domain depends on Infrastructure", result));
    }

    [Fact]
    public void Domain_ShouldNotDependOn_Api()
    {
        var result = Types.InAssembly(DomainAssembly)
            .ShouldNot()
            .HaveDependencyOn("YourSolution.Api")
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Domain depends on Api", result));
    }

    [Fact]
    public void Application_ShouldNotDependOn_Infrastructure()
    {
        var result = Types.InAssembly(ApplicationAssembly)
            .ShouldNot()
            .HaveDependencyOn("YourSolution.Infrastructure")
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Application depends on Infrastructure", result));
    }

    [Fact]
    public void Application_ShouldNotDependOn_Api()
    {
        var result = Types.InAssembly(ApplicationAssembly)
            .ShouldNot()
            .HaveDependencyOn("YourSolution.Api")
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Application depends on Api", result));
    }

    #endregion

    #region Technology Isolation Rules

    [Fact]
    public void Domain_ShouldNotUse_EntityFramework()
    {
        var result = Types.InAssembly(DomainAssembly)
            .ShouldNot()
            .HaveDependencyOnAny(
                "Microsoft.EntityFrameworkCore",
                "Microsoft.EntityFrameworkCore.Relational"
            )
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Domain uses Entity Framework", result));
    }

    [Fact]
    public void Domain_ShouldNotUse_AspNetCore()
    {
        var result = Types.InAssembly(DomainAssembly)
            .ShouldNot()
            .HaveDependencyOnAny(
                "Microsoft.AspNetCore",
                "Microsoft.AspNetCore.Mvc",
                "Microsoft.AspNetCore.Http"
            )
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Domain uses ASP.NET Core", result));
    }

    #endregion

    #region Naming Convention Rules

    [Fact]
    public void Handlers_ShouldEndWith_Handler()
    {
        var result = Types.InAssembly(ApplicationAssembly)
            .That()
            .ImplementInterface(typeof(MediatR.IRequestHandler<,>))
            .Should()
            .HaveNameEndingWith("Handler")
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Handler naming violation", result));
    }

    [Fact]
    public void Repositories_ShouldEndWith_Repository()
    {
        var result = Types.InAssembly(InfrastructureAssembly)
            .That()
            .HaveNameEndingWith("Repository")
            .Should()
            .ImplementInterface(typeof(Domain.IRepository<>))
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Repository implementation violation", result));
    }

    [Fact]
    public void Controllers_ShouldEndWith_Controller()
    {
        var result = Types.InAssembly(ApiAssembly)
            .That()
            .Inherit(typeof(Microsoft.AspNetCore.Mvc.ControllerBase))
            .Should()
            .HaveNameEndingWith("Controller")
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Controller naming violation", result));
    }

    #endregion

    #region Interface Implementation Rules

    [Fact]
    public void Entities_ShouldImplement_IEntity()
    {
        var result = Types.InAssembly(DomainAssembly)
            .That()
            .ResideInNamespace("YourSolution.Domain.Entities")
            .And()
            .AreClasses()
            .Should()
            .ImplementInterface(typeof(Domain.IEntity))
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Entity interface violation", result));
    }

    [Fact]
    public void ValueObjects_ShouldBeSealed()
    {
        var result = Types.InAssembly(DomainAssembly)
            .That()
            .Inherit(typeof(Domain.ValueObject))
            .Should()
            .BeSealed()
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("ValueObject sealing violation", result));
    }

    #endregion

    #region Module Isolation Rules (for Modular Monolith)

    // TODO: Add your module assemblies
    // private static readonly Assembly OrderingCore = typeof(Ordering.Order).Assembly;
    // private static readonly Assembly InventoryCore = typeof(Inventory.Product).Assembly;

    // [Fact]
    // public void OrderingModule_ShouldNotDependOn_InventoryCore()
    // {
    //     var result = Types.InAssembly(OrderingCore)
    //         .ShouldNot()
    //         .HaveDependencyOn("Inventory.Core")
    //         .GetResult();
    //
    //     Assert.True(result.IsSuccessful,
    //         FormatFailures("Cross-module dependency violation", result));
    // }

    #endregion

    #region Attribute Rules

    [Fact]
    public void Controllers_ShouldHave_ApiControllerAttribute()
    {
        var result = Types.InAssembly(ApiAssembly)
            .That()
            .Inherit(typeof(Microsoft.AspNetCore.Mvc.ControllerBase))
            .Should()
            .HaveCustomAttribute(typeof(Microsoft.AspNetCore.Mvc.ApiControllerAttribute))
            .GetResult();

        Assert.True(result.IsSuccessful,
            FormatFailures("Controller attribute violation", result));
    }

    #endregion

    #region Helper Methods

    private static string FormatFailures(string message, TestResult result)
    {
        if (result.IsSuccessful || result.FailingTypeNames == null)
            return message;

        var failures = string.Join(", ", result.FailingTypeNames.Take(10));
        var count = result.FailingTypeNames.Count();

        return count > 10
            ? $"{message}: {failures} (and {count - 10} more)"
            : $"{message}: {failures}";
    }

    #endregion
}

#region Custom Rules Extension Example

/// <summary>
/// Example of custom rule predicates for complex validations.
/// </summary>
public static class CustomRules
{
    public static bool HasPrivateConstructor(this Type type)
    {
        return type.GetConstructors(BindingFlags.NonPublic | BindingFlags.Instance)
            .Any();
    }
}

#endregion
