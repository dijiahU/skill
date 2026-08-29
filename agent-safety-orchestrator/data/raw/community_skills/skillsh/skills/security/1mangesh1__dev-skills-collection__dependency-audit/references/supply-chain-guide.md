# Supply Chain Security

## Vulnerability Assessment

### SCA Tools (Software Composition Analysis)

- **npm audit** - Built-in, checks against NPM security DB
- **Snyk** - Advanced vulnerability detection
- **OWASP Dependency-Check** - Most comprehensive
- **Black Duck** - Enterprise scanning

### Example npm audit output
```
npm notice found 3 vulnerabilities

┌─────────────────────────────────────────────────────────────┐
│ Critical  │ High  │ Moderate  │ Low                             │
│ 0         │ 1     │ 2         │ 0                               │
└─────────────────────────────────────────────────────────────┘

The json dependency has a high severity vulnerability.
Upgrade to: json@2.0.0 or later.
```

## Dependency Tree

```
Your App
├── express@4.18.0
│   ├── body-parser@1.20.0
│   │   └── bytes@3.1.0 (3 vulns)
│   └── cookie
├── lodash@4.17.0 (1 vuln) 
└── axios@1.0.0
```

## Prevention Strategies

1. **Minimize Dependencies** - Each adds risk
2. **Use Lock Files** - npm-lock.json
3. **Regular Audits** - Weekly or in CI
4. **Keep Updated** - Patch versions immediately
5. **Vendor Review** - Understand what you're adding
6. **Monitor Published** - Watch for new vulnerabilities

## CVE Database

Common Vulnerabilities and Exposures:

```
CVE-2021-23567: Lodash vulnerable to prototype pollution
https://nvd.nist.gov/vuln/detail/CVE-2021-23567
Affected: lodash < 4.17.21
Fix: npm update lodash
```
