import os
import io
import json
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.utils.sample_data import seed_sample_database

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    seed_sample_database()

def get_auth_token():
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]

def test_report_types_catalog():
    res = client.get("/api/reports/types")
    assert res.status_code == 200
    types = res.json()
    assert len(types) == 10
    type_ids = [t["id"] for t in types]
    assert "complete_audit_analysis" in type_ids
    assert "engagement_summary" in type_ids
    assert "data_import" in type_ids
    assert "trial_balance" in type_ids
    assert "bank_reconciliation" in type_ids
    assert "gst_reconciliation" in type_ids
    assert "anomaly_report" in type_ids
    assert "yoy_comparison" in type_ids
    assert "risk_findings" in type_ids
    assert "audit_checklist" in type_ids

def test_generate_all_10_pdf_report_types():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    engagement_id = 1

    report_types = [
        "engagement_summary",
        "data_import",
        "trial_balance",
        "bank_reconciliation",
        "gst_reconciliation",
        "anomaly_report",
        "yoy_comparison",
        "risk_findings",
        "audit_checklist",
        "complete_audit_analysis"
    ]

    for r_type in report_types:
        res = client.post(
            f"/api/reports/generate-pdf/{engagement_id}",
            json={"report_type": r_type},
            headers=headers
        )
        assert res.status_code == 200, f"Failed generating {r_type}: {res.text}"
        data = res.json()
        assert data["report_id"] is not None
        assert data["filename"].endswith(".pdf")
        assert data["report_type"] == r_type

        # Verify download endpoint
        dl_res = client.get(f"/api/reports/download/{data['report_id']}")
        assert dl_res.status_code == 200
        assert dl_res.headers["content-type"] == "application/pdf"
        assert len(dl_res.content) > 1000  # Valid PDF binary

    # Verify reports history list
    list_res = client.get(f"/api/reports/{engagement_id}")
    assert list_res.status_code == 200
    reports_history = list_res.json()
    assert len(reports_history) >= 10

    # Verify audit logs for report generation
    conn = get_db_connection()
    logs = conn.execute("SELECT * FROM audit_logs WHERE action IN ('REPORT_GENERATION', 'GENERATE_REPORT') ORDER BY id DESC").fetchall()
    conn.close()
    assert len(logs) >= 10
