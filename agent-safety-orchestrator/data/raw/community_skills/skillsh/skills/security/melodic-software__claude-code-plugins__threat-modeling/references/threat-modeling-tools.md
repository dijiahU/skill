# Threat Modeling Tools

Tools and automation for threat modeling as code, including pytm, Threagile, and Microsoft Threat Modeling Tool.

## Tool Comparison

| Tool | Type | Output | Best For |
|------|------|--------|----------|
| **pytm** | Python library | DFD, reports | Python shops, automation |
| **Threagile** | YAML + CLI | Reports, risk tracking | GitOps, CI/CD integration |
| **MS TMT** | GUI application | Diagrams, reports | Windows users, visual modeling |
| **OWASP Threat Dragon** | Web app | DFD, threats | Browser-based, collaboration |
| **IriusRisk** | SaaS platform | Full lifecycle | Enterprise, compliance |

## pytm - Pythonic Threat Modeling

pytm enables threat modeling as code in Python.

### Installation

```bash
pip install pytm
# For diagram generation
pip install graphviz
# Or via conda
conda install -c conda-forge graphviz
```

### Basic Example

> **Note:** pytm is a Python-specific library. The following shows an equivalent .NET approach for threat modeling as code.

```csharp
using System.Collections.Frozen;
using System.Text;

// Enumerations for classification and element types
public enum Classification { Public, Internal, Confidential, Restricted }
public enum ElementType { Actor, Server, Process, Datastore, ExternalEntity }

// Trust boundary definition
public sealed record TrustBoundary(string Name);

// Base element for all model components
public sealed record ModelElement
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    public required ElementType Type { get; init; }
    public TrustBoundary? Boundary { get; init; }
    public string? OperatingSystem { get; init; }
    public bool IsHardened { get; init; }
    public bool ImplementsAuthentication { get; init; }
    public string? AuthenticationScheme { get; init; }
    public bool SanitizesInput { get; init; }
    public bool EncodesOutput { get; init; }
    public bool IsEncryptedAtRest { get; init; }
    public bool HasAccessControl { get; init; }
    public bool StoresCredentials { get; init; }
    public bool StoresPII { get; init; }
    public bool ImplementsPCI { get; init; }
    public Classification Classification { get; init; } = Classification.Internal;
    public string? Protocol { get; init; }
    public bool IsAdmin { get; init; }
}

// Data flow between elements
public sealed record DataFlow
{
    public required ModelElement Source { get; init; }
    public required ModelElement Target { get; init; }
    public required string Name { get; init; }
    public string Protocol { get; init; } = "HTTPS";
    public bool IsEncrypted { get; init; }
    public bool AuthenticatesSource { get; init; }
    public bool AuthenticatesDestination { get; init; }
    public string? Data { get; init; }
    public string? Note { get; init; }
}

// Threat model definition
public sealed class ThreatModel(string name)
{
    public string Name { get; } = name;
    public string Description { get; set; } = "";
    private readonly List<TrustBoundary> _boundaries = [];
    private readonly List<ModelElement> _elements = [];
    private readonly List<DataFlow> _dataFlows = [];

    public IReadOnlyList<TrustBoundary> Boundaries => _boundaries;
    public IReadOnlyList<ModelElement> Elements => _elements;
    public IReadOnlyList<DataFlow> DataFlows => _dataFlows;

    public TrustBoundary AddBoundary(string name)
    {
        var boundary = new TrustBoundary(name);
        _boundaries.Add(boundary);
        return boundary;
    }

    public ModelElement AddElement(ModelElement element)
    {
        _elements.Add(element);
        return element;
    }

    public DataFlow AddDataFlow(DataFlow flow)
    {
        _dataFlows.Add(flow);
        return flow;
    }

    public string GenerateDfd()
    {
        var sb = new StringBuilder();
        sb.AppendLine("digraph ThreatModel {");
        sb.AppendLine("  rankdir=LR;");

        // Group elements by boundary
        foreach (var boundary in _boundaries)
        {
            sb.AppendLine($"  subgraph cluster_{boundary.Name.Replace(" ", "_")} {{");
            sb.AppendLine($"    label=\"{boundary.Name}\";");

            foreach (var element in _elements.Where(e => e.Boundary == boundary))
            {
                var shape = element.Type switch
                {
                    ElementType.Actor => "box",
                    ElementType.Datastore => "cylinder",
                    ElementType.Process => "ellipse",
                    _ => "rectangle"
                };
                sb.AppendLine($"    {element.Id} [label=\"{element.Name}\" shape={shape}];");
            }
            sb.AppendLine("  }");
        }

        // Add data flows
        foreach (var flow in _dataFlows)
        {
            var style = flow.IsEncrypted ? "solid" : "dashed";
            sb.AppendLine($"  {flow.Source.Id} -> {flow.Target.Id} [label=\"{flow.Name}\" style={style}];");
        }

        sb.AppendLine("}");
        return sb.ToString();
    }
}

// Example: E-Commerce Application Threat Model
public static class ECommerceThreatModel
{
    public static ThreatModel Create()
    {
        var tm = new ThreatModel("E-Commerce Application")
        {
            Description = "Online shopping platform threat model"
        };

        // Define boundaries
        var internet = tm.AddBoundary("Internet");
        var dmz = tm.AddBoundary("DMZ");
        var internalNet = tm.AddBoundary("Internal Network");
        var databaseZone = tm.AddBoundary("Database Zone");

        // External entities
        var customer = tm.AddElement(new ModelElement
        {
            Id = "customer", Name = "Customer", Type = ElementType.Actor,
            Boundary = internet, IsAdmin = false
        });

        // DMZ components
        var webApp = tm.AddElement(new ModelElement
        {
            Id = "web_app", Name = "Web Application", Type = ElementType.Server,
            Boundary = dmz, OperatingSystem = "Linux", IsHardened = true,
            ImplementsAuthentication = true, AuthenticationScheme = "OAuth2",
            SanitizesInput = true, EncodesOutput = true
        });

        // Internal components
        var apiGateway = tm.AddElement(new ModelElement
        {
            Id = "api_gateway", Name = "API Gateway", Type = ElementType.Server,
            Boundary = internalNet, ImplementsAuthentication = true,
            AuthenticationScheme = "JWT", SanitizesInput = true
        });

        var paymentService = tm.AddElement(new ModelElement
        {
            Id = "payment_svc", Name = "Payment Service", Type = ElementType.Process,
            Boundary = internalNet, ImplementsAuthentication = true,
            SanitizesInput = true, ImplementsPCI = true, IsEncryptedAtRest = true
        });

        // Database components
        var paymentVault = tm.AddElement(new ModelElement
        {
            Id = "payment_vault", Name = "Payment Vault", Type = ElementType.Datastore,
            Boundary = databaseZone, IsEncryptedAtRest = true, HasAccessControl = true,
            StoresPII = true, StoresCredentials = true, ImplementsPCI = true,
            Classification = Classification.Restricted
        });

        // Data flows
        tm.AddDataFlow(new DataFlow
        {
            Source = customer, Target = webApp, Name = "HTTPS Request",
            Protocol = "HTTPS", IsEncrypted = true, AuthenticatesDestination = true
        });

        tm.AddDataFlow(new DataFlow
        {
            Source = webApp, Target = apiGateway, Name = "API Call",
            Protocol = "HTTPS", IsEncrypted = true, AuthenticatesSource = true
        });

        tm.AddDataFlow(new DataFlow
        {
            Source = paymentService, Target = paymentVault, Name = "Payment Data",
            Protocol = "PostgreSQL", IsEncrypted = true, Data = "Tokenized payment info"
        });

        return tm;
    }
}
```

