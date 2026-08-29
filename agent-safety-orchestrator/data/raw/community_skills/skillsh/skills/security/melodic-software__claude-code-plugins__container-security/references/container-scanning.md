# Container Scanning Reference

## Overview

This reference covers container image vulnerability scanning, registry integration, and CI/CD pipeline configurations for comprehensive container security.

## Scanner Comparison

| Scanner | Type | SBOM | Secrets | IaC | License |
| --- | --- | --- | --- | --- | --- |
| **Trivy** | All-in-one | Yes | Yes | Yes | Apache 2.0 |
| **Grype** | Vulnerabilities | No | No | No | Apache 2.0 |
| **Clair** | Vulnerabilities | No | No | No | Apache 2.0 |
| **Snyk** | All-in-one | Yes | No | Yes | Commercial |
| **Anchore** | All-in-one | Yes | No | Yes | Apache 2.0 |

## Trivy Configuration

### Complete Trivy Configuration

```yaml
# trivy.yaml
scan:
  # Vulnerability scanning
  scanners:
    - vuln
    - secret
    - misconfig

  # Severity filter
  severity:
    - CRITICAL
    - HIGH
    - MEDIUM

  # Ignore unfixed vulnerabilities
  ignore-unfixed: false

  # Custom vulnerability database
  # db-repository: ghcr.io/aquasecurity/trivy-db

vulnerability:
  # Vulnerability types
  type:
    - os
    - library

secret:
  # Custom secret patterns
  config: trivy-secret.yaml

misconfiguration:
  # Terraform, CloudFormation, Kubernetes, Dockerfile
  scanners:
    - dockerfile
    - kubernetes

cache:
  # Cache directory
  dir: /tmp/trivy-cache
  # Cache TTL
  ttl: 24h

# Output format
format: table

# Exit code on findings
exit-code: 1

# Ignore specific vulnerabilities
ignorefile: .trivyignore
```

### Trivy Secret Detection Configuration

```yaml
# trivy-secret.yaml
rules:
  - id: custom-api-key
    category: general
    title: Custom API Key Pattern
    severity: HIGH
    regex: 'CUSTOM_API_KEY[=:]\s*["\']?([A-Za-z0-9_-]{32,})["\']?'

  - id: internal-token
    category: general
    title: Internal Service Token
    severity: CRITICAL
    regex: 'INTERNAL_TOKEN[=:]\s*["\']?([A-Za-z0-9_-]{40,})["\']?'

allow-rules:
  - id: test-secrets
    description: Allow test secrets
    regex: '(?i)(test|example|sample|dummy)'

  - id: environment-placeholder
    description: Allow environment variable placeholders
    regex: '\$\{[A-Z_]+\}'
```

### Trivy Ignore File

```yaml
# .trivyignore.yaml
vulnerabilities:
  # Ignore specific CVE (with justification)
  - id: CVE-2023-12345
    paths:
      - "node_modules/lodash"
    statement: "Not exploitable in our usage - tracked in JIRA-123"
    expires: 2024-06-01

  # Ignore by package
  - id: CVE-2023-67890
    paths:
      - "usr/lib/python3.11/site-packages/requests"
    statement: "Mitigated by network policy - no external access"

misconfigurations:
  # Ignore specific misconfig check
  - id: DS002
    paths:
      - "**/Dockerfile.dev"
    statement: "Development Dockerfile, not used in production"

secrets:
  # Ignore false positive
  - id: generic-api-key
    paths:
      - "test/**"
      - "docs/**"
    statement: "Test and documentation files with example keys"
```

## CI/CD Pipeline Integration

### GitHub Actions

```yaml
name: Container Security Scan

on:
  push:
    branches: [main]
    paths:
      - 'Dockerfile'
      - 'docker/**'
      - '.github/workflows/container-scan.yml'
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      security-events: write

    steps:
      - uses: actions/checkout@v5

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=
            type=ref,event=branch
            type=semver,pattern={{version}}

      - name: Build image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          load: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          ignore-unfixed: true
          vuln-type: 'os,library'

      - name: Upload Trivy scan results to Security tab
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: 'trivy-results.sarif'

      - name: Run Trivy in table format (for PR comment)
        if: github.event_name == 'pull_request'
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: 'table'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

      - name: Generate SBOM
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: 'cyclonedx'
          output: 'sbom.json'

      - name: Upload SBOM artifact
        uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: sbom.json

      - name: Run Dockle linter
        uses: erzz/dockle-action@v1
        with:
          image: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          failure-threshold: high
          exit-code: '1'

      - name: Push image (on main branch only)
        if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request'
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}

      - name: Sign image with Cosign
        if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request'
        uses: sigstore/cosign-installer@v3

      - name: Sign the published image
        if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request'
        env:
          COSIGN_EXPERIMENTAL: true
        run: |
          cosign sign --yes ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}@${{ steps.meta.outputs.digest }}
```

### GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - build
  - scan
  - push

variables:
  DOCKER_TLS_CERTDIR: "/certs"
  IMAGE_TAG: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker build -t $IMAGE_TAG .
    - docker save $IMAGE_TAG -o image.tar
  artifacts:
    paths:
      - image.tar
    expire_in: 1 hour

trivy-scan:
  stage: scan
  image:
    name: aquasec/trivy:latest
    entrypoint: [""]
  script:
    - trivy image --input image.tar
        --format sarif
        --output trivy-results.sarif
        --severity CRITICAL,HIGH
        --exit-code 1
  artifacts:
    reports:
      sast: trivy-results.sarif
    paths:
      - trivy-results.sarif
  allow_failure: false

grype-scan:
  stage: scan
  image:
    name: anchore/grype:latest
    entrypoint: [""]
  script:
    - grype image.tar
        --fail-on high
        --output sarif > grype-results.sarif
  artifacts:
    paths:
      - grype-results.sarif
  allow_failure: true

sbom-generate:
  stage: scan
  image:
    name: aquasec/trivy:latest
    entrypoint: [""]
  script:
    - trivy image --input image.tar
        --format cyclonedx
        --output sbom.json
  artifacts:
    paths:
      - sbom.json

push:
  stage: push
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker load -i image.tar
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker push $IMAGE_TAG
  only:
    - main
  needs:
    - job: trivy-scan
      artifacts: false
```

### Azure DevOps

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
      - main
  paths:
    include:
      - Dockerfile
      - docker/**

pool:
  vmImage: 'ubuntu-latest'

variables:
  containerRegistry: 'myacr.azurecr.io'
  imageName: 'myapp'
  tag: '$(Build.BuildId)'

stages:
  - stage: Build
    jobs:
      - job: BuildAndScan
        steps:
          - task: Docker@2
            displayName: Build image
            inputs:
              command: build
              repository: $(imageName)
              dockerfile: Dockerfile
              tags: $(tag)

          - script: |
              curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
            displayName: Install Trivy

          - script: |
              trivy image \
                --format sarif \
                --output trivy-results.sarif \
                --severity CRITICAL,HIGH \
                --exit-code 0 \
                $(imageName):$(tag)
            displayName: Trivy Scan

          - task: PublishBuildArtifacts@1
            inputs:
              pathToPublish: 'trivy-results.sarif'
              artifactName: 'TrivyResults'

          - script: |
              trivy image \
                --exit-code 1 \
                --severity CRITICAL \
                $(imageName):$(tag)
            displayName: Fail on Critical Vulnerabilities

          - task: Docker@2
            displayName: Push image
            condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
            inputs:
              command: push
              containerRegistry: $(containerRegistry)
              repository: $(imageName)
              tags: $(tag)
```

## Registry Integration

### Harbor with Trivy

```yaml
# Harbor configuration for automatic scanning
# In Harbor UI: Configuration > System Settings

# Scan settings
scanners:
  trivy:
    enabled: true
    scanner_adapter_url: http://trivy-adapter:8080

# Vulnerability policy
vulnerability_policy:
  # Block pull for images with critical vulnerabilities
  prevent_vulnerable: true
  severity: Critical

# Scan on push
scan_on_push: true
```

### AWS ECR Image Scanning

```bash
# Enable scanning on push
aws ecr put-image-scanning-configuration \
    --repository-name myapp \
    --image-scanning-configuration scanOnPush=true

# Get scan findings
aws ecr describe-image-scan-findings \
    --repository-name myapp \
    --image-id imageTag=latest \
    --query 'imageScanFindings.findings[?severity==`CRITICAL` || severity==`HIGH`]'

# Lifecycle policy to clean up vulnerable images
aws ecr put-lifecycle-policy \
    --repository-name myapp \
    --lifecycle-policy-text '{
        "rules": [
            {
                "rulePriority": 1,
                "description": "Delete images with critical vulnerabilities older than 7 days",
                "selection": {
                    "tagStatus": "any",
                    "countType": "sinceImagePushed",
                    "countUnit": "days",
                    "countNumber": 7
                },
                "action": {
                    "type": "expire"
                }
            }
        ]
    }'
```

