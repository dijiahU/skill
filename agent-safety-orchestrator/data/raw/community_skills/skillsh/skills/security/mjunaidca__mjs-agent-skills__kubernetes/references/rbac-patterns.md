# RBAC Patterns

Role-Based Access Control for securing Kubernetes workloads and AI agents.

---

## Core Concepts

### The Five RBAC Components

```
┌─────────────────┐     ┌─────────────────┐
│  ServiceAccount │     │      Role       │
│  (WHO - Identity)│     │ (WHAT - Perms)  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
              ┌──────▼──────┐
              │ RoleBinding │
              │  (CONNECT)  │
              └─────────────┘
```

| Component | Scope | Purpose |
|-----------|-------|---------|
| **ServiceAccount** | Namespace | Pod identity for API authentication |
| **Role** | Namespace | Permission set (what can be done) |
| **RoleBinding** | Namespace | Connects ServiceAccount to Role |
| **ClusterRole** | Cluster-wide | Permissions across all namespaces |
| **ClusterRoleBinding** | Cluster-wide | Connects SA to ClusterRole |

### Key Principle

> **Least Privilege**: Grant only the minimum permissions required.
> A compromised pod should not become a stepping stone for cluster-wide compromise.

---

## ServiceAccount

### Create ServiceAccount

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: agent-sa
  namespace: default
  labels:
    app.kubernetes.io/name: agent-sa
    app.kubernetes.io/component: security
```

Or imperatively:

```bash
kubectl create serviceaccount agent-sa -n default
```

### Assign to Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: agent-pod
spec:
  serviceAccountName: agent-sa    # Use custom SA, not default
  containers:
  - name: agent
    image: my-agent:latest
```

### Assign to Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent
spec:
  template:
    spec:
      serviceAccountName: agent-sa
      containers:
      - name: agent
        image: my-agent:latest
```

### Disable Token Auto-Mount (Security Hardening)

If pod doesn't need Kubernetes API access:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: no-api-access
automountServiceAccountToken: false
```

Or per-pod:

```yaml
spec:
  serviceAccountName: no-api-access
  automountServiceAccountToken: false
```

---

## Token Mounting

When a pod uses a ServiceAccount, Kubernetes automatically mounts:

```
/var/run/secrets/kubernetes.io/serviceaccount/
├── token      # JWT for API authentication
├── ca.crt     # Cluster CA certificate
└── namespace  # Current namespace name
```

### Access Token in Application

```python
# Python example
with open('/var/run/secrets/kubernetes.io/serviceaccount/token') as f:
    token = f.read()

# Use token in API requests
headers = {'Authorization': f'Bearer {token}'}
```

---

## Role

### Basic Role (Read-Only)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: agent-reader
  namespace: default
rules:
- apiGroups: [""]              # Core API group
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list"]       # Read-only
```

### Role with Resource Name Restriction (Least Privilege)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: agent-config-reader
  namespace: default
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  resourceNames: ["agent-config"]    # ONLY this ConfigMap
  verbs: ["get"]
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["api-credentials"] # ONLY this Secret
  verbs: ["get"]
```

### Role with Write Access

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: agent-writer
  namespace: default
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list"]
```

### Common Verbs

| Verb | Action |
|------|--------|
| `get` | Read single resource |
| `list` | Read multiple resources |
| `watch` | Stream changes |
| `create` | Create new resource |
| `update` | Replace entire resource |
| `patch` | Modify part of resource |
| `delete` | Delete resource |
| `deletecollection` | Delete multiple resources |

### Common API Groups

| apiGroup | Resources |
|----------|-----------|
| `""` (core) | pods, services, configmaps, secrets, namespaces, nodes |
| `apps` | deployments, replicasets, statefulsets, daemonsets |
| `batch` | jobs, cronjobs |
| `networking.k8s.io` | networkpolicies, ingresses |
| `rbac.authorization.k8s.io` | roles, rolebindings, clusterroles |
| `autoscaling` | horizontalpodautoscalers |

---

## RoleBinding

### Connect ServiceAccount to Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: agent-reader-binding
  namespace: default
subjects:
- kind: ServiceAccount
  name: agent-sa
  namespace: default
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: agent-reader
```

### Multiple Subjects

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: team-readers
  namespace: default
subjects:
- kind: ServiceAccount
  name: agent-sa
  namespace: default
- kind: ServiceAccount
  name: worker-sa
  namespace: default
- kind: User
  name: developer@example.com
  apiGroup: rbac.authorization.k8s.io
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: reader-role
```

---

## ClusterRole and ClusterRoleBinding

### ClusterRole (Cluster-Wide Permissions)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: namespace-reader
rules:
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
  # No resourceNames = all pods in any namespace
```

### ClusterRoleBinding

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: namespace-reader-binding
subjects:
- kind: ServiceAccount
  name: monitoring-sa
  namespace: monitoring
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: namespace-reader
```

### Use ClusterRole with RoleBinding (Namespace-Scoped)

Reuse ClusterRole but limit to single namespace:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pod-reader-in-dev
  namespace: dev
subjects:
- kind: ServiceAccount
  name: dev-agent
  namespace: dev
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole         # Reference ClusterRole
  name: pod-reader          # But bound only in 'dev' namespace
```

---

## AI Agent RBAC Patterns

### Minimal Inference Agent

AI agent that only reads config and secrets:

```yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: inference-agent
  namespace: ai-prod
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: inference-agent-role
  namespace: ai-prod
rules:
# Read only specific ConfigMap
- apiGroups: [""]
  resources: ["configmaps"]
  resourceNames: ["model-config"]
  verbs: ["get"]
# Read only specific Secret (API keys)
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["inference-credentials"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: inference-agent-binding
  namespace: ai-prod
subjects:
- kind: ServiceAccount
  name: inference-agent
  namespace: ai-prod
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: inference-agent-role
```

### Agent with Job Creation (Batch Processing)

Agent that can spawn jobs for batch inference:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: batch-agent-role
  namespace: ai-batch
rules:
# Read config
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  resourceNames: ["batch-config", "batch-credentials"]
  verbs: ["get"]
# Create and monitor jobs
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["get", "list", "watch", "create", "delete"]
# Read job pods for logs
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list"]
```

### Multi-Tenant Agent Isolation

Each team gets isolated RBAC:

```yaml
# Team A - namespace: agents-team-a
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: team-a-agent
  namespace: agents-team-a
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: team-a-role
  namespace: agents-team-a
rules:
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  resourceNames: ["team-a-config", "team-a-creds"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: team-a-binding
  namespace: agents-team-a
subjects:
- kind: ServiceAccount
  name: team-a-agent
  namespace: agents-team-a
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: team-a-role
```

Team B gets identical structure in `agents-team-b` namespace. **Cross-namespace access is impossible** with namespace-scoped Roles.

---

## Permission Auditing

### Check Permissions with `kubectl auth can-i`

```bash
# Check if ServiceAccount can get configmaps
kubectl auth can-i get configmaps \
  --as=system:serviceaccount:default:agent-sa

# Check specific resource
kubectl auth can-i get secrets/api-credentials \
  --as=system:serviceaccount:default:agent-sa

# Check in specific namespace
kubectl auth can-i create pods \
  --as=system:serviceaccount:ai-prod:inference-agent \
  -n ai-prod

# List all permissions
kubectl auth can-i --list \
  --as=system:serviceaccount:default:agent-sa
```

### Expected Outputs

```bash
# Minimal agent should show:
kubectl auth can-i get configmaps --as=system:serviceaccount:default:agent-sa
# yes

kubectl auth can-i delete deployments --as=system:serviceaccount:default:agent-sa
# no

kubectl auth can-i create pods --as=system:serviceaccount:default:agent-sa
# no
```

### Inspect RBAC Resources

```bash
# View ServiceAccount
kubectl get serviceaccount agent-sa -o yaml

# View Role
kubectl get role agent-reader -o yaml

# View RoleBinding
kubectl get rolebinding agent-reader-binding -o yaml

# List all roles in namespace
kubectl get roles -n default

# List all rolebindings
kubectl get rolebindings -n default
```

---

## Anti-Patterns (NEVER DO)

### ❌ Cluster-Admin for Agents

```bash
# NEVER: Grants full cluster access
kubectl create clusterrolebinding agent-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=default:agent-sa
```

**Why dangerous**: Compromised agent can delete any resource, access all secrets, create privileged pods.

### ❌ Wildcard Permissions

```yaml
# NEVER: Access to everything
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
```

### ❌ Using Default ServiceAccount

```yaml
# BAD: Default SA may have unexpected permissions
spec:
  # serviceAccountName not specified = uses 'default'
  containers:
  - name: agent
```

**Fix**: Always create and use a dedicated ServiceAccount.

### ❌ Cross-Namespace Secret Access

```yaml
# BAD: Agent in 'dev' accessing 'prod' secrets via ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: dev-agent-all-secrets
subjects:
- kind: ServiceAccount
  name: dev-agent
  namespace: dev
roleRef:
  kind: ClusterRole
  name: secret-reader-all  # Reads secrets in ALL namespaces
```

**Fix**: Use namespace-scoped Roles, never ClusterRoles for secret access.

---

## Best Practices

| Practice | Implementation |
|----------|----------------|
| Dedicated ServiceAccounts | One SA per workload type |
| Use `resourceNames` | Restrict to specific ConfigMaps/Secrets |
| Namespace isolation | Roles, not ClusterRoles for app permissions |
| Disable unused token mounts | `automountServiceAccountToken: false` |
| Audit permissions regularly | `kubectl auth can-i --list` |
| Separate read/write roles | Different roles for different access levels |
| Document RBAC decisions | Comments in Role manifests |

---

## Quick Reference

### Minimal Agent RBAC (Copy-Paste)

```yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-agent
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: my-agent-role
  namespace: default
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  resourceNames: ["my-config"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: my-agent-binding
  namespace: default
subjects:
- kind: ServiceAccount
  name: my-agent
  namespace: default
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: my-agent-role
```

### Common Permission Sets

| Use Case | Verbs |
|----------|-------|
| Read-only | `get`, `list`, `watch` |
| Read-write | `get`, `list`, `create`, `update`, `patch` |
| Full control | `get`, `list`, `watch`, `create`, `update`, `patch`, `delete` |
| Watch only | `watch` (for controllers) |

### Debugging RBAC Issues

```bash
# Pod can't access resource? Check:
# 1. Is SA assigned to pod?
kubectl get pod <pod> -o jsonpath='{.spec.serviceAccountName}'

# 2. Does SA have RoleBinding?
kubectl get rolebindings -o wide | grep <sa-name>

# 3. What permissions does SA have?
kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa>

# 4. Check specific permission
kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<ns>:<sa>
```