### Running pytm

```bash
# Generate DFD diagram
python tm.py --dfd | dot -Tpng -o dfd.png

# Generate sequence diagram
python tm.py --seq | java -jar plantuml.jar -pipe > seq.png

# Generate threat report
python tm.py --report report.html

# Generate JSON output
python tm.py --json > threats.json

# List all identified threats
python tm.py --list
```

### Custom Threat Rules

> **Note:** The following shows a .NET equivalent for defining custom threat rules.

```csharp
using System.Collections.Frozen;

// Custom threat definition
public sealed record CustomThreat
{
    public required string Id { get; init; }
    public required string Description { get; init; }
    public required ElementType TargetType { get; init; }
    public required Func<ModelElement, bool> Condition { get; init; }
    public required string Severity { get; init; }
    public IReadOnlyList<string> Mitigations { get; init; } = [];
    public IReadOnlyList<string> References { get; init; } = [];
}

// Custom threat rule definitions
public static class CustomThreatRules
{
    /// <summary>Threat for unencrypted PII transmission.</summary>
    public static CustomThreat UnencryptedPiiFlow => new()
    {
        Id = "CUSTOM-001",
        Description = "PII transmitted without encryption",
        TargetType = ElementType.Datastore,
        Condition = element => element.StoresPII && !element.IsEncryptedAtRest,
        Severity = "High",
        Mitigations = ["Enable TLS for all data flows", "Use field-level encryption for PII"],
        References = ["GDPR Art. 32", "CCPA 1798.150"]
    };

    /// <summary>Threat for internet-facing servers without WAF.</summary>
    public static CustomThreat MissingWaf => new()
    {
        Id = "CUSTOM-002",
        Description = "Internet-facing service without WAF protection",
        TargetType = ElementType.Server,
        Condition = element =>
            element.Boundary?.Name == "DMZ" &&
            element.Type == ElementType.Server &&
            !element.IsHardened,
        Severity = "Medium",
        Mitigations =
        [
            "Deploy WAF in front of web applications",
            "Configure OWASP ModSecurity Core Rule Set"
        ]
    };

    /// <summary>Get all custom threat rules.</summary>
    public static IReadOnlyList<CustomThreat> All => [UnencryptedPiiFlow, MissingWaf];
}

// Threat analyzer with custom rules
public sealed class ThreatAnalyzer(ThreatModel model)
{
    private readonly List<CustomThreat> _customRules = [.. CustomThreatRules.All];

    public void AddRule(CustomThreat rule) => _customRules.Add(rule);

    public IReadOnlyList<(ModelElement Element, CustomThreat Threat)> Analyze()
    {
        var findings = new List<(ModelElement, CustomThreat)>();

        foreach (var element in model.Elements)
        {
            foreach (var rule in _customRules.Where(r => r.TargetType == element.Type))
            {
                if (rule.Condition(element))
                {
                    findings.Add((element, rule));
                }
            }
        }

        return findings;
    }
}
```

