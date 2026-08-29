# Obscura Deposit & Withdraw Flows

Step-by-step integration patterns for privacy-preserving transfers.

---

## Deposit Flow

### Step 1: Client Generates Deposit Note

```typescript
interface DepositParams {
  amount: bigint;      // In base units (lamports/smallest unit)
  token: 'native' | 'usdc' | 'usdt';
  chainId: 'solana-devnet' | 'sepolia';
}

interface DepositNote {
  commitment: string;    // Public: hash(secrets + amount + token + chainId)
  nullifier: string;    // SECRET: 32 random bytes
  nullifierHash: string; // Public: hash(nullifier)
  secret: string;       // SECRET: 32 random bytes
  amount: string;       // Stringified amount
  token: string;
  chainId: string;
  timestamp: number;
}

// Generate commitment (client-side)
function generateDepositNote(params: DepositParams): DepositNote {
  const secret = randomBytes(32);
  const nullifier = randomBytes(32);
  const nullifierHash = sha256(nullifier);
  const commitment = sha256(secret + nullifier + params.amount + params.token + params.chainId);
  
  return {
    commitment,
    nullifier: nullifier.toString('hex'),
    nullifierHash: nullifierHash.toString('hex'),
    secret: secret.toString('hex'),
    amount: params.amount.toString(),
    token: params.token,
    chainId: params.chainId,
    timestamp: Date.now()
  };
}
```

### Step 2: User Signs Deposit Transaction

```typescript
// Frontend: User signs with wallet (backend never sees private key)
const depositNote = generateDepositNote({
  amount: 5_000_000n,  // 0.005 SOL
  token: 'native',
  chainId: 'solana-devnet'
});

// Save note locally (user's device only)
localStorage.setItem('obscuraDeposit', JSON.stringify(depositNote));

// User signs and sends transaction via wallet
const txHash = await wallet.signAndSend(depositTransaction);
```

### Step 3: Backend Records Deposit

```typescript
// POST /api/v1/deposit
const response = await fetch('https://api.obscura-app.com/api/v1/deposit', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    network: 'solana-devnet',
    token: 'native',
    amount: '5000000'
  })
});

const { depositNote, txHash, vaultAddress } = await response.json();
```

---

## Withdraw Flow

### Step 1: Load Saved Deposit Note

```typescript
// User loads their saved deposit note
const depositNote = JSON.parse(localStorage.getItem('obscuraDeposit'));

// Verify note is valid
if (!depositNote.nullifier || !depositNote.secret) {
  throw new Error('Invalid deposit note - missing secrets');
}
```

### Step 2: Request Withdrawal from Relayer

```typescript
// POST /api/v1/withdraw
const response = await fetch('https://api.obscura-app.com/api/v1/withdraw', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    commitment: depositNote.commitment,
    nullifierHash: depositNote.nullifierHash,
    recipient: 'ECYks1hYG3xVRyYpwaesqGrkpj9ZQh1R6S3T3KXDrhrA',
    amount: depositNote.amount,
    chainId: depositNote.chainId
  })
});

const { requestId, status } = await response.json();

// Wait for relayer to execute
```

### Step 3: Check Withdrawal Status

```typescript
// GET /api/v1/relayer/request/:requestId
const statusResponse = await fetch(
  `https://api.obscura-app.com/api/v1/relayer/request/${requestId}`
);

const result = await statusResponse.json();
// result.status: 'pending' | 'processing' | 'completed' | 'failed'
// result.txHash: Final transaction hash
```

---

## Complete Transfer Flow (Two-Parties)

### Scenario: Alice sends to Bob privately

```typescript
// ALICE SIDE
async function aliceDeposit(amount: bigint) {
  // 1. Generate deposit note
  const note = generateDepositNote({
    amount,
    token: 'native',
    chainId: 'solana-devnet'
  });
  
  // 2. Sign deposit transaction
  const txHash = await aliceWallet.signDeposit(note);
  
  // 3. Save note securely
  secureStorage.save(note);
  
  // 4. Send note to Bob (secure channel)
  await sendNoteToBob(note);
  
  return txHash;
}

