# ConfigMap Patterns

Non-sensitive configuration data for Kubernetes applications.

---

## When to Use

| Trigger | Action |
|---------|--------|
| "Add configuration to deployment" | ConfigMap + volume/env mount |
| "Externalize config from container" | ConfigMap with app settings |
| "Hot-reload config without restart" | ConfigMap + Reloader |
| "Store config files for pods" | ConfigMap as volume |

---

## ConfigMap vs Secret Decision

| Data Type | Use | Why |
|-----------|-----|-----|
| Database connection strings | **Secret** | Contains credentials |
| API endpoints (no auth) | **ConfigMap** | Non-sensitive |
| Feature flags | **ConfigMap** | Non-sensitive |
| TLS certificates | **Secret** | Sensitive |
| Application config (no secrets) | **ConfigMap** | Non-sensitive |
| Environment-specific settings | **ConfigMap** | Non-sensitive |

**Rule**: If leaking it would cause harm → Secret. Otherwise → ConfigMap.

---

## Creating ConfigMaps

### From Literal Values

```bash
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=info \
  --from-literal=MAX_CONNECTIONS=100 \
  --from-literal=CACHE_TTL=3600
```

### From File

```bash
# Single file
kubectl create configmap nginx-config \
  --from-file=nginx.conf

# File with custom key name
kubectl create configmap nginx-config \
  --from-file=config=nginx.conf
```

### From Directory

```bash
# All files in directory become keys
kubectl create configmap app-configs \
  --from-file=./config/
```

### From env File

```bash
# .env format: KEY=value per line
kubectl create configmap app-env \
  --from-env-file=app.env
```

---

## ConfigMap YAML

### Basic ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  labels:
    app.kubernetes.io/name: myapp
data:
  # Simple key-value pairs
  LOG_LEVEL: "info"
  MAX_CONNECTIONS: "100"
  CACHE_TTL: "3600"

  # Multi-line config file
  config.yaml: |
    database:
      host: postgres.default.svc.cluster.local
      port: 5432
      pool_size: 10
    logging:
      level: info
      format: json

  # JSON config
  settings.json: |
    {
      "feature_flags": {
        "new_ui": true,
        "beta_features": false
      }
    }
```

### Binary Data

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: binary-config
binaryData:
  # Base64-encoded binary files
  logo.png: iVBORw0KGgoAAAANSUhEUgAA...
  font.woff2: d09GMgABAAAAA...
data:
  # Regular text data can coexist
  version: "1.0.0"
```

**Note**: Use `binaryData` for non-UTF-8 content (images, fonts, compiled assets).

---

## Using ConfigMaps as Environment Variables

### All Keys as Env Vars (envFrom)

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: app
        image: myapp:latest
        envFrom:
        # WHY: All keys in ConfigMap become env vars
        - configMapRef:
            name: app-config
        # Optional: Add prefix to avoid collisions
        - configMapRef:
            name: db-config
            prefix: DB_
```

### Specific Keys (valueFrom)

```yaml
spec:
  containers:
  - name: app
    env:
    # WHY: Select specific keys, can rename
    - name: APP_LOG_LEVEL
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: LOG_LEVEL
    - name: APP_MAX_CONN
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: MAX_CONNECTIONS
          optional: true  # WHY: Don't fail if key missing
```

### Multiple ConfigMaps

```yaml
spec:
  containers:
  - name: app
    envFrom:
    - configMapRef:
        name: app-config
    - configMapRef:
        name: feature-flags
    - secretRef:
        name: app-secrets
```

**Priority**: Later entries override earlier ones for duplicate keys.

---

## Using ConfigMaps as Volumes

### Mount Entire ConfigMap

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: app
        image: myapp:latest
        volumeMounts:
        - name: config-volume
          mountPath: /etc/app/config
          readOnly: true
      volumes:
      - name: config-volume
        configMap:
          name: app-config
          # WHY: Set file permissions (octal)
          defaultMode: 0644
```

**Result**: Each key becomes a file at `/etc/app/config/<key>`.

### Mount Specific Keys (items)

```yaml
volumes:
- name: config-volume
  configMap:
    name: app-config
    items:
    # WHY: Only mount specific keys, control filenames
    - key: config.yaml
      path: application.yaml    # Custom filename
      mode: 0644
    - key: settings.json
      path: settings.json
```

### Mount Single File (subPath)

```yaml
volumeMounts:
- name: config-volume
  mountPath: /etc/nginx/nginx.conf
  subPath: nginx.conf           # WHY: Mount single file, not directory
  readOnly: true
```

**Warning**: `subPath` mounts don't receive automatic updates when ConfigMap changes.

### Preserve Existing Directory Contents

```yaml
volumeMounts:
# WITHOUT subPath: /etc/app becomes symlink, existing files hidden
- name: config
  mountPath: /etc/app

# WITH subPath: Only adds specific file, preserves existing
- name: config
  mountPath: /etc/app/custom.conf
  subPath: custom.conf
```

---

## Immutable ConfigMaps

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-v1
immutable: true               # WHY: Can't be modified after creation
data:
  LOG_LEVEL: "info"
