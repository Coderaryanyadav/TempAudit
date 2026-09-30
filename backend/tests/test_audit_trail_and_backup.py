import io
import json
import os
import pytest
import sqlite3
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import get_db_connection, DB_PATH, init_db
from backend.app.utils.audit_logger import log_audit_event

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield

def get_auth_token(username="admin", password="admin123"):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


def test_01_all_14_actions_logged_with_required_fields():
    """
    Verifies that all 14 required actions can be recorded into the append-only audit trail:
    - Timestamp
    - User
    - Action
    - Module
    - Record ID
    - Old Value
    - New Value
    """
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Login (already tested in get_auth_token, let's verify in DB)
    conn = get_db_connection()
    login_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'LOGIN' ORDER BY id DESC LIMIT 1").fetchone()
    assert login_log is not None
    assert login_log["username"] == "admin"
    assert login_log["module"] == "AUTH"
    assert login_log["timestamp"] is not None

    # 2. Logout
    res_logout = client.post("/api/auth/logout", headers=headers)
    assert res_logout.status_code == 200
    logout_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'LOGOUT' ORDER BY id DESC LIMIT 1").fetchone()
    assert logout_log is not None
    assert logout_log["module"] == "AUTH"

    # Re-login for remaining actions
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    import uuid, random
    uid_str = uuid.uuid4().hex[:4].upper()
    random_digits = f"{random.randint(1000, 9999)}"
    client_name = f"Audit Trail Test Corp {uid_str}"
    pan_str = f"AABCT{random_digits}K"
    gstin_str = f"27AABCT{random_digits}K1Z5"

    # 3. Client Creation
    res_client = client.post("/api/clients", json={
        "name": client_name,
        "entity_type": "Private Limited Company",
        "pan": pan_str,
        "gstin": gstin_str,
        "industry": "Information Technology"
    }, headers=headers)
    assert res_client.status_code == 200, f"Create client failed: {res_client.text}"
    client_id = res_client.json()["id"]

    client_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'CREATE_CLIENT' AND record_id = ?", (str(client_id),)).fetchone()
    assert client_log is not None
    assert client_log["module"] == "CLIENTS"
    assert client_log["new_value"] is not None
    assert client_name in client_log["new_value"]

    # 4. Engagement Creation
    res_eng = client.post("/api/engagements", json={
        "client_id": client_id,
        "title": "Statutory Audit FY 2024-25",
        "audit_type": "Statutory Audit",
        "financial_year": "2024-25"
    }, headers=headers)
    assert res_eng.status_code == 200
    eng_id = res_eng.json()["id"]

    eng_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'CREATE_ENGAGEMENT' AND record_id = ?", (str(eng_id),)).fetchone()
    assert eng_log is not None
    assert eng_log["module"] == "ENGAGEMENTS"

    # 5. Data Modification (Updating Client details)
    res_up_client = client.put(f"/api/clients/{client_id}", json={
        "contact_person": "Mr. Rajesh Audit",
        "notes": "Updated for audit trail test"
    }, headers=headers)
    assert res_up_client.status_code == 200

    mod_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'DATA_MODIFICATION' AND module = 'CLIENTS' AND record_id = ?", (str(client_id),)).fetchone()
    assert mod_log is not None
    assert mod_log["old_value"] is not None
    assert mod_log["new_value"] is not None
    assert "Rajesh Audit" in mod_log["new_value"]

    # 6. File Import (log_audit_event directly or via import endpoint)
    log_audit_event(
        conn,
        action="FILE_IMPORT",
        module="IMPORT",
        record_id=101,
        engagement_id=eng_id,
        new_value={"file_name": "tally_ledger.xlsx", "rows": 1250, "category": "General Ledger"},
        details="Imported 1250 transactions from tally_ledger.xlsx",
        user={"id": 1, "username": "admin"}
    )
    conn.commit()

    import_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'FILE_IMPORT' AND record_id = '101'").fetchone()
    assert import_log is not None
    assert import_log["module"] == "IMPORT"
    assert "tally_ledger.xlsx" in import_log["new_value"]

    # 7. Finding Creation
    res_finding = client.post("/api/findings/custom", json={
        "engagement_id": eng_id,
        "title": "Unexplained High Value Cash Withdrawal",
        "module": "Cash & Bank",
        "category": "Statutory Compliance",
        "severity": "HIGH",
        "description": "Cash withdrawal exceeding threshold without voucher authorization.",
        "rule_used": "Section 40A(3)"
    }, headers=headers)
    assert res_finding.status_code == 200
    finding_id = res_finding.json()["finding_id"]

    find_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'CREATE_FINDING' AND record_id = ?", (str(finding_id),)).fetchone()
    assert find_log is not None
    assert find_log["module"] == "FINDINGS"
    assert "Unexplained High Value Cash Withdrawal" in find_log["new_value"]

    # 8. Finding Status Change
    res_status = client.put(f"/api/findings/detail/{finding_id}", json={
        "status": "In Review"
    }, headers=headers)
    assert res_status.status_code == 200

    status_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'FINDING_STATUS_CHANGE' AND record_id = ?", (str(finding_id),)).fetchone()
    assert status_log is not None
    assert "Open" in status_log["old_value"]
    assert "In Review" in status_log["new_value"]

    # 9. Auditor Comment
    res_comment = client.put(f"/api/findings/detail/{finding_id}", json={
        "auditor_comment": "Verified bank statement. Requires management representation."
    }, headers=headers)
    assert res_comment.status_code == 200

    comment_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'AUDITOR_COMMENT' AND record_id = ?", (str(finding_id),)).fetchone()
    assert comment_log is not None
    assert "Requires management representation" in comment_log["new_value"]

    # 10. Checklist Change
    chk_row = conn.execute("SELECT id, item_code FROM audit_checklists WHERE engagement_id = ? LIMIT 1", (eng_id,)).fetchone()
    assert chk_row is not None
    chk_id = chk_row["id"]

    res_chk_up = client.put(f"/api/checklist/item/{chk_id}", json={
        "status": "Completed",
        "comment": "All vouchers verified and cross-checked.",
        "assigned_staff": "Senior Auditor"
    }, headers=headers)
    assert res_chk_up.status_code == 200

    chk_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'CHECKLIST_CHANGE' AND record_id = ?", (str(chk_id),)).fetchone()
    assert chk_log is not None
    assert chk_log["module"] == "CHECKLISTS"

    # 11. Working Paper Change
    wp_ref_str = f"WP-AUD-{uid_str}"
    res_wp = client.post(f"/api/working-papers?engagement_id={eng_id}", json={
        "wp_reference": wp_ref_str,
        "title": "Cash and Bank Verification Schedule",
        "area": "Cash & Bank",
        "description": "Verification of year-end cash certificates and bank confirmations."
    }, headers=headers)
    assert res_wp.status_code == 200, f"Create WP failed: {res_wp.text}"
    wp_id = res_wp.json()["id"]

    wp_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'CREATE_WORKING_PAPER' AND record_id = ?", (str(wp_id),)).fetchone()
    assert wp_log is not None
    assert wp_log["module"] == "WORKING_PAPER" or wp_log["module"] == "WORKING_PAPERS"

    # 12. Report Generation
    res_rep = client.post(f"/api/reports/generate-pdf/{eng_id}?report_type=engagement_summary", headers=headers)
    assert res_rep.status_code == 200
    rep_id = res_rep.json()["report_id"]

    rep_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'REPORT_GENERATION' AND record_id = ?", (str(rep_id),)).fetchone()
    assert rep_log is not None
    assert rep_log["module"] == "REPORTS"

    # 13. Report Export
    res_dl = client.get(f"/api/reports/download/{rep_id}", headers=headers)
    assert res_dl.status_code == 200

    export_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'REPORT_EXPORT' AND record_id = ?", (str(rep_id),)).fetchone()
    assert export_log is not None

    # 14. Settings Change
    res_settings = client.post("/api/settings", json={
        "settings": {
            "firm_name": "Sharma & Associates LLP",
            "materiality_percentage": 0.75,
            "cash_threshold_40a3": 10000.0
        }
    }, headers=headers)
    assert res_settings.status_code == 200

    set_log = conn.execute("SELECT * FROM audit_logs WHERE action = 'SETTINGS_CHANGE' ORDER BY id DESC LIMIT 1").fetchone()
    assert set_log is not None
    assert set_log["module"] == "SETTINGS"
    assert "Sharma & Associates LLP" in set_log["new_value"]

    conn.close()


def test_02_immutable_append_only_sqlite_triggers():
    """
    Verifies that SQLite triggers actively block direct UPDATE and DELETE
    operations on the audit_logs table, ensuring true tamper-resistance.
    """
    conn = get_db_connection()
    test_id = conn.execute("SELECT id FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()["id"]

    # Attempt UPDATE
    with pytest.raises(sqlite3.DatabaseError) as exc_update:
        conn.execute("UPDATE audit_logs SET details = 'HACKED' WHERE id = ?", (test_id,))
    assert "immutable" in str(exc_update.value).lower()

    # Attempt DELETE
    with pytest.raises(sqlite3.DatabaseError) as exc_delete:
        conn.execute("DELETE FROM audit_logs WHERE id = ?", (test_id,))
    assert "immutable" in str(exc_delete.value).lower()

    conn.close()


def test_03_audit_trail_search_filtering_and_pagination():
    """
    Verifies multi-criteria search, module/action/user filtering, and pagination on /api/audit-trail.
    """
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Search by action
    res_act = client.get("/api/audit-trail?action=LOGIN", headers=headers)
    assert res_act.status_code == 200
    data_act = res_act.json()
    assert data_act["total"] >= 1
    assert all(item["action"] == "LOGIN" for item in data_act["items"])

    # 2. Search by module
    res_mod = client.get("/api/audit-trail?module=CLIENTS", headers=headers)
    assert res_mod.status_code == 200
    data_mod = res_mod.json()
    assert all(item["module"] == "CLIENTS" for item in data_mod["items"])

    # 3. Search by keyword
    res_kw = client.get("/api/audit-trail?search=Sharma", headers=headers)
    assert res_kw.status_code == 200
    data_kw = res_kw.json()
    assert len(data_kw["items"]) >= 1

    # 4. Pagination
    res_p1 = client.get("/api/audit-trail?page=1&page_size=2", headers=headers)
    assert res_p1.status_code == 200
    p1_data = res_p1.json()
    assert len(p1_data["items"]) <= 2
    assert p1_data["page"] == 1
    assert p1_data["page_size"] == 2


def test_04_audit_trail_csv_and_json_export():
    """
    Verifies that filtered audit logs can be exported as downloadable CSV and JSON files.
    """
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # CSV Export
    res_csv = client.get("/api/audit-trail/export/csv", headers=headers)
    assert res_csv.status_code == 200
    assert res_csv.headers["content-type"].startswith("text/csv")
    assert "Log ID,Timestamp (ISO),User,Action,Module" in res_csv.text

    # JSON Export
    res_json = client.get("/api/audit-trail/export/json", headers=headers)
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]
    parsed = json.loads(res_json.text)
    assert "audit_logs" in parsed
    assert len(parsed["audit_logs"]) > 0


def test_05_database_backup_and_restore_workflow():
    """
    Verifies creating local SQLite backup, listing backups, downloading,
    and restoring from backup with automatic pre-restore safety snapshot.
    """
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create local backup
    res_backup = client.post("/api/audit-trail/backup/create", headers=headers)
    assert res_backup.status_code == 200
    backup_data = res_backup.json()
    filename = backup_data["filename"]
    assert filename.startswith("finauditpro_backup_")
    assert backup_data["checksum_sha256"] is not None
    assert backup_data["size_kb"] > 0

    # 2. List backups
    res_list = client.get("/api/audit-trail/backups", headers=headers)
    assert res_list.status_code == 200
    backups = res_list.json()
    assert any(b["filename"] == filename for b in backups)

    # 3. Download backup
    res_dl = client.get(f"/api/audit-trail/backup/download/{filename}", headers=headers)
    assert res_dl.status_code == 200
    assert len(res_dl.content) > 0

    # 4. Restore database from existing backup
    res_restore = client.post(f"/api/audit-trail/backup/restore/{filename}", headers=headers)
    assert res_restore.status_code == 200
    restore_data = res_restore.json()
    assert restore_data["restored_from"] == filename
    assert restore_data["safety_snapshot_created"].startswith("pre_restore_safety_")

    # 5. Verify database connection remains healthy after restore
    conn = get_db_connection()
    user = conn.execute("SELECT username FROM users WHERE username = 'admin'").fetchone()
    assert user is not None
    assert user["username"] == "admin"
    conn.close()
