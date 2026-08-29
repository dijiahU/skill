# Secrets Patterns

Kubernetes Secrets, External Secrets Operator, and Sealed Secrets.

---

## Secrets Strategy Decision

| Approach | Use When |
|----------|----------|
| **K8s Secrets** | Simple apps, dev environments |
| **Sealed Secrets** | GitOps, need secrets in Git |
| **External Secrets** | Enterprise, centralized vault |
| **Placeholder** | Templates, user fills in |

---

## Kubernetes Secrets (Basic)

### Creating Secrets

```bash
# From literal values
kubectl create secret generic db-creds \
  --from-literal=username=admin \
  --from-literal=password=supersecret

# From file
kubectl create secret generic tls-certs \
  --from-file=cert.pem \
  --from-file=key.pem

# Docker registry
kubectl create secret docker-registry regcred \
  --docker-server=registry.example.com \
  --docker-username=user \
  --docker-password=pass
```

### Secret YAML

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-creds
type: Opaque
stringData:                    # Plain text (encoded on apply)
  username: admin
  password: supersecret
# OR
data:                          # Base64 encoded
  username: YWRtaW4=
  password: c3VwZXJzZWNyZXQ=
```

### Using Secrets as Environment Variables

```yaml
spec:
  containers:
  - name: app
    envFrom:
    - secretRef:
        name: db-creds         # All keys as env vars

    # Or specific keys
    env:
    - name: DB_PASSWORD
      valueFrom:
        secretKeyRef:
          name: db-creds
          key: password
```

### Using Secrets as Volumes

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
      defaultMode: 0400
```

---

## External Secrets Operator (ESO)

Pull secrets from external vaults at runtime.

### Install ESO

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace
```

### SecretStore (AWS Secrets Manager)

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
```

### ExternalSecret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-creds
spec:
  refreshInterval: 1h          # Sync every hour
  secretStoreRef:
    name: aws-secrets
    kind: SecretStore
  target:
    name: db-creds             # K8s secret to create
    creationPolicy: Owner
  data:
  - secretKey: username
    remoteRef:
      key: prod/database       # AWS SM secret name
      property: username
  - secretKey: password
    remoteRef:
      key: prod/database
      property: password
```

### ClusterSecretStore (Cluster-Wide)

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "external-secrets"
```

---

## Sealed Secrets

Encrypt secrets for Git storage.

### Install

```bash
# Controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# CLI
brew install kubeseal
```

### Create Sealed Secret

```bash
# Create regular secret
kubectl create secret generic db-creds \
  --from-literal=password=supersecret \
  --dry-run=client -o yaml > secret.yaml

# Seal it
kubeseal --format yaml < secret.yaml > sealed-secret.yaml
```

### SealedSecret YAML

```yaml
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: db-creds
  namespace: production
spec:
  encryptedData:
    password: AgBy3i4O...encrypted...
  template:
    metadata:
      name: db-creds
    type: Opaque
```

**Safe to commit to Git!** Only cluster can decrypt.

---

## Placeholder Pattern

For templates where user provides values:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-creds
  annotations:
    description: "Database credentials - fill in before applying"
type: Opaque
stringData:
  # TODO: Replace with actual values
  username: "REPLACE_WITH_DB_USERNAME"
  password: "REPLACE_WITH_DB_PASSWORD"
```

Or use Kustomize secretGenerator:

```yaml
# kustomization.yaml
secretGenerator:
- name: db-creds
  envs:
  - secrets.env              # User creates this file locally
```

---

## Secret Types

| Type | Use Case |
|------|----------|
| `Opaque` | Generic secrets (default) |
| `kubernetes.io/basic-auth` | Basic auth (username/password) |
| `kubernetes.io/ssh-auth` | SSH private keys |
| `kubernetes.io/tls` | TLS certificates |
| `kubernetes.io/dockerconfigjson` | Docker registry auth |
| `kubernetes.io/service-account-token` | SA tokens |

### TLS Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tls-secret
type: kubernetes.io/tls
data:
  tls.crt: <base64-encoded-cert>
  tls.key: <base64-encoded-key>
```

### Docker Registry Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: regcred
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-encoded-docker-config>
```

---

## Best Practices

### 1. Don't Log Secrets

```yaml
# BAD: Secrets visible in logs
command: ["echo", "$(DB_PASSWORD)"]

# GOOD: Use in app, not shell
env:
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: db-creds
      key: password
```

### 2. Restrict Access with RBAC

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secret-reader
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["db-creds"]  # Only specific secrets
  verbs: ["get"]
```

### 3. Use Immutable Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: config-secret
immutable: true               # Can't be modified after creation
```

### 4. Set File Permissions

```yaml
volumes:
- name: certs
  secret:
    secretName: tls-certs
    defaultMode: 0400         # Read-only for owner
    items:
    - key: tls.key
      path: key.pem
      mode: 0400
```

---

## Security Considerations

| Risk | Mitigation |
|------|------------|
| Secrets in etcd | Enable etcd encryption |
| Secrets in logs | Don't echo secrets |
| Secrets in env | Prefer volume mounts for sensitive data |
| Secrets in Git | Use Sealed Secrets or ESO |
| Broad access | RBAC with least privilege |

### Enable etcd Encryption

```yaml
# EncryptionConfiguration
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
- resources:
  - secrets
  providers:
  - aescbc:
      keys:
      - name: key1
        secret: <base64-encoded-key>
  - identity: {}
```
