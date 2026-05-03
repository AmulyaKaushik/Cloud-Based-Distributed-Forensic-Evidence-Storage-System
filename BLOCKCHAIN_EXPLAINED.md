# Blockchain in Forensic Evidence Manager - Simple Explanation

## What is a Blockchain? (Simple Version)

Imagine you have a **notebook where you write down everything that happens** in your evidence lab:
- "Alice uploaded a file at 2pm"
- "Bob verified evidence at 3pm"
- "Charlie downloaded a file at 4pm"

Now, if someone tries to **cheat by changing an old entry**, you want to know immediately.

**A blockchain is like a special notebook where:**
1. You write entries (called "transactions" or "blocks")
2. Each entry is **mathematically locked** to the previous one
3. If anyone tries to change an old entry, the lock breaks and you can see the tampering

**That's it! That's what a blockchain does.**

---

## How Does the Lock Work?

Think of it like a **chain of sealed envelopes**:

```
Envelope 1 (Block 0):
┌─────────────────────────┐
│ Action: LOGIN           │
│ User: admin             │
│ Time: 2025-01-01 10:00  │
│ Seal: A1B2C3D4          │ ← Special code for THIS envelope
└─────────────────────────┘
           ↓
Envelope 2 (Block 1):
┌─────────────────────────────────────────┐
│ Action: UPLOAD                          │
│ User: police_officer                    │
│ Time: 2025-01-01 10:15                  │
│ Previous Seal: A1B2C3D4  ← Points back   │
│ Seal: E5F6G7H8          ← to previous   │
└─────────────────────────────────────────┘
           ↓
Envelope 3 (Block 2):
┌─────────────────────────────────────────┐
│ Action: VERIFY                          │
│ User: forensic_analyst                  │
│ Time: 2025-01-01 10:30                  │
│ Previous Seal: E5F6G7H8  ← Points back   │
│ Seal: I9J0K1L2          ← to previous   │
└─────────────────────────────────────────┘
```

**What happens if someone tries to cheat?**

