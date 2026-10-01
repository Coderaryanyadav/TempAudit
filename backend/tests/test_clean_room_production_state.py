import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import DB_PATH, init_db, get_db_connection

client = TestClient(app)

def test_clean_room_zero_data_and_onboarding_lifecycle(tmp_path, monkeypatch):
    """
    Acceptance test for clean-room fresh installation:
    1. Fresh database contains exactly 0 records across all entities.
    2. /api/auth/setup-status returns UNINITIALIZED and is_setup_completed=False.
    3. First administrator creation sets users=1, everything else remains 0.
    4. Administrator logs in and obtains JWT token.
    5. First client creation increases clients from 0 to 1 with no ghost records.
    6. First engagement creation increases engagements from 0 to 1 with no ghost records.
    7. Database persistence across reconnects is verified.
    """
    # 1. Point DB to isolated temp file
    test_db = str(tmp_path / "clean_room_fresh.db")
    monkeypatch.setenv("FINAUDIT_DB_PATH", test_db)
    monkeypatch.setattr("backend.app.database.DB_PATH", test_db)

    init_db()

    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # 2. Strict Zero-Data Check on pristine installation
    core_tables = [
        "users", "clients", "engagements", "transactions",
        "ledgers", "working_papers", "audit_findings",
        "uploaded_files", "audit_logs"
    ]
    for tbl in core_tables:
        cnt = conn.execute(f"SELECT COUNT(*) as c FROM {tbl}").fetchone()["c"]
        assert cnt == 0, f"Expected table '{tbl}' to have 0 records, found {cnt}"
    conn.close()

    # 3. Setup Status Verification
    resp = client.get("/api/auth/setup-status")
    assert resp.status_code == 200
    status_data = resp.json()
    assert status_data["state"] == "UNINITIALIZED"
    assert status_data["is_setup_completed"] is False
    assert status_data["user_count"] == 0

    # 4. Create First Administrator
    admin_payload = {
        "full_name": "CA Rajeshwar Sharma",
        "username": "lead_partner",
        "email": "partner@sharma-ca.in",
        "designation": "Engagement Partner (FCA)",
        "password": "MasterSecurePassphrase2026!",
        "role": "Admin"
    }
    resp = client.post("/api/auth/initial-setup", json=admin_payload)
    assert resp.status_code == 200
    setup_res = resp.json()
    assert "access_token" in setup_res
    admin_token = setup_res["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Verify users=1, all other tables still 0
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    assert conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) as c FROM clients").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) as c FROM engagements").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) as c FROM transactions").fetchone()["c"] == 0
    conn.close()

    # 5. Complete Setup Wizard Steps (Firm, Security, Backup)
    firm_resp = client.post("/api/auth/setup/firm-profile", json={
        "firm_name": "Sharma & Associates LLP",
        "icai_reg_number": "FRN-123456N",
        "address": "100 Nariman Point",
        "city": "Mumbai",
        "state": "Maharashtra",
        "pin_code": "400021",
        "email": "contact@sharma-ca.in"
    }, headers=headers)
    assert firm_resp.status_code == 200

    sec_resp = client.post("/api/auth/setup/security-config", json={
        "session_timeout_minutes": 60,
        "local_ai_mode": "LOCAL_ONLY"
    }, headers=headers)
    assert sec_resp.status_code == 200

    comp_resp = client.post("/api/auth/setup/complete", headers=headers)
    assert comp_resp.status_code == 200

    # 6. Verify Dashboard Metrics with 0 clients & 0 engagements
    dash_resp = client.get("/api/engagements/dashboard/comprehensive", headers=headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["top_cards"]["active_clients_count"] == 0
    assert dash_data["top_cards"]["active_engagements_count"] == 0
    assert dash_data["top_cards"]["open_findings_count"] == 0

    # 7. Create First Client
    client_payload = {
        "name": "Reliance Horizons Pvt Ltd",
        "entity_type": "Private Limited Company",
        "pan": "ABCDE1234F",
        "gstin": "27ABCDE1234F1Z5",
        "address": "101 BKC Complex, Mumbai",
        "industry": "Manufacturing",
        "financial_year": "2025-26"
    }
    create_client_resp = client.post("/api/clients/", json=client_payload, headers=headers)
    assert create_client_resp.status_code == 200
    client_obj = create_client_resp.json()
    client_id = client_obj["id"]

    # Verify clients=1, engagements=0, transactions=0
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    assert conn.execute("SELECT COUNT(*) as c FROM clients").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) as c FROM engagements").fetchone()["c"] == 0
    conn.close()

    # 8. Create First Engagement
    eng_payload = {
        "client_id": client_id,
        "title": "Statutory Audit FY 2025-26",
        "audit_type": "Statutory Audit",
        "financial_year": "2025-26",
        "period_start": "2025-04-01",
        "period_end": "2026-03-31",
        "materiality_threshold": 75000.0,
        "status": "In Progress"
    }
    create_eng_resp = client.post("/api/engagements/", json=eng_payload, headers=headers)
    assert create_eng_resp.status_code == 200
    eng_obj = create_eng_resp.json()
    assert eng_obj["id"] is not None

    # Verify engagements=1, transactions=0
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    assert conn.execute("SELECT COUNT(*) as c FROM engagements").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) as c FROM transactions").fetchone()["c"] == 0
    conn.close()
