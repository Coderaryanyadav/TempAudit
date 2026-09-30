"""
Test Database Seeder
FinAuditPro - Test Data Architecture

*** TEST FIXTURES ONLY — NEVER USE THESE SEEDED CREDENTIALS IN PRODUCTION ENVIRONMENTS ***
"""

import os
import csv
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from backend.app.database import get_db_connection, init_db
from backend.app.auth import hash_password
from test_data.companies import ARYAN_COMPANY, HITANSH_COMPANY
from test_data.transactions import get_transactions_for_company, get_prior_year_transactions_for_company
from test_data.findings import get_test_findings_for_company
from test_data.working_papers import get_test_working_papers_for_company
from test_data.checklists import get_test_checklist_items

# Configurable passwords for test automation suites (TEST ONLY)
TEST_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")
TEST_AUDITOR_PASSWORD = os.environ.get("TEST_AUDITOR_PASSWORD", "audit123")
TEST_STAFF_PASSWORD = os.environ.get("TEST_STAFF_PASSWORD", "staff123")


def clean_currency(val) -> float:
    """Accurately normalizes monetary amounts to 2 decimal places using Decimal."""
    if val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        d = Decimal(str(val))
    else:
        s = str(val).replace(",", "").replace("₹", "").replace("$", "").strip()
        try:
            d = Decimal(s)
        except Exception:
            return 0.0
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def seed_test_users(conn):
    """Explicitly seeds isolated test users for testing/development (NEVER FOR PRODUCTION)."""
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    
    admin_hash = hash_password(TEST_ADMIN_PASSWORD)
    audit_hash = hash_password(TEST_AUDITOR_PASSWORD)
    staff_hash = hash_password(TEST_STAFF_PASSWORD)

    test_users = [
        (1, "admin", "admin@finauditpro.local", "System Administrator (FCA)", "Admin", admin_hash),
        (2, "auditor_aryan", "lead.aryan@finauditpro.in", "Auditor A (Aryan Lead Manager)", "Auditor", audit_hash),
        (3, "staff_aryan", "staff.aryan@finauditpro.in", "Staff A (Aryan Engagement Staff)", "Audit Staff", staff_hash),
        (4, "auditor_hitansh", "lead.hitansh@finauditpro.in", "Auditor B (Hitansh Lead Manager)", "Auditor", audit_hash),
        (5, "staff_hitansh", "staff.hitansh@finauditpro.in", "Staff B (Hitansh Engagement Staff)", "Audit Staff", staff_hash),
        (6, "auditor", "senior@finauditpro.in", "Rohan Mehta (General Auditor)", "Auditor", audit_hash),
        (7, "staff", "assistant@finauditpro.in", "Pooja Verma (General Staff)", "Audit Staff", staff_hash),
    ]

    for uid, uname, uemail, ufullname, urole, uhash in test_users:
        cursor.execute("""
            INSERT OR REPLACE INTO users (id, username, email, full_name, role, password_hash, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (uid, uname, uemail, ufullname, urole, uhash, now_str))

def seed_company_engagement(conn, company: dict) -> dict:
    now_str = datetime.now().isoformat()
    cursor = conn.cursor()

    is_aryan = company.get("short_code") == "ARYAN"
    lead_auditor_id = 2 if is_aryan else 4
    assigned_staff_id = 3 if is_aryan else 5

    # 1. Insert Client with synthetic flag notes
    client_notes = f"[SYNTHETIC TEST DATASET - NOT REAL CLIENT DATA] {company.get('nature_of_business', '')}"
    cursor.execute("""
        INSERT INTO clients (name, pan, gstin, entity_type, contact_person, email, phone, address, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        company["name"], company["pan"], company["gstin"], company["company_type"],
        company["primary_contact"], company["email"], company["phone"], company["address"],
        client_notes, now_str, now_str
    ))
    client_id = cursor.lastrowid

    # 2. Insert Prior Year Engagement (FY 2024-25)
    cursor.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, status, lead_auditor_id, assigned_staff_id, materiality_threshold, notes, created_at, updated_at)
        VALUES (?, ?, 'Statutory Audit', ?, ?, ?, 'Completed', ?, ?, 50000.0, ?, ?, ?)
    """, (
        client_id, f"Statutory Audit {company['prior_financial_year']}", company["prior_financial_year"],
        f"2024-04-01", f"2025-03-31", lead_auditor_id, assigned_staff_id,
        f"[TEST FIXTURE] Prior year audit records for {company['name']}", now_str, now_str
    ))
    py_eng_id = cursor.lastrowid

    # 3. Insert Current Year Engagement (FY 2025-26)
    cursor.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, status, lead_auditor_id, assigned_staff_id, materiality_threshold, notes, created_at, updated_at)
        VALUES (?, ?, 'Statutory Audit', ?, ?, ?, 'In Progress', ?, ?, 50000.0, ?, ?, ?)
    """, (
        client_id, f"Statutory & Tax Audit {company['financial_year']}", company["financial_year"],
        f"2025-04-01", f"2026-03-31", lead_auditor_id, assigned_staff_id,
        f"[TEST FIXTURE] Current year active audit for {company['name']}", now_str, now_str
    ))
    cy_eng_id = cursor.lastrowid

    # 4. Insert PY Transactions
    py_txs = get_prior_year_transactions_for_company(company["short_code"])
    for t in py_txs:
        cursor.execute("""
            INSERT INTO transactions (
                engagement_id, date, voucher_no, invoice_no, ledger, account_group,
                description, debit, credit, amount, party_name, gstin,
                tax_amount, reference_no
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            py_eng_id, t["date"], t["voucher_no"], t["invoice_no"], t["ledger"], t["account_group"],
            t["description"], clean_currency(t["debit"]), clean_currency(t["credit"]), clean_currency(t["amount"]),
            t["party_name"], t["party_gstin"], clean_currency(t["tax_amount"]), t["reference"]
        ))

    # 5. Insert CY Transactions
    cy_txs = get_transactions_for_company(company["short_code"])
    for t in cy_txs:
        cursor.execute("""
            INSERT INTO transactions (
                engagement_id, date, voucher_no, invoice_no, ledger, account_group,
                description, debit, credit, amount, party_name, gstin,
                tax_amount, reference_no
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cy_eng_id, t["date"], t["voucher_no"], t["invoice_no"], t["ledger"], t["account_group"],
            t["description"], clean_currency(t["debit"]), clean_currency(t["credit"]), clean_currency(t["amount"]),
            t["party_name"], t["party_gstin"], clean_currency(t["tax_amount"]), t["reference"]
        ))

    # 6. Insert Checklists
    checklists = get_test_checklist_items(cy_eng_id)
    for c in checklists:
        cursor.execute("""
            INSERT INTO audit_checklists (engagement_id, category, item_code, question, guidance, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cy_eng_id, c["category"], c["item_code"], c["question"], c["guidance"], c["status"], now_str))

    # 7. Insert Findings
    findings = get_test_findings_for_company(company["short_code"], cy_eng_id)
    for idx, f in enumerate(findings, 1):
        cursor.execute("""
            INSERT INTO audit_findings (
                engagement_id, finding_code, module, category, severity,
                risk_score, title, description, rule_used, engine_type,
                recommended_action, status, created_at
            )
            VALUES (?, ?, ?, 'Statutory Compliance', ?, 85.0, ?, ?, ?, 'DETERMINISTIC', ?, ?, ?)
        """, (
            cy_eng_id, f"FND-{company['short_code']}-{idx:03d}", "Compliance", f["severity"],
            f["title"], f["description"], f["rule_id"],
            f["recommendation"], f["status"], now_str
        ))

    # 8. Insert Working Papers
    wps = get_test_working_papers_for_company(company["short_code"], cy_eng_id)
    for wp in wps:
        cursor.execute("""
            INSERT INTO working_papers (
                engagement_id, wp_reference, title, area, category,
                description, status, prepared_by, prepared_date, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'Substantive Testing', ?, ?, ?, ?, ?, ?, ?)
        """, (
            cy_eng_id, wp["wp_reference"], wp["title"], wp["module"],
            wp["objective"], wp["status"], wp["prepared_by"], now_str[:10], wp["notes"], now_str, now_str
        ))

    # 9. Register Uploaded Files references with explicit source_type = 'TEST_FIXTURE' and uploaded_by = 'SYSTEM_TEST_SEED'
    for cat, fname in [
        ("General Ledger", "transactions.csv"),
        ("Sales Register", "sales_register.csv"),
        ("Purchase Register", "purchase_register.csv"),
        ("Bank Statement", "bank_statement.csv"),
        ("GST Data", "gst_portal.csv")
    ]:
        cursor.execute("""
            INSERT INTO uploaded_files (engagement_id, file_name, file_type, file_path, source_type, data_category, row_count, uploaded_by, uploaded_at)
            VALUES (?, ?, 'CSV', ?, 'TEST_FIXTURE', ?, 200, 'SYSTEM_TEST_SEED', ?)
        """, (
            cy_eng_id, f"{company['short_code'].lower()}_{fname}", f"test_data/{company['short_code'].lower()}_fintech/{fname}", cat, now_str
        ))

    return {
        "client_id": client_id,
        "cy_engagement_id": cy_eng_id,
        "py_engagement_id": py_eng_id,
        "company": company["name"],
        "lead_auditor_id": lead_auditor_id,
        "assigned_staff_id": assigned_staff_id
    }

def seed_test_database():
    """Seeds the SQLite database with both Aryan Fintech and Hitansh Fintech datasets and test users."""
    init_db()
    conn = get_db_connection()
    seed_test_users(conn)
    res_aryan = seed_company_engagement(conn, ARYAN_COMPANY)
    res_hitansh = seed_company_engagement(conn, HITANSH_COMPANY)
    conn.commit()
    conn.close()
    return {
        "aryan": res_aryan,
        "hitansh": res_hitansh
    }

if __name__ == "__main__":
    out = seed_test_database()
    print("Test Database successfully seeded with Aryan Fintech and Hitansh Fintech:")
    print(out)
