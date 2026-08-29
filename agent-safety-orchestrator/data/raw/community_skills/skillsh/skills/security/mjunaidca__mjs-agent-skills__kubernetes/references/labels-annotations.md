# Labels and Annotations

Standard labels, ArgoCD compatibility, and metadata patterns.

---

## Kubernetes Recommended Labels

Always use these for production workloads:

```yaml
metadata:
  labels:
    # Required
    app.kubernetes.io/name: myapp           # Application name
    app.kubernetes.io/instance: myapp-prod  # Unique instance ID

    # Recommended
    app.kubernetes.io/version: "1.2.3"      # App version
    app.kubernetes.io/component: api        # Component type
    app.kubernetes.io/part-of: platform     # Parent application
    app.kubernetes.io/managed-by: kubectl   # Management tool
```

### Field Reference

| Label | Purpose | Example |
|-------|---------|---------|
| `app.kubernetes.io/name` | Application name | `mysql`, `nginx` |
| `app.kubernetes.io/instance` | Unique instance | `mysql-prod`, `mysql-staging` |
| `app.kubernetes.io/version` | Current version | `5.7.21`, `v1.0.0` |
| `app.kubernetes.io/component` | Component role | `database`, `cache`, `frontend` |
| `app.kubernetes.io/part-of` | Higher-level app | `wordpress`, `ecommerce` |
| `app.kubernetes.io/managed-by` | Management tool | `helm`, `kustomize`, `kubectl` |

---

## Complete Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  labels:
    app.kubernetes.io/name: api-server
    app.kubernetes.io/instance: api-server-production
    app.kubernetes.io/version: "2.1.0"
    app.kubernetes.io/component: api
    app.kubernetes.io/part-of: ecommerce
    app.kubernetes.io/managed-by: kubectl
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: api-server
      app.kubernetes.io/instance: api-server-production
  template:
    metadata:
      labels:
        # Must match selector
        app.kubernetes.io/name: api-server
        app.kubernetes.io/instance: api-server-production
        app.kubernetes.io/version: "2.1.0"
        app.kubernetes.io/component: api
        app.kubernetes.io/part-of: ecommerce
```

---

## Label Selector Patterns

### Service Selector

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-server
spec:
  selector:
    app.kubernetes.io/name: api-server
    app.kubernetes.io/component: api
```

### Network Policy

```yaml
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: api-server
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: frontend
```

### HPA

```yaml
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server     # Target by name, not labels
```

---

## ArgoCD Compatibility

### Application Labels

```yaml
metadata:
  labels:
    # Standard K8s labels
    app.kubernetes.io/name: myapp
    app.kubernetes.io/instance: myapp-prod
    app.kubernetes.io/managed-by: argocd

    # ArgoCD-specific
    argocd.argoproj.io/instance: myapp
```

### Sync Annotations

```yaml
metadata:
  annotations:
    # Sync options
    argocd.argoproj.io/sync-options: Prune=false
    argocd.argoproj.io/sync-wave: "1"

    # Hook annotations
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
```

### Resource Tracking

```yaml
metadata:
  annotations:
    # Track by annotation (recommended)
    argocd.argoproj.io/tracking-id: myapp:/Deployment:default/api
```

---

## Common Annotations

### Deployment

```yaml
metadata:
  annotations:
    # Description
    description: "API server for the ecommerce platform"

    # Change cause (for rollback)
    kubernetes.io/change-cause: "Update to v2.1.0"

    # Config checksum (trigger rollout on config change)
    checksum/config: "abc123..."
```

### Ingress

```yaml
metadata:
  annotations:
    # Ingress class
    kubernetes.io/ingress.class: nginx

    # TLS
    cert-manager.io/cluster-issuer: letsencrypt-prod

    # NGINX specific
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
```

### Service

```yaml
metadata:
  annotations:
    # Load balancer type
    service.beta.kubernetes.io/aws-load-balancer-type: nlb

    # Health check
    service.beta.kubernetes.io/aws-load-balancer-healthcheck-path: /health
```

---

## Environment-Specific Labels

```yaml
metadata:
  labels:
    # Environment
    environment: production      # or: staging, development

    # Team ownership
    team: platform
    cost-center: engineering

    # Criticality
    tier: critical              # or: high, medium, low
```

---

## GitOps Directory Structure Labels

For ArgoCD app-of-apps pattern:

```yaml
# base/kustomization.yaml
commonLabels:
  app.kubernetes.io/part-of: myapp
  app.kubernetes.io/managed-by: argocd

# overlays/production/kustomization.yaml
commonLabels:
  environment: production
  app.kubernetes.io/instance: myapp-production
```

---

## Label Naming Conventions

### Key Format

```
prefix/name

# Examples
app.kubernetes.io/name
argocd.argoproj.io/instance
team.example.com/owner
```

### Value Constraints

- Max 63 characters
- Start/end with alphanumeric
- May contain `-`, `_`, `.`
- Case-sensitive

```yaml
# Valid
labels:
  version: "1.0.0"
  app-type: api
  tier_level: "1"

# Invalid
labels:
  version: "very-long-version-string-that-exceeds-63-characters-limit"
  app type: api        # No spaces
  -starts-with-dash: x # Can't start with dash
```

---

## Common Patterns

### Canary Deployments

```yaml
# Stable
metadata:
  labels:
    app: myapp
    track: stable

# Canary
metadata:
  labels:
    app: myapp
    track: canary
```

### Blue-Green

```yaml
# Active (blue)
metadata:
  labels:
    app: myapp
    version: blue
    active: "true"

# Inactive (green)
metadata:
  labels:
    app: myapp
    version: green
    active: "false"
```

### Multi-Tenant

```yaml
metadata:
  labels:
    tenant: customer-a
    app.kubernetes.io/name: myapp
    app.kubernetes.io/instance: myapp-customer-a
```

---

## Querying by Labels

```bash
# Get pods with specific label
kubectl get pods -l app.kubernetes.io/name=api-server

# Multiple labels (AND)
kubectl get pods -l 'app.kubernetes.io/name=api-server,environment=production'

# Set-based selectors
kubectl get pods -l 'environment in (production, staging)'
kubectl get pods -l 'tier notin (frontend)'

# Label exists
kubectl get pods -l 'team'

# Label doesn't exist
kubectl get pods -l '!experimental'
```
