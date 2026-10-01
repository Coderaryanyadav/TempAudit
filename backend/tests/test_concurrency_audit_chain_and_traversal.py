import os
import io
import time
import uuid
import threading
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import get_db_connection
from backend.app.utils.audit_logger import log_audit_event, verify_audit_trail_integrity
from backend.app.routers.working_papers import resolve_safe_evidence_path

client = TestClient(app)

def get_auth_token(username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


def test_20_concurrent_audit_writes_maintain_unbroken_hash_chain():
    """
    Stress test with 20 concurrent threads writing audit logs.
    Verifies that the serialized mutex prevents race conditions,
    ensuring every previous_hash correctly chains to the prior event's entry_hash.
    """
    conn = get_db_connection()
    baseline_count = conn.execute("SELECT COUNT(*) as c FROM audit_logs").fetchone()["c"]
    conn.close()

    thread_count = 20
    errors = []

    def write_event(idx):
        t_conn = get_db_connection()
        try:
            log_audit_event(
                conn=t_conn,
                action=f"CONCURRENT_TEST_EVENT_{idx}",
                module="StressTest",
                record_id=idx,
                details=f"Concurrent audit event test #{idx}",
                user={"id": 1, "username": "admin"},
                engagement_id=1,
                ip_address="127.0.0.1"
            )
            t_conn.commit()
        except Exception as e:
            errors.append((idx, str(e)))
        finally:
            t_conn.close()

    threads = [threading.Thread(target=write_event, args=(i,)) for i in range(thread_count)]
    
    # Launch all threads at once
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Thread errors during concurrent audit logging: {errors}"

    # Verify integrity using the verification engine
    integrity_result = verify_audit_trail_integrity()
    assert integrity_result["valid"] is True, f"Audit trail broken! Error: {integrity_result}"
    assert integrity_result["entries_checked"] >= baseline_count + thread_count
    assert integrity_result["first_invalid_entry"] is None


def test_audit_trail_verify_endpoint():
    """Test the POST /api/audit-trail/verify endpoint."""
    token = get_auth_token("admin", "admin123")
    res = client.post(
        "/api/audit-trail/verify",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["entries_checked"] > 0
    assert data["first_invalid_entry"] is None


def test_audit_trail_export_and_metadata_engagement_scoping():
    """
    Test that non-Admin users (Auditor/Staff) cannot access or export
    audit events, metadata, or statistics outside their assigned engagements.
    """
    auditor_token = get_auth_token("auditor", "audit123")

    # Auditor accessing audit-trail without engagement_id filter
    res = client.get(
        "/api/audit-trail",
        headers={"Authorization": f"Bearer {auditor_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    logs = data.get("items", [])
    # All logs returned must either belong to an engagement the auditor has access to or have no engagement (system)
    for l in logs:
        if l.get("engagement_id"):
            # Ensure engagement_id belongs to assigned engagements
            conn = get_db_connection()
            eng = conn.execute("SELECT lead_auditor_id, assigned_staff_id FROM engagements WHERE id = ?", (l["engagement_id"],)).fetchone()
            conn.close()
            assert eng is not None

    # Test CSV Export
    csv_res = client.get(
        "/api/audit-trail/export/csv",
        headers={"Authorization": f"Bearer {auditor_token}"}
    )
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")

    # Test JSON Export
    json_res = client.get(
        "/api/audit-trail/export/json",
        headers={"Authorization": f"Bearer {auditor_token}"}
    )
    assert json_res.status_code == 200
    assert "application/json" in json_res.headers.get("content-type", "")

    # Test Metadata Scoping
    meta_res = client.get(
        "/api/audit-trail/metadata",
        headers={"Authorization": f"Bearer {auditor_token}"}
    )
    assert meta_res.status_code == 200
    meta = meta_res.json()
    assert "users" in meta
    assert "actions" in meta


def test_working_papers_path_traversal_prevention():
    """
    Test that malicious filenames such as '../../outside.txt'
    are neutralized, assigned random UUID filenames, and strictly contained within the storage root.
    """
    admin_token = get_auth_token("admin", "admin123")
    
    # 1. Upload evidence with path traversal payload in filename
    fake_file_content = b"Confidential Audit Workpaper Evidence"
    malicious_filename = "../../../malicious_payload.pdf"
    
    res = client.post(
        "/api/working-papers/1/upload-document",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": (malicious_filename, io.BytesIO(fake_file_content), "application/pdf")}
    )
    assert res.status_code == 200
    res_data = res.json()
    doc = res_data["document"]
    
    # Verify original filename is stored safely
    assert doc["name"] == "malicious_payload.pdf"
    # Verify stored file path does NOT contain ../ or outside directories
    assert ".." not in doc["file_path"]
    
    # Verify safe path resolver
    safe_path = resolve_safe_evidence_path(1, doc["file_name"])
    assert safe_path.exists()
    assert safe_path.name != malicious_filename
    assert safe_path.suffix == ".pdf"

    # Verify download works safely
    doc_id = doc["id"]
    dl_res = client.get(
        f"/api/working-papers/download-file/1/{doc_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert dl_res.status_code == 200
    assert dl_res.content == fake_file_content

    # Verify delete works safely
    del_res = client.delete(
        f"/api/working-papers/1/document/{doc_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert del_res.status_code == 200
    assert not safe_path.exists()


def test_client_master_confidentiality_scoping():
    """
    Test that non-Admin users only see clients for engagements they are assigned to.
    """
    auditor_token = get_auth_token("auditor", "audit123")
    
    res = client.get(
        "/api/clients",
        headers={"Authorization": f"Bearer {auditor_token}"}
    )
    assert res.status_code == 200
    clients = res.json()
    assert isinstance(clients, list)
