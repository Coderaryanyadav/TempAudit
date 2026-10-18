import pytest
import sqlite3
import time
from unittest.mock import patch
from fastapi import HTTPException
from backend.app.database import init_db, get_db_connection
from backend.app.routers.import_data import check_engagement_access, UPLOAD_DIR
from backend.app.routers.auth import (
    _check_setup_rate_limit,
    _check_login_rate_limit,
    _record_login_failure,
    _clear_login_failures,
    _ensure_rate_limit_table
)
from backend.app.services.backup_service import (
    BackupService,
    compute_canonical_manifest_checksum,
    compute_manifest_signature,
    compute_file_sha256
)
import tarfile
import os
import json
import uuid

def test_strict_engagement_access_for_audit_staff():
    """Verify Audit Staff cannot access unassigned or restricted engagements."""
    init_db()
    conn = get_db_connection()
    try:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        # 1. Create client and users
        conn.execute("INSERT OR REPLACE INTO clients (id, name, entity_type, created_at) VALUES (991, 'Strict Access Client', 'Pvt Ltd', ?)", (now,))
        for u_id, u_name, u_role in [(101, "auditor_lead", "Auditor"), (201, "staff_201", "Audit Staff"), (202, "staff_202", "Audit Staff")]:
            conn.execute("""
                INSERT OR REPLACE INTO users (id, username, email, full_name, password_hash, role, is_active, created_at)
                VALUES (?, ?, ? || '@test.com', ? || ' User', 'hash', ?, 1, ?)
            """, (u_id, u_name, u_name, u_name, u_role, now))
        # 2. Create unassigned engagement
        conn.execute("""
            INSERT OR REPLACE INTO engagements (id, client_id, title, audit_type, financial_year, lead_auditor_id, assigned_staff_id, created_at, updated_at)
            VALUES (9901, 991, 'Unassigned Engagement', 'Statutory', '2024-25', 101, NULL, ?, ?)
        """, (now, now))
        
        # 3. Create engagement assigned to staff 202
        conn.execute("""
            INSERT OR REPLACE INTO engagements (id, client_id, title, audit_type, financial_year, lead_auditor_id, assigned_staff_id, created_at, updated_at)
            VALUES (9902, 991, 'Staff 202 Engagement', 'Statutory', '2024-25', 101, 202, ?, ?)
        """, (now, now))
        
        staff_user_201 = {"id": 201, "username": "staff_201", "role": "Audit Staff"}
        staff_user_202 = {"id": 202, "username": "staff_202", "role": "Audit Staff"}
        auditor_user = {"id": 101, "username": "auditor_lead", "role": "Auditor"}
        admin_user = {"id": 1, "username": "admin", "role": "Admin"}
        
        # Test A: Staff 201 accessing unassigned engagement -> MUST BE FORBIDDEN (403)
        with pytest.raises(HTTPException) as exc_info:
            check_engagement_access(conn, 9901, staff_user_201)
        assert exc_info.value.status_code == 403
        assert "not assigned" in exc_info.value.detail.lower()
        
        # Test B: Staff 201 accessing engagement assigned to Staff 202 -> MUST BE FORBIDDEN (403)
        with pytest.raises(HTTPException) as exc_info:
            check_engagement_access(conn, 9902, staff_user_201)
        assert exc_info.value.status_code == 403
        assert "not assigned" in exc_info.value.detail.lower()
        
        # Test C: Staff 202 accessing engagement assigned to Staff 202 -> ALLOWED
        eng_res = check_engagement_access(conn, 9902, staff_user_202)
        assert eng_res["id"] == 9902
        
        # Test D: Auditor accessing unassigned or assigned engagement -> ALLOWED
        eng_auditor = check_engagement_access(conn, 9901, auditor_user)
        assert eng_auditor["id"] == 9901
        
        # Test E: Admin accessing any engagement -> ALLOWED
        eng_admin = check_engagement_access(conn, 9901, admin_user)
        assert eng_admin["id"] == 9901
    finally:
        conn.close()

