# ABAC Implementation Reference

This reference provides a comprehensive XACML-style Attribute-Based Access Control implementation.

## XACML Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        Policy Administration Point (PAP)            │
│                    (Policy creation and management)                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Policy Decision Point (PDP)                   │
│                    (Evaluates policies, returns decisions)           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
┌─────────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐
│ Policy Information  │ │ Policy          │ │ Context Handler          │
│ Point (PIP)         │ │ Retrieval       │ │ (Formats requests)       │
│ (Attribute lookup)  │ │ Point (PRP)     │ │                         │
└─────────────────────┘ └─────────────────┘ └─────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Policy Enforcement Point (PEP)                   │
│                   (Enforces decisions at resource)                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Data Structures

```csharp
using System.Collections.Frozen;
using System.Text.RegularExpressions;

/// <summary>
/// Policy effect (XACML-style).
/// </summary>
public enum Effect
{
    Permit,
    Deny,
    NotApplicable,
    Indeterminate
}

/// <summary>
/// Policy combining algorithms.
/// </summary>
public enum CombiningAlgorithm
{
    DenyOverrides,
    PermitOverrides,
    FirstApplicable,
    OnlyOneApplicable,
    DenyUnlessPermit,
    PermitUnlessDeny
}

/// <summary>
/// An attribute with category and value.
/// </summary>
public sealed record Attribute(
    string Category,      // subject, resource, action, environment
    string Id,
    object? Value,
    string DataType = "string",
    string? Issuer = null);

/// <summary>
/// Access request with all attributes.
/// </summary>
public sealed class AttributeRequest
{
    public Dictionary<string, Attribute> SubjectAttributes { get; init; } = [];
    public Dictionary<string, Attribute> ResourceAttributes { get; init; } = [];
    public Dictionary<string, Attribute> ActionAttributes { get; init; } = [];
    public Dictionary<string, Attribute> EnvironmentAttributes { get; init; } = [];

    /// <summary>
    /// Get attribute by category and ID.
    /// </summary>
    public Attribute? GetAttribute(string category, string attrId)
    {
        var attrMap = category switch
        {
            "subject" => SubjectAttributes,
            "resource" => ResourceAttributes,
            "action" => ActionAttributes,
            "environment" => EnvironmentAttributes,
            _ => null
        };

        return attrMap?.GetValueOrDefault(attrId);
    }

    /// <summary>
    /// Get attribute value with optional default.
    /// </summary>
    public object? GetValue(string category, string attrId, object? defaultValue = null)
    {
        var attr = GetAttribute(category, attrId);
        return attr?.Value ?? defaultValue;
    }
}

/// <summary>
/// Authorization decision.
/// </summary>
public sealed record Decision(
    Effect Effect,
    string Status = "ok",
    IReadOnlyList<Dictionary<string, object>>? Obligations = null,
    IReadOnlyList<Dictionary<string, object>>? Advice = null)
{
    public IReadOnlyList<Dictionary<string, object>> Obligations { get; init; } =
        Obligations ?? [];
    public IReadOnlyList<Dictionary<string, object>> Advice { get; init; } =
        Advice ?? [];
}
```

## Conditions and Matching

