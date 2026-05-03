# Project Progress and Remaining Work

Project Title: Cloud-Based Distributed Forensic Evidence Storage System
Last Updated: 2026-05-03

## 1. Current Completion Snapshot

### Implemented So Far
- Flask web app with core routes for login, dashboard, upload, verify, logs, logout.
- SHA-256 hash generation for evidence integrity check.
- AES-256-GCM encryption before storage.
- Multi-node replication simulation to 3 local storage nodes.
- PostgreSQL storage for users and evidence metadata.
- Structured chain-of-custody audit log with timestamp, user, role, action, status, source IP, and details.
- HTML templates and basic styling.
- Supabase PostgreSQL connectivity and schema initialization.
- Automated test suite for auth, upload, verify, and API v1 endpoints.

### Partially Implemented
- Distributed storage is still simulated locally by default; S3 backend support is available but not yet tested with real AWS credentials in production.
- Storage adapter supports S3 configuration via environment variables; node health/replication visibility is basic.
- Blockchain is implemented locally; optional external anchoring (e.g., on a public blockchain) is not yet integrated.

### Not Implemented Yet
- Optional blockchain integrity layer.
- Production deployment guide with final cloud hosting steps.
- Stronger operational monitoring for storage/node health.

## 2. Requirement-by-Requirement Status

## Functional Requirements
- [x] User Registration and Login for all required roles
- [x] Evidence Upload
- [x] Automatic SHA-256 generation
- [x] AES-256 encryption before storage
- [x] Replication across 3 nodes (local simulation)
- [x] Integrity verification by hash comparison
- [x] Full role model enforcement (Admin, Police Officer, Forensic Analyst, Court Authority)
- [x] Complete chain-of-custody actions (upload, verify, download, view all logged)

## Non-Functional Requirements
- [~] High Availability (basic local replication only)
- [~] Fault Tolerance (node copy simulation only)
- [~] Data Consistency (no conflict/version handling)
- [ ] Scalability (single Flask process)
- [~] Security (auth/session + encrypted at rest, key management still local)
- [~] Fast Retrieval (basic local file operations)

Legend:
- [x] Complete
- [~] Partial
- [ ] Pending

## 3. Remaining Work Plan

## Phase 1: Security and Access Control ✅ COMPLETE
1. ~~Add secure password hashing (bcrypt/argon2) and migrate existing plain-text passwords.~~ Done — bcrypt used for all passwords.
2. ~~Add registration or admin user-management route for required roles.~~ Done — `/register` route, admin-only.
3. ~~Enforce role-based authorization per route/action:~~ Done — `@role_required` decorator on all routes.
   - Admin: full control
   - Police Officer: upload/verify/logs
   - Forensic Analyst: verify/logs
   - Court Authority: logs only
4. ~~Add secure session settings and environment-based secret key.~~ Done — `SECRET_KEY` via `.env`.

Deliverable: secure login, strict role permissions, and compliant role model.

## Phase 2: Evidence Protection Layer ✅ COMPLETE
1. ✅ Add AES-256-GCM encryption before writing to storage nodes. (Completed)
2. ✅ Store encryption metadata safely. (Nonce prepended to ciphertext in file format)
3. ✅ Add decrypt-on-authorized-access workflow. (/download/<evidence_id> route, role-restricted)
4. ✅ Keep SHA-256 chain for tamper verification. (Hash stored on original plaintext before encryption)

Deliverable: encrypted-at-rest evidence pipeline with preserved integrity checks and secure authorized download.

## Phase 3: Chain-of-Custody Expansion ✅ COMPLETE
1. ✅ Expand audit schema to structured log table with all required fields.
   - evidence_id, user, role, action, timestamp, source_ip, status, details
2. ✅ Log view/download/update/verify events per evidence item.
3. ✅ Add filterable logs page by date, user, evidence, and action.
4. ✅ Add export option (CSV) for legal reporting.

Deliverable: complete, queryable chain-of-custody trail with full forensic-grade audit capabilities.

## Phase 4: Storage and Cloud Upgrade (Priority: Medium) ✅ PARTIALLY COMPLETE
1. ✅ Create pluggable storage adapter interface with local and S3 backends
2. ✅ Implement LocalStorageAdapter for multi-node replication
3. ✅ Refactor upload/download to use storage_adapter instead of direct replicate_file()
4. ✅ Add health check endpoint for storage backend monitoring
5. ⏳ Next: S3 adapter testing with real AWS credentials
6. ⏳ Next: Add replication policy and node health visibility layer

Deliverable (in progress): pluggable storage abstraction enabling cloud migration without app refactoring.

## Phase 5: Database and API Hardening (Priority: Medium) ✅ COMPLETE
1. ✅ Migrate from SQLite to PostgreSQL for production readiness.
2. ✅ Add evidence metadata indexing for faster retrieval.
3. ✅ Introduce API layer versioning and validation.
4. ✅ Add unit/integration tests for auth, upload, verify, and logs.

Deliverable: hardened backend with PostgreSQL, indexed queries, validated v1 APIs, and expanded automated test coverage.

## Phase 6: Optional Blockchain Layer (Advanced) ✅ IMPLEMENTED (off-chain)
1. Implemented a private, Ed25519-signed off-chain audit ledger persisted to `blockchain/chain.json`.
2. Added endpoints and UI components to view the chain, validate it, and create anchors (`/blockchain`, `/api/v1/chain`, `/api/v1/validate-chain`, `/api/v1/anchor`).
3. The ledger is local/off-chain (no Solidity smart contracts). Anchors can be exported for optional external anchoring.

Deliverable: tamper-evident off-chain audit ledger with signing and anchor support.

## 4. Immediate Next Sprint (Recommended)

Sprint Goal: cloud storage integration and production hardening

Tasks:
- [x] Implement password hashing and role policy middleware.
- [x] Add user/role management interface.
- [x] Add AES-256 encryption module for upload pipeline.
- [x] Extend audit logging to include structured events (evidence_id, action, status).
- [x] Add tests for login, upload, verify, and access-control failures.
- [ ] Replace local storage with AWS S3 or compatible backend.
- [x] Migrate database from SQLite to PostgreSQL.

Current next step: test S3 adapter with real AWS credentials in a staging environment, validate production key rotation workflows, and then add simple node-health and replication visibility for monitoring.

Success Criteria (Phase 3 ✅ Complete):
- Unauthorized roles cannot access restricted actions. ✅
- Uploaded evidence is encrypted before storage. ✅
- Evidence can be listed and downloaded by authorized roles. ✅
- All critical actions are captured in chain-of-custody logs. ✅
- Integrity verification passes for untampered files and fails for modified files. ✅
- Logs are queryable by user, action, status, and evidence. ✅
- CSV export available for legal reporting. ✅

## 5. Risks and Mitigations

- Key management risk: use environment variables or secret manager, never hardcode keys.
- Data loss risk: add retry and periodic node consistency checks.
- Legal admissibility risk: preserve immutable timestamps and actor identity for every action.
- Scale risk: move to PostgreSQL and object storage before load testing.

## 6. Definition of Done (Final Project)

Project is considered complete when all are true:
- Role-based access fully enforced for all required roles.
- Evidence is encrypted at rest and hash-verifiable.
- Distributed/cloud storage is operational with replication.
- Chain-of-custody is complete, searchable, and exportable.
- Core workflows are covered by tests and pass consistently.
- Deployment guide is documented for reproducible setup.
