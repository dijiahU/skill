# Networking Patterns

Service types, DNS discovery, label selectors, and debugging.

---

## Why Services Exist: The Pod Ephemerality Problem

**Pods are ephemeral. When a Pod crashes and is replaced, it gets a NEW IP address.**

```
# WHY: This direct Pod IP approach FAILS in Kubernetes
response = requests.get("http://10.244.0.45:5000/data")
# Pod crashes → new Pod gets 10.244.0.67 → old IP is DEAD
```

A **Service** provides:
1. **Stable virtual IP** (ClusterIP) that never changes
2. **Load balancing** across Pods matching the selector
3. **DNS discovery** (`service-name.namespace.svc.cluster.local`)

Think of a Service like a phone number—the number stays the same, but who answers may change.

---

## Label Selectors: The Connection Mechanism (CRITICAL)

**Label selectors connect Services to Pods. Misconfigured selectors = zero endpoints = broken Service.**

```yaml
# WHY: Service finds Pods by matching labels, not by name
apiVersion: v1
kind: Service
metadata:
  name: backend-service
spec:
  selector:
    app: backend          # <-- Finds Pods with label app=backend
  ports:
  - port: 80
    targetPort: 5000
```

### Matching Rules

| Pod Labels | Service Selector | Match? |
|------------|------------------|--------|
| `app: backend` | `app: backend` | ✅ Yes |
| `app: backend, version: v1` | `app: backend` | ✅ Yes (extra labels OK) |
| `app: api` | `app: backend` | ❌ No (wrong value) |
| `app: backend` | `app: backend, tier: api` | ❌ No (missing required label) |

**Rule**: Pod must have ALL labels in selector. Extra Pod labels are ignored.

---

## Port Mapping

```yaml
spec:
  ports:
  - port: 80              # WHY: Service port (what clients connect to)
    targetPort: 8000      # WHY: Pod/container port (where app listens)
    nodePort: 30080       # WHY: Node port (external access, NodePort only)
```

**Traffic flow**: `Client → port (80) → Service → targetPort (8000) → Pod`

---

## Service Type Decision Framework

| Requirement | Type | Why |
|-------------|------|-----|
| Pod-to-Pod communication | **ClusterIP** | Internal only, most efficient |
| Local development/testing | **NodePort** | Quick external access, no cloud LB |
| Production external access | **LoadBalancer** | Cloud LB handles scale + reliability |
| Multiple services, one IP | **ClusterIP + Ingress** | Layer 7 routing (covered below) |

---

## Service Types

| Type | Use Case | Accessibility |
|------|----------|---------------|
| `ClusterIP` | Internal services | Cluster only (default) |
| `NodePort` | Development/testing | Node IP + port |
| `LoadBalancer` | External production | Cloud LB |
| `ExternalName` | DNS alias | Maps to external DNS |

---

## ClusterIP (Default)

Internal cluster communication:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-internal
  labels:
    app.kubernetes.io/name: api
spec:
  type: ClusterIP              # Default, can omit
  selector:
    app.kubernetes.io/name: api
  ports:
  - name: http
    port: 80                   # Service port
    targetPort: 8000           # Container port
    protocol: TCP
```

**Access**: `http://api-internal.namespace.svc.cluster.local`

---

## NodePort

Expose on each node's IP:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-nodeport
spec:
  type: NodePort
  selector:
    app.kubernetes.io/name: api
  ports:
  - port: 80
    targetPort: 8000
    nodePort: 30080            # Optional: 30000-32767
```

**Access**: `http://<node-ip>:30080`

---

## LoadBalancer

Cloud-managed load balancer:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-external
  annotations:
    # AWS NLB
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
    # Or GCP internal LB
    cloud.google.com/load-balancer-type: Internal
spec:
  type: LoadBalancer
  selector:
    app.kubernetes.io/name: api
  ports:
  - port: 443
    targetPort: 8000
