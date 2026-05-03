# Forensic Evidence Management System

A secure, production-ready web application for managing, verifying, and auditing digital forensic evidence with tamper-proof chain-of-custody tracking, end-to-end encryption, and cryptographic audit proof via an off-chain blockchain ledger.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [System Architecture](#system-architecture)
- [Installation & Configuration](#installation--configuration)
- [Usage Guide](#usage-guide)
- [API Reference](#api-reference)
- [Database Schema](#database-schema)
- [Storage Backends](#storage-backends)
- [Blockchain & Audit Ledger](#blockchain--audit-ledger)
- [Security & Access Control](#security--access-control)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## Overview

This forensic evidence management system provides a complete solution for secure evidence handling in forensic investigations and legal proceedings. It combines:

- **Secure Evidence Storage:** AES-256-GCM encryption at rest with automatic replication or cloud backup
- **Integrity Verification:** SHA-256 hashing to detect tampering
- **Chain-of-Custody Tracking:** Comprehensive audit logging with PostgreSQL persistence
- **Tamper Proof Proof:** An off-chain, Ed25519-signed blockchain ledger for immutable audit trail verification
- **Role-Based Access Control:** Four distinct roles with granular permissions
- **Pluggable Storage:** Support for both local multi-node replication and AWS S3 backends

---

## Key Features

### 🔐 Security & Authentication

- Multi-role user authentication (Admin, Police Officer, Forensic Analyst, Court Authority)
- bcrypt password hashing with automatic legacy plaintext migration
- Session-based access control
- Role-based permission enforcement on all routes
- Protected endpoints with JSON API versioning

### 📤 Evidence Upload & Storage

- File type validation (images, video, audio, PDF, documents)
- Automatic SHA-256 hashing of original files
- AES-256-GCM encryption before storage
- Automatic replication to three local nodes OR direct upload to AWS S3
- Evidence metadata stored in PostgreSQL with proper indexing

### ✅ Integrity Verification

- Compare uploaded files against stored hash values
- Immediate tamper detection with audit logging
- Both UI and REST API verification endpoints

### 📊 Audit Logging & Chain-of-Custody

- Structured PostgreSQL audit trail with full event details:
  - Username, role, action, timestamp, source IP, evidence link, status, details
- Comprehensive filtering and search (by user, action, evidence, status)
- CSV export for legal reporting
- Legacy plaintext fallback logging for resilience

### ⛓️ Blockchain Audit Ledger

- Off-chain, append-only signed ledger (Ed25519 cryptography)
- Every audit event appended to immutable chain
- Chain validation endpoints for auditor verification
- Anchor snapshots to capture chain state at critical moments
- Public key exposed for external verification

### 🖥️ Web Interface

- Role-aware responsive dashboard
- Evidence upload form with type validation
- Integrity verification UI
- Evidence inventory with download capability
- Queryable audit logs with filtering and export
- Blockchain status dashboard with validation controls

### 📡 REST APIs

- `/api/v1/health` — System health check
- `/api/v1/evidence` — List evidence with pagination
- `/api/v1/verify/hash` — Verify file integrity by hash
- `/api/v1/chain` — Get full blockchain JSON
- `/api/v1/validate-chain` — Validate chain integrity
- `/api/v1/anchor` — Create blockchain anchor

---

## Quick Start

### Prerequisites

- Python 3.7+
- PostgreSQL database (local or cloud, e.g., Supabase)
- Git

### Installation

1. **Clone and navigate to project:**
   ```bash
   git clone https://github.com/AmulyaKaushik/Cloud-Based-Distributed-Forensic-Evidence-Storage-System.git
   cd Cloud-Based-Distributed-Forensic-Evidence-Storage-System
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Create a `.env` file in the project root:
   ```bash
   # Required
   DATABASE_URL=postgresql://user:password@host:port/dbname?sslmode=require

   # Optional but recommended for production
   SECRET_KEY=your-secret-key-here
   EVIDENCE_AES_KEY=your-base64-32-byte-key
   STORAGE_BACKEND=local  # or 's3' for AWS S3
   
   # If using S3 storage
   S3_BUCKET_NAME=your-bucket-name
   AWS_REGION=us-east-1
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

   The app will start at `http://localhost:5000`

6. **Login with default admin account:**
   - Username: `admin`
   - Password: `admin123`

   ⚠️ **Change this password immediately in production!**

---

## System Architecture

### High-Level Architecture Diagram

```mermaid
flowchart TB
    User["👤 User / Browser"]
    User -->|Login/Upload/Verify| UI["🖥️ Flask Web UI<br/>Templates & Routes"]
    User -->|REST API| API["📡 REST API v1<br/>/api/v1/*"]
    
    UI -->|PostgreSQL| DB["🗄️ PostgreSQL<br/>Users, Evidence,<br/>Audit Logs, Anchors"]
    API -->|PostgreSQL| DB
    
    UI -->|Encrypt & Store| SA["💾 Storage Adapter<br/>(Pluggable Backend)"]
    API -->|Encrypt & Store| SA
    
    SA -->|Local Mode| LN["📁 Local Storage Nodes<br/>node1, node2, node3"]
    SA -->|S3 Mode| S3["☁️ AWS S3 Bucket<br/>(Production)"]
    
    UI -->|Append Block| BC["⛓️ Blockchain<br/>chain.json<br/>Ed25519 Signed"]
    API -->|Append Block| BC
    
    BC -->|Hash + Sign| Auditor["👮 External Auditor<br/>Verify Immutability"]
    
    DB -->|Stores Anchors| AN["🔗 Anchors Table<br/>Chain Snapshots"]
```

### Component Interaction Flow

```mermaid
sequenceDiagram
    participant User
    participant App as Flask App
    participant DB as PostgreSQL
    participant SA as Storage Adapter
    participant BC as Blockchain
    participant Audit as Audit Log
    
    User->>App: Upload Evidence
    App->>App: Hash (SHA-256)
    App->>App: Encrypt (AES-256-GCM)
    App->>SA: put(encrypted_file)
    SA->>DB: Store Metadata
    App->>DB: Insert Evidence Record
    App->>Audit: write_log(UPLOAD)
    Audit->>DB: Insert Audit Entry
    Audit->>BC: add_block(tx)
    BC->>BC: Sign with Ed25519
    App-->>User: Success
```

---

## Installation & Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ Yes | — | PostgreSQL connection string (Supabase or self-hosted) |
| `SECRET_KEY` | ⚠️ Recommended | `change_this_before_production` | Flask session key; change in production |
| `EVIDENCE_AES_KEY` | ⚠️ Recommended | Derived from SECRET_KEY | Base64-encoded 32-byte AES key |
| `STORAGE_BACKEND` | ❌ No | `local` | `local` or `s3` |
| `S3_BUCKET_NAME` | If S3 | — | AWS S3 bucket name (required if `STORAGE_BACKEND=s3`) |
| `AWS_REGION` | ❌ No | `us-east-1` | AWS region for S3 |
| `RUNTIME_DATA_DIR` | ❌ No | Project root (or `/tmp/forensic2` on Vercel) | Directory for runtime data (blockchain, audit logs, local nodes) |

### PostgreSQL Setup

#### Option 1: Local PostgreSQL
```bash
# Install PostgreSQL locally, then create a database
createdb forensic_db
# Connection string:
DATABASE_URL="postgresql://postgres:password@localhost:5432/forensic_db"
```

#### Option 2: Supabase (Recommended for Production)
1. Create a project on [supabase.com](https://supabase.com)
2. Copy the PostgreSQL connection string from project settings
3. Ensure `sslmode=require` is included
4. Set `DATABASE_URL` to this value

Tables are created automatically on first run via `init_db()`.

### Storage Backend Configuration

#### Local Storage (Development & Small Deployments)
Default; replicates encrypted files to three local directories.
```bash
export STORAGE_BACKEND=local
export RUNTIME_DATA_DIR=/path/to/storage
```

#### AWS S3 (Production)
Requires AWS credentials configured locally or via IAM role.
```bash
export STORAGE_BACKEND=s3
export S3_BUCKET_NAME=my-forensic-bucket
export AWS_REGION=us-east-1
pip install boto3  # Required for S3 backend
```

---

## Usage Guide

### User Roles & Permissions

| Role | Upload | Verify | View Logs | Manage Users | View Evidence | Download | Create Anchors |
|------|--------|--------|-----------|--------------|---------------|----------|----------------|
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Police Officer | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| Forensic Analyst | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| Court Authority | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ |

### Workflow: Upload Evidence

1. Login with appropriate credentials
2. Navigate to "Upload Evidence"
3. Select a file (images, video, audio, PDF, documents)
4. Click "Upload"
5. System:
   - Computes SHA-256 hash of original file
   - Encrypts file using AES-256-GCM
   - Replicates encrypted copy to storage backend
   - Stores metadata and hash in database
   - Appends audit entry to blockchain
6. Receive confirmation with evidence ID

### Workflow: Verify Integrity

1. Navigate to "Verify Integrity"
2. Upload the same file again
3. System:
   - Computes SHA-256 hash of uploaded file
   - Compares with stored hash
   - Logs result to audit trail and blockchain
4. Receive result: **"Integrity Verified"** or **"Tampering Detected"**

### Workflow: View Audit Logs

1. Navigate to "Audit Logs"
2. Apply optional filters:
   - By username
   - By action (UPLOAD, DOWNLOAD, VERIFY, etc.)
   - By evidence filename
   - By status (success, failure, warning)
3. View detailed chain-of-custody trail
4. Export as CSV for legal reporting

### Workflow: Verify Blockchain Integrity

1. Navigate to "Blockchain" dashboard
2. View:
   - Chain length (total blocks)
   - Validation status (✅ valid or ❌ invalid)
   - Recent blocks with transactions
   - Public key for external verification
   - Existing anchors (chain snapshots)
3. Create an anchor to snapshot current chain state
4. Download chain JSON and public key for auditor verification

---

## API Reference

### Authentication & General Notes

- All API endpoints require the user to be logged in (session-based)
- Role-based access control enforced on all endpoints
- Responses are JSON with versioning (`"version": "v1"`)
- Errors include error codes and descriptive messages

### Health & System

#### GET /health
Basic health check (unprotected).
```bash
curl http://localhost:5000/health
```
Response:
```json
{
  "app": "forensic-evidence-manager",
  "timestamp": "2026-05-03 14:30:00.123456",
  "database": "ok (5 users)",
  "storage": { "healthy": true, "message": "All nodes accessible", "backend": "local" }
}
```

#### GET /api/v1/health
Versioned health endpoint (requires authentication).
```bash
curl http://localhost:5000/api/v1/health -H "Cookie: session=..."
```

### Evidence Management

#### GET /api/v1/evidence
List evidence (paginated).
```bash
curl http://localhost:5000/api/v1/evidence?limit=20 -H "Cookie: session=..."
```
Query Parameters:
- `limit` (1-100, default 50): Number of records to return

Response:
```json
{
  "version": "v1",
  "count": 3,
  "items": [
    {
      "id": 1,
      "filename": "evidence.pdf",
      "uploaded_by": "alice",
      "upload_time": "2026-05-03 10:00:00",
      "encryption_algo": "AES-256-GCM"
    }
  ]
}
```

#### POST /api/v1/verify/hash
Verify file integrity by comparing SHA-256 hash.
```bash
curl -X POST http://localhost:5000/api/v1/verify/hash \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{
    "filename": "evidence.pdf",
    "sha256": "a1b2c3d4e5f6...64_hex_chars"
  }'
```
Response:
```json
{
  "version": "v1",
  "filename": "evidence.pdf",
  "evidence_id": 1,
  "verified": true,
  "message": "Integrity Verified"
}
```

### Blockchain

#### GET /api/v1/chain
Retrieve full blockchain (read-only).
```bash
curl http://localhost:5000/api/v1/chain -H "Cookie: session=..."
```
Response:
```json
{
  "version": "v1",
  "count": 42,
  "chain": [
    {
      "index": 0,
      "timestamp": "2026-05-03 10:00:00.000000+00:00",
      "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
      "transactions": [],
      "signer_pub": "abcd1234...",
      "signature": "xyz789...",
      "hash": "a7f3e2c8b1d4a9f3e2c8b1d4a9f3e2c8b1d4a9f3e2c8b1d4a9f3e2c8b1d4"
    },
    ...
  ]
}
```

#### GET /api/v1/validate-chain
Validate blockchain integrity (all hashes and signatures).
```bash
curl http://localhost:5000/api/v1/validate-chain -H "Cookie: session=..."
```
Response:
```json
{
  "version": "v1",
  "valid": true,
  "message": "chain valid"
}
```

#### POST /api/v1/anchor
Create an anchor (snapshot of current chain head).
```bash
curl -X POST http://localhost:5000/api/v1/anchor \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..."
```
Response:
```json
{
  "version": "v1",
  "anchor_id": 5,
  "anchor_hash": "275b709ebdf3834f5cc210789a544c175979d924ea147b741b47f50650672c49",
  "chain_length": 42,
  "created_at": "2026-05-03 14:30:00.000000"
}
```

---

## Database Schema

### Tables

#### `users`
Stores user accounts and roles.
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,  -- bcrypt hash
    role TEXT NOT NULL       -- admin, police_officer, forensic_analyst, court_authority
);
```

#### `evidence`
Stores metadata for uploaded evidence files.
```sql
CREATE TABLE evidence (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    hash TEXT NOT NULL,                      -- SHA-256 of original file
    uploaded_by TEXT NOT NULL,
    upload_time TEXT NOT NULL,
    encrypted_filename TEXT NOT NULL,        -- Stored name in storage backend
    encryption_algo TEXT NOT NULL            -- e.g., "AES-256-GCM"
);
```

#### `audit_logs`
Comprehensive chain-of-custody trail.
```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    evidence_id INTEGER REFERENCES evidence(id),
    username TEXT NOT NULL,
    user_role TEXT NOT NULL,
    action TEXT NOT NULL,                    -- UPLOAD, DOWNLOAD, VERIFY, LOGIN, etc.
    status TEXT NOT NULL,                    -- success, failure, warning
    timestamp TEXT NOT NULL,
    source_ip TEXT NOT NULL,
    details TEXT                             -- Additional context
);
```

#### `anchors`
Blockchain anchor snapshots.
```sql
CREATE TABLE anchors (
    id SERIAL PRIMARY KEY,
    anchor_hash TEXT NOT NULL,               -- Chain head hash at time of anchor
    chain_length INTEGER NOT NULL,           -- Number of blocks in chain
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    tx_ref TEXT                              -- Optional external transaction reference
);
```

### Indexes
Created automatically for query performance:
- `idx_evidence_filename` on evidence(filename)
- `idx_evidence_upload_time` on evidence(upload_time)
- `idx_audit_timestamp` on audit_logs(timestamp)
- `idx_audit_action` on audit_logs(action)
- `idx_audit_username` on audit_logs(username)
- `idx_audit_evidence_id` on audit_logs(evidence_id)
- `idx_anchors_created_at` on anchors(created_at)

---

## Storage Backends

### Local Storage (Multi-Node Replication)

**Default backend.** Replicates encrypted evidence to three local directories for redundancy.

```bash
export STORAGE_BACKEND=local
export RUNTIME_DATA_DIR=/data/forensic2
```

Directory structure:
```
/data/forensic2/
├── storage_nodes/
│   ├── node1/
│   ├── node2/
│   └── node3/
├── audit_logs/
└── blockchain/
    ├── chain.json
    └── key.pem
```

**Health check:**
```bash
curl http://localhost:5000/health
# Response includes status of all three nodes
```

### AWS S3 Storage

**Production backend.** Stores encrypted evidence directly in S3 with built-in redundancy.

**Prerequisites:**
```bash
pip install boto3
# Configure AWS credentials:
# - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
# - ~/.aws/credentials
# - IAM role (recommended for deployments)
```

**Configuration:**
```bash
export STORAGE_BACKEND=s3
export S3_BUCKET_NAME=my-forensic-evidence-bucket
export AWS_REGION=us-west-2
```

**Health check:**
```bash
curl http://localhost:5000/health
# Response indicates S3 bucket connectivity
```

**Migration from Local to S3:**
1. Set up S3 bucket with appropriate permissions
2. Update environment variables
3. Restart application
4. New uploads use S3; existing local files remain accessible during transition

---

## Blockchain & Audit Ledger

### Overview

The blockchain is an **off-chain, tamper-evident audit ledger** that provides cryptographic proof of the integrity of the audit trail. Key characteristics:

- **Off-chain:** Persisted locally (not on a public blockchain)
- **Ed25519-signed:** Each block is signed with a private key; signatures can be verified with the public key
- **Append-only:** New audit entries create new blocks; old blocks cannot be modified without breaking subsequent signatures
- **Immutable proof:** Auditors can download the chain JSON and public key and verify independently that no entries were tampered with

### How It Works

1. **Every audit event** (LOGIN, UPLOAD, VERIFY, DOWNLOAD, etc.) is:
   - Written to the PostgreSQL audit_logs table
   - Appended as a transaction to a new blockchain block
   - Signed with the app's Ed25519 private key
   - Persisted to `blockchain/chain.json`

2. **Each block contains:**
   - Index (position in chain)
   - Timestamp
   - List of transactions (audit entries)
   - Hash of the previous block
   - Hash of current block data
   - Ed25519 signature
   - Public key for verification

3. **Validation:**
   - GET `/api/v1/validate-chain` verifies:
     - Each block's hash matches its data
     - Each block links to the previous block (prev_hash matches)
     - Each signature is valid (recoverable with public key)
   - If any tampering is detected, validation fails

### Anchors

An **anchor** is a snapshot of the blockchain's current head state stored in the database. Use cases:

- **Legal proof of timeline:** "At this date and time, the audit chain was exactly this hash"
- **Notarization:** Export anchor metadata for external timestamping
- **Recovery:** If blockchain file is corrupted, anchors allow reconstruction

**Create an anchor:**
```bash
curl -X POST http://localhost:5000/api/v1/anchor -H "Cookie: session=..."
```

Anchors are stored in the `anchors` table with:
- `anchor_hash`: Head block hash at time of creation
- `chain_length`: Total blocks in chain
- `created_by`: Username of anchor creator
- `created_at`: Timestamp

### Key Security Notes

- **Private key location:** `blockchain/key.pem` (created at app startup)
- **DO NOT COMMIT** this file to git (added to `.gitignore`)
- **If exposed:** Rotate immediately by:
  1. Generating a new keypair
  2. Updating running instance
  3. Publishing new public key to auditors
  4. Consider chain from moment of rotation onwards untrusted
- See `BLOCKCHAIN_EXPLAINED.md` for detailed key rotation procedures

---

## Security & Access Control

### Authentication

- **Method:** Session-based (Flask sessions)
- **Password storage:** bcrypt hashing with automatic salt generation
- **Legacy migration:** Plaintext passwords accepted on first login, then upgraded to bcrypt
- **Session timeout:** Standard Flask session timeout (configurable)

### Authorization

**Role-based permissions:**

| Action | Admin | Police Officer | Forensic Analyst | Court Authority |
|--------|-------|-----------------|------------------|-----------------|
| Upload Evidence | ✅ | ✅ | ❌ | ❌ |
| Verify Integrity | ✅ | ✅ | ✅ | ❌ |
| Download Evidence | ✅ | ✅ | ✅ | ✅ |
| View Audit Logs | ✅ | ✅ | ✅ | ✅ |
| Export Logs (CSV) | ✅ | ✅ | ✅ | ✅ |
| Create Blockchain Anchor | ✅ | ❌ | ❌ | ❌ |
| Manage Users (Register) | ✅ | ❌ | ❌ | ❌ |

- Enforced via `@role_required()` decorator on all protected routes
- Violations logged as `ACCESS_DENIED` events with audit trail

### Data Protection

- **At rest:** AES-256-GCM encryption of evidence files
- **In transit:** HTTPS recommended (enable in production)
- **In database:** Plaintext metadata (focus on confidentiality of evidence files)
- **Audit trail:** Not encrypted (needed for filtering and legal reporting); stored in secure PostgreSQL

### Audit Trail

Every significant action is logged:
```
LOGIN, LOGOUT, UPLOAD, DOWNLOAD, VERIFY, CREATE_USER, ACCESS_DENIED, EXPORT_LOGS, ANCHOR, VIEW_BLOCKCHAIN
```

Each log entry includes:
- **Who:** Username and role
- **What:** Action and details
- **When:** Timestamp
- **Where:** Source IP address
- **Status:** Success / failure / warning

---

## Deployment

### Local Development

```bash
python app.py
# Runs on http://localhost:5000 with debug=True
```

### Vercel (Serverless)

The project includes `vercel.json` for deployment on Vercel.

**Prerequisites:**
- Vercel account
- PostgreSQL database (e.g., Supabase) for data persistence
- S3 bucket (optional, for evidence storage)

**Environment variables on Vercel:**
- `DATABASE_URL`
- `SECRET_KEY`
- `EVIDENCE_AES_KEY`
- `STORAGE_BACKEND` (recommended: `s3`)
- `S3_BUCKET_NAME`
- `AWS_REGION`
- AWS credentials (via GitHub secrets or IAM role)

**Deploy:**
```bash
vercel deploy
```

### Docker (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

Build and run:
```bash
docker build -t forensic-app .
docker run -p 5000:5000 --env-file .env forensic-app
```

---

## Troubleshooting

### Common Issues

**Q: "DATABASE_URL is required" error**
- A: Set `DATABASE_URL` environment variable to your PostgreSQL connection string

**Q: Tables not created automatically**
- A: Tables are created on app startup in `init_db()`. Restart the app after setting DATABASE_URL.

**Q: S3 upload fails with credentials error**
- A: Ensure AWS credentials are configured (env vars or ~/.aws/credentials) and bucket exists

**Q: Blockchain validation fails**
- A: If blockchain file is corrupted, delete `blockchain/chain.json` to start fresh (note: chain data will be lost)

**Q: Can't decrypt evidence file**
- A: Ensure `EVIDENCE_AES_KEY` hasn't changed. If it has, old files cannot be decrypted.

### Logs & Debugging

**View Flask logs:**
```bash
python app.py  # Logs printed to console in debug mode
```

**Check database:**
```bash
psql -h hostname -U username -d dbname -c "SELECT COUNT(*) FROM audit_logs;"
```

**Verify blockchain:**
```bash
python -c "
from blockchain import Blockchain
bc = Blockchain('./blockchain')
valid, msg = bc.validate()
print(f'Valid: {valid}, Message: {msg}')
"
```

---

## Additional Resources

- **Blockchain Details:** See `BLOCKCHAIN_EXPLAINED.md` for cryptography, key rotation, and verification procedures
- **Storage Configuration:** See `STORAGE_BACKENDS.md` for S3 setup and migration
- **Project Overview:** See `PROJECT_WORKING_OVERVIEW.md` for technical architecture and detailed workflows
- **Progress & Roadmap:** See `PROGRESS.md` for development status and future plans

---

## License

[Specify your license here]

## Support

For issues or questions, open an issue on GitHub or contact the development team.

---

**Last Updated:** 2026-05-03
