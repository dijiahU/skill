# KEDA Patterns

Event-driven autoscaling and scale-to-zero for Kubernetes.

---

## What is KEDA

KEDA (Kubernetes Event-Driven Autoscaling) extends Kubernetes with:
- Scale to/from zero (not possible with HPA alone)
- Event-driven scaling (queues, schedules, external metrics)
- 70+ scalers for various event sources

---

## Core Resources

| Resource | Purpose |
|----------|---------|
| `ScaledObject` | Scale Deployments/StatefulSets |
| `ScaledJob` | Scale Jobs (create jobs based on events) |
| `TriggerAuthentication` | Store credentials for event sources |

---

## Basic ScaledObject

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: worker-scaler
spec:
  scaleTargetRef:
    name: worker              # Deployment name
  minReplicaCount: 0          # Scale to zero!
  maxReplicaCount: 100
  cooldownPeriod: 300         # 5 min before scale down
  pollingInterval: 30         # Check every 30s
  triggers:
  - type: prometheus          # Trigger type
    metadata:
      serverAddress: http://prometheus:9090
      query: sum(rate(http_requests_total[2m]))
      threshold: "100"
```

---

## Common Triggers

### RabbitMQ Queue

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rabbitmq-secret
data:
  host: <base64-encoded-url>  # http://guest:password@rabbitmq:15672/
---
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: rabbitmq-auth
spec:
  secretTargetRef:
  - parameter: host
    name: rabbitmq-secret
    key: host
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: queue-worker
spec:
  scaleTargetRef:
    name: queue-worker
  minReplicaCount: 0
  maxReplicaCount: 50
  triggers:
  - type: rabbitmq
    metadata:
      protocol: http
      queueName: tasks
      mode: QueueLength        # or MessageRate
      value: "20"              # 1 pod per 20 messages
    authenticationRef:
      name: rabbitmq-auth
```

### Prometheus

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: api-scaler
spec:
  scaleTargetRef:
    name: api-server
  minReplicaCount: 1          # Don't scale to zero for API
  maxReplicaCount: 50
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus:9090
      threshold: "100"
      query: |
        sum(rate(http_requests_total{deployment="api-server"}[2m]))
      # Optional: activation threshold (when to start scaling)
      activationThreshold: "10"
```

### Redis List

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: redis-worker
spec:
  scaleTargetRef:
    name: redis-worker
  minReplicaCount: 0
  maxReplicaCount: 30
  triggers:
  - type: redis
    metadata:
      address: redis:6379
      listName: job-queue
      listLength: "10"         # 1 pod per 10 items
      databaseIndex: "0"
```

### Cron (Schedule-Based)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: batch-processor
spec:
  scaleTargetRef:
    name: batch-processor
  minReplicaCount: 0
  maxReplicaCount: 10
  triggers:
  - type: cron
    metadata:
      timezone: America/New_York
      start: "0 8 * * 1-5"     # Mon-Fri 8am
      end: "0 18 * * 1-5"      # Mon-Fri 6pm
      desiredReplicas: "5"
```

### Kafka

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: kafka-consumer
spec:
  scaleTargetRef:
    name: kafka-consumer
  minReplicaCount: 0
  maxReplicaCount: 100
  triggers:
  - type: kafka
    metadata:
      bootstrapServers: kafka:9092
      consumerGroup: my-group
      topic: events
      lagThreshold: "100"      # 1 pod per 100 lag
```

---

## ScaledJob (Batch Processing)

Creates Jobs instead of scaling Deployments:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: image-processor
spec:
  jobTargetRef:
    parallelism: 1
    completions: 1
    backoffLimit: 3
    template:
      spec:
        restartPolicy: Never
        containers:
        - name: processor
          image: processor:v1
          command: ["./process.sh"]
  pollingInterval: 30
  successfulJobsHistoryLimit: 5
  failedJobsHistoryLimit: 5
  maxReplicaCount: 100
  triggers:
  - type: rabbitmq
    metadata:
      queueName: images
      mode: QueueLength
      value: "1"               # 1 job per message
    authenticationRef:
      name: rabbitmq-auth
```

---

## TriggerAuthentication

### From Secret

```yaml
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: prometheus-auth
spec:
  secretTargetRef:
  - parameter: bearerToken
    name: prometheus-secret
    key: token
```

### From Environment

```yaml
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: api-key-auth
spec:
  env:
  - parameter: apiKey
    name: API_KEY
    containerName: worker
```

### Cluster-Wide

```yaml
apiVersion: keda.sh/v1alpha1
kind: ClusterTriggerAuthentication
metadata:
  name: azure-auth
spec:
  secretTargetRef:
  - parameter: connectionString
    name: azure-storage
    key: connectionString
```

---

## Scaling Behavior

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: worker
spec:
  scaleTargetRef:
    name: worker
  minReplicaCount: 0
  maxReplicaCount: 100

  # Scaling behavior
  cooldownPeriod: 300          # Wait 5 min before scale down
  pollingInterval: 30          # Check triggers every 30s

  # Advanced: HPA-style behavior
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          stabilizationWindowSeconds: 300
          policies:
          - type: Percent
            value: 10
            periodSeconds: 60
        scaleUp:
          stabilizationWindowSeconds: 0
          policies:
          - type: Pods
            value: 10
            periodSeconds: 15
```

---

## Common Patterns

### Scale-to-Zero Worker

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: worker
spec:
  scaleTargetRef:
    name: worker
  minReplicaCount: 0           # Scale to zero when idle
  maxReplicaCount: 50
  cooldownPeriod: 300          # 5 min idle before zero
  triggers:
  - type: rabbitmq
    metadata:
      queueName: tasks
      mode: QueueLength
      value: "5"
    authenticationRef:
      name: rabbitmq-auth
```

### Business Hours Only

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: api
spec:
  scaleTargetRef:
    name: api
  minReplicaCount: 0
  maxReplicaCount: 10
  triggers:
  # Scale based on load during business hours
  - type: cron
    metadata:
      timezone: America/New_York
      start: "0 8 * * 1-5"
      end: "0 18 * * 1-5"
      desiredReplicas: "2"
  # Also scale on CPU when running
  - type: cpu
    metadata:
      type: Utilization
      value: "70"
```

### Multi-Queue Worker

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: multi-worker
spec:
  scaleTargetRef:
    name: worker
  minReplicaCount: 0
  maxReplicaCount: 100
  triggers:
  # Scale on high-priority queue
  - type: rabbitmq
    metadata:
      queueName: high-priority
      mode: QueueLength
      value: "1"               # Process immediately
    authenticationRef:
      name: rabbitmq-auth
  # Also scale on normal queue
  - type: rabbitmq
    metadata:
      queueName: normal
      mode: QueueLength
      value: "10"
    authenticationRef:
      name: rabbitmq-auth
```

---

## Installation

```bash
# Helm
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda --namespace keda --create-namespace

# Verify
kubectl get pods -n keda
```