### CI/CD Integration

```yaml
# .github/workflows/threat-model.yaml
name: Threat Model

on:
  push:
    paths:
      - 'threat-model/**'
  pull_request:
    paths:
      - 'threat-model/**'

jobs:
  analyze:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pytm graphviz
          sudo apt-get install -y graphviz

      - name: Generate threat model
        run: |
          cd threat-model
          python tm.py --dfd | dot -Tpng -o dfd.png
          python tm.py --report report.html
          python tm.py --json > threats.json

      - name: Check for high severity threats
        run: |
          HIGH_COUNT=$(jq '[.[] | select(.severity == "High")] | length' threats.json)
          echo "High severity threats: $HIGH_COUNT"
          if [ "$HIGH_COUNT" -gt 0 ]; then
            echo "::warning::Found $HIGH_COUNT high severity threats"
          fi

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: threat-model-report
          path: |
            threat-model/dfd.png
            threat-model/report.html
            threat-model/threats.json

      - name: Comment PR with summary
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const threats = JSON.parse(fs.readFileSync('threat-model/threats.json'));

            const summary = {
              total: threats.length,
              high: threats.filter(t => t.severity === 'High').length,
              medium: threats.filter(t => t.severity === 'Medium').length,
              low: threats.filter(t => t.severity === 'Low').length
            };

            const body = `## Threat Model Analysis

            | Severity | Count |
            |----------|-------|
            | High | ${summary.high} |
            | Medium | ${summary.medium} |
            | Low | ${summary.low} |
            | **Total** | **${summary.total}** |

            See artifacts for full report.`;

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            });
```

## Threagile - YAML-Based Threat Modeling

Threagile provides threat modeling through YAML configuration.

### Installation

```bash
# Docker (recommended)
docker pull threagile/threagile

# Or download binary
# https://github.com/Threagile/threagile/releases
```

### Model Definition