```

---

## Kubernetes DNS Discovery

Every Service gets automatic DNS. No hardcoding IPs.

### DNS Name Format

```
<service-name>.<namespace>.svc.cluster.local
```

### Short Names (Same Namespace)

```python
# WHY: Within same namespace, short name works
response = requests.get("http://backend-service/api")  # ✅
```

### Full DNS (Cross-Namespace)

```python
# WHY: Accessing service in different namespace requires FQDN
response = requests.get("http://backend-service.production.svc.cluster.local/api")
```

### DNS Resolution Test

```bash
# From inside a Pod
nslookup web-service
# Returns: 10.96.0.234 (the Service's ClusterIP)

curl http://web-service  # Uses DNS, routes to any backend Pod
```

---

## Debugging: Service Has No Endpoints (90% of Issues)

**When a Service has no endpoints, traffic fails. This is the #1 networking problem.**

### Systematic Debug Process

```bash
# Step 1: Check endpoints (THE TRUTH)
kubectl get endpoints backend-service
# Expected: 10.244.0.5:5000,10.244.0.6:5000
# Problem:  <none>  ← No Pods matched!

# Step 2: Check Service selector
kubectl describe service backend-service | grep Selector
# Output: Selector: app=api

# Step 3: Check Pod labels
kubectl get pods --show-labels
# Output: app=backend  ← MISMATCH! Service looks for 'api', Pods have 'backend'

# Step 4: Fix selector OR fix Pod labels
kubectl edit service backend-service  # Change selector to app=backend

# Step 5: Verify fix
kubectl get endpoints backend-service
# Output: 10.244.0.5:5000,10.244.0.6:5000  ← Fixed!
```

### Common Causes of Zero Endpoints

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Endpoints: <none>` | Selector doesn't match Pod labels | Align selector with Pod labels |
| `Endpoints: <none>` | Pods not Ready (probe failing) | Fix readinessProbe or app health |
| `Endpoints: <none>` | Pods in different namespace | Service must be in same namespace as Pods |
| `Endpoints: <none>` | Typo in label key or value | Check exact spelling: `app` vs `App` |

### Quick Comparison Command

```bash
# Compare side by side
echo "Service selector:" && kubectl get svc backend-service -o jsonpath='{.spec.selector}' && echo
echo "Pod labels:" && kubectl get pods -l app -o jsonpath='{range .items[*]}{.metadata.name}: {.metadata.labels}{"\n"}{end}'
```

---

## Headless Service (StatefulSet)

For direct pod DNS:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  clusterIP: None              # Headless
  selector:
    app: postgres
  ports:
  - port: 5432
```

**DNS**: `postgres-0.postgres.namespace.svc.cluster.local`

---

## Ingress

### Basic Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 80
```

### Path-Based Routing

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
spec:
  ingressClassName: nginx
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
```

### TLS Termination

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: secure-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: api-tls-secret
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 80
```

### Path Types

| Type | Match Behavior |
|------|----------------|
| `Exact` | Exact path only (`/foo` matches `/foo` only) |
| `Prefix` | Path prefix (`/api` matches `/api`, `/api/v1`, etc.) |
| `ImplementationSpecific` | Ingress controller decides |

---

## IngressClass

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: nginx
  annotations:
    ingressclass.kubernetes.io/is-default-class: "true"
spec:
  controller: k8s.io/ingress-nginx
```

---

## NGINX Ingress Annotations

```yaml
metadata:
  annotations:
    # Rate limiting
    nginx.ingress.kubernetes.io/limit-rps: "10"

    # Body size
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"

    # Timeouts
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "10"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"

    # SSL redirect
    nginx.ingress.kubernetes.io/ssl-redirect: "true"

    # CORS
    nginx.ingress.kubernetes.io/enable-cors: "true"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://app.example.com"

    # Rewrite
    nginx.ingress.kubernetes.io/rewrite-target: /$2
```

---

## Traffic Splitting (A/B Testing)

Route percentage of traffic to canary deployment:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agent-canary
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "10"  # 10% to canary
spec:
  ingressClassName: nginx
  rules:
  - host: agent.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: agent-canary  # New version
            port:
              number: 80
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agent-stable
spec:
  ingressClassName: nginx
  rules:
  - host: agent.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: agent-stable  # Current version (90%)
            port:
              number: 80
```

**Canary options:**
- `canary-weight`: Percentage (0-100)
- `canary-by-header`: Route by header (`X-Canary: always`)
- `canary-by-cookie`: Route by cookie value

