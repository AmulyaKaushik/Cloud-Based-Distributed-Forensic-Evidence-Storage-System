# Project Working Overview

## Purpose

This project is a Flask-based forensic evidence management system for uploading, storing, verifying, and auditing digital evidence.

In its current state, the system provides:

- User authentication with role-based access control
- Secure evidence upload with SHA-256 hashing
- AES-256-GCM encryption before storage
- Replication of encrypted evidence across three storage nodes
- Integrity verification by comparing uploaded file hashes with stored records
- Evidence inventory and authorized download
- Structured chain-of-custody logging with CSV export
- A browser-based interface for all main workflows
 - Replication of encrypted evidence across three storage nodes
 - Integrity verification by comparing uploaded file hashes with stored records
 - Evidence inventory and authorized download
 - Structured chain-of-custody logging with CSV export
 - A browser-based interface for all main workflows
 - An off-chain, Ed25519-signed append-only audit ledger persisted under `blockchain/` for tamper-evident proof

The project is implemented primarily in [app.py](/c:/Users/anura/OneDrive/Desktop/forensic2/app.py), with Vercel support exposed through [api/index.py](/c:/Users/anura/OneDrive/Desktop/forensic2/api/index.py).

## High-Level Architecture

The application is organized into five main layers:

1. Web interface: HTML templates in `templates/` and styling in `static/style.css`
2. Application logic: Flask routes, permissions, encryption, hashing, and audit handling in `app.py`
3. Metadata storage: SQLite database created at runtime as `database.db`
4. Evidence storage: encrypted files replicated into `storage_nodes/node1`, `node2`, and `node3`
5. Audit trail: structured records in the database, with fallback plaintext file logging in `audit_logs/audit.log`

## Main Technologies Used

- Flask 3.1.0 for the web app and routing
- SQLite for user, evidence, and audit metadata
- bcrypt for password hashing
- cryptography with AESGCM for evidence encryption
- python-dotenv for environment variable loading
- Standard Python modules for hashing, file handling, CSV export, and timestamps

These dependencies are listed in [requirements.txt](/c:/Users/anura/OneDrive/Desktop/forensic2/requirements.txt).

## Runtime Behavior and Environment

At startup, the application loads environment variables and configures runtime paths.

### Runtime data directory

The app uses `RUNTIME_DATA_DIR` to decide where mutable data lives.

- In local development, it defaults to the project folder
- In Vercel, it defaults to `/tmp/forensic2`

This directory contains:

- `database.db`
- `storage_nodes/`
- `audit_logs/`
 - `blockchain/` (chain.json and signer key are stored here at runtime; private keys must not be committed)

### Important environment variables

- `SECRET_KEY`: Flask session secret. If not supplied, a fallback development value is used.
- `EVIDENCE_AES_KEY`: optional URL-safe base64 encoded 32-byte key for AES-256-GCM encryption.
- `RUNTIME_DATA_DIR`: optional override for runtime storage location.
- `VERCEL`: used to switch runtime storage to `/tmp/forensic2` in serverless deployments.

### Startup initialization

When the app starts, it immediately:

1. Creates runtime directories if they do not exist
2. Initializes the SQLite database
3. Ensures the required tables exist
4. Seeds a default admin user if no admin exists yet

Default seeded admin account:

- Username: `admin`
- Password: `admin123`
- Role: `admin`

## Directory Structure and What Each Part Does

### Root files

- [app.py](/c:/Users/anura/OneDrive/Desktop/forensic2/app.py): main Flask application, routes, auth, hashing, encryption, logging, downloads
- [api/index.py](/c:/Users/anura/OneDrive/Desktop/forensic2/api/index.py): Vercel entrypoint that imports the Flask app
- [requirements.txt](/c:/Users/anura/OneDrive/Desktop/forensic2/requirements.txt): Python dependencies
- [vercel.json](/c:/Users/anura/OneDrive/Desktop/forensic2/vercel.json): Vercel routing and Python build config
- [README.md](/c:/Users/anura/OneDrive/Desktop/forensic2/README.md): general project summary
- [PROGRESS.md](/c:/Users/anura/OneDrive/Desktop/forensic2/PROGRESS.md): implementation status and roadmap

