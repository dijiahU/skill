# Kubernetes Security Reference

## Overview

This reference provides comprehensive Kubernetes security configurations including Pod Security Standards, RBAC, network policies, secrets management, and admission control.

## Pod Security Standards (PSS)

### Security Levels

| Level | Description | Use Case |
| --- | --- | --- |
| **Privileged** | Unrestricted, allows all | System workloads, privileged pods |
| **Baseline** | Minimally restrictive | General workloads |
| **Restricted** | Heavily restricted | Security-critical workloads |

### Namespace Configuration

```yaml
# Restricted namespace with enforcement
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    # Enforce restricted policy (reject violations)
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: v1.28

    # Warn on restricted violations (allow but warn)
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: v1.28

    # Audit all for logging
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/audit-version: v1.28
---
# Baseline namespace for less restrictive workloads
apiVersion: v1
kind: Namespace
metadata:
  name: internal-tools
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/enforce-version: v1.28
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

### Pod Security Context Templates

```yaml
# Restricted-compliant pod template
apiVersion: v1
kind: Pod
metadata:
  name: secure-pod
spec:
  # Pod-level security context
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
    fsGroupChangePolicy: OnRootMismatch
    seccompProfile:
      type: RuntimeDefault
    supplementalGroups: [1000]

  serviceAccountName: restricted-sa
  automountServiceAccountToken: false

  containers:
    - name: app
      image: myapp:v1.0.0
      securityContext:
        allowPrivilegeEscalation: false
        privileged: false
        readOnlyRootFilesystem: true
        runAsNonRoot: true
        runAsUser: 1000
        capabilities:
          drop:
            - ALL
        seccompProfile:
          type: RuntimeDefault

      resources:
        limits:
          cpu: "500m"
          memory: "256Mi"
          ephemeral-storage: "100Mi"
        requests:
          cpu: "100m"
          memory: "128Mi"

      volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: cache
          mountPath: /var/cache

  volumes:
    - name: tmp
      emptyDir:
        sizeLimit: 100Mi
    - name: cache
      emptyDir:
        sizeLimit: 100Mi

  # Host isolation
  hostNetwork: false
  hostPID: false
  hostIPC: false

  # DNS configuration
  dnsPolicy: ClusterFirst
```

## RBAC Configuration

### Principle of Least Privilege

```yaml
# Minimal service account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-sa
  namespace: production
automountServiceAccountToken: false
---
# Read-only role for specific resources
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: app-reader
  namespace: production
