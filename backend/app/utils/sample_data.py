"""
FinAuditPro - Sample & Test Database Initializer
Initializes default active users and seeds the two independent test companies:
1. Aryan Fintech Pvt. Ltd. (ARYAN)
2. Hitansh Fintech Pvt. Ltd. (HITANSH)
"""

import os
import shutil
import pandas as pd
from datetime import datetime
from backend.app.database import get_db_connection, init_db
from backend.app.auth import hash_password
from test_data.companies import ARYAN_COMPANY, HITANSH_COMPANY
from test_data.seed import seed_company_engagement

def seed_sample_database():
    """Initializes and seeds database with clean users and the 2 official test companies."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Seed Default Staff & Partner Users
    now_str = datetime.now().isoformat()
    admin_hash = hash_password("admin123")
    auditor_hash = hash_password("audit123")
    staff_hash = hash_password("staff123")

    cursor.execute("""
    INSERT OR REPLACE INTO users (id, username, email, full_name, role, password_hash, is_active, phone, last_login, created_at)
    VALUES (1, 'admin', 'partner@finauditpro.in', 'Aaliya Kherani (Engagement Partner, FCA)', 'Admin', ?, 1, '+91 98200 11223', ?, ?)
    """, (admin_hash, now_str, now_str))

    cursor.execute("""
    INSERT OR REPLACE INTO users (id, username, email, full_name, role, password_hash, is_active, phone, last_login, created_at)
    VALUES (2, 'auditor', 'senior@finauditpro.in', 'Rohan Mehta (Senior Audit Manager, ACA)', 'Auditor', ?, 1, '+91 98200 22334', ?, ?)
    """, (auditor_hash, now_str, now_str))

    cursor.execute("""
    INSERT OR REPLACE INTO users (id, username, email, full_name, role, password_hash, is_active, phone, last_login, created_at)
    VALUES (3, 'staff', 'assistant@finauditpro.in', 'Pooja Verma (Audit Assistant)', 'Audit Staff', ?, 1, '+91 98200 33445', ?, ?)
    """, (staff_hash, now_str, now_str))

    # 2. Seed Official Companies (Aryan Fintech & Hitansh Fintech)
    seed_company_engagement(conn, ARYAN_COMPANY)
    seed_company_engagement(conn, HITANSH_COMPANY)

    conn.commit()
    conn.close()

    export_sample_files()

def export_sample_files():
    """Copies generated test CSV files to sample_files folder for user upload convenience."""
    sample_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sample_files")
    os.makedirs(sample_dir, exist_ok=True)
    test_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "test_data")

    for co_dir, prefix in [("aryan_fintech", "aryan"), ("hitansh_fintech", "hitansh")]:
        src_path = os.path.join(test_data_dir, co_dir)
        if os.path.exists(src_path):
            for fname in os.listdir(src_path):
                if fname.endswith(".csv"):
                    dest_name = f"{prefix}_{fname}"
                    shutil.copy2(os.path.join(src_path, fname), os.path.join(sample_dir, dest_name))

if __name__ == "__main__":
    seed_sample_database()
