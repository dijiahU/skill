# Cluster-Level Security Configuration

Complete guide to hardening EKS control plane, IAM authentication, RBAC, audit logging, and compliance frameworks.

## Table of Contents

1. [Control Plane Security](#control-plane-security)
2. [API Endpoint Configuration](#api-endpoint-configuration)
3. [IAM Roles for Service Accounts (IRSA)](#iam-roles-for-service-accounts-irsa)
4. [RBAC Configuration](#rbac-configuration)
5. [Audit Logging](#audit-logging)
6. [Secrets Encryption](#secrets-encryption)
7. [Compliance Frameworks](#compliance-frameworks)
8. [Terraform Examples](#terraform-examples)

---

## Control Plane Security

### Overview

EKS control plane runs in AWS-managed VPC with automatic multi-AZ deployment:
- Minimum 2 API server nodes in distinct AZs
- etcd cluster spanning 3 AZs with auto-scaling
- Automatic monitoring and replacement of failed instances
- Isolated infrastructure per cluster (no cross-cluster or cross-account overlap)

### Security Checklist

- [ ] **Latest Kubernetes version**: Stay within 2 versions of latest (currently 1.33)
- [ ] **Secrets encryption enabled**: KMS-based encryption for etcd secrets
- [ ] **Control plane logging enabled**: All 5 log types activated
- [ ] **Private endpoint configuration**: Limit API server exposure
- [ ] **IP allowlisting**: Restrict public endpoint access
- [ ] **Security group controls**: Limit network access

### Kubernetes Version Management

**Current Supported Versions (2025)**:
- 1.33 (latest)
- 1.32
- 1.31
- 1.30

**Version Skew Policy**:
- Worker nodes support 2-3 version skew from control plane
- Stay within 2 versions of latest for security patches
- Plan upgrades quarterly

**Version Check**:
```bash
# Check cluster version
aws eks describe-cluster --name production-cluster --query 'cluster.version' --output text

# Check available versions
aws eks describe-addon-versions --kubernetes-version 1.33
```

### Control Plane Update Strategy

**Blue/Green Cluster Approach**:
1. Create new cluster with updated version
2. Update IRSA trust policies with new OIDC endpoint
3. Migrate workloads incrementally
4. Validate functionality
5. Decommission old cluster

**In-Place Upgrade**:
```bash
# Upgrade control plane
aws eks update-cluster-version \
  --name production-cluster \
  --kubernetes-version 1.33

# Monitor upgrade
aws eks describe-update \
  --name production-cluster \
  --update-id <update-id>

# Upgrade managed node groups
aws eks update-nodegroup-version \
  --cluster-name production-cluster \
  --nodegroup-name general-nodes \
  --kubernetes-version 1.33
```

---

## API Endpoint Configuration

### Endpoint Patterns

#### Pattern 1: Public Endpoint Only (Not Recommended for Production)

**Configuration**:
```hcl
cluster_endpoint_public_access  = true
cluster_endpoint_private_access = false
public_access_cidrs            = ["0.0.0.0/0"]  # Open to internet
```

**Use Case**: Development, testing, demos

**Security Concerns**:
- API server exposed to internet
- Vulnerable to scanning and brute-force
- No internal optimization

**If You Must Use**:
- Implement strict IP allowlisting
- Enable audit logging
- Use strong IAM authentication
- Monitor API calls continuously

#### Pattern 2: Public + Private Endpoints (Recommended for Production)

**Configuration**:
```hcl
cluster_endpoint_public_access  = true
cluster_endpoint_private_access = true
public_access_cidrs            = [
  "203.0.113.0/24",  # Office network
  "198.51.100.0/24"  # VPN gateway
]
```

**Benefits**:
- Internal traffic uses private endpoint (lower latency, no NAT costs)
- External access for CI/CD, developers
- Optimized performance
- Flexible access control

**Architecture**:
```
┌─────────────────┐
│   Developer     │
│   kubectl       │────► Public Endpoint (IP allowlist)
└─────────────────┘

┌─────────────────┐
│   Worker Nodes  │
│   in VPC        │────► Private Endpoint (X-ENIs)
└─────────────────┘
```

**Best Practices**:
- Allowlist only necessary IPs (VPN, CI/CD, bastion)
- Use /32 CIDR for individual IPs
- Document each allowed CIDR with purpose
- Review allowlist monthly

#### Pattern 3: Private Endpoint Only (Maximum Security)

**Configuration**:
```hcl
cluster_endpoint_public_access  = false
cluster_endpoint_private_access = true
```

**Requirements**:
- VPN or AWS Direct Connect for external access
- Bastion host in VPC for kubectl access
- VPC peering for cross-VPC access
- Cloud9 or similar cloud IDE

**Access Methods**:

**AWS VPN**:
```bash
# Connect via VPN
aws ec2 create-vpn-connection \
  --type ipsec.1 \
  --customer-gateway-id cgw-xxx \
  --vpn-gateway-id vgw-xxx

# Access cluster
kubectl get nodes
```

**Bastion Host**:
```bash
# SSH to bastion in VPC
ssh -i bastion-key.pem ec2-user@bastion-host

# From bastion, access cluster
kubectl get nodes
```

**Cloud9 IDE**:
```bash
# Launch Cloud9 in VPC
aws cloud9 create-environment-ec2 \
  --name eks-admin \
  --instance-type t3.small \
  --subnet-id subnet-xxx \
  --automatic-stop-time-minutes 30

# Access cluster from Cloud9 terminal
kubectl get nodes
```

**Use Case**: Healthcare, finance, highly regulated industries

### IP Allowlist Management

**Best Practices**:
```hcl
# Terraform: IP allowlist with documentation
variable "api_access_cidrs" {
  type = map(string)
  default = {
    "office_network"     = "203.0.113.0/24"
    "vpn_gateway"        = "198.51.100.0/24"
    "ci_cd_github"       = "192.0.2.0/24"
    "bastion_host"       = "198.51.100.10/32"
    "admin_home_office"  = "203.0.113.50/32"
  }
}

module "eks" {
  source = "terraform-aws-modules/eks/aws"

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true
  public_access_cidrs            = values(var.api_access_cidrs)
}
```

**Update Allowlist**:
```bash
# Add new CIDR
aws eks update-cluster-config \
  --name production-cluster \
  --resources-vpc-config \
    publicAccessCidrs=["203.0.113.0/24","198.51.100.0/24","192.0.2.50/32"]

# View current allowlist
aws eks describe-cluster \
  --name production-cluster \
  --query 'cluster.resourcesVpcConfig.publicAccessCidrs'
```

### Security Groups

**Control Plane Security Group**:
- Automatically created by EKS
- Controls traffic between control plane and worker nodes
- Do not modify (managed by AWS)

**Cluster Security Group**:
- Additional security group for cluster resources
- Can customize for specific requirements
- Applied to all worker nodes

**Custom Security Group Example**:
```hcl
resource "aws_security_group" "cluster_additional" {
  name_prefix = "${var.cluster_name}-additional-"
  vpc_id      = module.vpc.vpc_id

  # Allow inbound HTTPS from VPN
  ingress {
    description = "HTTPS from VPN"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  # Deny all other inbound
  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.cluster_name}-additional-sg"
  }
}

module "eks" {
  source = "terraform-aws-modules/eks/aws"

  cluster_additional_security_group_ids = [
    aws_security_group.cluster_additional.id
  ]
}
```

---

## IAM Roles for Service Accounts (IRSA)

### Overview

IRSA allows Kubernetes service accounts to assume IAM roles using OIDC identity provider:
- Pod-level AWS permissions (not node-level)
- Automatic credential rotation via AWS STS
- Prevents privilege escalation
- Audit trail through CloudTrail
- Eliminates need for extended node permissions

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    IRSA Flow                            │
└─────────────────────────────────────────────────────────┘

1. Pod requests credentials
   ↓
2. EKS injects OIDC token (JWT) into pod
   ↓
3. Pod calls AWS STS AssumeRoleWithWebIdentity
   ↓
4. STS validates OIDC token with EKS OIDC provider
   ↓
5. STS returns temporary credentials (15 min - 12 hours)
   ↓
6. Pod uses credentials to access AWS services
   ↓
7. Credentials auto-rotate before expiration
```

### Setup IRSA

**Step 1: Enable IRSA on Cluster** (Terraform)
```hcl
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  cluster_name = "production-cluster"
  enable_irsa  = true  # Enables OIDC provider
}

# OIDC provider ARN output
output "oidc_provider_arn" {
  value = module.eks.oidc_provider_arn
}
```

**Step 2: Create IAM Role for Service Account**
```hcl
# IAM Role with OIDC trust policy
module "app_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "my-app-s3-access"

  # Trust policy scoped to specific namespace and service account
  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = [
        "production:my-app-sa",
        "staging:my-app-sa"
      ]
    }
  }

  # Attach policies
  role_policy_arns = {
    s3_access = aws_iam_policy.app_s3_policy.arn
  }

  tags = {
    Application = "my-app"
    Environment = "production"
  }
}

# Custom IAM policy
resource "aws_iam_policy" "app_s3_policy" {
  name        = "my-app-s3-policy"
  description = "S3 access for my-app"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "arn:aws:s3:::my-app-bucket/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = "arn:aws:s3:::my-app-bucket"
      }
    ]
  })
}
```

**Step 3: Create Kubernetes Service Account**
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app-sa
  namespace: production
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/my-app-s3-access
```

