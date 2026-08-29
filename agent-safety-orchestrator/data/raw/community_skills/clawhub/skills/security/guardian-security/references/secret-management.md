# Secret Management — Reference Guide

Vault storage, environment variables, the never-in-code rules, and the operational
discipline of keeping secrets where they belong.

---

## 1. THE GOLDEN RULE

Secrets live in one of these three places:
1. Environment variables (local dev)
2. Replit Secrets (deployed apps)
3. Password manager (human-accessed credentials)

Secrets NEVER live in:
- Source code (any language)
- Comments
- Chat messages
- Email body
- Docs or READMEs
- URLs
- Log files

---

## 2. SECRET TYPES AND STORAGE

### By Secret Type
```
API KEYS & TOKENS:
  Local dev: .env file (never committed)
  Replit: Replit Secrets
  GitHub Actions: GitHub Secrets
  
ACCOUNT PASSWORDS:
  Where: Password manager (1Password, Bitwarden, etc.)
  NOT: Notepad, spreadsheet, browser password manager for critical accounts
  
WEBHOOK SECRETS:
  Same as API keys — environment variables only
  
PRIVATE KEYS (SSH, certificates):
  Stored in ~/.ssh/ (never in project directories)
  Never committed to version control
  
DATABASE CONNECTION STRINGS:
  Same as API keys — environment variables only
```

---

## 3. THE ENVIRONMENT VARIABLE SYSTEM

### How Secrets Flow (Never Hardcoded)
```
SECRET LIFECYCLE:
  1. Secret created on platform (Stripe, SendGrid, etc.)
  2. Copied to .env (local) or Replit Secrets (deployed)
  3. Application reads from environment at runtime:
     os.environ['SECRET_NAME']
  4. Secret never touches source code
  5. When secret changes: update env, not code

PYTHON LOADING PATTERN:
  from dotenv import load_dotenv
  import os
  
  load_dotenv()  # Loads .env in development
  
  STRIPE_KEY = os.environ['STRIPE_SECRET_KEY']  # Raises if missing
  OPTIONAL_KEY = os.getenv('OPTIONAL_KEY', 'default')  # Returns default if missing

NODE.JS LOADING PATTERN:
  require('dotenv').config();
  const stripeKey = process.env.STRIPE_SECRET_KEY;
  if (!stripeKey) throw new Error('STRIPE_SECRET_KEY required');
```

---

## 4. GITIGNORE CONFIGURATION

### Minimum .gitignore for Any Project
```gitignore
# Environment and secrets
.env
.env.*
!.env.example
*.env
secrets.json
credentials.json
service-account.json

# Python
__pycache__/
*.py[cod]
.Python
venv/
env/
.venv/

# Node.js
node_modules/
npm-debug.log

# IDE
.idea/
.vscode/
*.swp
.DS_Store

# Data (often contains sensitive info)
data/*.json
data/*.csv
*.log
```

---

## 5. SECRET AUDIT PROTOCOL

### Monthly Secret Audit
```
QUESTIONS TO ANSWER:

1. What secrets do we currently have?
   List all credentials in use (not their values — just what they are)
   Example: "Stripe live key, Stripe test key, Gumroad token, SendGrid key..."

2. Where is each secret stored?
   For each: is it ONLY in the secure location? Not also in a doc or email?

3. Who has access to each secret?
   Should anyone be removed? Anyone who needs to be added?

4. When was each secret last rotated?
   Identify any that are overdue for rotation

5. Are there any secrets that should be deleted?
   Old project credentials, unused services, deprecated keys

ACTION: Document in credential-inventory.json (values never stored, just metadata)
```

### Credential Inventory Template (No Values)
```json
{
  "credentials": [
    {
      "name": "Stripe Live Secret Key",
      "service": "Stripe",
      "type": "api_key",
      "risk_level": "HIGH",
      "stored_in": ["Replit Secrets", ".env (local)"],
      "last_rotated": "2024-01-15",
      "next_rotation": "2024-04-15",
      "owner": "Joshua"
    }
  ]
}
```

---

## 6. NEVER-IN-CODE ENFORCEMENT

### Code Review Trigger Words
When reviewing any code, immediately flag if these appear as values (not variable names):
```
Pattern: Actual key/secret values, not variable references

FLAG IMMEDIATELY:
  "sk_live_" anywhere in code → Stripe live key
  "sk_test_" anywhere in code → Stripe test key
  "SG." at start of string → SendGrid key
  "AKIA" at start of string → AWS key
  "ghp_" at start → GitHub PAT
  "pat[A-Za-z0-9]{14}\." → Airtable PAT

AUTOMATIC FAIL IN CODE REVIEW:
  Any variable assigned a string value that matches a known credential pattern
```
