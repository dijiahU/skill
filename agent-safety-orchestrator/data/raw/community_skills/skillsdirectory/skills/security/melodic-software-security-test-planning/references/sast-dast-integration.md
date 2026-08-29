# SAST/DAST Integration

## CI/CD Security Gates

### GitHub Actions Example

```yaml
security-scan:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v5

    # Secret scanning
    - name: Gitleaks Scan
      uses: gitleaks/gitleaks-action@v2
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

    # SAST
    - name: SonarQube Scan
      uses: SonarSource/sonarcloud-github-action@v2
      with:
        args: >
          -Dsonar.qualitygate.wait=true

    # Dependency scanning
    - name: Dependency Check
      uses: dependency-check/Dependency-Check_Action@main
      with:
        project: 'MyProject'
        path: '.'
        format: 'HTML'
        args: >
          --failOnCVSS 7
          --suppression suppressions.xml

    # Container scanning
    - name: Trivy Container Scan
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: 'myregistry/myimage:${{ github.sha }}'
        severity: 'CRITICAL,HIGH'
        exit-code: '1'
```

---

## DAST with OWASP ZAP

### ZAP API Integration

```csharp
// ZAP API integration for automated DAST
public class ZapSecurityScan
{
    private readonly HttpClient _zapClient;
    private readonly string _targetUrl;

    public async Task<ScanResult> RunFullScan()
    {
        // Start spider
        await _zapClient.GetAsync($"/JSON/spider/action/scan/?url={_targetUrl}");
        await WaitForSpiderComplete();

        // Run active scan
        var scanId = await StartActiveScan();
        await WaitForScanComplete(scanId);

        // Get alerts
        var alerts = await GetAlerts();

        return new ScanResult
        {
            HighAlerts = alerts.Count(a => a.Risk == "High"),
            MediumAlerts = alerts.Count(a => a.Risk == "Medium"),
            LowAlerts = alerts.Count(a => a.Risk == "Low"),
            Alerts = alerts
        };
    }
}
```

### ZAP Docker Integration

```yaml
# GitHub Actions with ZAP
dast-scan:
  runs-on: ubuntu-latest
  steps:
    - name: Start Application
      run: docker-compose up -d app

    - name: Wait for App
      run: |
        until curl -s http://localhost:8080/health; do
          sleep 5
        done

    - name: ZAP Full Scan
      uses: zaproxy/action-full-scan@v0.8.0
      with:
        target: 'http://localhost:8080'
        rules_file_name: '.zap/rules.tsv'
        cmd_options: '-a'

    - name: Upload ZAP Report
      uses: actions/upload-artifact@v4
      with:
        name: zap-report
        path: report_html.html
```

---

## Tool Comparison

| Tool | Type | Strengths | Integration |
|------|------|-----------|-------------|
| SonarQube | SAST | Code quality + security | GitHub, GitLab, Jenkins |
| Semgrep | SAST | Fast, custom rules | CLI, CI/CD native |
| Snyk | SCA/SAST | Dependency focus | GitHub App |
| OWASP ZAP | DAST | Free, comprehensive | Docker, API |
| Burp Suite | DAST | Enterprise features | CI/CD plugins |
| Trivy | Container | Fast, multi-target | CI/CD native |
| Gitleaks | Secrets | Pre-commit ready | Git hooks |

---

## Security Gates by Pipeline Stage

```text
┌─────────────────────────────────────────────────────────────┐
│                    CI/CD SECURITY GATES                     │
├─────────────────────────────────────────────────────────────┤
│  PRE-COMMIT                                                 │
│  ├── Gitleaks (secrets)                                    │
│  └── Pre-commit hooks                                      │
├─────────────────────────────────────────────────────────────┤
│  BUILD                                                      │
│  ├── SAST (SonarQube, Semgrep)                             │
│  ├── SCA (Snyk, Dependabot)                                │
│  └── License scanning                                      │
├─────────────────────────────────────────────────────────────┤
│  TEST                                                       │
│  ├── Security unit tests                                   │
│  ├── Container scanning (Trivy)                            │
│  └── IaC scanning (Checkov)                                │
├─────────────────────────────────────────────────────────────┤
│  DEPLOY (Staging)                                           │
│  ├── DAST (ZAP, Burp)                                      │
│  ├── API security testing                                  │
│  └── Smoke security tests                                  │
├─────────────────────────────────────────────────────────────┤
│  DEPLOY (Production)                                        │
│  ├── Final vulnerability check                             │
│  └── Compliance validation                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Gate Thresholds

| Stage | Critical | High | Medium | Action |
|-------|----------|------|--------|--------|
| Pre-commit | 0 | 0 | - | Block |
| Build | 0 | 0 | - | Block |
| Test | 0 | 0 | 5 | Warn on medium |
| Staging | 0 | 0 | 10 | Block high+ |
| Production | 0 | 0 | - | Block all |