**Step 4: Use Service Account in Deployment**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      serviceAccountName: my-app-sa  # ← Use IRSA service account
      containers:
      - name: app
        image: my-app:v1.0.0
        env:
        # AWS SDK automatically discovers credentials from IRSA
        - name: AWS_REGION
          value: us-west-2
        # These are automatically injected by EKS:
        # - AWS_WEB_IDENTITY_TOKEN_FILE
        # - AWS_ROLE_ARN
```

### IRSA Best Practices

#### 1. Explicit Trust Policies

**Bad** - Allows any service account in namespace:
```json
{
  "Condition": {
    "StringEquals": {
      "oidc.eks.us-west-2.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE:sub": "system:serviceaccount:production:*"
    }
  }
}
```

**Good** - Scoped to specific service account:
```json
{
  "Condition": {
    "StringEquals": {
      "oidc.eks.us-west-2.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE:sub": "system:serviceaccount:production:my-app-sa",
      "oidc.eks.us-west-2.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE:aud": "sts.amazonaws.com"
    }
  }
}
```

#### 2. Least Privilege IAM Policies

**Bad** - Overly permissive:
```json
{
  "Effect": "Allow",
  "Action": "s3:*",
  "Resource": "*"
}
```

**Good** - Scoped to specific resources and actions:
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:GetObject",
    "s3:PutObject"
  ],
  "Resource": "arn:aws:s3:::my-app-bucket/data/*"
}
```

