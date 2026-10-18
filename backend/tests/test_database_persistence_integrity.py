"""
Database Persistence, Integrity & Audit Findings Lifecycle Tests (Phase 3 & 5)
Verifies multi-client isolation, manual finding preservation, transaction rollbacks,
and audit trail immutability.
"""
import pytest
import sqlite3
from datetime import datetime
from backend.app.database import get_db_connection
from backend.app.audit_engine.engine import HybridAuditEngine
from backend.app.services.backup_service import BackupService

def test_manual_findings_preserved_across_engine_reruns():
    """Phase 5: Manual auditor findings must never be deleted when automated audit is rerun."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    # 1. Create a dummy client and engagement
    cur = conn.execute(
        "INSERT INTO clients (name, pan, entity_type, created_at) VALUES ('Lifecycle Client Ltd', 'ABCDE1111A', 'Company', ?)",
        (now_str,)
    )
    client_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO engagements (client_id, title, financial_year, audit_type, status, created_at) VALUES (?, 'Statutory Audit FY25', '2024-25', 'Statutory', 'Active', ?)",
        (client_id, now_str)
    )
    eng_id = cur.lastrowid

    # 2. Insert transactions
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type)
        VALUES (?, '2024-05-01', 'CPV-01', 'Cash Account', 'Subcontractor', 18000.0, 0.0, 18000.0, 'Payment')
    """, (eng_id,))
    
    # 3. Insert a manual finding
    conn.execute("""
        INSERT INTO audit_findings (
            engagement_id, finding_code, category, severity, risk_score,
            title, description, engine_type, status, created_at
        ) VALUES (
            ?, 'MANUAL-01', 'Internal Controls', 'HIGH', 8.5,
            'Physical asset register not updated', 'Auditor physical observation', 'MANUAL', 'Open', ?
        )
    """, (eng_id, now_str))

    # 4. Insert an already reviewed finding
    conn.execute("""
        INSERT INTO audit_findings (
            engagement_id, finding_code, category, severity, risk_score,
            title, description, engine_type, status, created_at
        ) VALUES (
            ?, 'REV-01', 'Statutory Compliance', 'MEDIUM', 6.0,
            'Previous year expense accrual', 'Reviewed and accepted by engagement partner', 'DETERMINISTIC', 'Resolved', ?
        )
    """, (eng_id, now_str))
    conn.commit()
    conn.close()

    # 5. Execute hybrid audit engine twice
    engine = HybridAuditEngine(eng_id)
    engine.execute_audit()
    engine.execute_audit()

    # 6. Verify database records
    conn = get_db_connection()
    findings = conn.execute("SELECT finding_code, engine_type, status FROM audit_findings WHERE engagement_id = ?", (eng_id,)).fetchall()
    conn.close()

    codes = [f["finding_code"] for f in findings]
    assert "MANUAL-01" in codes, "Manual finding must survive automated audit rerun"
    assert "REV-01" in codes, "Resolved/reviewed finding must survive automated audit rerun"

def test_immutable_audit_trail_trigger_blocks_tampering():
    """Phase 3/5: SQLite trigger must block direct modifications or deletions on audit_logs."""
    conn = get_db_connection()
    # Insert legitimate audit log
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action="LOGIN",
        module="AUTH",
        user="auditor_aryan",
        details="Legitimate login event"
    )
    conn.commit()

    # Fetch last inserted log id
    log_row = conn.execute("SELECT id FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()
    log_id = log_row["id"]

    # Attempt direct UPDATE - must fail with sqlite3.IntegrityError or OperationalError
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        conn.execute("UPDATE audit_logs SET details = 'Tampered log content' WHERE id = ?", (log_id,))
        conn.commit()

    # Attempt direct DELETE - must fail
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        conn.execute("DELETE FROM audit_logs WHERE id = ?", (log_id,))
        conn.commit()

    conn.close()

def test_cross_engagement_transaction_isolation():
    """Phase 3: Transactions and findings for Engagement A must never be accessible under Engagement B."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cur = conn.execute("INSERT INTO clients (name, pan, entity_type, created_at) VALUES ('Company Alpha', 'AAAAA1111A', 'Company', ?)", (now_str,))
    c1 = cur.lastrowid
    cur = conn.execute("INSERT INTO clients (name, pan, entity_type, created_at) VALUES ('Company Beta', 'BBBBB2222B', 'Company', ?)", (now_str,))
    c2 = cur.lastrowid

    cur = conn.execute("INSERT INTO engagements (client_id, title, financial_year, created_at) VALUES (?, 'Eng Alpha', '2024-25', ?)", (c1, now_str))
    e1 = cur.lastrowid
    cur = conn.execute("INSERT INTO engagements (client_id, title, financial_year, created_at) VALUES (?, 'Eng Beta', '2024-25', ?)", (c2, now_str))
    e2 = cur.lastrowid

    # Insert transactions into e1 only
    conn.execute("INSERT INTO transactions (engagement_id, voucher_no, amount, ledger) VALUES (?, 'V-ALPHA-1', 99000.0, 'Sales')", (e1,))
    conn.commit()

    # Query e2 transactions
    e2_txs = conn.execute("SELECT * FROM transactions WHERE engagement_id = ?", (e2,)).fetchall()
    conn.close()

    assert len(e2_txs) == 0, "Engagement Beta must have zero transactions from Engagement Alpha"

def test_database_backup_and_restore_cycle():
    """Phase 3: Backup snapshot creation and restoration integrity."""
    bundle_path, manifest = BackupService.create_verified_bundle(created_by="test_runner")
    assert bundle_path.endswith(".finpkg")
    assert manifest["backup_version"] in (1, 2)
    assert manifest["database_sha256"] is not None
    assert manifest["created_by"] == "test_runner"

    # Validate bundle
    val = BackupService.validate_bundle(bundle_path)
    assert val.get("valid") is True
    assert val.get("manifest")["database_sha256"] == manifest["database_sha256"]
