# Secret Detection Guide

## Common Secrets to Protect

- **API Keys** - AWS, Azure, GCP, etc.
- **Database Credentials** - Password, connection string
- **SSH Keys** - Private key files
- **Tokens** - JWT, bearer tokens, OAuth tokens
- **Encryption Keys** - Master keys
- **Webhooks** - Webhook URLs with secrets
- **PII** - Personal identifying information

## Patterns to Detect

```
password.*=
api.?key.*=
secret.*=
token.*=
bearer.+
authorization.+
aws_access_key
aws_secret_access_key
-----BEGIN.*PRIVATE KEY-----
mongodb.*://
```

## Prevention

1. **Use environment variables** - Don't hardcode secrets
2. **.gitignore secrets** - Add to .gitignore
3. **Use git-secrets** - Prevent committing secrets
4. **Rotate credentials** - If accidentally exposed
5. **Use vaults** - HashiCorp Vault, AWS Secrets Manager

## Tools

- **git-secrets** - Native git hook
- **TruffleHog** - Scans git history
- **detect-secrets** - Python tool
- **gitleaks** - Fast, accurate detection
- **Snyk** - Integrated secret detection

## If Secret is Exposed

1. **Rotate immediately** - Generate new secret
2. **Revoke access** - If possible
3. **Audit logs** - Check who had access
4. **Update references** - All places using secret
5. **Communicate** - Alert team/users if needed
6. **Review commits** - Check git history

## .gitignore for Secrets

```
.env
.env.local
.env.*.local
.aws/
.ssh/
.kube/
config/secrets.yml
credentials.json
```

## Environment Variables

```bash
# Use environment variables instead of files
export DATABASE_PASSWORD=$(aws secretsmanager get-secret-value --secret-id db-pass)
export API_KEY=$(vault kv get -field=key secret/api)
```
