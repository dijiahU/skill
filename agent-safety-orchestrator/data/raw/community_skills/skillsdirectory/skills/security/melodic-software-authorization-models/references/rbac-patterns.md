# RBAC Patterns Reference

This reference provides advanced Role-Based Access Control patterns including constraints, separation of duties, and multi-tenancy.

## RBAC Models (NIST Standard)

### RBAC0 - Core RBAC

```csharp
using System.Collections.Frozen;

/// <summary>
/// Fine-grained permissions for RBAC.
/// </summary>
[Flags]
public enum Permission
{
    None = 0,
    Create = 1,
    Read = 2,
    Update = 4,
    Delete = 8,
    Approve = 16,
    Publish = 32,
    Admin = 64
}

/// <summary>
/// User entity.
/// </summary>
public sealed record User(string Id, string Name, string Email);

/// <summary>
/// Role with permissions.
/// </summary>
public sealed record Role(
    string Id,
    string Name,
    Permission Permissions,
    string Description = "");

/// <summary>
/// User session with activated roles.
/// </summary>
public sealed record Session(User User, FrozenSet<Role> ActiveRoles);

/// <summary>
/// Core RBAC implementation (RBAC0 - NIST standard).
/// </summary>
public class Rbac0
{
    private readonly Dictionary<string, User> _users = [];
    private readonly Dictionary<string, Role> _roles = [];
    private readonly Dictionary<string, HashSet<string>> _userRoleAssignments = [];

    public void CreateUser(User user)
    {
        _users[user.Id] = user;
        _userRoleAssignments[user.Id] = [];
    }

    public void CreateRole(Role role) => _roles[role.Id] = role;

    /// <summary>
    /// Assign a role to a user (UA relation).
    /// </summary>
    public void AssignRole(string userId, string roleId)
    {
        if (_userRoleAssignments.TryGetValue(userId, out var roles))
        {
            roles.Add(roleId);
        }
    }

    /// <summary>
    /// Revoke a role from a user.
    /// </summary>
    public void RevokeRole(string userId, string roleId)
    {
        if (_userRoleAssignments.TryGetValue(userId, out var roles))
        {
            roles.Remove(roleId);
        }
    }

    /// <summary>
    /// Create a session with activated roles.
    /// </summary>
    public Session CreateSession(string userId, ISet<string>? requestedRoles = null)
    {
        if (!_users.TryGetValue(userId, out var user))
        {
            throw new ArgumentException($"User {userId} not found", nameof(userId));
        }

        var assignedRoles = _userRoleAssignments.GetValueOrDefault(userId) ?? [];

        // Activate requested roles (or all assigned if none specified)
        var activeRoleIds = requestedRoles is not null
            ? assignedRoles.Intersect(requestedRoles)
            : assignedRoles;

        var activeRoles = activeRoleIds
            .Where(rid => _roles.ContainsKey(rid))
            .Select(rid => _roles[rid])
            .ToFrozenSet();

        return new Session(user, activeRoles);
    }

    /// <summary>
    /// Check if session has permission.
    /// </summary>
    public bool CheckPermission(Session session, Permission permission) =>
        session.ActiveRoles.Any(role => role.Permissions.HasFlag(permission));

    /// <summary>
    /// Get all permissions available in session.
    /// </summary>
    public Permission GetSessionPermissions(Session session) =>
        session.ActiveRoles.Aggregate(Permission.None, (acc, role) => acc | role.Permissions);
}
```

### RBAC1 - Hierarchical RBAC