### Templates

- `login.html`: login form for authorised personnel
- `dashboard.html`: role-aware landing page after login
- `register.html`: admin-only user creation page
- `upload.html`: evidence upload form
- `verify.html`: file integrity verification form
- `evidence.html`: evidence inventory and download page
- `logs.html`: chain-of-custody log viewer with filters and export
- `error.html`: shared access/error page

### Storage folders

- `storage_nodes/node1`
- `storage_nodes/node2`
- `storage_nodes/node3`

Each node stores encrypted copies of evidence files. The system treats these as three local replicas of the same evidence payload.

### Audit folder

- `audit_logs/`: contains legacy file logs when database logging fails or for backward compatibility

## Database Design

The app creates three SQLite tables.

### `users`

Stores login accounts and roles.

Columns:

- `id`
- `username` as a unique value
- `password` as a bcrypt hash or legacy plaintext value awaiting migration
- `role`

### `evidence`

Stores metadata for each uploaded evidence item.

Columns:

- `id`
- `filename`: original filename
- `hash`: SHA-256 hash of the original plaintext file
- `uploaded_by`
- `upload_time`
- `encrypted_filename`: stored encrypted filename used in node folders
- `encryption_algo`: currently `AES-256-GCM`

### `audit_logs`

Stores structured chain-of-custody events.

Columns:

- `id`
- `evidence_id`
- `username`
- `user_role`
- `action`
- `status`
- `timestamp`
- `source_ip`
- `details`

This table is the main source for the logs page and CSV export.

## Authentication and User Management

### Login flow

Users log in through `/`.

The app:

1. Validates that username and password were provided
2. Looks up the user in the `users` table
3. Verifies the password
4. Writes the username and role into the Flask session
5. Logs the login outcome to `audit_logs`

### Password migration behavior

The application supports a one-time upgrade path from legacy plaintext passwords.

If a stored password is not already a bcrypt hash and the entered plaintext password matches, the app:

1. Accepts the login
2. Re-hashes the password with bcrypt
3. Updates the database record
4. Logs a `PASSWORD HASH UPGRADE` event

This allows older user records to be migrated transparently after a successful login.

### Role model and permissions

The project currently defines four roles:

- `admin`
- `police_officer`
- `forensic_analyst`
- `court_authority`

Permission mapping:

- `admin`: upload, verify, logs, manage users, view evidence, download evidence
- `police_officer`: upload, verify, logs, view evidence, download evidence
- `forensic_analyst`: verify, logs, view evidence, download evidence
- `court_authority`: logs, view evidence, download evidence

Authorization is enforced with a `role_required()` decorator. If a logged-in user attempts to access a route without the required permission, the app returns a 403 page and logs an `ACCESS_DENIED` event.

### User registration

The `/register` route is admin-only.

It allows an administrator to:

- Create a new user
- Assign one of the valid roles
- Enforce a minimum password length of 8 characters
- Require password confirmation
- Prevent duplicate usernames

Successful account creation is logged as `CREATE_USER`.

## Evidence Handling Pipeline

This is the core forensic workflow in the project.

### File type restrictions

The app accepts only a defined set of extensions.

Allowed categories include:

- Images: jpg, jpeg, png, gif, bmp
- Video: mp4, avi, mov, mkv
- Audio: mp3, wav
- Documents: pdf, doc, docx, txt

### Upload flow

Route: `/upload`

Required permission: `upload`

Detailed behavior:

1. The user selects a file and submits the form
2. The app rejects empty submissions
3. The app rejects file types outside the allowed extension list
4. The original filename is sanitized with `os.path.basename()`
5. The file is saved temporarily as `temp_<filename>`
6. A SHA-256 hash of the plaintext file is generated
7. The plaintext file is encrypted into a temporary encrypted file using AES-256-GCM
8. The encrypted file is replicated to each storage node under `<original_filename>.enc`
9. A metadata row is inserted into the `evidence` table
10. A structured `UPLOAD` audit record is written
11. Temporary local files are deleted