```yaml
# threagile.yaml
threagile_version: 1.0.0

title: E-Commerce Platform
date: 2024-01-15

author:
  name: Security Team
  homepage: https://example.com/security

management_summary_comment: |
  Threat model for the e-commerce platform handling
  customer orders and payment processing.

business_criticality: critical

business_overview:
  description: |
    Online shopping platform serving retail customers.
    Handles sensitive payment data and personal information.
  images: []

technical_overview:
  description: |
    Microservices architecture with API gateway,
    deployed on Kubernetes in AWS.
  images: []

questions:
  - text: Has penetration testing been performed?
    answer: Annual pentest by third party

abuse_cases:
  - name: Data Breach
    description: Attacker exfiltrates customer data
  - name: Payment Fraud
    description: Attacker performs unauthorized transactions

security_requirements:
  - name: PCI-DSS Compliance
    description: Must comply with PCI-DSS for payment processing
  - name: GDPR Compliance
    description: Must comply with GDPR for EU customers

# Define data assets
data_assets:

  Customer PII:
    id: customer-pii
    description: Customer personal information
    usage: business
    tags: [pii, gdpr]
    origin: Customer
    owner: User Service Team
    quantity: many
    confidentiality: confidential
    integrity: critical
    availability: important
    justification_cia_rating: |
      Contains names, addresses, emails. Must be protected under GDPR.

  Payment Credentials:
    id: payment-credentials
    description: Tokenized payment information
    usage: business
    tags: [pci, financial]
    origin: Customer
    owner: Payment Team
    quantity: many
    confidentiality: strictly-confidential
    integrity: critical
    availability: critical
    justification_cia_rating: |
      Payment data subject to PCI-DSS. Breach would cause significant harm.

  Session Tokens:
    id: session-tokens
    description: User authentication tokens
    usage: business
    tags: [authentication]
    origin: System
    owner: Security Team
    quantity: many
    confidentiality: confidential
    integrity: critical
    availability: important

# Define technical assets
technical_assets:

  Web Application:
    id: web-app
    description: Frontend web application
    type: web-application
    usage: business
    used_as_client_by_human: true
    out_of_scope: false
    justification_out_of_scope: ""
    size: application
    technology: browser
    tags: [frontend, react]
    internet: true
    machine: container
    encryption: none
    owner: Frontend Team
    confidentiality: internal
    integrity: important
    availability: critical
    justification_cia_rating: Primary customer interface
    multi_tenant: false
    redundant: true
    custom_developed_parts: true
    data_assets_processed:
      - customer-pii
      - session-tokens
    data_assets_stored: []
    data_formats_accepted:
      - json

  API Gateway:
    id: api-gateway
    description: Kong API Gateway
    type: gateway
    usage: business
    used_as_client_by_human: false
    out_of_scope: false
    size: service
    technology: kong
    tags: [api, gateway]
    internet: false
    machine: container
    encryption: transparent
    owner: Platform Team
    confidentiality: internal
    integrity: critical
    availability: critical
    multi_tenant: false
    redundant: true
    custom_developed_parts: false
    data_assets_processed:
      - session-tokens
    data_assets_stored: []
    data_formats_accepted:
      - json

  User Service:
    id: user-service
    description: User management microservice
    type: process
    usage: business
    used_as_client_by_human: false
    out_of_scope: false
    size: service
    technology: go
    tags: [microservice, users]
    internet: false
    machine: container
    encryption: none
    owner: User Service Team
    confidentiality: confidential
    integrity: critical
    availability: important
    multi_tenant: false
    redundant: true
    custom_developed_parts: true
    data_assets_processed:
      - customer-pii
      - session-tokens
    data_assets_stored: []

  Payment Service:
    id: payment-service
    description: Payment processing microservice
    type: process
    usage: business
    used_as_client_by_human: false
    out_of_scope: false
    size: service
    technology: java
    tags: [microservice, payments, pci]
    internet: false
    machine: container
    encryption: symmetric-shared-key
    owner: Payment Team
    confidentiality: strictly-confidential
    integrity: critical
    availability: critical
    multi_tenant: false
    redundant: true
    custom_developed_parts: true
    data_assets_processed:
      - payment-credentials
    data_assets_stored: []

  User Database:
    id: user-db
    description: PostgreSQL database for user data
    type: datastore
    usage: business
    used_as_client_by_human: false
    out_of_scope: false
    size: service
    technology: postgresql
    tags: [database, users]
    internet: false
    machine: container
    encryption: data-with-symmetric-shared-key
    owner: User Service Team
    confidentiality: confidential
    integrity: critical
    availability: important
    multi_tenant: false
    redundant: true
    custom_developed_parts: false
    data_assets_processed: []
    data_assets_stored:
      - customer-pii

  Payment Vault:
    id: payment-vault
    description: Encrypted payment data store
    type: datastore
    usage: business
    used_as_client_by_human: false
    out_of_scope: false
    size: service
    technology: vault
    tags: [database, payments, pci]
    internet: false
    machine: container
    encryption: data-with-asymmetric-shared-key
    owner: Payment Team
    confidentiality: strictly-confidential
    integrity: critical
    availability: critical
    multi_tenant: false
    redundant: true
    custom_developed_parts: false
    data_assets_stored:
      - payment-credentials

# Define trust boundaries
trust_boundaries:

  Internet Boundary:
    id: internet-boundary
    description: External internet facing boundary
    type: network-cloud-security-group
    tags: [external]
    technical_assets_inside:
      - web-app

  Internal Network:
    id: internal-network
    description: Internal service network
    type: network-cloud-security-group
    tags: [internal]
    technical_assets_inside:
      - api-gateway
      - user-service
      - payment-service

  Database Zone:
    id: database-zone
    description: Restricted database network
    type: network-cloud-security-group
    tags: [database, restricted]
    technical_assets_inside:
      - user-db
      - payment-vault

# Define communication links
communication_links:

  Web to API Gateway:
    source_id: web-app
    target_id: api-gateway
    description: Frontend to API Gateway
    protocol: https
    authentication: token
    authorization: technical-user
    tags: []
    vpn: false
    ip_filtered: false
    readonly: false
    usage: business
    data_assets_sent:
      - session-tokens
    data_assets_received:
      - customer-pii

  API Gateway to User Service:
    source_id: api-gateway
    target_id: user-service
    description: API Gateway to User Service
    protocol: grpc
    authentication: token
    authorization: technical-user
    tags: []
    vpn: false
    ip_filtered: true
    readonly: false
    usage: business
    data_assets_sent:
      - session-tokens
    data_assets_received:
      - customer-pii

  User Service to Database:
    source_id: user-service
    target_id: user-db
    description: User Service to PostgreSQL
    protocol: postgresql
    authentication: credentials
    authorization: technical-user
    tags: []
    vpn: false
    ip_filtered: true
    readonly: false
    usage: business
    data_assets_sent:
      - customer-pii
    data_assets_received:
      - customer-pii

  Payment Service to Vault:
    source_id: payment-service
    target_id: payment-vault
    description: Payment Service to Vault
    protocol: vault
    authentication: client-certificate
    authorization: technical-user
    tags: [pci]
    vpn: false
    ip_filtered: true
    readonly: false
    usage: business
    data_assets_sent:
      - payment-credentials
    data_assets_received:
      - payment-credentials

# Individual risk tracking
individual_risk_categories:

  Missing Rate Limiting:
    id: missing-rate-limiting
    description: API endpoints lack rate limiting
    impact: Denial of service, credential stuffing
    asvs: V4.3
    cheat_sheet: https://cheatsheetseries.owasp.org/cheatsheets/API_Security_Cheat_Sheet.html
    action: Implement rate limiting at API Gateway
    mitigation: Configure Kong rate limiting plugin
    check: Verify rate limits in load testing
    function: operations
    stride: denial-of-service
    detection_logic: Monitor for traffic spikes
    risk_assessment: High volume attacks possible
    false_positives: Legitimate traffic spikes
    model_failure_possible_reason: false
    cwe: 307
    risks_identified:
      API Gateway Rate Limiting:
        severity: medium
        exploitation_likelihood: likely
        exploitation_impact: medium
        data_breach_probability: improbable
        data_breach_technical_assets: []
        most_relevant_data_asset: session-tokens
        most_relevant_technical_asset: api-gateway
        most_relevant_communication_link: ""
        most_relevant_trust_boundary: ""
        most_relevant_shared_runtime: ""
```

