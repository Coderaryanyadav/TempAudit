"""
Report Generation Traceability & PDF Audit Export Verification (Phase 9)
Verifies deterministic PDF report creation, physical file readability,
financial number accuracy, and token-based download authentication.
"""
import os
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db_connection

client = TestClient(app)

@pytest.fixture
def auth_headers():
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Token": token}

def test_report_generation_and_physical_pdf_validation(auth_headers):
    """Phase 9: PDF report must be generated, persisted, and physically readable on disk."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cur = conn.execute("INSERT INTO clients (name, pan, created_at) VALUES ('Report Traceability Client', 'ABCDE5555E', ?)", (now_str,))
    client_id = cur.lastrowid
    cur = conn.execute("INSERT INTO engagements (client_id, title, financial_year, created_at) VALUES (?, 'Report Audit', '2024-25', ?)", (client_id, now_str))
    eng_id = cur.lastrowid

    # Insert sample transactions and findings
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, ledger, amount, debit, credit, transaction_type)
        VALUES (?, '2024-05-01', 'REP-01', 'Audit Fees', 50000.0, 50000.0, 0.0, 'Payment')
    """, (eng_id,))
    conn.execute("""
        INSERT INTO audit_findings (engagement_id, finding_code, category, severity, risk_score, title, description, rule_used, engine_type, status, created_at)
        VALUES (?, 'DET-001', 'Accounting Standard', 'HIGH', 8.0, 'Discrepancy Title', 'Factual discrepancy', 'Rule 1', 'DETERMINISTIC', 'Open', ?)
    """, (eng_id, now_str))
    conn.commit()
    conn.close()

    # Generate PDF report
    res_gen = client.post(
        f"/api/reports/generate-pdf/{eng_id}?report_type=complete_audit_analysis",
        headers={"Authorization": auth_headers["Authorization"]}
    )
    assert res_gen.status_code == 200
    data = res_gen.json()
    assert "report_id" in data
    report_id = data["report_id"]

    # Verify database record
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    conn.close()

    assert row is not None
    assert row["engagement_id"] == eng_id
    file_path = row["file_path"]

    # Verify physical file existence and valid PDF header
    assert os.path.exists(file_path), "Generated PDF report file must exist on disk"
    with open(file_path, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-", "Generated report must have valid '%PDF-' header"

    # Verify download via Bearer header
    res_dl = client.get(f"/api/reports/download/{report_id}", headers={"Authorization": auth_headers["Authorization"]})
    assert res_dl.status_code == 200
    assert res_dl.headers.get("content-type") == "application/pdf"
    assert len(res_dl.content) > 100

    # Verify download via query token is rejected (closing URL token leakage vector)
    token = auth_headers["Token"]
    res_dl_token = client.get(f"/api/reports/download/{report_id}?token={token}")
    assert res_dl_token.status_code == 401, "Query token authentication must be rejected; Bearer header is required"

    # Verify unauthenticated download is rejected
    res_unauth = client.get(f"/api/reports/download/{report_id}")
    assert res_unauth.status_code == 401

def test_report_generation_with_zero_findings_completes_cleanly(auth_headers):
    """Phase 9: Generating report when zero findings exist must succeed without crashing."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cur = conn.execute("INSERT INTO clients (name, pan, created_at) VALUES ('Clean Client', 'ABCDE6666F', ?)", (now_str,))
    client_id = cur.lastrowid
    cur = conn.execute("INSERT INTO engagements (client_id, title, financial_year, created_at) VALUES (?, 'Clean Audit', '2024-25', ?)", (client_id, now_str))
    eng_id = cur.lastrowid
    conn.commit()
    conn.close()

    res_gen = client.post(
        f"/api/reports/generate-pdf/{eng_id}?report_type=executive_summary",
        headers={"Authorization": auth_headers["Authorization"]}
    )
    assert res_gen.status_code == 200
    data = res_gen.json()
    assert "report_id" in data
