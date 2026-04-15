from flask import Flask, render_template, request, redirect, session, flash, send_file, jsonify
import psycopg2
import psycopg2.errors
import hashlib
import os
import shutil
import bcrypt
import base64
import binascii
import csv
from datetime import datetime
from dotenv import load_dotenv
from functools import wraps
from io import BytesIO, StringIO
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from storage_adapter import get_storage_adapter

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change_this_before_production")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DATA_DIR = os.environ.get(
    "RUNTIME_DATA_DIR",
    "/tmp/forensic2" if os.environ.get("VERCEL") else BASE_DIR
)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required. Configure a PostgreSQL connection string.")

NODES = [
    os.path.join(RUNTIME_DATA_DIR, "storage_nodes", "node1"),
    os.path.join(RUNTIME_DATA_DIR, "storage_nodes", "node2"),
    os.path.join(RUNTIME_DATA_DIR, "storage_nodes", "node3")
]

LOG_FILE = os.path.join(RUNTIME_DATA_DIR, "audit_logs", "audit.log")

# Role hierarchy: what each role is allowed to do
# admin            → all actions
# police_officer   → upload, verify, view own logs
# forensic_analyst → verify, view logs (read evidence)
# court_authority  → view logs only (read-only)

ROLE_PERMISSIONS = {
    "admin":            {"upload", "verify", "logs", "manage_users", "evidence", "download"},
    "police_officer":   {"upload", "verify", "logs", "evidence", "download"},
    "forensic_analyst": {"verify", "logs", "evidence", "download"},
    "court_authority":  {"logs", "evidence", "download"},
}

VALID_ROLES = list(ROLE_PERMISSIONS.keys())

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp",
                      "mp4", "avi", "mov", "mkv",
                      "mp3", "wav",
                      "pdf", "doc", "docx", "txt"}


def ensure_runtime_dirs():
    os.makedirs(RUNTIME_DATA_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    for node in NODES:
        os.makedirs(node, exist_ok=True)


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


 
# Helpers
 

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def verify_and_migrate_password(username, entered_password, stored_password):
    if not stored_password:
        return False

    # Handle bcrypt-based accounts.
    if stored_password.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(entered_password.encode(), stored_password.encode())
        except ValueError:
            return False

    # Legacy plaintext support: allow login once, then upgrade to bcrypt.
    if entered_password == stored_password:
        upgraded_hash = bcrypt.hashpw(entered_password.encode(), bcrypt.gensalt()).decode()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE users SET password=%s WHERE username=%s", (upgraded_hash, username))
        conn.commit()
        conn.close()
        write_log(username, "PASSWORD HASH UPGRADE")
        return True

    return False


def get_encryption_key():
    env_value = os.environ.get("EVIDENCE_AES_KEY", "").strip()
    if env_value:
        try:
            key = base64.urlsafe_b64decode(env_value.encode())
            if len(key) != 32:
                raise ValueError("invalid key size")
            return key
        except (binascii.Error, ValueError):
            raise RuntimeError("EVIDENCE_AES_KEY must be URL-safe base64 for a 32-byte key")

    # Fallback for local development so encryption still works without env setup.
    return hashlib.sha256(app.secret_key.encode()).digest()


def encrypt_file(input_path, output_path):
    key = get_encryption_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)

    with open(input_path, "rb") as f:
        plaintext = f.read()

    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Store nonce prefix + ciphertext payload (ciphertext includes auth tag).
    with open(output_path, "wb") as f:
        f.write(nonce + ciphertext)


def decrypt_file(encrypted_path):
    """
    Decrypt an encrypted evidence file.
    Format: first 12 bytes are nonce, remainder is ciphertext (includes auth tag).
    Returns plaintext bytes or None on failure.
    """
    key = get_encryption_key()
    aesgcm = AESGCM(key)

    try:
        with open(encrypted_path, "rb") as f:
            data = f.read()

        if len(data) < 12:
            return None

        nonce = data[:12]
        ciphertext = data[12:]

        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext
    except Exception:
        return None


def decrypt_file_from_bytes(encrypted_data):
    """
    Decrypt encrypted data from raw bytes (as returned by storage adapter).
    Format: first 12 bytes are nonce, remainder is ciphertext (includes auth tag).
    Returns plaintext bytes or None on failure.
    """
    key = get_encryption_key()
    aesgcm = AESGCM(key)

    try:
        if len(encrypted_data) < 12:
            return None

        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]

        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext
    except Exception:
        return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated


