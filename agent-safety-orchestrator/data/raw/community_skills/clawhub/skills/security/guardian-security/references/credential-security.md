# Credential Security — Reference Guide

API keys, tokens, passwords — storage, rotation, exposure prevention, and the
protocols that keep the company's secrets actually secret.

---

## TABLE OF CONTENTS
1. The Credential Security Fundamentals
2. Types of Credentials at TLC
3. Secure Storage Methods
4. Credential Rotation Protocol
5. Exposure Detection
6. Handling Exposed Credentials
7. Credential Audit Checklist
8. Common Credential Mistakes

---

## 1. THE CREDENTIAL SECURITY FUNDAMENTALS

### The Three Laws of Credential Security
```
LAW 1: Credentials never appear in source code
  This includes:
    - Hardcoded in Python/JS/any language
    - In comments
    - In configuration files committed to git
    - In README examples
    - In test files
  
LAW 2: Credentials are never transmitted insecurely
  This means:
    - Never in URL query strings (visible in logs)
    - Never in email body
    - Never in chat messages (even "private" ones)
    - Never in error messages or logs
    - Always over HTTPS

LAW 3: Credentials have the minimum scope required
  Don't use admin credentials for read-only operations
  Don't use production credentials for testing
  Create purpose-specific keys where platforms allow
```

---

## 2. TYPES OF CREDENTIALS AT TLC

### Credential Inventory
```
PAYMENT PROCESSING:
  Stripe Secret Key (sk_live_xxx): HIGH RISK — full API access
  Stripe Publishable Key (pk_live_xxx): MEDIUM RISK — limited scope
  Stripe Webhook Secret: HIGH RISK — webhook validation
  
PLATFORM APIS:
  Gumroad Access Token: HIGH RISK — product and sales access
  Airtable Personal Access Token (pat_xxx): MEDIUM RISK — CRM data
  SendGrid API Key: HIGH RISK — email sending
  OpenClaw API Key: HIGH RISK — agent platform

INFRASTRUCTURE:
  GitHub Personal Access Token: HIGH RISK — code repository
  Replit deploy tokens: HIGH RISK — production deployment
  Firebase Service Account JSON: HIGH RISK — database access
  
ACCOUNTS (password):
  Gumroad account: HIGH RISK
  Amazon KDP account: HIGH RISK
  Stripe account: HIGH RISK
  
RISK LEVELS:
  HIGH: If compromised, direct financial loss or data breach possible
  MEDIUM: If compromised, service disruption or data access possible
  LOW: If compromised, minor inconvenience only
```

---

## 3. SECURE STORAGE METHODS

### Storage by Environment
```
LOCAL DEVELOPMENT:
  Use: .env file in project root
  Protect: Add .env to .gitignore (MANDATORY)
  Load with: python-dotenv (Python) or dotenv (Node.js)
  
  .env format:
    STRIPE_SECRET_KEY=sk_live_xxxxx
    GUMROAD_ACCESS_TOKEN=xxxxxxxx
    
  .gitignore MUST contain:
    .env
    .env.*
    !.env.example
    *.env

REPLIT DEPLOYMENT:
  Use: Replit Secrets (encrypted, not in code)
  Access via: os.environ['KEY_NAME']
  Never: Use .env files in Replit (not needed, use Secrets)

SHARED SCRIPTS (run by multiple agents):
  Use: Environment variables injected at runtime
  Never: Pass credentials as function arguments in logs
  
VERIFYING SECRETS ARE SET:
  def require_env(name: str) -> str:
      value = os.environ.get(name)
      if not value:
          raise EnvironmentError(f"Required environment variable missing: {name}")
      return value
```

### The .env.example Pattern
```bash
# .env.example — COMMIT THIS FILE
# Copy to .env and fill in real values — NEVER commit .env

# Stripe
STRIPE_SECRET_KEY=sk_live_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_live_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_secret_here

# Gumroad
GUMROAD_ACCESS_TOKEN=your_token_here

# Airtable
AIRTABLE_API_KEY=patYourKey.xxx
AIRTABLE_BASE_ID=appYourBaseId

# Email
SENDGRID_API_KEY=SG.your_key_here
```

---

## 4. CREDENTIAL ROTATION PROTOCOL

### When to Rotate Credentials
```
MANDATORY ROTATION (do immediately):
  - Any credential that may have been exposed (code, chat, email)
  - Any credential in a repository that was made public (even briefly)
  - After any team member with access leaves
  - After any suspected security incident

SCHEDULED ROTATION (preventive):
  HIGH RISK credentials: Every 90 days
  MEDIUM RISK credentials: Every 180 days
  LOW RISK credentials: Annually
  
  Note: At TLC's current stage, focus on mandatory rotation.
  Scheduled rotation is best practice — implement when capacity allows.
```