#### 3. Dedicated Service Accounts

**Bad** - Sharing service accounts:
```yaml
# Multiple apps using same service account
serviceAccountName: default  # ❌ Never use default
```

**Good** - One service account per application:
```yaml
# Each app has its own service account
serviceAccountName: my-app-sa
```

#### 4. IMDSv2 Enforcement

Restrict IMDS access to prevent pods from accessing node IAM role:

```hcl
# Managed node group with IMDSv2
eks_managed_node_groups = {
  general = {
    # ... other config ...

    metadata_options = {
      http_endpoint               = "enabled"
      http_tokens                 = "required"  # Enforce IMDSv2
      http_put_response_hop_limit = 1
      instance_metadata_tags      = "disabled"
    }
  }
}
```

### IRSA Troubleshooting

**Pod cannot assume role**:
```bash
# Check service account annotation
kubectl get sa my-app-sa -n production -o yaml | grep role-arn

# Check IAM role trust policy
aws iam get-role --role-name my-app-s3-access --query 'Role.AssumeRolePolicyDocument'

# Check OIDC provider
aws iam list-open-id-connect-providers

# Verify token injection
kubectl describe pod <pod-name> -n production | grep AWS_
```

**Access denied errors**:
```bash
# Check CloudTrail for denied API calls
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=my-app-bucket \
  --max-results 10

# Verify IAM policy
aws iam get-policy-version \
  --policy-arn arn:aws:iam::123456789012:policy/my-app-s3-policy \
  --version-id v1
```

