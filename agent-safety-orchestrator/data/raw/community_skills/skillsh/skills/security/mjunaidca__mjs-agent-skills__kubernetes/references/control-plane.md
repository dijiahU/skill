# Control Plane & Reconciliation

Essential knowledge for debugging when things go wrong.

---

## The Reconciliation Loop

Every K8s controller runs this loop continuously:

```
┌─────────────────────────────────────────┐
│                                         │
│   1. OBSERVE    →  Read current state   │
│        ↓                                │
│   2. DIFF       →  Compare to desired   │
│        ↓                                │
│   3. ACT        →  Make changes         │
│        ↓                                │
│   (loop forever)                        │
│                                         │
└─────────────────────────────────────────┘
```

**Key insight**: K8s is declarative. You declare desired state, controllers reconcile reality to match.

---

## Controller Chain: Deployment → Pod

When you `kubectl apply -f deployment.yaml`:

```
You apply Deployment
        ↓
Deployment Controller (watches Deployments)
  - Sees new/changed Deployment
  - Creates/updates ReplicaSet
        ↓
ReplicaSet Controller (watches ReplicaSets)
  - Sees ReplicaSet needs N pods
  - Creates Pod objects (status: Pending)
        ↓
Scheduler (watches unscheduled Pods)
  - Finds suitable Node for each Pod
  - Binds Pod to Node (status: Pending, but scheduled)
        ↓
Kubelet on Node (watches Pods assigned to its Node)
  - Pulls image
  - Creates container
  - Updates Pod status (status: Running)
```

---

## Where to Look When Debugging

| Symptom | Check This |
|---------|------------|
| Deployment not progressing | `kubectl describe deployment` → Events |
| ReplicaSet not creating pods | `kubectl describe rs <name>` → Events |
| Pods stuck Pending | `kubectl describe pod` → Events (scheduling failures) |
| Pods stuck ContainerCreating | `kubectl describe pod` → Events (image pull, volume mount) |
| Pods CrashLoopBackOff | `kubectl logs <pod>` → Application errors |
| Pods keep restarting | `kubectl describe pod` → Liveness probe failures |

### Debug Commands Cheatsheet

```bash
# See the full chain
kubectl get deploy,rs,pods -l app=myapp

# Deployment events (why no ReplicaSet?)
kubectl describe deployment myapp

# ReplicaSet events (why no Pods?)
kubectl get rs -l app=myapp
kubectl describe rs myapp-abc123

# Pod events (why not running?)
kubectl describe pod myapp-abc123-xyz

# Scheduler decisions
kubectl get events --field-selector reason=FailedScheduling

# All events for namespace
kubectl get events --sort-by='.lastTimestamp'
```

---

## The Deployment → ReplicaSet Relationship

```yaml
# You create:
Deployment: myapp
  replicas: 3
  template: (pod spec v1)

# Deployment controller creates:
ReplicaSet: myapp-abc123  # Hash of pod template
  replicas: 3
  template: (pod spec v1)

# When you update template:
ReplicaSet: myapp-def456  # NEW hash
  replicas: 3  # Scales up
ReplicaSet: myapp-abc123
  replicas: 0  # Scales down (kept for rollback)
```

**Why this matters**: Each ReplicaSet is a "revision". Rollback = scale old RS up, new RS down.

```bash
# See revision history
kubectl rollout history deployment/myapp

# Rollback to previous
kubectl rollout undo deployment/myapp

# Rollback to specific revision
kubectl rollout undo deployment/myapp --to-revision=2
```

---

## Scheduler Decisions

The Scheduler decides WHERE pods run based on:

### 1. Filtering (Can this node run the pod?)

| Check | Failure Reason |
|-------|----------------|
| Node has enough CPU/memory | `Insufficient cpu/memory` |
| Node matches nodeSelector | `node(s) didn't match Pod's node selector` |
| Pod tolerates node taints | `node(s) had taints that the pod didn't tolerate` |
| PVC can be mounted on node | `node(s) had volume node affinity conflict` |

