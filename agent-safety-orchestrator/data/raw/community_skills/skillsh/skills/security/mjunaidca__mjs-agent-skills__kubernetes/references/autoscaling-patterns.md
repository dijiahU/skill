# Autoscaling Patterns

HPA, custom metrics, and KEDA patterns for production workloads.

---

## Quick Commands

### Create HPA (Imperative)

```bash
# Quick HPA creation for testing
kubectl autoscale deployment api --cpu-percent=70 --min=2 --max=10

# With memory (requires metrics-server)
kubectl autoscale deployment worker --cpu-percent=80 --min=1 --max=20
```

### Monitor HPA

```bash
# Check HPA status
kubectl get hpa

# Detailed view with targets
kubectl get hpa -o wide

# Watch scaling in real-time
kubectl get hpa -w

# Describe for events and conditions
kubectl describe hpa api-hpa
```

### Resource Monitoring

```bash
# Pod resource usage (requires metrics-server)
kubectl top pods

# Node resource usage
kubectl top nodes

# Specific deployment pods
kubectl top pods -l app=api
```

### Debug HPA

```bash
# Check if metrics-server is running
kubectl get pods -n kube-system | grep metrics-server

# Verify metrics available
kubectl get --raw "/apis/metrics.k8s.io/v1beta1/pods"

# HPA conditions and events
kubectl describe hpa <hpa-name> | grep -A 20 "Conditions\|Events"
```

---

## Prerequisites

### Metrics Server (Required)

HPA requires metrics-server to read CPU/memory usage:

```bash
# Verify metrics-server is running
kubectl get deployment metrics-server -n kube-system

# Expected output:
# NAME             READY   UP-TO-DATE   AVAILABLE
# metrics-server   1/1     1            1

# If not installed (kind/minikube)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# For local clusters, may need insecure TLS
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
```

### Verify Metrics Available

```bash
# Wait 1-2 minutes after install, then:
kubectl top nodes
kubectl top pods

# If "error: Metrics API not available", wait or check metrics-server logs
kubectl logs -n kube-system deployment/metrics-server
```

---

## Scaling Mathematics

### The Formula

```
desired_replicas = ceil(current_replicas × (current_usage / target_usage))
```

### Examples

| Current Pods | Current CPU | Target CPU | Calculation | Result |
|--------------|-------------|------------|-------------|--------|
| 2 | 80% | 50% | ceil(2 × 80/50) = ceil(3.2) | **4 pods** |
| 3 | 70% | 50% | ceil(3 × 70/50) = ceil(4.2) | **5 pods** |
| 6 | 20% | 50% | ceil(6 × 20/50) = ceil(2.4) | **3 pods** |
| 4 | 50% | 50% | ceil(4 × 50/50) = ceil(4.0) | **4 pods** (no change) |

**Key insight**: HPA biases toward scaling UP (ceil rounds up). Brief spikes trigger scale-up, but scale-down requires sustained low usage due to stabilization window.

### Target Utilization Guidelines

| Target % | Use Case |
|----------|----------|
| 30-40% | Over-provisioned, wasting resources |
| **50-70%** | Recommended for most workloads |
| 80-90% | Aggressive, slow spike response |
| >90% | Risky, may not handle traffic bursts |

---

## Troubleshooting

### Problem: `<unknown>` in TARGETS Column

```bash
kubectl get hpa
# NAME         TARGETS         MINPODS   MAXPODS   REPLICAS
# api-hpa      <unknown>/70%   2         10        2
```

**Causes & Fixes:**

| Cause | Fix |
|-------|-----|
| Metrics-server not running | `kubectl get deploy metrics-server -n kube-system` |
| Metrics not collected yet | Wait 1-2 minutes after deployment |
| Deployment doesn't exist | Verify `scaleTargetRef` name matches |
| No resource requests | Add `resources.requests.cpu` to container |

```bash
# Verify deployment has resource requests
kubectl get deploy <name> -o jsonpath='{.spec.template.spec.containers[0].resources.requests}'
```

### Problem: HPA Not Scaling Despite High CPU

