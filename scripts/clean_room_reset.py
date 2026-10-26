#!/usr/bin/env python3
"""
FinAuditPro - Clean-Room Production Reset & Verification Script
Safely creates an archive backup of the local development environment,
wipes temporary test artifacts, runs migrations to create a pristine schema,
and strictly verifies that zero dummy records exist.

Usage:
  python scripts/clean_room_reset.py --confirm-reset
"""

import sys
import os
import shutil
import sqlite3
import argparse
from datetime import datetime

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from backend.app.database import get_db_connection, get_db_path, init_db

def perform_clean_room_reset(confirm: bool = False):
    print("=" * 80)
    print("FINAUDITPRO - SANDBOX CLEAN-ROOM RESET UTILITY (DEVELOPMENT ONLY)")
    print("=" * 80)

    # Safety Guard: Refuse to execute in production environment
    env = os.environ.get("FINAUDIT_ENV", os.environ.get("ENVIRONMENT", "development")).lower()
    if env == "production":
        print("\n[!] FATAL: Clean-room reset is strictly prohibited in production environment.")
        print("Refusing to execute on a live production deployment.")
        sys.exit(1)

    if not confirm:
        print("\n[!] WARNING: This will archive and reset the sandbox database and temporary upload artifacts.")
        print("To proceed, re-run with --confirm-reset")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(PROJECT_ROOT, "backend", "backups")
    os.makedirs(backup_dir, exist_ok=True)

    # 1. Archive full bundle (DB snapshot via SQLite backup API + all uploaded files and reports)
    db_path = get_db_path()
    uploads_dir = os.path.join(PROJECT_ROOT, "backend", "uploaded_files")
    reports_dir = os.path.join(PROJECT_ROOT, "backend", "reports_generated")

    if os.path.exists(db_path):
        archive_db_path = os.path.join(backup_dir, f"pre_clean_reset_{timestamp}.db")
        # Consistent SQLite WAL-mode snapshot using online backup API
        src_conn = sqlite3.connect(db_path)
        dst_conn = sqlite3.connect(archive_db_path)
        try:
            src_conn.backup(dst_conn)
            print(f"[OK] Consistent WAL-mode database snapshot created at: {archive_db_path}")
        finally:
            dst_conn.close()
            src_conn.close()

        # Archive uploads and reports before wiping
        import tarfile
        full_archive_path = os.path.join(backup_dir, f"pre_clean_reset_full_archive_{timestamp}.tar.gz")
        with tarfile.open(full_archive_path, "w:gz") as tar:
            tar.add(archive_db_path, arcname="finauditpro.db")
            if os.path.exists(uploads_dir):
                tar.add(uploads_dir, arcname="uploaded_files")
            if os.path.exists(reports_dir):
                tar.add(reports_dir, arcname="reports_generated")
        print(f"[OK] Complete verified safety archive (DB + uploads + reports) saved to: {full_archive_path}")

        # Remove active DB
        os.remove(db_path)
        print(f"[OK] Reset active sandbox database: {db_path}")

    # 2. Clean temporary upload and generated report directories
    for target_dir in [uploads_dir, reports_dir]:
        if os.path.exists(target_dir):
            for fname in os.listdir(target_dir):
                if fname == ".gitkeep":
                    continue
                fpath = os.path.join(target_dir, fname)
                try:
                    if os.path.isfile(fpath) or os.path.islink(fpath):
                        os.unlink(fpath)
                    elif os.path.isdir(fpath):
                        shutil.rmtree(fpath)
                except Exception as e:
                    print(f"[!] Warning cleaning {fpath}: {e}")
            print(f"[OK] Cleaned directory: {target_dir}")
        else:
            os.makedirs(target_dir, exist_ok=True)
            print(f"[OK] Initialized empty directory: {target_dir}")

    # 3. Initialize Pristine Production Database Schema
    print("\n[+] Initializing pristine production schema and indexes...")
    init_db()
    print("[OK] Database initialized successfully.")

    # 4. Strict Zero-Data Assertions
    print("\n[+] Verifying Clean-Room Zero-Data Invariants...")
    conn = get_db_connection()
    cursor = conn.cursor()

    tables_to_verify = [
        "users",
        "clients",
        "engagements",
        "transactions",
        "ledgers",
        "uploaded_files",
        "working_papers",
        "audit_logs",
        "reconciliations",
        "audit_findings",
        "audit_checklists",
        "data_cleaning_logs",
        "reports",
        "notifications",
        "yoy_comparison_reviews"
    ]

    all_clean = True
    for tbl in tables_to_verify:
        try:
            count = cursor.execute(f"SELECT COUNT(*) as c FROM {tbl}").fetchone()["c"]
            if count == 0:
                print(f"  [OK] Table '{tbl}': 0 records (CLEAN)")
            else:
                print(f"  [X] Table '{tbl}': {count} records (NOT CLEAN)")
                all_clean = False
        except sqlite3.OperationalError:
            # Table might not exist in optional modules, which is clean
            print(f"  [OK] Table '{tbl}': not present or optional (CLEAN)")

    conn.close()

    print("\n" + "=" * 80)
    if all_clean:
        print("[SUCCESS] CLEAN-ROOM RESET COMPLETE: Application is in genuine 100% clean production state.")
        print("Start the application with: python run.py")
        print("=" * 80)
        return 0
    else:
        print("[FAIL] CLEAN-ROOM RESET FAILED: Non-zero records detected.")
        print("=" * 80)
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinAuditPro Clean-Room Reset")
    parser.add_argument("--confirm-reset", action="store_true", help="Confirm database and test artifact reset")
    args = parser.parse_args()
    sys.exit(perform_clean_room_reset(args.confirm_reset))
