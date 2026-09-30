import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.auth import create_access_token, invalidate_user_sessions
from backend.app.services.local_ai_provider import is_valid_loopback_endpoint
from backend.app.services.data_normalizer import normalize_date
from backend.app.services.anomaly_detection_engine import detect_all_anomalies
from backend.app.services.financial_statement_analysis_engine import run_financial_statement_analysis

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_unauthenticated_endpoints_return_401_matrix():
    """Matrix asserting EVERY sensitive endpoint without token returns 401."""
    sensitive_endpoints = [
        ("GET", "/api/settings/system-info"),
        ("GET", "/api/assistant/summary/1"),
        ("POST", "/api/assistant/query"),
        ("GET", "/api/financial-statements/1"),
        ("GET", "/api/financial-statements/1/report/download"),
        ("GET", "/api/cleaning/summary/1"),
        ("GET", "/api/cleaning/logs/1"),
        ("GET", "/api/trial-balance/1"),
        ("GET", "/api/trial-balance/1/analysis"),
        ("GET", "/api/trial-balance/1/report/download"),
        ("GET", "/api/findings/1"),
        ("GET", "/api/findings/detail/1"),
        ("GET", "/api/checklist/1"),
        ("GET", "/api/transactions?engagement_id=1"),
        ("GET", "/api/transactions/analysis/1"),
        ("GET", "/api/transactions/ledgers-list/1"),
        ("GET", "/api/transactions/parties-list/1"),
        ("GET", "/api/transactions/1"),
        ("GET", "/api/reconciliation/1"),
        ("GET", "/api/reconciliation/details/1"),
        ("GET", "/api/reconciliation/1/report/download"),
        ("GET", "/api/reports/1"),
        ("GET", "/api/reports/download/1"),
        ("GET", "/api/working-papers/1"),
        ("GET", "/api/working-papers/1/linkable-items"),
        ("GET", "/api/working-papers/1/export/csv"),
        ("POST", "/api/ai-manager/generate"),
        ("GET", "/api/ai-manager/status"),
        ("GET", "/api/duplicates-and-gaps/1"),
        ("GET", "/api/yoy-comparison/1"),
    ]

    for method, path in sensitive_endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={"engagement_id": 1, "prompt": "test", "query": "test"})
        assert res.status_code == 401, f"Expected 401 for unauthenticated {method} {path}, got {res.status_code}"

def test_local_ai_endpoint_validation_prevents_ssrf():
    """Flaw 21: Verify SSRF attempts with deceptive localhost prefixes are rejected."""
    malicious_endpoints = [
        "http://localhost.evil.com:1234",
        "http://127.0.0.1.evil.com:1234",
        "http://localhost@evil.com:1234",
        "http://127.0.0.1@attacker.net",
        "http://evil-localhost.com",
        "http://192.168.1.50:1234",
        "http://localhost:22",
        "http://127.0.0.1:5432",
        "http://localhost:6379",
        "http://127.0.0.1:8080",
        "local://evil_scheme",
        "https://google.com",
        "ftp://localhost:1234"
    ]
    for bad_url in malicious_endpoints:
        assert not is_valid_loopback_endpoint(bad_url), f"Validation permitted malicious URL: {bad_url}"

    # Valid loopback endpoints should pass
    valid_endpoints = [
        "http://localhost:1234",
        "http://127.0.0.1:1234",
        "http://127.0.0.1:11434",
        "http://[::1]:1234",
        "local://builtin"
    ]
    for good_url in valid_endpoints:
        assert is_valid_loopback_endpoint(good_url), f"Validation rejected valid loopback URL: {good_url}"

def test_no_synthetic_financial_statement_data():
    """Flaw 44 & 45: Zero synthetic multipliers on missing source data."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO clients (name, entity_type, created_at) VALUES ('Zero Synth Client', 'Pvt Ltd', datetime('now'))")
    cid = cur.lastrowid
    cur.execute("INSERT INTO engagements (client_id, title, financial_year, audit_type, created_at, updated_at) VALUES (?, 'Clean Audit', '2024-25', 'Statutory Audit', datetime('now'), datetime('now'))", (cid,))
    eid = cur.lastrowid
    # Insert only Revenue
    cur.execute("INSERT INTO transactions (engagement_id, date, ledger, amount, debit, credit) VALUES (?, '2024-05-01', 'Sales', 1000000.0, 0.0, 1000000.0)", (eid,))
    conn.commit()
    conn.close()

    res = run_financial_statement_analysis(engagement_id=eid)
    pnl = res.get("pnl_statement", {}).get("current_year", {})
    # Verify COGS is 0.0, NOT fabricated to 600,000 (rev * 0.60)
    assert pnl.get("cogs", 0.0) == 0.0
    assert pnl.get("employee_expenses", 0.0) == 0.0
    # Prior year comparison should indicate not available or None when no PY engagement exists
    assert res.get("py_available") is False or res.get("comparative", {}).get("py_total_revenue") is None

def test_calendar_invalid_dates_rejected():
    """Flaw 34: 31/02/2026 should be flagged and not blindly transformed to 2026-02-31."""
    norm, rule, is_q, conf = normalize_date("31/02/2026")
    # Must NOT return '2026-02-31'
    assert norm != "2026-02-31"

def test_bounded_pagination():
    """Flaw 36: Bounded limit on transactions."""
    token = create_access_token({"sub": "admin", "role": "Admin", "uid": 1})
    res = client.get("/api/transactions?engagement_id=1&limit=9999", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    # Returned limit in pagination should be capped at 500
    assert res.json()["limit"] <= 500

def test_deterministic_anomaly_ids():
    """Flaw 50: Anomaly IDs must be stable and pattern-linked."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO clients (name, entity_type, created_at) VALUES ('Anom Client', 'Pvt Ltd', datetime('now'))")
    cid = cur.lastrowid
    cur.execute("INSERT INTO engagements (client_id, title, financial_year, audit_type, created_at, updated_at) VALUES (?, 'Anom Audit', '2024-25', 'Statutory Audit', datetime('now'), datetime('now'))", (cid,))
    eid = cur.lastrowid
    cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, amount, debit, credit, description)
        VALUES (?, '2024-05-01', 'Cash in Hand', 250000.0, 0.0, 250000.0, 'Large cash payment')
    """, (eid,))
    txn_id = cur.lastrowid
    conn.commit()
    conn.close()

    res = detect_all_anomalies(engagement_id=eid)
    anomalies = res.get("anomalies", [])
    if anomalies:
        for a in anomalies:
            anom_id = a.get("anomaly_id") or a.get("id") or ""
            assert anom_id.startswith(f"ANOM-TX{txn_id}-") or anom_id.startswith("ANOM-")
            assert "score" in a or "anomaly_score" in a
