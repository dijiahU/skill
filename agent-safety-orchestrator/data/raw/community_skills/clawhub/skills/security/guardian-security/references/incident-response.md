# Incident Response — Reference Guide

What to do when something goes wrong — data breach, credential exposure,
unauthorized access, or any security incident requiring immediate action.

---

## 1. INCIDENT CLASSIFICATION

### Severity Levels
```
SEV 1 — CRITICAL (Act within 15 minutes):
  - Payment credentials compromised (Stripe key exposed)
  - Customer data breach (unauthorized access to customer PII)
  - Active unauthorized access to any account
  - Malicious code deployed to production
  
SEV 2 — HIGH (Act within 1 hour):
  - Non-payment API key compromised
  - Credential accidentally committed to git
  - Potential data exposure (unsure of scope)
  - Platform account security alert
  
SEV 3 — MEDIUM (Act within 24 hours):
  - Security configuration weakness discovered
  - Non-critical credential potentially exposed
  - Third-party service security incident that may affect us
  
SEV 4 — LOW (Address in next 48 hours):
  - Minor security improvement opportunity
  - Outdated dependency with medium vulnerability
```

---

## 2. INCIDENT RESPONSE PROTOCOL

### The STOP Protocol (First 15 Minutes)
```
S — STOP: Stop all potentially affected activity
  If a script is running that may be using compromised credentials: stop it
  If a deployment is in progress: halt it
  If in doubt: stop the thing, ask questions after

T — TELL: Notify Hutch immediately
  Message format:
  "🚨 Security Incident: [Brief description]
  Severity: [SEV 1/2/3]
  What happened: [2 sentences]
  What I've done so far: [Any immediate actions taken]
  What needs to happen now: [Specific ask from you]"

O — OBSERVE: Document what you know RIGHT NOW
  What exactly happened?
  When was it first detected?
  What systems/data may be affected?
  Any evidence available?

P — PROTECT: Prevent further exposure
  Rotate compromised credentials
  Revoke suspicious access
  Disable affected services if necessary
```

### Full Incident Response Phases
```
PHASE 1 — DETECT (0-15 min):
  Incident identified
  Initial classification (what severity?)
  Guardian notified + Hutch notified

PHASE 2 — CONTAIN (15-60 min):
  Stop the bleeding
  Rotate compromised credentials
  Revoke unauthorized access
  Preserve evidence (don't delete logs)

PHASE 3 — ASSESS (1-4 hours):
  What data was accessed?
  How long did the incident last?
  What's the full scope?
  Is there ongoing risk?

PHASE 4 — REMEDIATE (1-7 days):
  Fix the root cause
  Verify the fix
  Update security controls to prevent recurrence

PHASE 5 — RECOVER (Days to weeks):
  Restore normal operations
  Validate that affected systems are clean
  
PHASE 6 — LEARN:
  Root cause analysis
  Update procedures
  Document for future reference
```

---

## 3. CREDENTIAL EXPOSURE RESPONSE

### When a Key Is Exposed
```
STEP 1 (Immediate): Generate new credential
  Go to the platform NOW
  Create a new API key/token
  
STEP 2 (Within 5 min): Update all uses
  Update Replit Secrets
  Update any .env files
  Update any other places this key is used
  
STEP 3 (Within 10 min): Revoke old credential
  Delete/revoke the old key
  Confirm it's no longer valid (test it)
  
STEP 4 (Within 30 min): Check for abuse
  Stripe: Check for unexpected API calls or charges
  Gumroad: Check for unexpected product/listing changes
  Any platform: Check activity logs for unusual access
  
STEP 5 (Within 24 hours): Remove from git history
  If key was committed to git:
  Use git-filter-repo or BFG Repo Cleaner to remove from history
  Force push (requires authorization)
  Note: The key is still compromised even if removed from history
  Anyone who cloned/forked before removal still has it
  
STEP 6: Document and improve
  How did this happen?
  What prevents it next time?
  Update checklist or automation to catch it earlier
```

---

## 4. INCIDENT REPORT TEMPLATE

```markdown
# Security Incident Report

**Incident ID:** INC-[YYYYMMDD]-[NNN]
**Date/Time Detected:** [ISO timestamp]
**Detected By:** Guardian Agent
**Severity:** SEV [1/2/3/4]
**Status:** [Open / Contained / Resolved]

## What Happened
[Specific description of the incident]

## Timeline
- [Time]: [Event]
- [Time]: [Event]
- [Time]: [Action taken]

## Scope
- Systems/data affected: [Specific list]
- Duration of exposure: [Estimated]
- Customer data involved: [Yes/No — if Yes, describe]

## Actions Taken
1. [Action]
2. [Action]

## Root Cause
[Why this happened]

## Remediation
[How it was fixed]

## Prevention Measures
[What prevents this from happening again]

## Lessons Learned
[Key takeaways for the team]
```

---

## 5. BREACH NOTIFICATION CONSIDERATIONS

### When We May Need to Notify Customers
```
If customer PII was exposed:
  - Email addresses
  - Purchase history
  - Any combination that identifies them
  
NOTIFICATION THRESHOLDS:
  Definite notification: Customer data was accessed by unauthorized party
  Possible notification: Significant uncertainty about access scope
  No notification needed: Security weakness discovered and fixed without exposure
  
NOTIFICATION REQUIREMENTS:
  GDPR: 72 hours to supervisory authority (if European customers affected)
  CCPA: "Expedient" notification (if California customers affected)
  General: Best practice is prompt, honest notification
  
For TLC at current scale: Consult with Hutch on any breach involving customer data.
No notification sent without Hutch's explicit approval.
```
