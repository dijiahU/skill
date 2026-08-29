# Secret Management Best Practices

## Vault Systems

### HashiCorp Vault
```bash
# Store secret
vault kv put secret/my-app db-password=secret123

# Retrieve
vault kv get secret/my-app

# Dynamic secrets
vault read database/creds/my-role  # Time-limited creds
```

### AWS Secrets Manager
```bash
# Store secret
aws secretsmanager create-secret --name my-db-secret --secret-string '{"password":"secret"}'

# Retrieve
aws secretsmanager get-secret-value --secret-id my-db-secret
```

## Local Development

```bash
# .env file (never commit)
DATABASE_PASSWORD=local_dev_password
API_KEY=dev_api_key

# Load in application
from dotenv import load_dotenv
load_dotenv()
password = os.getenv('DATABASE_PASSWORD')
```

## CI/CD Secrets

GitHub:
```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy
        env:
          DATABASE_PASSWORD: ${{ secrets.DATABASE_PASSWORD }}
        run: ./deploy.sh
```

GitLab:
```yaml
deploy:
  script:
    - deploy.sh
  variables:
    DATABASE_PASSWORD: $DATABASE_PASSWORD  # Masked
```

## Code Review

Never accept PRs with:
- Hardcoded credentials
- Unmasked API keys
- Private keys
- Database passwords

## Audit & Rotation

```bash
# Find exposed secrets in git
git log -p | grep -i "password\|secret\|key"

# Rotate secrets regularly
# - Database passwords: monthly
# - API keys: quarterly
# - SSL certificates: yearly
```
