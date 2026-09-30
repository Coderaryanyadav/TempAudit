import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db_connection, init_db
from backend.app.services.checklist_generator import CHECKLIST_CATEGORIES, CHECKLIST_STATUSES, ChecklistGenerator

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield

def get_auth_header():
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    if res.status_code == 200:
        return {"Authorization": f"Bearer {res.json()['access_token']}"}
    return {}

def test_checklist_generation_across_15_categories():
    headers = get_auth_header()

    # 1. Create client & engagement
    cl_res = client.post("/api/clients/", json={
        "name": "Checklist Standard Corp Ltd",
        "client_type": "Public Limited",
        "industry": "Manufacturing"
    }, headers=headers)
    assert cl_res.status_code == 200
    client_id = cl_res.json()["id"]

    eng_res = client.post("/api/engagements/", json={
        "client_id": client_id,
        "title": "Statutory Audit FY 2024-25",
        "financial_year": "2024-25",
        "audit_type": "Statutory Audit"
    }, headers=headers)
    assert eng_res.status_code == 200
    eng_id = eng_res.json()["id"]

    # 2. Generate Checklist
    gen_res = client.post(f"/api/checklist/{eng_id}/generate", json={
        "client_type": "Public Limited",
        "audit_type": "Statutory Audit",
        "financial_year": "2024-25",
        "selected_modules": ["General Ledger", "Bank Reconciliation", "GST Reconciliation", "Financial Statements"]
    }, headers=headers)
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["total_items"] >= 20

    # 3. Verify all 15 categories are present in summary
    summary_res = client.get(f"/api/checklist/{eng_id}/summary", headers=headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    for cat in CHECKLIST_CATEGORIES:
        assert cat in summary["by_category"]

    # Verify no items were automatically marked 'Completed' by AI
    assert summary["by_status"]["Completed"] == 0
    assert summary["by_status"]["Not Started"] > 0

def test_risk_findings_integration_in_checklist():
    headers = get_auth_header()

    # Create client & engagement
    cl_res = client.post("/api/clients/", json={"name": "Risk Linked Client", "client_type": "Private Limited"}, headers=headers)
    client_id = cl_res.json()["id"]

    eng_res = client.post("/api/engagements/", json={
        "client_id": client_id,
        "title": "Tax & Statutory Audit",
        "financial_year": "2024-25",
        "audit_type": "Tax Audit"
    }, headers=headers)
    eng_id = eng_res.json()["id"]

    # Insert a critical risk finding
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO audit_findings (
            engagement_id, finding_code, module, category, severity, risk_score,
            title, description, rule_used, engine_type, status, created_at
        ) VALUES (?, 'FIND-40A3-001', 'Statutory & Tax Rules', 'Statutory Compliance', 'CRITICAL', 9.0,
            'Section 40A(3) Cash Payment of Rs 85,000', 'Cash payment exceeding threshold',
            'Income Tax Act Sec 40A(3)', 'DETERMINISTIC', 'Open', '2024-10-01T10:00:00')
    """, (eng_id,))
    conn.commit()
    conn.close()

    # Generate checklist
    gen_res = client.post(f"/api/checklist/{eng_id}/generate", json={
        "client_type": "Private Limited",
        "audit_type": "Tax Audit",
        "financial_year": "2024-25"
    }, headers=headers)
    assert gen_res.status_code == 200
    assert gen_res.json()["risk_finding_procedures_count"] >= 1

    # Fetch checklist and check for the risk procedure
    items_res = client.get(f"/api/checklist/{eng_id}?status=Requires%20Review", headers=headers)
    assert items_res.status_code == 200
    req_items = items_res.json()
    assert len(req_items) >= 1
    risk_item = req_items[0]
    assert "40A(3)" in risk_item["question"] or "40A3" in risk_item["evidence"]
    assert risk_item["status"] == "Requires Review"

def test_custom_checklist_item_and_auditor_signoff():
    headers = get_auth_header()

    # Create client & engagement
    cl_res = client.post("/api/clients", json={"name": "Custom Check Client", "entity_type": "Private Limited Company"}, headers=headers)
    assert cl_res.status_code == 200
    client_id = cl_res.json()["id"]
    eng_res = client.post("/api/engagements", json={"client_id": client_id, "title": "Eng 1", "financial_year": "2024-25", "audit_type": "Statutory Audit"}, headers=headers)
    assert eng_res.status_code == 200
    eng_id = eng_res.json()["id"]

    # 1. Create custom checklist item
    create_res = client.post(f"/api/checklist/{eng_id}/custom", json={
        "category": "Loans",
        "question": "Inspect bank sanction letter covenants for working capital term loan of ₹5 Crores.",
        "assigned_staff": "Senior Auditor",
        "due_date": "2024-11-30",
        "comment": "Ensure DSCR > 1.33 covenant compliance"
    }, headers=headers)
    assert create_res.status_code == 200
    item_id = create_res.json()["id"]
    assert create_res.json()["item_code"].startswith("CHK-CUST")

    # 2. Update status and sign-off
    update_res = client.put(f"/api/checklist/item/{item_id}", json={
        "status": "Completed",
        "evidence": "Working Paper WP-LON-04 attached; Debt Covenants confirmed compliant",
        "comment": "Reviewed HDFC Bank term loan agreement and tested interest recalculation."
    }, headers=headers)
    assert update_res.status_code == 200

    # 3. Verify item fields persisted
    chk_res = client.get(f"/api/checklist/{eng_id}?category=Loans", headers=headers)
    assert chk_res.status_code == 200
    loans_items = chk_res.json()
    assert len(loans_items) >= 1
    item = [it for it in loans_items if it["id"] == item_id][0]
    assert item["status"] == "Completed"
    assert item["completed_date"] is not None
    assert "WP-LON-04" in item["evidence"]

    # 4. Verify CSV Export
    csv_res = client.get(f"/api/checklist/{eng_id}/export/csv", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    assert "Checklist ID,Category,Question/Procedure" in csv_res.text
    assert "Inspect bank sanction letter covenants" in csv_res.text
