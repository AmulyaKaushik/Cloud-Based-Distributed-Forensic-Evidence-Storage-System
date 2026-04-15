# Forensic Evidence Management System

A secure, web-based application for managing and verifying forensic evidence with built-in integrity checks, distributed storage, and comprehensive audit logging.

## Overview

This forensic evidence management system is designed to handle the secure storage, verification, and tracking of digital evidence. It provides a secure chain-of-custody through:

- **User Authentication**: Role-based login system
- **Evidence Upload**: SHA256 hashing for integrity verification
- **Distributed Storage**: Automatic replication across 3 storage nodes for redundancy
- **Integrity Verification**: Detect tampering by comparing file hashes
- **Audit Logging**: Complete audit trail of all user actions
- **Dashboard**: Intuitive interface for managing evidence

## Features

### 🔐 Authentication & Authorization
- User login with role-based access control
- Session management
- Secure logout functionality

### 📤 Evidence Upload
- Upload files as evidence
- Automatic SHA256 hash generation for integrity verification
- Files are replicated across 3 distributed storage nodes
- Audit log entry created for each upload

### ✅ Integrity Verification
- Verify evidence hasn't been tampered with
- Compare file hash against stored hash value
- Immediate tampering detection

### 📊 Audit Logging
- Complete audit trail of all activities:
  - User logins/logouts
  - Evidence uploads
  - Integrity verification checks
  - Tampering detection alerts
- Timestamped entries with user information

### 🖥️ Web Interface
- Responsive dashboard
- Login page
- Evidence upload form
- Integrity verification interface
- Audit logs viewer

## Project Structure

```
forensic2/
├── app.py                    # Main Flask application
├── storage_adapter.py       # Pluggable storage backend adapters
├── README.md                # This file
├── templates/               # HTML templates
│   ├── dashboard.html       # Main dashboard
│   ├── login.html          # Login page
│   ├── logs.html           # Audit logs viewer
│   ├── upload.html         # Evidence upload form
│   └── verify.html         # Evidence verification form
├── static/                  # Static assets
│   └── style.css           # CSS styling
├── storage_nodes/          # Distributed storage for evidence
│   ├── node1/              # Storage node 1
│   ├── node2/              # Storage node 2
│   └── node3/              # Storage node 3
└── audit_logs/             # Audit trail
    └── audit.log           # Timestamped audit entries
```

## Installation & Setup

### Requirements
- Python 3.x
- Flask
- PostgreSQL

### Installation Steps

1. **Install Dependencies**
   ```
   pip install -r requirements.txt
   ```

2. **Initialize Database**
   Set PostgreSQL connection string:
   ```
   set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/forensic2
   ```
   Database tables are automatically initialized on first run.

3. **Create Storage Directories**
   ```
   mkdir -p storage_nodes/node1
   mkdir -p storage_nodes/node2
   mkdir -p storage_nodes/node3
   mkdir -p audit_logs
   ```

4. **Run the Application**
   ```
   python app.py
   ```

5. **Access the Application**
   Open your browser and navigate to `http://localhost:5000`

## Default Credentials

If no admin exists, the app auto-seeds this account on startup:
- Username: admin
- Password: admin123

## Database Schema

### Users Table
```sql
CREATE TABLE users(
   id SERIAL PRIMARY KEY,
    username TEXT,
    password TEXT,
    role TEXT
)
```

### Evidence Table
```sql
CREATE TABLE evidence(
   id SERIAL PRIMARY KEY,
    filename TEXT,
    hash TEXT,
    uploaded_by TEXT,
   upload_time TEXT,
   encrypted_filename TEXT,
   encryption_algo TEXT
)
```

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET, POST | Login page |
| `/dashboard` | GET | Main dashboard |
| `/upload` | GET, POST | Upload evidence |
| `/verify` | GET, POST | Verify evidence integrity |
| `/logs` | GET | View audit logs |
| `/logout` | GET | Logout user |

## How It Works

### Evidence Upload Flow
1. User logs in with credentials
2. Navigates to upload page
3. Selects file to upload
4. File is saved temporarily
5. SHA256 hash is generated
6. File is replicated to all 3 storage nodes
7. Evidence record is stored in database with hash value
8. Temporary file is deleted
9. Audit log entry is recorded

### Integrity Verification Flow
1. User uploads a file in the verify page
2. SHA256 hash is generated for the uploaded file
3. Hash is compared with stored hash in database
4. If hashes match: **Integrity Verified**
5. If hashes differ: **Tampering Detected**
6. Audit log is updated accordingly

### Distributed Storage
Files are automatically replicated across three storage nodes:
- `storage_nodes/node1/`
- `storage_nodes/node2/`
- `storage_nodes/node3/`

This ensures redundancy and prevents loss of evidence in case of storage failure.

## Audit Logging

All activities are logged with timestamps:
```
[YYYY-MM-DD HH:MM:SS.MMMMMM] USER:username ACTION:action_details
```

Examples:
- `[2026-03-11 10:30:45.123456] USER:investigator1 ACTION:LOGIN`
- `[2026-03-11 10:31:20.654321] USER:investigator1 ACTION:UPLOAD evidence.jpg`
- `[2026-03-11 10:32:10.987654] USER:investigator1 ACTION:VERIFY evidence.jpg`
- `[2026-03-11 10:33:05.456789] USER:investigator1 ACTION:LOGOUT`

## Security Considerations

- Change the secret key in `app.py` before production deployment
- Use HTTPS for production environments
- Implement stronger password hashing (consider bcrypt instead of plain text storage)
- Restrict file upload size limits
- Implement role-based access controls more granularly
- Use proper database connection pooling

## Future Enhancements

- Role-based access control for specific functionalities
- Advanced search and filtering in audit logs
- File retention policies
- Multi-factor authentication
- Encryption at rest for sensitive files
- API endpoints for integration with other systems
- Performance dashboard with storage metrics
- User management interface

## License

[Specify your license here]

## Support

For issues or questions, contact the development team.
