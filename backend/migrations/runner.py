import glob
import hashlib
import os
import re
import sqlite3
import sys
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

MIGRATIONS_DIR = os.path.dirname(os.path.abspath(__file__))
MIGRATION_PATTERN = re.compile(r"^(?P<version>\d{3})_(?P<name>[A-Za-z0-9_]+)\.sql$")


def _version_key(version: str) -> int:
    try:
        return int(version)
    except (TypeError, ValueError):
        return -1


def _iter_sql_statements(content: str) -> Generator[str, None, None]:
    buffer = ""
    for line in content.splitlines():
        buffer += line + "\n"
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                yield statement
            buffer = ""
    if buffer.strip():
        yield buffer.strip()


def _index_exists(conn: sqlite3.Connection, index_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ? LIMIT 1",
        (index_name,),
    ).fetchone()
    return row is not None


def _migration_statements_for(conn: sqlite3.Connection, file_name: str, content: str) -> List[str]:
    statements = list(_iter_sql_statements(content))
    if file_name != "004_user_onboarding_and_firm_profile.sql":
        return statements

    existing_columns = {
        row[1] if isinstance(row, tuple) else row["name"]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    filtered: List[str] = []
    for statement in statements:
        lowered = statement.lower()
        if "alter table users" in lowered and "add column" in lowered:
            match = re.search(r"add\s+column\s+([a-zA-Z_][a-zA-Z0-9_]*)", lowered)
            if match and match.group(1) in existing_columns:
                continue
        if "create index" in lowered and "if not exists" in lowered:
            match = re.search(r"create\s+index\s+if\s+not\s+exists\s+([a-zA-Z_][a-zA-Z0-9_]*)", lowered)
            if match and _index_exists(conn, match.group(1)):
                continue
        filtered.append(statement)
    return filtered


def get_migration_files() -> List[str]:
    """Returns a sorted list of versioned migration files while excluding teardown scripts."""
    files: List[str] = []
    seen_versions = set()
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")), key=lambda f: os.path.basename(f)):
        file_name = os.path.basename(path)
        if file_name == "drop_all.sql":
            continue
        match = MIGRATION_PATTERN.match(file_name)
        if match is None:
            continue
        version = match.group("version")
        if version in seen_versions:
            raise ValueError(f"Duplicate migration version '{version}' detected for {file_name}")
        seen_versions.add(version)
        files.append(path)
    return files


def init_migration_table(conn: sqlite3.Connection):
    """Ensures schema_migrations table exists."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            description TEXT,
            applied_at TEXT NOT NULL,
            checksum TEXT NOT NULL
        )
        """
    )


def compute_checksum(content: str) -> str:
    """Computes SHA-256 checksum of SQL migration content."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def apply_migrations(conn: Optional[sqlite3.Connection] = None, db_path: Optional[str] = None) -> List[str]:
    """Applies all unapplied migrations in ascending order and records each one atomically."""
    close_at_end = False
    if conn is None:
        from backend.app.database import get_db_connection

        conn = get_db_connection()
        close_at_end = True

    applied_now: List[str] = []
    try:
        init_migration_table(conn)

        migration_files = get_migration_files()
        migration_by_version = {}
        for file_path in migration_files:
            version = os.path.basename(file_path).split("_")[0]
            migration_by_version[version] = file_path

        rows = conn.execute(
            "SELECT version, description, checksum FROM schema_migrations ORDER BY version ASC"
        ).fetchall()
        applied_map = {
            (row[0] if isinstance(row, tuple) else row["version"]):
            (row[2] if isinstance(row, tuple) else row["checksum"])
            for row in rows
        }

        for file_path in migration_files:
            file_name = os.path.basename(file_path)
            version = file_name.split("_")[0]

            with open(file_path, "r", encoding="utf-8") as fh:
                content = fh.read()
            checksum = compute_checksum(content)

            if version in applied_map:
                if applied_map[version] != checksum:
                    raise ValueError(
                        f"Checksum mismatch for applied migration {version} ({file_name}). "
                        "The migration file has changed after it was recorded."
                    )
                continue

            statements = _migration_statements_for(conn, file_name, content)

            try:
                conn.execute("BEGIN IMMEDIATE")
                for statement in statements:
                    if not statement.strip():
                        continue
                    conn.execute(statement)

                now_str = datetime.now().isoformat()
                conn.execute(
                    "INSERT INTO schema_migrations (version, description, applied_at, checksum) VALUES (?, ?, ?, ?)",
                    (version, file_name, now_str, checksum),
                )
                conn.commit()
                applied_now.append(version)
            except Exception as exc:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                print(f"[migration] {file_name} failed: {exc}", file=sys.stderr)
                raise RuntimeError(f"Migration {file_name} failed: {exc}") from exc

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
        migration_files = get_migration_files()
        version_to_file = {
            os.path.basename(file_path).split("_")[0]: file_path for file_path in migration_files
        }

        applied_rows = conn.execute(
            "SELECT version, description, applied_at, checksum FROM schema_migrations ORDER BY version ASC"
        ).fetchall()
        applied = []
        for row in applied_rows:
            if isinstance(row, sqlite3.Row):
                applied.append(dict(row))
            else:
                applied.append({
                    "version": row[0],
                    "description": row[1],
                    "applied_at": row[2],
                    "checksum": row[3],
                })
        applied_versions = set()
        for row in applied_rows:
            version = row[0] if isinstance(row, tuple) else row["version"]
            applied_versions.add(version)
            file_path = version_to_file.get(version)
            if file_path is None:
                continue
            with open(file_path, "r", encoding="utf-8") as fh:
                expected = compute_checksum(fh.read())
            checksum = row[3] if isinstance(row, tuple) else row["checksum"]
            if checksum != expected:
                raise ValueError(
                    f"Migration history mismatch for version {version}: recorded checksum differs from actual migration file."
                )

        pending = [
            os.path.basename(file_path).split("_")[0]
            for file_path in migration_files
            if os.path.basename(file_path).split("_")[0] not in applied_versions
        ]

        current_version = "000"
        valid_applied = sorted(applied_versions & set(version_to_file), key=_version_key)
        if valid_applied:
            current_version = str(valid_applied[-1])

        return {
            "current_version": current_version,
            "total_migrations": len(migration_files),
            "applied_count": len(applied),
            "pending_count": len(pending),
            "applied": applied,
            "pending": pending,
            "is_up_to_date": len(pending) == 0,
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