Important design detail:

- The stored hash represents the original unencrypted evidence, not the encrypted payload
- The storage nodes contain only encrypted evidence copies

### Encryption behavior

Encryption is handled with AES-GCM using a 32-byte key.

If `EVIDENCE_AES_KEY` is configured correctly, that key is used.

If it is missing, the app derives a fallback key by hashing the Flask `SECRET_KEY`. This is acceptable for local development, but not ideal for production key management.

Encrypted file format:

- First 12 bytes: random nonce
- Remaining bytes: AES-GCM ciphertext including the authentication tag

### Replication behavior

The function `replicate_file()` copies the encrypted file to all three node directories.

This gives the project a local simulation of distributed evidence storage and redundancy. It is not yet true cloud or network-distributed storage.

## Integrity Verification Workflow

Route: `/verify`

Required permission: `verify`

Detailed behavior:

1. The user uploads a file they want to verify
2. The app stores it temporarily as `verify_<filename>`
3. The app computes the SHA-256 hash of that uploaded file
4. The app queries the `evidence` table by original filename
5. The new hash is compared with the stored hash
6. The temporary file is deleted
7. A structured log entry is written with result details
8. The result page reports either verification success or tampering detected

Verification outcomes:

- Matching hash: `Integrity Verified - No Tampering Detected`
- Non-matching hash or missing record: `Tampering Detected - File hash does not match stored record`

Important limitation:

- Verification currently matches evidence by filename, not by evidence ID or content fingerprint index. If multiple records reused the same filename, the lookup logic would be ambiguous.

## Evidence Inventory and Download Workflow

### Inventory listing

Route: `/evidence`

Required permission: `evidence`

The page lists every evidence record ordered by newest upload time first. Each row shows:

- Original filename
- Uploading user
- Upload timestamp
- Encryption algorithm used
- Download action

### Download flow

Route: `/download/<evidence_id>`

Required permission: `download`

Detailed behavior:

1. The app looks up the evidence record by database ID
2. It retrieves the original filename and encrypted stored filename
3. It searches each storage node for the encrypted file
4. It uses the first available copy it finds
5. It decrypts the file in memory
6. It writes a `DOWNLOAD` audit record
7. It streams the original file back to the browser as a download

Failure handling includes:

- Evidence record not found
- Encrypted replica missing from all nodes
- Decryption failure

Each failure path is logged to the audit table with status `failure`.

## Audit Logging and Chain of Custody

Route: `/logs`

Required permission: `logs`

This page provides a queryable chain-of-custody view backed by the `audit_logs` table.

### What gets logged

The system logs actions such as:

- `LOGIN`
- `LOGOUT`
- `UPLOAD`
- `VERIFY`
- `DOWNLOAD`
- `CREATE_USER`
- `ACCESS_DENIED`
- `EXPORT_LOGS`
- `PASSWORD HASH UPGRADE`

### Log fields captured

For each event, the app records:

- Acting username
- Current user role
- Action name
- Status such as `success`, `failure`, or `warning`
- Timestamp
- Source IP address
- Optional evidence ID
- Additional context in `details`

### Filtering behavior

The logs page supports filtering by:

- User
- Action
- Evidence filename
- Status

### CSV export

Route: `/logs/export`

This route applies the same filters used on the logs page, builds an in-memory CSV file, logs the export event, and sends the CSV to the browser.

### Fallback log file

If structured database logging fails because of a transient SQLite issue, the app falls back to writing a plaintext line into `audit_logs/audit.log`.

That means the project has both:

- A primary structured audit trail in SQLite
- A secondary legacy plaintext log file for resilience and backward compatibility

## User Interface Behavior

The application uses server-rendered HTML templates.

### Dashboard behavior

After login, users are sent to `/dashboard`.

The dashboard shows a role badge and only renders the cards the user is allowed to access. This means the UI mirrors backend authorization instead of showing links to pages the user cannot open.