```csharp
/// <summary>
/// Abstract condition for policy matching.
/// </summary>
public abstract class Condition
{
    public abstract bool Evaluate(AttributeRequest request);
}

/// <summary>
/// Check if attribute equals a value.
/// </summary>
public sealed class AttributeEquals(string category, string attrId, object? expectedValue) : Condition
{
    public override bool Evaluate(AttributeRequest request)
    {
        var actual = request.GetValue(category, attrId);
        return Equals(actual, expectedValue);
    }
}

/// <summary>
/// Check if attribute is in a set.
/// </summary>
public sealed class AttributeIn(string category, string attrId, IReadOnlySet<object> allowedValues) : Condition
{
    public override bool Evaluate(AttributeRequest request)
    {
        var actual = request.GetValue(category, attrId);
        return actual is not null && allowedValues.Contains(actual);
    }
}

/// <summary>
/// Check if attribute (list) contains a value.
/// </summary>
public sealed class AttributeContains(string category, string attrId, object searchValue) : Condition
{
    public override bool Evaluate(AttributeRequest request)
    {
        var actual = request.GetValue(category, attrId);
        return actual switch
        {
            IEnumerable<object> list => list.Contains(searchValue),
            IEnumerable<string> strings when searchValue is string s => strings.Contains(s),
            _ => false
        };
    }
}

/// <summary>
/// Check if attribute matches regex.
/// </summary>
public sealed class AttributeMatches : Condition
{
    private readonly string _category;
    private readonly string _attrId;
    private readonly Regex _pattern;

    public AttributeMatches(string category, string attrId, string pattern)
    {
        _category = category;
        _attrId = attrId;
        _pattern = new Regex(pattern, RegexOptions.Compiled);
    }

    public override bool Evaluate(AttributeRequest request)
    {
        var actual = request.GetValue(_category, _attrId, "");
        return actual is string s && _pattern.IsMatch(s);
    }
}

/// <summary>
/// Numeric comparison: greater than threshold.
/// </summary>
public sealed class AttributeGreaterThan(string category, string attrId, double threshold) : Condition
{
    public override bool Evaluate(AttributeRequest request)
    {
        var actual = request.GetValue(category, attrId, 0);
        return actual switch
        {
            double d => d > threshold,
            int i => i > threshold,
            decimal dec => (double)dec > threshold,
            string s when double.TryParse(s, out var parsed) => parsed > threshold,
            _ => false
        };
    }
}

/// <summary>
/// Numeric comparison: less than threshold.
/// </summary>
public sealed class AttributeLessThan(string category, string attrId, double threshold) : Condition
{
    public override bool Evaluate(AttributeRequest request)
    {
        var actual = request.GetValue(category, attrId, 0);
        return actual switch
        {
            double d => d < threshold,
            int i => i < threshold,
            decimal dec => (double)dec < threshold,
            string s when double.TryParse(s, out var parsed) => parsed < threshold,
            _ => false
        };
    }
}

/// <summary>
/// Check if current time is in range.
/// </summary>
public sealed class TimeInRange : Condition
{
    private readonly int _startHour;
    private readonly int _endHour;
    private readonly FrozenSet<DayOfWeek> _allowedDays;

    public TimeInRange(int startHour, int endHour, IEnumerable<DayOfWeek>? allowedDays = null)
    {
        _startHour = startHour;
        _endHour = endHour;
        _allowedDays = (allowedDays ?? new[]
        {
            DayOfWeek.Monday, DayOfWeek.Tuesday, DayOfWeek.Wednesday,
            DayOfWeek.Thursday, DayOfWeek.Friday
        }).ToFrozenSet();
    }

    public override bool Evaluate(AttributeRequest request)
    {
        var now = DateTime.Now;
        if (!_allowedDays.Contains(now.DayOfWeek))
        {
            return false;
        }
        return _startHour <= now.Hour && now.Hour < _endHour;
    }
}

/// <summary>
/// Check if IP is in CIDR range (simplified prefix matching).
/// </summary>
public sealed class IpInRange : Condition
{
    private readonly string[] _prefixes;

    public IpInRange(IEnumerable<string> cidrRanges)
    {
        // In production, use System.Net.IPNetwork for proper CIDR matching
        _prefixes = cidrRanges
            .Select(cidr => string.Join(".", cidr.Split('/')[0].Split('.').Take(3)))
            .ToArray();
    }

    public override bool Evaluate(AttributeRequest request)
    {
        var ip = request.GetValue("environment", "ip_address", "") as string ?? "";
        return _prefixes.Any(prefix => ip.StartsWith(prefix, StringComparison.Ordinal));
    }
}
```

## Composite Conditions

```csharp
/// <summary>
/// Logical AND of conditions.
/// </summary>
public sealed class And(params Condition[] conditions) : Condition
{
    public override bool Evaluate(AttributeRequest request) =>
        conditions.All(c => c.Evaluate(request));
}

/// <summary>
/// Logical OR of conditions.
/// </summary>
public sealed class Or(params Condition[] conditions) : Condition
{
    public override bool Evaluate(AttributeRequest request) =>
        conditions.Any(c => c.Evaluate(request));
}

/// <summary>
/// Logical NOT of condition.
/// </summary>
public sealed class Not(Condition condition) : Condition
{
    public override bool Evaluate(AttributeRequest request) =>
        !condition.Evaluate(request);
}

/// <summary>
/// Compare two attributes for equality.
/// </summary>
public sealed class AttributeComparison(
    string category1, string attr1,
    string category2, string attr2) : Condition
{
    public override bool Evaluate(AttributeRequest request)
    {
        var val1 = request.GetValue(category1, attr1);
        var val2 = request.GetValue(category2, attr2);
        return Equals(val1, val2);
    }
}
```

