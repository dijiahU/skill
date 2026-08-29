---
name: secure-vault
description: Secure encrypted secrets storage with local key file protection. Inspired by ZeroClaw's encrypted secrets with XOR + local key file.
---

# Secure Vault

Secure encrypted secrets storage with local key file protection. Inspired by ZeroClaw's encrypted secrets with XOR + local key file.

## Setup

No additional setup required. Generates encryption key on first use.

## Usage

### Store a Secret

```bash
{baseDir}/secure-vault.js set --name "api_key" --value "secret-value"
```

### Retrieve a Secret

```bash
{baseDir}/secure-vault.js get --name "api_key"
```

### List All Secrets

```bash
{baseDir}/secure-vault.js list
```

### Delete a Secret

```bash
{baseDir}/secure-vault.js delete --name "api_key"
```

### Export Secrets (Encrypted)

```bash
{baseDir}/secure-vault.js export --output "vault-backup.enc"
```

### Import Secrets

```bash
{baseDir}/secure-vault.js import --path "vault-backup.enc"
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--name` | Secret name/identifier | Required for set/get/delete |
| `--value` | Secret value | - |
| `--path` | File path for import/export | - |
| `--output` | Output file path | - |
| `--key` | External encryption key (optional) | Auto-generated |

## Encryption

Uses XOR encryption with a local key file (similar to ZeroClaw):
- Key file stored at `~/.config/agent/vault.key` (mode 0600)
- Secrets encrypted before storage
- Key file never leaves the local system

## Security Features

- **Local-only key**: Encryption key never stored with secrets
- **File permissions**: Key file created with 0600 permissions
- **No plaintext storage**: All secrets stored encrypted
- **Secure deletion**: Overwrites data before deletion

## Response Format

```json
{
  "success": true,
  "name": "api_key",
  "encrypted": true
}
```

## When to Use

- Storing API keys securely
- Managing credentials for multiple services
- Backup and restore encrypted secrets
- Secure configuration storage
- Managing secrets across environments