Possible dashboard cards include:

- Upload Evidence
- Evidence Inventory
- Verify Integrity
- Audit Logs
- Manage Users

### Screen purposes

- Login page: sign in
- Dashboard: central navigation based on permissions
- Upload page: submit evidence for secure storage
- Verify page: confirm whether a file matches the stored hash
- Evidence page: browse and download stored evidence
- Logs page: inspect and export chain-of-custody records
- Register page: create authorized users
- Error page: display access or lookup failures

## Error Handling

The app has explicit handling for:

- Unauthenticated access: redirected to `/`
- Unauthorized access: 403 error page
- Missing routes: 404 error page
- Evidence download failures: handled with user-facing error messages and audit logs
- Transient log write failures: fallback to plaintext audit file

## Deployment Model

### Local development

Running `python app.py` starts the Flask development server with `debug=True`.

Local behavior includes:

- Runtime data stored in the project directory unless overridden
- SQLite database stored locally
- Storage nodes implemented as local folders

### Vercel deployment

The Vercel configuration points all requests to [api/index.py](/c:/Users/anura/OneDrive/Desktop/forensic2/api/index.py), which imports the Flask app object.

In this environment:

- The build uses `@vercel/python`
- The route config sends all paths to the Flask app
- Runtime data is redirected to `/tmp/forensic2`

Important practical note:

- Because the current design uses SQLite and local temporary storage, Vercel can host the app for demonstration purposes, but it is not a durable production storage model.

## Current Security Measures

What is already implemented:

- Session-based authentication
- bcrypt password hashing for new and migrated accounts
- Role-based route protection
- AES-256-GCM encryption at rest
- SHA-256 integrity hashing
- Source IP logging in audit records
- Restricted allowed file extensions

## Current Limitations and Gaps

The document should reflect the project as it exists now, including what is still incomplete.

### Architectural limitations

- Storage replication is local folder copying, not real distributed cloud storage
- SQLite is adequate for demo use, but not ideal for production concurrency and scale
- Runtime evidence storage is local filesystem based
- No formal storage node health checks or retry policies exist yet

### Workflow limitations

- Verification identifies records by filename only
- There is no evidence versioning model
- There is no delete, edit, or evidence update workflow
- There is no separate API version layer or JSON API design yet

### Security and operational limitations

- The fallback encryption key derives from `SECRET_KEY` when `EVIDENCE_AES_KEY` is missing
- The default admin account is seeded automatically if no admin exists, so this must be changed in any serious deployment
- There is no multi-factor authentication
- There is no external secret manager integration
- There are no automated tests in the project yet

## End-to-End Summary of How the System Works Today

From a user perspective, the current system works like this:

1. An administrator or existing user logs in
2. The dashboard shows only the tools allowed for that role
3. Authorized users upload evidence files
4. The app hashes the original file, encrypts it, and replicates encrypted copies to all three nodes
5. Metadata about the evidence is stored in SQLite
6. Every significant action is recorded in the structured audit log
7. Authorized users can browse the evidence inventory and download decrypted evidence on demand
8. Authorized users can upload a suspected file again to verify whether its hash still matches the stored original
9. Authorized users can inspect, filter, and export chain-of-custody logs

## Current Project Status

Based on the implementation and the progress notes, the system has already moved beyond a basic upload-and-verify demo. It now includes role-based access control, account management, encrypted storage, evidence download, and structured audit reporting.

What is still missing for a more production-ready forensic platform is mainly around infrastructure and hardening:

- real cloud-backed storage
- stronger operational key management
- production database migration
- automated testing
- scalability and resilience improvements

## Recommended Use of This Document

This file is intended to serve as the current-state technical explanation of the project. It is useful for:

- report writing
- viva or demo explanation
- onboarding another developer
- understanding what has already been implemented versus what remains

If the project changes further, this document should be updated alongside [PROGRESS.md](/c:/Users/anura/OneDrive/Desktop/forensic2/PROGRESS.md) so the implementation summary stays accurate.