```csharp
/// <summary>
/// Role with parent (inheritance).
/// </summary>
public sealed class HierarchicalRole(
    string id,
    string name,
    Permission permissions = Permission.None,
    HierarchicalRole? parent = null,
    string description = "")
{
    public string Id { get; } = id;
    public string Name { get; } = name;
    public Permission Permissions { get; } = permissions;
    public HierarchicalRole? Parent { get; } = parent;
    public string Description { get; } = description;

    /// <summary>
    /// Get permissions including inherited from ancestors.
    /// </summary>
    public Permission GetAllPermissions()
    {
        var allPerms = Permissions;
        if (Parent is not null)
        {
            allPerms |= Parent.GetAllPermissions();
        }
        return allPerms;
    }

    /// <summary>
    /// Get all ancestor roles.
    /// </summary>
    public IReadOnlyList<HierarchicalRole> GetAncestors()
    {
        var ancestors = new List<HierarchicalRole>();
        var current = Parent;
        while (current is not null)
        {
            ancestors.Add(current);
            current = current.Parent;
        }
        return ancestors;
    }
}

/// <summary>
/// Hierarchical RBAC with role inheritance (RBAC1).
/// </summary>
public class Rbac1 : Rbac0
{
    private readonly Dictionary<string, HierarchicalRole> _hierarchicalRoles = [];

    public void CreateHierarchicalRole(HierarchicalRole role) =>
        _hierarchicalRoles[role.Id] = role;

    /// <summary>
    /// Check permission considering role hierarchy.
    /// </summary>
    public bool CheckPermissionHierarchical(string userId, Permission permission)
    {
        var roleIds = GetUserRoleIds(userId);

        foreach (var roleId in roleIds)
        {
            if (_hierarchicalRoles.TryGetValue(roleId, out var role))
            {
                if (role.GetAllPermissions().HasFlag(permission))
                {
                    return true;
                }
            }
        }
        return false;
    }
}

// Example hierarchy:
//                     admin
//                       │
//             ┌─────────┴─────────┐
//             │                   │
//         manager             developer
//             │                   │
//         ┌───┴───┐               │
//         │       │               │
//     hr_lead   finance_lead   tech_lead

// Build hierarchy:
// var viewer = new HierarchicalRole("viewer", "Viewer", Permission.Read);
// var developer = new HierarchicalRole("developer", "Developer",
//     Permission.Create | Permission.Update, parent: viewer);
// var techLead = new HierarchicalRole("tech_lead", "Tech Lead",
//     Permission.Approve, parent: developer);
// var manager = new HierarchicalRole("manager", "Manager",
//     Permission.Delete, parent: viewer);
// var admin = new HierarchicalRole("admin", "Admin",
//     Permission.Admin, parent: manager);
```

### RBAC2 - Constrained RBAC

