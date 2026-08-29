# Security Contexts

Production-hardened security patterns for Kubernetes workloads.

---

## Default Security Context (ALWAYS APPLY)

```yaml
spec:
  # Pod-level security
  securityContext:
    runAsNonRoot: true              # Never run as root
    runAsUser: 1000                 # Consistent non-root UID
    runAsGroup: 1000                # Consistent GID
    fsGroup: 1000                   # Volume ownership
    seccompProfile:
      type: RuntimeDefault          # Block dangerous syscalls

  containers:
  - name: app
    # Container-level security
    securityContext:
      allowPrivilegeEscalation: false  # Block sudo/setuid
      readOnlyRootFilesystem: true     # Immutable container
      capabilities:
        drop: ["ALL"]                  # Remove all capabilities
```

---

## Field Reference

### Pod Security Context

| Field | Purpose | Default |
|-------|---------|---------|
| `runAsNonRoot` | Fail if container tries to run as root | true |
| `runAsUser` | UID for container processes | 1000 |
| `runAsGroup` | GID for container processes | 1000 |
| `fsGroup` | GID for volume ownership | 1000 |
| `seccompProfile.type` | Syscall filtering | RuntimeDefault |

### Container Security Context

| Field | Purpose | Default |
|-------|---------|---------|
| `allowPrivilegeEscalation` | Block setuid/sudo | false |
| `readOnlyRootFilesystem` | Prevent writes to / | true |
| `capabilities.drop` | Remove Linux capabilities | ["ALL"] |
| `capabilities.add` | Add specific capabilities | [] |

---

## Handling Read-Only Filesystem

When `readOnlyRootFilesystem: true`, apps needing write access require emptyDir volumes:

```yaml
spec:
  containers:
  - name: app
    securityContext:
      readOnlyRootFilesystem: true
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: cache
      mountPath: /var/cache
  volumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir:
      sizeLimit: 100Mi  # Optional size limit
```

**Common writable paths**:
- `/tmp` - Temporary files
- `/var/cache` - Application caches
- `/var/run` - Runtime files (PID files, sockets)
- `/home/appuser` - User home directory

---

## Network Policies

Restrict pod-to-pod communication:

### Default Deny All

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: production
spec:
  podSelector: {}  # Apply to all pods
  policyTypes:
  - Ingress
  - Egress
```

### Allow Specific Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-policy
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8000
```

### Allow Egress to Database

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-egress
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
  # Allow DNS
  - to:
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

---

## Capabilities Reference

**Rarely needed capabilities** (add only if required):

| Capability | Use Case |
|------------|----------|
| NET_BIND_SERVICE | Bind ports <1024 |
| SYS_TIME | Modify system clock |
| CHOWN | Change file ownership |

```yaml
securityContext:
  capabilities:
    drop: ["ALL"]
    add: ["NET_BIND_SERVICE"]  # Only if needed
```

---

## ValidatingAdmissionPolicy (K8s 1.26+)

Cluster-wide policy enforcement:

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata:
  name: require-security-context
spec:
  failurePolicy: Fail
  matchConstraints:
    resourceRules:
    - apiGroups: ["apps"]
      apiVersions: ["v1"]
      operations: ["CREATE", "UPDATE"]
      resources: ["deployments"]
  validations:
  - expression: |
      object.spec.template.spec.containers.all(c,
        has(c.securityContext) &&
        has(c.securityContext.runAsNonRoot) &&
        c.securityContext.runAsNonRoot)
    message: 'all containers must set runAsNonRoot to true'
  - expression: |
      object.spec.template.spec.containers.all(c,
        has(c.securityContext) &&
        has(c.securityContext.readOnlyRootFilesystem) &&
        c.securityContext.readOnlyRootFilesystem)
    message: 'all containers must set readOnlyRootFilesystem to true'
  - expression: |
      object.spec.template.spec.containers.all(c,
        !has(c.securityContext) ||
        !has(c.securityContext.allowPrivilegeEscalation) ||
        !c.securityContext.allowPrivilegeEscalation)
    message: 'no container may set allowPrivilegeEscalation to true'
```

---

## Pod Security Standards (PSS)

Apply namespace-level enforcement:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

**Levels**:
- `privileged` - Unrestricted (avoid)
- `baseline` - Minimal restrictions
- `restricted` - Hardened (recommended for production)
