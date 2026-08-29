# Resource Limits

CPU and memory requests/limits for production workloads.

---

## Core Concepts

| Field | Purpose | Behavior |
|-------|---------|----------|
| `requests.cpu` | Guaranteed CPU | Scheduler uses for placement |
| `requests.memory` | Guaranteed memory | Scheduler uses for placement |
| `limits.cpu` | CPU ceiling | Throttled if exceeded |
| `limits.memory` | Memory ceiling | OOM killed if exceeded |

---

## Default Template

```yaml
resources:
  requests:
    cpu: "100m"      # 0.1 CPU cores
    memory: "128Mi"  # 128 MiB
  limits:
    cpu: "500m"      # 0.5 CPU cores
    memory: "512Mi"  # 512 MiB
```

---

## Units Reference

### CPU

| Value | Meaning |
|-------|---------|
| `1` | 1 vCPU/core |
| `500m` | 0.5 vCPU (500 millicores) |
| `100m` | 0.1 vCPU (100 millicores) |
| `250m` | 0.25 vCPU (250 millicores) |

### Memory

| Value | Meaning |
|-------|---------|
| `128Mi` | 128 Mebibytes (134 MB) |
| `1Gi` | 1 Gibibyte (1.07 GB) |
| `512M` | 512 Megabytes |
| `2G` | 2 Gigabytes |

**Prefer `Mi` and `Gi`** (binary units) for consistency.

---

## Workload Sizing Guide

### API Servers (Lightweight)

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

### API Servers (Standard)

```yaml
resources:
  requests:
    cpu: "250m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "1Gi"
```

### Background Workers

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "512Mi"
  limits:
    cpu: "2000m"
    memory: "2Gi"
```

### ML Inference (CPU)

```yaml
resources:
  requests:
    cpu: "2000m"
    memory: "4Gi"
  limits:
    cpu: "4000m"
    memory: "8Gi"
```

### ML Training (GPU)

```yaml
resources:
  requests:
    cpu: "4000m"
    memory: "16Gi"
    nvidia.com/gpu: 1
  limits:
    cpu: "8000m"
    memory: "32Gi"
    nvidia.com/gpu: 1
```

---

## Best Practices

### 1. Always Set Both Requests and Limits

```yaml
# GOOD: Both set
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"

# BAD: Missing requests
resources:
  limits:
    cpu: "500m"
    memory: "512Mi"
```

### 2. Request:Limit Ratio

**Conservative (predictable)**: 1:1 ratio
```yaml
requests:
  cpu: "500m"
limits:
  cpu: "500m"
```

**Bursty workloads**: 1:2 to 1:5 ratio
```yaml
requests:
  cpu: "100m"    # Baseline
limits:
  cpu: "500m"    # Peak usage
```

### 3. Memory Limits = Memory Requests

Avoid OOM kills from overcommit:
```yaml
requests:
  memory: "512Mi"
limits:
  memory: "512Mi"  # Same as request
```

---

## Quality of Service (QoS) Classes

| Class | Criteria | Behavior |
|-------|----------|----------|
| **Guaranteed** | requests = limits for all resources | Highest priority, last to evict |
| **Burstable** | requests < limits | Medium priority |
| **BestEffort** | No requests or limits | First to evict under pressure |

**For production**: Always use Guaranteed or Burstable.

---

## LimitRange (Namespace Defaults)

Set defaults for pods without resource specs:

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: production
spec:
  limits:
  - default:
      cpu: "500m"
      memory: "512Mi"
    defaultRequest:
      cpu: "100m"
      memory: "128Mi"
    max:
      cpu: "2000m"
      memory: "4Gi"
    min:
      cpu: "50m"
      memory: "64Mi"
    type: Container
```

---

## ResourceQuota (Namespace Limits)

Limit total resources per namespace:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: compute-quota
  namespace: dev
spec:
  hard:
    requests.cpu: "10"       # 10 cores total
    requests.memory: 20Gi    # 20 GiB total
    limits.cpu: "20"         # 20 cores max
    limits.memory: 40Gi      # 40 GiB max
    pods: "50"               # 50 pods max
```

---

## Monitoring Actual Usage

Get recommendations from actual usage:

```bash
# View current resource usage
kubectl top pods -n production

# View resource requests/limits
kubectl describe pod <pod-name> | grep -A 5 "Requests\|Limits"

# Use Vertical Pod Autoscaler for recommendations
kubectl get vpa -n production
```

---

## HPA Interaction

HPA scales based on requests, not limits:

```yaml
# If request is 100m CPU and target is 80%,
# HPA scales when pod uses 80m or more
resources:
  requests:
    cpu: "100m"    # HPA uses this for scaling decisions
  limits:
    cpu: "500m"    # Burst capacity
```

**Tip**: Set requests at typical usage, limits at peak usage.
