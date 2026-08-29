# Init Containers & Sidecars

Patterns for setup tasks and helper containers in AI workloads.

---

## Concepts

### Init Containers

Run **sequentially to completion** before app containers start.

```
Init-1 → Init-2 → Init-3 → App Container(s)
         (each must succeed)
```

**Use for**: Setup tasks that MUST complete before app starts.

### Sidecar Containers (K8s 1.28+)

Run **alongside** app containers for the entire Pod lifetime.

```yaml
# Native sidecar: init container with restartPolicy: Always
initContainers:
- name: logging-sidecar
  restartPolicy: Always  # Makes it a sidecar
```

**Use for**: Ongoing tasks (logging, metrics, proxying).

---

## Init Container Patterns

### Pattern 1: Model Download (AI Critical)

Download ML model before inference agent starts:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: inference-agent
spec:
  initContainers:
  # WHY: Agent crashes with FileNotFoundError if model missing
  - name: download-model
    image: alpine:3.18
    command: ['sh', '-c']
    args:
    - |
      echo "Downloading model..."
      wget -q -O /models/sentiment.bin \
        https://models.example.com/sentiment-v2.bin
      echo "Model downloaded: $(ls -lh /models/)"
    volumeMounts:
    - name: model-storage
      mountPath: /models
    resources:
      requests:
        cpu: "100m"
        memory: "256Mi"
      limits:
        cpu: "500m"
        memory: "512Mi"

  containers:
  - name: agent
    image: inference-api:v1.0.0
    env:
    - name: MODEL_PATH
      value: /models/sentiment.bin
    volumeMounts:
    - name: model-storage
      mountPath: /models
      readOnly: true  # WHY: Agent only reads model
    # ... rest of container spec

  volumes:
  # WHY: emptyDir shares data between init and app containers
  - name: model-storage
    emptyDir:
      sizeLimit: 2Gi  # WHY: Prevent runaway disk usage
```

### Pattern 2: Wait for Dependencies

Wait for database/Redis/Kafka before app starts:

```yaml
initContainers:
# WHY: App crashes if DB not ready, causing CrashLoopBackOff
- name: wait-for-postgres
  image: busybox:1.36
  command: ['sh', '-c']
  args:
  - |
    echo "Waiting for PostgreSQL..."
    until nc -z postgres-service 5432; do
      echo "Postgres not ready, sleeping 2s..."
      sleep 2
    done
    echo "PostgreSQL is ready!"
  resources:
    requests:
      cpu: "10m"
      memory: "16Mi"
    limits:
      cpu: "50m"
      memory: "32Mi"

- name: wait-for-redis
  image: busybox:1.36
  command: ['sh', '-c']
  args:
  - |
    until nc -z redis-service 6379; do
      sleep 2
    done
    echo "Redis is ready!"
  resources:
    requests:
      cpu: "10m"
      memory: "16Mi"
```

### Pattern 3: Database Migration

Run migrations before app starts:

```yaml
initContainers:
- name: run-migrations
  image: myapp:v1.0.0  # WHY: Same image has migration tools
  command: ['python', 'manage.py', 'migrate', '--noinput']
  env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: db-credentials
        key: url
  resources:
    requests:
      cpu: "100m"
      memory: "256Mi"
    limits:
      cpu: "500m"
      memory: "512Mi"
```

### Pattern 4: Config Validation

Validate config files exist and are valid:

```yaml
initContainers:
- name: validate-config
  image: busybox:1.36
  command: ['sh', '-c']
  args:
  - |
    # Check required files exist
    for file in /config/app.yaml /secrets/api-key; do
      if [ ! -f "$file" ]; then
        echo "ERROR: Required file missing: $file"
        exit 1
      fi
    done

    # Validate YAML syntax
    if ! grep -q "^model:" /config/app.yaml; then
      echo "ERROR: Missing 'model' key in config"
      exit 1
    fi

    echo "Config validation passed!"
  volumeMounts:
  - name: config
    mountPath: /config
  - name: secrets
    mountPath: /secrets
```

### Pattern 5: Init with Retry Logic

Handle transient failures (network timeouts):

```yaml
initContainers:
- name: download-model-retry
  image: alpine:3.18
  command: ['sh', '-c']
  args:
  - |
    MAX_ATTEMPTS=5
    ATTEMPT=1

    while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
      echo "Download attempt $ATTEMPT of $MAX_ATTEMPTS..."

      if wget -q -T 30 -O /models/model.bin \
           https://models.example.com/model.bin; then
        echo "Download successful!"
        exit 0
      fi

      echo "Download failed, retrying in 5s..."
      ATTEMPT=$((ATTEMPT + 1))
      sleep 5
    done

    echo "ERROR: All download attempts failed"
    exit 1
  volumeMounts:
  - name: model-storage
    mountPath: /models
