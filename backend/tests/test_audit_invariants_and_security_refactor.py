import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth import create_access_token, get_jwt_secret
from backend.app.utils.financial_year import parse_financial_year, derive_prior_financial_year, validate_financial_year
from backend.app.database import get_db_connection
from backend.app.services.bank_reconciliation_engine import run_bank_reconciliation
from backend.app.services.local_ai_provider import is_valid_loopback_endpoint

client = TestClient(app)

def test_financial_year_strict_derivation():
    """Verify standard Indian financial year parsing and strict prior year derivation."""
    assert validate_financial_year("2025-26") is True
    assert validate_financial_year("2024-25") is True
    assert validate_financial_year("FY 2025-26") is True
    assert validate_financial_year("invalid-fy") is False
    assert validate_financial_year("2025-2027") is False

    assert derive_prior_financial_year("2025-26") == "2024-25"
    assert derive_prior_financial_year("2024-25") == "2023-24"
    assert derive_prior_financial_year("2020-21") == "2019-20"


def test_jwt_secret_generation_and_persistence():
    """Verify JWT secret is persistent, high-entropy, and never returns hardcoded strings."""
    secret = get_jwt_secret()
    assert secret is not None
    assert len(secret) >= 32
    assert "finauditpro-local-secure-key" not in secret
    # Ensure repeated call returns the same persisted secret
    assert get_jwt_secret() == secret


def test_settings_schema_and_whitelist_enforcement():
    """Verify settings endpoint rejects unknown keys and out-of-range values."""
    admin_token = create_access_token({"sub": "admin", "role": "Admin", "id": 1})
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Unknown key rejection
    resp = client.post("/api/settings", json={"settings": {"banana_key": "arbitrary_val"}}, headers=headers)
    assert resp.status_code == 400
    assert "Unknown configuration setting" in resp.json()["detail"]

    # 2. Out-of-bounds materiality percentage
    resp = client.post("/api/settings", json={"settings": {"materiality_percentage": -50.0}}, headers=headers)
    assert resp.status_code == 400
    assert "materiality_percentage" in resp.json()["detail"]

    # 3. Invalid benchmark
    resp = client.post("/api/settings", json={"settings": {"materiality_benchmark": "NonExistentBenchmark"}}, headers=headers)
    assert resp.status_code == 400

    # 4. Valid update
    resp = client.post("/api/settings", json={"settings": {"materiality_percentage": 1.5, "materiality_benchmark": "Turnover"}}, headers=headers)
    assert resp.status_code == 200
    assert "materiality_percentage" in resp.json()["updated_keys"]


def test_backup_unique_filenames_and_bundle_creation():
    """Verify backup filenames contain collision-free IDs and full bundle backup functions."""
    admin_token = create_access_token({"sub": "admin", "role": "Admin", "id": 1})
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp1 = client.post("/api/audit-trail/backup/create", headers=headers)
    assert resp1.status_code == 200
    fn1 = resp1.json()["filename"]

    resp2 = client.post("/api/audit-trail/backup/create", headers=headers)
    assert resp2.status_code == 200
    fn2 = resp2.json()["filename"]

    assert fn1 != fn2, "Backup filenames must not collide even if created in rapid succession"

    bundle_resp = client.post("/api/audit-trail/backup/create-full-bundle", headers=headers)
    assert bundle_resp.status_code == 200
    bundle_fn = bundle_resp.json()["filename"]
    assert bundle_fn.endswith(".zip")
    assert "full_bundle" in bundle_fn


def test_brs_exact_match_requires_strong_party_or_cheque():
    """Verify BRS does not grant EXACT_MATCH to transactions with different parties lacking cheque/reference."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO clients (name, entity_type, created_at) VALUES ('BRS Invariant Client', 'Pvt Ltd', datetime('now'))")
    cid = cur.lastrowid
    cur.execute("INSERT INTO engagements (client_id, title, financial_year, audit_type, created_at, updated_at) VALUES (?, 'BRS Invariant Audit', '2025-26', 'Statutory Audit', datetime('now'), datetime('now'))", (cid,))
    eid = cur.lastrowid

    # Books transaction
    cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description, transaction_type)
        VALUES (?, '2025-04-10', 'Vendor Alpha', 'Vendor Alpha Private Limited', 50000.0, 0.0, 50000.0, 'V-101', 'Payment to Alpha', 'Payment Voucher')
    """, (eid,))
    # Bank transaction with DIFFERENT party and no cheque
    cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description, transaction_type)
        VALUES (?, '2025-04-10', 'HDFC Bank Account', 'Vendor Beta Enterprises', 0.0, 50000.0, 50000.0, 'B-201', 'Bank entry for Beta', 'BANK_STATEMENT')
    """, (eid,))
    conn.commit()
    conn.close()

    result = run_bank_reconciliation(eid)
    exact_matches = [m for m in result.get("matched_transactions", []) if m.get("confidence") == 1.0]
    assert len(exact_matches) == 0, "Different parties without cheque/ref must not produce confidence 1.0 EXACT MATCH"
