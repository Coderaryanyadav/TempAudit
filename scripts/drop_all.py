#!/usr/bin/env python3
"""
FinAuditPro - Database Drop & Reset Utility
Usage:
    python3 scripts/drop_all.py          # Drops all tables, triggers, and views
    python3 scripts/drop_all.py --init   # Drops all tables and recreates clean schema
"""

import os
import sys
import sqlite3

# Resolve paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from backend.app.database import get_db_path, get_db_connection, init_db
from backend.migrations.runner import apply_migrations

SQL_DROP_SCRIPT = os.path.join(REPO_ROOT, "backend", "migrations", "drop_all.sql")

def drop_all_objects(recreate_schema=False):
    db_path = get_db_path()
    print(f"[*] Targeting database: {db_path}")

    if not os.path.exists(db_path):
        print(f"[!] Database file does not exist at {db_path}. Creating fresh database.")
        if recreate_schema:
            init_db()
            print("[+] Clean schema initialized.")
        return

    with open(SQL_DROP_SCRIPT, "r", encoding="utf-8") as f:
        sql_content = f.read()

    conn = get_db_connection()
    try:
        conn.executescript(sql_content)
        conn.commit()
        print("[+] Successfully dropped all tables, triggers, and constraints.")

        # Verify that all user tables have been dropped
        remaining = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view', 'trigger') AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        
        if remaining:
            print(f"[!] Warning: {len(remaining)} objects remained: {[r[0] for r in remaining]}")
        else:
            print("[+] Database is 100% empty (Zero tables/triggers remain).")

    except Exception as e:
        print(f"[x] Error executing drop script: {e}")
        sys.exit(1)
    finally:
        conn.close()

    if recreate_schema:
        print("[*] Recreating pristine initial schema via migrations...")
        init_db()
        print("[+] Pristine schema created. FinAuditPro is ready for first-run launch.")

if __name__ == "__main__":
    recreate = "--init" in sys.argv or "--reset" in sys.argv
    drop_all_objects(recreate_schema=recreate)
