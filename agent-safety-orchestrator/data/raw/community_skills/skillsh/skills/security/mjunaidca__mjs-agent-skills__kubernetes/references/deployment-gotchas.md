# Deployment Gotchas

Battle-tested patterns from real deployment failures. Each gotcha represents 1-4+ hours of debugging.

---

## Architecture Matching (CRITICAL)

**Problem**: Container runs on local Mac (arm64) but fails on cloud cluster (amd64).

### Check Node Architecture First

```bash
# What architecture does your cluster run?
kubectl get nodes -o jsonpath='{.items[*].status.nodeInfo.architecture}'
# Expected: amd64 (most cloud clusters)

# What did you build?
docker inspect --format='{{.Architecture}}' myapp:v1
# If arm64 on amd64 cluster → exec format error
```

### Multi-Arch Build (Correct Way)

```bash
# Build for specific platform
docker buildx build --platform linux/amd64 -t myapp:v1 .

# Build for multiple platforms
docker buildx build --platform linux/amd64,linux/arm64 -t myapp:v1 --push .
```

### Provenance Attestation Issue

**Problem**: `--provenance=true` (default in buildx) creates manifest lists that confuse some container runtimes.

```bash
# WRONG: May cause ImagePullBackOff on some clusters
docker buildx build --platform linux/amd64 -t myapp:v1 --push .

# CORRECT: Disable provenance for single-platform images
docker buildx build --platform linux/amd64 --provenance=false -t myapp:v1 --push .
```

**Signs of this issue:**
- ImagePullBackOff but image exists in registry
- `kubectl describe pod` shows successful pull but container fails
- Works locally but fails in cluster

---

## Pre-Deployment Validation Checks

Run these BEFORE `kubectl apply`. Each prevents a specific failure mode.

### 1. Password Generation (No Special Characters)

**Problem**: Base64 passwords with `+`, `/`, `=` break URL encoding and DB connection strings.

```bash
# WRONG: May contain URL-unsafe characters
openssl rand -base64 16

# CORRECT: Hex is always safe
openssl rand -hex 16
```

**Validation:**
```bash
# Check existing secrets for unsafe characters
kubectl get secret db-credentials -o jsonpath='{.data.password}' | base64 -d | grep -E '[+/=]' && echo "WARNING: Contains unsafe chars"
```

### 2. Environment Variable Flow

**Problem**: Variable defined in .env but Pod shows empty.

```bash
# Trace the flow: .env → ConfigMap/Secret → Pod
echo "Expected: $(grep MY_VAR .env | cut -d= -f2)"
echo "In ConfigMap: $(kubectl get configmap app-config -o jsonpath='{.data.MY_VAR}')"
echo "In Pod: $(kubectl exec deploy/myapp -- printenv MY_VAR)"
```

**Common breaks:**
- Variable in .env but not in ConfigMap template
- ConfigMap key typo (`MY_VAR` vs `MY-VAR`)
- Pod envFrom not referencing ConfigMap

### 3. Database Authentication

**Problem**: CLI tool works but application library fails (different auth methods).

```bash
# Test with same method your app uses
kubectl exec -it deploy/myapp -- python -c "
import psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
print('Connection successful')
"
```

**Don't trust:** `psql -U user` working (uses different auth flow than libraries)

### 4. CORS Configuration

**Problem**: CORS allows http://localhost but production uses https://app.domain.com.

```bash
# Check: Does NODE_ENV match protocol expectation?
kubectl exec deploy/myapp -- printenv NODE_ENV
# dev → http://localhost:3000 (OK)
# prod → https://app.domain.com (must be HTTPS)
```

**Validation:**
```bash
# Test CORS preflight
curl -I -X OPTIONS \
  -H "Origin: https://app.domain.com" \
  -H "Access-Control-Request-Method: POST" \
  http://api-service/endpoint
```

### 5. Service Endpoint Verification

**Problem**: Service exists but has no endpoints (selector mismatch).

```bash
# MUST show Pod IPs, not <none>
kubectl get endpoints myapp

# If <none>, compare selectors
kubectl get svc myapp -o jsonpath='{.spec.selector}'
kubectl get pods --show-labels | grep myapp
```

### 6. Secret Existence

**Problem**: Deployment references secret that doesn't exist → CreateContainerConfigError.

```bash
# Extract all secret references from deployment
kubectl get deploy myapp -o yaml | grep -A 2 secretKeyRef

# Verify each exists
kubectl get secret db-credentials
kubectl get secret api-keys
```

### 7. Resource Quota Fit

**Problem**: Pod pending because namespace quota exceeded.

```bash
# Check quota usage
kubectl describe resourcequota -n myns

# Compare with deployment requests
kubectl get deploy myapp -o jsonpath='{.spec.template.spec.containers[0].resources}'
```

---

## Helm Gotchas

### Comma in Values

**Problem**: `--set` interprets commas as list delimiters.

```bash
# WRONG: "a,b,c" becomes ["a", "b", "c"]
helm install myapp ./chart --set config.cors="http://a.com,http://b.com"

# CORRECT: Use values file
cat > values-override.yaml << 'EOF'
config:
  cors: "http://a.com,http://b.com"
EOF
helm install myapp ./chart -f values-override.yaml
```

### Build-Time vs Runtime Variables (Next.js)

**Problem**: `NEXT_PUBLIC_*` variables must be present at BUILD time, not just runtime.

