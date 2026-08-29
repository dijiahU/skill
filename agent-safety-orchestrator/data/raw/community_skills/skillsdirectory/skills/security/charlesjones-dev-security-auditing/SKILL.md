---
name: security-auditing
description: Guide for conducting comprehensive security audits of code to identify vulnerabilities. This skill should be used when reviewing authentication, input validation, cryptography, or API security.
--- 

# Security Audit Skill

This skill provides elite security expertise for identifying and eliminating vulnerabilities before malicious actors can exploit them.

## When to Use This Skill

Invoke this skill when:
- Reviewing authentication and authorization mechanisms
- Auditing code for injection vulnerabilities (SQL, NoSQL, command, XSS)
- Validating input sanitization and data protection measures
- Assessing cryptographic implementations and key management
- Analyzing API security, rate limiting, and authorization controls
- Conducting security reviews of new features or code changes
- Auditing payment processing, file uploads, or sensitive data handling
- Investigating potential security vulnerabilities reported by users or tools

## Core Security Expertise

### 1. Authentication & Authorization Vulnerabilities

To identify authentication and authorization issues, examine:
- Password policies and storage mechanisms (bcrypt, argon2 vs plaintext)
- Session management and token expiration
- Authorization checks at every protected resource
- JWT token implementation (secret strength, expiration, algorithm)
- OAuth/SAML flows for common implementation errors
- Multi-factor authentication bypass opportunities

**Key Rules:**
- Never trust client-side authorization checks alone
- Every protected endpoint must verify both authentication AND authorization
- Session tokens should have appropriate timeouts and secure flags

### 2. Injection Attacks

To detect injection vulnerabilities, trace user input through:
- Database queries (SQL injection, NoSQL operator injection)
- System commands (command injection, path traversal)
- Template engines (template injection, SSTI)
- XML parsers (XXE injection)
- LDAP queries (LDAP injection)

**Key Rules:**
- User input must be validated, sanitized, and parameterized
- Never concatenate user input directly into queries or commands
- Use ORM/query builders with parameterization, not string concatenation

### 3. Input Validation & Sanitization

To validate input handling, check for:
- Whitelist-based validation on all user inputs
- Proper encoding for output contexts (HTML, JavaScript, URL, SQL)
- File upload restrictions (type, size, content validation)
- Mass assignment protection on data models
- Type validation to prevent coercion attacks

**Key Rules:**
- Validate on the server side, never trust client-side validation alone
- Use context-appropriate encoding when outputting user data
- Implement file upload validation beyond just file extension checks

### 4. Data Protection & Cryptography

To assess data protection, evaluate:
- Sensitive data identification and classification (PII, credentials, tokens)
- Encryption at rest (database fields, file storage)
- Encryption in transit (HTTPS enforcement, certificate validation)
- Cryptographic algorithm strength (avoid MD5, SHA1, DES, ECB mode)
- Key management and rotation procedures
- Timing attack vulnerabilities in comparison operations

**Key Rules:**
- Never store passwords in plaintext or with reversible encryption
- Use industry-standard libraries (not custom cryptography)
- Enforce HTTPS for all sensitive data transmission

### 5. API Security

To audit API security, review:
- Rate limiting implementation on all endpoints
- Object-level authorization (IDOR prevention)
- Excessive data exposure in API responses
- Security headers (CORS, CSP, HSTS, X-Frame-Options)
- API key rotation and secure storage
- Mass assignment vulnerabilities in request handlers

**Key Rules:**
- Implement rate limiting based on business requirements
- Return only the data the user is authorized to see
- Use security headers to enforce browser-side protections

### 6. Business Logic Vulnerabilities

To find business logic flaws, analyze:
- Race conditions in critical operations (TOCTOU issues)
- Price manipulation opportunities
- Privilege escalation paths through workflow abuse
- State transition validation
- Anti-automation controls (CAPTCHA, rate limiting)

**Key Rules:**
- Critical operations should be atomic and idempotent
- Validate state transitions, not just individual states
- Implement transaction-level integrity checks

## Audit Methodology

