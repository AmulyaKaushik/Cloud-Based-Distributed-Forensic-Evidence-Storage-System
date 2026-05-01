import base64
import hashlib
import importlib
import io
import os
import shutil
import sys
import tempfile
import unittest


def load_app(runtime_dir):
    test_database_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not test_database_url:
        raise unittest.SkipTest("Set TEST_DATABASE_URL (or DATABASE_URL) to run PostgreSQL tests.")

    os.environ["RUNTIME_DATA_DIR"] = runtime_dir
    os.environ["SECRET_KEY"] = "test-secret-key"
    os.environ["EVIDENCE_AES_KEY"] = base64.urlsafe_b64encode(bytes(range(32))).decode()
    os.environ["DATABASE_URL"] = test_database_url

    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    module.app.config.update(TESTING=True)
    return module


class ForensicAppTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_dir = tempfile.mkdtemp(prefix="forensic2-tests-")
        self.module = load_app(self.runtime_dir)
        self.reset_database()
        self.client = self.module.app.test_client()

    def tearDown(self):
        sys.modules.pop("app", None)
        shutil.rmtree(self.runtime_dir, ignore_errors=True)

    def create_user(self, username, password, role):
        conn = self.module.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users(username, password, role) VALUES(%s, %s, %s)",
            (
                username,
                self.module.bcrypt.hashpw(password.encode(), self.module.bcrypt.gensalt()).decode(),
                role,
            ),
        )
        conn.commit()
        conn.close()

    def reset_database(self):
        conn = self.module.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE audit_logs, evidence, users RESTART IDENTITY CASCADE")
        conn.commit()
        conn.close()
        self.module.init_db()

    def login(self, username, password):
        return self.client.post(
            "/",
            data={"username": username, "password": password},
            follow_redirects=False,
        )

    def test_admin_login_succeeds(self):
        response = self.login("admin", "admin123")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/dashboard")

    def test_register_requires_admin_role(self):
        self.create_user("officer1", "StrongPass123", "police_officer")
        self.login("officer1", "StrongPass123")

        response = self.client.get("/register")
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"You do not have permission to access this page.", response.data)

    def test_upload_encrypts_and_replicates(self):
        self.login("admin", "admin123")

        response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(b"evidence payload"), "evidence.txt")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"uploaded and replicated successfully", response.data)

        conn = self.module.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT filename, hash, encrypted_filename FROM evidence WHERE filename=%s",
            ("evidence.txt",),
        )
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        filename, stored_hash, encrypted_filename = row
        self.assertEqual(filename, "evidence.txt")
        self.assertEqual(stored_hash, hashlib.sha256(b"evidence payload").hexdigest())

        for node in self.module.NODES:
            replica_path = os.path.join(node, encrypted_filename)
            self.assertTrue(os.path.exists(replica_path))
            with open(replica_path, "rb") as replica_file:
                self.assertNotEqual(replica_file.read(), b"evidence payload")

    def test_verify_detects_match_and_tampering(self):
        self.login("admin", "admin123")

        upload_response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(b"verify me"), "verify.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_response.status_code, 200)

        verified_response = self.client.post(
            "/verify",
            data={"file": (io.BytesIO(b"verify me"), "verify.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(verified_response.status_code, 200)
        self.assertIn(b"Integrity Verified", verified_response.data)

        tampered_response = self.client.post(
            "/verify",
            data={"file": (io.BytesIO(b"tampered data"), "verify.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(tampered_response.status_code, 200)
        self.assertIn(b"Tampering Detected", tampered_response.data)

    def test_api_v1_health_returns_json(self):
        response = self.client.get("/api/v1/health")
        self.assertIn(response.status_code, (200, 503))
        payload = response.get_json()
        self.assertEqual(payload["version"], "v1")
        self.assertIn("health", payload)
        self.assertIn("storage", payload["health"])
        self.assertIn("backend", payload["health"]["storage"])
        self.assertIn("nodes", payload["health"]["storage"])

    def test_api_v1_evidence_requires_auth(self):
        response = self.client.get("/api/v1/evidence")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "authentication_required")

    def test_api_v1_evidence_limit_validation(self):
        self.login("admin", "admin123")
        response = self.client.get("/api/v1/evidence?limit=abc")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_limit")

    def test_api_v1_evidence_list_returns_items(self):
        self.login("admin", "admin123")
        self.client.post(
            "/upload",
            data={"file": (io.BytesIO(b"api evidence payload"), "api-evidence.txt")},
            content_type="multipart/form-data",
        )

        response = self.client.get("/api/v1/evidence?limit=10")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["version"], "v1")
        self.assertGreaterEqual(payload["count"], 1)
        filenames = [item["filename"] for item in payload["items"]]
        self.assertIn("api-evidence.txt", filenames)

    def test_api_v1_verify_hash_validation_and_success(self):
        self.login("admin", "admin123")
        file_bytes = b"hash-verify-content"
        expected_hash = hashlib.sha256(file_bytes).hexdigest()

        self.client.post(
            "/upload",
            data={"file": (io.BytesIO(file_bytes), "hashcheck.txt")},
            content_type="multipart/form-data",
        )

        invalid_response = self.client.post(
            "/api/v1/verify/hash",
            json={"filename": "hashcheck.txt", "sha256": "bad-hash"},
        )
        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.get_json()["error"], "validation_error")

        ok_response = self.client.post(
            "/api/v1/verify/hash",
            json={"filename": "hashcheck.txt", "sha256": expected_hash},
        )
        self.assertEqual(ok_response.status_code, 200)
        self.assertTrue(ok_response.get_json()["verified"])

    def test_api_v1_verify_hash_tampered(self):
        self.login("admin", "admin123")
        self.client.post(
            "/upload",
            data={"file": (io.BytesIO(b"original content"), "tamper-api.txt")},
            content_type="multipart/form-data",
        )

        tampered_hash = hashlib.sha256(b"different content").hexdigest()
        response = self.client.post(
            "/api/v1/verify/hash",
            json={"filename": "tamper-api.txt", "sha256": tampered_hash},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["verified"])


if __name__ == "__main__":
    unittest.main()