### Google Artifact Registry with Binary Authorization

```yaml
# Binary Authorization policy
admissionWhitelistPatterns:
  - namePattern: gcr.io/google-samples/*
  - namePattern: k8s.gcr.io/*

defaultAdmissionRule:
  evaluationMode: REQUIRE_ATTESTATION
  enforcementMode: ENFORCED_BLOCK_AND_AUDIT_LOG
  requireAttestationsBy:
    - projects/my-project/attestors/security-scanner
    - projects/my-project/attestors/qa-attestor

clusterAdmissionRules:
  us-central1-a.production:
    evaluationMode: REQUIRE_ATTESTATION
    enforcementMode: ENFORCED_BLOCK_AND_AUDIT_LOG
    requireAttestationsBy:
      - projects/my-project/attestors/security-scanner
      - projects/my-project/attestors/prod-release
```

## Image Signing with Cosign

### Keyless Signing (Recommended)

```bash
# Install cosign
brew install cosign  # macOS
# or
go install github.com/sigstore/cosign/v2/cmd/cosign@latest

# Keyless sign (uses OIDC)
COSIGN_EXPERIMENTAL=1 cosign sign myregistry/myimage:v1.0.0

# Verify keyless signature
COSIGN_EXPERIMENTAL=1 cosign verify myregistry/myimage:v1.0.0

# Verify with specific issuer and subject
COSIGN_EXPERIMENTAL=1 cosign verify \
    --certificate-identity=user@example.com \
    --certificate-oidc-issuer=https://accounts.google.com \
    myregistry/myimage:v1.0.0
```

### Key-Based Signing

```bash
# Generate key pair
cosign generate-key-pair

# Sign image with private key
cosign sign --key cosign.key myregistry/myimage:v1.0.0

# Verify with public key
cosign verify --key cosign.pub myregistry/myimage:v1.0.0

# Attach SBOM as attestation
cosign attest --key cosign.key \
    --predicate sbom.json \
    --type cyclonedx \
    myregistry/myimage:v1.0.0

# Verify SBOM attestation
cosign verify-attestation --key cosign.pub \
    --type cyclonedx \
    myregistry/myimage:v1.0.0
```

### Kubernetes Policy Enforcement

```yaml
# Kyverno policy for signature verification
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signature
spec:
  validationFailureAction: Enforce
  background: false
  rules:
    - name: verify-signature
      match:
        any:
          - resources:
              kinds:
                - Pod
      verifyImages:
        - imageReferences:
            - "myregistry/*"
          attestors:
            - entries:
                - keyless:
                    subject: "user@example.com"
                    issuer: "https://accounts.google.com"
                    rekor:
                      url: https://rekor.sigstore.dev
```

## Vulnerability Remediation Automation

### Automatic Base Image Updates

```yaml
# Renovate configuration for base image updates
# renovate.json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "docker": {
    "fileMatch": ["(^|/)Dockerfile$", "(^|/)Dockerfile\\.[a-zA-Z]+$"],
    "pinDigests": true
  },
  "packageRules": [
    {
      "matchDatasources": ["docker"],
      "matchPackagePatterns": ["*"],
      "groupName": "Docker images",
      "schedule": ["after 6am on monday"]
    },
    {
      "matchDatasources": ["docker"],
      "matchPackageNames": ["node", "python", "golang"],
      "matchUpdateTypes": ["patch", "minor"],
      "automerge": true
    }
  ],
  "vulnerabilityAlerts": {
    "enabled": true,
    "labels": ["security"]
  }
}
```

### Dependabot for Container Images

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: docker
    directory: "/"
    schedule:
      interval: daily
    open-pull-requests-limit: 10
    labels:
      - dependencies
      - docker
    reviewers:
      - security-team
    commit-message:
      prefix: "docker"
      include: "scope"
```

## Reporting and Dashboards

### Aggregated Scanning Report Script

```csharp
// Aggregate container vulnerability scans into a report
using System.Text;
using System.Text.Json.Nodes;

/// <summary>
/// Represents a vulnerability finding from SARIF scan output.
/// </summary>
public sealed record Finding(string RuleId, string Message, JsonObject? Location);

