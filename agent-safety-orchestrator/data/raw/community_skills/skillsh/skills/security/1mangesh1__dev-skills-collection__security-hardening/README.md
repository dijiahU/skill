# Security Hardening Quick Start

Build secure applications by implementing core security practices.

## OWASP Top 10 Summary

| # | Vulnerability | Prevention |
|---|---------------|-----------|
| 1 | Broken Access Control | Check permissions always |
| 2 | Cryptographic Failures | Use TLS, encrypt data |
| 3 | Injection | Use parameterized queries |
| 4 | Insecure Design | Threat modeling upfront |
| 5 | Misconfiguration | Remove defaults, harden |
| 6 | Vulnerable Deps | Keep packages updated |
| 7 | Auth Failures | Strong auth + MFA |
| 8 | Data Integrity | Verify package/code signatures |
| 9 | Logging Failures | Log security events |
| 10 | SSRF | Validate URLs/redirects |

## Critical Practices

### Input Validation
```javascript
// ❌ Bad
const id = req.query.id;
const user = db.query(`SELECT * FROM users WHERE id = ${id}`);

// ✅ Good
const id = parseInt(req.query.id, 10);
const user = db.query('SELECT * FROM users WHERE id = ?', [id]);
```

### Secure Headers
```
Content-Security-Policy: default-src 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000
```

### Dependency Scanning
```bash
npm audit
pip check
cargo audit
```

## Quick Security Checklist

- [ ] All inputs validated
- [ ] Parameterized queries used
- [ ] HTTPS/TLS enabled
- [ ] Secrets in environment variables
- [ ] Dependencies updated
- [ ] Error messages sanitized
- [ ] Security headers set
- [ ] Rate limiting enabled
- [ ] Logging captures security events
- [ ] MFA enabled for admin access

## Common Vulnerabilities

| Type | Example | Fix |
|------|---------|-----|
| SQL Injection | `WHERE id = ${input}` | Use parameterized queries |
| XSS | `<div>${userName}</div>` | Escape HTML output |
| CSRF | No token verification | Add CSRF tokens |
| CORS | `* allow all` | Specify allowed origins |
| Exposed Secrets | Secrets in git | Use env variables |

## Tools

- `npm audit` / `pip check` - Dependency scanning
- OWASP ZAP - Web app scanning
- Snyk - Vulnerability database
- SonarQube - Code quality & security
- TruffleHog - Secret detection

## Standards

- OWASP Top 10
- CWE/SANS Top 25
- NIST Cybersecurity Framework
- PCI DSS (payment systems)

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Cheat Sheets](https://cheatsheetseries.owasp.org/)
- [CWE Top 25](https://cwe.mitre.org/top25/)

## See Also

- SKILL.md - Detailed vulnerability patterns
- metadata.json - Security tool references