### Rotation Procedure
```
FOR EACH CREDENTIAL TO ROTATE:

STEP 1: Generate new credential first (don't delete old one yet)
  Reason: Prevents service interruption if new key fails

STEP 2: Update all places that use the old credential
  Local .env files
  Replit Secrets
  Any other deployment configs

STEP 3: Verify new credential works
  Run a test operation that uses the credential
  Confirm it works in production context

STEP 4: Revoke/delete old credential
  Do this LAST, not first

STEP 5: Document the rotation
  Update credential inventory (not with the actual key, just metadata):
    Credential: Stripe Secret Key
    Last rotated: [Date]
    Next rotation due: [Date]
    Rotated by: Guardian Agent
    Reason: Scheduled rotation
```

---

## 5. EXPOSURE DETECTION

### Pre-Commit Scanning
```bash
# Scan working directory for potential credential exposure before committing
# Run this before ANY git commit

# Simple grep scan:
git diff HEAD | grep -iE "(api.?key|secret|password|token|auth)\s*[=:]\s*['\"][^'\"]{8,}"

# More comprehensive scan:
git diff HEAD | grep -iE "(sk_live|pk_live|sk_test|SG\.|pat[A-Za-z0-9]{14}\.|AKIA|ghp_)"

# Check all files being staged:
git diff --cached | grep -iE "(sk_live|sk_test|SG\.|pat[A-Za-z0-9])"
```

### GitHub Secret Scanning
```
GitHub automatically scans for known credential formats.
If you see a "Secret scanning alert":
  1. STOP. Don't commit or push anything else.
  2. Assume the secret is compromised.
  3. Rotate the secret immediately.
  4. Then address how to remove it from git history if needed.
```

---

## 6. HANDLING EXPOSED CREDENTIALS

### Incident Response: Credential Exposure
```
WHEN A CREDENTIAL MAY HAVE BEEN EXPOSED:

IMMEDIATE (Within 15 minutes):
  1. Rotate the exposed credential NOW
     Don't wait to assess impact — rotate first
     Impact assessment comes AFTER rotation
  2. Notify Hutch: "Potential credential exposure — [which credential] — rotating now"

WITHIN 1 HOUR:
  3. Assess the exposure:
     How long was it exposed?
     Who could have seen it?
     In what context (public repo, private message, etc.)?
  4. Check for unauthorized use:
     Platform logs (Stripe: check for unexpected charges/access)
     API logs (any unexpected calls?)
  5. If unauthorized use detected → escalate immediately

WITHIN 24 HOURS:
  6. Document the incident
  7. Implement prevention measure (why did this happen? what prevents recurrence?)
```

---

## 7. CREDENTIAL AUDIT CHECKLIST

### Run Monthly
```
FOR EACH HIGH-RISK CREDENTIAL:
- [ ] Is it stored only in secure locations (env vars, not code)?
- [ ] Is it in .gitignore? (verify .gitignore exists and contains .env)
- [ ] When was it last rotated?
- [ ] Is the rotation due? (> 90 days for high-risk)
- [ ] Is the scope minimum necessary?
- [ ] Are there any unused credentials that should be deleted?

REPOSITORY SCAN:
- [ ] Search repo for any hardcoded credentials: 
      grep -r "sk_live\|sk_test\|SG\.\|pat[A-Z]" --include="*.py" --include="*.js" .
- [ ] Verify .gitignore includes .env patterns
- [ ] Check git log for any accidentally committed secrets

PLATFORM AUDIT:
- [ ] Remove API keys for services we no longer use
- [ ] Verify each active API key has a known, documented use
- [ ] Ensure no shared/team credentials (each service has its own key)
```

---

## 8. COMMON CREDENTIAL MISTAKES

### Mistakes That Lead to Credential Exposure

**Mistake 1: Hardcoding for "just testing"**
```python
# "Temporary" hardcoded key that gets committed
API_KEY = "sk_test_abc123"  # NEVER do this
```
Fix: Use os.getenv() even for test keys. There is no "temporary" in git history.

**Mistake 2: Credentials in comments**
```python
# API key: sk_live_abc123 (this is the production key)
# VISIBLE IN GIT HISTORY FOREVER
```
Fix: Never put credentials in comments. Store them only in env vars.

**Mistake 3: Printing credentials in debug logs**
```python
logger.debug(f"Connecting with key: {api_key}")  # EXPOSED IN LOGS
```
Fix: Never log credential values. Log "Key: [SET]" or "Key: [FIRST 4 CHARS]..."

**Mistake 4: .env committed by accident**
Warning signs: `.env` appears in `git status` as untracked
Fix: Add to .gitignore BEFORE first commit. If already committed: immediate incident response.

**Mistake 5: Using prod credentials for development**
Fix: Platform sandboxes and test keys exist for a reason. Use them.
Stripe: sk_test_ for development
Gumroad: Use staging environment if available
