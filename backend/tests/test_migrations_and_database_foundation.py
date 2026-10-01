import os
import sqlite3
import pytest
from backend.app.database import get_db_connection, init_db
from backend.migrations.runner import apply_migrations, get_migration_status, get_migration_files

def test_database_pragmas_and_wal():
    """Verify SQLite WAL mode, foreign keys, and busy timeout."""
    conn = get_db_connection()
    try:
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

        assert journal.upper() == "WAL"
        assert fk == 1
        assert timeout >= 5000
    finally:
        conn.close()

def test_migrations_tracking_and_idempotency(tmp_path):
    """Verify migrations runner creates schema_migrations, records versions, and is idempotent."""
    db_file = str(tmp_path / "test_mig.db")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row

    # 1. Apply migrations on fresh DB
    applied_first = apply_migrations(conn)
    assert len(applied_first) >= 3
    assert "001" in applied_first
    assert "002" in applied_first
    assert "003" in applied_first

    # 2. Check schema_migrations table
    rows = conn.execute("SELECT * FROM schema_migrations ORDER BY version ASC").fetchall()
    assert len(rows) == len(applied_first)
    for r in rows:
        assert r["checksum"] is not None
        assert len(r["checksum"]) == 64  # SHA-256

    # 3. Re-running migrations should be a safe no-op
    applied_second = apply_migrations(conn)
    assert len(applied_second) == 0

    # 4. Check status
    status = get_migration_status(conn)
    assert status["is_up_to_date"] is True
    assert status["pending_count"] == 0
    all_mig_files = get_migration_files()
    latest_version = os.path.basename(all_mig_files[-1]).split("_")[0]
    assert status["current_version"] == latest_version

    conn.close()

def test_foreign_key_constraints_enforced(tmp_path):
    """Verify foreign key constraint violations are rejected."""
    db_file = str(tmp_path / "test_fk.db")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)

    # Attempting to insert an engagement with non-existent client_id should fail
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""
        INSERT INTO engagements (client_id, title, financial_year, created_at)
        VALUES (99999, 'Orphan Engagement', '2025-26', '2026-10-01T00:00:00')
        """)

    conn.close()