```csharp
/// <summary>
/// Context for constraint validation.
/// </summary>
public sealed record ConstraintContext(
    IReadOnlySet<string> UserRoles,
    string? AssigningRole = null,
    IReadOnlyDictionary<string, int>? RoleUserCount = null,
    Session? Session = null);

/// <summary>
/// Abstract constraint for RBAC.
/// </summary>
public abstract class Constraint
{
    public abstract bool Validate(ConstraintContext context);
}

/// <summary>
/// Mutual exclusion - conflicting roles.
/// </summary>
public sealed class MutualExclusionConstraint(IReadOnlySet<string> conflictingRoles) : Constraint
{
    /// <summary>
    /// User can only have one role from the conflicting set.
    /// </summary>
    public override bool Validate(ConstraintContext context)
    {
        var matching = context.UserRoles.Intersect(conflictingRoles);
        return matching.Count() <= 1;
    }
}

/// <summary>
/// Limit number of users per role.
/// </summary>
public sealed class CardinalityConstraint(string roleId, int maxUsers) : Constraint
{
    /// <summary>
    /// Role cannot have more than maxUsers assigned.
    /// </summary>
    public override bool Validate(ConstraintContext context)
    {
        var currentCount = context.RoleUserCount?.GetValueOrDefault(roleId) ?? 0;
        return currentCount < maxUsers;
    }
}

/// <summary>
/// Role requires another role first.
/// </summary>
public sealed class PrerequisiteConstraint(string roleId, string prerequisiteRoleId) : Constraint
{
    /// <summary>
    /// User must have prerequisite role before getting this role.
    /// </summary>
    public override bool Validate(ConstraintContext context)
    {
        if (context.AssigningRole == roleId)
        {
            return context.UserRoles.Contains(prerequisiteRoleId);
        }
        return true;
    }
}

/// <summary>
/// Time-based constraint.
/// </summary>
public sealed class TemporalConstraint(
    string roleId,
    int startHour,
    int endHour,
    IReadOnlySet<DayOfWeek>? allowedDays = null) : Constraint
{
    private readonly IReadOnlySet<DayOfWeek> _allowedDays = allowedDays ??
        new HashSet<DayOfWeek> { DayOfWeek.Monday, DayOfWeek.Tuesday, DayOfWeek.Wednesday,
                                  DayOfWeek.Thursday, DayOfWeek.Friday }.ToFrozenSet();

    /// <summary>
    /// Role only active during specified times.
    /// </summary>
    public override bool Validate(ConstraintContext context)
    {
        var now = DateTime.Now;
        if (!_allowedDays.Contains(now.DayOfWeek))
        {
            return false;
        }
        if (now.Hour < startHour || now.Hour >= endHour)
        {
            return false;
        }
        return true;
    }
}

/// <summary>
/// Constrained RBAC (RBAC2).
/// </summary>
public class Rbac2 : Rbac1
{
    private readonly List<Constraint> _staticConstraints = [];   // Assignment-time
    private readonly List<Constraint> _dynamicConstraints = [];  // Runtime

    public void AddStaticConstraint(Constraint constraint) =>
        _staticConstraints.Add(constraint);

    public void AddDynamicConstraint(Constraint constraint) =>
        _dynamicConstraints.Add(constraint);

    /// <summary>
    /// Assign role if constraints pass.
    /// </summary>
    public bool AssignRoleConstrained(string userId, string roleId)
    {
        var context = new ConstraintContext(
            UserRoles: GetUserRoleIds(userId).ToHashSet(),
            AssigningRole: roleId,
            RoleUserCount: GetRoleUserCounts());

        foreach (var constraint in _staticConstraints)
        {
            if (!constraint.Validate(context))
            {
                return false;
            }
        }

        AssignRole(userId, roleId);
        return true;
    }

    /// <summary>
    /// Check permission with dynamic constraints.
    /// </summary>
    public bool CheckPermissionConstrained(Session session, Permission permission)
    {
        var context = new ConstraintContext(
            UserRoles: session.ActiveRoles.Select(r => r.Id).ToHashSet(),
            Session: session);

        foreach (var constraint in _dynamicConstraints)
        {
            if (!constraint.Validate(context))
            {
                return false;
            }
        }

        return CheckPermission(session, permission);
    }

    private Dictionary<string, int> GetRoleUserCounts()
    {
        var counts = new Dictionary<string, int>();
        foreach (var userId in GetAllUserIds())
        {
            foreach (var roleId in GetUserRoleIds(userId))
            {
                counts[roleId] = counts.GetValueOrDefault(roleId) + 1;
            }
        }
        return counts;
    }
}
```

## Separation of Duties (SoD)

### Static Separation of Duties (SSD)

```csharp
/// <summary>
/// SSD constraint: (conflicting role set, max roles allowed from set).
/// </summary>
public sealed record SsdConstraint(FrozenSet<string> ConflictingRoles, int MaxRoles = 1);

/// <summary>
/// Static Separation of Duties management.
/// </summary>
public sealed class SsdManager
{
    private readonly List<SsdConstraint> _ssdConstraints = [];

    /// <summary>
    /// Add SSD constraint: user can have at most maxRoles from the set.
    /// </summary>
    public void AddSsdConstraint(IEnumerable<string> conflictingRoles, int maxRoles = 1) =>
        _ssdConstraints.Add(new SsdConstraint(conflictingRoles.ToFrozenSet(), maxRoles));

    /// <summary>
    /// Check if assigning newRole would violate SSD.
    /// </summary>
    public bool CanAssignRole(IReadOnlySet<string> userRoles, string newRole)
    {
        var potentialRoles = userRoles.Append(newRole).ToHashSet();

        foreach (var (roleSet, maxRoles) in _ssdConstraints)
        {
            var overlap = potentialRoles.Intersect(roleSet).Count();
            if (overlap > maxRoles)
            {
                return false;
            }
        }
        return true;
    }
}

// Example: Financial controls
// var ssd = new SsdManager();
//
// // User cannot be both requester and approver
// ssd.AddSsdConstraint(["expense_requester", "expense_approver"]);
//
// // User cannot be both developer and production deployer
// ssd.AddSsdConstraint(["developer", "production_deployer"]);
//
// // User can have at most 2 of these sensitive roles
// ssd.AddSsdConstraint(
//     ["security_admin", "system_admin", "database_admin", "network_admin"],
//     maxRoles: 2);
```