### 2. Scoring (Which node is best?)

| Factor | Preference |
|--------|------------|
| Resource balance | Spread load across nodes |
| Affinity rules | Co-locate or anti-co-locate pods |
| Data locality | Prefer nodes with data already present |

### Debug: Why Won't My Pod Schedule?

```bash
# See pending pods
kubectl get pods --field-selector=status.phase=Pending

# See WHY it's pending
kubectl describe pod <pending-pod>
# Look at Events section:
#   Warning  FailedScheduling  default-scheduler
#   0/3 nodes available: 3 Insufficient memory.

# See node resources
kubectl describe nodes | grep -A 5 "Allocated resources"
```

---

## Ownership & Garbage Collection

K8s tracks what created what:

```yaml
# Pod has ownerReference to ReplicaSet
metadata:
  ownerReferences:
  - apiVersion: apps/v1
    kind: ReplicaSet
    name: myapp-abc123
    uid: xxx
    controller: true
```

**Why this matters**: Delete ReplicaSet → Pods deleted automatically. Delete Deployment → ReplicaSets → Pods all deleted.

```bash
# See owner of a pod
kubectl get pod myapp-abc123-xyz -o jsonpath='{.metadata.ownerReferences[0].name}'
```

---

## Common Failure Patterns

### 1. Deployment Stuck (no new ReplicaSet)

**Symptom**: `kubectl rollout status` hangs

**Cause**: Usually resource quota exceeded or invalid spec

```bash
kubectl describe deployment myapp
# Look for: "exceeded quota", "spec.containers: Required"
```

### 2. ReplicaSet Not Creating Pods

**Symptom**: RS exists, but 0/3 pods

**Cause**: Admission webhook rejected, resource quota

```bash
kubectl describe rs myapp-abc123
# Look for: "Error creating", "forbidden"
```

### 3. Pods Pending Forever

**Symptom**: Pods stuck in Pending

**Causes**:

| Event Message | Fix |
|--------------|-----|
| `Insufficient cpu/memory` | Reduce requests or add nodes |
| `node(s) didn't match selector` | Check nodeSelector matches node labels |
| `no persistent volumes available` | Create PV or check StorageClass |
| `pod has unbound immediate PersistentVolumeClaims` | PVC not bound, check storage |

### 4. Pods CrashLoopBackOff

**Symptom**: Pod restarts repeatedly

**Causes**:

| Check | Command |
|-------|---------|
| App crash on startup | `kubectl logs <pod>` |
| Missing config/secret | `kubectl describe pod` → volume mount errors |
| Wrong command/args | Check `command:` and `args:` in spec |
| Liveness probe too aggressive | Check probe timing |

### 5. Rolling Update Stuck

**Symptom**: New pods created but old pods not terminated

**Cause**: New pods failing readiness probe

```bash
# Check new pods
kubectl get pods -l app=myapp
# Find ones not Ready, check logs/events

# Force rollback if needed
kubectl rollout undo deployment/myapp
```

---

## Control Plane Components

| Component | Role | Watches |
|-----------|------|---------|
| **kube-apiserver** | API gateway, validates, stores in etcd | Everything (entry point) |
| **etcd** | Key-value store for cluster state | N/A (data store) |
| **kube-scheduler** | Assigns pods to nodes | Unscheduled Pods |
| **kube-controller-manager** | Runs all controllers | Various resources |
| **kubelet** | Runs pods on node | Pods assigned to its node |

### Where State Lives

```
You → API Server → etcd (source of truth)
                      ↓
                 Controllers watch
                      ↓
                 Make changes via API Server
                      ↓
                 etcd updated
```

---

## Key Debugging Principle

**Follow the chain**: Deployment → ReplicaSet → Pod → Container

At each level, run `kubectl describe` and read the **Events** section. The failure usually shows up as an event at one of these levels.
