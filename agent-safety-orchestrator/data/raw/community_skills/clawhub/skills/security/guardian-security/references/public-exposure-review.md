# Public Exposure Review — Reference Guide

Reviewing anything before it goes public for security risks, credential leaks,
private information, and content that could cause legal or reputational harm.

---

## 1. WHAT GETS A PUBLIC EXPOSURE REVIEW

A public exposure review is required before:
- Any code repository is made public
- Any document is published or shared externally
- Any product file is uploaded to a platform
- Any configuration file is shared
- Any script or tool is distributed as a product

---

## 2. THE PUBLIC EXPOSURE REVIEW CHECKLIST

### Code/Scripts Going Public
```
CREDENTIALS SCAN:
- [ ] No API keys or tokens (grep -r "sk_\|SG\.\|pat[A-Z]" .)
- [ ] No passwords or secrets
- [ ] No internal URLs or IPs that reveal infrastructure
- [ ] .env NOT included (verify with: ls -la | grep .env)
- [ ] .env.example IS included (no real values)
- [ ] .gitignore configured correctly

SENSITIVE DATA SCAN:
- [ ] No customer data or PII in code
- [ ] No internal business metrics hardcoded
- [ ] No file paths that reveal home directory structure
- [ ] No comments with sensitive information

SECURITY WEAKNESSES:
- [ ] No insecure patterns that could be exploited (SQL injection, etc.)
- [ ] No backdoors, debug modes, or test bypasses
- [ ] Error messages don't expose system details
```

### Documents/Files Going Public
```
CONTENT REVIEW:
- [ ] No personal information (home address, phone numbers not meant to be public)
- [ ] No private business information (unreleased product plans, revenue details)
- [ ] No information about third parties shared without their consent
- [ ] No copyrighted content without proper license

METADATA REVIEW:
- [ ] Document metadata cleaned (File → Properties in many apps)
  (Can contain author name, company, edit history, comments)
- [ ] Hidden layers/objects removed (Photoshop, Illustrator)
- [ ] Track changes removed (Word documents)
- [ ] Comments removed (if they contain internal notes)
```

---

## 3. PRE-PUBLICATION SECURITY SCAN

### Automated Scan Before Any Public Repository
```bash
# Run before making any repo public or before PR review

# Scan for common secret patterns
echo "=== Scanning for potential credentials ==="
grep -r --include="*.py" --include="*.js" --include="*.sh" --include="*.env" \
  -E "(sk_live|sk_test|pk_live|SG\.|AKIA|ghp_|pat[A-Za-z0-9]{14}|password\s*=\s*['\"][^'\"]{8})" \
  . 2>/dev/null | grep -v ".git"

# Check for .env files not in .gitignore
echo "=== Checking for .env files ==="
find . -name "*.env" -not -path "./.git/*" -not -name ".env.example"

# Check git config for private info
echo "=== Git remote URL ==="
git remote -v

echo "=== Scan complete ==="
```

---

## 4. WHAT TO DO WHEN SENSITIVE DATA IS FOUND

### If Found Before Publishing
```
Stop. Don't publish.
Remove the sensitive data.
Verify removal.
Re-scan.
Then publish.
```

### If Found After Publishing (Already Public)
```
IMMEDIATE:
  1. If credentials: Rotate them NOW
  2. Make the repository private immediately
  3. Notify Hutch: SECURITY ESCALATION
  4. Document: What was exposed, when, for how long

THEN:
  5. Remove from git history (git-filter-repo)
  6. Force push
  7. Re-verify
  8. If credentials were live: check platform for unauthorized use
```