## Rules and Policies

```csharp
/// <summary>
/// Action to perform on permit/deny.
/// </summary>
public sealed record Obligation(
    string ObligationId,
    Effect FulfillOn,
    Dictionary<string, object>? Parameters = null)
{
    public Dictionary<string, object> Parameters { get; init; } = Parameters ?? [];
}

/// <summary>
/// A single rule with target, condition, and effect.
/// </summary>
public sealed class Rule(
    string ruleId,
    Effect effect,
    string description = "",
    Condition? target = null,
    Condition? condition = null,
    IReadOnlyList<Obligation>? obligations = null)
{
    public string RuleId { get; } = ruleId;
    public Effect Effect { get; } = effect;
    public string Description { get; } = description;
    public Condition? Target { get; } = target;
    public Condition? Condition { get; } = condition;
    public IReadOnlyList<Obligation> Obligations { get; } = obligations ?? [];

    /// <summary>
    /// Evaluate rule against request.
    /// </summary>
    public Effect Evaluate(AttributeRequest request)
    {
        // Check target
        if (Target is not null && !Target.Evaluate(request))
        {
            return Effect.NotApplicable;
        }

        // Check condition
        if (Condition is not null)
        {
            try
            {
                return Condition.Evaluate(request)
                    ? Effect
                    : Effect.NotApplicable;
            }
            catch
            {
                return Effect.Indeterminate;
            }
        }

        return Effect;
    }
}

/// <summary>
/// A policy containing multiple rules.
/// </summary>
public sealed class Policy(
    string policyId,
    string description = "",
    Condition? target = null,
    IReadOnlyList<Rule>? rules = null,
    CombiningAlgorithm combiningAlgorithm = CombiningAlgorithm.DenyOverrides,
    IReadOnlyList<Obligation>? obligations = null)
{
    public string PolicyId { get; } = policyId;
    public string Description { get; } = description;
    public Condition? Target { get; } = target;
    public IReadOnlyList<Rule> Rules { get; } = rules ?? [];
    public CombiningAlgorithm CombiningAlgorithm { get; } = combiningAlgorithm;
    public IReadOnlyList<Obligation> Obligations { get; } = obligations ?? [];

    /// <summary>
    /// Evaluate policy using combining algorithm.
    /// </summary>
    public Decision Evaluate(AttributeRequest request)
    {
        // Check target
        if (Target is not null && !Target.Evaluate(request))
        {
            return new Decision(Effect.NotApplicable);
        }

        // Evaluate all rules
        var ruleEffects = new List<(Rule Rule, Effect Effect)>();
        foreach (var rule in Rules)
        {
            var effect = rule.Evaluate(request);
            if (effect != Effect.NotApplicable)
            {
                ruleEffects.Add((rule, effect));
            }
        }

        // Apply combining algorithm
        var finalEffect = CombineEffects(ruleEffects);

        // Collect obligations
        var collectedObligations = new List<Dictionary<string, object>>();
        foreach (var (rule, _) in ruleEffects)
        {
            foreach (var obligation in rule.Obligations)
            {
                if (obligation.FulfillOn == finalEffect)
                {
                    collectedObligations.Add(new Dictionary<string, object>
                    {
                        ["id"] = obligation.ObligationId,
                        ["parameters"] = obligation.Parameters
                    });
                }
            }
        }

        return new Decision(finalEffect, Obligations: collectedObligations);
    }

    private Effect CombineEffects(List<(Rule Rule, Effect Effect)> ruleEffects)
    {
        if (ruleEffects.Count == 0)
        {
            return Effect.NotApplicable;
        }

        var effects = ruleEffects.Select(re => re.Effect).ToList();

        return CombiningAlgorithm switch
        {
            CombiningAlgorithm.DenyOverrides => effects.Contains(Effect.Deny) ? Effect.Deny
                : effects.Contains(Effect.Permit) ? Effect.Permit
                : effects.Contains(Effect.Indeterminate) ? Effect.Indeterminate
                : Effect.NotApplicable,

            CombiningAlgorithm.PermitOverrides => effects.Contains(Effect.Permit) ? Effect.Permit
                : effects.Contains(Effect.Deny) ? Effect.Deny
                : effects.Contains(Effect.Indeterminate) ? Effect.Indeterminate
                : Effect.NotApplicable,

            CombiningAlgorithm.FirstApplicable => ruleEffects
                .Select(re => re.Effect)
                .FirstOrDefault(e => e is Effect.Permit or Effect.Deny, Effect.NotApplicable),

            CombiningAlgorithm.DenyUnlessPermit => effects.Contains(Effect.Permit)
                ? Effect.Permit : Effect.Deny,

            CombiningAlgorithm.PermitUnlessDeny => effects.Contains(Effect.Deny)
                ? Effect.Deny : Effect.Permit,

            _ => Effect.Indeterminate
        };
    }
}

/// <summary>
/// A set of policies.
/// </summary>
public sealed class PolicySet(
    string policySetId,
    string description = "",
    Condition? target = null,
    IReadOnlyList<Policy>? policies = null,
    CombiningAlgorithm combiningAlgorithm = CombiningAlgorithm.DenyOverrides)
{
    public string PolicySetId { get; } = policySetId;
    public string Description { get; } = description;
    public Condition? Target { get; } = target;
    public IReadOnlyList<Policy> Policies { get; } = policies ?? [];
    public CombiningAlgorithm CombiningAlgorithm { get; } = combiningAlgorithm;
}
```