// BOB SIDE
async function bobWithdraw(note: DepositNote, bobAddress: string) {
  // 1. Verify note structure
  if (!note.commitment || !note.nullifierHash) {
    throw new Error('Invalid note');
  }
  
  // 2. Request withdrawal
  const response = await fetch('https://api.obscura-app.com/api/v1/withdraw', {
    method: 'POST',
    body: JSON.stringify({
      commitment: note.commitment,
      nullifierHash: note.nullifierHash,
      recipient: bobAddress,
      amount: note.amount,
      chainId: note.chainId
    })
  });
  
  // 3. Wait for relayer
  const { requestId } = await response.json();
  return requestId;
}
```

---

## Balance Query Flow

### Query Vault Balance (Arcium cSPL)

```typescript
async function queryVaultBalance(commitment: string) {
  const response = await fetch('https://api.obscura-app.com/api/v1/balance', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      commitment,
      chainId: 'solana-devnet'  // Only Solana supported
    })
  });
  
  const result = await response.json();
  
  if (!result.success) {
    throw new Error(result.error);
  }
  
  return {
    balance: BigInt(result.balance),
    pendingBalance: BigInt(result.pendingBalance),
    confidentialAccount: result.confidentialAccount,
    deposits: result.deposits,
    withdrawals: result.withdrawals
  };
}

// Display in human-readable format
const vault = await queryVaultBalance(commitment);
const solBalance = Number(vault.balance) / 1e9;
console.log(`Vault Balance: ${solBalance.toFixed(6)} SOL`);
```

---

## Error Handling

### Common Errors

```typescript
async function handleDeposit(amount: bigint) {
  try {
    const response = await fetch('/api/v1/deposit', {
      method: 'POST',
      body: JSON.stringify({ amount })
    });
    
    if (!response.ok) {
      const error = await response.json();
      
      switch (error.error) {
        case 'Amount too low':
          // Show minimum deposit warning
          console.log(`Minimum deposit: 0.0003 SOL`);
          break;
        case 'Vault balance insufficient':
          // Show vault funding required
          break;
        default:
          throw new Error(error.error);
      }
    }
    
    return await response.json();
  } catch (err) {
    // Handle network errors
    console.error('Deposit failed:', err);
  }
}

async function handleWithdraw(note: DepositNote) {
  try {
    const response = await fetch('/api/v1/withdraw', {
      method: 'POST',
      body: JSON.stringify({
        commitment: note.commitment,
        nullifierHash: note.nullifierHash,
        recipient: getRecipient(),
        amount: note.amount,
        chainId: note.chainId
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      
      if (error.error === 'Nullifier already used') {
        throw new Error('Note already spent!');
      }
      
      throw new Error(error.error);
    }
    
    return await response.json();
  } catch (err) {
    // Handle withdrawal errors
    console.error('Withdrawal failed:', err);
  }
}
```

---

## Security Best Practices

### Client-Side Security

```typescript
// ✅ DO: Use secure storage
const secureNote = {
  nullifier: secureRandom(32).toString('hex'),
  secret: secureRandom(32).toString('hex'),
  commitment: sha256(secureNote.secret + secureNote.nullifier + amount),
  nullifierHash: sha256(secureNote.nullifier)
};

// ❌ DON'T: Log secrets
console.log('Nullifier:', nullifier); // NEVER

// ❌ DON'T: Send secrets over network
fetch('/api/log', { body: JSON.stringify({ nullifier }) }); // NEVER

// ✅ DO: Verify before withdrawal
function validateNote(note: DepositNote): boolean {
  return (
    note.nullifier?.length === 64 &&
    note.secret?.length === 64 &&
    note.commitment?.length === 64
  );
}
```

### Server-Side Security

```typescript
// ✅ DO: Never log or store nullifier/secret
// Backend should only receive:
interface WithdrawalRequest {
  commitment: string;     // Public hash
  nullifierHash: string; // Public hash (not nullifier)
  recipient: string;
  amount: string;
  chainId: string;
}

// ❌ DON'T: Backend receives nullifier directly
interface BadRequest {
  nullifier: string; // WRONG - security breach!
}
```
