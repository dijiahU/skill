# Credential Storage Architecture

How GPC stores and protects credentials across platforms.

## Storage hierarchy

```
User-level (per OS user)
├── ~/.config/gpc/
│   ├── config.json          # User config (may reference key paths)
│   └── audit.log            # Command audit trail
├── ~/.cache/gpc/
│   └── tokens/              # Cached access tokens (auto-expire)
└── OS Keychain              # OAuth refresh tokens (encrypted)

Project-level (per repository)
└── .gpcrc.json              # Project config (NEVER contains secrets)
```

## What goes where

| Data | Storage | Persists | Encrypted |
|------|---------|----------|-----------|
| Service account key path | config.json or env var | Yes | No (path only) |
| Service account JSON content | `GPC_SERVICE_ACCOUNT` env var | Session | No |
| OAuth refresh token | OS keychain | Yes | Yes (OS-managed) |
| Access token (cached) | `~/.cache/gpc/tokens/` | 1 hour | No (short-lived) |
| App package name | `.gpcrc.json` or config | Yes | No (not sensitive) |
| Audit entries | `audit.log` | Yes | No |

## Security boundaries

### Safe to commit (.gpcrc.json)

```json
{
  "app": "com.example.app",
  "output": "json",
  "plugins": ["@gpc-cli/plugin-ci"]
}
```

### Never commit

- Service account JSON key files
- Access tokens
- OAuth credentials
- Private keys

### File permissions

GPC sets appropriate permissions on creation:

| File | Permission | Reason |
|------|-----------|--------|
| `config.json` | 0600 | May contain key file paths |
| `tokens/*.json` | 0600 | Contains access tokens |
| `audit.log` | 0600 | Contains command history |

## OS keychain integration

| OS | Backend | Tool |
|----|---------|------|
| macOS | Keychain Access | `security` CLI |
| Linux | libsecret / GNOME Keyring | `secret-tool` |
| Windows | Windows Credential Manager | `cmdkey` |

Fallback when no keychain is available: `~/.config/gpc/credentials.json` (file-based, less secure).

## CI/CD credential patterns

### GitHub Actions (recommended)

```yaml
env:
  GPC_SERVICE_ACCOUNT: ${{ secrets.PLAY_SA_KEY }}
```

Secrets are:
- Encrypted at rest (NaCl sealed box)
- Not visible in logs (auto-masked)
- Not available in PRs from forks

### GitLab CI

```yaml
variables:
  GPC_SERVICE_ACCOUNT: $PLAY_SA_KEY  # Protected variable
```

### Environment variable formats

`GPC_SERVICE_ACCOUNT` accepts:
1. File path: `/path/to/key.json`
2. Raw JSON: `{"type": "service_account", ...}`

GPC auto-detects which format is provided.

## Token lifecycle

```
Service Account Key
  │
  ├─ resolveAuth() loads key
  │
  ├─ getAccessToken()
  │   ├─ Check cache → return if valid
  │   ├─ JWT grant → Google OAuth2
  │   └─ Cache new token (3600s TTL)
  │
  └─ Token expires → auto-refresh on next call
```

Access tokens are short-lived (1 hour) and auto-refreshed. Even if a cached token is leaked, it expires quickly.
