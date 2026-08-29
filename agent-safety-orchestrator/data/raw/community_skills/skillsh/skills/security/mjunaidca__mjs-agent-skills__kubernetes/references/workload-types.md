# Workload Types Decision Guide

## Decision Tree

```
Is this a batch task that runs to completion?
├─ Yes: Does it run on a schedule?
│       ├─ Yes → CronJob
│       └─ No → Job
└─ No: Does it need stable network identity?
       ├─ Yes → StatefulSet
       └─ No: Must it run on every node?
              ├─ Yes → DaemonSet
              └─ No → Deployment
```

---

## Deployment

**Use for**: Stateless applications where pods are interchangeable.

**Characteristics**:
- Pods can be replaced/rescheduled freely
- Rolling updates with zero downtime
- Horizontal scaling via replicas or HPA
- No persistent identity

**Examples**: API servers, web frontends, stateless workers

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      containers:
      - name: api
        image: myapp:v1.0.0
        ports:
        - containerPort: 8000
```

---

## StatefulSet

**Use for**: Stateful applications requiring stable identity and storage.

### Deployment vs StatefulSet

| Aspect | Deployment | StatefulSet |
|--------|-----------|-------------|
| **Pod Identity** | Random (`pod-abc123`) | Stable ordinal (`db-0`, `db-1`) |
| **Scaling Order** | Parallel (all at once) | Sequential (0→1→2) |
| **Storage** | Shared or ephemeral | Per-pod persistent (survives restart) |
| **Network** | Dynamic IP via Service | Stable DNS per pod |
| **Best For** | Stateless APIs, workers | Databases, message brokers, caches |

### Characteristics

- Stable, unique network identifiers (pod-0, pod-1, ...)
- Stable, persistent storage per pod
- Ordered, graceful deployment and scaling
- Ordered, automated rolling updates

### DNS Resolution

Each pod gets predictable DNS:

```
{pod-name}.{service-name}.{namespace}.svc.cluster.local

Examples:
postgres-0.postgres.default.svc.cluster.local
postgres-1.postgres.default.svc.cluster.local
qdrant-0.qdrant.ai-prod.svc.cluster.local
```

### Ordered Lifecycle

**Startup**: Sequential, waits for Ready
```
postgres-0 (Running, Ready) → postgres-1 starts → postgres-2 starts
```

**Shutdown**: Reverse order (highest first)
```
postgres-2 terminates → postgres-1 terminates → postgres-0 terminates
```

### Basic Example (Database)

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres  # Headless service name
  replicas: 3
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: standard
      resources:
        requests:
          storage: 10Gi
```

**Headless Service** (required for StatefulSet):
```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  clusterIP: None  # Headless - direct pod DNS
  selector:
    app: postgres
  ports:
  - port: 5432
```

### AI Pattern: Vector Database (Qdrant)

Vector databases need stable identity for shard ownership:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: qdrant
spec:
  serviceName: qdrant
  replicas: 3
  selector:
    matchLabels:
      app: qdrant
  template:
    metadata:
      labels:
        app: qdrant
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: qdrant
        image: qdrant/qdrant:v1.7.0
        ports:
        - containerPort: 6333
          name: http
        - containerPort: 6334
          name: grpc
        env:
        # WHY: Each replica knows its position in cluster
        - name: QDRANT__CLUSTER__ENABLED
          value: "true"
        volumeMounts:
        - name: storage
          mountPath: /qdrant/storage
        resources:
          requests:
            cpu: "500m"
            memory: "2Gi"
          limits:
            cpu: "2"
            memory: "8Gi"
  volumeClaimTemplates:
  - metadata:
      name: storage
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 50Gi
---
apiVersion: v1
kind: Service
metadata:
  name: qdrant
spec:
  clusterIP: None
  selector:
    app: qdrant
  ports:
  - port: 6333
    name: http
  - port: 6334
    name: grpc