def test_auth_rate_limit_connection_cleanup():
    """Verify rate-limit helpers cleanly close connections even under 429 lockouts."""
    init_db()
    
    # Reset setup rate limits
    conn = get_db_connection()
    try:
        _ensure_rate_limit_table(conn)
        conn.execute("DELETE FROM rate_limits WHERE key = 'setup'")
        conn.commit()
    finally:
        conn.close()
    
    # Trigger 5 calls -> 5th should succeed, 6th should raise 429
    for _ in range(5):
        _check_setup_rate_limit()
        
    with pytest.raises(HTTPException) as exc_info:
        _check_setup_rate_limit()
    assert exc_info.value.status_code == 429
    
    # Verify login rate limiting and cleanup
    test_key = "test_user_ip_cleanup"
    _clear_login_failures(test_key)
    
    for _ in range(10):
        _record_login_failure(test_key)
        
    with pytest.raises(HTTPException) as exc_info:
        _check_login_rate_limit(test_key)
    assert exc_info.value.status_code == 429
    
    # Clear failures and verify recovery
    _clear_login_failures(test_key)
    _check_login_rate_limit(test_key) # Should not raise after clear

def test_backup_tampered_manifest_and_malicious_archive(tmp_path):
    """Verify backup validation & restore reject tampered manifests, altered checksums, missing signatures, and malicious members."""
    init_db()
    bundle_path, manifest = BackupService.create_verified_bundle(created_by="SecurityAuditTest")
    assert os.path.exists(bundle_path)
    
    # 1. Tamper test: alter database_sha256 in manifest inside tar
    tampered_dir = tmp_path / f"tamper_{uuid.uuid4().hex[:6]}"
    tampered_dir.mkdir()
    
    with tarfile.open(bundle_path, "r:gz") as tar:
        if hasattr(tarfile, 'data_filter'):
            tar.extractall(path=tampered_dir, filter='data')
        else:
            tar.extractall(path=tampered_dir)
        
    manifest_file = tampered_dir / "manifest.json"
    with open(manifest_file, "r") as f:
        m_data = json.load(f)
        
    # Alter manifest data without updating manifest_checksum
    m_data["engagement_count"] = 99999
    with open(manifest_file, "w") as f:
        json.dump(m_data, f, indent=2)
        
    tampered_bundle = str(tmp_path / "tampered_manifest.finpkg")
    with tarfile.open(tampered_bundle, "w:gz") as tar:
        tar.add(str(tampered_dir / "finauditpro.db"), arcname="finauditpro.db")
        tar.add(str(manifest_file), arcname="manifest.json")
        
    val_tamper = BackupService.validate_bundle(tampered_bundle)
    assert val_tamper["valid"] is False
    assert "manifest integrity violation" in val_tamper["error"].lower()
    with pytest.raises(ValueError) as exc:
        BackupService.restore_verified_bundle(tampered_bundle)
    assert "validation failed" in str(exc.value).lower()

    # 1b. Signature forgery test: attacker recomputes manifest_checksum to bypass SHA check, but lacks HMAC key
    m_data["manifest_checksum"] = compute_canonical_manifest_checksum(m_data)
    m_data["manifest_signature"] = "forged_signature_000000000000000000000000000000000000000000000000"
    with open(manifest_file, "w") as f:
        json.dump(m_data, f, indent=2)

    tampered_sig_bundle = str(tmp_path / "tampered_signature.finpkg")
    with tarfile.open(tampered_sig_bundle, "w:gz") as tar:
        tar.add(str(tampered_dir / "finauditpro.db"), arcname="finauditpro.db")
        tar.add(str(manifest_file), arcname="manifest.json")

    val_tamper_sig = BackupService.validate_bundle(tampered_sig_bundle)
    assert val_tamper_sig["valid"] is False
    assert "cryptographic authenticity violation" in val_tamper_sig["error"].lower()
    with pytest.raises(ValueError) as exc:
        BackupService.restore_verified_bundle(tampered_sig_bundle)
    assert "validation failed" in str(exc.value).lower()

    # 1c. Signature stripping test: attacker removes manifest_signature completely
    del m_data["manifest_signature"]
    m_data["manifest_checksum"] = compute_canonical_manifest_checksum(m_data)
    with open(manifest_file, "w") as f:
        json.dump(m_data, f, indent=2)

    stripped_sig_bundle = str(tmp_path / "stripped_signature.finpkg")
    with tarfile.open(stripped_sig_bundle, "w:gz") as tar:
        tar.add(str(tampered_dir / "finauditpro.db"), arcname="finauditpro.db")
        tar.add(str(manifest_file), arcname="manifest.json")

    val_stripped_sig = BackupService.validate_bundle(stripped_sig_bundle)
    assert val_stripped_sig["valid"] is False
    assert "missing cryptographic manifest_signature" in val_stripped_sig["error"].lower()
    with pytest.raises(ValueError) as exc:
        BackupService.restore_verified_bundle(stripped_sig_bundle)
    assert "validation failed" in str(exc.value).lower()
    
    # 2. Malicious member test: attempt archive with path traversal member
    malicious_bundle = str(tmp_path / "malicious_member.finpkg")
    with tarfile.open(malicious_bundle, "w:gz") as tar:
        tar.add(str(tampered_dir / "finauditpro.db"), arcname="finauditpro.db")
        tar.add(str(manifest_file), arcname="manifest.json")
        # Add rogue file outside allowed root
        rogue_file = tmp_path / "rogue.sh"
        rogue_file.write_text("echo pwned")
        tar.add(str(rogue_file), arcname="etc/evil_cron.sh")
        
    val_malicious = BackupService.validate_bundle(malicious_bundle)
    assert val_malicious["valid"] is False
    assert "security violation" in val_malicious["error"].lower()
    with pytest.raises(ValueError) as exc:
        BackupService.restore_verified_bundle(malicious_bundle)
    assert "validation failed" in str(exc.value).lower()

    # 3. Database corruption test: corrupted SQLite database content
    corrupt_db_file = tampered_dir / "finauditpro.db"
    corrupt_db_file.write_bytes(b"corrupted binary database payload")
    m_data["manifest_signature"] = compute_manifest_signature(m_data)
    with open(manifest_file, "w") as f:
        json.dump(m_data, f, indent=2)

    corrupt_bundle = str(tmp_path / "corrupt_db.finpkg")
    with tarfile.open(corrupt_bundle, "w:gz") as tar:
        tar.add(str(corrupt_db_file), arcname="finauditpro.db")
        tar.add(str(manifest_file), arcname="manifest.json")

    val_corrupt = BackupService.validate_bundle(corrupt_bundle)
    assert val_corrupt["valid"] is False
    assert ("checksum mismatch" in val_corrupt["error"].lower() or "integrity violation" in val_corrupt["error"].lower() or "manifest verification failed" in val_corrupt["error"].lower())
    with pytest.raises(ValueError) as exc:
        BackupService.restore_verified_bundle(corrupt_bundle)
    assert "validation failed" in str(exc.value).lower()
    
    # Clean up
    if os.path.exists(bundle_path):
        os.remove(bundle_path)