### Dynamic Separation of Duties (DSD)

```csharp
/// <summary>
/// DSD constraint: (conflicting role set, max active at once).
/// </summary>
public sealed record DsdConstraint(FrozenSet<string> ConflictingRoles, int MaxActive = 1);

/// <summary>
/// Dynamic Separation of Duties management.
/// </summary>
public sealed class DsdManager
{
    private readonly List<DsdConstraint> _dsdConstraints = [];

    /// <summary>
    /// Add DSD constraint: user can activate at most maxActive at once.
    /// </summary>
    public void AddDsdConstraint(IEnumerable<string> conflictingRoles, int maxActive = 1) =>
        _dsdConstraints.Add(new DsdConstraint(conflictingRoles.ToFrozenSet(), maxActive));

    /// <summary>
    /// Check if activating newRole would violate DSD.
    /// </summary>
    public bool CanActivateRole(IReadOnlySet<string> activeRoles, string newRole)
    {
        var potentialActive = activeRoles.Append(newRole).ToHashSet();

        foreach (var (roleSet, maxActive) in _dsdConstraints)
        {
            var overlap = potentialActive.Intersect(roleSet).Count();
            if (overlap > maxActive)
            {
                return false;
            }
        }
        return true;
    }

    /// <summary>
    /// Get roles user can currently activate.
    /// </summary>
    public IReadOnlySet<string> GetActivatableRoles(
        IReadOnlySet<string> userRoles,
        IReadOnlySet<string> activeRoles)
    {
        var activatable = new HashSet<string>();

        foreach (var role in userRoles)
        {
            if (!activeRoles.Contains(role) && CanActivateRole(activeRoles, role))
            {
                activatable.Add(role);
            }
        }

        return activatable;
    }
}

// Example: Cannot simultaneously review and approve same document
// var dsd = new DsdManager();
// dsd.AddDsdConstraint(["document_reviewer", "document_approver"]);
```

### Object-Based Separation of Duties

```csharp
/// <summary>
/// Object-level separation of duties constraint.
/// </summary>
public sealed record ObjectSodConstraint(
    IReadOnlyList<string> ActionSequence,  // e.g., ["create", "review", "approve"]
    bool SameUserProhibited = true);

/// <summary>
/// Action record for audit trail.
/// </summary>
public sealed record ActionRecord(string Action, string UserId, DateTime Timestamp);

/// <summary>
/// Track actions per object for SoD.
/// </summary>
public sealed class ObjectSodManager
{
    private readonly List<ObjectSodConstraint> _constraints = [];
    private readonly Dictionary<string, List<ActionRecord>> _actionHistory = [];

    public void AddConstraint(ObjectSodConstraint constraint) =>
        _constraints.Add(constraint);

    /// <summary>
    /// Record an action taken on an object.
    /// </summary>
    public void RecordAction(string objectId, string action, string userId)
    {
        if (!_actionHistory.TryGetValue(objectId, out var history))
        {
            history = [];
            _actionHistory[objectId] = history;
        }
        history.Add(new ActionRecord(action, userId, DateTime.UtcNow));
    }

    /// <summary>
    /// Check if user can perform action on object.
    /// </summary>
    public bool CanPerformAction(string objectId, string action, string userId)
    {
        var history = _actionHistory.GetValueOrDefault(objectId) ?? [];

        foreach (var constraint in _constraints)
        {
            var actionIndex = constraint.ActionSequence.IndexOf(action);
            if (actionIndex < 0)
            {
                continue; // Action not in this constraint's sequence
            }

            if (actionIndex == 0)
            {
                continue; // First action always allowed
            }

            // Check previous actions in sequence
            var previousActions = constraint.ActionSequence.Take(actionIndex).ToHashSet();
            foreach (var record in history)
            {
                if (previousActions.Contains(record.Action))
                {
                    if (constraint.SameUserProhibited && record.UserId == userId)
                    {
                        return false;
                    }
                }
            }
        }

        return true;
    }
}

// Example: Expense workflow
// var expenseSod = new ObjectSodManager();
// expenseSod.AddConstraint(new ObjectSodConstraint(
//     ActionSequence: ["submit", "review", "approve"],
//     SameUserProhibited: true));
//
// // Alice submits expense
// expenseSod.RecordAction("exp-123", "submit", "alice");
//
// // Alice cannot review her own expense
// expenseSod.CanPerformAction("exp-123", "review", "alice");  // False
//
// // Bob can review
// expenseSod.CanPerformAction("exp-123", "review", "bob");    // True
// expenseSod.RecordAction("exp-123", "review", "bob");
//
// // Bob cannot approve what he reviewed
// expenseSod.CanPerformAction("exp-123", "approve", "bob");   // False
```