When reviewing code, follow this systematic approach:

1. **Threat Modeling**: Identify attack surfaces and potential threat actors
2. **Code Flow Analysis**: Trace data flow from user input to sensitive operations
3. **Vulnerability Scanning**: Systematically check for known vulnerability patterns
4. **Attack Simulation**: Think like an attacker - how would this be exploited?
5. **Defense Verification**: Validate that security controls are properly implemented
6. **Compliance Check**: Ensure adherence to standards (OWASP Top 10, PCI-DSS, GDPR)

## Report Output Format

**IMPORTANT**: The section below defines the COMPLETE report structure that MUST be used. Do NOT create your own format or simplified version.

### Location and Naming
- **Directory**: `/docs/security/`
- **Filename**: `YYYY-MM-DD-HHMMSS-security-audit.md`
- **Example**: `2025-10-29-143022-security-audit.md`

### Report Template

**🚨 CRITICAL INSTRUCTION - READ CAREFULLY 🚨**

You MUST use this exact template structure for ALL security audit reports. This is MANDATORY and NON-NEGOTIABLE.

**REQUIREMENTS:**
1. ✅ Use the COMPLETE template structure below - ALL sections are REQUIRED
2. ✅ Follow the EXACT heading hierarchy (##, ###, ####)
3. ✅ Include ALL section headings as written in the template
4. ✅ Use the finding numbering format: C-001, H-001, M-001, L-001, etc.
5. ✅ Include the tables, code examples, and checklists as shown
6. ❌ DO NOT create your own format or structure
7. ❌ DO NOT skip or combine sections
8. ❌ DO NOT create abbreviated or simplified versions
9. ❌ DO NOT number issues as "1, 2, 3" - use C-001, H-001, M-001 format

**If you do not follow this template exactly, the report will be rejected.**

<template>
## Executive Summary

### Audit Overview

- **Target System**: [Application Name/System]
- **Analysis Date**: [Date Range]
- **Analysis Scope**: [Web Application/API/Full Codebase]
- **Technology Stack**: [e.g., .NET 8, Umbraco CMS, Azure AD B2C, SQL Server, Elasticsearch]

### Risk Assessment Summary

| Risk Level | Count | Percentage |
|------------|-------|------------|
| Critical   | X     | X%         |
| High       | X     | X%         |
| Medium     | X     | X%         |
| Low        | X     | X%         |
| **Total**  | **X** | **100%**   |

### Key Findings

- **Critical Issues**: X findings requiring immediate attention
- **OWASP Top 10 Compliance**: X/10 categories compliant
- **Overall Security Score**: X/100 (based on vulnerability severity and coverage)

---

## Analysis Methodology

### Security Analysis Approach

- **Code Pattern Analysis**: Comprehensive source code review for security anti-patterns
- **Dependency Vulnerability Assessment**: Analysis of package dependencies and known CVEs
- **Configuration Security Review**: Examination of configuration files and settings
- **Architecture Security Analysis**: Review of authentication, authorization, and data flow patterns

### Analysis Coverage

- **Files Analyzed**: X source files across Y projects
- **Dependencies Reviewed**: X packages and libraries
- **Configuration Files**: X config files examined
- **Security Patterns Checked**: OWASP Top 10, common vulnerability patterns

### Analysis Capabilities

- **Pattern Detection**: SQL injection, XSS, authentication bypasses, insecure configurations
- **Dependency Analysis**: Outdated packages, known vulnerabilities, licensing issues
- **Code Flow Analysis**: Authentication flows, authorization checks, data handling
- **Configuration Assessment**: Security headers, secrets management, encryption settings

---

## Security Findings

### Critical Risk Findings

#### C-001: SQL Injection Vulnerability

**Location**: `src/Website.Data/Services/UserService.cs:45`
**Risk Score**: 9.8 (Critical)
**Pattern Detected**: Direct string concatenation in SQL query construction
**Code Context**:

```csharp
var query = $"SELECT * FROM Users WHERE id = {userId}";
```

**Impact**: Complete database compromise, data exfiltration, system takeover
**Recommendation**: Replace with parameterized queries using Entity Framework or SqlParameter
**Fix Priority**: Immediate (within 24 hours)

#### C-002: Authentication Bypass

**Location**: `src/Website.Security/Middleware/AuthMiddleware.cs:67`
**Risk Score**: 9.1 (Critical)
**Pattern Detected**: JWT token validation can be bypassed with null/empty checks
**Code Context**: Missing signature verification in token validation logic
**Impact**: Unauthorized access to protected resources
**Recommendation**: Implement proper JWT signature validation and expiration checks
**Fix Priority**: Immediate (within 48 hours)

### High Risk Findings

#### H-001: Hardcoded Secrets

**Location**: Multiple configuration files and source files
**Risk Score**: 7.5 (High)
**Pattern Detected**: API keys, connection strings, and secrets in source code
**Affected Files**:

- `src/Website.Web/appsettings.json`
- `src/Website.Core/Services/ExternalApiService.cs:23`
**Impact**: Credential compromise, unauthorized system access
**Recommendation**: Move all secrets to secure configuration (Azure Key Vault, environment variables)
**Fix Priority**: Within 1 week

#### H-002: Insufficient Access Controls

**Location**: `src/Website.Core/Controllers/AdminController.cs`
**Risk Score**: 7.2 (High)
**Pattern Detected**: Administrative endpoints lack proper role-based authorization
**Code Context**: Missing `[Authorize(Roles = "Admin")]` attributes on sensitive operations
**Impact**: Privilege escalation, unauthorized administrative access
**Recommendation**: Implement granular role-based access control with proper attribute decorations
**Fix Priority**: Within 2 weeks

### Medium Risk Findings

#### M-001: Cross-Site Scripting (XSS)

**Location**: Multiple view templates and API responses
**Risk Score**: 6.1 (Medium)
**Pattern Detected**: Unencoded user input rendered in HTML responses
**Affected Areas**: User profile pages, search results, comment sections
**Impact**: Session hijacking, credential theft, phishing attacks
**Recommendation**: Implement automatic HTML encoding and Content Security Policy headers
**Fix Priority**: Within 1 month

#### M-002: Insecure Direct Object References

**Location**: `src/Website.Core/Controllers/DocumentController.cs:89`
**Risk Score**: 5.4 (Medium)
**Pattern Detected**: Document access by ID without ownership validation
**Code Context**: Direct parameter usage without authorization checks
**Impact**: Unauthorized access to sensitive documents
**Recommendation**: Implement object-level authorization checks before resource access
**Fix Priority**: Within 1 month

### Low Risk Findings

#### L-001: Missing Security Headers

**Location**: Web server configuration
**Risk Score**: 3.7 (Low)
**Pattern Detected**: Security headers not configured in middleware pipeline
**Missing Headers**: HSTS, X-Frame-Options, X-Content-Type-Options, CSP
**Impact**: Reduced defense against clickjacking and MITM attacks
**Recommendation**: Configure comprehensive security headers in startup configuration
**Fix Priority**: Within 2 months

---

## Architecture Security Assessment

### Authentication & Authorization Analysis

- **Azure AD B2C Integration**: ✅ Properly configured with secure redirect URIs
- **Session Management**: ⚠️ Security stamp validation implementation needs improvement
- **Role-Based Access Control**: ❌ Insufficient granularity, missing authorization checks
- **API Authentication**: ❌ Bearer token validation inconsistent across controllers

### Data Protection Analysis

- **Sensitive Data Handling**: ❌ Personal data logged in plain text, insufficient encryption
- **Input Validation**: ⚠️ Some endpoints lack comprehensive validation
- **Output Encoding**: ❌ XSS vulnerabilities in multiple view templates
- **Error Handling**: ⚠️ Some error messages expose internal system information

### Dependency Security Analysis

- **Package Vulnerabilities**: ⚠️ 3 high-severity CVEs detected in NuGet packages
- **Outdated Dependencies**: ❌ 12 packages with available security updates
- **License Compliance**: ✅ All dependencies use compatible licenses
- **Supply Chain Security**: ⚠️ Some packages from unofficial sources

---

## OWASP Top 10 2021 Compliance Analysis

| Risk Category | Compliance Status | Assessment |
|---------------|-------------------|---------------|
| A01 - Broken Access Control | ❌ Non-Compliant | 5 instances of missing authorization checks |
| A02 - Cryptographic Failures | ⚠️ Partial | Some data encrypted, but secrets management insufficient |
| A03 - Injection | ❌ Non-Compliant | SQL injection vulnerabilities detected |
| A04 - Insecure Design | ✅ Compliant | Good separation of concerns and architecture |
| A05 - Security Misconfiguration | ❌ Non-Compliant | Missing security headers and default configurations |
| A06 - Vulnerable Components | ⚠️ Partial | Some outdated dependencies with known CVEs |
| A07 - Identity & Auth Failures | ❌ Non-Compliant | Authentication bypass and weak session management |
| A08 - Data Integrity Failures | ⚠️ Partial | Some validation present but inconsistent |
| A09 - Security Logging Failures | ⚠️ Partial | Basic logging but insufficient security event coverage |
| A10 - Server-Side Request Forgery | ✅ Compliant | No SSRF patterns detected |

**Overall OWASP Compliance**: 40% (4/10 categories fully compliant)

---

## Technical Recommendations

### Immediate Code Fixes

1. **Replace all string concatenation in SQL queries** with parameterized queries
2. **Remove hardcoded secrets** from source code and configuration files
3. **Add missing authorization attributes** to administrative endpoints
4. **Fix JWT token validation** to include proper signature verification

### Security Enhancements

1. **Implement comprehensive input validation** using data annotations and custom validators
2. **Add automatic HTML encoding** for all user-generated content
3. **Configure security headers** middleware in the application pipeline
4. **Update vulnerable dependencies** to latest secure versions

### Architecture Improvements

1. **Implement centralized secrets management** using Azure Key Vault
2. **Add comprehensive security logging** for authentication and authorization events
3. **Implement rate limiting** for API endpoints
4. **Add automated security testing** to the CI/CD pipeline

---

## Code Remediation Examples

### SQL Injection Fix

**Before (Vulnerable)**:

```csharp
var query = $"SELECT * FROM Users WHERE id = {userId}";
var user = context.Database.SqlQuery<User>(query).FirstOrDefault();
```

**After (Secure)**:

```csharp
var user = context.Users.FirstOrDefault(u => u.Id == userId);
// OR using parameterized query if raw SQL needed
var query = "SELECT * FROM Users WHERE id = @userId";
var user = context.Database.SqlQuery<User>(query, new SqlParameter("@userId", userId)).FirstOrDefault();
```

### Authorization Fix

**Before (Vulnerable)**:

```csharp
[HttpDelete]
public IActionResult DeleteUser(int id)
{
    // No authorization check
    userService.Delete(id);
    return Ok();
}
```

**After (Secure)**:

```csharp
[HttpDelete]
[Authorize(Roles = "Admin")]
public IActionResult DeleteUser(int id)
{
    userService.Delete(id);
    return Ok();
}
```

---

## Risk Mitigation Priorities

### Phase 1: Critical Vulnerability Remediation

- [ ] Fix SQL injection in `UserService.cs:45`
- [ ] Patch authentication bypass in `AuthMiddleware.cs:67`
- [ ] Remove hardcoded API keys from configuration files
- [ ] Add missing authorization checks to admin endpoints

### Phase 2: High Risk Resolution

- [ ] Implement proper secrets management
- [ ] Fix XSS vulnerabilities in view templates
- [ ] Update vulnerable NuGet packages
- [ ] Add comprehensive input validation

### Phase 3: Medium Risk and Configuration

- [ ] Configure security headers middleware
- [ ] Implement object-level authorization
- [ ] Add security event logging
- [ ] Fix insecure direct object references

### Phase 4: Security Hardening

- [ ] Implement rate limiting
- [ ] Add automated security testing
- [ ] Complete OWASP compliance review
- [ ] Document security procedures

---

## Summary

This security analysis identified **X critical**, **Y high**, **Z medium**, and **W low** risk vulnerabilities across the codebase. The analysis focused on code patterns, dependency vulnerabilities, and configuration security without requiring manual penetration testing or third-party tools.

**Key Strengths Identified**:

- Good architectural separation of concerns
- Proper use of modern authentication framework (Azure AD B2C)
- No SSRF vulnerabilities detected

**Critical Areas Requiring Immediate Attention**:

- SQL injection vulnerabilities requiring immediate patching
- Authentication bypass issues
- Hardcoded secrets in source code
- Missing authorization controls
</template>

## Severity Assessment Framework

When determining severity, apply these criteria:

- **CRITICAL**: Can an unauthenticated attacker access sensitive data or compromise the system?
- **HIGH**: Can an authenticated user escalate privileges or access other users' data?
- **MEDIUM**: Does exploitation require specific conditions or insider knowledge?
- **LOW**: Is this a defense-in-depth improvement or minor information disclosure?

## Examples

**Example 1: SQL Injection**

Bad approach:
```javascript
const query = `SELECT * FROM users WHERE email = '${userEmail}'`;
db.query(query);
```

Good approach:
```javascript
const query = 'SELECT * FROM users WHERE email = ?';
db.query(query, [userEmail]);
```

**Example 2: Password Storage**

Bad approach:
```javascript
user.password = md5(password);
```

Good approach:
```javascript
user.password = await bcrypt.hash(password, 12);
```

**Example 3: Authorization Check**

Bad approach:
```javascript
// Only checking authentication, not authorization
if (req.user) {
  return db.getOrder(req.params.orderId);
}
```

Good approach:
```javascript
// Check both authentication and authorization
if (req.user) {
  const order = await db.getOrder(req.params.orderId);
  if (order.userId !== req.user.id) {
    throw new ForbiddenError();
  }
  return order;
}
```

## Best Practices

1. **Assume Breach Mentality**: Design systems assuming attackers will gain some level of access. Implement defense-in-depth with multiple layers of security.

2. **Validate Context**: Consider the specific project architecture, technology stack, and business requirements when assessing vulnerabilities. A vulnerability's severity depends on context.

3. **Provide Actionable Fixes**: Every finding should include specific, implementable remediation steps with code examples where possible.

4. **Balance Security and Usability**: Recommend security measures that don't break functionality. Verify proposed fixes work with the existing architecture.

5. **Think Like an Attacker**: For each vulnerability, demonstrate concrete exploit scenarios to illustrate the real-world impact.

6. **Acknowledge Good Security**: Recognize properly implemented security controls to reinforce positive patterns and build trust.

## Quality Assurance Checklist

Before finalizing a security audit, verify:

- ✓ Have all user input points been identified and traced?
- ✓ Have sensitive data flows been traced end-to-end?
- ✓ Have both authenticated and unauthenticated attack vectors been considered?
- ✓ Are remediation recommendations specific and actionable?
- ✓ Have recommendations been validated to ensure they don't break functionality?
- ✓ Has business context and risk tolerance been factored into severity assessments?

## Context-Aware Analysis

When project-specific context is available in CLAUDE.md files, incorporate:

- **Project Architecture**: Understand security boundaries and trust zones
- **Technology Stack**: Identify framework-specific vulnerabilities and security features
- **Business Logic**: Recognize domain-specific security requirements
- **Compliance Requirements**: Note regulatory constraints (PCI-DSS, HIPAA, GDPR)
- **Existing Security Measures**: Build upon established security patterns

## Communication Guidelines

When reporting findings:
- Be direct and precise about security risks
- Use technical terminology accurately
- Provide concrete exploit scenarios to demonstrate impact
- Include code snippets showing both vulnerable and secure implementations
- Balance thoroughness with clarity - reports should be actionable
- Acknowledge properly implemented security controls
- Escalate critical findings immediately with clear urgency

Remember: The goal is not to criticize but to protect. Every vulnerability found and fixed is a potential breach prevented. Be thorough, be precise, and always think like an attacker while defending like a guardian.
