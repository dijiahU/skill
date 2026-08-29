# Dependency Management Best Practices

## Security Checks

### npm audit

```bash
# Run audit
npm audit

# Show JSON output
npm audit --json

# Fix automatically
npm audit fix

# Fix with major version updates
npm audit fix --force
```

Severity levels:
- **Critical** - Immediate security threat
- **High** - Significant security issue
- **Moderate** - Some risk
- **Low** - Minor issue

### Regular Updates

```bash
# Check outdated packages
npm outdated

# Update to latest minor/patch
npm update

# Update specific package
npm update package-name@latest
```

## Dependency Lock Files

### npm-lock.json (or yarn.lock, package-lock.json)

```bash
# Always commit lock file
git add package-lock.json

# Don't edit manually - use npm commands
npm install      # Respects lock file
npm update       # Updates and regenerates lock file
```

Benefits:
- Reproducible installs
- Prevents version mismatches
- Security: Know exactly what's installed

## Avoiding Common Issues

### 1. Too Many Dependencies
```
❌ 500 dependencies (slow, large bundle, more attack surface)
✓ < 100 production dependencies
```

### 2. Outdated Dependencies
```bash
# Use npm audit regularly
npm audit

# Update lock file in CI
npm ci  # Uses lock file exactly
npm install --production  # Production dependencies only
```

### 3. Breaking Changes

When updating major versions:
```bash
# Check changelog
npm info package-name
npm view package-name CHANGELOG

# Test thoroughly
npm test

# Update gradually
npm update package@latest
```

## Dependency Size

```bash
# Check bundle size
npm install webbundlesize  # or npm-bundle
npm-bundle size lodash

# Track dependencies
npm list --depth=0

# Find duplicates
npm list d

# Analyze
npm install webpack-bundle-analyzer
```

## CI/CD Best Practices

```bash
# Use exact versions in CI
npm ci  # Cleaner installs

# Lock staging and production
npm install --save-exact

# Regular audit runs
npm audit --audit-level=high
```