### Common IRSA Patterns

**Pattern 1: S3 Access**
```hcl
module "s3_irsa" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name = "app-s3-access"
  attach_s3_policy = true  # Predefined S3 policy
  s3_bucket_arns   = ["arn:aws:s3:::my-bucket"]

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["production:app-sa"]
    }
  }
}
```

**Pattern 2: RDS Access**
```hcl
module "rds_irsa" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name = "app-rds-access"

  role_policy_arns = {
    rds = aws_iam_policy.rds_connect.arn
  }

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["production:app-sa"]
    }
  }
}

resource "aws_iam_policy" "rds_connect" {
  name = "rds-iam-auth-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "rds-db:connect"
      Resource = "arn:aws:rds-db:${var.region}:${data.aws_caller_identity.current.account_id}:dbuser:${aws_db_instance.main.resource_id}/*"
    }]
  })
}
```

**Pattern 3: Secrets Manager Access**
```hcl
module "secrets_irsa" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name = "external-secrets-controller"

  role_policy_arns = {
    secrets = aws_iam_policy.secrets_access.arn
  }

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["external-secrets:external-secrets-sa"]
    }
  }
}

resource "aws_iam_policy" "secrets_access" {
  name = "secrets-manager-read-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:prod/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = aws_kms_key.secrets.arn
      }
    ]
  })
}
```

---

## RBAC Configuration

### Overview

Role-Based Access Control (RBAC) controls Kubernetes API access:
- Who can perform what actions on which resources
- Namespace-scoped (Role) or cluster-wide (ClusterRole)
- Binds users/groups/service accounts to roles
- Principle of least privilege

### RBAC Architecture

```
User/ServiceAccount
        ↓
  RoleBinding / ClusterRoleBinding
        ↓
   Role / ClusterRole
        ↓
  API Resources (pods, services, deployments, etc.)
```

### Default Roles

**cluster-admin**: Full cluster access (super admin)
**admin**: Full namespace access
**edit**: Read/write namespace access (no RBAC modification)
**view**: Read-only namespace access

### RBAC Best Practices

#### 1. Dedicated Service Accounts

```yaml
# Create service account per application
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app-sa
  namespace: production
```

#### 2. Namespace-Scoped Roles (Preferred)

```yaml
# Role for deployment management
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: deployment-manager
  namespace: production
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
---
# Bind role to service account
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: my-app-deployment-manager
  namespace: production
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: deployment-manager
subjects:
- kind: ServiceAccount
  name: my-app-sa
  namespace: production
```

#### 3. Cluster-Wide Roles (Use Sparingly)

```yaml
# ClusterRole for node access (cluster-wide resource)
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: node-reader
rules:
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list", "watch"]
---
# ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: monitoring-node-reader
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: node-reader
subjects:
- kind: ServiceAccount
  name: prometheus-sa
  namespace: monitoring
```

### Common RBAC Patterns

**Pattern 1: Read-Only Access**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: read-only
  namespace: production
rules:
- apiGroups: ["", "apps", "batch"]
  resources: ["*"]
  verbs: ["get", "list", "watch"]
```

**Pattern 2: CI/CD Deployer**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: cicd-deployer
  namespace: production
rules:
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "watch", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
```