/// <summary>
/// Aggregated findings by severity level.
/// </summary>
public sealed record ScanFindings
{
    public List<Finding> Critical { get; init; } = [];
    public List<Finding> High { get; init; } = [];
    public List<Finding> Medium { get; init; } = [];
    public List<Finding> Low { get; init; } = [];

    public int Total => Critical.Count + High.Count + Medium.Count + Low.Count;
}

/// <summary>
/// Container scan report generator for Trivy SARIF output.
/// </summary>
public static class ContainerScanReporter
{
    private static readonly Dictionary<string, string> SeverityMap = new()
    {
        ["error"] = "critical",
        ["warning"] = "high",
        ["note"] = "medium",
        ["none"] = "low"
    };

    /// <summary>
    /// Parse Trivy SARIF output file.
    /// </summary>
    public static async Task<ScanFindings> ParseTrivySarifAsync(string sarifPath, CancellationToken ct = default)
    {
        var json = await File.ReadAllTextAsync(sarifPath, ct);
        var data = JsonNode.Parse(json)?.AsObject()
            ?? throw new InvalidOperationException("Invalid SARIF JSON");

        var findings = new ScanFindings();

        foreach (var run in data["runs"]?.AsArray() ?? [])
        {
            foreach (var result in run?["results"]?.AsArray() ?? [])
            {
                var level = result?["level"]?.GetValue<string>() ?? "warning";
                var ruleId = result?["ruleId"]?.GetValue<string>() ?? "unknown";
                var message = result?["message"]?["text"]?.GetValue<string>() ?? "";
                var location = result?["locations"]?.AsArray().FirstOrDefault()?.AsObject();

                var finding = new Finding(ruleId, message, location);
                var severity = SeverityMap.GetValueOrDefault(level, "medium");

                switch (severity)
                {
                    case "critical": findings.Critical.Add(finding); break;
                    case "high": findings.High.Add(finding); break;
                    case "medium": findings.Medium.Add(finding); break;
                    case "low": findings.Low.Add(finding); break;
                }
            }
        }

        return findings;
    }

    /// <summary>
    /// Generate markdown report from scan findings.
    /// </summary>
    public static string GenerateReport(string imageName, ScanFindings findings)
    {
        var sb = new StringBuilder();

        sb.AppendLine("# Container Security Scan Report");
        sb.AppendLine();
        sb.AppendLine($"**Image:** {imageName}");
        sb.AppendLine($"**Scan Date:** {DateTime.UtcNow:O}");
        sb.AppendLine($"**Total Findings:** {findings.Total}");
        sb.AppendLine();
        sb.AppendLine("## Summary");
        sb.AppendLine();
        sb.AppendLine("| Severity | Count |");
        sb.AppendLine("|----------|-------|");
        sb.AppendLine($"| Critical | {findings.Critical.Count} |");
        sb.AppendLine($"| High | {findings.High.Count} |");
        sb.AppendLine($"| Medium | {findings.Medium.Count} |");
        sb.AppendLine($"| Low | {findings.Low.Count} |");
        sb.AppendLine();

        AppendFindings(sb, "Critical Findings", findings.Critical);
        AppendFindings(sb, "High Findings", findings.High);

        return sb.ToString();
    }

    private static void AppendFindings(StringBuilder sb, string header, List<Finding> findings)
    {
        sb.AppendLine($"## {header}");
        sb.AppendLine();
        foreach (var finding in findings.Take(10))
        {
            var message = finding.Message.Length > 100
                ? finding.Message[..100] + "..."
                : finding.Message;
            sb.AppendLine($"- **{finding.RuleId}**: {message}");
        }
        sb.AppendLine();
    }
}

// CLI usage example
public static class Program
{
    public static async Task Main(string[] args)
    {
        if (args.Length < 2)
        {
            Console.WriteLine("Usage: report <image-name> <sarif-file>");
            Environment.Exit(1);
        }

        var imageName = args[0];
        var sarifPath = args[1];

        var findings = await ContainerScanReporter.ParseTrivySarifAsync(sarifPath);
        var report = ContainerScanReporter.GenerateReport(imageName, findings);

        Console.WriteLine(report);
    }
}
```

## Related Documentation

- **Parent Skill**: See `../SKILL.md` for container security overview
- **Dockerfile Security**: See `dockerfile-security.md` for image hardening
- **Kubernetes Security**: See `kubernetes-security.md` for K8s configurations

---

**Last Updated:** 2025-12-26
