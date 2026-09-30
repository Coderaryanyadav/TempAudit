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
    # Login as default admin
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


def test_working_papers_full_workflow():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    engagement_id = 1

    # 1. Create working paper
    wp_data = {
        "wp_reference": "WP-REV-01",
        "title": "Revenue Cut-off and Substantive Testing",
        "area": "Revenue & Debtors",
        "description": "Verification of sales invoices recorded 5 days before and after balance sheet date.",
        "evidence": "Tested 25 sample invoices against delivery challans and e-way bills.",
        "prepared_by": "Audit Senior",
        "prepared_date": "2024-05-15",
        "notes": "No cut-off errors identified in sampled transactions.",
        "status": "Prepared",
        "linked_findings": [],
        "linked_transactions": [],
        "linked_checklists": []
    }

    create_res = client.post(
        f"/api/working-papers?engagement_id={engagement_id}",
        json=wp_data,
        headers=headers
    )
    assert create_res.status_code == 200, f"Create WP failed: {create_res.text}"
    created_json = create_res.json()
    wp_id = created_json["id"]
    assert created_json["wp_reference"] == "WP-REV-01"
    assert created_json["status"] == "Prepared"

    # 2. Upload supporting document
    file_content = b"Invoice sample verification schedule and e-way bill references for FY2425"
    upload_res = client.post(
        f"/api/working-papers/{wp_id}/upload-document",
        files={"file": ("revenue_sampling_schedule.xlsx", file_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"description": "Detailed sampling schedule of top 25 invoices"},
        headers=headers
    )
    assert upload_res.status_code == 200, f"Upload document failed: {upload_res.text}"
    upload_json = upload_res.json()
    doc_id = upload_json["document"]["id"]
    assert upload_json["document"]["name"] == "revenue_sampling_schedule.xlsx"

    # 3. Download supporting document
    download_res = client.get(f"/api/working-papers/download-file/{wp_id}/{doc_id}")
    assert download_res.status_code == 200
    assert download_res.content == file_content

    # 4. Add notes
    notes_res = client.post(
        f"/api/working-papers/{wp_id}/notes",
        json={"notes": "Updated note: Reconciled dispatch registers with ERP system with zero variances."},
        headers=headers
    )
    assert notes_res.status_code == 200

    # 5. Link finding, transaction, and checklist item
    link_f_res = client.post(
        f"/api/working-papers/{wp_id}/links",
        json={"link_type": "finding", "action": "link", "item_id": 1},
        headers=headers
    )
    assert link_f_res.status_code == 200

    link_t_res = client.post(
        f"/api/working-papers/{wp_id}/links",
        json={"link_type": "transaction", "action": "link", "item_id": 1},
        headers=headers
    )
    assert link_t_res.status_code == 200

    link_c_res = client.post(
        f"/api/working-papers/{wp_id}/links",
        json={"link_type": "checklist", "action": "link", "item_id": 1},
        headers=headers
    )
    assert link_c_res.status_code == 200

    # 6. Add reviewer comment
    comment_res = client.post(
        f"/api/working-papers/{wp_id}/comments",
        json={"comment": "Please verify subsequent credit notes issued in April 2025 as well."},
        headers=headers
    )
    assert comment_res.status_code == 200

    # 7. Update status to Under Review
    status_res1 = client.post(
        f"/api/working-papers/{wp_id}/status",
        json={"status": "Under Review"},
        headers=headers
    )
    assert status_res1.status_code == 200
    assert status_res1.json()["new_status"] == "Under Review"

    # 8. Mark Reviewed
    review_res = client.post(
        f"/api/working-papers/{wp_id}/status",
        json={
            "status": "Reviewed",
            "reviewed_by": "CA Rajesh Sharma (Partner)",
            "review_date": "2024-05-20",
            "comment": "Substantive testing methodology reviewed and approved."
        },
        headers=headers
    )
    assert review_res.status_code == 200
    assert review_res.json()["new_status"] == "Reviewed"
    assert review_res.json()["reviewed_by"] == "CA Rajesh Sharma (Partner)"

    # 9. Fetch detail and verify all populated fields & audit trail
    detail_res = client.get(f"/api/working-papers/detail/{wp_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["wp_reference"] == "WP-REV-01"
    assert detail["status"] == "Reviewed"
    assert detail["reviewed_by"] == "CA Rajesh Sharma (Partner)"
    assert len(detail["attached_files"]) == 1
    assert len(detail["reviewer_comments"]) == 2
    assert 1 in detail["linked_findings"]
    assert 1 in detail["linked_transactions"]
    assert 1 in detail["linked_checklists"]
    assert len(detail["audit_trail"]) > 0

    # 10. Test CSV Export
    csv_res = client.get(f"/api/working-papers/{engagement_id}/export/csv")
    assert csv_res.status_code == 200
    assert "WP-REV-01" in csv_res.text

    # 11. Test Delete Rules:
    # Reviewed working paper cannot be deleted without justification/reason
    del_fail_res = client.delete(f"/api/working-papers/{wp_id}", headers=headers)
    assert del_fail_res.status_code == 400
    assert "justification" in del_fail_res.json()["detail"].lower()

    # Reviewed working paper deleted WITH justification
    del_ok_res = client.request(
        "DELETE",
        f"/api/working-papers/{wp_id}",
        json={"reason": "Re-indexed under WP-REV-02 with expanded audit scope"},
        headers=headers
    )
    assert del_ok_res.status_code == 200

    # Verify audit trail records the deletion action
    conn = get_db_connection()
    del_log = conn.execute(
        "SELECT * FROM audit_logs WHERE entity_type = 'working_paper' AND action = 'DELETE_REVIEWED_WORKING_PAPER' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert del_log is not None
    assert "WP-REV-01" in del_log["details"]
    assert "Re-indexed under WP-REV-02" in del_log["details"]
    print("ALL WORKING PAPERS TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    setup_database()
    test_working_papers_full_workflow()