## Policy Decision Point (PDP)

```csharp
/// <summary>
/// Central PDP for evaluating all policies.
/// </summary>
public sealed class PolicyDecisionPoint(Effect defaultDecision = Effect.Deny)
{
    private readonly List<PolicySet> _policySets = [];
    private readonly List<Policy> _policies = [];
    private PolicyInformationPoint? _pip;

    public void AddPolicy(Policy policy) => _policies.Add(policy);

    public void AddPolicySet(PolicySet policySet) => _policySets.Add(policySet);

    public void SetPip(PolicyInformationPoint pip) => _pip = pip;

    /// <summary>
    /// Evaluate request against all policies.
    /// </summary>
    public Decision Evaluate(AttributeRequest request)
    {
        // Enrich request with PIP attributes
        if (_pip is not null)
        {
            request = _pip.EnrichRequest(request);
        }

        var allDecisions = new List<Decision>();

        // Evaluate policy sets
        foreach (var policySet in _policySets)
        {
            var decision = EvaluatePolicySet(policySet, request);
            if (decision.Effect != Effect.NotApplicable)
            {
                allDecisions.Add(decision);
            }
        }

        // Evaluate standalone policies
        foreach (var policy in _policies)
        {
            var decision = policy.Evaluate(request);
            if (decision.Effect != Effect.NotApplicable)
            {
                allDecisions.Add(decision);
            }
        }

        // Combine all decisions (deny overrides)
        return CombineDecisions(allDecisions);
    }

    private Decision EvaluatePolicySet(PolicySet policySet, AttributeRequest request)
    {
        if (policySet.Target is not null && !policySet.Target.Evaluate(request))
        {
            return new Decision(Effect.NotApplicable);
        }

        var decisions = policySet.Policies.Select(p => p.Evaluate(request)).ToList();
        return CombineDecisionsWithAlgorithm(decisions, policySet.CombiningAlgorithm);
    }

    private Decision CombineDecisions(List<Decision> decisions) =>
        CombineDecisionsWithAlgorithm(decisions, CombiningAlgorithm.DenyOverrides);

    private Decision CombineDecisionsWithAlgorithm(
        List<Decision> decisions,
        CombiningAlgorithm algorithm)
    {
        if (decisions.Count == 0)
        {
            return new Decision(defaultDecision);
        }

        var effects = decisions.Select(d => d.Effect).ToList();
        var allObligations = decisions
            .SelectMany(d => d.Obligations)
            .ToList();

        var resultEffect = algorithm switch
        {
            CombiningAlgorithm.DenyOverrides => effects.Contains(Effect.Deny) ? Effect.Deny
                : effects.Contains(Effect.Permit) ? Effect.Permit
                : defaultDecision,

            CombiningAlgorithm.PermitOverrides => effects.Contains(Effect.Permit) ? Effect.Permit
                : effects.Contains(Effect.Deny) ? Effect.Deny
                : defaultDecision,

            _ => defaultDecision
        };

        return new Decision(resultEffect, Obligations: allObligations);
    }
}
```

