---
name: obscura-privacy
description: >
  Complete reference for the Obscura API — a post-quantum secure intent settlement system with true 
  privacy combining WOTS+ signatures, Shielded Intent Protocol (SIP), stealth addresses, Pedersen 
  commitments, Arcium MPC confidential computing, and Light Protocol ZK Compression.

  Use this skill whenever the user wants to: implement privacy-preserving cryptocurrency transfers, 
  create shielded deposits and withdrawals, integrate with Arcium MPC for confidential computing, 
  use ZK compression for Solana, build privacy pools, implement stealth addresses, or understand 
  post-quantum secure transactions. Also trigger when the user mentions Obscura, privacy vault, 
  shielded transactions, Arcium, ZK compression, WOTS+, or anonymous transfers.
---

# Obscura — Post-Quantum Secure Privacy Platform

Obscura is a post-quantum secure intent settlement system combining:
- **WOTS+** — Winternitz One-Time Signatures for quantum-resistant authorization
- **SIP** — Shielded Intent Protocol for privacy-preserving transactions
- **Stealth addresses** — Unlinkable payments
- **Pedersen commitments** — Hidden amounts
- **Arcium MPC** — Confidential computing with encrypted data
- **Light Protocol ZK Compression** — ~1000x cheaper Solana storage

**Base URL:** `https://api.obscura-app.com`

---

## Quick Orientation

| What you need | Endpoint |
|---|---|
| Deposit to privacy vault | `POST /api/v1/deposit` |
| Withdraw privately | `POST /api/v1/withdraw` |
| Check privacy status | `GET /api/v1/privacy/status` |
| Query vault balance | `POST /api/v1/balance` |

---

## Deployed Contracts

### Solana Devnet
- **Program ID:** `GG9U34H1xXkuzvv8Heoy4UWav5vUgrQFEVwrYMi84QuE`
- **Vault PDA:** `6owJu2yXoPvTbM67XwmRguVRQhCADaswHkAVhVHSvoH7`

### Sepolia Testnet
- **SIPVault:** `0xc4937Ba6418eE72EDABF72694198024b5a3599CC`
- **SIPSettlement:** `0x88dA9c5D9801cb33615f0A516eb1098dF1889DA9`

---

## Privacy Architecture

### The Privacy Problem with Basic Vaults

```
Basic Vault (Vulnerable):
- Deposit: User_A → Vault (User_A visible)
- Withdraw: User_A calls withdraw() → Vault → Recipient
- ❌ User_A visible as withdrawal initiator
- ❌ Vault PDA visible — enables graph tracing
```

### Obscura Solution: Direct Transfer + Off-Chain Balance

```
Obscura (True Privacy):
1. DEPOSIT: User → Vault (pooled, unlinkable)
2. VERIFICATION: Off-chain (Arcium MPC, encrypted)
3. WITHDRAWAL: Relayer → Recipient (direct, NO vault PDA!)
```

**Key insight:** Vault PDA is public but safe because:
- Only receives deposits (never sends withdrawals)
- Direct transfer breaks the link
- Cannot trace depositor → recipient

---

## Core Endpoints

### Health Check

```
GET /health
```

```json
{
  "status": "healthy",
  "services": { "auth": "ready", "aggregator": "ready", "solana": "ready", "evm": "ready" }
}
```

### Privacy Status

```
GET /api/v1/privacy/status
```

Returns Arcium MPC and Light Protocol configuration:

```json
{
  "features": {
    "pedersenCommitments": true,
    "stealthAddresses": true,
    "batchSettlement": true,
    "wotsAuthorization": true,
    "confidentialComputing": true
  },
  "arcium": {
    "configured": true,
    "clusterOffset": "456",
    "version": "v0.6.3",
    "programId": "arcaborPMqYhZbLqPKPRXpBKyCMgH8kApNoxp4cLKg"
  },
  "lightProtocol": {
    "zkCompression": true,
    "compressedPDAs": true,
    "costSavings": "~1000x cheaper storage"
  }
}
```

### Deposit

```
POST /api/v1/deposit
```

**Minimum:** 0.0003 SOL or 0.0003 ETH

**Request:**
```json
{
  "network": "solana-devnet",
  "token": "native",
  "amount": "5000000"
}
```

**Response:**
```json
{
  "success": true,
  "depositNote": {
    "commitment": "0x...",
    "nullifier": "abc123...",      // SECRET — save locally!
    "nullifierHash": "0x...",
    "secret": "def456...",         // SECRET — save locally!
    "amount": "5000000",
    "token": "native",
    "chainId": "solana-devnet"
  },
  "txHash": "5YiJ1SCm3C...",
  "vaultAddress": "6owJu2yXoPvTbM67XwmRguVRQhCADaswHkAVhVHSvoH7"
}
```

⚠️ **IMPORTANT:** Save `nullifier` and `secret` — required for withdrawal!

### Query Balance

```
POST /api/v1/balance
```

Query Arcium cSPL off-chain balance (Solana only):

**Request:**
```json
{
  "commitment": "b4083a81a64f7bf5...",
  "chainId": "solana-devnet"
}
```