```dockerfile
# WRONG: Runtime-only
FROM node:20-alpine
COPY . .
RUN npm run build    # NEXT_PUBLIC_API_URL is empty here!
ENV NEXT_PUBLIC_API_URL=https://api.prod.com

# CORRECT: Build-time ARG
FROM node:20-alpine
ARG NEXT_PUBLIC_API_URL
COPY . .
RUN npm run build    # Embedded into bundle
```

```bash
# Build with ARG
docker build --build-arg NEXT_PUBLIC_API_URL=https://api.prod.com -t myapp .
```

---

## Image Pull Failures

### ImagePullBackOff Decision Tree

```
ImagePullBackOff
     │
     ▼
┌─────────────────────────────────────┐
│ kubectl describe pod | grep -A5 Events
└─────────────────────────────────────┘
     │
     ├─── "repository does not exist"
     │         → Check image name spelling
     │         → Check registry URL
     │
     ├─── "unauthorized" / "access denied"
     │         → Create imagePullSecret
     │         → Check secret is in correct namespace
     │         → Verify registry credentials work locally
     │
     ├─── "manifest unknown"
     │         → Tag doesn't exist
     │         → Check exact tag name
     │
     └─── "exec format error" (after pull succeeds)
              → Architecture mismatch (see above)
              → Rebuild with correct --platform
```

### Registry Authentication

```yaml
# Create pull secret
kubectl create secret docker-registry regcred \
  --docker-server=ghcr.io \
  --docker-username=$GITHUB_USER \
  --docker-password=$GITHUB_TOKEN

# Reference in deployment
spec:
  template:
    spec:
      imagePullSecrets:
      - name: regcred
```

---

## CrashLoopBackOff Extended Patterns

### exec format error

**Cause**: Binary compiled for wrong architecture.

```bash
# Verify architecture
kubectl exec deploy/myapp -- uname -m  # Won't work if crashing
kubectl debug -it <pod> --image=busybox -- uname -m

# Compare with node
kubectl get node -o jsonpath='{.items[0].status.nodeInfo.architecture}'
```

**Fix**: Rebuild image with correct platform.

### OOMKilled

```bash
# Check exit reason
kubectl describe pod <pod> | grep -A3 "Last State"

# Check actual usage before kill
kubectl top pod <pod>  # If still running

# Check limits
kubectl get pod <pod> -o jsonpath='{.spec.containers[0].resources.limits.memory}'
```

**Fix**: Increase memory limit or fix memory leak.

### Liveness Probe Killing Healthy Container

**Signs:**
- Container works for a while then restarts
- Logs show no application errors
- Events show "Liveness probe failed"

```bash
# Check probe config
kubectl get deploy myapp -o jsonpath='{.spec.template.spec.containers[0].livenessProbe}'

# Test probe endpoint manually
kubectl exec deploy/myapp -- wget -qO- http://localhost:8080/health
```

**Fixes:**
- Increase `initialDelaySeconds` for slow-starting apps
- Increase `periodSeconds` for variable response times
- Check if probe endpoint actually returns 2xx

---

## CI/CD Integration

### Path-Filtered Builds

```yaml
# GitHub Actions: Only build when relevant files change
on:
  push:
    paths:
      - 'src/**'
      - 'Dockerfile'
      - '.github/workflows/deploy.yml'
    paths-ignore:
      - '*.md'
      - 'docs/**'
```

### Avoiding Cached Failures

```bash
# Force fresh pull in CI
docker pull --platform linux/amd64 myapp:latest || true
docker build --no-cache --platform linux/amd64 -t myapp:v1 .
```

---

## Validation Script Template

```bash
#!/bin/bash
# pre-deploy-check.sh - Run before kubectl apply

set -e

echo "=== Pre-Deployment Validation ==="

# 1. Cluster access
echo -n "Cluster access: "
kubectl cluster-info > /dev/null && echo "✓" || { echo "✗ Cannot reach cluster"; exit 1; }

# 2. Namespace
echo -n "Namespace exists: "
kubectl get ns $NAMESPACE > /dev/null 2>&1 && echo "✓" || { echo "✗ Creating..."; kubectl create ns $NAMESPACE; }

# 3. Image exists
echo -n "Image pullable: "
docker pull $IMAGE:$TAG > /dev/null 2>&1 && echo "✓" || { echo "✗ Image not found"; exit 1; }

# 4. Secrets exist
echo -n "Secrets present: "
for secret in db-credentials api-keys; do
  kubectl get secret $secret -n $NAMESPACE > /dev/null 2>&1 || { echo "✗ Missing: $secret"; exit 1; }
done
echo "✓"

# 5. ResourceQuota room
echo -n "Quota available: "
kubectl describe resourcequota -n $NAMESPACE 2>/dev/null | grep -q "cpu.*0%" && { echo "✗ CPU quota exhausted"; exit 1; }
echo "✓"

# 6. Dry run
echo -n "Manifest valid: "
kubectl apply -f k8s/base/ --dry-run=server > /dev/null && echo "✓" || { echo "✗ Invalid manifest"; exit 1; }

echo "=== All checks passed ==="
```

---

## Quick Reference

| Issue | First Command | Likely Cause |
|-------|---------------|--------------|
| ImagePullBackOff | `kubectl describe pod` | Auth, tag, registry |
| CrashLoopBackOff | `kubectl logs --previous` | App error, config |
| Pending | `kubectl describe pod` | Resources, scheduling |
| exec format error | `uname -m` vs node arch | Platform mismatch |
| Service no endpoints | `kubectl get endpoints` | Selector mismatch |
| CreateContainerConfigError | `kubectl describe pod` | Missing secret/configmap |
| OOMKilled | `kubectl describe pod` | Memory limit |
