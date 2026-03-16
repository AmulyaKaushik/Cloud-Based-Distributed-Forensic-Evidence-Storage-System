# Project Progress and Remaining Work

Project Title: Cloud-Based Distributed Forensic Evidence Storage System
Last Updated: 2026-03-16

## 1. Current Completion Snapshot

### Implemented So Far
- Flask web app with core routes for login, dashboard, upload, verify, logs, logout.
- SHA-256 hash generation for evidence integrity check.
- Multi-node replication simulation to 3 local storage nodes.
- SQLite storage for users and evidence metadata.
- Basic chain-of-custody audit log with timestamp, user, and action.
- HTML templates and basic styling.

### Partially Implemented
- Role-based access exists in schema/session, but fine-grained permissions are not enforced.
- Distributed storage is simulated locally, not cloud-hosted.

### Not Implemented Yet
- User registration workflow.
- AES-256 encryption before storage.
- Full role model enforcement (Admin, Police Officer, Forensic Analyst, Court Authority).
- Access-level chain-of-custody events (view/download/update) per file.
- Production-grade database (PostgreSQL/MongoDB).
- Real cloud storage integration (AWS S3/GCP/HDFS).
- Optional blockchain integrity layer.

## 2. Requirement-by-Requirement Status

## Functional Requirements
- [ ] User Registration and Login for all required roles
- [x] Evidence Upload
- [x] Automatic SHA-256 generation
- [ ] AES-256 encryption before storage
- [x] Replication across 3 nodes (local simulation)
- [x] Integrity verification by hash comparison
- [ ] Complete chain-of-custody actions (view/download/update)

## Non-Functional Requirements
- [~] High Availability (basic local replication only)
- [~] Fault Tolerance (node copy simulation only)
- [~] Data Consistency (no conflict/version handling)
- [ ] Scalability (single Flask process)
- [~] Security (basic auth/session, no encryption at rest)
- [~] Fast Retrieval (basic local file operations)

Legend:
- [x] Complete
- [~] Partial
- [ ] Pending

## 3. Remaining Work Plan

## Phase 1: Security and Access Control (Priority: High)
1. Add secure password hashing (bcrypt/argon2) and migrate existing plain-text passwords.
2. Add registration or admin user-management route for required roles.
3. Enforce role-based authorization per route/action:
   - Admin: full control
   - Police Officer: upload/view own investigations
   - Forensic Analyst: verify and analyze
   - Court Authority: read-only access to approved evidence
4. Add secure session settings and environment-based secret key.

Deliverable: secure login, strict role permissions, and compliant role model.

## Phase 2: Evidence Protection Layer (Priority: High)
1. Add AES-256 encryption before writing to storage nodes.
2. Store encryption metadata safely (nonce/iv/tag/key reference, never raw key in DB).
3. Add decrypt-on-authorized-access workflow.
4. Keep SHA-256 chain for tamper verification over encrypted payload and/or original file policy.

Deliverable: encrypted-at-rest evidence pipeline with preserved integrity checks.

## Phase 3: Chain-of-Custody Expansion (Priority: High)
1. Expand audit schema to structured log table:
   - evidence_id, user, role, action, timestamp, source_ip, status
2. Log view/download/update/verify events per evidence item.
3. Add filterable logs page by date, user, evidence, and action.
4. Add export option (CSV/PDF) for legal reporting.

Deliverable: complete, queryable chain-of-custody trail.

## Phase 4: Storage and Cloud Upgrade (Priority: Medium)
1. Replace local node folders with pluggable storage adapter.
2. Integrate one target backend:
   - AWS S3 (recommended for demo)
   - or HDFS
   - or GCP storage
3. Add replication policy and health checks.
4. Add retry logic and failure handling.

Deliverable: cloud-backed distributed storage with node health visibility.

## Phase 5: Database and API Hardening (Priority: Medium)
1. Migrate from SQLite to PostgreSQL (or MongoDB) for production readiness.
2. Add evidence metadata indexing for faster retrieval.
3. Introduce API layer versioning and validation.
4. Add unit/integration tests for auth, upload, verify, and logs.

Deliverable: reliable backend with tested core workflows.

## Phase 6: Optional Blockchain Layer (Advanced)
1. Store hash fingerprints of evidence/audit events on Hyperledger Fabric.
2. Implement verification endpoint to cross-check DB hash with blockchain entry.

Deliverable: immutable external proof layer.

## 4. Immediate Next Sprint (Recommended)

Sprint Goal: complete security baseline and custody compliance

Tasks:
- [ ] Implement password hashing and role policy middleware.
- [ ] Add user/role management interface.
- [ ] Add AES-256 encryption module for upload pipeline.
- [ ] Extend audit logging to include view/download/update.
- [ ] Add tests for login, upload, verify, and access-control failures.

Success Criteria:
- Unauthorized roles cannot access restricted actions.
- Uploaded evidence is encrypted before storage.
- All critical actions are captured in chain-of-custody logs.
- Integrity verification passes for untampered files and fails for modified files.

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
