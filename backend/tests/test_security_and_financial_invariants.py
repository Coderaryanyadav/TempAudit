import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth import create_access_token, hash_password, verify_password, normalize_role
from backend.app.parsers.excel_csv import auto_detect_mapping
from backend.app.services.bank_reconciliation_engine import run_bank_reconciliation
from backend.app.database import get_db_connection

client = TestClient(app)

def test_no_token_cannot_access_client_endpoints():
    response = client.get("/api/clients/")
    assert response.status_code == 401
    assert "detail" in response.json()

def test_no_token_cannot_access_uploaded_files():
    response = client.get("/api/import/files/1")
    assert response.status_code == 401

def test_unknown_role_fails_closed():
    # normalize_role should return None for unknown roles
    assert normalize_role("Superuser") is None
    assert normalize_role("Hacker") is None
    assert normalize_role("Guest") is None
    assert normalize_role("Admin") == "Admin"
    assert normalize_role("Auditor") == "Auditor"
    assert normalize_role("Audit Staff") == "Audit Staff"

def test_password_pbkdf2_verification():
    h = hash_password("SecurePass123!")
    assert h.startswith("pbkdf2_sha256$")
    assert verify_password("SecurePass123!", h) is True
    assert verify_password("WrongPassword", h) is False

def test_jwt_token_claims_and_issuer():
    token = create_access_token({"sub": "admin", "role": "Admin", "uid": 1})
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"

def test_mapping_disambiguation_tax_vs_amount():
    columns = ["Date", "Particulars", "Amount", "Tax Amount", "Invoice No"]
    mapping = auto_detect_mapping(columns)
    assert mapping.get("Amount") == "amount"
    assert mapping.get("Tax Amount") == "tax_amount"

def test_client_pan_and_gstin_validation():
    token = create_access_token({"sub": "admin", "role": "Admin", "uid": 1})
    headers = {"Authorization": f"Bearer {token}"}

    # Invalid PAN
    invalid_pan_payload = {
        "name": "Acme Corp Ltd",
        "entity_type": "Private Limited Company",
        "pan": "INVALID_PAN",
        "gstin": "27AAACA1234A1Z5"
    }
    res = client.post("/api/clients", json=invalid_pan_payload, headers=headers)
    assert res.status_code == 400

    # Invalid GSTIN
    invalid_gst_payload = {
        "name": "Acme Corp Ltd",
        "entity_type": "Private Limited Company",
        "pan": "ABCDE1234F",
        "gstin": "INVALID_GST"
    }
    res = client.post("/api/clients", json=invalid_gst_payload, headers=headers)
    assert res.status_code == 400

def test_file_path_not_exposed_in_files_api():
    token = create_access_token({"sub": "admin", "role": "Admin", "uid": 1})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Query uploaded files for engagement 1
    res = client.get("/api/import/files/1", headers=headers)
    if res.status_code == 200:
        files = res.json()
        for f in files:
            assert "file_path" not in f
