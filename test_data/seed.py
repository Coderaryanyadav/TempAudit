"""
Test Database Seeder
FinAuditPro - Test Data Architecture

Seeds independent client and engagement records for:
1. Aryan Fintech Pvt. Ltd. (FY 2025-26 and Prior FY 2024-25)
2. Hitansh Fintech Pvt. Ltd. (FY 2025-26 and Prior FY 2024-25)
"""

import os
import csv
from datetime import datetime
from backend.app.database import get_db_connection, init_db
from test_data.companies import ARYAN_COMPANY, HITANSH_COMPANY
from test_data.transactions import get_transactions_for_company, get_prior_year_transactions_for_company
from test_data.findings import get_test_findings_for_company
from test_data.working_papers import get_test_working_papers_for_company
from test_data.checklists import get_test_checklist_items

def seed_company_engagement(conn, company: dict) -> dict:
    now_str = datetime.now().isoformat()
    cursor = conn.cursor()

    # 1. Insert Client
    cursor.execute("""
        INSERT INTO clients (name, pan, gstin, entity_type, contact_person, email, phone, address, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        company["name"], company["pan"], company["gstin"], company["company_type"],
        company["primary_contact"], company["email"], company["phone"], company["address"],
        now_str, now_str
    ))
    client_id = cursor.lastrowid

    # 2. Insert Prior Year Engagement (FY 2024-25)
    cursor.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, status, lead_auditor_id, assigned_staff_id, notes, created_at, updated_at)
        VALUES (?, ?, 'Statutory Audit', ?, ?, ?, 'Completed', 1, 2, ?, ?, ?)
    """, (
        client_id, f"Statutory Audit {company['prior_financial_year']}", company["prior_financial_year"],
        f"2024-04-01", f"2025-03-31", f"Prior year audit records for {company['name']}", now_str, now_str
    ))
    py_eng_id = cursor.lastrowid

    # 3. Insert Current Year Engagement (FY 2025-26)
    cursor.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, status, lead_auditor_id, assigned_staff_id, notes, created_at, updated_at)
        VALUES (?, ?, 'Statutory Audit', ?, ?, ?, 'In Progress', 1, 2, ?, ?, ?)
    """, (
        client_id, f"Statutory & Tax Audit {company['financial_year']}", company["financial_year"],
        f"2025-04-01", f"2026-03-31", f"Current year active audit for {company['name']}", now_str, now_str
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
            t["description"], float(t["debit"] or 0.0), float(t["credit"] or 0.0), float(t["amount"] or 0.0),
            t["party_name"], t["party_gstin"], float(t["tax_amount"] or 0.0), t["reference"]
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
            t["description"], float(t["debit"] or 0.0), float(t["credit"] or 0.0), float(t["amount"] or 0.0),
            t["party_name"], t["party_gstin"], float(t["tax_amount"] or 0.0), t["reference"]
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

    # 9. Register Uploaded Files references
    for cat, fname in [
        ("General Ledger", "transactions.csv"),
        ("Sales Register", "sales_register.csv"),
        ("Purchase Register", "purchase_register.csv"),
        ("Bank Statement", "bank_statement.csv"),
        ("GST Data", "gst_portal.csv")
    ]:
        cursor.execute("""
            INSERT INTO uploaded_files (engagement_id, file_name, file_type, file_path, data_category, row_count, uploaded_by, uploaded_at)
            VALUES (?, ?, 'CSV', ?, ?, 200, 'admin', ?)
        """, (
            cy_eng_id, f"{company['short_code'].lower()}_{fname}", f"test_data/{company['short_code'].lower()}_fintech/{fname}", cat, now_str
        ))

    return {
        "client_id": client_id,
        "cy_engagement_id": cy_eng_id,
        "py_engagement_id": py_eng_id,
        "company": company["name"]
    }

def seed_test_database():
    """Seeds the SQLite database with both Aryan Fintech and Hitansh Fintech datasets."""
    init_db()
    conn = get_db_connection()
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