```

---

## Sidecar Patterns (K8s 1.28+)

### Native Sidecar Syntax

```yaml
initContainers:
- name: my-sidecar
  image: sidecar-image:v1
  restartPolicy: Always  # KEY: Makes it a sidecar
  # Starts before app, runs alongside, restarts independently
```

**Lifecycle:**
1. Sidecars start (with `restartPolicy: Always`)
2. App containers start after sidecars ready
3. Sidecars run for entire Pod lifetime
4. If sidecar crashes, K8s restarts it (doesn't affect app)

### Pattern 1: Logging Sidecar

Collect logs and forward to centralized service:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: agent-with-logging
spec:
  initContainers:
  # WHY: Native sidecar - starts before app, runs alongside
  - name: log-collector
    image: fluent/fluent-bit:2.2
    restartPolicy: Always
    volumeMounts:
    - name: log-volume
      mountPath: /var/log/agent
    - name: fluent-config
      mountPath: /fluent-bit/etc
    resources:
      requests:
        cpu: "50m"
        memory: "64Mi"
      limits:
        cpu: "200m"
        memory: "128Mi"

  containers:
  - name: agent
    image: inference-api:v1.0.0
    env:
    - name: LOG_FILE
      value: /var/log/agent/requests.log
    volumeMounts:
    - name: log-volume
      mountPath: /var/log/agent
    # ... rest of spec

  volumes:
  - name: log-volume
    emptyDir: {}
  - name: fluent-config
    configMap:
      name: fluent-bit-config
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         5
        Daemon        Off
        Log_Level     info

    [INPUT]
        Name          tail
        Path          /var/log/agent/*.log
        Tag           agent.*

    [OUTPUT]
        Name          forward
        Match         *
        Host          fluentd-aggregator
        Port          24224
```

### Pattern 2: Metrics Sidecar

Expose Prometheus metrics endpoint:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: agent-with-metrics
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "9090"
    prometheus.io/path: "/metrics"
spec:
  initContainers:
  - name: metrics-exporter
    image: prom/statsd-exporter:v0.26.0
    restartPolicy: Always
    ports:
    - containerPort: 9090
      name: metrics
    - containerPort: 9125
      name: statsd
      protocol: UDP
    volumeMounts:
    - name: statsd-config
      mountPath: /etc/statsd
    args:
    - --statsd.mapping-config=/etc/statsd/mapping.yaml
    resources:
      requests:
        cpu: "50m"
        memory: "64Mi"
      limits:
        cpu: "200m"
        memory: "128Mi"

  containers:
  - name: agent
    image: inference-api:v1.0.0
    env:
    # WHY: App sends metrics to sidecar via localhost
    - name: STATSD_HOST
      value: "localhost"
    - name: STATSD_PORT
      value: "9125"
    ports:
    - containerPort: 8000
      name: http

  volumes:
  - name: statsd-config
    configMap:
      name: statsd-mapping
```

### Pattern 3: Request Audit Sidecar

Log all inference requests/responses for compliance:

```yaml
initContainers:
- name: audit-logger
  image: audit-sidecar:v1.0.0
  restartPolicy: Always
  env:
  - name: LISTEN_PORT
    value: "8080"        # WHY: Sidecar receives traffic first
  - name: UPSTREAM_PORT
    value: "8000"        # WHY: Forwards to actual app
  - name: AUDIT_LOG_PATH
    value: /audit/requests.jsonl
  ports:
  - containerPort: 8080
    name: audit-proxy
  volumeMounts:
  - name: audit-logs
    mountPath: /audit
  resources:
    requests:
      cpu: "100m"
      memory: "128Mi"

containers:
- name: agent
  image: inference-api:v1.0.0
  ports:
  - containerPort: 8000  # WHY: Internal port, sidecar proxies
    name: internal
```

### Pattern 4: Combined Init + Sidecar

Model download (init) + logging (sidecar):

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: full-ai-agent
spec:
  initContainers:
  # INIT: Download model first (runs to completion)
  - name: download-model
    image: alpine:3.18
    command: ['wget', '-O', '/models/model.bin', 'https://models.example.com/v2.bin']
    volumeMounts:
    - name: models
      mountPath: /models

  # SIDECAR: Logging (runs alongside app)
  - name: log-collector
    image: fluent/fluent-bit:2.2
    restartPolicy: Always
    volumeMounts:
    - name: logs
      mountPath: /var/log/agent

  # SIDECAR: Metrics (runs alongside app)
  - name: metrics
    image: prom/statsd-exporter:v0.26.0
    restartPolicy: Always
    ports:
    - containerPort: 9090

  containers:
  - name: agent
    image: inference-api:v1.0.0
    volumeMounts:
    - name: models
      mountPath: /models
      readOnly: true
    - name: logs
      mountPath: /var/log/agent

  volumes:
  - name: models
    emptyDir:
      sizeLimit: 2Gi
  - name: logs
    emptyDir: {}
```

