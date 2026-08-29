# Health Probes

Liveness, readiness, and startup probe patterns for production workloads.

---

## Probe Types

| Probe | Purpose | Failure Action |
|-------|---------|----------------|
| **Liveness** | Is container alive? | Restart container |
| **Readiness** | Can it accept traffic? | Remove from service endpoints |
| **Startup** | Has app finished starting? | Block liveness/readiness checks |

---

## Default Configuration

```yaml
containers:
- name: app
  # Liveness: Restart if deadlocked
  livenessProbe:
    httpGet:
      path: /health/live
      port: 8000
    initialDelaySeconds: 10   # Wait for app startup
    periodSeconds: 15         # Check every 15s
    timeoutSeconds: 3         # Timeout per check
    failureThreshold: 3       # Restart after 3 failures

  # Readiness: Remove from LB if not ready
  readinessProbe:
    httpGet:
      path: /health/ready
      port: 8000
    initialDelaySeconds: 5
    periodSeconds: 10
    timeoutSeconds: 3
    failureThreshold: 3

  # Startup: For slow-starting apps (ML models, etc.)
  startupProbe:
    httpGet:
      path: /health/live
      port: 8000
    initialDelaySeconds: 0
    periodSeconds: 10
    failureThreshold: 30     # 5 minutes max startup
```

---

## Probe Parameters

| Parameter | Description | Default | Recommendation |
|-----------|-------------|---------|----------------|
| `initialDelaySeconds` | Wait before first probe | 0 | Set based on startup time |
| `periodSeconds` | Time between probes | 10 | 10-30s for production |
| `timeoutSeconds` | Probe timeout | 1 | 3-5s to handle slow responses |
| `successThreshold` | Successes to mark healthy | 1 | Keep at 1 |
| `failureThreshold` | Failures to mark unhealthy | 3 | 3 for liveness, 3-5 for readiness |

---

## Probe Methods

### HTTP GET (Recommended)

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
    httpHeaders:
    - name: Accept
      value: application/json
```

### TCP Socket

For non-HTTP services (databases, Redis):

```yaml
livenessProbe:
  tcpSocket:
    port: 5432
  initialDelaySeconds: 15
  periodSeconds: 20
```

### Exec Command

For complex health checks:

```yaml
livenessProbe:
  exec:
    command:
    - /bin/sh
    - -c
    - pg_isready -U postgres
  initialDelaySeconds: 30
  periodSeconds: 10
```

---

## Health Endpoint Patterns

### Liveness Endpoint

Simple check - is the process alive?

```python
# FastAPI
@app.get("/health/live")
async def liveness():
    return {"status": "alive"}
```

```javascript
// Express
app.get('/health/live', (req, res) => {
  res.json({ status: 'alive' });
});
```

### Readiness Endpoint

Checks dependencies (DB, cache, external services):

```python
# FastAPI
@app.get("/health/ready")
async def readiness():
    try:
        await db.execute("SELECT 1")
        await redis.ping()
        return {"status": "ready", "checks": {"db": "ok", "redis": "ok"}}
    except Exception as e:
        raise HTTPException(503, detail=str(e))
```

```javascript
// Express
app.get('/health/ready', async (req, res) => {
  try {
    await db.query('SELECT 1');
    await redis.ping();
    res.json({ status: 'ready' });
  } catch (err) {
    res.status(503).json({ status: 'not ready', error: err.message });
  }
});
```

---

## Common Patterns

### Fast-Starting App (No Startup Probe)

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 3
  periodSeconds: 5
```

### Slow-Starting App (ML Models)

```yaml
startupProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 0
  periodSeconds: 10
  failureThreshold: 60  # 10 minutes max startup

livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  periodSeconds: 30     # Less frequent after startup

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  periodSeconds: 10
```

### Database (TCP)

```yaml
livenessProbe:
  tcpSocket:
    port: 5432
  initialDelaySeconds: 30
  periodSeconds: 20

readinessProbe:
  exec:
    command:
    - pg_isready
    - -U
    - postgres
  periodSeconds: 10
```

---

## Debugging Probes

### Check Probe Events

```bash
# View probe failures in events
kubectl describe pod <pod-name> | grep -A 10 "Events"

# Common probe failure messages:
# - "Liveness probe failed: HTTP probe failed with statuscode: 503"
# - "Readiness probe failed: connection refused"
# - "Startup probe failed: timeout"
```

### Test Endpoints Manually

```bash
# Port-forward to pod
kubectl port-forward pod/<pod-name> 8000:8000

# Test in another terminal
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready

# Check response time (should be < timeoutSeconds)
time curl http://localhost:8000/health/ready
```

### View Container Logs

```bash
# Check app logs for probe handling
kubectl logs <pod-name> | grep -i health

# Watch logs during probe failures
kubectl logs <pod-name> -f
```

### Timing Calculation

```
Total startup allowance = periodSeconds × failureThreshold

Example: startupProbe with periodSeconds=5, failureThreshold=30
→ 5 × 30 = 150 seconds (2.5 minutes) before pod is killed
```

**Critical Rule**: `timeoutSeconds` must be LESS than `periodSeconds` to avoid overlapping probes.

```yaml
# GOOD: No overlap
periodSeconds: 10
timeoutSeconds: 3

# BAD: Overlapping probes
periodSeconds: 5
timeoutSeconds: 10  # Probe still running when next one starts!
```

---

## Anti-Patterns

### DON'T: Heavy Liveness Checks

```yaml
# BAD: DB check in liveness can cause cascade failures
livenessProbe:
  exec:
    command: ["./check-db.sh"]  # If DB is slow, pods restart
```

### DON'T: Missing Startup Probe for Slow Apps

```yaml
# BAD: Short timeout kills slow-starting apps
livenessProbe:
  initialDelaySeconds: 10  # ML model needs 2 minutes
```

### DON'T: Same Path for Liveness and Readiness

```yaml
# BAD: Same endpoint for both probes
livenessProbe:
  httpGet:
    path: /health  # Checks DB
readinessProbe:
  httpGet:
    path: /health  # Also checks DB - if DB is down, pods restart!
```

**Correct approach**:
- Liveness: Simple, no dependencies
- Readiness: Check dependencies
