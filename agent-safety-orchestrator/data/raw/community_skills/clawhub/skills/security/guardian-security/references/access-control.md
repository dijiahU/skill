# Access Control — Reference Guide

Who has access to what, principle of least privilege, and managing account access
for a small business where multiple agents interact with external platforms.

---

## 1. THE PRINCIPLE OF LEAST PRIVILEGE

Give every system and every person the minimum access required to do their job.
Not "might need someday" access. The minimum for TODAY's job.

If an agent only reads Airtable records: give read-only access, not admin.
If a script only sends emails: give send permission, not admin.
If a webhook only needs to verify signatures: don't give it database access.

---

## 2. TLC ACCESS INVENTORY

### Platform Access Matrix
```
STRIPE:
  Who has admin access: Joshua (owner)
  Who has read access: Analyst Agent (via API)
  Webhook access: Restricted to webhook secret verification only
  API key scope: Use restricted keys where Stripe allows

GUMROAD:
  Who has admin access: Joshua (owner)
  Who has product access: Publisher Agent (via API)
  API access: Access token with minimum required scope

AIRTABLE:
  Who has admin access: Joshua (owner)
  Who has write access: Closer Agent (CRM updates), Publisher Agent
  Who has read access: Analyst Agent, Navigator Agent
  Key type: Personal Access Token with scoped permissions

SENDGRID:
  Who has admin access: Joshua (owner)
  Who has send access: Email automation scripts only
  API key scope: "Mail Send" permission only (not admin)

GITHUB:
  Who has admin access: Joshua (owner)
  Who has write access: Architect Agent (code changes)
  Key type: Fine-grained PAT with specific repo access

REPLIT:
  Who has admin access: Joshua (owner)
  Deployment access: Managed through Replit secrets
```

---

## 3. API KEY SCOPE BEST PRACTICES

### Creating Scoped API Keys
```
STRIPE:
  Instead of using the full secret key everywhere:
  Create "Restricted Keys" in Stripe Dashboard for specific use cases:
    Read-only key for reporting: No write permissions
    Webhook validation key: Only signature verification
    
  How to create restricted key:
    Stripe Dashboard → Developers → API Keys → Create restricted key
    Select only the permissions needed

SENDGRID:
  Create API keys with specific permissions:
    "Mail Send" only: Can't modify lists, templates, or settings
    Don't use the "Full Access" key for automated sending
    
  How to create: SendGrid → Settings → API Keys → Create API Key

AIRTABLE:
  Personal Access Tokens support specific scopes:
    data.records:read - read records
    data.records:write - create/update/delete records
    schema.bases:read - view table structures
    
  Create separate tokens for read-only vs. write access
```

---

## 4. SHARED ACCOUNT SECURITY

### When Multiple Agents/Tools Access Same Account
```
PROBLEM: Multiple agents with full access = larger attack surface
SOLUTION: Separate credentials per use case where possible

CURRENT PRACTICE AT TLC:
  Each script/agent uses its own API key (not a shared "master" key)
  Allows:
    Tracking which key is being used (audit trail)
    Rotating one key without affecting others
    Revoking a compromised key without breaking everything
    
NAMING CONVENTION FOR KEYS:
  STRIPE_REPORTING_KEY (for analytics/reporting)
  STRIPE_WEBHOOK_SECRET (for webhook validation)
  AIRTABLE_READ_ONLY_KEY (for reporting scripts)
  AIRTABLE_CRM_WRITE_KEY (for CRM update scripts)
```

---

## 5. ACCESS REVIEW CHECKLIST

### Monthly Access Review
```
REVIEW QUESTIONS:
- [ ] Who has admin access to each platform? (Should only be Joshua)
- [ ] Are there any API keys for services we no longer use? (Revoke them)
- [ ] Are there any API keys with broader than necessary scope? (Restrict them)
- [ ] Have any team changes (new agents, retired agents) occurred that require access changes?
- [ ] Are all active API keys documented and attributed to specific uses?

QUARTERLY TASKS:
- [ ] Review and rotate any credentials that haven't been rotated in 90+ days
- [ ] Remove any "just in case" access grants
- [ ] Verify that automated scripts are still using appropriate scope credentials
```

---

## 6. ACCOUNT SECURITY HARDENING

### Platform Account Security
```
FOR EACH CRITICAL PLATFORM ACCOUNT:
  ✅ Strong, unique password (use a password manager)
  ✅ Two-factor authentication enabled
  ✅ Recovery codes stored securely (not just in email)
  ✅ Notification settings: alert on new login, new API key created
  ✅ Regular review of active sessions
  ✅ Business email used (not personal email) for account registration
  
2FA PRIORITY:
  CRITICAL: Stripe, Gumroad, GitHub, email provider, Replit
  HIGH: Airtable, SendGrid, any platform with API keys
  MEDIUM: Social media accounts with publishing access
```