---

## Volume Sharing

### emptyDir (Most Common)

```yaml
volumes:
- name: shared-data
  emptyDir: {}          # Default: node's disk
  # OR
  emptyDir:
    medium: Memory      # WHY: Faster, but uses RAM quota
    sizeLimit: 1Gi      # WHY: Prevent runaway usage
```

### Read-Only for App Container

```yaml
initContainers:
- name: setup
  volumeMounts:
  - name: data
    mountPath: /data    # Writes here

containers:
- name: app
  volumeMounts:
  - name: data
    mountPath: /data
    readOnly: true      # WHY: App only reads, can't corrupt
```

---

## Debugging Init Containers

### Check Init Status

```bash
# View init container status
kubectl get pod <pod-name> -o jsonpath='{.status.initContainerStatuses[*].name}'

# Detailed init container state
kubectl describe pod <pod-name> | grep -A 20 "Init Containers"
```

### View Init Logs

```bash
# Current run
kubectl logs <pod-name> -c <init-container-name>

# Previous failed run
kubectl logs <pod-name> -c <init-container-name> --previous
```

### Common Init Failures

| Status | Cause | Fix |
|--------|-------|-----|
| `Init:0/2` | First init still running | Check logs, may be slow |
| `Init:Error` | Init failed with error | Check logs for error message |
| `Init:CrashLoopBackOff` | Init keeps failing | Fix script or add retry logic |

### Debug Init Container Issue

```bash
# 1. Check which init failed
kubectl get pod failing-pod -o jsonpath='{.status.initContainerStatuses}'

# 2. Get logs from failed init
kubectl logs failing-pod -c download-model

# 3. Check events for scheduling issues
kubectl describe pod failing-pod | grep -A 10 "Events"
```

---

## Debugging Sidecars

### Check All Containers

```bash
# List all containers (init sidecars + app)
kubectl get pod <pod-name> -o jsonpath='{.spec.initContainers[*].name} {.spec.containers[*].name}'

# Check READY status (e.g., 3/3 = all healthy)
kubectl get pod <pod-name>
```

### View Sidecar Logs

```bash
# Sidecar logs
kubectl logs <pod-name> -c log-collector

# Follow sidecar logs
kubectl logs <pod-name> -c metrics-exporter -f
```

### Common Sidecar Issues

| Issue | Symptom | Fix |
|-------|---------|-----|
| Volume mismatch | Sidecar can't read logs | Verify same mountPath in both containers |
| Port conflict | Connection refused | Check ports don't overlap |
| Config missing | Sidecar crashes | Verify ConfigMap exists and mounted |
| Permission denied | Can't write to volume | Check securityContext, fsGroup |

---

## Decision Tree

```
Need setup BEFORE app starts?
├─ Yes: Is it one-time or ongoing?
│       ├─ One-time → Init Container
│       └─ Ongoing → Sidecar (restartPolicy: Always)
└─ No: Does it need to run alongside app?
       ├─ Yes → Sidecar
       └─ No → Separate Pod/Deployment
```

| Task Type | Use | Example |
|-----------|-----|---------|
| Download model | Init | `wget` to emptyDir |
| Wait for DB | Init | `nc -z` loop |
| Run migrations | Init | `python manage.py migrate` |
| Collect logs | Sidecar | fluent-bit |
| Export metrics | Sidecar | statsd-exporter |
| Proxy/audit | Sidecar | Request interceptor |

---

## Anti-Patterns

### DON'T: Long-Running Init Container

```yaml
# BAD: This should be a sidecar
initContainers:
- name: log-collector
  command: ['tail', '-f', '/var/log/app.log']  # Never completes!
```

### DON'T: Heavy Work in App Container

```yaml
# BAD: Model download blocks app startup
containers:
- name: agent
  command: ['sh', '-c', 'wget model.bin && python app.py']
```

### DON'T: Missing Resource Limits on Init

```yaml
# BAD: Init can consume unlimited resources
initContainers:
- name: download-model
  # No resources specified - can starve node
```

### DON'T: Forget Volume Sharing

```yaml
# BAD: Init writes to /data, app reads from /models
initContainers:
- name: setup
  volumeMounts:
  - name: data
    mountPath: /data       # Writes here

containers:
- name: app
  volumeMounts:
  - name: data
    mountPath: /models     # Different path!
```