def role_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user" not in session:
                return redirect("/")
            role = session.get("role", "")
            if permission not in ROLE_PERMISSIONS.get(role, set()):
                write_log(session["user"], "ACCESS_DENIED", status="failure", details=f"Permission: {permission}")
                return render_template("error.html",
                                       message="You do not have permission to access this page."), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def api_role_required(permission):
    """API variant of role checks that returns JSON errors instead of redirects."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user" not in session:
                return jsonify({"error": "authentication_required"}), 401
            role = session.get("role", "")
            if permission not in ROLE_PERMISSIONS.get(role, set()):
                write_log(session["user"], "ACCESS_DENIED", status="failure", details=f"API Permission: {permission}")
                return jsonify({"error": "forbidden", "message": "Insufficient permissions."}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def is_valid_sha256(hex_string):
    if not hex_string or len(hex_string) != 64:
        return False
    try:
        int(hex_string, 16)
        return True
    except ValueError:
        return False


# Database Initialization
 

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS evidence(
        id SERIAL PRIMARY KEY,
        filename TEXT,
        hash TEXT,
        uploaded_by TEXT,
        upload_time TEXT,
        encrypted_filename TEXT,
        encryption_algo TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS audit_logs(
        id SERIAL PRIMARY KEY,
        evidence_id INTEGER,
        username TEXT,
        user_role TEXT,
        action TEXT,
        status TEXT,
        timestamp TEXT,
        source_ip TEXT,
        details TEXT,
        FOREIGN KEY(evidence_id) REFERENCES evidence(id)
    )
    ''')

    # Indexes for faster evidence lookup and audit filtering.
    c.execute("CREATE INDEX IF NOT EXISTS idx_evidence_filename ON evidence(filename)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_evidence_upload_time ON evidence(upload_time)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_logs(username)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_evidence_id ON audit_logs(evidence_id)")

    # Seed a default admin if none exists
    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if c.fetchone()[0] == 0:
        hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt())
        c.execute("INSERT INTO users(username,password,role) VALUES(%s,%s,%s)",
                  ("admin", hashed.decode(), "admin"))

    conn.commit()
    conn.close()


ensure_runtime_dirs()
init_db()

# Initialize storage adapter
storage_adapter = get_storage_adapter()


 
# Audit Logging
 

def get_remote_ip():
    """Extract client IP from request headers or fallback to connection IP."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or "unknown"


