#!/usr/bin/env python3
"""
CLI Administrator & User Management Utility
FinAuditPro - Autonomous Setup & Administration

Usage:
    # 1. Create a brand new Administrator (Refuses collisions by default):
    python scripts/create_admin.py --username auditadmin --password StrongPass123! --email admin@firm.com --name "Senior CA"

    # 2. Explicit Account Recovery / Password Reset:
    python scripts/create_admin.py --reset-password --username auditadmin --password NewStrongPass123!

    # 3. Interactive prompt:
    python scripts/create_admin.py
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
from backend.app.auth import hash_password, validate_password_strength
from backend.app.utils.audit_logger import log_audit_event


def create_admin_user(
    username: str,
    password: str,
    email: str,
    full_name: str,
    designation: str = "Managing Partner (FCA)",
    phone: str = ""
) -> int:
    """
    Creates a new Master Administrator.
    Refuses existing username or email collisions by default to prevent unauthorized privilege elevation.
    """
    validate_password_strength(password)
    init_db()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.now().isoformat()

        # WF-004: Check for username and email collisions independently
        existing_username = cursor.execute(
            "SELECT id, username, email, role FROM users WHERE LOWER(username) = LOWER(?)",
            (username.strip(),)
        ).fetchone()

        existing_email = cursor.execute(
            "SELECT id, username, email, role FROM users WHERE LOWER(email) = LOWER(?)",
            (email.strip(),)
        ).fetchone()

        if existing_username and existing_email and existing_username["id"] != existing_email["id"]:
            raise ValueError(
                f"Conflict detected: Username '{username}' belongs to account #{existing_username['id']} "
                f"while email '{email}' belongs to a different account #{existing_email['id']}. "
                "Account creation refused to prevent cross-account corruption or privilege escalation."
            )
        if existing_username:
            raise ValueError(
                f"An account with username '{username}' already exists (ID #{existing_username['id']}). "
                "Account creation refused to prevent privilege escalation or accidental credential overwrite. "
                "Use the '--reset-password' flag with an unambiguous identifier to authorize account recovery."
            )
        if existing_email:
            raise ValueError(
                f"An account with email '{email}' already exists (ID #{existing_email['id']}). "
                "Account creation refused to prevent privilege escalation or accidental credential overwrite. "
                "Use the '--reset-password' flag with an unambiguous identifier to authorize account recovery."
            )

        pwd_hash = hash_password(password)

        cursor.execute("""
            INSERT INTO users (
                username, email, full_name, role, designation, status,
                password_hash, is_active, phone, created_at, token_version
            ) VALUES (?, ?, ?, 'Admin', ?, 'ACTIVE', ?, 1, ?, ?, 1)
        """, (username.strip(), email.strip(), full_name.strip(), designation, pwd_hash, phone, now_str))
        uid = cursor.lastrowid

        # Mark wizard setup complete in settings so system is immediately unlocked
        cursor.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('initial_admin_created', '1', ?)", (now_str,))
        cursor.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('is_initial_setup_completed', '1', ?)", (now_str,))

        log_audit_event(
            conn,
            action="CREATE_ADMIN",
            module="AUTH",
            record_id=uid,
            details=f"Master Administrator account '{username}' configured via CLI initialization utility",
            user={"id": uid, "username": username}
        )
        conn.commit()
        print(f"[SUCCESS] Master Administrator '{username}' created successfully. (User ID #{uid})")
        return uid
    finally:
        conn.close()


def reset_admin_account(
    identifier: str,
    new_password: str,
    full_name: str = None,
    designation: str = None,
    phone: str = None
) -> int:
    """
    Explicitly resets an existing user's password and elevates to Admin role if needed.
    Invalidates all prior JWT sessions by incrementing token_version.
    """
    validate_password_strength(new_password)
    init_db()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.now().isoformat()

        # WF-004: Strict lookup by email if contains '@', else by username
        clean_id = identifier.strip()
        if "@" in clean_id:
            matches = cursor.execute(
                "SELECT id, username, email, role FROM users WHERE LOWER(email) = LOWER(?)",
                (clean_id,)
            ).fetchall()
        else:
            matches = cursor.execute(
                "SELECT id, username, email, role FROM users WHERE LOWER(username) = LOWER(?)",
                (clean_id,)
            ).fetchall()

        if not matches:
            raise ValueError(f"No existing user account matching '{identifier}' was found to reset.")
        if len(matches) > 1:
            raise ValueError(f"Ambiguous identifier '{identifier}': multiple accounts matched ({[m['id'] for m in matches]}). Specify unique username.")

        existing = matches[0]

        uid = existing["id"]
        pwd_hash = hash_password(new_password)

        cursor.execute("""
            UPDATE users 
            SET password_hash = ?, role = 'Admin', status = 'ACTIVE', is_active = 1,
                token_version = COALESCE(token_version, 1) + 1
            WHERE id = ?
        """, (pwd_hash, uid))

        if full_name:
            cursor.execute("UPDATE users SET full_name = ? WHERE id = ?", (full_name.strip(), uid))
        if designation:
            cursor.execute("UPDATE users SET designation = ? WHERE id = ?", (designation.strip(), uid))
        if phone:
            cursor.execute("UPDATE users SET phone = ? WHERE id = ?", (phone.strip(), uid))

        cursor.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('initial_admin_created', '1', ?)", (now_str,))
        cursor.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('is_initial_setup_completed', '1', ?)", (now_str,))

        log_audit_event(
            conn,
            action="ADMIN_ACCOUNT_RECOVERY",
            module="AUTH",
            record_id=uid,
            details=f"User '{existing['username']}' account explicitly reset/recovered via CLI utility",
            user={"id": uid, "username": existing["username"]}
        )
        conn.commit()
        print(f"[SUCCESS] Administrator account '{existing['username']}' successfully reset and session tokens invalidated. (User ID #{uid})")
        return uid
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Create or recover a FinAuditPro Administrator account.")
    parser.add_argument("--username", "-u", help="Username for the administrator")
    parser.add_argument("--password", "-p", help="Password for the administrator")
    parser.add_argument("--email", "-e", help="Email address")
    parser.add_argument("--name", "-n", help="Full Name (e.g. CA Rajeshwar Sharma)")
    parser.add_argument("--designation", "-d", default="Managing Partner (FCA)", help="Designation")
    parser.add_argument("--phone", help="Phone number (optional)", default="")
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Explicitly authorize password reset / account recovery for an existing account"
    )

    args = parser.parse_args()

    username = args.username
    password = args.password
    email = args.email
    full_name = args.name

    if not username:
        prompt_label = "Enter Admin Username to Reset: " if args.reset_password else "Enter Admin Username [admin]: "
        username = input(prompt_label).strip()
        if not username and not args.reset_password:
            username = "admin"

    if not args.reset_password:
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

    try:
        validate_password_strength(password)
    except ValueError as val_err:
        print(f"[ERROR] Invalid password: {val_err}")
        sys.exit(1)

    try:
        if args.reset_password:
            reset_admin_account(
                identifier=username or email,
                new_password=password,
                full_name=full_name,
                designation=args.designation,
                phone=args.phone
            )
        else:
            create_admin_user(
                username=username,
                password=password,
                email=email,
                full_name=full_name,
                designation=args.designation,
                phone=args.phone
            )
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
