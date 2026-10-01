import os
import hashlib
import sqlite3
import pytest
from backend.app.repositories.evidence_repo import EvidenceRepository
from backend.migrations.runner import apply_migrations

def test_evidence_registration_hashing_and_integrity(tmp_path):
    """Verify evidence file SHA-256 recording and tampering detection."""
    db_file = str(tmp_path / "test_ev.db")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)

    # 1. Create client and engagement
    conn.execute("INSERT INTO clients (id, name, created_at) VALUES (1, 'Test Client Ltd', '2026-10-01T00:00:00')")
    conn.execute("INSERT INTO engagements (id, client_id, title, financial_year, created_at) VALUES (1, 1, 'Statutory Audit 25-26', '2025-26', '2026-10-01T00:00:00')")
    conn.commit()

    # 2. Create physical file on disk
    file_content = b"Audit Evidence - Bank Confirmation Statement for Account 12345"
    file_sha256 = hashlib.sha256(file_content).hexdigest()
    ev_path = tmp_path / "bank_confirm_v1.bin"
    ev_path.write_bytes(file_content)

    repo = EvidenceRepository(conn)
    ev_id = repo.register_evidence(
        engagement_id=1,
        filename="bank_confirm_v1.bin",
        original_filename="bank_confirm.pdf",
        storage_path=str(ev_path),
        file_size=len(file_content),
        mime_type="application/pdf",
        sha256_hash=file_sha256,
        uploaded_by="Lead Auditor",
        version=1
    )
    conn.commit()

    # 3. Verify physical integrity matches PASS
    result = repo.verify_physical_integrity(ev_id)
    assert result["valid"] is True
    assert result["status"] == "VALID"
    assert result["actual_hash"] == file_sha256

    # 4. Tamper with the physical file on disk
    ev_path.write_bytes(b"Tampered unauthorized content modification!")

    tampered_result = repo.verify_physical_integrity(ev_id)
    assert tampered_result["valid"] is False
    assert tampered_result["status"] == "CORRUPTED"
    assert tampered_result["actual_hash"] != file_sha256

    # 5. Test evidence versioning
    new_content = b"Audit Evidence - Bank Confirmation Statement v2 Corrected"
    new_sha256 = hashlib.sha256(new_content).hexdigest()
    v2_path = tmp_path / "bank_confirm_v2.bin"
    v2_path.write_bytes(new_content)

    v2_id = repo.register_evidence(
        engagement_id=1,
        filename="bank_confirm_v2.bin",
        original_filename="bank_confirm.pdf",
        storage_path=str(v2_path),
        file_size=len(new_content),
        mime_type="application/pdf",
        sha256_hash=new_sha256,
        uploaded_by="Lead Auditor",
        parent_evidence_id=ev_id,
        replacement_reason="Management provided signed stamp version",
        version=2
    )
    conn.commit()

    v1_rec = repo.get_by_id(ev_id)
    v2_rec = repo.get_by_id(v2_id)
    assert v1_rec["status"] == "SUPERSEDED"
    assert v2_rec["status"] == "ACTIVE"
    assert v2_rec["version"] == 2
    assert v2_rec["parent_evidence_id"] == ev_id

    conn.close()