```bash
# Check node capacity - maybe can't schedule more pods
kubectl top nodes
kubectl describe nodes | grep -A 5 "Allocated resources"

# Check for scheduling failures
kubectl get events --field-selector reason=FailedScheduling

# Check if pods are OOMKilled (wrong limit, not CPU issue)
kubectl describe pod <pod> | grep -A 3 "Last State"

# Verify HPA sees the metrics
kubectl describe hpa <name> | grep -A 10 "Metrics"
```

### Problem: Constant Scale Up/Down (Thrashing)

**Cause**: Stabilization window too short or workload highly variable.

**Fix**: Increase stabilization window:

```yaml
behavior:
  scaleDown:
    stabilizationWindowSeconds: 600  # 10 minutes
  scaleUp:
    stabilizationWindowSeconds: 60   # 1 minute buffer
```

### Problem: Scale-Down Too Slow

**Cause**: Default 300s stabilization for scaleDown.

**Fix**: Reduce window (carefully):

```yaml
behavior:
  scaleDown:
    stabilizationWindowSeconds: 120  # 2 minutes
    policies:
    - type: Percent
      value: 25              # Remove 25% at a time (not 100%)
      periodSeconds: 60
```

---

## Autoscaling Decision Tree

```
Need to scale based on external events (queues, schedules)?
├─ Yes → KEDA (see keda-patterns.md)
└─ No: Need custom metrics (requests/sec, queue depth)?
       ├─ Yes → HPA v2 with custom metrics
       └─ No → HPA v2 with CPU/Memory
```

---

## HPA v2 (autoscaling/v2)

### Basic CPU/Memory Scaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 2        # Minimum for availability
  maxReplicas: 10       # Cost ceiling
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70   # Scale at 70% CPU

  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # 5 min cooldown
      policies:
      - type: Percent
        value: 10              # Scale down 10% at a time
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0   # Scale up immediately
      policies:
      - type: Percent
        value: 100             # Double pods if needed
        periodSeconds: 15
      - type: Pods
        value: 4               # Add up to 4 pods at once
        periodSeconds: 15
```

### Memory-Based Scaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: worker
  minReplicas: 1
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: memory
      target:
        type: AverageValue
        averageValue: 500Mi    # Scale when avg > 500Mi
```

### Multi-Metric Scaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 2
  maxReplicas: 10
  metrics:
  # Scale on CPU OR memory (whichever is higher)
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## Custom Metrics

### Prometheus Adapter Setup

```yaml
# Prometheus Adapter config for custom metrics
rules:
- seriesQuery: 'http_requests_total{namespace!="",pod!=""}'
  resources:
    overrides:
      namespace: {resource: "namespace"}
      pod: {resource: "pod"}
  name:
    matches: "^(.*)_total$"
    as: "${1}_per_second"
  metricsQuery: 'rate(<<.Series>>{<<.LabelMatchers>>}[2m])'
```

### HPA with Custom Metrics

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 2
  maxReplicas: 50
  metrics:
  # Scale on requests per second
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: 100    # 100 req/s per pod
```

### External Metrics (Queue Depth)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: worker
  minReplicas: 1
  maxReplicas: 100
  metrics:
  - type: External
    external:
      metric:
        name: rabbitmq_queue_messages
        selector:
          matchLabels:
            queue: "tasks"
      target:
        type: AverageValue
        averageValue: 10    # 10 messages per pod
```

---

## Scaling Behavior

### Conservative (Default for Production)

```yaml
behavior:
  scaleDown:
    stabilizationWindowSeconds: 300  # Wait 5 min before scaling down
    policies:
    - type: Percent
      value: 10                      # Remove 10% of pods at a time
      periodSeconds: 60
  scaleUp:
    stabilizationWindowSeconds: 0    # Scale up immediately
    policies:
    - type: Percent
      value: 50                      # Add 50% more pods
      periodSeconds: 30
```

### Aggressive (Event-Driven)

```yaml
behavior:
  scaleDown:
    stabilizationWindowSeconds: 60   # 1 min cooldown
    policies:
    - type: Pods
      value: 5                       # Remove 5 pods at a time
      periodSeconds: 30
  scaleUp:
    stabilizationWindowSeconds: 0
    policies:
    - type: Pods
      value: 10                      # Add 10 pods at once
      periodSeconds: 10
```

