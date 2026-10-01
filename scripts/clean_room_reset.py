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

from backend.app.database import DB_PATH, init_db, get_db_connection

def perform_clean_room_reset(confirm: bool = False):
    print("=" * 80)
    print("🧹 FINAUDITPRO - PRODUCTION CLEAN-ROOM RESET UTILITY")
    print("=" * 80)

    if not confirm:
        print("\n⚠️  WARNING: This will reset the local database and remove temporary upload artifacts.")
        print("To proceed, re-run with --confirm-reset")
        sys.exit(1)

    # 1. Archive existing DB if present
    if os.path.exists(DB_PATH):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(PROJECT_ROOT, "backend", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        archive_path = os.path.join(backup_dir, f"pre_clean_reset_backup_{timestamp}.db")
        shutil.copy2(DB_PATH, archive_path)
        print(f"[✓] Archived existing database to: {archive_path}")

        # Remove active DB
        os.remove(DB_PATH)
        print(f"[✓] Removed existing database: {DB_PATH}")

    # 2. Clean temporary upload and generated report directories
    uploads_dir = os.path.join(PROJECT_ROOT, "backend", "uploaded_files")
    reports_dir = os.path.join(PROJECT_ROOT, "backend", "reports_generated")

    for target_dir in [uploads_dir, reports_dir]:
        if os.path.exists(target_dir):
            for fname in os.listdir(target_dir):
                fpath = os.path.join(target_dir, fname)
                try:
                    if os.path.isfile(fpath) or os.path.islink(fpath):
                        os.unlink(fpath)
                    elif os.path.isdir(fpath):
                        shutil.rmtree(fpath)
                except Exception as e:
                    print(f"[!] Warning cleaning {fpath}: {e}")
            print(f"[✓] Cleaned directory: {target_dir}")
        else:
            os.makedirs(target_dir, exist_ok=True)
            print(f"[✓] Initialized empty directory: {target_dir}")

    # 3. Initialize Pristine Production Database Schema
    print("\n[+] Initializing pristine production schema and indexes...")
    init_db()
    print("[✓] Database initialized successfully.")

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
                print(f"  [✓] Table '{tbl}': 0 records (CLEAN)")
            else:
                print(f"  [❌] Table '{tbl}': {count} records (NOT CLEAN)")
                all_clean = False
        except sqlite3.OperationalError:
            # Table might not exist in optional modules, which is clean
            print(f"  [✓] Table '{tbl}': not present or optional (CLEAN)")

    conn.close()

    print("\n" + "=" * 80)
    if all_clean:
        print("🎉 CLEAN-ROOM RESET COMPLETE: Application is in genuine 100% clean production state.")
        print("Start the application with: python run.py")
        print("=" * 80)
        return 0
    else:
        print("❌ CLEAN-ROOM RESET FAILED: Non-zero records detected.")
        print("=" * 80)
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinAuditPro Clean-Room Reset")
    parser.add_argument("--confirm-reset", action="store_true", help="Confirm database and test artifact reset")
    args = parser.parse_args()
    sys.exit(perform_clean_room_reset(args.confirm_reset))