def write_log(username, action, evidence_id=None, status="success", details=""):
    """
    Structured chain-of-custody logging to database.
    - username: who performed the action
    - action: what was done (UPLOAD, DOWNLOAD, VERIFY, LOGIN, etc.)
    - evidence_id: optional link to evidence record
    - status: success/failure/warning
    - details: optional extra context
    """
    role = session.get("role", "unknown") if "user" in session else "unknown"
    source_ip = get_remote_ip()
    timestamp = str(datetime.now())

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO audit_logs(username, user_role, action, status, timestamp, source_ip, evidence_id, details)
            VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
        """, (username, role, action, status, timestamp, source_ip, evidence_id, details))
        conn.commit()
        conn.close()
    except psycopg2.Error:
        # Avoid crashing primary action if logging fails under transient lock.
        write_log_file(username, f"{action} status={status} details={details}")


# Legacy plaintext log support (still write to file for backwards compatibility)
def write_log_file(user, action):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] USER:{user} ACTION:{action}\n")


 
# SHA256 Hash
 

def generate_hash(path):
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


 
# Distributed Storage Replication
#
# Note: Storage operations are now delegated to the storage adapter.
# See storage_adapter.py for backend implementations.


 
# LOGIN
 

@app.route("/", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect("/dashboard")

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            error = "Please enter both username and password."
        else:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT password, role FROM users WHERE username=%s", (username,))
            result = c.fetchone()
            conn.close()

            if result and verify_and_migrate_password(username, password, result[0]):
                session["user"] = username
                session["role"] = result[1]
                write_log(username, "LOGIN", status="success")
                return redirect("/dashboard")
            else:
                error = "Invalid username or password."
                write_log(username, "LOGIN", status="failure", details="Invalid credentials")

    return render_template("login.html", error=error)


 
# REGISTER (Admin only creates accounts)
 

@app.route("/register", methods=["GET", "POST"])
@role_required("manage_users")
def register():
    error = None
    success = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")
        role     = request.form.get("role", "")

        if not username or not password or not role:
            error = "All fields are required."
        elif role not in VALID_ROLES:
            error = "Invalid role selected."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            try:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO users(username,password,role) VALUES(%s,%s,%s)",
                          (username, hashed.decode(), role))
                conn.commit()
                write_log(session["user"], "CREATE_USER", status="success", details=f"Username: {username}, Role: {role}")
                success = f"User '{username}' created successfully."
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                error = f"Username '{username}' already exists."
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    return render_template("register.html", error=error, success=success, roles=VALID_ROLES)


 
# DASHBOARD
 

@app.route("/dashboard")
@login_required
def dashboard():
    role = session.get("role", "")
    permissions = ROLE_PERMISSIONS.get(role, set())
    return render_template("dashboard.html",
                           user=session["user"],
                           role=role,
                           permissions=permissions)


 
# UPLOAD EVIDENCE
 

@app.route("/upload", methods=["GET", "POST"])
@role_required("upload")
def upload():
    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            return render_template("upload.html", error="No file selected.")

        if not allowed_file(file.filename):
            return render_template("upload.html",
                                   error="File type not allowed. Accepted: images, video, audio, PDF, documents.")

        safe_name = os.path.basename(file.filename)
        temp_plain = "temp_" + safe_name
        temp_encrypted = "enc_" + safe_name + ".bin"
        encrypted_name = safe_name + ".enc"

        try:
            file.save(temp_plain)

            # Preserve original-file hash for integrity verification.
            hash_value = generate_hash(temp_plain)

            # Encrypt file at rest using AES-256-GCM, then replicate encrypted payload via storage adapter.
            encrypt_file(temp_plain, temp_encrypted)
            storage_adapter.put(temp_encrypted, encrypted_name)

            conn = get_db_connection()
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO evidence(filename,hash,uploaded_by,upload_time,encrypted_filename,encryption_algo)
                VALUES(%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (safe_name, hash_value, session["user"], str(datetime.now()), encrypted_name, "AES-256-GCM")
            )
            ev_id = c.fetchone()[0]
            conn.commit()
            conn.close()

            write_log(session["user"], "UPLOAD", evidence_id=ev_id, status="success", details=f"Filename: {safe_name}, Encrypted: {encrypted_name}")
        finally:
            if os.path.exists(temp_plain):
                os.remove(temp_plain)
            if os.path.exists(temp_encrypted):
                os.remove(temp_encrypted)

        return render_template("upload.html", success=f"'{safe_name}' uploaded and replicated successfully.")

    return render_template("upload.html")


 
# VERIFY INTEGRITY
 

@app.route("/verify", methods=["GET", "POST"])
@role_required("verify")
def verify():
    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            return render_template("verify.html", error="No file selected.")

        safe_name = os.path.basename(file.filename)
        path = "verify_" + safe_name
        file.save(path)

        new_hash = generate_hash(path)

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT hash FROM evidence WHERE filename=%s", (safe_name,))
        result = c.fetchone()
        conn.close()

        os.remove(path)

        if result and result[0] == new_hash:
            write_log(session["user"], "VERIFY", status="success", details=f"Filename: {safe_name}, Result: PASSED")
            return render_template("verify.html",
                                   result="verified",
                                   message="Integrity Verified — No Tampering Detected.")
        else:
            write_log(session["user"], "VERIFY", status="warning", details=f"Filename: {safe_name}, Result: TAMPER_DETECTED")
            return render_template("verify.html",
                                   result="tampered",
                                   message="Tampering Detected — File hash does not match stored record.")

    return render_template("verify.html")


 
# EVIDENCE INVENTORY
 

@app.route("/evidence")
@role_required("evidence")
def evidence():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, filename, uploaded_by, upload_time, encryption_algo 
        FROM evidence 
        ORDER BY upload_time DESC
    """)
    rows = c.fetchall()
    conn.close()

    evidence_list = []
    for row in rows:
        evidence_list.append({
            "id": row[0],
            "filename": row[1],
            "uploaded_by": row[2],
            "upload_time": row[3],
            "encryption_algo": row[4] or "None"
        })

    return render_template("evidence.html", evidence=evidence_list, user=session["user"], role=session.get("role"))


 
# DOWNLOAD EVIDENCE (Decrypt & Serve)
 