### Prevent Scale Down

```yaml
behavior:
  scaleDown:
    selectPolicy: Disabled           # Never scale down
```

---

## Pod Disruption Budget (PDB)

Ensure availability during scaling and updates:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  # At least 2 pods must be available
  minAvailable: 2
  # OR: At most 1 pod can be unavailable
  # maxUnavailable: 1
  selector:
    matchLabels:
      app: api-server
```

**Best Practice**: Always create PDB alongside HPA.

---

## Common Patterns

### Web API (CPU-Based)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api
```

### AI Inference Service (Latency-Based)

AI inference workloads are CPU-intensive with unpredictable traffic. Scale on CPU with conservative scale-down:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: inference-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: inference-api
  minReplicas: 2          # Always ready for requests
  maxReplicas: 20         # Cost ceiling
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50   # Lower target for inference latency
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0    # Immediate response to spikes
      policies:
      - type: Percent
        value: 100                     # Double capacity quickly
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 600  # 10 min - inference traffic is bursty
      policies:
      - type: Percent
        value: 10                      # Slow scale-down
        periodSeconds: 60
```

**AI-Specific Considerations:**

| Factor | Recommendation |
|--------|----------------|
| Target CPU | 50% (lower than web APIs) - inference needs headroom |
| Scale-down window | 600s+ (bursty traffic patterns) |
| Min replicas | 2+ (cold start latency is expensive) |
| Resource requests | Must reflect actual model memory/CPU needs |

### AI with Custom Metrics (Latency/Queue)

For advanced AI deployments, scale on inference latency or request queue:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: inference-latency-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: inference-api
  minReplicas: 2
  maxReplicas: 50
  metrics:
  # Scale when p95 latency exceeds 500ms
  - type: Pods
    pods:
      metric:
        name: inference_latency_p95_seconds
      target:
        type: AverageValue
        averageValue: "0.5"    # 500ms target
  # OR scale on pending requests
  - type: Pods
    pods:
      metric:
        name: inference_queue_depth
      target:
        type: AverageValue
        averageValue: "5"      # 5 pending requests per pod
```

**Requires**: Prometheus Adapter with custom metrics from your inference service.

### Test Deployment (CPU Stress)

For testing HPA behavior:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cpu-stress
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cpu-stress
  template:
    metadata:
      labels:
        app: cpu-stress
    spec:
      containers:
      - name: stress
        image: python:3.11-slim
        command: ["python", "-c"]
        args:
          - |
            import time
            while True:
              # CPU-intensive loop
              for i in range(1000000):
                _ = i * 2
              time.sleep(0.1)
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
```

### Queue Worker (Queue-Based)

Use KEDA for queue-based scaling - see `keda-patterns.md`.

### Batch Processor (Schedule-Based)

Use KEDA cron trigger - see `keda-patterns.md`.

---

## Vertical Pod Autoscaler (VPA)

For automatic resource request tuning:

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: api-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  updatePolicy:
    updateMode: "Off"   # Recommendation only
  resourcePolicy:
    containerPolicies:
    - containerName: api
      minAllowed:
        cpu: 100m
        memory: 128Mi
      maxAllowed:
        cpu: 2
        memory: 4Gi
```

**Modes**:
- `Off`: Only recommendations (check with `kubectl describe vpa`)
- `Initial`: Set on pod creation only
- `Auto`: Live updates (can cause restarts)

---

## Anti-Patterns

### DON'T: Scale on Memory for Java/Node

```yaml
# BAD: JVM/Node expands heap to limit, then stays there
metrics:
- type: Resource
  resource:
    name: memory
    target:
      type: Utilization
      averageUtilization: 80
```

### DON'T: Min = Max

```yaml
# BAD: No scaling range
minReplicas: 5
maxReplicas: 5   # Why have HPA?
```

### DON'T: Forget PDB

```yaml
# BAD: HPA without PDB risks downtime during scale-down
# Missing PodDisruptionBudget
```