## Policy Information Point (PIP)

```csharp
/// <summary>
/// Retrieves additional attributes for evaluation.
/// </summary>
public sealed class PolicyInformationPoint
{
    private readonly Dictionary<string, Func<AttributeRequest, object?>> _retrievers = [];
    private readonly Dictionary<string, (object? Value, DateTime ExpiresAt)> _cache = [];
    private readonly TimeSpan _cacheTtl = TimeSpan.FromSeconds(300);

    /// <summary>
    /// Register a function to retrieve an attribute.
    /// </summary>
    public void RegisterRetriever(string attributeId, Func<AttributeRequest, object?> retriever)
    {
        _retrievers[attributeId] = retriever;
    }

    /// <summary>
    /// Enrich request with additional attributes.
    /// </summary>
    public AttributeRequest EnrichRequest(AttributeRequest request)
    {
        foreach (var (attrId, retriever) in _retrievers)
        {
            try
            {
                var value = retriever(request);

                // Add to appropriate category based on attribute ID prefix
                if (attrId.StartsWith("subject."))
                {
                    var name = attrId[8..];
                    request.SubjectAttributes[name] = new Attribute("subject", name, value);
                }
                else if (attrId.StartsWith("resource."))
                {
                    var name = attrId[9..];
                    request.ResourceAttributes[name] = new Attribute("resource", name, value);
                }
                else if (attrId.StartsWith("environment."))
                {
                    var name = attrId[12..];
                    request.EnvironmentAttributes[name] = new Attribute("environment", name, value);
                }
            }
            catch
            {
                // Attribute retrieval failed, continue
            }
        }

        return request;
    }
}

// Example PIP retrievers
public static class AttributeRetrievers
{
    /// <summary>
    /// Look up user's department from database.
    /// </summary>
    public static object? GetUserDepartment(AttributeRequest request)
    {
        var userId = request.GetValue("subject", "id")?.ToString();
        // In production: database lookup
        var departments = new Dictionary<string, string>
        {
            ["alice"] = "engineering",
            ["bob"] = "finance"
        };
        return userId is not null && departments.TryGetValue(userId, out var dept)
            ? dept
            : "unknown";
    }

    /// <summary>
    /// Look up user's groups from LDAP/AD.
    /// </summary>
    public static object? GetUserGroups(AttributeRequest request)
    {
        var userId = request.GetValue("subject", "id")?.ToString();
        // In production: LDAP lookup
        var groups = new Dictionary<string, List<string>>
        {
            ["alice"] = ["developers", "team-alpha"],
            ["bob"] = ["finance", "managers"]
        };
        return userId is not null && groups.TryGetValue(userId, out var userGroups)
            ? userGroups
            : new List<string>();
    }

    /// <summary>
    /// Look up resource classification.
    /// </summary>
    public static object? GetResourceClassification(AttributeRequest request)
    {
        var resourceId = request.GetValue("resource", "id")?.ToString();
        // In production: metadata service lookup
        var classifications = new Dictionary<string, string>
        {
            ["doc-123"] = "confidential",
            ["doc-456"] = "public"
        };
        return resourceId is not null && classifications.TryGetValue(resourceId, out var classification)
            ? classification
            : "internal";
    }
}

// Usage
var pip = new PolicyInformationPoint();
pip.RegisterRetriever("subject.department", AttributeRetrievers.GetUserDepartment);
pip.RegisterRetriever("subject.groups", AttributeRetrievers.GetUserGroups);
pip.RegisterRetriever("resource.classification", AttributeRetrievers.GetResourceClassification);
```

## Policy Enforcement Point (PEP)

