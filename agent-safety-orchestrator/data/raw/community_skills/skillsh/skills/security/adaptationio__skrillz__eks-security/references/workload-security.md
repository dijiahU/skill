# Workload Security Configuration

Complete guide to securing Kubernetes workloads with Pod Security Standards, network policies, image scanning, runtime security, and incident response.

## Table of Contents

1. [Pod Security Standards](#pod-security-standards)
2. [Security Contexts](#security-contexts)
3. [Network Policies](#network-policies)
4. [Security Groups for Pods](#security-groups-for-pods)
5. [Image Scanning and Verification](#image-scanning-and-verification)
6. [Admission Controllers](#admission-controllers)
7. [Runtime Security](#runtime-security)
8. [Incident Response](#incident-response)

---

## Pod Security Standards

### Overview

Pod Security Standards (PSS) define three security levels for pods:
- **Privileged**: Unrestricted (no security restrictions)
- **Baseline**: Minimally restrictive (prevents known privilege escalations)
- **Restricted**: Heavily restrictive (current pod hardening best practices)

Pod Security Admission (PSA) is the built-in controller enforcing PSS:
- Beta feature, enabled by default in EKS
- Replaces deprecated Pod Security Policies
- Applied at namespace level via labels

### Security Levels Comparison

| Control | Privileged | Baseline | Restricted |
|---------|-----------|----------|------------|
| Host namespaces | ✅ Allowed | ❌ Forbidden | ❌ Forbidden |
| Privileged containers | ✅ Allowed | ❌ Forbidden | ❌ Forbidden |
| Capabilities | ✅ All | ⚠️ Limited | ⚠️ Minimal |
| HostPath volumes | ✅ Allowed | ❌ Forbidden | ❌ Forbidden |
| Host ports | ✅ Allowed | ❌ Forbidden | ❌ Forbidden |
| AppArmor | ➖ Not required | ➖ Not required | ✅ Required |
| SELinux | ➖ Not required | ➖ Not required | ✅ Required |
| Seccomp | ➖ Not required | ➖ Not required | ✅ Required |
| Non-root user | ➖ Not required | ➖ Not required | ✅ Required |
| Read-only root fs | ➖ Not required | ➖ Not required | ⚠️ Recommended |

### Implementation

**Apply PSS at Namespace Level**:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    # Enforcement mode - blocks non-compliant pods
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest

    # Audit mode - logs violations
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/audit-version: latest

    # Warn mode - returns warnings to user
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: latest
```

**Modes**:
- **enforce**: Blocks non-compliant pods (pod creation fails)
- **audit**: Logs violations to audit logs (pod still created)
- **warn**: Returns warning to user (pod still created)

**Best Practice**: Use all three modes in production namespaces.

### Restricted Level Requirements

**Complete Pod Specification**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-app
  namespace: production
spec:
  # Security context at pod level
  securityContext:
    runAsNonRoot: true           # ✅ Required
    runAsUser: 1000              # ✅ Required (non-root UID)
    runAsGroup: 3000
    fsGroup: 2000
    seccompProfile:              # ✅ Required
      type: RuntimeDefault

  containers:
  - name: app
    image: my-app:v1.0.0

    # Security context at container level
    securityContext:
      allowPrivilegeEscalation: false  # ✅ Required
      runAsNonRoot: true               # ✅ Required
      runAsUser: 1000
      readOnlyRootFilesystem: true     # ⚠️ Strongly recommended
      capabilities:
        drop:
        - ALL                           # ✅ Required
      seccompProfile:
        type: RuntimeDefault            # ✅ Required

    # Resource limits (best practice)
    resources:
      limits:
        cpu: "1"
        memory: 1Gi
      requests:
        cpu: "0.5"
        memory: 512Mi

    # Volume mounts (writable volumes only where needed)
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: cache
      mountPath: /app/cache

  volumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir: {}
```

### Common PSS Violations and Fixes

**Violation 1: Running as root**
```yaml
# ❌ FAILS restricted
spec:
  containers:
  - name: app
    image: nginx

# ✅ PASSES restricted
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
  containers:
  - name: app
    image: nginx
```

**Violation 2: Privileged container**
```yaml
# ❌ FAILS baseline and restricted
spec:
  containers:
  - name: app
    securityContext:
      privileged: true

# ✅ PASSES
spec:
  containers:
  - name: app
    securityContext:
      privileged: false
      allowPrivilegeEscalation: false
```

**Violation 3: Host namespaces**
```yaml
# ❌ FAILS baseline and restricted
spec:
  hostNetwork: true
  hostPID: true
  hostIPC: true

# ✅ PASSES
spec:
  hostNetwork: false
  hostPID: false
  hostIPC: false
```

**Violation 4: HostPath volumes**
```yaml
# ❌ FAILS baseline and restricted
spec:
  volumes:
  - name: host-data
    hostPath:
      path: /data

# ✅ PASSES - use emptyDir, PV, or ConfigMap
spec:
  volumes:
  - name: app-data
    emptyDir: {}
```

**Violation 5: Dangerous capabilities**
```yaml
# ❌ FAILS restricted
spec:
  containers:
  - name: app
    securityContext:
      capabilities:
        add:
        - NET_ADMIN
        - SYS_ADMIN

# ✅ PASSES restricted
spec:
  containers:
  - name: app
    securityContext:
      capabilities:
        drop:
        - ALL
```

### Exemptions (Use Sparingly)

Some workloads require exceptions (system components, monitoring agents):

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: monitoring
  labels:
    # Exempt specific pods using label selector
    pod-security.kubernetes.io/enforce: baseline  # Lower level for monitoring
    pod-security.kubernetes.io/warn: restricted   # Still warn about violations
```

**Exempt specific users/runtimeClasses**: Not supported by PSA. Use OPA/Gatekeeper for complex exemption logic.

---

## Security Contexts

### Overview

Security contexts define privilege and access control settings:
- **Pod-level**: Applies to all containers (runAsUser, fsGroup, seccompProfile)
- **Container-level**: Overrides pod-level (allowPrivilegeEscalation, capabilities)

### Complete Security Context Reference

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: security-context-demo
spec:
  # Pod-level security context
  securityContext:
    # Run as non-root user
    runAsNonRoot: true
    runAsUser: 1000        # UID 1000
    runAsGroup: 3000       # Primary GID 3000
    fsGroup: 2000          # Volume ownership GID 2000
    fsGroupChangePolicy: OnRootMismatch  # Only chown if necessary

    # Supplemental groups
    supplementalGroups: [4000, 5000]

    # SELinux options
    seLinuxOptions:
      level: "s0:c123,c456"
      role: "spc_r"
      type: "spc_t"
      user: "system_u"

    # Seccomp profile
    seccompProfile:
      type: RuntimeDefault  # Use default seccomp profile

    # Sysctl settings (requires SysctlsPodSecurityPolicy)
    sysctls:
    - name: net.ipv4.ip_local_port_range
      value: "32768 60999"

  containers:
  - name: app
    image: my-app:v1.0.0

    # Container-level security context (overrides pod-level)
    securityContext:
      # Privilege escalation
      allowPrivilegeEscalation: false
      privileged: false

      # User/group
      runAsNonRoot: true
      runAsUser: 1000

      # Read-only root filesystem
      readOnlyRootFilesystem: true

      # Capabilities
      capabilities:
        drop:
        - ALL           # Drop all capabilities
        add:
        - NET_BIND_SERVICE  # Only add what's needed

      # Seccomp (overrides pod-level)
      seccompProfile:
        type: Localhost
        localhostProfile: profiles/audit.json

      # Proc mount (default: DefaultProcMount)
      procMount: Default
```

### Security Context Best Practices

#### 1. Always Run as Non-Root

**Why**: Prevent container escape and privilege escalation

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000     # Explicit non-root UID
```

**Dockerfile Best Practice**:
```dockerfile
FROM node:18-alpine

# Create non-root user
RUN addgroup -g 1000 appgroup && \
    adduser -D -u 1000 -G appgroup appuser

# Set ownership
WORKDIR /app
COPY --chown=appuser:appgroup . .

# Switch to non-root user
USER appuser

CMD ["node", "server.js"]
```

#### 2. Read-Only Root Filesystem

**Why**: Prevent malicious file writes, reduce attack surface

```yaml
spec:
  containers:
  - name: app
    securityContext:
      readOnlyRootFilesystem: true

    # Provide writable volumes where needed
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: cache
      mountPath: /app/cache
    - name: logs
      mountPath: /var/log/app

  volumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir: {}
  - name: logs
    emptyDir: {}
```

#### 3. Drop All Capabilities

**Why**: Minimize privileges, defense in depth

```yaml
spec:
  containers:
  - name: app
    securityContext:
      capabilities:
        drop:
        - ALL
        add:
        - NET_BIND_SERVICE  # Only if binding to ports < 1024
```

**Common Capabilities** (add only if needed):
- **NET_BIND_SERVICE**: Bind to ports < 1024
- **NET_RAW**: Raw sockets (ping, traceroute)
- **SYS_CHROOT**: Use chroot()
- **SETUID/SETGID**: Change UID/GID

**Avoid**:
- **SYS_ADMIN**: Effectively root
- **NET_ADMIN**: Network configuration
- **SYS_PTRACE**: Debug processes

#### 4. Use Seccomp Profiles

**Why**: Restrict syscalls, reduce kernel attack surface

**RuntimeDefault** (recommended):
```yaml
spec:
  securityContext:
    seccompProfile:
      type: RuntimeDefault
```

**Custom Profile**:
```yaml
spec:
  containers:
  - name: app
    securityContext:
      seccompProfile:
        type: Localhost
        localhostProfile: profiles/my-app.json
```

**Generate Custom Profile**:
```bash
# Use oci-seccomp-bpf-hook to generate profile
docker run --rm \
  --annotation io.containers.trace-syscalls="of:/tmp/profile.json" \
  my-app:v1.0.0

# Copy profile to nodes
kubectl cp profile.json node:/var/lib/kubelet/seccomp/profiles/my-app.json
```

#### 5. Set Resource Limits

**Why**: Prevent resource exhaustion attacks

```yaml
spec:
  containers:
  - name: app
    resources:
      limits:
        cpu: "1"
        memory: 1Gi
        ephemeral-storage: 2Gi
      requests:
        cpu: "0.5"
        memory: 512Mi
        ephemeral-storage: 1Gi
```

---

## Network Policies

### Overview

Network policies control traffic between pods (East-West) and to/from external endpoints:
- Namespace-scoped
- Implemented by CNI plugin (VPC CNI 1.14+, Calico, Cilium)
- Default behavior: All traffic allowed if no policies exist
- **Best Practice**: Start with default-deny, then allow specific traffic

### Enable Network Policies (VPC CNI 1.14+)

**Terraform**:
```hcl
module "eks" {
  source = "terraform-aws-modules/eks/aws"

  cluster_addons = {
    vpc-cni = {
      addon_version = "v1.19.2-eksbuild.1"
      configuration_values = jsonencode({
        env = {
          ENABLE_NETWORK_POLICY = "true"  # Enable network policies
        }
      })
    }
  }
}
```

**Verify**:
```bash
# Check if network policy controller is running
kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-network-policy-agent

# Check VPC CNI config
kubectl get daemonset -n kube-system aws-node -o yaml | grep ENABLE_NETWORK_POLICY
```

### Default Deny Policy

**Deny All Ingress and Egress** (start here):
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}  # Applies to all pods in namespace
  policyTypes:
  - Ingress
  - Egress
```

**After applying, all pods in namespace are isolated. Explicitly allow needed traffic.**

### Common Network Policy Patterns

#### Pattern 1: Allow Frontend → Backend

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-allow-frontend
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
```

#### Pattern 2: Allow Backend → Database

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: db-allow-backend
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: database
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: backend
    ports:
    - protocol: TCP
      port: 5432
```

#### Pattern 3: Allow Egress to External API

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-allow-external-api
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Egress
  egress:
  # Allow DNS resolution
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
  # Allow external API access
  - to:
    - podSelector: {}  # Any pod
    ports:
    - protocol: TCP
      port: 443
  # Allow specific external IP
  - to:
    - ipBlock:
        cidr: 203.0.113.0/24  # External API subnet
    ports:
    - protocol: TCP
      port: 443
```

#### Pattern 4: Namespace Isolation

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: namespace-isolation
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  # Only allow traffic from same namespace
  - from:
    - podSelector: {}
```

#### Pattern 5: Allow Ingress Controller

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-allow-ingress
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: frontend
  policyTypes:
  - Ingress
  ingress:
  # Allow traffic from ingress controller namespace
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: ingress-nginx
    ports:
    - protocol: TCP
      port: 80
```

#### Pattern 6: Multi-Tier Application

```yaml
# Frontend policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      tier: frontend
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Allow from ingress controller
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8080
  egress:
  # Allow to backend
  - to:
    - podSelector:
        matchLabels:
          tier: backend
    ports:
    - protocol: TCP
      port: 8080
  # Allow DNS
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
---
# Backend policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      tier: backend
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Allow from frontend
  - from:
    - podSelector:
        matchLabels:
          tier: frontend
    ports:
    - protocol: TCP
      port: 8080
  egress:
  # Allow to database
  - to:
    - podSelector:
        matchLabels:
          tier: database
    ports:
    - protocol: TCP
      port: 5432
  # Allow DNS
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
---
# Database policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: database-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      tier: database
  policyTypes:
  - Ingress
  ingress:
  # Only allow from backend
  - from:
    - podSelector:
        matchLabels:
          tier: backend
    ports:
    - protocol: TCP
      port: 5432
```

### Network Policy Testing

**Test connectivity**:
```bash
# Deploy test pod
kubectl run test-pod --rm -it --image=busybox --namespace=production -- sh

# Test connection to backend
wget -O- http://backend-service:8080

# Test connection to external API
wget -O- https://api.example.com

# Test DNS resolution
nslookup backend-service
```

**Verify policies**:
```bash
# List network policies
kubectl get networkpolicies -n production

# Describe policy
kubectl describe networkpolicy default-deny-all -n production

# View policy YAML
kubectl get networkpolicy backend-allow-frontend -n production -o yaml
```

### Network Policy Tools

**Calico Network Policy Viewer**:
```bash
# Install calicoctl
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/master/manifests/calicoctl.yaml

# View policies
kubectl exec -it -n kube-system calicoctl -- calicoctl get networkpolicy -o wide
```

**Network Policy Visualizer** (https://github.com/kinvolk/inspektor-gadget):
```bash
# Install inspektor-gadget
kubectl gadget deploy

# Trace network connections
kubectl gadget trace tcp --namespace production
```

---

## Security Groups for Pods

### Overview

Security Groups for Pods (SGP) provide AWS-level network security:
- Apply EC2 security groups directly to pods
- Complementary to Kubernetes Network Policies
- Defense-in-depth strategy
- Control access to AWS services (RDS, ElastiCache, etc.)

**Requirements**:
- VPC CNI with `ENABLE_POD_ENI=true`
- EC2 instances with multiple network interfaces
- Supported instance types (not all support pod ENI)

### Enable Security Groups for Pods

**Terraform**:
```hcl
module "eks" {
  source = "terraform-aws-modules/eks/aws"

  cluster_addons = {
    vpc-cni = {
      configuration_values = jsonencode({
        env = {
          ENABLE_POD_ENI = "true"  # Enable SGP
        }
      })
    }
  }
}
```

### Create Security Group for Pods

```hcl
# Security group for backend pods accessing RDS
resource "aws_security_group" "backend_pod_sg" {
  name_prefix = "backend-pod-sg-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for backend pods"

  # Allow outbound to RDS
  egress {
    description     = "Access to RDS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.rds.id]
  }

  # Allow outbound HTTPS
  egress {
    description = "HTTPS to external APIs"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "backend-pod-sg"
  }
}

# Update RDS security group to allow from backend pods
resource "aws_security_group_rule" "rds_allow_backend_pods" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.backend_pod_sg.id
  security_group_id        = aws_security_group.rds.id
  description              = "Allow backend pods to access RDS"
}
```

### Apply Security Group to Pods

**Create SecurityGroupPolicy**:
```yaml
apiVersion: vpcresources.k8s.aws/v1beta1
kind: SecurityGroupPolicy
metadata:
  name: backend-sgp
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend
  securityGroups:
    groupIds:
    - sg-0123456789abcdef0  # backend_pod_sg ID
```

**Deployment with SGP**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend  # Matches SecurityGroupPolicy podSelector
    spec:
      serviceAccountName: backend-sa
      containers:
      - name: backend
        image: backend:v1.0.0
        env:
        - name: DB_HOST
          value: postgres.example.com
        - name: DB_PORT
          value: "5432"
```

### Security Groups for Pods Best Practices

1. **Use with Network Policies**: Defense in depth
2. **One SGP per workload type**: Backend, frontend, workers
3. **Least privilege**: Allow only required traffic
4. **Document security groups**: Tag with purpose and owner
5. **Review regularly**: Audit unused or overly permissive rules

---

## Image Scanning and Verification

### Amazon Inspector for ECR (2025)

**New Capabilities**:
- Container image mapping (ECR images → running containers)
- Extended vulnerability coverage (distroless, scratch, Chainguard images)
- Continuous monitoring and automatic rescans
- Prioritization based on actively running images

### Enable Enhanced Scanning

```bash
# Enable enhanced scanning for all repositories
aws ecr put-registry-scanning-configuration \
  --scan-type ENHANCED \
  --rules '[{
    "repositoryFilters": [{
      "filter": "*",
      "filterType": "WILDCARD"
    }],
    "scanFrequency": "CONTINUOUS_SCAN"
  }]'
```

**Terraform**:
```hcl
resource "aws_ecr_registry_scanning_configuration" "this" {
  scan_type = "ENHANCED"

  rule {
    scan_frequency = "CONTINUOUS_SCAN"

    repository_filter {
      filter      = "*"
      filter_type = "WILDCARD"
    }
  }
}
```

### Automatic Scanning on Push

**ECR Repository Configuration**:
```hcl
resource "aws_ecr_repository" "app" {
  name                 = "my-app"
  image_tag_mutability = "IMMUTABLE"  # Prevent tag overwrites

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr.arn
  }

  tags = {
    Application = "my-app"
    Environment = "production"
  }
}
```

### View Scan Results

```bash
# List findings for a repository
aws inspector2 list-findings \
  --filter-criteria '{
    "ecrImageRepositoryName": [{
      "comparison": "EQUALS",
      "value": "my-app"
    }]
  }'

# Get findings for specific image
aws inspector2 list-findings \
  --filter-criteria '{
    "ecrImageHash": [{
      "comparison": "EQUALS",
      "value": "sha256:abc123..."
    }]
  }'

# Filter by severity
aws inspector2 list-findings \
  --filter-criteria '{
    "severity": [{
      "comparison": "EQUALS",
      "value": "CRITICAL"
    }]
  }'
```

### Block Deployment of Vulnerable Images

**Admission Controller with OPA/Gatekeeper**:
```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: blockvulnerableimages
spec:
  crd:
    spec:
      names:
        kind: BlockVulnerableImages
      validation:
        openAPIV3Schema:
          type: object
          properties:
            maxSeverity:
              type: string
              enum: ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
  targets:
  - target: admission.k8s.gatekeeper.sh
    rego: |
      package blockvulnerableimages

      violation[{"msg": msg}] {
        input.review.kind.kind == "Pod"
        image := input.review.object.spec.containers[_].image
        has_critical_vulnerabilities(image)
        msg := sprintf("Image %v has critical vulnerabilities", [image])
      }

      has_critical_vulnerabilities(image) {
        # Call external API or webhook to check scan results
        # Implementation depends on your scanning tool
      }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: BlockVulnerableImages
metadata:
  name: block-critical-vulns
spec:
  match:
    kinds:
    - apiGroups: [""]
      kinds: ["Pod"]
  parameters:
    maxSeverity: "CRITICAL"
```

### Image Signing and Verification

**Sigstore/Cosign**:

**Sign Image**:
```bash
# Sign image during CI/CD
cosign sign --key cosign.key my-app:v1.0.0

# Verify signature
cosign verify --key cosign.pub my-app:v1.0.0
```

**Verify at Admission with Kyverno**:
```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signatures
spec:
  validationFailureAction: Enforce
  rules:
  - name: verify-signature
    match:
      any:
      - resources:
          kinds:
          - Pod
    verifyImages:
    - imageReferences:
      - "my-registry.io/my-app:*"
      attestors:
      - count: 1
        entries:
        - keys:
            publicKeys: |
              -----BEGIN PUBLIC KEY-----
              MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...
              -----END PUBLIC KEY-----
```

### Lifecycle Policies for Old Images

```hcl
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 production images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Delete untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
```

---

## Admission Controllers

### Overview

Admission controllers intercept requests to Kubernetes API before persistence:
- **Validating**: Validate requests (accept/reject)
- **Mutating**: Modify requests before storage
- Can enforce custom policies beyond RBAC

**Popular Admission Controllers**:
- **OPA/Gatekeeper**: Policy as code (Rego)
- **Kyverno**: Kubernetes-native policies (YAML)
- **Pod Security Admission**: Built-in PSS enforcement

### OPA/Gatekeeper

**Installation**:
```bash
kubectl apply -f https://raw.githubusercontent.com/open-policy-agent/gatekeeper/master/deploy/gatekeeper.yaml
```

**Example Policy: Require Labels**:
```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: requiredlabels
spec:
  crd:
    spec:
      names:
        kind: RequiredLabels
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
      package requiredlabels

      violation[{"msg": msg, "details": {"missing_labels": missing}}] {
        provided := {label | input.review.object.metadata.labels[label]}
        required := {label | label := input.parameters.labels[_]}
        missing := required - provided
        count(missing) > 0
        msg := sprintf("Missing required labels: %v", [missing])
      }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: RequiredLabels
metadata:
  name: require-owner-label
spec:
  match:
    kinds:
    - apiGroups: [""]
      kinds: ["Pod"]
  parameters:
    labels:
    - "owner"
    - "environment"
```

**Example Policy: Allowed Registries**:
```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: allowedregistries
spec:
  crd:
    spec:
      names:
        kind: AllowedRegistries
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
      package allowedregistries

      violation[{"msg": msg}] {
        container := input.review.object.spec.containers[_]
        not startswith(container.image, input.parameters.registries[_])
        msg := sprintf("Image %v not from allowed registry", [container.image])
      }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: AllowedRegistries
metadata:
  name: prod-registries
spec:
  match:
    kinds:
    - apiGroups: [""]
      kinds: ["Pod"]
    namespaces:
    - "production"
  parameters:
    registries:
    - "123456789012.dkr.ecr.us-west-2.amazonaws.com/"
    - "my-approved-registry.io/"
```

### Kyverno

**Installation**:
```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno --namespace kyverno --create-namespace
```

**Example Policy: Require Resource Limits**:
```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-resource-limits
spec:
  validationFailureAction: Enforce
  rules:
  - name: require-cpu-limits
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "CPU limits are required"
      pattern:
        spec:
          containers:
          - resources:
              limits:
                cpu: "?*"
  - name: require-memory-limits
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Memory limits are required"
      pattern:
        spec:
          containers:
          - resources:
              limits:
                memory: "?*"
```

**Example Policy: Disallow Latest Tag**:
```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-latest-tag
spec:
  validationFailureAction: Enforce
  rules:
  - name: require-image-tag
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Using :latest tag is not allowed"
      pattern:
        spec:
          containers:
          - image: "!*:latest"
```

---

## Runtime Security

### Amazon GuardDuty for EKS

**Enable GuardDuty**:
```bash
# Enable GuardDuty
aws guardduty create-detector --enable

# Enable EKS protection
DETECTOR_ID=$(aws guardduty list-detectors --query 'DetectorIds[0]' --output text)

aws guardduty update-detector \
  --detector-id $DETECTOR_ID \
  --data-sources '{
    "Kubernetes": {
      "AuditLogs": {
        "Enable": true
      }
    }
  }'
```

**Terraform**:
```hcl
resource "aws_guardduty_detector" "main" {
  enable = true

  datasources {
    kubernetes {
      audit_logs {
        enable = true
      }
    }
  }
}
```

**GuardDuty Findings**:
- Suspicious API calls
- Privilege escalation attempts
- Cryptocurrency mining detection
- Anomalous network activity
- Container escape attempts
- Compromised credentials

**View Findings**:
```bash
# List EKS-related findings
aws guardduty list-findings \
  --detector-id $DETECTOR_ID \
  --finding-criteria '{
    "Criterion": {
      "resource.resourceType": {
        "Eq": ["EKSCluster"]
      }
    }
  }'

# Get finding details
aws guardduty get-findings \
  --detector-id $DETECTOR_ID \
  --finding-ids <finding-id>
```

### Falco Runtime Security

**Installation via Helm**:
```bash
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco \
  --namespace falco \
  --create-namespace \
  --set ebpf.enabled=true \
  --set falco.grpc.enabled=true \
  --set falco.grpcOutput.enabled=true
```

**Custom Falco Rules**:
```yaml
# /etc/falco/rules.d/custom-rules.yaml
- rule: Detect Shell in Container
  desc: Detect shell execution in container
  condition: >
    spawned_process and
    container and
    proc.name in (bash, sh, zsh)
  output: >
    Shell spawned in container
    (user=%user.name container_id=%container.id container_name=%container.name
    shell=%proc.name parent=%proc.pname cmdline=%proc.cmdline)
  priority: WARNING
  tags: [container, shell]

- rule: Detect Container Escape
  desc: Detect potential container escape attempts
  condition: >
    spawned_process and
    container and
    proc.name in (nsenter, unshare, capsh)
  output: >
    Container escape attempt detected
    (user=%user.name container_id=%container.id proc=%proc.name cmdline=%proc.cmdline)
  priority: CRITICAL
  tags: [container, escape]

- rule: Detect Privileged Container
  desc: Detect containers running in privileged mode
  condition: >
    container_started and
    container.privileged=true
  output: >
    Privileged container started
    (container_id=%container.id container_name=%container.name image=%container.image.repository)
  priority: HIGH
  tags: [container, privileged]
```

**Falco Sidekick for Alerting**:
```bash
helm install falco-sidekick falcosecurity/falcosidekick \
  --namespace falco \
  --set config.slack.webhookurl="https://hooks.slack.com/services/XXX" \
  --set config.slack.minimumpriority="warning"
```

---

## Incident Response

### Detection and Alerting

**Detection Sources**:
1. GuardDuty findings
2. Falco runtime alerts
3. CloudWatch audit log anomalies
4. Network policy violations
5. Container image scan results
6. Application-level security events

### Response Procedures

#### Scenario 1: Compromised Pod

**Detection**:
- GuardDuty alert: "Execution:Kubernetes/MaliciousFileExecuted"
- Falco alert: Unexpected process spawned

**Response**:
```bash
# 1. Immediate isolation
kubectl label pod <pod-name> -n <namespace> security=isolated

# 2. Apply network policy to isolate
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: isolate-compromised-pod
  namespace: <namespace>
spec:
  podSelector:
    matchLabels:
      security: isolated
  policyTypes:
  - Ingress
  - Egress
EOF

# 3. Collect forensics
kubectl logs <pod-name> -n <namespace> > pod-logs.txt
kubectl exec <pod-name> -n <namespace> -- ps aux > processes.txt
kubectl exec <pod-name> -n <namespace> -- netstat -tuln > connections.txt

# 4. Save pod manifest
kubectl get pod <pod-name> -n <namespace> -o yaml > pod-manifest.yaml

# 5. Delete pod
kubectl delete pod <pod-name> -n <namespace>

# 6. Check deployment/replicaset
kubectl get deployment -n <namespace>
kubectl rollout history deployment/<deployment-name> -n <namespace>

# 7. If needed, rollback
kubectl rollout undo deployment/<deployment-name> -n <namespace>

# 8. Analyze and patch
# - Review logs and forensics
# - Identify vulnerability or misconfiguration
# - Update deployment with fix
# - Re-scan container image
```

#### Scenario 2: Privilege Escalation Attempt

**Detection**:
- Audit log: RBAC modification attempt
- GuardDuty: "PrivilegeEscalation:Kubernetes/PrivilegedContainer"

**Response**:
```bash
# 1. Identify user/service account
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# 2. Review RBAC permissions
kubectl auth can-i --list --as=system:serviceaccount:<namespace>:<sa-name>

# 3. Check role bindings
kubectl get rolebindings,clusterrolebindings -A -o wide | grep <user-or-sa>

# 4. Revoke excessive permissions
kubectl delete rolebinding <rolebinding-name> -n <namespace>

# 5. Review audit logs
aws logs filter-log-events \
  --log-group-name /aws/eks/<cluster-name>/cluster \
  --filter-pattern '{ $.user.username = "<username>" && $.verb = "create" }'

# 6. Update RBAC policies
kubectl apply -f updated-rbac.yaml
```

#### Scenario 3: Cryptocurrency Mining

**Detection**:
- High CPU utilization
- GuardDuty: "CryptoCurrency:Kubernetes/MiningActivity"
- Network traffic to mining pools

**Response**:
```bash
# 1. Identify affected pods
kubectl top pods -A --sort-by=cpu

# 2. Check network connections
kubectl exec <pod-name> -n <namespace> -- netstat -tuln | grep -E '(3333|4444|5555)'

# 3. Isolate pod (see Scenario 1)
kubectl label pod <pod-name> -n <namespace> security=isolated

# 4. Block mining pool egress
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: block-mining-pools
  namespace: <namespace>
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
        except:
        - 45.76.0.0/16   # Common mining pool IP range
        - 104.16.0.0/12  # Another mining pool range
EOF

# 5. Delete pod and review image
kubectl delete pod <pod-name> -n <namespace>

# 6. Scan image for malware
aws ecr start-image-scan --repository-name <repo> --image-id imageTag=<tag>
```

#### Scenario 4: Data Exfiltration

**Detection**:
- Large egress traffic volumes
- Access to sensitive resources (S3, RDS)
- GuardDuty: "Exfiltration:Kubernetes/AnomalousDataVolume"

**Response**:
```bash
# 1. Identify source pod
kubectl top pods -A --sort-by=memory

# 2. Check VPC Flow Logs
aws ec2 describe-flow-logs --filter "Name=resource-id,Values=<eni-id>"

# 3. Block egress immediately
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: block-all-egress
  namespace: <namespace>
spec:
  podSelector:
    matchLabels:
      app: <app-label>
  policyTypes:
  - Egress
  egress: []  # Block all egress
EOF

# 4. Review IAM permissions (if using IRSA)
aws iam get-role --role-name <irsa-role-name>
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=<s3-bucket>

# 5. Revoke IAM permissions
aws iam detach-role-policy \
  --role-name <irsa-role-name> \
  --policy-arn <policy-arn>

# 6. Investigate and remediate
# - Review application code for vulnerabilities
# - Check for compromised credentials
# - Rotate secrets
```

### Post-Incident Actions

1. **Root Cause Analysis**: Document what happened, how it happened, why controls failed
2. **Update Runbooks**: Improve incident response procedures
3. **Patch Vulnerabilities**: Fix identified security gaps
4. **Enhance Monitoring**: Add new detection rules
5. **Training**: Educate team on lessons learned
6. **Compliance Reporting**: Notify required parties (HIPAA, PCI-DSS, etc.)

---

**Next**: [Secrets Management](secrets-management.md) for External Secrets Operator, AWS Secrets Manager integration, and secure secret handling.