```

### AI Pattern: LLM Inference with Local Cache

Cache large models on persistent storage:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: llm-inference
spec:
  serviceName: llm-inference
  replicas: 3
  selector:
    matchLabels:
      app: llm-inference
  template:
    metadata:
      labels:
        app: llm-inference
    spec:
      containers:
      - name: inference
        image: llm-server:v1.0.0
        env:
        # WHY: Each replica caches model locally
        - name: MODEL_CACHE_DIR
          value: /models
        - name: REPLICA_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name  # llm-inference-0, etc.
        volumeMounts:
        - name: model-cache
          mountPath: /models
        resources:
          requests:
            cpu: "4"
            memory: "16Gi"
          limits:
            cpu: "8"
            memory: "32Gi"
  volumeClaimTemplates:
  - metadata:
      name: model-cache
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 100Gi  # Large models need space
```

### Rolling Updates with Partition

Test updates on specific replicas before full rollout:

```yaml
spec:
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      partition: 2  # Only update replicas >= 2
```

```bash
# Update image, only replica-2 gets new version
kubectl set image statefulset/qdrant qdrant=qdrant/qdrant:v1.8.0

# Verify replica-2 works, then update all
kubectl patch statefulset qdrant -p '{"spec":{"updateStrategy":{"rollingUpdate":{"partition":0}}}}'
```

### StatefulSet Debugging

```bash
# Check StatefulSet status
kubectl get statefulset
kubectl describe statefulset <name>

# Watch pod creation order
kubectl get pods -l app=<name> -w

# Check PVCs created by volumeClaimTemplates
kubectl get pvc -l app=<name>
# PVCs named: data-postgres-0, data-postgres-1, data-postgres-2

# Scale (adds/removes in order)
kubectl scale statefulset <name> --replicas=5

# Force delete stuck pod (use cautiously)
kubectl delete pod <pod-name> --grace-period=0 --force
```

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Pod stuck Pending | PVC not bound | Check StorageClass, PV availability |
| Pod won't start | Previous pod not Ready | Check pod-0 logs first |
| Data lost on restart | Wrong volumeMount path | Verify mountPath matches app expectation |
| DNS not resolving | Missing headless Service | Create Service with `clusterIP: None` |

---

## DaemonSet

**Use for**: Node-level agents that must run on every (or selected) nodes.

**Characteristics**:
- One pod per node
- Auto-deploys to new nodes
- Supports node selectors/tolerations

**Examples**: Log collectors, monitoring agents, network plugins, storage drivers

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
spec:
  selector:
    matchLabels:
      app: node-exporter
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      tolerations:
      # Run on all nodes including control plane
      - operator: Exists
      containers:
      - name: node-exporter
        image: prom/node-exporter:v1.6.0
        ports:
        - containerPort: 9100
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 100m
            memory: 128Mi
```

---

## Job

**Use for**: Batch tasks that run to completion.

**Characteristics**:
- Runs until successful completion
- Tracks successful completions
- Supports parallelism
- Auto-retries on failure

**Examples**: Database migrations, batch processing, report generation

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate
spec:
  backoffLimit: 3  # Retry 3 times on failure
  activeDeadlineSeconds: 600  # Timeout after 10 minutes
  template:
    spec:
      restartPolicy: Never  # Required for Jobs
      containers:
      - name: migrate
        image: myapp:v1.0.0
        command: ["python", "manage.py", "migrate"]
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
```

**Parallel Job** (process queue items):
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: queue-processor
spec:
  parallelism: 5        # 5 pods running in parallel
  completions: 100      # Process 100 items total
  backoffLimit: 10
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: processor
        image: worker:v1.0.0
```

---

## CronJob

**Use for**: Scheduled batch tasks.

**Characteristics**:
- Runs Jobs on a schedule
- Cron syntax for scheduling
- Configurable concurrency policy
- Job history retention

**Examples**: Nightly backups, hourly reports, daily cleanup

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup
spec:
  schedule: "0 2 * * *"  # Daily at 2am
  concurrencyPolicy: Forbid  # Don't start if previous still running
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: backup
            image: backup-tool:v1.0.0
            command: ["./backup.sh"]
```

**Cron Syntax**:
```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sun-Sat)
│ │ │ │ │
* * * * *
```