```csharp
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;
using Microsoft.Extensions.Logging;

/// <summary>
/// Enforces authorization decisions.
/// </summary>
public sealed class PolicyEnforcementPoint(
    PolicyDecisionPoint pdp,
    ILogger<PolicyEnforcementPoint> logger)
{
    /// <summary>
    /// Enforce policy and return decision.
    /// </summary>
    public bool Enforce(AttributeRequest accessRequest)
    {
        var decision = pdp.Evaluate(accessRequest);

        // Handle obligations
        foreach (var obligation in decision.Obligations)
        {
            FulfillObligation(obligation);
        }

        return decision.Effect == Effect.Permit;
    }

    private void FulfillObligation(Obligation obligation)
    {
        switch (obligation.Id)
        {
            case "log_access":
                // Log access to audit system
                logger.LogInformation("AUDIT: Access logged with params {Params}",
                    obligation.Parameters);
                break;

            case "notify_admin":
                // Send notification
                logger.LogWarning("NOTIFY: Admin notified with params {Params}",
                    obligation.Parameters);
                break;

            case "increment_counter":
                // Rate limiting counter
                logger.LogInformation("COUNTER: Incremented for {Params}",
                    obligation.Parameters);
                break;
        }
    }
}

/// <summary>
/// ASP.NET Core authorization filter for PEP.
/// </summary>
public sealed class AbacAuthorizationAttribute(string action, string resourceType)
    : ActionFilterAttribute
{
    public override void OnActionExecuting(ActionExecutingContext context)
    {
        var pep = context.HttpContext.RequestServices
            .GetRequiredService<PolicyEnforcementPoint>();

        var httpContext = context.HttpContext;
        var user = httpContext.User;

        // Extract resource ID from route
        context.RouteData.Values.TryGetValue("resourceId", out var resourceIdObj);
        var resourceId = resourceIdObj?.ToString();

        // Build attribute request
        var accessRequest = new AttributeRequest
        {
            SubjectAttributes = new Dictionary<string, Attribute>
            {
                ["id"] = new("subject", "id", user.Identity?.Name),
                ["roles"] = new("subject", "roles",
                    user.Claims.Where(c => c.Type == "role").Select(c => c.Value).ToList())
            },
            ActionAttributes = new Dictionary<string, Attribute>
            {
                ["id"] = new("action", "id", action)
            },
            ResourceAttributes = new Dictionary<string, Attribute>
            {
                ["type"] = new("resource", "type", resourceType),
                ["id"] = new("resource", "id", resourceId)
            },
            EnvironmentAttributes = new Dictionary<string, Attribute>
            {
                ["ip_address"] = new("environment", "ip_address",
                    httpContext.Connection.RemoteIpAddress?.ToString()),
                ["time"] = new("environment", "time", DateTime.UtcNow)
            }
        };

        if (!pep.Enforce(accessRequest))
        {
            context.Result = new ForbidResult();
            return;
        }

        base.OnActionExecuting(context);
    }
}

// Usage in ASP.NET Core controller
[ApiController]
[Route("[controller]")]
public sealed class DocumentsController : ControllerBase
{
    [HttpGet("{resourceId}")]
    [AbacAuthorization("read", "document")]
    public IActionResult GetDocument(string resourceId)
    {
        return Ok(new { id = resourceId, content = "..." });
    }

    [HttpPut("{resourceId}")]
    [AbacAuthorization("update", "document")]
    public IActionResult UpdateDocument(string resourceId)
    {
        return Ok(new { id = resourceId, updated = true });
    }
}
```

## Complete Example