**Response:**
```json
{
  "success": true,
  "balance": "1200000000",
  "pendingBalance": "0",
  "confidentialAccount": "5599a875...",
  "encrypted": true,
  "deposits": 1,
  "withdrawals": 0
}
```

### Withdraw

```
POST /api/v1/withdraw
```

**Request:**
```json
{
  "commitment": "0x...",
  "nullifierHash": "0x...",
  "recipient": "ECYks1hYG3xVRyYpwaesqGrkpj9ZQh1R6S3T3KXDrhrA",
  "amount": "5000000",
  "chainId": "solana-devnet"
}
```

**Response:**
```json
{
  "success": true,
  "requestId": "3ae33176109d737e",
  "status": "pending"
}
```

After relayer executes (Solana with ZK Compression):
```json
{
  "success": true,
  "requestId": "3ae33176109d737e",
  "txHash": "5fmG66Xz8Uyv5Sfu6QfPUYYzcNaLPfgWVSZV5rijKmJKQ...",
  "status": "completed",
  "zkCompressed": true,
  "compressionSignature": "3Ag8rUJB6tswcHubJ62aspEkJFf3QvShwCJPa4jgUsX..."
}
```

---

## Deposit Note Structure

```typescript
interface DepositNote {
  commitment: string;    // Public — hash of secrets, stored on-chain
  nullifier: string;     // SECRET — random 32 bytes, proves ownership
  nullifierHash: string; // Public — hash(nullifier), replay protection
  secret: string;        // SECRET — random 32 bytes, part of commitment
  amount: string;        // Amount deposited
  token: string;         // Token type
  chainId: string;       // Chain identifier
  timestamp: number;      // Deposit time
}
```

---

## Relayer Service

### Fee Structure (Tiered)

| Amount | Fee Rate | Example |
|---|---|---|
| 0-10 SOL/ETH | 0.10% | 10 SOL → 0.01 SOL |
| 10-100 SOL/ETH | 0.08% | 100 SOL → 0.08 SOL |
| 100-1000 SOL/ETH | 0.06% | 1000 SOL → 0.6 SOL |
| 1000+ SOL/ETH | 0.05% | 10000 SOL → 5 SOL |

**Minimum fees:** 0.0001 SOL, 0.00001 ETH

---

## Supported Chains

| Chain | Chain ID | Status |
|---|---|---|
| Solana Devnet | `solana-devnet` | ✅ Active |
| Sepolia | `sepolia` | ✅ Active |
| Ethereum | `ethereum` | 🔜 Soon |
| Polygon | `polygon` | 🔜 Soon |

---

## Privacy Levels

| Level | Description | Use Case |
|---|---|---|
| `transparent` | All data visible | Debugging, auditing |
| `shielded` | Maximum privacy (default) | Private transfers |
| `compliant` | Viewing keys enabled | Regulatory compliance |

---

## Arcium MPC Integration

### Capabilities

| Use Case | Description |
|---|---|
| Confidential Solver Auctions | Fair solver selection without bid visibility |
| Intent Encryption | Private amounts prevent front-running |
| Batch Optimization | Encrypted routing optimization |
| Compliance Disclosure | Sealed viewing keys for regulators |

### Version
- **Arcium:** v0.6.3, cluster offset 456
- **SDK:** @arcium-hq/client v0.6.1

### View Transactions
- **Arcium Explorer:** `https://explorer.arcium.com/tx/<mxe_id>?cluster=devnet`

---

## ZK Compression (Light Protocol)

### Cost Savings

| Storage Type | 1000 Records | Cost |
|---|---|---|
| Traditional | 1000 accounts | ~2 SOL |
| ZK Compressed | 1 Merkle tree | ~0.002 SOL |

### ETH Privacy
ZK Compression is **disabled for ETH** to prevent cross-chain data correlation that could break privacy.

---

## Complete Flow Example

### Private SOL Transfer

```bash
# Step 1: Deposit
curl -X POST https://api.obscura-app.com/api/v1/deposit \
  -H "Content-Type: application/json" \
  -d '{"network": "solana-devnet", "token": "native", "amount": "5000000"}'
# Save the depositNote! (nullifier and secret)

# Step 2: Request withdrawal (later, different device/IP)
curl -X POST https://api.obscura-app.com/api/v1/withdraw \
  -H "Content-Type: application/json" \
  -d '{
    "commitment": "0x...",
    "nullifierHash": "0x...",
    "recipient": "ECYks1hYG3xVRyYpwaesqGrkpj9ZQh1R6S3T3KXDrhrA",
    "amount": "5000000",
    "chainId": "solana-devnet"
  }'
```

---

## Error Codes

| HTTP | Error | Description |
|---|---|---|
| 400 | Missing required fields | Request validation failed |
| 400 | Nullifier already used | Double-spend attempt |
| 400 | Amount too low | Below minimum (0.0003) |
| 404 | Not found | Resource not found |
| 500 | Relayer execution failed | On-chain tx failed |

---

## Additional Resources

### Reference Files

For cryptographic details, advanced patterns, and integration guides:

- **`references/deposit-withdraw-flows.md`** — Step-by-step flow documentation
- **`references/arcium-integration.md`** — Arcium MPC detailed integration
- **`references/cryptographic-primitives.md`** — WOTS+, Pedersen, stealth addresses
