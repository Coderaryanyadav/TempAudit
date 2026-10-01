import sqlite3
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import init_db
from backend.migrations.runner import apply_migrations

client = TestClient(app)

def test_complete_first_run_user_onboarding_and_auth_journey(tmp_path, monkeypatch):
    """
    Comprehensive E2E verification of:
    Fresh DB -> Setup status uninitialized -> Admin creation -> Firm profile ->
    Security setup -> Backup config -> Completion -> Login -> Invite Staff ->
    Offline Activation -> Client & Engagement creation -> Engagement Scoping ->
    Admin Privilege isolation -> Account Disabling.
    """
    test_db = str(tmp_path / "finaudit_onboarding.db")
    monkeypatch.setenv("FINAUDIT_DB_PATH", test_db)
    
    # Initialize fresh database
    conn = sqlite3.connect(test_db)
    apply_migrations(conn)
    conn.close()

    # Step 1: Check initial setup status on fresh DB
    res = client.get("/api/auth/setup-status")
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "UNINITIALIZED"
    assert data["user_count"] == 0
    assert data["is_setup_completed"] is False

    # Step 2: Create Master Administrator
    admin_payload = {
        "full_name": "CA Aakash Verma",
        "username": "aakash_partner",
        "email": "aakash@verma-audit.in",
        "designation": "Senior Engagement Partner (FCA)",
        "phone": "+91 98111 22334",
        "password": "StrongMasterAdminPass@2026"
    }
    res = client.post("/api/auth/initial-setup", json=admin_payload)
    assert res.status_code == 200
    setup_res = res.json()
    assert setup_res["status"] == "success"
    admin_token = setup_res["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Step 3: Verify duplicate admin setup is blocked
    res_dup = client.post("/api/auth/initial-setup", json=admin_payload)
    assert res_dup.status_code == 400
    assert "already been initialized" in res_dup.json()["detail"]

    # Step 4: Step 2 of Wizard — Configure Firm Profile
    firm_payload = {
        "firm_name": "Verma & Associates, Chartered Accountants",
        "address": "104, Nariman Point Commercial Hub",
        "city": "Mumbai",
        "state": "Maharashtra",
        "country": "India",
        "pin_code": "400021",
        "email": "contact@verma-audit.in",
        "phone": "+91 22 2288 1234",
        "website": "https://verma-audit.in",
        "icai_reg_number": "FRN-009876W"
    }
    res_firm = client.post("/api/auth/setup/firm-profile", json=firm_payload, headers=admin_headers)
    assert res_firm.status_code == 200
    assert res_firm.json()["status"] == "success"

    # Step 5: Step 3 of Wizard — Configure Security & Local AI Privacy
    sec_payload = {
        "session_timeout_minutes": 60,
        "local_ai_mode": "LOCAL_ONLY"
    }
    res_sec = client.post("/api/auth/setup/security-config", json=sec_payload, headers=admin_headers)
    assert res_sec.status_code == 200

    # Step 6: Step 4 of Wizard — Configure Backup Storage
    backup_payload = {
        "backup_location": "backups",
        "auto_backup_enabled": True,
        "backup_retention_days": 30
    }
    res_backup = client.post("/api/auth/setup/backup-config", json=backup_payload, headers=admin_headers)
    assert res_backup.status_code == 200

    # Step 7: Step 5 of Wizard — Mark Setup Complete
    res_comp = client.post("/api/auth/setup/complete", headers=admin_headers)
    assert res_comp.status_code == 200

    # Step 8: Verify Setup Status is now CONFIGURED
    res_status = client.get("/api/auth/setup-status")
    assert res_status.status_code == 200
    assert res_status.json()["state"] == "CONFIGURED"
    assert res_status.json()["is_setup_completed"] is True
    assert res_status.json()["user_count"] == 1

    # Step 9: Administrator Login
    login_res = client.post("/api/auth/login", json={
        "username": "aakash_partner",
        "password": "StrongMasterAdminPass@2026"
    })
    assert login_res.status_code == 200
    admin_token = login_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Step 10: Admin Invites Staff User (Offline Activation Flow)
    invite_payload = {
        "full_name": "Rohan Deshmukh",
        "username": "rohan_staff",
        "email": "rohan@verma-audit.in",
        "role": "Audit Staff",
        "phone": "+91 98222 33445",
        "designation": "Article Assistant / Audit Staff"
    }
    res_invite = client.post("/api/auth/users/invite", json=invite_payload, headers=admin_headers)
    assert res_invite.status_code == 200
    invite_data = res_invite.json()
    activation_token = invite_data["activation_token"]
    staff_user_id = invite_data["user_id"]
    assert activation_token is not None

    # Step 11: Invited Staff User queries activation token status
    res_info = client.get(f"/api/auth/activation-info/{activation_token}")
    assert res_info.status_code == 200
    info_data = res_info.json()
    assert info_data["is_valid"] is True
    assert info_data["username"] == "rohan_staff"
    assert info_data["role"] == "Audit Staff"

    # Step 12: Invited User attempts to log in before activation -> Blocked
    res_early_login = client.post("/api/auth/login", json={
        "username": "rohan_staff",
        "password": "AnyPassword"
    })
    assert res_early_login.status_code in (401, 403)

    # Step 13: Staff User completes onboarding and activates account
    activate_payload = {
        "activation_token": activation_token,
        "password": "RohanStaffPassword@2026",
        "full_name": "Rohan Deshmukh (Audit Staff)",
        "phone": "+91 98222 33445"
    }
    res_act = client.post("/api/auth/activate-user", json=activate_payload)
    assert res_act.status_code == 200
    staff_token = res_act.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Step 14: Activation token cannot be reused
    res_reuse = client.post("/api/auth/activate-user", json=activate_payload)
    assert res_reuse.status_code == 404

    # Step 15: Staff User gets /me profile
    res_me = client.get("/api/auth/me", headers=staff_headers)
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "rohan_staff"
    assert res_me.json()["role"] == "Audit Staff"
    assert res_me.json()["permissions"]["can_manage_users"] is False

    # Step 16: Staff cannot perform admin user management (RBAC protection)
    res_hack = client.post("/api/auth/users", json={
        "username": "hacked_admin",
        "email": "hacked@admin.in",
        "full_name": "Hacker",
        "role": "Admin",
        "password": "Password12345"
    }, headers=staff_headers)
    assert res_hack.status_code == 403

    # Step 17: Admin creates Client
    client_res = client.post("/api/clients", json={
        "name": "Tata Consumer Logistics Ltd",
        "entity_type": "Public Limited Company",
        "pan": "ABCDE1234F",
        "gstin": "27ABCDE1234F1Z5",
        "industry": "Supply Chain & Logistics",
        "financial_year": "2025-26"
    }, headers=admin_headers)
    assert client_res.status_code == 200
    client_id = client_res.json()["id"]

    # Step 18: Admin creates Engagement 1 (assigned to Staff) and Engagement 2 (unassigned)
    eng1_res = client.post("/api/engagements", json={
        "client_id": client_id,
        "title": "Statutory Audit FY 2025-26",
        "audit_type": "Statutory Audit",
        "financial_year": "2025-26",
        "assigned_staff_id": staff_user_id
    }, headers=admin_headers)
    assert eng1_res.status_code == 200
    eng1_id = eng1_res.json()["id"]

    eng2_res = client.post("/api/engagements", json={
        "client_id": client_id,
        "title": "Confidential Forensic Audit 2025-26",
        "audit_type": "Special Audit",
        "financial_year": "2025-26",
        "assigned_staff_id": None
    }, headers=admin_headers)
    assert eng2_res.status_code == 200
    eng2_id = eng2_res.json()["id"]

    # Step 19: Staff accesses assigned engagement -> Allowed
    res_staff_eng1 = client.get(f"/api/working-papers/{eng1_id}", headers=staff_headers)
    assert res_staff_eng1.status_code == 200

    # Step 20: Staff accesses unassigned engagement -> Forbidden (403)
    res_staff_eng2 = client.get(f"/api/working-papers/{eng2_id}", headers=staff_headers)
    assert res_staff_eng2.status_code == 403

    # Step 21: Admin disables Staff user account
    res_disable = client.put(f"/api/auth/users/{staff_user_id}/status", json={"is_active": False}, headers=admin_headers)
    assert res_disable.status_code == 200
    assert res_disable.json()["is_active"] == 0

    # Step 22: Disabled Staff user cannot log in
    res_staff_login_blocked = client.post("/api/auth/login", json={
        "username": "rohan_staff",
        "password": "RohanStaffPassword@2026"
    })
    assert res_staff_login_blocked.status_code == 403
    assert "disabled" in res_staff_login_blocked.json()["detail"].lower()