### Running Threagile

```bash
# Generate full report
docker run --rm -v $(pwd):/app threagile/threagile \
  analyze-model \
  --model /app/threagile.yaml \
  --output /app/output

# Generate specific outputs
docker run --rm -v $(pwd):/app threagile/threagile \
  analyze-model \
  --model /app/threagile.yaml \
  --output /app/output \
  --generate-data-flow-diagram \
  --generate-data-asset-diagram \
  --generate-risks-json \
  --generate-technical-assets-json \
  --generate-stats-json \
  --generate-risks-excel \
  --generate-tags-excel \
  --generate-report-pdf

# List available built-in risk rules
docker run --rm threagile/threagile list-risk-rules

# Validate model syntax
docker run --rm -v $(pwd):/app threagile/threagile \
  analyze-model \
  --model /app/threagile.yaml \
  --skip-risk-rules \
  --verbose
```

### Threagile CI/CD Integration

```yaml
# .github/workflows/threagile.yaml
name: Threat Model Analysis

on:
  push:
    paths:
      - 'threat-model/threagile.yaml'
  pull_request:
    paths:
      - 'threat-model/threagile.yaml'

jobs:
  analyze:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v5

      - name: Run Threagile analysis
        run: |
          docker run --rm \
            -v ${{ github.workspace }}/threat-model:/app \
            threagile/threagile \
            analyze-model \
            --model /app/threagile.yaml \
            --output /app/output \
            --generate-data-flow-diagram \
            --generate-risks-json \
            --generate-report-pdf

      - name: Check critical risks
        run: |
          CRITICAL=$(jq '[.[] | select(.severity == "critical")] | length' \
            threat-model/output/risks.json)
          HIGH=$(jq '[.[] | select(.severity == "elevated")] | length' \
            threat-model/output/risks.json)

          echo "Critical: $CRITICAL, High: $HIGH"

          if [ "$CRITICAL" -gt 0 ]; then
            echo "::error::Found $CRITICAL critical risks"
            exit 1
          fi

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: threat-model-report
          path: threat-model/output/
```

## Microsoft Threat Modeling Tool

Microsoft's official threat modeling tool with STRIDE analysis.

### Installation

Download from: <https://aka.ms/threatmodelingtool>

### Template Selection

| Template | Use Case |
|----------|----------|
| Azure | Azure-hosted applications |
| SDL | General applications |
| Medical Device | Healthcare/FDA requirements |
| Automotive | Vehicle systems |

### Automation with TMT

```powershell
# Export threat model to JSON
& "C:\Program Files\Microsoft Threat Modeling Tool\ThreatModelingTool.exe" `
    /import /model "model.tm7" `
    /exportjson /output "threats.json"

# Generate report
& "C:\Program Files\Microsoft Threat Modeling Tool\ThreatModelingTool.exe" `
    /import /model "model.tm7" `
    /generatereport /output "report.html"
```

### TMT to SARIF Conversion