@app.route("/download/<int:evidence_id>")
@role_required("download")
def download(evidence_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT filename, encrypted_filename FROM evidence WHERE id=%s", (evidence_id,))
    result = c.fetchone()
    conn.close()

    if not result:
        write_log(session["user"], "DOWNLOAD", evidence_id=evidence_id, status="failure", details="Evidence not found")
        return render_template("error.html", message="Evidence not found."), 404

    original_filename, encrypted_filename = result

    # Retrieve encrypted file from storage adapter
    try:
        plaintext = storage_adapter.get(encrypted_filename)
    except FileNotFoundError:
        write_log(session["user"], "DOWNLOAD", evidence_id=evidence_id, status="failure", details="Encrypted copy not found in storage")
        return render_template("error.html", message="Encrypted evidence file not found in storage."), 404
    except Exception as e:
        write_log(session["user"], "DOWNLOAD", evidence_id=evidence_id, status="failure", details=f"Storage retrieval failed: {str(e)}")
        return render_template("error.html", message="Failed to retrieve evidence file from storage."), 500

    # Decrypt
    plaintext_decrypted = decrypt_file_from_bytes(plaintext)
    if plaintext_decrypted is None:
        write_log(session["user"], "DOWNLOAD", evidence_id=evidence_id, status="failure", details="Decryption failed")
        return render_template("error.html", message="Failed to decrypt evidence file."), 500
    
    plaintext = plaintext_decrypted

    # Log successful download
    write_log(session["user"], "DOWNLOAD", evidence_id=evidence_id, status="success", details=f"Filename: {original_filename}")

    # Return file as response for browser download
    return send_file(
        BytesIO(plaintext),
        as_attachment=True,
        download_name=original_filename,
        mimetype="application/octet-stream"
    )


 
# VIEW AUDIT LOGS
 

@app.route("/logs")
@role_required("logs")
def logs():
    filter_user   = request.args.get("user", "").strip()
    filter_action = request.args.get("action", "").strip().upper()
    filter_evidence = request.args.get("evidence", "").strip()
    filter_status = request.args.get("status", "").strip()

    conn = get_db_connection()
    c = conn.cursor()

    query = """
        SELECT al.id, al.username, al.user_role, al.action, al.status, 
               al.timestamp, al.source_ip, al.evidence_id, e.filename, al.details
        FROM audit_logs al
        LEFT JOIN evidence e ON al.evidence_id = e.id
        WHERE 1=1
    """
    params = []

    if filter_user:
        query += " AND al.username ILIKE %s"
        params.append(f"%{filter_user}%")

    if filter_action:
        query += " AND al.action = %s"
        params.append(filter_action)

    if filter_evidence:
        query += " AND e.filename ILIKE %s"
        params.append(f"%{filter_evidence}%")

    if filter_status:
        query += " AND al.status = %s"
        params.append(filter_status)

    query += " ORDER BY al.timestamp DESC"

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    logs_data = []
    for row in rows:
        logs_data.append({
            "id": row[0],
            "username": row[1],
            "role": row[2],
            "action": row[3],
            "status": row[4],
            "timestamp": row[5],
            "ip": row[6],
            "evidence_id": row[7],
            "evidence_filename": row[8],
            "details": row[9]
        })

    return render_template("logs.html", logs=logs_data,
                           filter_user=filter_user,
                           filter_action=filter_action,
                           filter_evidence=filter_evidence,
                           filter_status=filter_status,
                           total_count=len(logs_data))


 
# EXPORT AUDIT LOGS AS CSV
 

@app.route("/logs/export")
@role_required("logs")
def export_logs():
    import csv

    filter_user   = request.args.get("user", "").strip()
    filter_action = request.args.get("action", "").strip().upper()
    filter_evidence = request.args.get("evidence", "").strip()
    filter_status = request.args.get("status", "").strip()

    conn = get_db_connection()
    c = conn.cursor()

    query = """
        SELECT al.username, al.user_role, al.action, al.status, 
               al.timestamp, al.source_ip, al.evidence_id, e.filename, al.details
        FROM audit_logs al
        LEFT JOIN evidence e ON al.evidence_id = e.id
        WHERE 1=1
    """
    params = []

    if filter_user:
        query += " AND al.username ILIKE %s"
        params.append(f"%{filter_user}%")

    if filter_action:
        query += " AND al.action = %s"
        params.append(filter_action)

    if filter_evidence:
        query += " AND e.filename ILIKE %s"
        params.append(f"%{filter_evidence}%")

    if filter_status:
        query += " AND al.status = %s"
        params.append(filter_status)

    query += " ORDER BY al.timestamp DESC"

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "Username", "Role", "Action", "Status", "Timestamp", "Source IP", "Evidence ID", "Evidence Name", "Details"
    ])
    
    for row in rows:
        writer.writerow(row)

    # Convert to bytes for download
    csv_bytes = output.getvalue().encode('utf-8')

    write_log(session["user"], "EXPORT_LOGS", status="success", 
              details=f"Exported {len(rows)} records")

    return send_file(
        BytesIO(csv_bytes),
        as_attachment=True,
        download_name=f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mimetype="text/csv"
    )


 
