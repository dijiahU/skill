---
name: moca-credential-verifier
description: Verifies user credentials on Moca chain testnet via AIR agent sessions. Use when a user wants to verify a credential, list available verification programs, or check credential compliance.
---

# Moca Credential Verifier

## Purpose

This skill teaches an agent how to browse available verification programs, show numeric options, and trigger credential verification through `moca-chain-api` in **query_match mode**.

After receiving a `compliant` result, install/use the standalone `moca-proof-skill` repository and run the `moca-proof` skill to complete the program and fetch MoCat progression.

This skill starts **after** the agent key already exists and the handoff bundle is available.

## Provided Scripts

Use the provided scripts first. Do not scaffold a new project or rewrite signing/request logic from scratch unless the requested action is unsupported. Treat all files in this skill bundle as read-only reference tooling.

Task mapping:

- create a scoped session -> `scripts/moca-create-session.mjs`
- list/browse verification programs -> `scripts/moca-list-programs.mjs`
- trigger credential verification (`query_match` mode) -> `scripts/moca-verify-by-agent.mjs`
- poll verification status -> `scripts/moca-poll-status.mjs`

Before first use, run `node <script> --help` to inspect supported parameters.

## Required Inputs

Expect a handoff bundle equivalent to:

```json
{
  "userId": "...",
  "walletId": "...",
  "privyAppId": "...",
  "abstractAccountAddress": "0x...",
  "airApiAgentSignUrl": "https://.../v2/wallet/agent-sign",
  "partnerId": "8ab60850-bdfa-4e48-8afa-d67a3d715224"
}
```

The agent must also already have access to its own P-256 private key.
If `partnerId` is missing, scripts default to the sandbox partner ID above.

## Sandbox Defaults

```json
{
  "airApiUrl": "https://air.api.sandbox.air3.com/v2",
  "mocaChainApiUrl": "https://api.sandbox.mocachain.org/v1",
  "vpApiUrl": "https://vp.api.sandbox.moca.network/v1",
  "mocaProofApiUrl": "https://proof.api.sandbox.moca.network/v1",
  "partnerId": "8ab60850-bdfa-4e48-8afa-d67a3d715224"
}
```

These are hardcoded as defaults in the scripts. Override via CLI flags, environment variables, or `.air-wallet-config.json`.

## Project-Level Defaults

It is allowed to create or update a project-level `.air-wallet-config.json` file in the working directory. Use that file for defaults such as endpoint URLs, partner ID, and key paths. Do not store defaults by editing files inside this skill bundle.

Example additions for this skill:

```json
{
  "airApiUrl": "https://air.api.sandbox.air3.com/v2",
  "mocaChainApiUrl": "https://api.sandbox.mocachain.org/v1",
  "vpApiUrl": "https://vp.api.sandbox.moca.network/v1",
  "mocaProofApiUrl": "https://proof.api.sandbox.moca.network/v1",
  "partnerId": "8ab60850-bdfa-4e48-8afa-d67a3d715224"
}
```

## Config Resolution Order

All provided scripts resolve configuration in this order:

1. CLI flags
2. Environment variables
3. `.air-wallet-config.json`
4. Hardcoded sandbox defaults

## Credential Verification Flow

### Step 1: Create a Scoped Session

```bash
node scripts/moca-create-session.mjs --program-id <programId>
```

Calls `POST {airApiUrl}/auth/agent/session` with:
- `signedMessage`: fresh agent-signed message
- `scope`: `"<programId>,<partnerId>"`

Returns an `accessToken` used as Bearer token for all subsequent calls.

### Step 2: List Verification Programs

```bash
node scripts/moca-list-programs.mjs
# optional personalized mode
node scripts/moca-list-programs.mjs --access-token <token>
```

Calls `GET {vpApiUrl}/vp/mocaproof/search?page=1&limit=20`.

- Without token: public listing mode
- With token: personalized listing mode (user verified metadata and filtering)

Results are paginated. The script shows a summary of the first page. Use `--page <n>` to fetch more.

The list output includes numeric options in this format:

- Option index: `[1]`, `[2]`, ...
- Tier index inside option: `(1.1)`, `(1.2)`, ...

### Step 3: Trigger Verification (query_match mode)

```bash
node scripts/moca-verify-by-agent.mjs --access-token <token> --program-id <programId> --issue-url <issueUrl>
```

Always pass `--issue-url` with the `issueUrl` from the selected program's listing output. When verification returns `no_vc`, the script prints the issuance link so the user can obtain the credential.

Calls `POST {mocaChainApiUrl}/credentials/verify-by-agent` with:
- `programId` in the body
- `responseMode: "query_match"` in the body
- Bearer `accessToken` in the Authorization header

The response is normalized using the rules below.

### Optional: Poll VP Status

```bash
node scripts/moca-poll-status.mjs --access-token <token>
```

Use this when you want to inspect status progression separately from the default flow.

## After Verification Succeeds

When verification returns `compliant`, use the **moca-proof** skill from the standalone `moca-proof-skill` repository to:

```bash
npx skills add MocaNetwork/moca-proof-skill
```

1. Complete the program via `moca-complete-program.mjs`
2. Fetch MoCat progression via `moca-get-mocat.mjs`

Pass the same `accessToken` and `programId` to the proof skill scripts.

## Verify Response Normalization

The `verify-by-agent` endpoint returns inconsistent response shapes. Normalize exactly as:

- `verified: true` -> `compliant`
- `verified: false` + `reason: "NO_CREDENTIAL"` -> `no_vc`
- `verified: false` + `reason: "NOT_COMPLIANT"` -> `non_compliant`
- `verified: false` + `status: "NON_COMPLIANT"` -> `non_compliant`
- `verified: false` + `status` present -> `status_bucket:<status>`
- `verified: false` + only `code` present -> `unknown_failure_code:<code>`
- `verified: "pending"` -> `processing`
- Any other shape -> `unknown_response` (print raw payload)

Known `status` values:

- `NO_EXIST`: user has no credential for this program
- `WAIT_ONCHAIN`: credential is being published on-chain
- `EXPIRE`: credential has expired
- `WAIT_REMOVE`: credential is being revoked
- `REMOVE`: credential has been revoked
- `NON_COMPLIANT`: credential does not meet requirements

## Terminal Messaging

- Print numeric options and tiers before verification attempts
- Print `Verifying....` on each verification attempt
- If non-compliant, print `Sorry, not compliant` and end
- When verify succeeds in query_match mode: print `OK, verified, <verifier name> is processing your data`

## Non-Negotiable Rules

- Always generate a **fresh** `signedMessage` for every session request
- Never reuse an old `signedMessage`
- Use Bearer `accessToken` from scoped session for all downstream API calls
- Never modify files inside this installed skill bundle
- If a custom script is truly required, create it outside the skill directory

## Failure Handling

- Unknown public key: the key was removed, wrong, or never registered. Stop and ask for a new handoff bundle.
- Expired signed message: rebuild a fresh `signedMessage` and retry once.
- `unknown_failure_code`: print the raw code and payload for debugging; do not retry automatically.
- `unknown_response`: print the full raw response; do not retry automatically.