```csharp
using System.Collections.Frozen;
using System.Text.Json;
using System.Text.Json.Serialization;

/// <summary>Convert Microsoft Threat Modeling Tool JSON to SARIF for GitHub Security integration.</summary>
public static class TmtToSarifConverter
{
    private static readonly FrozenDictionary<string, string> SeverityMapping =
        new Dictionary<string, string>
        {
            ["High"] = "error",
            ["Medium"] = "warning",
            ["Low"] = "note"
        }.ToFrozenDictionary();

    public static async Task ConvertAsync(string tmtFile, string outputFile, CancellationToken ct = default)
    {
        await using var stream = File.OpenRead(tmtFile);
        var tmtData = await JsonSerializer.DeserializeAsync<TmtModel>(stream, cancellationToken: ct)
            ?? throw new InvalidOperationException("Failed to parse TMT file");

        var rules = new Dictionary<string, SarifRule>();
        var results = new List<SarifResult>();

        foreach (var threat in tmtData.Threats)
        {
            var ruleId = $"TMT-{threat.Category}";

            if (!rules.ContainsKey(ruleId))
            {
                rules[ruleId] = new SarifRule
                {
                    Id = ruleId,
                    Name = threat.Category,
                    ShortDescription = new SarifMessage { Text = threat.Category },
                    FullDescription = new SarifMessage { Text = $"STRIDE: {threat.Category}" },
                    DefaultConfiguration = new SarifConfiguration
                    {
                        Level = MapSeverity(threat.Priority)
                    }
                };
            }

            results.Add(new SarifResult
            {
                RuleId = ruleId,
                Message = new SarifMessage { Text = threat.Description },
                Level = MapSeverity(threat.Priority),
                Locations =
                [
                    new SarifLocation
                    {
                        PhysicalLocation = new SarifPhysicalLocation
                        {
                            ArtifactLocation = new SarifArtifactLocation { Uri = "threat-model.tm7" },
                            Region = new SarifRegion { StartLine = 1 }
                        }
                    }
                ],
                Properties = new SarifResultProperties
                {
                    Element = threat.Element ?? "",
                    Mitigation = threat.Mitigation ?? "",
                    State = threat.State ?? ""
                }
            });
        }

        var sarif = new SarifReport
        {
            Schema = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            Version = "2.1.0",
            Runs =
            [
                new SarifRun
                {
                    Tool = new SarifTool
                    {
                        Driver = new SarifDriver
                        {
                            Name = "Microsoft Threat Modeling Tool",
                            Version = "7.3",
                            InformationUri = "https://aka.ms/threatmodelingtool",
                            Rules = [.. rules.Values]
                        }
                    },
                    Results = results
                }
            ]
        };

        var options = new JsonSerializerOptions { WriteIndented = true };
        await using var output = File.Create(outputFile);
        await JsonSerializer.SerializeAsync(output, sarif, options, ct);
    }

    private static string MapSeverity(string? priority) =>
        SeverityMapping.GetValueOrDefault(priority ?? "Medium", "warning");
}

// TMT input model
public sealed record TmtModel
{
    [JsonPropertyName("threats")]
    public IReadOnlyList<TmtThreat> Threats { get; init; } = [];
}

public sealed record TmtThreat
{
    [JsonPropertyName("category")]
    public string Category { get; init; } = "";

    [JsonPropertyName("description")]
    public string Description { get; init; } = "";

    [JsonPropertyName("priority")]
    public string? Priority { get; init; }

    [JsonPropertyName("element")]
    public string? Element { get; init; }

    [JsonPropertyName("mitigation")]
    public string? Mitigation { get; init; }

    [JsonPropertyName("state")]
    public string? State { get; init; }
}

// SARIF output model
public sealed record SarifReport
{
    [JsonPropertyName("$schema")]
    public required string Schema { get; init; }

    [JsonPropertyName("version")]
    public required string Version { get; init; }

    [JsonPropertyName("runs")]
    public required IReadOnlyList<SarifRun> Runs { get; init; }
}

public sealed record SarifRun
{
    [JsonPropertyName("tool")]
    public required SarifTool Tool { get; init; }

    [JsonPropertyName("results")]
    public required IReadOnlyList<SarifResult> Results { get; init; }
}

public sealed record SarifTool
{
    [JsonPropertyName("driver")]
    public required SarifDriver Driver { get; init; }
}

public sealed record SarifDriver
{
    [JsonPropertyName("name")]
    public required string Name { get; init; }

    [JsonPropertyName("version")]
    public required string Version { get; init; }

    [JsonPropertyName("informationUri")]
    public required string InformationUri { get; init; }

    [JsonPropertyName("rules")]
    public required IReadOnlyList<SarifRule> Rules { get; init; }
}

public sealed record SarifRule
{
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    [JsonPropertyName("name")]
    public required string Name { get; init; }

    [JsonPropertyName("shortDescription")]
    public required SarifMessage ShortDescription { get; init; }

    [JsonPropertyName("fullDescription")]
    public required SarifMessage FullDescription { get; init; }

    [JsonPropertyName("defaultConfiguration")]
    public required SarifConfiguration DefaultConfiguration { get; init; }
}

public sealed record SarifMessage
{
    [JsonPropertyName("text")]
    public required string Text { get; init; }
}

public sealed record SarifConfiguration
{
    [JsonPropertyName("level")]
    public required string Level { get; init; }
}

public sealed record SarifResult
{
    [JsonPropertyName("ruleId")]
    public required string RuleId { get; init; }

    [JsonPropertyName("message")]
    public required SarifMessage Message { get; init; }

    [JsonPropertyName("level")]
    public required string Level { get; init; }

    [JsonPropertyName("locations")]
    public required IReadOnlyList<SarifLocation> Locations { get; init; }

    [JsonPropertyName("properties")]
    public required SarifResultProperties Properties { get; init; }
}

public sealed record SarifLocation
{
    [JsonPropertyName("physicalLocation")]
    public required SarifPhysicalLocation PhysicalLocation { get; init; }
}

public sealed record SarifPhysicalLocation
{
    [JsonPropertyName("artifactLocation")]
    public required SarifArtifactLocation ArtifactLocation { get; init; }

    [JsonPropertyName("region")]
    public required SarifRegion Region { get; init; }
}

public sealed record SarifArtifactLocation
{
    [JsonPropertyName("uri")]
    public required string Uri { get; init; }
}

public sealed record SarifRegion
{
    [JsonPropertyName("startLine")]
    public required int StartLine { get; init; }
}

public sealed record SarifResultProperties
{
    [JsonPropertyName("element")]
    public required string Element { get; init; }

    [JsonPropertyName("mitigation")]
    public required string Mitigation { get; init; }

    [JsonPropertyName("state")]
    public required string State { get; init; }
}
```