## Multi-Tenant RBAC

```csharp
/// <summary>
/// Tenant/organization.
/// </summary>
public sealed record Tenant(string Id, string Name, string Plan = "basic");

/// <summary>
/// Role scoped to a tenant.
/// </summary>
public sealed record TenantRole(
    string Id,
    string TenantId,
    string Name,
    Permission Permissions,
    bool IsCustom = false);  // Tenant-defined vs system role

/// <summary>
/// RBAC with multi-tenancy support.
/// </summary>
public sealed class MultiTenantRbac
{
    private readonly Dictionary<string, Tenant> _tenants = [];
    private readonly Dictionary<string, Role> _systemRoles = [];  // Shared across tenants
    private readonly Dictionary<string, Dictionary<string, TenantRole>> _tenantRoles = [];  // tenant_id -> roles
    // user_id -> tenant_id -> role_ids
    private readonly Dictionary<string, Dictionary<string, HashSet<string>>> _userTenantRoles = [];

    /// <summary>
    /// Create a tenant with default roles.
    /// </summary>
    public void CreateTenant(Tenant tenant)
    {
        _tenants[tenant.Id] = tenant;
        _tenantRoles[tenant.Id] = [];
        CreateDefaultTenantRoles(tenant);
    }

    private void CreateDefaultTenantRoles(Tenant tenant)
    {
        var defaultRoles = new TenantRole[]
        {
            new($"{tenant.Id}_owner", tenant.Id, "Owner",
                Permission.Read | Permission.Create | Permission.Update |
                Permission.Delete | Permission.Admin),
            new($"{tenant.Id}_admin", tenant.Id, "Admin",
                Permission.Read | Permission.Create | Permission.Update | Permission.Delete),
            new($"{tenant.Id}_member", tenant.Id, "Member",
                Permission.Read | Permission.Create | Permission.Update),
            new($"{tenant.Id}_viewer", tenant.Id, "Viewer", Permission.Read)
        };

        foreach (var role in defaultRoles)
        {
            _tenantRoles[tenant.Id][role.Id] = role;
        }
    }

    /// <summary>
    /// Add user to tenant with a role.
    /// </summary>
    public void AddUserToTenant(string userId, string tenantId, string roleId)
    {
        if (!_userTenantRoles.TryGetValue(userId, out var tenantRoles))
        {
            tenantRoles = [];
            _userTenantRoles[userId] = tenantRoles;
        }

        if (!tenantRoles.TryGetValue(tenantId, out var roles))
        {
            roles = [];
            tenantRoles[tenantId] = roles;
        }

        roles.Add(roleId);
    }

    /// <summary>
    /// Check permission within tenant context.
    /// </summary>
    public bool CheckPermission(string userId, string tenantId, Permission permission)
    {
        var userRoles = _userTenantRoles
            .GetValueOrDefault(userId)?
            .GetValueOrDefault(tenantId) ?? [];

        // Check tenant-specific roles
        var tenantRoleDefs = _tenantRoles.GetValueOrDefault(tenantId) ?? [];
        foreach (var roleId in userRoles)
        {
            if (tenantRoleDefs.TryGetValue(roleId, out var role) &&
                role.Permissions.HasFlag(permission))
            {
                return true;
            }
        }

        // Check system roles (if any)
        foreach (var roleId in userRoles)
        {
            if (_systemRoles.TryGetValue(roleId, out var role) &&
                role.Permissions.HasFlag(permission))
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>
    /// Get all tenants user belongs to.
    /// </summary>
    public IReadOnlyList<string> GetUserTenants(string userId) =>
        _userTenantRoles.GetValueOrDefault(userId)?.Keys.ToList() ?? [];

    /// <summary>
    /// Create a custom role for a tenant.
    /// </summary>
    public TenantRole CreateCustomRole(string tenantId, string name, Permission permissions)
    {
        var roleId = $"{tenantId}_custom_{name.ToLowerInvariant().Replace(' ', '_')}";
        var role = new TenantRole(roleId, tenantId, name, permissions, IsCustom: true);

        if (!_tenantRoles.TryGetValue(tenantId, out var roles))
        {
            roles = [];
            _tenantRoles[tenantId] = roles;
        }

        roles[roleId] = role;
        return role;
    }
}
```

