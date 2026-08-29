---
name: credentials-agent
skill: credentials
description: Manages AES-256-GCM encrypted secrets — add, retrieve, list, delete, and rotate named credentials stored at ~/.aibtc/credentials.json.
---

# Credentials Agent

Manages the encrypted credential store for the AIBTC skill suite. Stores and retrieves arbitrary named secrets — API keys, tokens, passwords, and URLs — encrypted at rest with AES-256-GCM and per-credential PBKDF2 key derivation. No wallet is required; the store uses its own master password. Use this agent to seed credentials before running workflows that depend on external API keys.

## Prerequisites

- No wallet required — the credential store is fully independent of the wallet system
- A master password must be chosen before the first `add` call (not persisted — must be supplied each time)
- `get`, `delete`, and `rotate-password` require at least one credential already in the store

## Decision Logic

| Goal | Subcommand |
|------|-----------|
| Store a new secret | `add` — encrypts value with the master password |
| Update an existing secret | `add` with the same `--id` — overwrites the encrypted value |
| Retrieve a secret value | `get` — decrypts and returns the plaintext value |
| Audit stored secrets | `list` — returns metadata only, no decryption |
| Remove a secret | `delete` — requires password verification + `--confirm DELETE` |
| Change master password | `rotate-password` — re-encrypts all credentials atomically |

## Safety Checks

- The master password is never written to disk — always pass via `--password` flag or env var substitution
- Never hardcode the master password in scripts; use `$CRED_PASS` or similar env var
- The `get` subcommand prints the plaintext value in JSON output — treat output as sensitive
- `delete` is irreversible — verify the credential ID via `list` before deleting
- `rotate-password` decrypts all credentials with the old password before writing any changes; it aborts if any credential fails to decrypt, preserving the original store

## Error Handling

| Error message | Cause | Fix |
|--------------|-------|-----|
| "Credential not found: <id>" | ID does not exist in the store | Run `list` to see available IDs; check spelling |
| "Decryption failed — invalid password or corrupted credential data" | Wrong master password | Verify the password; the store cannot be recovered without it |
| "Confirmation required: pass --confirm DELETE" | `--confirm` flag missing or wrong | Pass `--confirm DELETE` exactly |
| "New password must be at least 8 characters" | `--new-password` too short | Use a password of 8 or more characters |

## Output Handling

- `add`: check `success: true` and record `id`, `label`, `category` for reference
- `get`: extract the `value` field for use in downstream commands; avoid logging it
- `list`: use `id` field values as `--id` arguments in `get` or `delete`; `count` confirms how many secrets are stored
- `delete`: check `success: true` and `deleted` field to confirm which credential was removed
- `rotate-password`: check `count` to verify all credentials were re-encrypted

## Example Invocations

```bash
# Store a Hiro API key encrypted with the master password
bun run credentials/credentials.ts add --id hiro-api-key --value "hiro_abc123" --password $CRED_PASS --label "Hiro API Key" --category api-key

# Retrieve and print the decrypted value
bun run credentials/credentials.ts get --id hiro-api-key --password $CRED_PASS

# List all stored credential IDs (no decryption)
bun run credentials/credentials.ts list
```
