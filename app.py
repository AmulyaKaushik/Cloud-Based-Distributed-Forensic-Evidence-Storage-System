from flask import Flask, render_template, request, redirect, session
import sqlite3
import hashlib
import os
import shutil
from datetime import datetime

app = Flask(__name__)
app.secret_key = "forensic_secret_key"

DB = "database.db"

NODES = [
    "storage_nodes/node1/",
    "storage_nodes/node2/",
    "storage_nodes/node3/"
]

LOG_FILE = "audit_logs/audit.log"


# -------------------------------
# Database Initialization
# -------------------------------

def init_db():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
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

    conn.commit()
    conn.close()


# -------------------------------
# Audit Logging
# -------------------------------

def write_log(user, action):

    with open(LOG_FILE,"a") as f:
        f.write(f"[{datetime.now()}] USER:{user} ACTION:{action}\n")


# -------------------------------
# SHA256 Hash
# -------------------------------

def generate_hash(path):

    sha = hashlib.sha256()

    with open(path,'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha.update(chunk)

    return sha.hexdigest()


# -------------------------------
# Distributed Storage Replication
# -------------------------------

def replicate_file(filepath):

    for node in NODES:
        shutil.copy(filepath,node)


# -------------------------------
# LOGIN
# -------------------------------

@app.route("/", methods=["GET","POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        c.execute("SELECT role FROM users WHERE username=? AND password=?",(username,password))
        result = c.fetchone()

        conn.close()

        if result:

            session["user"] = username
            session["role"] = result[0]

            write_log(username,"LOGIN")

            return redirect("/dashboard")

    return render_template("login.html")


# -------------------------------
# DASHBOARD
# -------------------------------

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/")

    return render_template("dashboard.html",
                           user=session["user"],
                           role=session["role"])


# -------------------------------
# UPLOAD EVIDENCE
# -------------------------------

@app.route("/upload", methods=["GET","POST"])
def upload():

    if "user" not in session:
        return redirect("/")

    if request.method == "POST":

        file = request.files["file"]
        filepath = "temp_" + file.filename
        file.save(filepath)

        hash_value = generate_hash(filepath)

        replicate_file(filepath)

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        c.execute("INSERT INTO evidence(filename,hash,uploaded_by,upload_time) VALUES(?,?,?,?)",
                  (file.filename,hash_value,session["user"],str(datetime.now())))

        conn.commit()
        conn.close()

        write_log(session["user"],f"UPLOAD {file.filename}")

        os.remove(filepath)

        return '''
<h2>Evidence Uploaded Successfully</h2>

<a href="/upload"><button>Add More Evidence</button></a>

<a href="/dashboard"><button>Return to Main Menu</button></a>
'''

    return render_template("upload.html")


# -------------------------------
# VERIFY INTEGRITY
# -------------------------------

@app.route("/verify", methods=["GET","POST"])
def verify():

    if "user" not in session:
        return redirect("/")

    if request.method == "POST":

        file = request.files["file"]

        path = "verify_" + file.filename
        file.save(path)

        new_hash = generate_hash(path)

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        c.execute("SELECT hash FROM evidence WHERE filename=?",(file.filename,))
        result = c.fetchone()

        conn.close()

        os.remove(path)

        if result and result[0] == new_hash:

            write_log(session["user"],f"VERIFY {file.filename}")

            return "Integrity Verified. No Tampering."

        else:

            write_log(session["user"],f"TAMPER DETECTED {file.filename}")

            return "Tampering Detected"

    return render_template("verify.html")


# -------------------------------
# VIEW AUDIT LOGS
# -------------------------------

@app.route("/logs")
def logs():

    if "user" not in session:
        return redirect("/")

    with open(LOG_FILE,"r") as f:
        data = f.readlines()

    return render_template("logs.html",logs=data)


# -------------------------------
# LOGOUT
# -------------------------------

@app.route("/logout")
def logout():

    write_log(session["user"],"LOGOUT")

    session.clear()

    return redirect("/")


if __name__ == "__main__":

    init_db()

    app.run(debug=True)