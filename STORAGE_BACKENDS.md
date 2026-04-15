## Storage Backend Configuration

The forensic evidence management system now uses a pluggable storage adapter that supports multiple backends for storing encrypted evidence.

### Backends

#### Local Storage (Default)
Replicates encrypted evidence to three local directories on the same machine.

**Configuration:**
```bash
export STORAGE_BACKEND=local
export RUNTIME_DATA_DIR=/path/to/storage  # Optional; defaults to project root or /tmp/forensic2 on Vercel
```

**Use case:** Development, testing, and small-scale deployments where local redundancy is sufficient.

#### AWS S3
Stores encrypted evidence directly to Amazon S3 with built-in redundancy and availability.

**Prerequisites:**
- Install boto3: `pip install boto3`
- AWS credentials configured (via environment variables, IAM role, or ~/.aws/credentials)

**Configuration:**
```bash
export STORAGE_BACKEND=s3
export S3_BUCKET_NAME=my-forensic-evidence-bucket
export AWS_REGION=us-east-1  # Optional; defaults to us-east-1
```

**Use case:** Production deployments requiring cloud-scale availability, automatic backups, and global access.

### Health Check Endpoint

Monitor storage and database status:

```bash
curl http://localhost:5000/health
```

Response:
```json
{
  "app": "forensic-evidence-manager",
  "timestamp": "2026-04-15 12:34:56.789012",
  "database": "ok (5 users)",
  "storage": {
    "healthy": true,
    "message": "All nodes accessible" 
  }
}
```

HTTP Status:
- **200**: All systems operational
- **503**: Database or storage unavailable

### Implementation Details

- **StorageAdapter**: Abstract base class defining put(), get(), exists(), delete(), health_check()
- **LocalStorageAdapter**: Replicates to `storage_nodes/node1`, `node2`, `node3` directories using shutil
- **S3StorageAdapter**: Uses boto3 to manage S3 operations

### Future Backends

Additional backends can be added by extending `StorageAdapter` in `storage_adapter.py`:
- HDFS (distributed file system)
- GCP Cloud Storage
- MinIO (S3-compatible)
- Azure Blob Storage

### File Naming in Storage

Encrypted evidence files are stored with `.enc` extension to indicate encrypted state:
- Original filename: `evidence.pdf`
- Stored as: `evidence.pdf.enc`
- Hash: SHA-256 of plaintext (stored in database)
- Content: AES-256-GCM encrypted with random nonce prepended

### Migration Example

To migrate from local storage to S3:

1. Set up S3 bucket and AWS credentials
2. Update environment configuration:
   ```bash
   export STORAGE_BACKEND=s3
   export S3_BUCKET_NAME=forensic-bucket
   ```
3. Restart the application
4. New uploads automatically use S3
5. Existing local files remain accessible if both backends are available during transition period
