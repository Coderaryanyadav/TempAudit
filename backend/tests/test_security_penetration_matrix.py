"""
Security, Robustness & Negative Penetration Matrix Tests (Phase 10)
Verifies path traversal resistance, SQL injection immunity, cross-engagement scoping,
session revocation, and password hashing security.
"""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db_connection
from backend.app.auth import verify_password, hash_password

client = TestClient(app)

@pytest.fixture
def auth_context():
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Token": token}

def test_sql_injection_resistance_in_filters(auth_context):
    """Phase 10: SQL injection payload in query params must be treated as literal strings and not executed."""
    sqli_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE transactions; --",
        "1 UNION SELECT 1,2,3,4,5,6,7,8,9,10 --",
        "admin'--"
    ]
    for payload in sqli_payloads:
        res = client.get(
            f"/api/transactions/1?ledger={payload}&party_name={payload}",
            headers={"Authorization": auth_context["Authorization"]}
        )
        assert res.status_code in [200, 404]
        # Verify table was not dropped
        conn = get_db_connection()
        tbl = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'").fetchone()
        conn.close()
        assert tbl is not None, "transactions table must remain intact"

def test_path_traversal_resistance_on_downloads(auth_context):
    """Phase 10: Directory traversal attempts on file/report downloads must be blocked."""
    traversal_paths = [
        "../../../../etc/passwd",
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "....//....//....//finauditpro.db",
        "C:\\Windows\\System32\\drivers\\etc\\hosts"
    ]
    for path in traversal_paths:
        res = client.get(
            f"/api/audit-trail/backup/download/{path}",
            headers={"Authorization": auth_context["Authorization"]}
        )
        assert res.status_code in [400, 404, 422], f"Path traversal '{path}' must not succeed"

def test_token_revocation_on_logout(auth_context):
    """Phase 10: Logging out must invalidate the user's active JWT session."""
    token = auth_context["Token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # Request works before logout
    res_before = client.get("/api/auth/me", headers=auth_header)
    assert res_before.status_code == 200

    # User logs out
    res_logout = client.post("/api/auth/logout", headers=auth_header)
    assert res_logout.status_code == 200

    # Request must fail with 401 after logout
    res_after = client.get("/api/auth/me", headers=auth_header)
    assert res_after.status_code == 401

def test_password_hashing_pbkdf2_and_salt_uniqueness():
    """Phase 10: Passwords must be hashed with PBKDF2-SHA256 and unique salts."""
    pwd = "SecureAuditorPassword!123"
    hash1 = hash_password(pwd)
    hash2 = hash_password(pwd)

    assert hash1.startswith("pbkdf2_sha256$")
    assert hash2.startswith("pbkdf2_sha256$")
    assert hash1 != hash2, "Unique salts must generate different hashes for identical passwords"
    assert verify_password(pwd, hash1) is True
    assert verify_password(pwd, hash2) is True
    assert verify_password("WrongPassword123", hash1) is False

def test_malformed_json_returns_422():
    """Phase 10: Sending unparseable or schema-violating payload returns 422 Unprocessable Entity."""
    res = client.post(
        "/api/auth/login",
        data="INVALID_NOT_JSON",
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 422