---

## AI Multi-Agent Routing

Route different AI services under single domain:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ai-agents-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"  # Long inference
    nginx.ingress.kubernetes.io/limit-rps: "100"
    nginx.ingress.kubernetes.io/enable-cors: "true"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://dashboard.example.com"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - ai.example.com
    secretName: ai-tls-secret
  rules:
  - host: ai.example.com
    http:
      paths:
      # WHY: Chat agent handles conversational AI
      - path: /chat
        pathType: Prefix
        backend:
          service:
            name: chat-agent
            port:
              number: 80
      # WHY: Tools agent handles function calling
      - path: /tools
        pathType: Prefix
        backend:
          service:
            name: tools-agent
            port:
              number: 80
      # WHY: Embeddings service for RAG
      - path: /embed
        pathType: Prefix
        backend:
          service:
            name: embedding-service
            port:
              number: 80
      # WHY: Health check for all services
      - path: /health
        pathType: Exact
        backend:
          service:
            name: health-aggregator
            port:
              number: 80
```

---

## Ingress Debugging

### Quick Commands

```bash
# List all Ingress resources
kubectl get ingress -A

# Detailed Ingress info (shows backends, rules)
kubectl describe ingress <ingress-name>

# Check Ingress controller pods
kubectl get pods -n ingress-nginx

# View controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx

# Test Service directly (bypass Ingress)
kubectl port-forward svc/<service-name> 8080:80
curl http://localhost:8080/health
```

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| ADDRESS is empty | Controller not ready or no external LB | Wait for controller; check cloud provider |
| 503 Service Unavailable | Backend pods unhealthy | Check `kubectl get endpoints <service>` |
| 404 Not Found | Path mismatch or wrong service name | Verify `spec.rules` paths and service names |
| SSL certificate error | Secret missing or wrong name | `kubectl get secret <tls-secret-name>` |
| Timeout on inference | Default timeout too short | Add `proxy-read-timeout: "300"` |

### Verify Backend Health

```bash
# Check if Service has endpoints (pods)
kubectl get endpoints <service-name>
# Should show Pod IPs, NOT <none>

# If <none>, check Pod labels match Service selector
kubectl get pods --show-labels
kubectl describe service <service-name> | grep Selector
```

### Test Ingress Routing

```bash
# Get Ingress external IP
INGRESS_IP=$(kubectl get ingress <name> -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Test with Host header
curl -H "Host: ai.example.com" http://$INGRESS_IP/chat/health

# Test TLS
curl -k https://ai.example.com/chat/health
```

---

## Service Mesh Annotations

### Istio

```yaml
apiVersion: v1
kind: Pod
metadata:
  annotations:
    # Enable sidecar injection
    sidecar.istio.io/inject: "true"
    # Exclude ports from proxy
    traffic.sidecar.istio.io/excludeOutboundPorts: "5432"
```

### Linkerd

```yaml
apiVersion: v1
kind: Pod
metadata:
  annotations:
    linkerd.io/inject: enabled
    # Timeout
    config.linkerd.io/proxy-outbound-connect-timeout: "10s"
```

---

## Network Policies

### Default Deny All

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

### Allow Internal Namespace Traffic

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-same-namespace
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector: {}          # All pods in same namespace
```

### Allow Ingress from Specific Pods

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
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 8000
```

### Allow Egress to External

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-external
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Egress
  egress:
  # Allow DNS
  - to:
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
  # Allow external HTTPS
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
        except:
        - 10.0.0.0/8
        - 172.16.0.0/12
        - 192.168.0.0/16
    ports:
    - protocol: TCP
      port: 443
```

---

## DNS Configuration

```yaml
spec:
  dnsPolicy: ClusterFirst     # Default
  dnsConfig:
    nameservers:
    - 8.8.8.8
    searches:
    - svc.cluster.local
    options:
    - name: ndots
      value: "2"
```

**DNS Policies**:
- `ClusterFirst`: Use cluster DNS, fall back to node DNS
- `Default`: Inherit node's DNS config
- `ClusterFirstWithHostNet`: For hostNetwork pods
- `None`: Must specify dnsConfig