## Resource-Level RBAC

```csharp
/// <summary>
/// Key for resource-level role assignment.
/// </summary>
public sealed record ResourceKey(string UserId, string ResourceType, string ResourceId);

/// <summary>
/// RBAC with resource-level role assignments.
/// </summary>
public sealed class ResourceRbac
{
    private readonly Dictionary<ResourceKey, HashSet<string>> _resourceAssignments = [];

    private readonly Dictionary<string, FrozenDictionary<string, Permission>> _resourceRoleDefinitions =
        new()
        {
            ["document"] = new Dictionary<string, Permission>
            {
                ["owner"] = Permission.Read | Permission.Update | Permission.Delete | Permission.Admin,
                ["editor"] = Permission.Read | Permission.Update,
                ["viewer"] = Permission.Read
            }.ToFrozenDictionary(),

            ["project"] = new Dictionary<string, Permission>
            {
                ["owner"] = Permission.Read | Permission.Create | Permission.Update |
                           Permission.Delete | Permission.Admin,
                ["maintainer"] = Permission.Read | Permission.Create | Permission.Update,
                ["contributor"] = Permission.Read | Permission.Create,
                ["viewer"] = Permission.Read
            }.ToFrozenDictionary()
        };

    /// <summary>
    /// Assign a role to user for specific resource.
    /// </summary>
    public void AssignResourceRole(string userId, string resourceType, string resourceId, string role)
    {
        var key = new ResourceKey(userId, resourceType, resourceId);
        if (!_resourceAssignments.TryGetValue(key, out var roles))
        {
            roles = [];
            _resourceAssignments[key] = roles;
        }
        roles.Add(role);
    }

    /// <summary>
    /// Check permission on specific resource.
    /// </summary>
    public bool CheckResourcePermission(
        string userId,
        string resourceType,
        string resourceId,
        Permission permission)
    {
        var key = new ResourceKey(userId, resourceType, resourceId);
        var userRoles = _resourceAssignments.GetValueOrDefault(key) ?? [];
        var roleDefs = _resourceRoleDefinitions.GetValueOrDefault(resourceType);

        if (roleDefs is null) return false;

        foreach (var role in userRoles)
        {
            if (roleDefs.TryGetValue(role, out var rolePerms) &&
                rolePerms.HasFlag(permission))
            {
                return true;
            }
        }
        return false;
    }

    /// <summary>
    /// Get all users with access to a resource.
    /// </summary>
    public IReadOnlySet<string> GetResourceUsers(
        string resourceType,
        string resourceId,
        string? role = null)
    {
        var users = new HashSet<string>();

        foreach (var (key, roles) in _resourceAssignments)
        {
            if (key.ResourceType == resourceType && key.ResourceId == resourceId)
            {
                if (role is null || roles.Contains(role))
                {
                    users.Add(key.UserId);
                }
            }
        }

        return users;
    }
}
```