```csharp
// Build a complete ABAC system

// 1. Create policies
var expensePolicy = new Policy(
    "expense-approval-policy",
    "Expense approval based on amount and role",
    new AndCondition(
        new AttributeEquals("resource", "type", "expense"),
        new AttributeIn("action", "id", ["approve", "reject"])
    ),
    [
        // Rule 1: Anyone can approve expenses under $100
        new Rule(
            "small-expense-approval",
            Effect.Permit,
            new AttributeLessThan("resource", "amount", 100)
        ),
        // Rule 2: Managers can approve up to $1000
        new Rule(
            "manager-expense-approval",
            Effect.Permit,
            new AndCondition(
                new AttributeContains("subject", "roles", "manager"),
                new AttributeLessThan("resource", "amount", 1000)
            )
        ),
        // Rule 3: Directors can approve up to $10000
        new Rule(
            "director-expense-approval",
            Effect.Permit,
            new AndCondition(
                new AttributeContains("subject", "roles", "director"),
                new AttributeLessThan("resource", "amount", 10000)
            )
        ),
        // Rule 4: CFO can approve any amount
        new Rule(
            "cfo-expense-approval",
            Effect.Permit,
            new AttributeContains("subject", "roles", "cfo"),
            [
                new Obligation("log_access", Effect.Permit,
                    new Dictionary<string, object> { ["action"] = "large_expense_approval" })
            ]
        ),
        // Rule 5: Cannot approve own expenses
        new Rule(
            "no-self-approval",
            Effect.Deny,
            new AttributeComparison("subject", "id", "resource", "submitter_id")
        )
    ],
    CombiningAlgorithm.DenyOverrides
);

var timePolicy = new Policy(
    "business-hours-policy",
    "Restrict access to business hours",
    new AttributeEquals("resource", "sensitivity", "high"),
    [
        new Rule(
            "business-hours-only",
            Effect.Permit,
            new TimeInRange(9, 17, [DayOfWeek.Monday, DayOfWeek.Tuesday,
                DayOfWeek.Wednesday, DayOfWeek.Thursday, DayOfWeek.Friday])
        ),
        new Rule(
            "deny-outside-hours",
            Effect.Deny,
            new NotCondition(new TimeInRange(9, 17, [DayOfWeek.Monday, DayOfWeek.Tuesday,
                DayOfWeek.Wednesday, DayOfWeek.Thursday, DayOfWeek.Friday])),
            [
                new Obligation("notify_admin", Effect.Deny,
                    new Dictionary<string, object> { ["reason"] = "after_hours_access_attempt" })
            ]
        )
    ]
);

// 2. Create PDP
var pdp = new PolicyDecisionPoint(Effect.Deny);
pdp.AddPolicy(expensePolicy);
pdp.AddPolicy(timePolicy);

// 3. Create PIP
var pip = new PolicyInformationPoint();
pip.RegisterRetriever("subject.department", AttributeRetrievers.GetUserDepartment);
pdp.SetPip(pip);

// 4. Create PEP
var loggerFactory = LoggerFactory.Create(builder => builder.AddConsole());
var pep = new PolicyEnforcementPoint(pdp, loggerFactory.CreateLogger<PolicyEnforcementPoint>());

// 5. Test request
var testRequest = new AttributeRequest
{
    SubjectAttributes = new Dictionary<string, Attribute>
    {
        ["id"] = new("subject", "id", "bob"),
        ["roles"] = new("subject", "roles", new List<string> { "manager" })
    },
    ActionAttributes = new Dictionary<string, Attribute>
    {
        ["id"] = new("action", "id", "approve")
    },
    ResourceAttributes = new Dictionary<string, Attribute>
    {
        ["type"] = new("resource", "type", "expense"),
        ["id"] = new("resource", "id", "exp-789"),
        ["amount"] = new("resource", "amount", 500),
        ["submitter_id"] = new("resource", "submitter_id", "alice")
    },
    EnvironmentAttributes = new Dictionary<string, Attribute>
    {
        ["ip_address"] = new("environment", "ip_address", "10.0.1.50")
    }
};

var decision = pdp.Evaluate(testRequest);
Console.WriteLine($"Decision: {decision.Effect}");
```

## Security Checklist

### Policy Design

- [ ] Default deny policy in place
- [ ] All sensitive actions have explicit policies
- [ ] Policies tested with positive and negative cases
- [ ] Combining algorithms chosen appropriately

### Attribute Management

- [ ] Attribute sources documented and secured
- [ ] PIP retrievers have appropriate error handling
- [ ] Sensitive attributes encrypted in transit
- [ ] Attribute caching has appropriate TTL

### Enforcement

- [ ] PEP at all access points
- [ ] Obligations fulfilled reliably
- [ ] Failed evaluations result in deny
- [ ] Audit logging comprehensive

### Operations

- [ ] Policy version control
- [ ] Policy testing before deployment
- [ ] Monitoring for policy evaluation failures
- [ ] Regular policy reviews
