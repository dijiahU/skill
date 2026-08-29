# Secrets Management

Complete guide to secure secrets handling in EKS with External Secrets Operator, AWS Secrets Manager, CSI Secrets Store Driver, rotation strategies, and audit practices.

## Table of Contents

1. [Overview](#overview)
2. [External Secrets Operator](#external-secrets-operator)
3. [AWS Secrets Manager Integration](#aws-secrets-manager-integration)
4. [CSI Secrets Store Driver](#csi-secrets-store-driver)
5. [Secret Rotation](#secret-rotation)
6. [Encryption at Rest](#encryption-at-rest)
7. [Audit and Monitoring](#audit-and-monitoring)
8. [Best Practices](#best-practices)

---

## Overview

### Secret Storage Options

| Solution | Pros | Cons | Use Case |
|----------|------|------|----------|
| **Kubernetes Secrets** | Native, simple | Base64 only, manual rotation | Development, non-sensitive config |
| **External Secrets Operator** | Auto-sync, multiple backends, Fargate support | Additional component | **Recommended for production** |
| **CSI Secrets Store Driver** | Direct volume mount, auto-rotation | DaemonSet (no Fargate), complexity | EC2 nodes only, high security |
| **Sealed Secrets** | GitOps-friendly | Key management burden | GitOps workflows |

### Secrets Management Strategy (2025)

**Recommended Approach**:
1. **Store secrets in AWS Secrets Manager** (or SSM Parameter Store)
2. **Use External Secrets Operator** for automatic synchronization
3. **Enable KMS encryption** for Kubernetes secrets at rest
4. **Implement automatic rotation** for credentials
5. **Audit access** via CloudTrail and Kubernetes audit logs

---

## External Secrets Operator

### Overview

External Secrets Operator (ESO) syncs secrets from external providers to Kubernetes:
- **Supported backends**: AWS Secrets Manager, SSM Parameter Store, HashiCorp Vault, Azure Key Vault, Google Secrets Manager, and 30+ others
- **Automatic synchronization**: Polls external store on configured interval (default: 1 hour)
- **IRSA authentication**: Uses service account IAM roles for AWS access
- **Fargate compatible**: Runs as Deployment (not DaemonSet)

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│              External Secrets Operator Flow             │
└─────────────────────────────────────────────────────────┘

1. ExternalSecret resource created
   ↓
2. ESO controller reads ExternalSecret
   ↓
3. ESO uses IRSA to authenticate to AWS
   ↓
4. ESO fetches secret from AWS Secrets Manager
   ↓
5. ESO creates/updates Kubernetes Secret
   ↓
6. Application mounts Secret as env var or volume
   ↓
7. ESO automatically refreshes on interval (default: 1h)
```

### Installation

**Helm Installation**:
```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets \
  external-secrets/external-secrets \
  --namespace external-secrets \
  --create-namespace \
  --set installCRDs=true
```

**Terraform**:
```hcl
resource "helm_release" "external_secrets" {
  name             = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  namespace        = "external-secrets"
  create_namespace = true

  set {
    name  = "installCRDs"
    value = "true"
  }

  # Enable service account for IRSA
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.external_secrets_irsa.iam_role_arn
  }
}

# IRSA role for External Secrets Operator
module "external_secrets_irsa" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name = "external-secrets-operator"

  role_policy_arns = {
    secrets_manager = aws_iam_policy.external_secrets_policy.arn
  }

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["external-secrets:external-secrets"]
    }
  }
}

# IAM policy for Secrets Manager access
resource "aws_iam_policy" "external_secrets_policy" {
  name        = "external-secrets-policy"
  description = "Policy for External Secrets Operator"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecrets"
        ]
        Resource = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:*"
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

### Configure SecretStore

**ClusterSecretStore** (cluster-wide):
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
```

**SecretStore** (namespace-scoped):
```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: production
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
```

### Create ExternalSecret

**Basic Example**:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-secrets
  namespace: production
spec:
  refreshInterval: 1h  # Sync every hour

  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore

  target:
    name: app-secrets-k8s  # Name of Kubernetes Secret to create
    creationPolicy: Owner  # ESO owns the secret
    template:
      type: Opaque
      metadata:
        labels:
          app: my-app

  data:
  # Single value
  - secretKey: database-password
    remoteRef:
      key: prod/db/password  # AWS Secrets Manager secret name

  # JSON field extraction
  - secretKey: db-username
    remoteRef:
      key: prod/database-credentials
      property: username  # Extract 'username' field from JSON

  - secretKey: db-password
    remoteRef:
      key: prod/database-credentials
      property: password
```

**Advanced Example with Template**:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-connection
  namespace: production
spec:
  refreshInterval: 15m  # More frequent sync

  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore

  target:
    name: db-connection-string
    creationPolicy: Owner
    template:
      type: Opaque
      data:
        # Template connection string from multiple secrets
        connection-string: |
          postgresql://{{ .username }}:{{ .password }}@{{ .host }}:{{ .port }}/{{ .database }}?sslmode=require

  data:
  - secretKey: username
    remoteRef:
      key: prod/database-credentials
      property: username

  - secretKey: password
    remoteRef:
      key: prod/database-credentials
      property: password

  - secretKey: host
    remoteRef:
      key: prod/database-endpoint

  - secretKey: port
    remoteRef:
      key: prod/database-port

  - secretKey: database
    remoteRef:
      key: prod/database-name
```

**Multiple Secrets Example**:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-all-secrets
  namespace: production
spec:
  refreshInterval: 1h

  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore

  target:
    name: app-all-secrets-k8s

  dataFrom:
  # Import all key-value pairs from a JSON secret
  - extract:
      key: prod/app-config

  # Import multiple secrets matching a pattern
  - find:
      name:
        regexp: "^prod/app/.*"
```

### Using ExternalSecrets in Pods

**Environment Variables**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: production
spec:
  template:
    spec:
      containers:
      - name: app
        image: my-app:v1.0.0
        envFrom:
        # Load all keys from secret as env vars
        - secretRef:
            name: app-secrets-k8s
        env:
        # Or individual env vars
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: app-secrets-k8s
              key: database-password
```

**Volume Mounts**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: production
spec:
  template:
    spec:
      containers:
      - name: app
        image: my-app:v1.0.0
        volumeMounts:
        - name: secrets
          mountPath: /etc/secrets
          readOnly: true

      volumes:
      - name: secrets
        secret:
          secretName: app-secrets-k8s
          items:
          - key: database-password
            path: db-password  # File: /etc/secrets/db-password
          - key: api-key
            path: api-key      # File: /etc/secrets/api-key
```

### Troubleshooting ExternalSecrets

**Check ExternalSecret Status**:
```bash
# View ExternalSecret
kubectl get externalsecret -n production

# Detailed status
kubectl describe externalsecret app-secrets -n production

# Check if Kubernetes Secret was created
kubectl get secret app-secrets-k8s -n production
```

**Common Issues**:

**Issue 1: Secret not syncing**
```bash
# Check ESO controller logs
kubectl logs -n external-secrets deployment/external-secrets -f

# Check IRSA permissions
kubectl get sa external-secrets -n external-secrets -o yaml | grep role-arn

# Verify IAM policy
aws iam get-policy-version \
  --policy-arn <policy-arn> \
  --version-id v1
```

**Issue 2: Authentication failure**
```bash
# Check SecretStore status
kubectl describe secretstore aws-secrets-manager -n production

# Test AWS Secrets Manager access
aws secretsmanager get-secret-value --secret-id prod/db/password
```

**Issue 3: Wrong secret value**
```bash
# View secret in AWS
aws secretsmanager get-secret-value --secret-id prod/db/password

# View Kubernetes secret
kubectl get secret app-secrets-k8s -n production -o jsonpath='{.data.database-password}' | base64 -d
```

---

## AWS Secrets Manager Integration

### Create Secrets in AWS Secrets Manager

**Simple String Secret**:
```bash
# Create secret
aws secretsmanager create-secret \
  --name prod/db/password \
  --description "Production database password" \
  --secret-string "MySecurePassword123!" \
  --kms-key-id alias/secrets-manager \
  --tags Key=Environment,Value=production Key=Application,Value=my-app

# Update secret
aws secretsmanager update-secret \
  --secret-id prod/db/password \
  --secret-string "NewPassword456!"
```

**JSON Secret**:
```bash
# Create JSON secret
aws secretsmanager create-secret \
  --name prod/database-credentials \
  --description "Production database credentials" \
  --secret-string '{
    "username": "dbadmin",
    "password": "SecurePass123!",
    "engine": "postgres",
    "host": "db.example.com",
    "port": 5432,
    "dbname": "production"
  }' \
  --kms-key-id alias/secrets-manager
```

**Terraform**:
```hcl
# KMS key for secrets encryption
resource "aws_kms_key" "secrets" {
  description             = "Secrets Manager encryption key"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = {
    Name = "secrets-manager-key"
  }
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/secrets-manager"
  target_key_id = aws_kms_key.secrets.key_id
}

# Simple string secret
resource "aws_secretsmanager_secret" "db_password" {
  name        = "prod/db/password"
  description = "Production database password"
  kms_key_id  = aws_kms_key.secrets.arn

  tags = {
    Environment = "production"
    Application = "my-app"
  }
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = var.db_password  # From Terraform variable
}

# JSON secret
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "prod/database-credentials"
  description = "Production database credentials"
  kms_key_id  = aws_kms_key.secrets.arn
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    dbname   = aws_db_instance.main.db_name
  })
}
```

### SSM Parameter Store Alternative

**When to Use SSM Parameter Store**:
- Lower cost (free for standard parameters)
- Simple key-value pairs
- Less frequent rotation needs
- Integration with Systems Manager

**Create Parameter**:
```bash
# Standard parameter (free)
aws ssm put-parameter \
  --name /prod/app/db-password \
  --type SecureString \
  --value "MyPassword123!" \
  --kms-key-id alias/aws/ssm

# Advanced parameter (paid, >4KB values)
aws ssm put-parameter \
  --name /prod/app/config \
  --type SecureString \
  --value "$(cat config.json)" \
  --tier Advanced
```

**SecretStore for SSM**:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-parameter-store
spec:
  provider:
    aws:
      service: ParameterStore
      region: us-west-2
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
```

**ExternalSecret for SSM**:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-config
  namespace: production
spec:
  refreshInterval: 1h

  secretStoreRef:
    name: aws-parameter-store
    kind: ClusterSecretStore

  target:
    name: app-config-k8s

  data:
  - secretKey: db-password
    remoteRef:
      key: /prod/app/db-password

  # Fetch all parameters with prefix
  dataFrom:
  - find:
      path: /prod/app/
```

---

## CSI Secrets Store Driver

### Overview

CSI Secrets Store Driver mounts secrets as volumes:
- Secrets sync'd to tmpfs volume
- Automatic rotation when secret updates
- Supports multiple backends
- **Limitation**: DaemonSet (no Fargate support)

### Installation

**Helm**:
```bash
# Install CSI driver
helm repo add secrets-store-csi-driver https://kubernetes-sigs.github.io/secrets-store-csi-driver/charts
helm install csi-secrets-store \
  secrets-store-csi-driver/secrets-store-csi-driver \
  --namespace kube-system \
  --set syncSecret.enabled=true \
  --set enableSecretRotation=true

# Install AWS provider
kubectl apply -f https://raw.githubusercontent.com/aws/secrets-store-csi-driver-provider-aws/main/deployment/aws-provider-installer.yaml
```

### Create SecretProviderClass

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: aws-secrets
  namespace: production
spec:
  provider: aws
  parameters:
    objects: |
      - objectName: "prod/db/password"
        objectType: "secretsmanager"
        objectAlias: "db-password"

      - objectName: "prod/database-credentials"
        objectType: "secretsmanager"
        jmesPath:
          - path: username
            objectAlias: db-username
          - path: password
            objectAlias: db-password

  # Sync to Kubernetes Secret (optional)
  secretObjects:
  - secretName: app-secrets-csi
    type: Opaque
    data:
    - objectName: db-password
      key: password
    - objectName: db-username
      key: username
```

### Using CSI Driver in Pods

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: production
spec:
  template:
    spec:
      serviceAccountName: my-app-sa  # Must have IRSA for Secrets Manager

      containers:
      - name: app
        image: my-app:v1.0.0
        volumeMounts:
        - name: secrets-store
          mountPath: /mnt/secrets
          readOnly: true
        env:
        # Option 1: Read from mounted file
        - name: DB_PASSWORD
          value: /mnt/secrets/db-password

        # Option 2: Use synced Kubernetes Secret
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: app-secrets-csi
              key: password

      volumes:
      - name: secrets-store
        csi:
          driver: secrets-store.csi.k8s.io
          readOnly: true
          volumeAttributes:
            secretProviderClass: aws-secrets
```

### Automatic Secret Rotation

**Enable Rotation**:
```yaml
# Install with rotation enabled
helm install csi-secrets-store \
  secrets-store-csi-driver/secrets-store-csi-driver \
  --set enableSecretRotation=true \
  --set rotationPollInterval=120s  # Check every 2 minutes
```

**How Rotation Works**:
1. CSI driver polls for secret changes (default: 2 minutes)
2. When secret changes in AWS, driver updates mounted file
3. Application must reload configuration to pick up changes
4. If using `syncSecret`, Kubernetes Secret also updated

**Application Reload Strategies**:

**Option 1: File watcher**:
```python
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class SecretReloader(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path == "/mnt/secrets/db-password":
            print("Secret updated, reloading configuration...")
            reload_config()

observer = Observer()
observer.schedule(SecretReloader(), path="/mnt/secrets", recursive=False)
observer.start()
```

**Option 2: Periodic reload**:
```python
import time
import hashlib

def get_secret_hash():
    with open("/mnt/secrets/db-password") as f:
        return hashlib.md5(f.read().encode()).hexdigest()

last_hash = get_secret_hash()

while True:
    time.sleep(60)  # Check every minute
    current_hash = get_secret_hash()
    if current_hash != last_hash:
        print("Secret changed, reloading...")
        reload_config()
        last_hash = current_hash
```

**Option 3: Restart pod** (if app doesn't support reload):
```yaml
# Deployment with rollout on secret change
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    metadata:
      annotations:
        # Update this annotation when secret changes
        secret-version: "v2"
    spec:
      # ... pod spec
```

---

## Secret Rotation

### Automatic Rotation with AWS Secrets Manager

**Enable Rotation**:
```hcl
# Lambda function for rotation
resource "aws_secretsmanager_secret_rotation" "db_password" {
  secret_id           = aws_secretsmanager_secret.db_password.id
  rotation_lambda_arn = aws_lambda_function.rotate_secret.arn

  rotation_rules {
    automatically_after_days = 30
  }
}

# Lambda function (example for RDS)
resource "aws_lambda_function" "rotate_secret" {
  filename      = "lambda-rotation.zip"
  function_name = "rotate-db-password"
  role          = aws_iam_role.lambda_rotation.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  environment {
    variables = {
      SECRETS_MANAGER_ENDPOINT = "https://secretsmanager.${var.region}.amazonaws.com"
    }
  }
}
```

**Rotation Function Template**:
```python
import boto3
import json
import os

def handler(event, context):
    """Lambda rotation function"""

    service_client = boto3.client('secretsmanager')

    # Get secret ARN and token
    arn = event['SecretId']
    token = event['ClientRequestToken']
    step = event['Step']

    # Four-step rotation process
    if step == "createSecret":
        create_secret(service_client, arn, token)
    elif step == "setSecret":
        set_secret(service_client, arn, token)
    elif step == "testSecret":
        test_secret(service_client, arn, token)
    elif step == "finishSecret":
        finish_secret(service_client, arn, token)
    else:
        raise ValueError("Invalid step parameter")

def create_secret(client, arn, token):
    """Generate new password"""
    # Generate new password
    new_password = generate_password()

    # Store pending version
    client.put_secret_value(
        SecretId=arn,
        ClientRequestToken=token,
        SecretString=json.dumps({"password": new_password}),
        VersionStages=['AWSPENDING']
    )

def set_secret(client, arn, token):
    """Update database with new password"""
    # Get new password
    pending = client.get_secret_value(
        SecretId=arn,
        VersionId=token,
        VersionStage='AWSPENDING'
    )
    new_password = json.loads(pending['SecretString'])['password']

    # Update database user password
    db_client = boto3.client('rds')
    db_client.modify_db_instance(
        DBInstanceIdentifier='my-db',
        MasterUserPassword=new_password
    )

def test_secret(client, arn, token):
    """Test new password works"""
    # Get new password
    pending = client.get_secret_value(
        SecretId=arn,
        VersionId=token,
        VersionStage='AWSPENDING'
    )

    # Test database connection with new password
    # ... connection test ...

def finish_secret(client, arn, token):
    """Finalize rotation"""
    # Move AWSCURRENT stage to new version
    client.update_secret_version_stage(
        SecretId=arn,
        VersionStage='AWSCURRENT',
        MoveToVersionId=token,
        RemoveFromVersionId=get_current_version(client, arn)
    )
```

### Manual Rotation Process

**Update Secret in AWS**:
```bash
# Update secret value
aws secretsmanager update-secret \
  --secret-id prod/db/password \
  --secret-string "NewPassword123!"

# Verify update
aws secretsmanager get-secret-value \
  --secret-id prod/db/password
```

**ExternalSecret automatically syncs** (within refresh interval):
```bash
# Check sync status
kubectl describe externalsecret app-secrets -n production

# Force immediate sync (delete and recreate)
kubectl delete externalsecret app-secrets -n production
kubectl apply -f externalsecret.yaml
```

**Restart pods** (if needed):
```bash
# Rolling restart
kubectl rollout restart deployment/my-app -n production

# Wait for rollout
kubectl rollout status deployment/my-app -n production
```

---

## Encryption at Rest

### Kubernetes Secrets Encryption

**Enable KMS Encryption** (at cluster creation):
```hcl
module "eks" {
  source = "terraform-aws-modules/eks/aws"

  cluster_encryption_config = {
    resources        = ["secrets"]
    provider_key_arn = aws_kms_key.eks.arn
  }
}

resource "aws_kms_key" "eks" {
  description             = "EKS secrets encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true
}
```

**Verify Encryption**:
```bash
# Check cluster encryption config
aws eks describe-cluster \
  --name production-cluster \
  --query 'cluster.encryptionConfig'

# Verify secret is encrypted in etcd
kubectl get secret app-secrets-k8s -n production -o yaml
```

### AWS Secrets Manager Encryption

**Always Encrypted**:
- Secrets Manager encrypts all secrets at rest
- Uses AWS KMS keys (default or custom)
- Encryption in transit via TLS

**Custom KMS Key**:
```hcl
resource "aws_kms_key" "secrets_manager" {
  description             = "Secrets Manager encryption key"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Secrets Manager"
        Effect = "Allow"
        Principal = {
          Service = "secretsmanager.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_secretsmanager_secret" "encrypted" {
  name       = "prod/encrypted-secret"
  kms_key_id = aws_kms_key.secrets_manager.arn
}
```

---

## Audit and Monitoring

### CloudTrail Audit

**Enable CloudTrail for Secrets Manager**:
```hcl
resource "aws_cloudtrail" "main" {
  name                          = "secrets-audit-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true

  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type = "AWS::SecretsManager::Secret"
      values = ["arn:aws:secretsmanager:*:${data.aws_caller_identity.current.account_id}:secret:*"]
    }
  }
}
```

**Query Secret Access**:
```bash
# Find who accessed a secret
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=prod/db/password \
  --max-results 50

# Filter by event name
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue

# Export to file
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=prod/db/password \
  --query 'Events[*].[EventTime,Username,EventName,Resources]' \
  --output table > secret-access-audit.txt
```

### Kubernetes Audit Logs

**Query Secret Access in Kubernetes**:
```bash
# Find secret access in audit logs
aws logs filter-log-events \
  --log-group-name /aws/eks/production-cluster/cluster \
  --filter-pattern '{ $.objectRef.resource = "secrets" && $.verb = "get" }'

# Find secret modifications
aws logs filter-log-events \
  --log-group-name /aws/eks/production-cluster/cluster \
  --filter-pattern '{ $.objectRef.resource = "secrets" && ($.verb = "create" || $.verb = "update" || $.verb = "patch") }'
```

**CloudWatch Insights Query**:
```sql
fields @timestamp, user.username, verb, objectRef.name, objectRef.namespace
| filter objectRef.resource = "secrets"
| filter verb = "get" or verb = "list"
| sort @timestamp desc
| limit 100
```

### Alerting on Secret Access

**CloudWatch Alarm**:
```hcl
resource "aws_cloudwatch_log_metric_filter" "secret_access" {
  name           = "secrets-access-count"
  log_group_name = "/aws/eks/production-cluster/cluster"
  pattern        = "{ $.objectRef.resource = \"secrets\" && $.verb = \"get\" }"

  metric_transformation {
    name      = "SecretAccessCount"
    namespace = "EKS/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "excessive_secret_access" {
  alarm_name          = "excessive-secret-access"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "SecretAccessCount"
  namespace           = "EKS/Security"
  period              = "300"
  statistic           = "Sum"
  threshold           = "100"
  alarm_description   = "Alert on excessive secret access"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}
```

### Secret Usage Tracking

**Tag Secrets**:
```hcl
resource "aws_secretsmanager_secret" "tagged" {
  name = "prod/app/api-key"

  tags = {
    Environment  = "production"
    Application  = "my-app"
    Owner        = "platform-team"
    CostCenter   = "engineering"
    Compliance   = "SOC2"
    LastRotated  = "2025-11-27"
  }
}
```

**Generate Secret Inventory**:
```bash
# List all secrets with tags
aws secretsmanager list-secrets \
  --query 'SecretList[*].[Name,Tags]' \
  --output table

# Export to CSV
aws secretsmanager list-secrets \
  --query 'SecretList[*].[Name,LastRotatedDate,LastAccessedDate]' \
  --output text > secrets-inventory.csv
```

---

## Best Practices

### 1. Never Hardcode Secrets

**Bad**:
```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    env:
    - name: DB_PASSWORD
      value: "MyPassword123!"  # ❌ Never do this
```

**Good**:
```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    env:
    - name: DB_PASSWORD
      valueFrom:
        secretKeyRef:
          name: app-secrets
          key: db-password  # ✅ Reference secret
```

### 2. Use Separate Secrets Per Environment

```
prod/app/db-password       # Production
staging/app/db-password    # Staging
dev/app/db-password        # Development
```

**Terraform**:
```hcl
resource "aws_secretsmanager_secret" "db_password" {
  for_each = toset(["prod", "staging", "dev"])

  name        = "${each.key}/app/db-password"
  description = "${title(each.key)} database password"
}
```

### 3. Rotate Regularly

- **Passwords**: 30-90 days
- **API keys**: 90-180 days
- **Certificates**: Before expiration
- **Service account keys**: 90 days

### 4. Principle of Least Privilege

**Bad** - Access to all secrets:
```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": "*"
}
```

**Good** - Scoped access:
```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": "arn:aws:secretsmanager:us-west-2:123456789012:secret:prod/app/*"
}
```

### 5. Audit Regularly

**Monthly Review**:
```bash
# List secrets not accessed in 90 days
aws secretsmanager list-secrets \
  --filters Key=name,Values=prod/* \
  --query 'SecretList[?LastAccessedDate < `2025-08-27`].[Name,LastAccessedDate]'

# List secrets not rotated in 90 days
aws secretsmanager list-secrets \
  --filters Key=name,Values=prod/* \
  --query 'SecretList[?LastRotatedDate < `2025-08-27`].[Name,LastRotatedDate]'
```

### 6. Use Immutable Secrets

**Versioning**:
```bash
# Create versioned secret
aws secretsmanager create-secret \
  --name prod/app/api-key-v2 \
  --secret-string "NewAPIKey"

# Update application to use new version
# Then delete old version
aws secretsmanager delete-secret \
  --secret-id prod/app/api-key-v1 \
  --recovery-window-in-days 30
```

### 7. Monitor and Alert

- **Alert on secret access** from unexpected sources
- **Track rotation failures**
- **Monitor access patterns** for anomalies
- **Set up notifications** for manual rotation reminders

### 8. Document Secret Ownership

**README.md**:
```markdown
# Secrets Inventory

| Secret Name | Owner | Purpose | Rotation | Last Updated |
|-------------|-------|---------|----------|--------------|
| prod/db/password | Platform Team | RDS password | Auto (30d) | 2025-11-27 |
| prod/api/stripe | Payments Team | Stripe API key | Manual (90d) | 2025-10-15 |
| prod/app/jwt-key | Security Team | JWT signing | Manual (180d) | 2025-09-01 |
```

### 9. Test Secret Rotation

```bash
# Test rotation function
aws lambda invoke \
  --function-name rotate-db-password \
  --payload '{"SecretId":"prod/db/password","Step":"testSecret","ClientRequestToken":"test-token"}' \
  response.json

# Verify rotation doesn't break application
kubectl rollout restart deployment/my-app -n production
kubectl rollout status deployment/my-app -n production
```

### 10. Backup and Disaster Recovery

**Replicate Critical Secrets**:
```hcl
resource "aws_secretsmanager_secret" "replicated" {
  name = "prod/critical-secret"

  replica {
    region     = "us-east-1"
    kms_key_id = aws_kms_key.east.arn
  }

  replica {
    region     = "eu-west-1"
    kms_key_id = aws_kms_key.eu.arn
  }
}
```

---

**Summary**: Use External Secrets Operator for production workloads with AWS Secrets Manager as the backend. Enable automatic rotation, audit all access, and follow least privilege principles.
