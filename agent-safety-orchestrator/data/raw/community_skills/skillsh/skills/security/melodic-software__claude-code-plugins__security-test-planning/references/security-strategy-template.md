# Security Test Strategy Template

## Template

```markdown
# Security Test Strategy: [Project Name]

## 1. Scope and Objectives

### Objectives
- Identify vulnerabilities before production
- Validate compliance with security requirements
- Verify remediation of known vulnerabilities
- Maintain security posture over time

### Scope
| Asset Type | In Scope | Testing Approach |
|------------|----------|------------------|
| Web Application | Yes | OWASP Testing Guide |
| REST APIs | Yes | API Security Testing |
| Mobile App | Yes | OWASP MASTG |
| Infrastructure | Limited | Config review only |
| Third-party | No | Vendor assessment |

### Compliance Requirements
- [ ] OWASP ASVS Level 2
- [ ] PCI-DSS (if payments)
- [ ] HIPAA (if healthcare)
- [ ] SOC 2 controls

## 2. Testing Layers

### Layer 1: Continuous Automated (CI/CD)
| Tool Type | Tool | Frequency | Gate |
|-----------|------|-----------|------|
| Secret Scanning | Gitleaks, TruffleHog | Pre-commit | Block |
| SAST | SonarQube, Semgrep | Every PR | Block Critical |
| Dependency Scan | Dependabot, Snyk | Every build | Block High+ |
| Container Scan | Trivy, Grype | Every build | Block Critical |

### Layer 2: Periodic Automated (Weekly/Release)
| Tool Type | Tool | Frequency | Scope |
|-----------|------|-----------|-------|
| DAST | OWASP ZAP, Burp | Weekly | Full app |
| API Security | 42Crunch, Postman | Per release | All endpoints |
| Infrastructure | ScoutSuite, Prowler | Monthly | Cloud config |

### Layer 3: Manual Testing (Quarterly)
| Activity | Frequency | Provider |
|----------|-----------|----------|
| Penetration Test | Quarterly | External firm |
| Code Review | Per major feature | Internal security |
| Threat Modeling | Per feature | Security + Dev |

## 3. OWASP Top 10 Coverage

| Category | Testing Approach | Tools |
|----------|------------------|-------|
| A01: Broken Access Control | Manual + Automated | ZAP, Burp, Custom scripts |
| A02: Cryptographic Failures | Code review + SAST | SonarQube, manual review |
| A03: Injection | SAST + DAST + Manual | SQLMap, ZAP, Semgrep |
| A04: Insecure Design | Threat modeling | Manual review |
| A05: Security Misconfiguration | Config scanning | ScoutSuite, Trivy |
| A06: Vulnerable Components | SCA | Snyk, Dependabot |
| A07: Auth Failures | Manual + Automated | Burp, custom tests |
| A08: Data Integrity | Manual testing | Custom scripts |
| A09: Logging Failures | Log review | Manual + SIEM |
| A10: SSRF | DAST + Manual | ZAP, Burp, custom |

## 4. Test Cases by Threat

### Authentication Testing
- [ ] Brute force protection
- [ ] Password policy enforcement
- [ ] Session timeout
- [ ] Multi-factor bypass attempts
- [ ] OAuth/OIDC flow security

### Authorization Testing
- [ ] Horizontal privilege escalation
- [ ] Vertical privilege escalation
- [ ] Direct object reference
- [ ] Function-level access control
- [ ] API authorization consistency

### Input Validation Testing
- [ ] SQL injection (all parameters)
- [ ] XSS (stored, reflected, DOM)
- [ ] Command injection
- [ ] Path traversal
- [ ] XML/XXE attacks

### Business Logic Testing
- [ ] Workflow bypass
- [ ] Rate limiting bypass
- [ ] Price/quantity manipulation
- [ ] Race conditions

## 5. Penetration Test Scope

### Included
- Public-facing web applications
- Internal APIs with sensitive data
- Authentication and session management
- File upload functionality
- Payment processing flows

### Excluded
- Third-party integrations (vendor managed)
- DDoS/availability testing
- Physical security
- Social engineering

### Rules of Engagement
- Testing window: [Dates]
- Notification: Security team notified
- Data: Use synthetic data only
- Reporting: Real-time for critical findings

## 6. Remediation SLAs

| Severity | SLA | Verification |
|----------|-----|--------------|
| Critical | 24 hours | Immediate retest |
| High | 7 days | Next sprint retest |
| Medium | 30 days | Quarterly scan |
| Low | 90 days | Annual review |

## 7. Metrics and Reporting

### KPIs
- Mean time to remediation (by severity)
- Vulnerability density (per KLOC)
- Security debt trend
- Coverage percentage

### Reporting
| Report | Audience | Frequency |
|--------|----------|-----------|
| Scan Summary | Dev team | Daily |
| Vulnerability Status | Management | Weekly |
| Security Posture | Executive | Monthly |
| Compliance Report | Auditors | Quarterly |
```

## Strategy Checklist

Before starting security testing:

- [ ] Scope and objectives defined
- [ ] Testing layers planned
- [ ] OWASP Top 10 coverage mapped
- [ ] Test cases by threat documented
- [ ] Penetration test scope agreed
- [ ] Remediation SLAs established
- [ ] Metrics and reporting configured
