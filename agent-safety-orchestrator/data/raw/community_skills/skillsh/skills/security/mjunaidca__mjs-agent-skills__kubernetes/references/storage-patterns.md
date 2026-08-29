# Storage Patterns

Ephemeral, persistent, and shared storage for Kubernetes workloads.

---

## Storage Decision Tree

```
Does the data need to persist after pod deletion?
├─ No → emptyDir or ConfigMap
└─ Yes: Is it shared across pods?
        ├─ Yes → PVC with ReadWriteMany
        └─ No → PVC with ReadWriteOnce
```

---

## Ephemeral Storage

### emptyDir

Temporary storage deleted with pod:

```yaml
spec:
  containers:
  - name: app
    volumeMounts:
    - name: cache
      mountPath: /cache
    - name: tmp
      mountPath: /tmp
  volumes:
  - name: cache
    emptyDir:
      sizeLimit: 1Gi           # Optional limit
  - name: tmp
    emptyDir: {}
```

**Use cases**: Caches, temp files, inter-container sharing

### emptyDir with tmpfs

In-memory storage (faster, lost on reboot):

```yaml
volumes:
- name: scratch
  emptyDir:
    medium: Memory
    sizeLimit: 500Mi           # Counts against memory limits!
```

---

## PersistentVolumeClaim

### Basic PVC

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-pvc
spec:
  accessModes:
  - ReadWriteOnce              # Single pod access
  storageClassName: standard   # Cloud provider default
  resources:
    requests:
      storage: 10Gi
```

### Using PVC in Pod

```yaml
spec:
  containers:
  - name: app
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: data-pvc
```

---

## Access Modes

| Mode | Short | Description |
|------|-------|-------------|
| `ReadWriteOnce` | RWO | Single node read/write |
| `ReadOnlyMany` | ROX | Many nodes read-only |
| `ReadWriteMany` | RWX | Many nodes read/write |
| `ReadWriteOncePod` | RWOP | Single pod read/write (K8s 1.22+) |

**Note**: Not all storage classes support all modes.

---

## Volume Modes

```yaml
spec:
  volumeMode: Filesystem       # Default: mounted as directory
  # or
  volumeMode: Block            # Raw block device
```

---

## Storage Classes

### Standard (Default)

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard
provisioner: kubernetes.io/gce-pd
parameters:
  type: pd-standard
reclaimPolicy: Delete
allowVolumeExpansion: true
```

### Fast SSD

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/gce-pd
parameters:
  type: pd-ssd
reclaimPolicy: Retain          # Keep data after PVC deletion
allowVolumeExpansion: true
```

---

## StatefulSet with Storage

Each pod gets its own PVC:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres
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
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:        # Creates PVC per pod
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 100Gi
```

**Result**: `data-postgres-0`, `data-postgres-1`, `data-postgres-2` PVCs

---

## Shared Storage (ReadWriteMany)

### NFS-based

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: shared-data
spec:
  accessModes:
  - ReadWriteMany              # Multiple pods
  storageClassName: nfs
  resources:
    requests:
      storage: 100Gi
```

### Using in Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: workers
spec:
  replicas: 10                 # All share same volume
  template:
    spec:
      containers:
      - name: worker
        volumeMounts:
        - name: shared
          mountPath: /shared
      volumes:
      - name: shared
        persistentVolumeClaim:
          claimName: shared-data
```

---

## Model Caching (AI Workloads)

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: model-cache
spec:
  accessModes:
  - ReadWriteMany              # Share across inference pods
  storageClassName: fast-ssd
  resources:
    requests:
      storage: 200Gi           # For large models
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: inference
spec:
  replicas: 5
  template:
    spec:
      containers:
      - name: inference
        volumeMounts:
        - name: models
          mountPath: /root/.cache/huggingface
        - name: tmp
          mountPath: /tmp
      volumes:
      - name: models
        persistentVolumeClaim:
          claimName: model-cache
      - name: tmp
        emptyDir: {}
```

---

## ConfigMap as Volume

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  config.yaml: |
    database:
      host: postgres
      port: 5432
---
spec:
  containers:
  - name: app
    volumeMounts:
    - name: config
      mountPath: /etc/app
      readOnly: true
  volumes:
  - name: config
    configMap:
      name: app-config
```

---

## Secret as Volume

```yaml
spec:
  containers:
  - name: app
    volumeMounts:
    - name: certs
      mountPath: /etc/ssl/certs
      readOnly: true
  volumes:
  - name: certs
    secret:
      secretName: tls-certs
      defaultMode: 0400        # Restrict permissions
```

---

## Projected Volumes

Combine multiple sources:

```yaml
spec:
  containers:
  - name: app
    volumeMounts:
    - name: all-config
      mountPath: /etc/config
  volumes:
  - name: all-config
    projected:
      sources:
      - configMap:
          name: app-config
      - secret:
          name: app-secrets
      - downwardAPI:
          items:
          - path: "labels"
            fieldRef:
              fieldPath: metadata.labels
```

---

## Volume Expansion

Expand PVC without downtime (if storage class allows):

```bash
# Edit PVC
kubectl patch pvc data-pvc -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
```

```yaml
# Storage class must have:
allowVolumeExpansion: true
```

---

## Cloud-Specific Storage

### AWS EBS

```yaml
storageClassName: gp3
# or for high IOPS
storageClassName: io2
```

### GCP Persistent Disk

```yaml
storageClassName: pd-ssd
# or for standard
storageClassName: pd-standard
```

### Azure Disk

```yaml
storageClassName: managed-premium
# or for standard
storageClassName: managed-standard
```

---

## Anti-Patterns

### DON'T: Use hostPath in Production

```yaml
# BAD: Ties pod to specific node, security risk
volumes:
- name: data
  hostPath:
    path: /data
```

### DON'T: Forget fsGroup

```yaml
# BAD: Volume permissions may prevent access
spec:
  containers:
  - name: app
    volumeMounts:
    - name: data
      mountPath: /data

# GOOD: Set fsGroup for volume ownership
spec:
  securityContext:
    fsGroup: 1000              # Files owned by this group
```