def test_backup_and_restore_with_evidence_files(tmp_path):
    """Verify evidence files in UPLOAD_DIR directory are bundled, restored, and verified."""
    init_db()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    test_evidence_file = os.path.join(UPLOAD_DIR, "test_evidence_receipt_123.txt")
    with open(test_evidence_file, "w", encoding="utf-8") as f:
        f.write("GST Invoice No: GST-9988-VALID-EVIDENCE")

    bundle_path = None
    try:
        # Create verified bundle containing evidence
        bundle_path, manifest = BackupService.create_verified_bundle(created_by="EvidenceBackupTest")
        assert os.path.exists(bundle_path)

        # Remove local evidence file to simulate data loss
        if os.path.exists(test_evidence_file):
            os.remove(test_evidence_file)
        assert not os.path.exists(test_evidence_file)

        # Restore bundle
        res = BackupService.restore_verified_bundle(bundle_path)
        assert res["status"] == "SUCCESS"
        assert res["safety_snapshot"] is not None

        # Verify evidence file is restored
        assert os.path.exists(test_evidence_file)
        with open(test_evidence_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "GST-9988-VALID-EVIDENCE" in content

    finally:
        if os.path.exists(test_evidence_file):
            try:
                os.remove(test_evidence_file)
            except Exception:
                pass
        if bundle_path and os.path.exists(bundle_path):
            try:
                os.remove(bundle_path)
            except Exception:
                pass

def test_upload_connection_cleanup_on_failure():
    """Verify upload endpoint closes DB connection on 404 (missing engagement) and 403 (unauthorized staff)."""
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.auth import create_access_token
    import io

    init_db()
    conn = get_db_connection()
    try:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT OR REPLACE INTO clients (id, name, entity_type, created_at) VALUES (991, 'Strict Access Client', 'Pvt Ltd', ?)", (now,))
        for u_id, u_name, u_role in [(101, "auditor_lead", "Auditor"), (201, "staff_201", "Audit Staff"), (202, "staff_202", "Audit Staff")]:
            conn.execute("""
                INSERT OR REPLACE INTO users (id, username, email, full_name, password_hash, role, is_active, created_at)
                VALUES (?, ?, ? || '@test.com', ? || ' User', 'hash', ?, 1, ?)
            """, (u_id, u_name, u_name, u_name, u_role, now))
        conn.execute("""
            INSERT OR REPLACE INTO engagements (id, client_id, title, audit_type, financial_year, lead_auditor_id, assigned_staff_id, created_at, updated_at)
            VALUES (9902, 991, 'Staff 202 Engagement', 'Statutory', '2024-25', 101, 202, ?, ?)
        """, (now, now))
    finally:
        conn.close()

    client = TestClient(app)
    staff_token = create_access_token({"sub": "staff_201", "id": 201, "role": "Audit Staff"})
    headers = {"Authorization": f"Bearer {staff_token}"}
    dummy_csv = io.BytesIO(b"date,ledger,amount\n2026-01-01,Sales,100\n")

    # Spy on get_db_connection in import_data router to verify conn.close() is strictly invoked
    import backend.app.routers.import_data as import_module
    original_get_db = import_module.get_db_connection

    closed_connections = []
    created_connections = []

    class ConnectionProxy:
        def __init__(self, real_conn):
            self._conn = real_conn
        def close(self):
            closed_connections.append(self._conn)
            return self._conn.close()
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()
        def __getattr__(self, name):
            return getattr(self._conn, name)

    def spying_get_db_connection():
        real_conn = original_get_db()
        created_connections.append(real_conn)
        return ConnectionProxy(real_conn)

    with patch.object(import_module, "get_db_connection", side_effect=spying_get_db_connection):
        # 1. Nonexistent engagement (should return 404 and strictly close connection)
        dummy_csv.seek(0)
        res_404 = client.post(
            "/api/import/upload",
            data={"engagement_id": 999999, "data_category": "General Ledger"},
            files={"file": ("test.csv", dummy_csv, "text/csv")},
            headers=headers
        )
        assert res_404.status_code == 404
        assert "not found" in res_404.json()["detail"].lower()
        assert len(created_connections) == 1
        assert len(closed_connections) == 1

        # 2. Unauthorized staff member for engagement 9902 (should return 403 and strictly close connection)
        dummy_csv.seek(0)
        res_403 = client.post(
            "/api/import/upload",
            data={"engagement_id": 9902, "data_category": "General Ledger"},
            files={"file": ("test.csv", dummy_csv, "text/csv")},
            headers=headers
        )
        assert res_403.status_code == 403
        assert "not assigned" in res_403.json()["detail"].lower()
        assert len(created_connections) == 2
        assert len(closed_connections) == 2
