#!/usr/bin/env python3
"""
CLI Administrator & User Management Utility
FinAuditPro - Autonomous Setup & Administration

Usage:
    python scripts/create_admin.py --username admin --password MyPassword123! --email admin@firm.com --name "Senior CA"
    python scripts/create_admin.py  (interactive prompt)
"""
import sys
import os
import argparse
import getpass
from datetime import datetime

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.database import get_db_connection, init_db
from backend.app.auth import hash_password
from backend.app.utils.audit_logger import log_audit_event


def create_admin_user(username: str, password: str, email: str, full_name: str, designation: str = "Managing Partner (FCA)", phone: str = ""):
    init_db()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.now().isoformat()

        # Check if user already exists
        existing = cursor.execute("SELECT id, role FROM users WHERE username = ? OR email = ?", (username, email)).fetchone()
        pwd_hash = hash_password(password)

        if existing:
            # Update user to Admin role with new password
            cursor.execute("""
                UPDATE users 
                SET password_hash = ?, full_name = ?, role = 'Admin', designation = ?, 
                    status = 'ACTIVE', is_active = 1, phone = ?,
                    token_version = COALESCE(token_version, 1) + 1
                WHERE id = ?
            """, (pwd_hash, full_name, designation, phone, existing["id"]))
            uid = existing["id"]
            action = "UPDATE_ADMIN"
            msg = f"User '{username}' updated to Administrator status."
        else:
            cursor.execute("""
                INSERT INTO users (
                    username, email, full_name, role, designation, status,
                    password_hash, is_active, phone, created_at
                ) VALUES (?, ?, ?, 'Admin', ?, 'ACTIVE', ?, 1, ?, ?)
            """, (username, email, full_name, designation, pwd_hash, phone, now_str))
            uid = cursor.lastrowid
            action = "CREATE_ADMIN"
            msg = f"Master Administrator '{username}' created successfully."

        # Mark wizard setup complete in settings so system is immediately unlocked
        cursor.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('initial_admin_created', '1', ?)", (now_str,))
        cursor.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('is_initial_setup_completed', '1', ?)", (now_str,))

        log_audit_event(
            conn,
            action=action,
            module="AUTH",
            record_id=uid,
            details=f"Administrator account '{username}' configured via CLI initialization utility",
            user={"id": uid, "username": username}
        )
        conn.commit()
        print(f"[SUCCESS] {msg} (User ID #{uid})")
        return uid
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Create or update a FinAuditPro Administrator account.")
    parser.add_argument("--username", "-u", help="Username for the administrator")
    parser.add_argument("--password", "-p", help="Password for the administrator")
    parser.add_argument("--email", "-e", help="Email address")
    parser.add_argument("--name", "-n", help="Full Name (e.g. CA Rajeshwar Sharma)")
    parser.add_argument("--designation", "-d", default="Managing Partner (FCA)", help="Designation")
    parser.add_argument("--phone", help="Phone number (optional)", default="")

    args = parser.parse_args()

    username = args.username
    password = args.password
    email = args.email
    full_name = args.name

    if not username:
        username = input("Enter Admin Username [admin]: ").strip() or "admin"
    if not email:
        email = input(f"Enter Admin Email [{username}@auditfirm.local]: ").strip() or f"{username}@auditfirm.local"
    if not full_name:
        full_name = input("Enter Full Name [Lead Auditor FCA]: ").strip() or "Lead Auditor FCA"
    if not password:
        password = getpass.getpass("Enter Admin Password (min 8 characters): ")
        confirm_pwd = getpass.getpass("Confirm Admin Password: ")
        if password != confirm_pwd:
            print("[ERROR] Passwords do not match.")
            sys.exit(1)

    if len(password) < 8:
        print("[ERROR] Password must be at least 8 characters long.")
        sys.exit(1)

    create_admin_user(
        username=username,
        password=password,
        email=email,
        full_name=full_name,
        designation=args.designation,
        phone=args.phone
    )


if __name__ == "__main__":
    main()