rules:
  # Read specific configmap
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["app-config"]
    verbs: ["get"]

  # Read specific secret
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["app-tls"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-reader-binding
  namespace: production
subjects:
  - kind: ServiceAccount
    name: app-sa
    namespace: production
roleRef:
  kind: Role
  name: app-reader
  apiGroup: rbac.authorization.k8s.io
```

### Cluster-Level RBAC

```yaml
# Read-only cluster role for monitoring
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: monitoring-reader
rules:
  - apiGroups: [""]
    resources: ["pods", "nodes", "services", "endpoints"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets", "statefulsets", "daemonsets"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["metrics.k8s.io"]
    resources: ["pods", "nodes"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: monitoring-reader-binding
subjects:
  - kind: ServiceAccount
    name: prometheus
    namespace: monitoring
roleRef:
  kind: ClusterRole
  name: monitoring-reader
  apiGroup: rbac.authorization.k8s.io
```

### RBAC Audit Script

```bash
#!/bin/bash
# Audit RBAC for security issues

echo "=== Cluster Admin Bindings ==="
kubectl get clusterrolebindings -o json | jq -r '
  .items[] | select(.roleRef.name == "cluster-admin") |
  "Binding: \(.metadata.name), Subjects: \(.subjects | map(.name) | join(", "))"'

echo -e "\n=== Service Accounts with Cluster Admin ==="
kubectl get clusterrolebindings -o json | jq -r '
  .items[] | select(.roleRef.name == "cluster-admin") |
  .subjects[]? | select(.kind == "ServiceAccount") |
  "\(.namespace)/\(.name)"'

echo -e "\n=== Roles with Wildcard Resources ==="
kubectl get roles,clusterroles -A -o json | jq -r '
  .items[] | select(.rules[]?.resources[]? == "*") |
  "\(.metadata.namespace // "cluster")/\(.metadata.name)"'

echo -e "\n=== Roles with Wildcard Verbs ==="
kubectl get roles,clusterroles -A -o json | jq -r '
  .items[] | select(.rules[]?.verbs[]? == "*") |
  "\(.metadata.namespace // "cluster")/\(.metadata.name)"'

echo -e "\n=== Service Account Token Auto-Mount ==="
kubectl get pods -A -o json | jq -r '
  .items[] |
  select(.spec.automountServiceAccountToken != false) |
  select(.spec.serviceAccountName != "default") |
  "\(.metadata.namespace)/\(.metadata.name): SA=\(.spec.serviceAccountName)"' | head -20
```

## Network Policies

### Zero-Trust Network Model

```yaml
# Default deny all traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
# Allow DNS resolution
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

### Micro-Segmentation Example

```yaml
# Frontend can only talk to API
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: frontend
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - port: 8080
  egress:
    # Allow to API service
    - to:
        - podSelector:
            matchLabels:
              app: api
      ports:
        - port: 8080
    # Allow DNS
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - port: 53
          protocol: UDP
---
# API can talk to database
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend
      ports:
        - port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - port: 5432
    # DNS
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - port: 53
          protocol: UDP
---
# Database only accepts from API
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: database-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: postgres
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api
      ports:
        - port: 5432
  egress: []  # No egress allowed
```

## Admission Control

### OPA Gatekeeper Policies

```yaml
# Install Gatekeeper
# helm install gatekeeper gatekeeper/gatekeeper -n gatekeeper-system

# Constraint Template: Require labels
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredlabels
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredLabels
      validation:
        openAPIV3Schema:
          type: object
          properties:
            labels:
              type: array
              items:
                type: string
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8srequiredlabels

        violation[{"msg": msg, "details": {"missing_labels": missing}}] {
          provided := {label | input.review.object.metadata.labels[label]}
          required := {label | label := input.parameters.labels[_]}
          missing := required - provided
          count(missing) > 0
          msg := sprintf("Missing required labels: %v", [missing])
        }
---
# Apply constraint
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-team-label
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Namespace", "Pod"]
      - apiGroups: ["apps"]
        kinds: ["Deployment", "StatefulSet"]
  parameters:
    labels: ["team", "environment"]
```

### Container Registry Restriction

```yaml
# Only allow images from trusted registries
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8sallowedregistries
spec:
  crd:
    spec:
      names:
        kind: K8sAllowedRegistries
      validation:
        openAPIV3Schema:
          type: object
          properties:
            registries:
              type: array
              items:
                type: string
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8sallowedregistries

        violation[{"msg": msg}] {
          container := input.review.object.spec.containers[_]
          not registry_allowed(container.image)
          msg := sprintf("Image '%v' is from an untrusted registry", [container.image])
        }

        violation[{"msg": msg}] {
          container := input.review.object.spec.initContainers[_]
          not registry_allowed(container.image)
          msg := sprintf("Init container image '%v' is from an untrusted registry", [container.image])
        }

        registry_allowed(image) {
          registry := input.parameters.registries[_]
          startswith(image, registry)
        }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sAllowedRegistries
metadata:
  name: allowed-registries
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
    namespaces: ["production", "staging"]
  parameters:
    registries:
      - "gcr.io/my-project/"
      - "us-docker.pkg.dev/my-project/"
      - "docker.io/library/"
```

## Secrets Management

### Encrypted Secrets at Rest

```yaml
# EncryptionConfiguration for kube-apiserver
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: <base64-encoded-32-byte-key>
      - identity: {}  # Fallback for reading unencrypted secrets
```

### External Secrets Operator

```yaml
# SecretStore for AWS Secrets Manager
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
            namespace: external-secrets
---
# External Secret
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-secrets
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: app-secrets
    creationPolicy: Owner
  data:
    - secretKey: database-password
      remoteRef:
        key: production/app/database
        property: password
    - secretKey: api-key
      remoteRef:
        key: production/app/api
        property: key
```

### Sealed Secrets

```yaml
# Install sealed-secrets controller
# helm install sealed-secrets sealed-secrets/sealed-secrets -n kube-system

# Create sealed secret
# kubectl create secret generic my-secret \
#   --from-literal=password=secret123 \
#   --dry-run=client -o yaml | kubeseal -o yaml > sealed-secret.yaml

apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: my-secret
  namespace: production
spec:
  encryptedData:
    password: AgBy3i...encrypted...
```

## Runtime Security

### Falco DaemonSet

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: falco
  namespace: falco
spec:
  selector:
    matchLabels:
      app: falco
  template:
    metadata:
      labels:
        app: falco
    spec:
      serviceAccountName: falco
      tolerations:
        - effect: NoSchedule
          key: node-role.kubernetes.io/master
      containers:
        - name: falco
          image: falcosecurity/falco:0.37.0
          securityContext:
            privileged: true
          args:
            - /usr/bin/falco
            - --cri
            - /run/containerd/containerd.sock
            - -K
            - /var/run/secrets/kubernetes.io/serviceaccount/token
            - -k
            - https://kubernetes.default
            - --k8s-node
            - $(FALCO_K8S_NODE_NAME)
            - -pk
          env:
            - name: FALCO_K8S_NODE_NAME
              valueFrom:
                fieldRef:
                  fieldPath: spec.nodeName
          volumeMounts:
            - name: containerd-socket
              mountPath: /run/containerd/containerd.sock
            - name: proc
              mountPath: /host/proc
              readOnly: true
            - name: boot
              mountPath: /host/boot
              readOnly: true
            - name: lib-modules
              mountPath: /host/lib/modules
              readOnly: true
            - name: config
              mountPath: /etc/falco
      volumes:
        - name: containerd-socket
          hostPath:
            path: /run/containerd/containerd.sock
        - name: proc
          hostPath:
            path: /proc
        - name: boot
          hostPath:
            path: /boot
        - name: lib-modules
          hostPath:
            path: /lib/modules
        - name: config
          configMap:
            name: falco-config
```

### Audit Logging

```yaml
# Audit policy
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  # Don't log requests to these endpoints
  - level: None
    resources:
      - group: ""
        resources: ["endpoints", "services", "services/status"]
    users:
      - system:kube-proxy

  # Don't log health checks
  - level: None
    nonResourceURLs:
      - /healthz*
      - /livez*
      - /readyz*

  # Log secret access at Metadata level
  - level: Metadata
    resources:
      - group: ""
        resources: ["secrets", "configmaps"]

  # Log pod execution
  - level: Request
    resources:
      - group: ""
        resources: ["pods/exec", "pods/portforward", "pods/attach"]

  # Log RBAC changes at RequestResponse level
  - level: RequestResponse
    resources:
      - group: "rbac.authorization.k8s.io"
        resources: ["roles", "rolebindings", "clusterroles", "clusterrolebindings"]

  # Log all other requests at Metadata level
  - level: Metadata
    omitStages:
      - RequestReceived
```

## Security Checklist

### Cluster Hardening

- [ ] RBAC enabled and configured
- [ ] Pod Security Standards enforced
- [ ] Network policies implemented
- [ ] Audit logging enabled
- [ ] Secrets encrypted at rest
- [ ] API server authentication configured
- [ ] etcd encrypted and access controlled
- [ ] Node OS hardened
- [ ] kubelet authentication enabled

### Workload Security

- [ ] Non-root containers
- [ ] Read-only root filesystem
- [ ] No privileged containers
- [ ] Capabilities dropped
- [ ] Resource limits set
- [ ] Seccomp profiles applied
- [ ] Service account tokens not mounted
- [ ] Images from trusted registries
- [ ] Images scanned for vulnerabilities

### Network Security

- [ ] Default deny network policies
- [ ] Ingress TLS configured
- [ ] Service mesh mTLS (if applicable)
- [ ] Egress traffic controlled
- [ ] API server access restricted

## Related Documentation

- **Parent Skill**: See `../SKILL.md` for container security overview
- **Dockerfile Security**: See `dockerfile-security.md` for image hardening
- **Container Scanning**: See `container-scanning.md` for vulnerability scanning

---

**Last Updated:** 2025-12-26