**Examples**:
- `0 * * * *` - Every hour
- `*/15 * * * *` - Every 15 minutes
- `0 0 * * 0` - Every Sunday at midnight
- `0 9 1 * *` - First of every month at 9am

**Concurrency Policies**:

| Policy | Effect |
|--------|--------|
| `Allow` | Create new Job even if previous running (default) |
| `Forbid` | Skip if previous Job still running |
| `Replace` | Cancel running Job and start new one |

---

## Advanced Job Features

### Auto-Cleanup with TTL

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: one-time-migration
spec:
  ttlSecondsAfterFinished: 3600  # Delete Job+Pods 1 hour after completion
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: migrate
        image: migrator:v1
```

### Indexed Parallel Jobs

Process items by index (0, 1, 2, ...):

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: indexed-processor
spec:
  completions: 10
  parallelism: 3
  completionMode: Indexed  # Enable JOB_COMPLETION_INDEX
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: worker
        image: processor:v1
        env:
        - name: JOB_INDEX
          valueFrom:
            fieldRef:
              fieldPath: metadata.annotations['batch.kubernetes.io/job-completion-index']
        command: ["./process.sh"]
        args: ["--partition=$(JOB_INDEX)"]
```

---

## AI Batch Processing Patterns

### Pattern 1: Nightly Embedding Refresh

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: embedding-sync
spec:
  schedule: "0 3 * * *"           # 3 AM daily
  concurrencyPolicy: Forbid       # Skip if previous still running
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: sync
            image: embedding-sync:v1
            env:
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: openai-credentials
                  key: api-key
            - name: VECTOR_DB_URL
              value: "http://qdrant:6333"
            resources:
              requests:
                cpu: "500m"
                memory: "1Gi"
              limits:
                cpu: "2"
                memory: "4Gi"
```

### Pattern 2: One-Time Model Migration

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: model-migration-v2
spec:
  backoffLimit: 2
  activeDeadlineSeconds: 3600     # 1 hour max
  ttlSecondsAfterFinished: 86400  # Cleanup after 24 hours
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: migrate
        image: model-migrator:v2
        env:
        - name: SOURCE_MODEL
          value: "gpt-3.5-turbo"
        - name: TARGET_MODEL
          value: "gpt-4o-mini"
        resources:
          requests:
            cpu: "1"
            memory: "2Gi"
```

### Pattern 3: Parallel Document Ingestion

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: document-ingest
spec:
  completions: 100        # 100 batches to process
  parallelism: 10         # 10 parallel workers
  completionMode: Indexed
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: ingest
        image: doc-processor:v1
        env:
        - name: BATCH_INDEX
          valueFrom:
            fieldRef:
              fieldPath: metadata.annotations['batch.kubernetes.io/job-completion-index']
        - name: TOTAL_BATCHES
          value: "100"
        command: ["python", "ingest.py"]
        args: ["--batch=$(BATCH_INDEX)", "--total=$(TOTAL_BATCHES)"]
```

---

## Job Debugging

### Monitor Job Progress

```bash
# Watch Job status
kubectl get jobs -w

# Detailed Job info
kubectl describe job <job-name>

# View Job pods
kubectl get pods -l job-name=<job-name>

# Check logs
kubectl logs job/<job-name>

# Logs from specific pod
kubectl logs <pod-name>
```

### Common Failures

| Symptom | Check | Fix |
|---------|-------|-----|
| Job stuck at 0 completions | `kubectl describe job` | Check image, resources |
| Pods in CrashLoopBackOff | `kubectl logs <pod>` | Fix application error |
| Job exceeded deadline | `activeDeadlineSeconds` | Increase or optimize |
| backoffLimit exceeded | `kubectl describe job` | Fix root cause, increase limit |

### CronJob Debugging

```bash
# View CronJob schedule
kubectl get cronjobs

# Check last schedule time
kubectl describe cronjob <name>

# See Jobs created by CronJob
kubectl get jobs -l cronjob-name=<name>

# Manual trigger (for testing)
kubectl create job --from=cronjob/<name> manual-test
```