## RBAC with Groups

```csharp
/// <summary>
/// User group with optional nesting.
/// </summary>
public sealed class Group(string id, string name, string? parentGroupId = null)
{
    public string Id { get; } = id;
    public string Name { get; } = name;
    public string? ParentGroupId { get; } = parentGroupId;
    public HashSet<string> Members { get; } = [];
}

/// <summary>
/// RBAC with group support.
/// </summary>
public sealed class GroupRbac
{
    private readonly Dictionary<string, Group> _groups = [];
    private readonly Dictionary<string, HashSet<string>> _userRoles = [];
    private readonly Dictionary<string, HashSet<string>> _groupRoles = [];
    private readonly Dictionary<string, Role> _roles = [];

    public void CreateGroup(Group group) => _groups[group.Id] = group;

    public void CreateRole(Role role) => _roles[role.Id] = role;

    public void AddUserToGroup(string userId, string groupId)
    {
        if (_groups.TryGetValue(groupId, out var group))
        {
            group.Members.Add(userId);
        }
    }

    public void AssignRoleToUser(string userId, string roleId)
    {
        if (!_userRoles.TryGetValue(userId, out var roles))
        {
            roles = [];
            _userRoles[userId] = roles;
        }
        roles.Add(roleId);
    }

    public void AssignRoleToGroup(string groupId, string roleId)
    {
        if (!_groupRoles.TryGetValue(groupId, out var roles))
        {
            roles = [];
            _groupRoles[groupId] = roles;
        }
        roles.Add(roleId);
    }

    /// <summary>
    /// Get all groups user belongs to (including nested/parent groups).
    /// </summary>
    public IReadOnlySet<string> GetUserGroups(string userId)
    {
        var groups = new HashSet<string>();

        foreach (var (groupId, group) in _groups)
        {
            if (group.Members.Contains(userId))
            {
                groups.Add(groupId);
                // Add parent groups recursively
                AddParentGroups(groupId, groups);
            }
        }

        return groups;
    }

    private void AddParentGroups(string groupId, HashSet<string> groups)
    {
        if (_groups.TryGetValue(groupId, out var group) &&
            group.ParentGroupId is not null)
        {
            groups.Add(group.ParentGroupId);
            AddParentGroups(group.ParentGroupId, groups);
        }
    }

    /// <summary>
    /// Get all roles including from groups.
    /// </summary>
    public IReadOnlySet<string> GetEffectiveRoles(string userId)
    {
        var roles = _userRoles.GetValueOrDefault(userId)?.ToHashSet() ?? [];

        // Add roles from groups
        foreach (var groupId in GetUserGroups(userId))
        {
            var groupRoles = _groupRoles.GetValueOrDefault(groupId);
            if (groupRoles is not null)
            {
                roles.UnionWith(groupRoles);
            }
        }

        return roles;
    }

    /// <summary>
    /// Check permission considering group memberships.
    /// </summary>
    public bool CheckPermission(string userId, Permission permission)
    {
        foreach (var roleId in GetEffectiveRoles(userId))
        {
            if (_roles.TryGetValue(roleId, out var role) &&
                role.Permissions.HasFlag(permission))
            {
                return true;
            }
        }
        return false;
    }
}
```

## Security Checklist

### RBAC Design

- [ ] Roles based on job functions, not individuals
- [ ] Principle of least privilege applied
- [ ] Role hierarchy well-defined
- [ ] Separation of duties constraints identified

### Implementation

- [ ] Centralized role management
- [ ] Roles assignable at appropriate scopes
- [ ] Group support for scalability
- [ ] Audit trail for role assignments

### Constraints

- [ ] Static SoD for conflicting roles
- [ ] Dynamic SoD where needed
- [ ] Cardinality limits on sensitive roles
- [ ] Temporal constraints if applicable

### Operations

- [ ] Regular role assignment reviews
- [ ] Unused roles identified and removed
- [ ] Role creep monitored
- [ ] Emergency access procedures documented