## OWASP Threat Dragon

Web-based threat modeling tool.

### Docker Deployment

```yaml
# docker-compose.yaml
version: '3.8'

services:
  threat-dragon:
    image: owasp/threat-dragon:latest
    ports:
      - "3000:3000"
    environment:
      - ENCRYPTION_KEYS=your-encryption-key
      - NODE_ENV=production
    volumes:
      - ./models:/app/models
```

### Integration Script

```csharp
using System.Text.Json;
using System.Text.Json.Serialization;

/// <summary>Standardized threat format for tooling integration.</summary>
public sealed record StandardizedThreat
{
    public required string Id { get; init; }
    public required string Title { get; init; }
    public required string Category { get; init; }  // STRIDE category
    public required string Description { get; init; }
    public required string Severity { get; init; }
    public required string Status { get; init; }
    public string? Mitigation { get; init; }
    public string? Element { get; init; }
}

/// <summary>Export Threat Dragon models to standardized format.</summary>
public static class ThreatDragonExporter
{
    public static async Task<IReadOnlyList<StandardizedThreat>> ExportAsync(
        string modelFile,
        CancellationToken ct = default)
    {
        await using var stream = File.OpenRead(modelFile);
        var model = await JsonSerializer.DeserializeAsync<ThreatDragonModel>(stream, cancellationToken: ct)
            ?? throw new InvalidOperationException("Failed to parse Threat Dragon model");

        var threats = new List<StandardizedThreat>();

        foreach (var diagram in model.Detail?.Diagrams ?? [])
        {
            foreach (var cell in diagram.Cells ?? [])
            {
                foreach (var threat in cell.Threats ?? [])
                {
                    threats.Add(new StandardizedThreat
                    {
                        Id = threat.Id ?? "",
                        Title = threat.Title ?? "",
                        Category = threat.Type ?? "",
                        Description = threat.Description ?? "",
                        Severity = threat.Severity ?? "Medium",
                        Status = threat.Status ?? "Open",
                        Mitigation = threat.Mitigation,
                        Element = cell.Id
                    });
                }
            }
        }

        return threats;
    }

    public static async Task ExportToJsonAsync(
        IReadOnlyList<StandardizedThreat> threats,
        string outputFile,
        CancellationToken ct = default)
    {
        var options = new JsonSerializerOptions { WriteIndented = true };
        await using var stream = File.Create(outputFile);
        await JsonSerializer.SerializeAsync(stream, threats, options, ct);
    }
}

// Threat Dragon model structure
public sealed record ThreatDragonModel
{
    [JsonPropertyName("detail")]
    public ThreatDragonDetail? Detail { get; init; }
}

public sealed record ThreatDragonDetail
{
    [JsonPropertyName("diagrams")]
    public IReadOnlyList<ThreatDragonDiagram>? Diagrams { get; init; }
}

public sealed record ThreatDragonDiagram
{
    [JsonPropertyName("cells")]
    public IReadOnlyList<ThreatDragonCell>? Cells { get; init; }
}

public sealed record ThreatDragonCell
{
    [JsonPropertyName("id")]
    public string? Id { get; init; }

    [JsonPropertyName("threats")]
    public IReadOnlyList<ThreatDragonThreat>? Threats { get; init; }
}

public sealed record ThreatDragonThreat
{
    [JsonPropertyName("id")]
    public string? Id { get; init; }

    [JsonPropertyName("title")]
    public string? Title { get; init; }

    [JsonPropertyName("type")]
    public string? Type { get; init; }

    [JsonPropertyName("description")]
    public string? Description { get; init; }

    [JsonPropertyName("severity")]
    public string? Severity { get; init; }

    [JsonPropertyName("status")]
    public string? Status { get; init; }

    [JsonPropertyName("mitigation")]
    public string? Mitigation { get; init; }
}
```

