# Service Account Key Rotation

Procedures for rotating service account keys safely.

## Manual rotation (recommended every 90 days)

### Step 1: Create new key

```bash
# Google Cloud Console:
# IAM & Admin → Service Accounts → [your SA] → Keys → Add Key → JSON
# Download the new key file
```

### Step 2: Test locally

```bash
# Authenticate with new key
gpc auth login --service-account /path/to/new-key.json

# Verify
gpc doctor
gpc releases list --app com.example.app
```

### Step 3: Update CI secrets

#### GitHub Actions

```bash
# Using gh CLI
gh secret set PLAY_SA_KEY < /path/to/new-key.json
```

#### GitLab CI

```bash
# Settings → CI/CD → Variables → Update PLAY_SA_KEY
```

### Step 4: Verify CI

Trigger a test pipeline to confirm the new key works in CI.

### Step 5: Delete old key

```bash
# Google Cloud Console:
# IAM & Admin → Service Accounts → [your SA] → Keys → Delete old key
```

### Step 6: Clean up

```bash
# Clear local token cache
rm -rf ~/.cache/gpc/tokens/

# Securely delete old key file
rm -P /path/to/old-key.json  # macOS secure delete
shred -u /path/to/old-key.json  # Linux secure delete
```

## Multi-environment rotation

When you have separate keys for dev/staging/production:

```bash
# Rotate one environment at a time
# 1. Create new prod key
# 2. Update prod CI secret
# 3. Verify prod pipeline
# 4. Delete old prod key
# 5. Repeat for staging
# 6. Repeat for dev
```

Never rotate all environments at once — if something goes wrong, you want at least one working key.

## Overlap period

Google allows multiple active keys per service account (up to 10). Use this for zero-downtime rotation:

```
Day 0: Create new key (old key still active)
Day 1: Update CI secrets with new key
Day 2: Verify all pipelines pass
Day 3: Delete old key
```

## Automated rotation with scripts

```bash
#!/bin/bash
# rotate-key.sh — automated key rotation

SA_EMAIL="gpc-sa@project-id.iam.gserviceaccount.com"
PROJECT="project-id"
NEW_KEY_PATH="/tmp/new-key.json"

# Create new key
gcloud iam service-accounts keys create "$NEW_KEY_PATH" \
  --iam-account="$SA_EMAIL" \
  --project="$PROJECT"

# Test new key
GPC_SERVICE_ACCOUNT=$(cat "$NEW_KEY_PATH") gpc doctor
if [ $? -ne 0 ]; then
  echo "New key failed verification!"
  exit 1
fi

# Update GitHub secret
gh secret set PLAY_SA_KEY < "$NEW_KEY_PATH"

echo "Key rotated. After verifying CI, delete old keys:"
gcloud iam service-accounts keys list \
  --iam-account="$SA_EMAIL" \
  --project="$PROJECT"

# Clean up
rm -P "$NEW_KEY_PATH"
```

## Key hygiene checklist

- [ ] Keys are not committed to git (check with `git log --all -p -- '*.json' | grep private_key`)
- [ ] Keys are rotated every 90 days
- [ ] Old keys are deleted promptly
- [ ] CI secrets are updated before deleting old keys
- [ ] Token cache is cleared after rotation
- [ ] Only necessary permissions are granted to service accounts
