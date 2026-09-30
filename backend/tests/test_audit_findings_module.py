import os
import json
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db_connection, init_db
from backend.app.services.centralized_findings_engine import CentralizedFindingsEngine

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    """Initializes DB schema and provides test token."""
    init_db()
    yield

def get_auth_header():
    login_res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    if login_res.status_code == 200:
        token = login_res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return {}

def test_deterministic_risk_score_calculation():
    """Tests that risk scores are strictly deterministic, explainable, and factor-driven."""
    # Test 1: Low base severity with small amount
    score_low, factors_low, exp_low = CentralizedFindingsEngine.calculate_deterministic_risk_score(
        severity="LOW",
        amount=5000.0,
        materiality_threshold=50000.0,
        frequency=1,
        affected_records_count=1
    )
    assert 1.0 <= score_low <= 3.0
    assert factors_low["base_severity"] == "LOW"
    assert factors_low["base_weight"] == 1.5
    assert "Base(1.5)" in factors_low["equation"]

    # Test 2: Critical base severity with large exposure exceeding materiality
    score_crit, factors_crit, exp_crit = CentralizedFindingsEngine.calculate_deterministic_risk_score(
        severity="CRITICAL",
        amount=500000.0,
        materiality_threshold=50000.0,
        frequency=12,
        repetition_count=12,
        data_quality_issue=True,
        data_quality_details="Missing tax identifier",
        difference_pct=60.0,
        historical_repeat=True,
        historical_details="Recurring monthly outlier",
        affected_records_count=15
    )
    assert score_crit >= 8.5
    assert factors_crit["base_weight"] == 7.0
    assert factors_crit["amount_impact"] == 2.0
    assert factors_crit["repetition_impact"] == 1.0
    assert factors_crit["records_impact"] == 1.0
    assert factors_crit["difference_impact"] == 1.0
    assert factors_crit["data_quality_impact"] == 0.5
    assert factors_crit["historical_impact"] == 0.5
    assert "Deterministic Risk Score" in exp_crit
    assert "Missing tax identifier" in exp_crit

    # Test 3: Repeatability / Determinism check (calling 100 times with identical input yields identical score)
    for _ in range(50):
        s, f, _ = CentralizedFindingsEngine.calculate_deterministic_risk_score(
            severity="HIGH",
            amount=150000.0,
            materiality_threshold=50000.0,
            frequency=3,
            affected_records_count=3,
            difference_pct=25.0
        )
        assert s == 7.9
        assert f["final_risk_score"] == 7.9

