from flask import Flask, render_template, request, redirect, session, flash, send_file
import sqlite3
import hashlib
import os
import shutil
import bcrypt
import base64
import binascii
from datetime import datetime
from dotenv import load_dotenv
from functools import wraps
from io import BytesIO
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change_this_before_production")

DB = "database.db"

NODES = [
    "storage_nodes/node1/",
    "storage_nodes/node2/",
    "storage_nodes/node3/"
]

LOG_FILE = "audit_logs/audit.log"

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


# -------------------------------
# Helpers
# -------------------------------

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
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("UPDATE users SET password=? WHERE username=?", (upgraded_hash, username))
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
                write_log(session["user"], f"ACCESS DENIED {permission}")
                return render_template("error.html",
                                       message="You do not have permission to access this page."), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# -------------------------------
# Database Initialization
# -------------------------------

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS evidence(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        hash TEXT,
        uploaded_by TEXT,
        upload_time TEXT
    )
    ''')

    evidence_columns = {row[1] for row in c.execute("PRAGMA table_info(evidence)").fetchall()}
    if "encrypted_filename" not in evidence_columns:
        c.execute("ALTER TABLE evidence ADD COLUMN encrypted_filename TEXT")
    if "encryption_algo" not in evidence_columns:
        c.execute("ALTER TABLE evidence ADD COLUMN encryption_algo TEXT")

    # Seed a default admin if none exists
    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if c.fetchone()[0] == 0:
        hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt())
        c.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                  ("admin", hashed.decode(), "admin"))

    conn.commit()
    conn.close()


# -------------------------------
# Audit Logging
# -------------------------------

def write_log(user, action):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] USER:{user} ACTION:{action}\n")


# -------------------------------
# SHA256 Hash
# -------------------------------

def generate_hash(path):
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


# -------------------------------
# Distributed Storage Replication
# -------------------------------

def replicate_file(filepath, stored_name=None):
    for node in NODES:
        destination = os.path.join(node, stored_name or os.path.basename(filepath))
        shutil.copy(filepath, destination)


# -------------------------------
# LOGIN
# -------------------------------

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
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            c.execute("SELECT password, role FROM users WHERE username=?", (username,))
            result = c.fetchone()
            conn.close()

            if result and verify_and_migrate_password(username, password, result[0]):
                session["user"] = username
                session["role"] = result[1]
                write_log(username, "LOGIN")
                return redirect("/dashboard")
            else:
                error = "Invalid username or password."
                write_log(username, "FAILED LOGIN")

    return render_template("login.html", error=error)


# -------------------------------
# REGISTER (Admin only creates accounts)
# -------------------------------

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
                conn = sqlite3.connect(DB)
                c = conn.cursor()
                c.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                          (username, hashed.decode(), role))
                conn.commit()
                conn.close()
                write_log(session["user"], f"CREATED USER {username} ROLE {role}")
                success = f"User '{username}' created successfully."
            except sqlite3.IntegrityError:
                error = f"Username '{username}' already exists."

    return render_template("register.html", error=error, success=success, roles=VALID_ROLES)


# -------------------------------
# DASHBOARD
# -------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    role = session.get("role", "")
    permissions = ROLE_PERMISSIONS.get(role, set())
    return render_template("dashboard.html",
                           user=session["user"],
                           role=role,
                           permissions=permissions)


# -------------------------------
# UPLOAD EVIDENCE
# -------------------------------

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

            # Encrypt file at rest using AES-256-GCM, then replicate encrypted payload.
            encrypt_file(temp_plain, temp_encrypted)
            replicate_file(temp_encrypted, stored_name=encrypted_name)

            conn = sqlite3.connect(DB)
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO evidence(filename,hash,uploaded_by,upload_time,encrypted_filename,encryption_algo)
                VALUES(?,?,?,?,?,?)
                """,
                (safe_name, hash_value, session["user"], str(datetime.now()), encrypted_name, "AES-256-GCM")
            )
            conn.commit()
            conn.close()

            write_log(session["user"], f"UPLOAD {safe_name} ENCRYPTED {encrypted_name}")
        finally:
            if os.path.exists(temp_plain):
                os.remove(temp_plain)
            if os.path.exists(temp_encrypted):
                os.remove(temp_encrypted)

        return render_template("upload.html", success=f"'{safe_name}' uploaded and replicated successfully.")

    return render_template("upload.html")


# -------------------------------
# VERIFY INTEGRITY
# -------------------------------

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

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT hash FROM evidence WHERE filename=?", (safe_name,))
        result = c.fetchone()
        conn.close()

        os.remove(path)

        if result and result[0] == new_hash:
            write_log(session["user"], f"VERIFY {safe_name} PASSED")
            return render_template("verify.html",
                                   result="verified",
                                   message="Integrity Verified — No Tampering Detected.")
        else:
            write_log(session["user"], f"VERIFY {safe_name} TAMPER DETECTED")
            return render_template("verify.html",
                                   result="tampered",
                                   message="Tampering Detected — File hash does not match stored record.")

    return render_template("verify.html")


# -------------------------------
# EVIDENCE INVENTORY
# -------------------------------

@app.route("/evidence")
@role_required("evidence")
def evidence():
    conn = sqlite3.connect(DB)
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


# -------------------------------
# DOWNLOAD EVIDENCE (Decrypt & Serve)
# -------------------------------

@app.route("/download/<int:evidence_id>")
@role_required("download")
def download(evidence_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT filename, encrypted_filename FROM evidence WHERE id=?", (evidence_id,))
    result = c.fetchone()
    conn.close()

    if not result:
        write_log(session["user"], f"DOWNLOAD FAILED evidence_id={evidence_id} NOT_FOUND")
        return render_template("error.html", message="Evidence not found."), 404

    original_filename, encrypted_filename = result

    # Try to recover encrypted file from storage nodes
    encrypted_path = None
    for node in NODES:
        candidate = os.path.join(node, encrypted_filename)
        if os.path.exists(candidate):
            encrypted_path = candidate
            break

    if not encrypted_path:
        write_log(session["user"], f"DOWNLOAD FAILED {original_filename} NO_ENCRYPTED_COPY")
        return render_template("error.html", message="Encrypted evidence file not found in storage."), 404

    # Decrypt
    plaintext = decrypt_file(encrypted_path)
    if plaintext is None:
        write_log(session["user"], f"DOWNLOAD FAILED {original_filename} DECRYPTION_ERROR")
        return render_template("error.html", message="Failed to decrypt evidence file."), 500

    # Log successful download
    write_log(session["user"], f"DOWNLOAD {original_filename} SUCCESS")

    # Return file as response for browser download
    return send_file(
        BytesIO(plaintext),
        as_attachment=True,
        download_name=original_filename,
        mimetype="application/octet-stream"
    )


# -------------------------------
# VIEW AUDIT LOGS
# -------------------------------

@app.route("/logs")
@role_required("logs")
def logs():
    filter_user   = request.args.get("user", "").strip()
    filter_action = request.args.get("action", "").strip().upper()

    with open(LOG_FILE, "r") as f:
        data = f.readlines()

    # Filter to lines that are actual log entries (skip any stray HTML)
    data = [line for line in data if line.startswith("[")]

    if filter_user:
        data = [l for l in data if f"USER:{filter_user}" in l]
    if filter_action:
        data = [l for l in data if f"ACTION:{filter_action}" in l]

    return render_template("logs.html", logs=data,
                           filter_user=filter_user,
                           filter_action=filter_action)


# -------------------------------
# LOGOUT
# -------------------------------

@app.route("/logout")
@login_required
def logout():
    write_log(session["user"], "LOGOUT")
    session.clear()
    return redirect("/")


# -------------------------------
# ERROR HANDLERS
# -------------------------------

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", message="Access Denied."), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", message="Page not found."), 404


if __name__ == "__main__":
    init_db()
    app.run(debug=True)