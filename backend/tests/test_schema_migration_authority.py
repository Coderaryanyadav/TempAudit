import os
import tempfile
import sqlite3
import pytest

from backend.app.database import init_db, get_db_connection
from backend.migrations.runner import get_migration_status, get_migration_files


def test_schema_initialization_from_empty_database():
    """
    Verifies that initializing from a clean, empty database uses the authoritative
    versioned migrations to apply all migrations and create all required tables.
    """
    old_db_path = os.environ.get("FINAUDIT_DB_PATH")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        os.environ["FINAUDIT_DB_PATH"] = db_path

        # 1. First initialization on clean DB
        init_db()

        conn = get_db_connection()
        try:
            # Verify migration status
            status = get_migration_status(conn)
            migration_files = get_migration_files()
            assert status["pending_count"] == 0, "No pending migrations should remain after init_db"
            assert status["applied_count"] == len(migration_files), "All migration versions must be recorded"

            # Verify core domain tables exist
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            expected_tables = {
                "users", "clients", "engagements", "uploaded_files", "transactions",
                "audit_logs", "audit_findings", "app_settings", "working_papers",
                "reconciliations", "reconciliation_items", "schema_migrations",
                "anomaly_reviews", "duplicate_group_reviews", "missing_sequence_reviews",
                "data_cleaning_logs", "rate_limits", "revoked_tokens"
            }
            assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

            # Verify rate limits index exists from migration 005
            indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
            assert "idx_rate_limits_key_ts" in indexes

        finally:
            conn.close()

        # 2. Idempotence check: Calling init_db again must succeed without error or drift
        init_db()

        conn2 = get_db_connection()
        try:
            status2 = get_migration_status(conn2)
            assert status2["pending_count"] == 0
        finally:
            conn2.close()

    finally:
        if old_db_path is not None:
            os.environ["FINAUDIT_DB_PATH"] = old_db_path
        else:
            os.environ.pop("FINAUDIT_DB_PATH", None)
        from backend.app.database import refresh_db_path
        refresh_db_path()
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except OSError:
                pass