def test_centralized_findings_sync_and_dashboard():
    """Creates an engagement with audit data across multiple modules, syncs findings, and verifies dashboard metrics."""
    headers = get_auth_header()

    # 1. Create client & engagement
    cl_res = client.post("/api/clients/", json={"name": "Findings Test Client", "industry": "Technology"}, headers=headers)
    assert cl_res.status_code == 200
    client_id = cl_res.json()["id"]

    eng_res = client.post("/api/engagements/", json={
        "client_id": client_id,
        "title": "FY 2025-26 Centralized Findings Audit",
        "financial_year": "2025-26",
        "audit_type": "Statutory Audit",
        "materiality_threshold": 50000.0
    }, headers=headers)
    assert eng_res.status_code == 200
    eng_id = eng_res.json()["id"]

    # 2. Insert test transactions violating Section 40A(3) and Section 269ST
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, invoice_no, ledger, account_group, description, debit, credit, party_name)
        VALUES (?, '2025-05-10', 'VCH-CASH-01', 'INV-001', 'Office Expenses', 'Expense', 'Cash payment for machinery repairs', 45000.0, 0.0, 'Speedy Repairs')
    """, (eng_id,))
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, invoice_no, ledger, account_group, description, debit, credit, party_name)
        VALUES (?, '2025-06-15', 'VCH-CASH-02', 'INV-002', 'Cash in Hand', 'Current Assets', 'Cash receipt exceeding limit', 0.0, 250000.0, 'Mega Corp')
    """, (eng_id,))

    # Insert duplicate transactions
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, invoice_no, ledger, account_group, description, debit, credit, party_name)
        VALUES (?, '2025-07-01', 'VCH-DUP-01', 'INV-DUP-100', 'Legal Fees', 'Expense', 'Retainer fee July', 75000.0, 0.0, 'Apex Legal Advisors')
    """, (eng_id,))
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, invoice_no, ledger, account_group, description, debit, credit, party_name)
        VALUES (?, '2025-07-01', 'VCH-DUP-02', 'INV-DUP-100', 'Legal Fees', 'Expense', 'Retainer fee July duplicate', 75000.0, 0.0, 'Apex Legal Advisors')
    """, (eng_id,))

    # Insert Bank Reconciliation Exception
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reconciliations (engagement_id, recon_type, title, status, book_balance, bank_balance, net_unreconciled_difference, unmatched_bank_count, created_at)
        VALUES (?, 'Bank BRS', 'HDFC Bank Operating Account Reconciliation', 'Completed', 1500000.0, 1320000.0, 180000.0, 3, '2025-07-31T10:00:00')
    """, (eng_id,))

    # Insert Suspense ledger
    conn.execute("""
        INSERT INTO ledgers (engagement_id, ledger_name, account_group, opening_balance, total_debit, total_credit, closing_balance)
        VALUES (?, 'Suspense Account', 'Current Assets', 0.0, 95000.0, 0.0, 95000.0)
    """, (eng_id,))
    conn.commit()
    conn.close()

    # 3. Trigger Centralized Findings Sync via API
    sync_res = client.post(f"/api/findings/{eng_id}/sync", headers=headers)
    assert sync_res.status_code == 200
    sync_data = sync_res.json()["data"]
    assert sync_data["total_collected"] > 0
    assert sync_data["new_findings_created"] > 0

    # 4. Fetch Dashboard Summary
    dash_res = client.get(f"/api/findings/{eng_id}/dashboard-summary")
    assert dash_res.status_code == 200
    summary = dash_res.json()
    assert summary["total_findings"] >= 3
    assert summary["open_findings"] >= 3
    assert summary["high_risk"] >= 1 or summary["critical"] >= 1
    assert "Statutory & Tax Rules" in summary["by_module"] or "Duplicate & Sequence Engine" in summary["by_module"]

    # 5. Fetch Findings List with filters
    list_res = client.get(f"/api/findings/{eng_id}?sort_by=risk_score_desc")
    assert list_res.status_code == 200
    findings = list_res.json()
    assert len(findings) >= 3
    first_finding = findings[0]
    assert "finding_code" in first_finding
    assert "risk_score" in first_finding
    assert "module" in first_finding
    assert "risk_factors" in first_finding
    assert first_finding["status"] == "Open"

    finding_id = first_finding["id"]

    # 6. Fetch Detail for Single Finding
    detail_res = client.get(f"/api/findings/detail/{finding_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == finding_id
    assert "affected_transactions" in detail
    assert "risk_factors" in detail

    # 7. Update Finding Status & Auditor Comment
    update_res = client.put(f"/api/findings/item/{finding_id}", json={
        "status": "Under Review",
        "auditor_comment": "Management inquiry letter dispatched regarding Section 40A(3) cash expense.",
        "reviewed_by": "lead_auditor_ca"
    }, headers=headers)
    assert update_res.status_code == 200

    # Verify update persisted
    verify_res = client.get(f"/api/findings/detail/{finding_id}")
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["status"] == "Under Review"
    assert "Management inquiry letter" in v_data["auditor_comment"]
    assert v_data["reviewed_by"] == "lead_auditor_ca"
    assert v_data["reviewed_at"] is not None

    # 8. Test AI Explanation Generation endpoint
    ai_res = client.post(f"/api/findings/item/{finding_id}/ai-explain", headers=headers)
    assert ai_res.status_code == 200
    ai_data = ai_res.json()
    assert "Deterministic Factor Breakdown" in ai_data["ai_explanation"]
    assert "Recommended Substantive Audit Procedures" in ai_data["ai_explanation"]

    # 9. Test Filter by Status and Module
    filter_res = client.get(f"/api/findings/{eng_id}?status=Under%20Review")
    assert filter_res.status_code == 200
    assert len(filter_res.json()) >= 1

    # 10. Test Manual / Custom Finding Creation
    custom_res = client.post("/api/findings/custom", json={
        "engagement_id": eng_id,
        "title": "Inventory Physical Verification Discrepancy",
        "description": "Shortage of 45 units noted during year-end physical count.",
        "severity": "HIGH",
        "category": "Physical Inventory",
        "module": "Inventory Audit",
        "expected_value": "500 units",
        "actual_value": "455 units",
        "difference": "45 units shortage (₹1,35,000)",
        "rule_used": "SA 501 Inventory Physical Verification",
        "recommended_action": "Investigate reconciliation with warehouse log and record inventory write-down."
    }, headers=headers)
    assert custom_res.status_code == 200
    custom_finding_id = custom_res.json()["finding_id"]
    assert custom_res.json()["risk_score"] >= 5.0

    # 11. Test CSV Export
    csv_res = client.get(f"/api/findings/{eng_id}/export/csv", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    assert "Finding ID,Module,Category,Severity" in csv_res.text
    assert "Inventory Physical Verification Discrepancy" in csv_res.text