If someone changes Block 1 from "UPLOAD" to "DELETE":
- The seal `E5F6G7H8` becomes invalid (doesn't match the changed content)
- Block 2 still points to the old seal `E5F6G7H8`
- This **mismatch proves tampering!**

---

## Real Technical Details (But Still Simple)

### What's the "Seal"?

The seal is created using something called **SHA-256** (a mathematical function):
- Input: All the data in the block
- Output: A unique 64-character code (like `a1b2c3d4e5f6...`)
- **Magic:** Even changing ONE letter in the data creates a completely different code

Example:
```
Input:  "ACTION:UPLOAD USER:alice TIME:2025-01-01"
Output: a7f3e2c8b1d4a9f3e2c8b1d4a9f3e2c8b1d4a9f3e2c8b1d4a9f3e2c8b1d4

Change ONE letter:
Input:  "ACTION:UPLOAD USER:alice TIME:2025-01-02"  ← Only "02" changed
Output: 9k2m5p1x7q8r9s3t2u1v4w5x6y7z8a9b0c1d2e3f4g5h6i7j8k9l0m1n2o3p4
        ↑ COMPLETELY DIFFERENT!
```

### Who Signs the Blocks?

Imagine you also **sign each envelope with a special pen that only you have** (called your private key):
- Only you can create that signature
- Everyone else can verify it's your signature using a public key you share
- If someone tries to fake your signature, it won't match

In this project:
- Each block is signed with an **Ed25519 private key**
- The public key is shared so auditors can verify

---

## How It Works in This Project (Step by Step)

### Step 1: Something Happens (An Action)

```
Alice uploads a file called "evidence.pdf"
```

### Step 2: It Gets Logged to the Database

The app records this in PostgreSQL:
```
audit_logs table:
┌─────────────────────────────────────────┐
│ ID: 101                                 │
│ Username: alice                         │
│ Action: UPLOAD                          │
│ Filename: evidence.pdf                  │
│ Timestamp: 2025-05-03 14:30:15         │
│ Status: success                         │
└─────────────────────────────────────────┘
```

### Step 3: It Also Gets Added to the Blockchain

The same information gets added to a block:
```
{
  "username": "alice",
  "action": "UPLOAD",
  "filename": "evidence.pdf",
  "status": "success",
  "timestamp": "2025-05-03 14:30:15"
}
```

The app creates a **Block** with this data:
```
Block 47:
┌──────────────────────────────────────────────────┐
│ Index: 47                                        │
│ Transactions: [{ username: alice, ... }]        │
│ Timestamp: 2025-05-03 14:30:15.123              │
│ Previous Hash: h2x7k9m3p1...  ← From Block 46   │
│ Hash: f5q8r2t9u1v3w6x8y9z...  ← This block      │
│ Signature: a1b2c3d4e5f6...    ← Signed by app   │
│ Public Key: 7z8x9c0v1b2n...   ← To verify sig   │
└──────────────────────────────────────────────────┘
```

### Step 4: The Block Gets Saved to Disk

The blockchain is saved to a JSON file:
```
blockchain/chain.json
```

And the signing key is saved separately:
```
blockchain/key.pem
```

### Step 5: You Can Verify the Chain is Real

When you visit `/blockchain` page or call `/api/v1/validate-chain`:
1. App loads the entire chain from disk
2. For each block, it recalculates the hash from the data
3. It verifies the signature matches the public key
4. It checks each block points to the previous one correctly
5. If all checks pass: **Chain is Valid ✓**
6. If anything is wrong: **Tampering Detected ✗**

---

## The Two Logs (Why Two?)

This project keeps **TWO separate logs** of everything:

| PostgreSQL Database | Blockchain (Local File) |
|---|---|
| Fast queries | Simple, immutable records |
| Can be accessed from anywhere | Stores signatures for proof |
| Normal database (could be hacked) | Cryptographically protected |
| Used for filtering/reporting | Used for chain-of-custody proof |

**Both** are updated every time something happens. If one is tampered with, the other proves it!

---

## Real Example: A Complete Audit Trail

Let's say this happens in one day:

```
Timeline:

10:00 AM - Alice (police officer) logs in
  → Block 100: LOGIN action added
  → Hash: a1b2c3d4...
  → Signed ✓

10:15 AM - Alice uploads evidence.pdf
  → Block 101: UPLOAD action added
  → Points to Block 100's hash ✓
  → New Hash: e5f6g7h8...
  → Signed ✓

10:30 AM - Bob (forensic analyst) verifies the file
  → Block 102: VERIFY action added
  → Points to Block 101's hash ✓
  → New Hash: i9j0k1l2...
  → Signed ✓

2:00 PM - Charlie (court authority) downloads evidence.pdf
  → Block 103: DOWNLOAD action added
  → Points to Block 102's hash ✓
  → New Hash: m3n4o5p6...
  → Signed ✓

LATER: External Auditor wants to verify
  → Gets the public key
  → Downloads the chain
  → Verifies all signatures and hashes
  → "Chain is valid and hasn't been tampered with!" ✓
```

---

## What Happens If Someone Tries to Cheat?

### Scenario: Bad guy tries to delete Block 101 (Alice's upload)

```
Original:
Block 100: hash = a1b2c3d4
Block 101: prev_hash = a1b2c3d4 ← Legit
Block 102: prev_hash = e5f6g7h8 ← Points to Block 101

Bad guy deletes Block 101:
Block 100: hash = a1b2c3d4
Block 102: prev_hash = e5f6g7h8 ← But Block 101 is gone!

Validation runs:
"Block 102 points to hash e5f6g7h8"
"But the block before it (Block 100) has hash a1b2c3d4"
"e5f6g7h8 ≠ a1b2c3d4 — TAMPERING DETECTED!" ✗
```

### Scenario: Bad guy tries to change a username in Block 101

```
Original Block 101:
{ username: "alice", action: "UPLOAD" }
Hash: e5f6g7h8
Signature: xyz123

Bad guy changes it:
{ username: "hacker", action: "UPLOAD" }
Hash: ??? (recalculated as k1l2m3n4 ≠ e5f6g7h8!)
Signature: xyz123 (no longer matches new hash!)

Validation:
"Signature xyz123 doesn't match new hash k1l2m3n4"
"INVALID SIGNATURE — TAMPERING DETECTED!" ✗
```

**You can't cheat! Any change breaks the chain.**

---

## Anchors (The Bookmarks)

Think of anchors as **bookmarks** you create at important moments:

```
Today at 3pm, the chain has 103 blocks, last hash is m3n4o5p6...
You create an ANCHOR:
  Anchor ID: 1
  Chain Length: 103
  Hash: m3n4o5p6...
  Created By: admin
  Created At: 2025-05-03 15:00:00

Later, after 50 more blocks have been added...
You can say: "At this anchor, the chain was definitely valid"
Anchor proves: "I took a snapshot when the chain was exactly 103 blocks long"
```

**Why are anchors useful?**
- Proves the chain's state at a specific moment
- Can be backed up or published separately
- Later, you could put anchors on a public blockchain for extra proof

---

## API Endpoints (How to Use It)

### 1. View the Blockchain

```bash
GET /api/v1/chain
```

Response:
```json
{
  "version": "v1",
  "count": 104,
  "chain": [
    {
      "index": 0,
      "timestamp": "2025-05-03 10:00:00",
      "transactions": [],
      "hash": "a1b2c3d4...",
      "prev_hash": "0000000000...",
      "signature": "xyz123...",
      "signer_pub": "pub789..."
    },
    ...
  ]
}
```

### 2. Validate the Blockchain

```bash
GET /api/v1/validate-chain
```

Response:
```json
{
  "version": "v1",
  "valid": true,
  "message": "chain valid"
}
```

### 3. Create an Anchor

```bash
POST /api/v1/anchor
```

Response:
```json
{
  "version": "v1",
  "anchor_id": 1,
  "anchor_hash": "m3n4o5p6...",
  "chain_length": 104,
  "created_at": "2025-05-03 15:00:00"
}
```

---

## Summary: The Big Picture

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  FORENSIC EVIDENCE MANAGER                                  │
│                                                             │
│  Every Action:                                              │
│  ├─ Logged to PostgreSQL (fast queries)                     │
│  └─ Added to Blockchain (cryptographic proof)              │
│                                                             │
│  Blockchain:                                                │
│  ├─ Chain of blocks, each locked to the previous           │
│  ├─ Each block is mathematically signed                    │
│  ├─ Any tampering is instantly detected                    │
│  └─ Auditors can verify using the public key               │
│                                                             │
│  Anchors:                                                   │
│  ├─ Snapshots of chain state at important moments          │
│  ├─ Prove "the chain was valid on this date"              │
│  └─ Can be published externally for extra proof            │
│                                                             │
│  Result: Chain-of-Custody Proof ✓                          │
│  Nobody can secretly alter the audit trail!                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **Blockchain = Tamper-Proof Notebook** — entries can't be secretly changed
2. **Hashes Lock Blocks Together** — changing one entry breaks all subsequent ones
3. **Signatures Prove Authenticity** — anyone can verify with the public key
4. **Two Logs = Extra Safety** — database + blockchain, both protected
5. **Anchors = Proofs of State** — "at time X, the chain was exactly this"
6. **For Evidence Management** — proves nobody altered the audit trail

---

## Testing It Out

To test the blockchain without the UI:

```bash
# View the chain JSON
curl http://localhost:5000/api/v1/chain

# Check if chain is valid
curl http://localhost:5000/api/v1/validate-chain

# Create an anchor (admin only)
curl -X POST http://localhost:5000/api/v1/anchor
```

Or visit the UI:
- Go to `/blockchain` page (after logging in)
- See all blocks, their hashes, and signatures
- See the public key
- See any anchors that have been created

---

**That's blockchain in simple terms for your forensic evidence project! 🔐**
