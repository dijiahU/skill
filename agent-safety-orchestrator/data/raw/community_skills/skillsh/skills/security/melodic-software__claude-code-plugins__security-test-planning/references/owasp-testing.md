# OWASP Testing Guide Categories

## Information Gathering (WSTG-INFO)

| Test ID | Test Name | Automation |
|---------|-----------|------------|
| WSTG-INFO-01 | Search engine discovery | Semi |
| WSTG-INFO-02 | Fingerprint web server | Automated |
| WSTG-INFO-03 | Review webserver metafiles | Automated |
| WSTG-INFO-04 | Enumerate applications | Semi |
| WSTG-INFO-05 | Review page content | Manual |

---

## Authentication Testing (WSTG-ATHN)

| Test ID | Test Name | Priority |
|---------|-----------|----------|
| WSTG-ATHN-01 | Credentials over encrypted channel | P1 |
| WSTG-ATHN-02 | Default credentials | P1 |
| WSTG-ATHN-03 | Weak lockout mechanism | P1 |
| WSTG-ATHN-04 | Bypassing authentication | P1 |
| WSTG-ATHN-05 | Vulnerable remember password | P2 |

---

## Authorization Testing (WSTG-ATHZ)

| Test ID | Test Name | Priority |
|---------|-----------|----------|
| WSTG-ATHZ-01 | Directory traversal | P1 |
| WSTG-ATHZ-02 | Bypassing authorization | P1 |
| WSTG-ATHZ-03 | Privilege escalation | P1 |
| WSTG-ATHZ-04 | Insecure direct object refs | P1 |

---

## Input Validation Testing (WSTG-INPV)

| Test ID | Test Name | Automation |
|---------|-----------|------------|
| WSTG-INPV-01 | Reflected XSS | Automated |
| WSTG-INPV-02 | Stored XSS | Semi |
| WSTG-INPV-03 | HTTP verb tampering | Automated |
| WSTG-INPV-05 | SQL injection | Automated |
| WSTG-INPV-11 | Code injection | Manual |
| WSTG-INPV-12 | Command injection | Automated |

---

## Security Test Case Template

```markdown
## Security Test Case: [Test ID]

### Metadata
- **OWASP Category**: [e.g., WSTG-ATHN-03]
- **Severity**: [Critical/High/Medium/Low]
- **Automation**: [Automated/Semi/Manual]
- **Compliance**: [PCI-DSS 8.1.6, ASVS 2.2.1]

### Objective
[What vulnerability are we testing for?]

### Prerequisites
- [Authentication state]
- [Test data requirements]
- [Tool configuration]

### Test Steps
1. [Step 1]
2. [Step 2]
3. [Step N]

### Expected Result (Pass)
[What should happen if secure]

### Vulnerability Indicator (Fail)
[What indicates a vulnerability]

### Remediation Guidance
[How to fix if vulnerable]

### Evidence Collection
- [ ] Request/response captured
- [ ] Screenshots if applicable
- [ ] Logs collected
```

---

## Test Category Overview

| Category | Code | Focus Area |
|----------|------|------------|
| Information Gathering | WSTG-INFO | Reconnaissance |
| Configuration | WSTG-CONF | Server/app config |
| Identity Management | WSTG-IDNT | User provisioning |
| Authentication | WSTG-ATHN | Login security |
| Authorization | WSTG-ATHZ | Access control |
| Session Management | WSTG-SESS | Session handling |
| Input Validation | WSTG-INPV | Injection attacks |
| Error Handling | WSTG-ERRH | Error messages |
| Cryptography | WSTG-CRYP | Encryption |
| Business Logic | WSTG-BUSL | Workflow flaws |
| Client-Side | WSTG-CLNT | Browser security |
