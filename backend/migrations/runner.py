import os
import glob
import hashlib
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

MIGRATIONS_DIR = os.path.dirname(os.path.abspath(__file__))

def get_migration_files() -> List[str]:
    """Returns sorted list of .sql migration file paths."""
    pattern = os.path.join(MIGRATIONS_DIR, "*.sql")
    files = glob.glob(pattern)
    return sorted(files, key=lambda f: os.path.basename(f))

def init_migration_table(conn: sqlite3.Connection):
    """Ensures schema_migrations table exists."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version TEXT PRIMARY KEY,
        description TEXT,
        applied_at TEXT NOT NULL,
        checksum TEXT NOT NULL
    )
    """)

def compute_checksum(content: str) -> str:
    """Computes SHA-256 checksum of SQL migration content."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

def apply_migrations(conn: Optional[sqlite3.Connection] = None, db_path: Optional[str] = None) -> List[str]:
    """
    Applies all unapplied migrations in ascending order.
    Returns list of newly applied migration versions.
    """
    close_at_end = False
    if conn is None:
        from backend.app.database import get_db_connection
        conn = get_db_connection()
        close_at_end = True

    applied_now: List[str] = []
    try:
        init_migration_table(conn)
        
        # Query existing applied migrations
        rows = conn.execute("SELECT version, checksum FROM schema_migrations ORDER BY version ASC").fetchall()
        applied_map = {r["version"]: r["checksum"] for r in rows}
        
        migration_files = get_migration_files()
        
        for file_path in migration_files:
            file_name = os.path.basename(file_path)
            version = file_name.split("_")[0]
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            checksum = compute_checksum(content)
            
            if version in applied_map:
                # Already applied, verify checksum consistency
                continue
            
            # Execute migration in a transaction
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.executescript(content)
                now_str = datetime.now().isoformat()
                description = file_name
                conn.execute(
                    "INSERT INTO schema_migrations (version, description, applied_at, checksum) VALUES (?, ?, ?, ?)",
                    (version, description, now_str, checksum)
                )
                conn.execute("COMMIT")
                applied_now.append(version)
            except Exception as e:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise RuntimeError(f"Migration {file_name} failed: {str(e)}") from e
                
        return applied_now
    finally:
        if close_at_end:
            conn.close()

def get_migration_status(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Returns detailed status of database migrations."""
    close_at_end = False
    if conn is None:
        from backend.app.database import get_db_connection
        conn = get_db_connection()
        close_at_end = True

    try:
        init_migration_table(conn)
        applied_rows = conn.execute("SELECT version, description, applied_at, checksum FROM schema_migrations ORDER BY version ASC").fetchall()
        applied = [dict(r) for r in applied_rows]
        applied_versions = {r["version"] for r in applied}
        
        all_files = get_migration_files()
        all_versions = [os.path.basename(f).split("_")[0] for f in all_files]
        pending = [v for v in all_versions if v not in applied_versions]
        
        current_version = applied[-1]["version"] if applied else "000"
        
        return {
            "current_version": current_version,
            "total_migrations": len(all_files),
            "applied_count": len(applied),
            "pending_count": len(pending),
            "applied": applied,
            "pending": pending,
            "is_up_to_date": len(pending) == 0
        }
    finally:
        if close_at_end:
            conn.close()

if __name__ == "__main__":
    from backend.app.database import get_db_connection
    conn = get_db_connection()
    applied = apply_migrations(conn)
    status = get_migration_status(conn)
    conn.close()
    print("Migrations applied:", applied)
    print("Current status:", status)