## Threat Model Validation

```csharp
using System.Collections.Frozen;
using System.Text.Json;

/// <summary>Validation result for threat model.</summary>
public sealed record ValidationResult
{
    public required bool Passed { get; init; }
    public required double Score { get; init; }  // 0-100
    public required IReadOnlyList<string> Findings { get; init; }
    public required IReadOnlyList<string> Recommendations { get; init; }
}

/// <summary>Validate threat model quality and completeness.</summary>
public sealed class ThreatModelValidator
{
    private static readonly FrozenSet<string> AllStrideCategories =
        new HashSet<string> { "S", "T", "R", "I", "D", "E" }.ToFrozenSet();

    public ValidationResult Validate(JsonDocument model)
    {
        var findings = new List<string>();
        var recommendations = new List<string>();
        var score = 100.0;

        var root = model.RootElement;

        // Check data assets defined
        if (!root.TryGetProperty("data_assets", out var dataAssets) ||
            dataAssets.ValueKind != JsonValueKind.Object ||
            dataAssets.EnumerateObject().Count() == 0)
        {
            findings.Add("No data assets defined");
            score -= 20;
            recommendations.Add("Define all sensitive data assets");
        }

        // Check all STRIDE categories covered
        var threats = GetThreats(root);
        var coveredStride = threats
            .Select(t => t.TryGetProperty("category", out var c) ? c.GetString() : null)
            .Where(c => c is not null)
            .ToHashSet();

        var missingStride = AllStrideCategories.Except(coveredStride!).ToList();
        if (missingStride.Count > 0)
        {
            findings.Add($"Missing STRIDE coverage: {string.Join(", ", missingStride)}");
            score -= 10 * missingStride.Count;
            recommendations.Add("Analyze all STRIDE categories");
        }

        // Check mitigations defined
        var unmitigatedCount = threats.Count(t =>
            !t.TryGetProperty("mitigation", out var m) ||
            m.ValueKind == JsonValueKind.Null ||
            string.IsNullOrEmpty(m.GetString()));

        if (unmitigatedCount > 0)
        {
            findings.Add($"{unmitigatedCount} threats without mitigations");
            score -= Math.Min(30, unmitigatedCount * 5);
            recommendations.Add("Define mitigations for all threats");
        }

        // Check trust boundaries
        var boundaryCount = root.TryGetProperty("trust_boundaries", out var boundaries)
            ? boundaries.ValueKind == JsonValueKind.Array ? boundaries.GetArrayLength() : 0
            : 0;

        if (boundaryCount < 2)
        {
            findings.Add("Insufficient trust boundaries defined");
            score -= 15;
            recommendations.Add("Define clear trust boundaries");
        }

        // Check data flows across boundaries
        var crossBoundaryFlows = CountCrossBoundaryFlows(root);
        if (crossBoundaryFlows == 0)
        {
            findings.Add("No cross-boundary data flows identified");
            score -= 10;
            recommendations.Add("Identify all cross-boundary data flows");
        }

        return new ValidationResult
        {
            Passed = score >= 70,
            Score = Math.Max(0, score),
            Findings = findings,
            Recommendations = recommendations
        };
    }

    private static IReadOnlyList<JsonElement> GetThreats(JsonElement root)
    {
        if (root.TryGetProperty("threats", out var threats) &&
            threats.ValueKind == JsonValueKind.Array)
        {
            return [.. threats.EnumerateArray()];
        }
        return [];
    }

    private static int CountCrossBoundaryFlows(JsonElement root)
    {
        // Implementation depends on model format
        if (root.TryGetProperty("communication_links", out var links) &&
            links.ValueKind == JsonValueKind.Array)
        {
            return links.GetArrayLength();
        }
        return 0;
    }
}

// Usage example
public static class ThreatModelValidatorUsage
{
    public static async Task<ValidationResult> ValidateFileAsync(
        string modelPath,
        CancellationToken ct = default)
    {
        await using var stream = File.OpenRead(modelPath);
        using var document = await JsonDocument.ParseAsync(stream, cancellationToken: ct);

        var validator = new ThreatModelValidator();
        return validator.Validate(document);
    }
}
```

## Version History

- **v1.0.0** (2025-12-26): Initial release with pytm, Threagile, MS TMT, Threat Dragon

---

**Last Updated:** 2025-12-26