```

**Benefits**:
- Protects against accidental changes
- Improves cluster performance (no watch needed)
- Kubelet doesn't poll for updates

**Trade-off**: Must delete and recreate to change. Use versioned names (app-config-v1, v2).

---

## Hot-Reload with Stakater Reloader

ConfigMap changes don't automatically restart pods. Use Reloader:

### Install Reloader

```bash
kubectl apply -f https://raw.githubusercontent.com/stakater/Reloader/master/deployments/kubernetes/reloader.yaml
```

### Enable Auto-Reload

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  annotations:
    # WHY: Reloader watches this ConfigMap, triggers rolling restart on change
    configmap.reloader.stakater.com/reload: "app-config"
    # Multiple ConfigMaps
    # configmap.reloader.stakater.com/reload: "app-config,feature-flags"
spec:
  template:
    spec:
      containers:
      - name: app
        envFrom:
        - configMapRef:
            name: app-config
```

### Reload on Any ConfigMap Change

```yaml
metadata:
  annotations:
    # WHY: Reload when ANY mounted ConfigMap changes
    reloader.stakater.com/auto: "true"
```

### Alternative: Checksum Annotation

Without Reloader, force restart by changing annotation:

```yaml
spec:
  template:
    metadata:
      annotations:
        # WHY: Change this value to trigger rolling restart
        checksum/config: "sha256-of-configmap-content"
```

Generate with: `kubectl get configmap app-config -o yaml | sha256sum`

---

## Size Limits and Constraints

| Constraint | Limit |
|------------|-------|
| **Total size** | 1 MiB (1,048,576 bytes) |
| **Key name** | 253 characters, alphanumeric + `-_.` |
| **Number of keys** | No hard limit (stay under total size) |

### Handling Large Configs

```yaml
# BAD: Single large config exceeds limit
data:
  huge-config.json: |
    { ... 2MB of JSON ... }

# GOOD: Split into multiple ConfigMaps
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-base
data:
  base.yaml: |
    # Core settings
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-features
data:
  features.yaml: |
    # Feature flags
```

---

## Update Propagation

| Mount Type | Auto-Update | Delay |
|------------|-------------|-------|
| Volume (no subPath) | ✅ Yes | ~1 minute (kubelet sync) |
| Volume with subPath | ❌ No | Never (pod restart required) |
| Environment variable | ❌ No | Never (pod restart required) |

### Reduce Update Delay

```yaml
# kubelet config (node-level)
syncFrequency: 10s    # Default: 1m
configMapAndSecretChangeDetectionStrategy: Watch  # vs Get
```

---

## Common Patterns

### Environment-Specific ConfigMaps

```yaml
# base/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  LOG_LEVEL: "info"
  API_URL: "https://api.example.com"

---
# overlays/dev/configmap-patch.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  LOG_LEVEL: "debug"
  API_URL: "https://api-dev.example.com"
```

### ConfigMap + Init Container

```yaml
spec:
  initContainers:
  - name: config-processor
    image: busybox
    command: ['sh', '-c', 'envsubst < /config-template/app.conf > /config/app.conf']
    volumeMounts:
    - name: config-template
      mountPath: /config-template
    - name: processed-config
      mountPath: /config
  containers:
  - name: app
    volumeMounts:
    - name: processed-config
      mountPath: /etc/app
  volumes:
  - name: config-template
    configMap:
      name: app-config-template
  - name: processed-config
    emptyDir: {}
```

### Projected Volume (ConfigMap + Secret + Downward API)

```yaml
volumes:
- name: combined-config
  projected:
    sources:
    - configMap:
        name: app-config
        items:
        - key: config.yaml
          path: config.yaml
    - secret:
        name: app-secrets
        items:
        - key: api-key
          path: secrets/api-key
    - downwardAPI:
        items:
        - path: labels
          fieldRef:
            fieldPath: metadata.labels
```

---

## Best Practices

| Practice | Why |
|----------|-----|
| Use descriptive key names | `database.host` > `DB_H` |
| Version ConfigMaps for immutability | `app-config-v1`, `app-config-v2` |
| Don't store secrets | Even "encrypted" - use Secrets |
| Keep under 100KB | Large ConfigMaps slow etcd |
| Use labels consistently | Enable bulk operations |
| Document expected keys | Help operators understand config |

### Naming Convention

```yaml
# Pattern: <app>-<purpose>-config
metadata:
  name: myapp-database-config   # Database settings
  name: myapp-logging-config    # Logging settings
  name: myapp-features-config   # Feature flags
```

---

## Debugging

```bash
# View ConfigMap
kubectl get configmap app-config -o yaml

# Describe (shows events)
kubectl describe configmap app-config

# Check if mounted in pod
kubectl exec -it mypod -- ls -la /etc/app/config/

# Verify env vars
kubectl exec -it mypod -- env | grep APP_

# Check ConfigMap update time
kubectl get configmap app-config -o jsonpath='{.metadata.resourceVersion}'
```

---

## Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Secrets in ConfigMap | Exposed in logs, etcd | Use Secret |
| Huge ConfigMaps | Slow etcd, sync delays | Split or use external config |
| subPath + hot-reload expectation | Updates never propagate | Restart pod or avoid subPath |
| Hardcoded config in image | Rebuild to change config | Externalize to ConfigMap |
| No resource versioning | Can't rollback config | Use immutable + versioned names |