# LOGOUT
 

@app.route("/logout")
@login_required
def logout():
    write_log(session["user"], "LOGOUT", status="success")
    session.clear()
    return redirect("/")


# HEALTH CHECK
 

@app.route("/health")
def health():
    """
    Health check endpoint for monitoring.
    Returns JSON with database and storage status.
    """
    import json
    
    health_report = {
        "app": "forensic-evidence-manager",
        "timestamp": str(datetime.now()),
        "database": "unknown",
        "storage": "unknown",
    }
    
    # Check database
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        conn.close()
        health_report["database"] = f"ok ({user_count} users)"
    except Exception as e:
        health_report["database"] = f"error: {str(e)}"
    
    # Check storage
    try:
        storage_status = storage_adapter.health_check()
        health_report["storage"] = storage_status
    except Exception as e:
        health_report["storage"] = {"healthy": False, "message": f"Error: {str(e)}"}
    
    status_code = 200 if (health_report["database"].startswith("ok") and health_report["storage"].get("healthy")) else 503
    return json.dumps(health_report), status_code, {"Content-Type": "application/json"}


# API V1


@app.route("/api/v1/health")
def api_health():
    """Versioned JSON health endpoint."""
    import json
    payload, status, _headers = health()
    return jsonify({"version": "v1", "health": json.loads(payload)}), status


@app.route("/api/v1/evidence", methods=["GET"])
@api_role_required("evidence")
def api_list_evidence():
    """List evidence metadata with optional pagination limit."""
    limit_raw = request.args.get("limit", "50").strip()
    try:
        limit = int(limit_raw)
    except ValueError:
        return jsonify({"error": "invalid_limit", "message": "limit must be an integer between 1 and 100"}), 400

    if limit < 1 or limit > 100:
        return jsonify({"error": "invalid_limit", "message": "limit must be between 1 and 100"}), 400

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, filename, uploaded_by, upload_time, encryption_algo
        FROM evidence
        ORDER BY upload_time DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = c.fetchall()
    conn.close()

    items = []
    for row in rows:
        items.append(
            {
                "id": row[0],
                "filename": row[1],
                "uploaded_by": row[2],
                "upload_time": row[3],
                "encryption_algo": row[4] or "None",
            }
        )

    return jsonify({"version": "v1", "count": len(items), "items": items})


@app.route("/api/v1/verify/hash", methods=["POST"])
@api_role_required("verify")
def api_verify_hash():
    """Verify file integrity by comparing submitted SHA-256 with stored value."""
    payload = request.get_json(silent=True) or {}
    filename = os.path.basename((payload.get("filename") or "").strip())
    sha256_hash = (payload.get("sha256") or "").strip().lower()

    if not filename:
        return jsonify({"error": "validation_error", "message": "filename is required"}), 400

    if not is_valid_sha256(sha256_hash):
        return jsonify({"error": "validation_error", "message": "sha256 must be a valid 64-char hex string"}), 400

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, hash FROM evidence WHERE filename=%s ORDER BY id DESC LIMIT 1", (filename,))
    row = c.fetchone()
    conn.close()

    if not row:
        write_log(session["user"], "VERIFY_API", status="failure", details=f"Filename not found: {filename}")
        return jsonify({"error": "not_found", "message": "evidence file not found"}), 404

    evidence_id, stored_hash = row
    verified = stored_hash == sha256_hash
    write_log(
        session["user"],
        "VERIFY_API",
        evidence_id=evidence_id,
        status="success" if verified else "warning",
        details=f"Filename: {filename}, Result: {'PASSED' if verified else 'TAMPER_DETECTED'}",
    )

    return jsonify(
        {
            "version": "v1",
            "filename": filename,
            "evidence_id": evidence_id,
            "verified": verified,
            "message": "Integrity Verified" if verified else "Tampering Detected",
        }
    )



# ERROR HANDLERS


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", message="Access Denied."), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", message="Page not found."), 404


if __name__ == "__main__":
    app.run(debug=True)