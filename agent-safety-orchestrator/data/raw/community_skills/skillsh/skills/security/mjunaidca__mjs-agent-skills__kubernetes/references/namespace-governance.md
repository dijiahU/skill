# Namespace Governance Patterns

Resource isolation and multi-team management for Kubernetes clusters.

---

## When to Use

| Trigger | Generate |
|---------|----------|
| "Create namespace for team X" | Namespace + ResourceQuota + LimitRange |
| "Set up dev/staging/prod environments" | Multi-namespace with quota progression |
| "Isolate team workloads" | NetworkPolicy + ResourceQuota |
| "Shared monitoring across namespaces" | RBAC + NetworkPolicy allow rules |

---

## Core Concepts

### Namespace = Virtual Cluster

```
Cluster
├── Namespace: dev         ← Team A's sandbox
├── Namespace: staging     ← Pre-production
├── Namespace: prod        ← Production workloads
└── Namespace: monitoring  ← Shared observability
```

**Three isolation layers:**
1. **ResourceQuota** - Namespace-wide resource caps
2. **LimitRange** - Per-container defaults and bounds
3. **NetworkPolicy** - Network isolation between namespaces

---

## ResourceQuota Patterns

### Environment Progression

| Environment | CPU Req | Memory Req | Pods | Use Case |
|-------------|---------|------------|------|----------|
| dev | 2 | 2Gi | 20 | Experimentation, tight limits |
| staging | 4 | 4Gi | 30 | Production-like testing |
| prod | 8+ | 8Gi+ | 50+ | Scaled for traffic |

### Dev Namespace Quota

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: dev-quota
  namespace: dev
spec:
  hard:
    # WHY: CPU requests limit prevents namespace from reserving entire cluster
    requests.cpu: "2"
    requests.memory: "2Gi"

    # WHY: Limits cap burst capacity - dev shouldn't burst beyond 4 cores
    limits.cpu: "4"
    limits.memory: "4Gi"

    # WHY: Pod count prevents HPA/replica misconfiguration from pod explosion
    pods: "20"

    # WHY: Storage prevents runaway PVC creation
    requests.storage: "10Gi"
    persistentvolumeclaims: "5"
```

### Staging Namespace Quota

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: staging-quota
  namespace: staging
spec:
  hard:
    # WHY: 2x dev resources for realistic load testing
    requests.cpu: "4"
    requests.memory: "4Gi"
    limits.cpu: "8"
    limits.memory: "8Gi"
    pods: "30"
    requests.storage: "20Gi"
    persistentvolumeclaims: "10"
```

### Production Namespace Quota

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: prod-quota
  namespace: prod
spec:
  hard:
    # WHY: Production needs headroom for scaling
    requests.cpu: "16"
    requests.memory: "16Gi"
    limits.cpu: "32"
    limits.memory: "32Gi"
    pods: "100"

    # WHY: Limit expensive resources
    requests.storage: "100Gi"
    persistentvolumeclaims: "20"

    # WHY: Prevent LoadBalancer cost explosion
    services.loadbalancers: "5"
    services.nodeports: "10"
```

### GPU Quota (AI/ML Teams)

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: ml-team-quota
  namespace: ml-training
spec:
  hard:
    requests.nvidia.com/gpu: "4"
    limits.nvidia.com/gpu: "4"
    # WHY: GPU workloads need high memory
    requests.memory: "64Gi"
    limits.memory: "128Gi"
    pods: "10"
```

---

## LimitRange Patterns

### Purpose

| Without LimitRange | With LimitRange |
|--------------------|-----------------|
| Pod with no limits → unbounded resources | Default limits injected |
| Single pod consumes entire quota | Max per-container enforced |
| Tiny pods waste scheduling overhead | Minimum resources enforced |

### Dev Environment LimitRange

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: dev-limits
  namespace: dev
spec:
  limits:
  - type: Container
    # WHY: Defaults when developer doesn't specify
    default:
      cpu: "250m"
      memory: "256Mi"
    defaultRequest:
      cpu: "100m"
      memory: "128Mi"

    # WHY: Max prevents single container from hogging quota
    max:
      cpu: "500m"
      memory: "512Mi"

    # WHY: Min ensures viable resources, prevents scheduling noise
    min:
      cpu: "10m"
      memory: "32Mi"
```

### Production LimitRange (Stricter)

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: prod-limits
  namespace: prod
spec:
  limits:
  - type: Container
    default:
      cpu: "500m"
      memory: "512Mi"
    defaultRequest:
      cpu: "250m"
      memory: "256Mi"
    max:
      cpu: "2"
      memory: "2Gi"
    min:
      cpu: "50m"
      memory: "64Mi"

    # WHY: Enforce predictable QoS - limit can't exceed 2x request
    maxLimitRequestRatio:
      cpu: "2"
      memory: "2"

  - type: Pod
    # WHY: Pod-level max for multi-container pods
    max:
      cpu: "4"
      memory: "4Gi"

  - type: PersistentVolumeClaim
    max:
      storage: "20Gi"
    min:
      storage: "1Gi"
```