**Pattern 3: Developer Access (No Secrets)**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: developer
  namespace: production
rules:
- apiGroups: ["", "apps", "batch"]
  resources: ["*"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: [""]
  resources: ["secrets"]
  verbs: []  # No access to secrets
```

### AWS IAM to Kubernetes RBAC Mapping

**ConfigMap: aws-auth**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aws-auth
  namespace: kube-system
data:
  mapRoles: |
    - rolearn: arn:aws:iam::123456789012:role/EKSNodeRole
      username: system:node:{{EC2PrivateDNSName}}
      groups:
        - system:bootstrappers
        - system:nodes
    - rolearn: arn:aws:iam::123456789012:role/EKSAdminRole
      username: admin
      groups:
        - system:masters
    - rolearn: arn:aws:iam::123456789012:role/EKSDeveloperRole
      username: developer
      groups:
        - developers
  mapUsers: |
    - userarn: arn:aws:iam::123456789012:user/alice
      username: alice
      groups:
        - system:masters
    - userarn: arn:aws:iam::123456789012:user/bob
      username: bob
      groups:
        - developers
```

**Terraform**:
```hcl
module "eks" {
  source = "terraform-aws-modules/eks/aws"

  # Map IAM roles to Kubernetes groups
  manage_aws_auth_configmap = true

  aws_auth_roles = [
    {
      rolearn  = "arn:aws:iam::123456789012:role/EKSAdminRole"
      username = "admin"
      groups   = ["system:masters"]
    },
    {
      rolearn  = "arn:aws:iam::123456789012:role/EKSDeveloperRole"
      username = "developer"
      groups   = ["developers"]
    }
  ]

  aws_auth_users = [
    {
      userarn  = "arn:aws:iam::123456789012:user/alice"
      username = "alice"
      groups   = ["system:masters"]
    }
  ]
}

# Create Kubernetes RoleBinding for developers group
resource "kubernetes_role_binding" "developers" {
  metadata {
    name      = "developers-binding"
    namespace = "production"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = "developer"
  }

  subject {
    kind = "Group"
    name = "developers"
  }
}
```

### RBAC Audit

```bash
# List all roles in namespace
kubectl get roles -n production

# List all role bindings
kubectl get rolebindings -n production

# Check what a service account can do
kubectl auth can-i --list --as=system:serviceaccount:production:my-app-sa -n production

# Check specific permission
kubectl auth can-i delete pods --as=system:serviceaccount:production:my-app-sa -n production

# View role details
kubectl describe role deployment-manager -n production

# View binding details
kubectl describe rolebinding my-app-deployment-manager -n production
```

---

## Audit Logging

### Overview

EKS control plane logging captures 5 log types:
1. **API server**: API requests (authentication, authorization, admission)
2. **Audit**: Record of requests to API server
3. **Authenticator**: IAM authentication logs
4. **Controller manager**: Core control loops
5. **Scheduler**: Pod scheduling decisions

### Enable All Logging

**Terraform**:
```hcl
module "eks" {
  source = "terraform-aws-modules/eks/aws"

  cluster_enabled_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]
}
```

**AWS CLI**:
```bash
aws eks update-cluster-config \
  --name production-cluster \
  --logging '{"clusterLogging":[{"types":["api","audit","authenticator","controllerManager","scheduler"],"enabled":true}]}'
```

### Log Retention

```bash
# Set retention to 90 days
aws logs put-retention-policy \
  --log-group-name /aws/eks/production-cluster/cluster \
  --retention-in-days 90
```

### Audit Log Analysis

**CloudWatch Logs Insights Queries**:

**Failed Authentication Attempts**:
```
fields @timestamp, user.username, sourceIPs[0], responseStatus.code
| filter responseStatus.code >= 400
| filter verb != "get" and verb != "list" and verb != "watch"
| sort @timestamp desc
| limit 100
```

**Unauthorized Access Attempts**:
```
fields @timestamp, user.username, verb, objectRef.resource, objectRef.name, responseStatus.code
| filter responseStatus.code == 403
| stats count() by user.username, verb, objectRef.resource
| sort count desc
```

**Secret Access**:
```
fields @timestamp, user.username, verb, objectRef.name
| filter objectRef.resource == "secrets"
| filter verb == "get" or verb == "list"
| sort @timestamp desc
```

**Privilege Escalation Attempts**:
```
fields @timestamp, user.username, objectRef.resource, verb
| filter objectRef.resource == "roles" or objectRef.resource == "clusterroles" or objectRef.resource == "rolebindings" or objectRef.resource == "clusterrolebindings"
| filter verb == "create" or verb == "update" or verb == "patch"
| sort @timestamp desc
```

**Pod Creation/Deletion**:
```
fields @timestamp, user.username, verb, objectRef.name, objectRef.namespace
| filter objectRef.resource == "pods"
| filter verb == "create" or verb == "delete"
| sort @timestamp desc
```

### Audit Policy Customization

**Custom Audit Policy** (Advanced):
```yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  # Log secret access at RequestResponse level
  - level: RequestResponse
    resources:
    - group: ""
      resources: ["secrets"]

  # Log RBAC changes at RequestResponse level
  - level: RequestResponse
    resources:
    - group: "rbac.authorization.k8s.io"
      resources: ["roles", "rolebindings", "clusterroles", "clusterrolebindings"]

  # Log pod creation/deletion at Metadata level
  - level: Metadata
    resources:
    - group: ""
      resources: ["pods"]
    verbs: ["create", "delete"]

  # Don't log read-only requests
  - level: None
    verbs: ["get", "list", "watch"]
```

**Note**: EKS does not currently support custom audit policies. Use CloudWatch Logs Insights for filtering.

### Alerting on Audit Events

**CloudWatch Alarm: Failed Authentication**:
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name eks-failed-auth \
  --alarm-description "Alert on failed authentication attempts" \
  --metric-name FailedAuthCount \
  --namespace EKS/Security \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:us-west-2:123456789012:security-alerts
```

---

## Secrets Encryption

### Enable KMS Encryption for etcd

**Terraform**:
```hcl
# KMS key for EKS secrets
resource "aws_kms_key" "eks" {
  description             = "EKS secrets encryption key"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = {
    Name = "${var.cluster_name}-eks-secrets"
  }
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${var.cluster_name}-eks-secrets"
  target_key_id = aws_kms_key.eks.key_id
}

# Grant EKS permission to use key
resource "aws_kms_grant" "eks" {
  name              = "${var.cluster_name}-eks-grant"
  key_id            = aws_kms_key.eks.key_id
  grantee_principal = data.aws_iam_role.cluster.arn

  operations = [
    "Encrypt",
    "Decrypt",
    "GenerateDataKey"
  ]
}

# Enable encryption on cluster
module "eks" {
  source = "terraform-aws-modules/eks/aws"

  cluster_encryption_config = {
    resources        = ["secrets"]
    provider_key_arn = aws_kms_key.eks.arn
  }
}
```

**AWS CLI**:
```bash
# Create KMS key
KEY_ID=$(aws kms create-key \
  --description "EKS secrets encryption" \
  --query 'KeyMetadata.KeyId' \
  --output text)

# Enable encryption (requires cluster recreation)
aws eks create-cluster \
  --name production-cluster \
  --encryption-config resources=secrets,provider={keyArn=arn:aws:kms:us-west-2:123456789012:key/$KEY_ID}
```

**Important**: Encryption can only be enabled at cluster creation, not after.

### Encryption Best Practices

1. **Enable key rotation**: Automatic annual rotation
2. **Monitor key usage**: CloudTrail logs all KMS operations
3. **Restrict key access**: Limit who can use encryption key
4. **Backup encrypted data**: Secrets remain encrypted in backups
5. **Document encryption**: Track which resources are encrypted

### Key Policy Example

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Enable IAM User Permissions",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:root"
      },
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "Allow EKS to use the key",
      "Effect": "Allow",
      "Principal": {
        "Service": "eks.amazonaws.com"
      },
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "eks.us-west-2.amazonaws.com"
        }
      }
    }
  ]
}
```

---

## Compliance Frameworks

### CIS Kubernetes Benchmark

**Tool**: kube-bench

**Installation**:
```bash
# Run as Kubernetes job
kubectl apply -f https://raw.githubusercontent.com/aquasecurity/kube-bench/main/job-eks.yaml

# View results
kubectl logs -n kube-bench job/kube-bench
```

**Key Controls**:

**1.2 API Server**:
- [ ] `--anonymous-auth=false`
- [ ] `--authorization-mode=RBAC`
- [ ] `--audit-log-path` configured
- [ ] `--encryption-provider-config` set

**2.1 etcd**:
- [ ] Encryption at rest enabled
- [ ] TLS enabled
- [ ] Access restricted to API server

**3.1 Control Plane Configuration**:
- [ ] RBAC enabled
- [ ] Pod Security Standards enforced
- [ ] Service account tokens mounted only when necessary

**4.1 Worker Nodes**:
- [ ] Kubelet authentication enabled
- [ ] Read-only port disabled
- [ ] Anonymous authentication disabled

**5.1 RBAC and Service Accounts**:
- [ ] Default service accounts not used
- [ ] Service account tokens auto-mounted only when necessary
- [ ] Least privilege RBAC policies

**Remediation**:
```bash
# Export results
kubectl logs -n kube-bench job/kube-bench > cis-benchmark-results.txt

# Review failures
grep "\[FAIL\]" cis-benchmark-results.txt

# Automated remediation (use with caution)
kubectl apply -f remediation-manifests/
```

### NIST 800-190 Container Security

**Five Pillars**:

**1. Image Security**:
- [ ] Scan images for vulnerabilities (Amazon Inspector)
- [ ] Use trusted base images
- [ ] Implement image signing (Sigstore, Notary)
- [ ] Maintain image inventory

**2. Registry Security**:
- [ ] Use Amazon ECR with encryption
- [ ] Implement access controls (IAM)
- [ ] Enable vulnerability scanning
- [ ] Lifecycle policies for old images

**3. Orchestrator Security**:
- [ ] RBAC configured
- [ ] Audit logging enabled
- [ ] Secrets encrypted
- [ ] Network segmentation

**4. Container Runtime Security**:
- [ ] Runtime monitoring (Falco, GuardDuty)
- [ ] Security contexts enforced
- [ ] Resource limits set
- [ ] Privileged containers restricted

**5. Host Security**:
- [ ] OS hardening (Bottlerocket, AL2023)
- [ ] IMDSv2 enforced
- [ ] Security patches applied
- [ ] SSM for access (no SSH)

### SOC2 Type II

**Control Objectives**:

**Security**:
- [ ] Multi-factor authentication (AWS IAM MFA)
- [ ] Encryption at rest and in transit
- [ ] Network segmentation
- [ ] Vulnerability management

**Availability**:
- [ ] Multi-AZ deployment
- [ ] Auto-scaling configured
- [ ] Disaster recovery tested
- [ ] Monitoring and alerting

**Processing Integrity**:
- [ ] Admission controllers (OPA/Gatekeeper)
- [ ] Data validation
- [ ] Audit trails

**Confidentiality**:
- [ ] Secrets management (External Secrets Operator)
- [ ] Access controls (RBAC + IRSA)
- [ ] Data classification

**Privacy**:
- [ ] PII handling procedures
- [ ] Data retention policies
- [ ] Right to deletion processes

### HIPAA Compliance

**Key Requirements**:

**Administrative Safeguards**:
- [ ] Access management (RBAC)
- [ ] Workforce training
- [ ] Incident response plan
- [ ] Risk assessments

**Physical Safeguards**:
- [ ] AWS facility controls (inherited)
- [ ] Workstation security
- [ ] Device controls

**Technical Safeguards**:
- [ ] Access controls (IAM + RBAC)
- [ ] Audit controls (CloudTrail + audit logs)
- [ ] Integrity controls (checksums, signatures)
- [ ] Transmission security (TLS, VPN)

**Breach Notification**:
- [ ] Detection mechanisms (GuardDuty)
- [ ] Notification procedures
- [ ] Documentation requirements

---

## Terraform Examples

### Complete Secure Cluster

```hcl
# Production-ready secure EKS cluster
module "eks_secure" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  cluster_name    = "production-secure"
  cluster_version = "1.33"

  # VPC configuration
  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.intra_subnets

  # Control plane security
  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true
  public_access_cidrs            = var.allowed_cidrs

  # Enable IRSA
  enable_irsa = true

  # Secrets encryption
  cluster_encryption_config = {
    resources        = ["secrets"]
    provider_key_arn = aws_kms_key.eks.arn
  }

  # Comprehensive logging
  cluster_enabled_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]

  # Managed add-ons
  cluster_addons = {
    coredns = {
      addon_version     = "v1.11.3-eksbuild.2"
      resolve_conflicts = "OVERWRITE"
    }
    kube-proxy = {
      addon_version     = "v1.33.1-eksbuild.1"
      resolve_conflicts = "OVERWRITE"
    }
    vpc-cni = {
      addon_version     = "v1.19.2-eksbuild.1"
      resolve_conflicts = "OVERWRITE"
      configuration_values = jsonencode({
        env = {
          ENABLE_PREFIX_DELEGATION = "true"
          ENABLE_POD_ENI          = "true"
        }
      })
      service_account_role_arn = module.vpc_cni_irsa.iam_role_arn
    }
    aws-ebs-csi-driver = {
      addon_version                = "v1.38.2-eksbuild.1"
      service_account_role_arn     = module.ebs_csi_irsa.iam_role_arn
      resolve_conflicts            = "OVERWRITE"
    }
  }

  # Managed node groups with security hardening
  eks_managed_node_groups = {
    secure_nodes = {
      name           = "secure-node-group"
      instance_types = ["t3.large"]

      min_size     = 2
      max_size     = 10
      desired_size = 3

      # Use latest AL2023 AMI
      ami_type = "AL2023_x86_64_STANDARD"

      # Enforce IMDSv2
      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 1
        instance_metadata_tags      = "disabled"
      }

      # Encrypted EBS volumes
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 100
            volume_type           = "gp3"
            encrypted             = true
            kms_key_id            = aws_kms_key.ebs.arn
            delete_on_termination = true
          }
        }
      }

      # Deploy in private subnets
      subnet_ids = module.vpc.private_subnets

      # Security labels
      labels = {
        Environment = "production"
        Security    = "hardened"
      }
    }
  }

  # Manage AWS auth ConfigMap
  manage_aws_auth_configmap = true

  aws_auth_roles = [
    {
      rolearn  = aws_iam_role.eks_admin.arn
      username = "admin"
      groups   = ["system:masters"]
    },
    {
      rolearn  = aws_iam_role.eks_developer.arn
      username = "developer"
      groups   = ["developers"]
    }
  ]

  tags = {
    Environment = "production"
    Compliance  = "SOC2-HIPAA"
    Security    = "hardened"
  }
}

# KMS keys
resource "aws_kms_key" "eks" {
  description             = "EKS secrets encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true
}

resource "aws_kms_key" "ebs" {
  description             = "EKS EBS volume encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true
}

# CloudWatch log retention
resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${module.eks_secure.cluster_name}/cluster"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.logs.arn
}

# GuardDuty for EKS
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

---

**Next**: [Workload Security](workload-security.md) for Pod Security Standards, network policies, and runtime security.
