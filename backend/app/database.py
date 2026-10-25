import sqlite3
import os
import json
from datetime import datetime


def get_db_path() -> str:
    return os.environ.get("FINAUDIT_DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "finauditpro.db"))


DB_PATH = get_db_path()


def refresh_db_path() -> str:
    global DB_PATH
    DB_PATH = get_db_path()
    return DB_PATH


def _ensure_db_dir():
    path = get_db_path()
    db_dir = os.path.dirname(os.path.abspath(path))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


def get_db_connection():
    _ensure_db_dir()
    path = refresh_db_path()
    conn = sqlite3.connect(path, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db():
    """
    Initializes database schema strictly and authoritatively via versioned migrations.
    Eliminates redundant parallel DDL and guarantees zero schema drift.
    """
    _ensure_db_dir()
    refresh_db_path()
    conn = get_db_connection()
    try:
        from backend.migrations.runner import apply_migrations

        apply_migrations(conn)

        required_tables = [
            "users",
            "clients",
            "engagements",
            "uploaded_files",
            "transactions",
            "audit_logs",
            "audit_findings",
            "app_settings",
            "working_papers",
            "reconciliations",
            "reconciliation_items",
            "schema_migrations",
            "ai_conversations",
            "ai_messages",
        ]
        missing_tables = []
        for table_name in required_tables:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            if row is None:
                missing_tables.append(table_name)
        if missing_tables:
            raise RuntimeError(
                "Database initialization incomplete; missing required tables: " + ", ".join(missing_tables)
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", get_db_path())