---

## NetworkPolicy Patterns

### Default Deny (Namespace Isolation)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: prod
spec:
  # WHY: Apply to all pods in namespace
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

**After applying:** All traffic blocked. Add allow rules for legitimate traffic.

### Allow Same-Namespace Traffic

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-same-namespace
  namespace: prod
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    # WHY: Pods in same namespace can communicate
    - podSelector: {}
```

### Allow Monitoring Namespace

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-prometheus-scrape
  namespace: prod  # Apply to each team namespace
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          # WHY: Only monitoring namespace can scrape metrics
          purpose: monitoring
    ports:
    - port: 9090
      protocol: TCP
    - port: 8080
      protocol: TCP
```

### Allow DNS (Required)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: prod
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - port: 53
      protocol: UDP
    - port: 53
      protocol: TCP
```

---

## Multi-Team Architecture

### Namespace Strategy

```
Cluster
├── Team Namespaces (isolated)
│   ├── team-alpha-dev
│   ├── team-alpha-prod
│   ├── team-beta-dev
│   └── team-beta-prod
│
├── Shared Services (accessible)
│   ├── monitoring (Prometheus, Grafana)
│   ├── logging (Loki, Fluentd)
│   └── ingress (NGINX, Traefik)
│
└── System
    ├── kube-system
    └── cert-manager
```

### Team Namespace Labels

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: team-alpha-prod
  labels:
    # WHY: Standard labels for tooling
    app.kubernetes.io/name: team-alpha-prod

    # WHY: Custom labels for policy selection
    team: alpha
    environment: production
    cost-center: engineering

    # WHY: Enable monitoring scraping
    monitoring: enabled
```

### Cross-Namespace Service Access

Services in one namespace access another via FQDN:

```
<service>.<namespace>.svc.cluster.local
```

**Example:** App in `team-alpha-prod` accessing shared Prometheus:

```yaml
env:
- name: PROMETHEUS_URL
  # WHY: FQDN required for cross-namespace access
  value: "http://prometheus.monitoring.svc.cluster.local:9090"
```

---

## RBAC for Namespace Isolation

### Team-Scoped Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: team-developer
  namespace: team-alpha-dev
rules:
- apiGroups: ["", "apps", "batch"]
  resources: ["pods", "deployments", "services", "configmaps", "jobs"]
  verbs: ["get", "list", "watch", "create", "update", "delete"]
- apiGroups: [""]
  resources: ["pods/log", "pods/exec"]
  verbs: ["get", "create"]
```

### Monitoring ClusterRole (Cross-Namespace)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus-scraper
rules:
- apiGroups: [""]
  resources: ["pods", "services", "endpoints"]
  verbs: ["get", "list", "watch"]
- nonResourceURLs: ["/metrics"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus-scraper
subjects:
- kind: ServiceAccount
  name: prometheus
  namespace: monitoring
roleRef:
  kind: ClusterRole
  name: prometheus-scraper
  apiGroup: rbac.authorization.k8s.io
```

---

## Quick Reference

### ResourceQuota Fields

| Field | Purpose |
|-------|---------|
| `requests.cpu` | Sum of all pod CPU requests |
| `limits.cpu` | Sum of all pod CPU limits |
| `requests.memory` | Sum of all pod memory requests |
| `limits.memory` | Sum of all pod memory limits |
| `pods` | Maximum pod count |
| `services.loadbalancers` | Max LoadBalancer services |
| `services.nodeports` | Max NodePort services |
| `persistentvolumeclaims` | Max PVC count |
| `requests.storage` | Sum of all PVC sizes |
| `requests.nvidia.com/gpu` | GPU allocation |

### LimitRange Types

| Type | Applies To |
|------|-----------|
| `Container` | Each container in pods |
| `Pod` | Aggregate of all containers in pod |
| `PersistentVolumeClaim` | Storage requests |

### Verification Commands

```bash
# Check quota usage
kubectl describe resourcequota -n $NAMESPACE

# Check limit range
kubectl describe limitrange -n $NAMESPACE

# Test pod against limits
kubectl run test --image=nginx --dry-run=server -n $NAMESPACE

# Verify network policies
kubectl get networkpolicy -n $NAMESPACE
```

---

## Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| No quota on dev | Dev pods starve prod | Always set quotas |
| Same limits dev=prod | Can't test real scaling | Use environment progression |
| No LimitRange | Pods without limits bypass quota | Always pair with ResourceQuota |
| Allow-all NetworkPolicy | No isolation | Default deny + explicit allows |
| Hardcoded namespace in manifests | Can't deploy to multiple envs | Use variables or Kustomize |
