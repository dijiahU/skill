---
name: security-checklist
description: Security rules for code generation including secret handling, credential storage, and environment files. Follow when generating code that handles secrets, credentials, or environment configuration.
type: guideline
---

# Security Checklist for AI Coding Assistants

**This is a strict guideline.** Follow these rules exactly.

Critical security rules to follow when generating or modifying code.

## Never Commit These Files

**Environment files with actual values:**
```
.env
.env.local
.env.development
.env.production
.env.test
.env.*
```

**Always commit templates (no actual values):**
```
.env_TEMPLATE
.env.example
```

**Required gitignore patterns:**
```gitignore
# Environment files
.env
.env.*
!.env_TEMPLATE
!.env.example

# AWS credentials
.aws/credentials
.aws/config

# SSH keys
*.pem
id_rsa
id_ed25519
```

## Never Hardcode Secrets

**❌ Never do this:**
```typescript
const apiKey = 'sk-1234567890abcdef';
const dbPassword = 'mypassword123';
const awsAccessKey = 'AKIAIOSFODNN7EXAMPLE';
```

**✅ Always do this:**
```typescript
// Runtime: Load from environment
const apiKey = process.env.API_KEY;
if (!apiKey) throw new Error('API_KEY not set');

// Infrastructure: Reference from Secrets Manager/SSM
const secret = secretsmanager.Secret.fromSecretNameV2(
  this, 'ApiKey', 
  '/project/prod/api-key'
);
```

## Secret Storage

**Use appropriate AWS services:**
- **Secrets Manager**: Passwords, API keys, database credentials, tokens
- **SSM Parameter Store (SecureString)**: Sensitive configuration values
- **SSM Parameter Store (String)**: Non-sensitive configuration

**Never:**
- Hardcode secrets in code
- Commit secrets to git
- Log secrets to console/CloudWatch
- Pass secrets in URLs or query parameters

## Token Handling in Frontend

**❌ Never expose sensitive tokens:**
```typescript
// Don't put backend API keys in frontend code
const token = 'secret-backend-token';
```

**✅ Use appropriate auth methods:**
```typescript
// Use public API keys or user-specific tokens
const publicKey = process.env.NEXT_PUBLIC_API_KEY; // Public, safe to expose
const userToken = cookies.get('auth-token'); // User-specific, from auth flow
```

## Environment Variable Validation

**Always validate required secrets exist:**
```typescript
// At application startup
const required = ['DATABASE_URL', 'API_KEY', 'JWT_SECRET'];
const missing = required.filter(key => !process.env[key]);

if (missing.length > 0) {
  throw new Error(`Missing required secrets: ${missing.join(', ')}`);
}
```

## Code Review Checklist

Before committing, verify:
- [ ] No hardcoded passwords, API keys, or tokens
- [ ] No `.env` files with actual values
- [ ] Gitignore includes all secret file patterns
- [ ] Environment variables validated at startup
- [ ] Secrets loaded from Secrets Manager/SSM in infrastructure
- [ ] No secrets in console.log or error messages
- [ ] Frontend only uses public API keys or user-specific tokens

## When in Doubt

**Stop and ask** if:
- You're about to commit a file with "key", "secret", "password", or "token" in the content
- You're hardcoding any credential or sensitive value
- You're unsure if a value should be in git or environment variables

**Default to secure**: If uncertain whether something is sensitive, treat it as a secret.

---

**Related**:
- [Core Principles - Security Baseline](../CORE_PRINCIPLES.md#8-security-baseline)
- [SSM Parameter Store Configuration](../patterns/configuration/ssm-parameter-store-configuration.md)

---

## Progressive Improvement

If the developer corrects a behavior that this skill should have prevented, suggest a specific amendment to this skill to prevent the same correction in the future.
