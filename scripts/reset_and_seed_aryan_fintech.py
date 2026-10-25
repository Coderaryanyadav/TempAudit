#!/usr/bin/env python3
"""
FinAuditPro - Fresh Clean-Room Reset & Aryan Fintech Comprehensive Seeder
TempAudit Audit Platform

1. Archives and resets the database finauditpro.db to a clean-room state.
2. Initializes fresh SQLite schema and migrations.
3. Populates ONLY Aryan Fintech Pvt. Ltd. as the active client (zero orphan or extraneous clients).
4. Populates all data required to test each and every feature:
   - Client Master: Aryan Fintech Pvt. Ltd. (PAN, GSTIN, CIN, bank details, contacts)
   - Engagements: Prior Year FY 2024-25 (Completed) & Current Year FY 2025-26 (In Progress)
   - Users: Admin, Auditor, Staff with standardized test credentials
   - General Ledger Transactions: 1,097 CY + 400 PY transactions with realistic anomalies:
     * Section 40A(3) Cash Payment > ₹10,000 (CPV-ARYAN-01: ₹55,000 cash freight)
     * Section 269ST Cash Receipt > ₹2,00,000 (CRV-ARYAN-01: ₹2,75,000 scrap sale)
     * Duplicate Vendor Invoices (INV-DUP-ARYAN-99: ₹1,25,000 posted twice)
     * Benford's Law outlier & round numbers (RND-VCH-ARYAN: ₹5,00,000)
     * Weekend / Sunday voucher posting (SUN-VCH-ARYAN: ₹2,10,000)
     * Structuring / Smurfing cash payments
   - Auxiliary Datasets:
     * Bank Statement (200 rows)
     * Sales Register (250 rows)
     * Purchase Register (250 rows)
     * GST Portal GSTR-2B Data (200 rows)
   - Ledgers: Pre-calculated summary table with accurate debit/credit balances
   - Reconciliations:
     * Bank Reconciliation Statement (BRS) with matched & timing differences
     * GST Reconciliation (GSTR-2B vs Books) with matched & tax discrepancies
   - Audit Procedures & Findings: Full hybrid engine execution and centralized sync
   - Working Papers: 6 substantive audit working papers (WP-REV-001, WP-BNK-001, etc.)
   - Audit Checklists: Standards on Auditing (SA 200/240/500) and Tax Audit checklists
   - Data Cleaning Logs: Full ingestion logs
   - Sample Audit Reports: PDF metadata entries
   - Cryptographic Audit Trail: Tamper-evident SHA-256 chained audit logs (valid = True)
   - Firm Settings: Setup wizard marked complete with CA firm profile

Usage:
    python scripts/reset_and_seed_aryan_fintech.py
"""

import os
import sys
import json
import shutil
import sqlite3
import csv
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from backend.app.database import get_db_connection, get_db_path, init_db, refresh_db_path
from backend.app.auth import hash_password
from backend.app.utils.audit_logger import log_audit_event, verify_audit_trail_integrity
from test_data.companies import ARYAN_COMPANY
from test_data.transactions import get_transactions_for_company, get_prior_year_transactions_for_company
from test_data.checklists import get_test_checklist_items


def clean_currency(val) -> float:
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


def reset_and_seed_aryan_only():
    print("=" * 80)
    print("FINAUDITPRO - ARYAN FINTECH PRISTINE CLEAN-ROOM SEEDER")
    print("=" * 80)

    db_path = get_db_path()
    backup_dir = os.path.join(PROJECT_ROOT, "backend", "backups")
    uploads_dir = os.path.join(PROJECT_ROOT, "backend", "uploaded_files")
    reports_dir = os.path.join(PROJECT_ROOT, "backend", "reports_generated")

    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(uploads_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    # 1. Archive active database if exists
    if os.path.exists(db_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_db = os.path.join(backup_dir, f"pre_aryan_reset_{timestamp}.db")
        try:
            src = sqlite3.connect(db_path)
            dst = sqlite3.connect(archive_db)
            src.backup(dst)
            dst.close()
            src.close()
            print(f"[OK] Archived active database snapshot to: {archive_db}")
        except Exception as e:
            print(f"[!] Warning archiving database: {e}")

        # Remove active DB and WAL files
        for p in [db_path, f"{db_path}-wal", f"{db_path}-shm"]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception as e:
                    print(f"[!] Warning removing {p}: {e}")
        print(f"[OK] Cleaned active database file: {db_path}")

    # Clean upload and report artifacts
    for d in [uploads_dir, reports_dir]:
        for fname in os.listdir(d):
            fpath = os.path.join(d, fname)
            try:
                if os.path.isfile(fpath) or os.path.islink(fpath):
                    os.unlink(fpath)
                elif os.path.isdir(fpath):
                    shutil.rmtree(fpath)
            except Exception as e:
                print(f"[!] Warning cleaning {fpath}: {e}")

    # 2. Initialize pristine schema
    print("\n[+] Initializing pristine production schema & migrations...")
    init_db()
    print("[OK] Database schema initialized successfully.")

    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    now_date = datetime.now().strftime("%Y-%m-%d")

    # 3. Seed App Settings (Setup wizard completed, firm profile ready)
    print("\n[+] Configuring CA firm profile and system settings...")
    firm_settings = [
        ("is_initial_setup_completed", "1"),
        ("firm_name", "Sharma & Associates Chartered Accountants"),
        ("firm_registration_no", "123456N"),
        ("firm_email", "admin@finauditpro.local"),
        ("firm_phone", "+91 98765 43210"),
        ("firm_address", "Suite 401, Nariman Point, Mumbai - 400021"),
        ("system_currency", "INR"),
        ("default_financial_year", "2025-26"),
        ("lead_partner_name", "CA Rajeshwar Sharma, FCA"),
        ("lead_partner_membership_no", "054321")
    ]
    for k, v in firm_settings:
        cursor.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)", (k, v, now_str))

    # 4. Seed Standardized Users
    print("[+] Seeding user accounts (Admin, Auditor, Staff)...")
    admin_pw = hash_password("admin123")
    audit_pw = hash_password("audit123")
    staff_pw = hash_password("staff123")

    users_data = [
        (1, "admin", "admin@finauditpro.local", "CA Rajeshwar Sharma (Lead Partner FCA)", "Admin", admin_pw),
        (2, "auditor_aryan", "lead.aryan@finauditpro.in", "Auditor A (Aryan Lead Manager)", "Auditor", audit_pw),
        (3, "staff_aryan", "staff.aryan@finauditpro.in", "Staff A (Aryan Engagement Staff)", "Audit Staff", staff_pw),
        (4, "auditor", "senior@finauditpro.in", "Rohan Mehta (Senior Auditor)", "Auditor", audit_pw),
        (5, "staff", "assistant@finauditpro.in", "Pooja Verma (Junior Audit Staff)", "Audit Staff", staff_pw),
    ]
    for uid, uname, uemail, ufullname, urole, uhash in users_data:
        cursor.execute("""
            INSERT OR REPLACE INTO users (id, username, email, full_name, role, password_hash, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (uid, uname, uemail, ufullname, urole, uhash, now_str))

    # 5. Seed Single Client: Aryan Fintech Pvt. Ltd.
    print("[+] Creating Client: Aryan Fintech Pvt. Ltd....")
    client_notes = (
        "Leading Indian fintech enterprise specializing in B2B payment orchestration, "
        "banking APIs, and real-time transaction processing. "
        "Authorized Capital: ₹5,00,00,000. Paid-up Capital: ₹2,50,00,000. "
        "Primary Banker: HDFC Bank Ltd (A/c: 50200011112233, IFSC: HDFC0000101)."
    )
    cursor.execute("""
        INSERT INTO clients (
            id, name, pan, gstin, entity_type, contact_person, email, phone, address, notes, created_at, updated_at
        ) VALUES (
            1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, (
        ARYAN_COMPANY["name"], ARYAN_COMPANY["pan"], ARYAN_COMPANY["gstin"], ARYAN_COMPANY["company_type"],
        ARYAN_COMPANY["primary_contact"], ARYAN_COMPANY["email"], ARYAN_COMPANY["phone"], ARYAN_COMPANY["address"],
        client_notes, now_str, now_str
    ))
    client_id = 1

    # 6. Seed Engagements (Prior Year FY 2024-25 and Current Year FY 2025-26)
    print("[+] Creating Engagements: FY 2024-25 (Prior Year) & FY 2025-26 (Current Year)...")
    cursor.execute("""
        INSERT INTO engagements (
            id, client_id, title, audit_type, financial_year, period_start, period_end, status,
            lead_auditor_id, assigned_staff_id, materiality_threshold, notes, created_at, updated_at
        ) VALUES (
            1, ?, 'Statutory Audit FY 2024-25', 'Statutory Audit', '2024-25', '2024-04-01', '2025-03-31', 'Completed',
            2, 3, 50000.0, 'Completed statutory audit for preceding financial year. Basis for comparative review.', ?, ?
        )
    """, (client_id, now_str, now_str))
    py_eng_id = 1

    cursor.execute("""
        INSERT INTO engagements (
            id, client_id, title, audit_type, financial_year, period_start, period_end, status,
            lead_auditor_id, assigned_staff_id, materiality_threshold, notes, created_at, updated_at
        ) VALUES (
            2, ?, 'Statutory & Tax Audit FY 2025-26', 'Statutory Audit', '2025-26', '2025-04-01', '2026-03-31', 'In Progress',
            2, 3, 50000.0, 'Active statutory and tax audit engagement for Aryan Fintech Pvt. Ltd.', ?, ?
        )
    """, (client_id, now_str, now_str))
    cy_eng_id = 2

    # 7. Copy Physical Files to uploaded_files/ and Insert Uploaded File Records
    print("[+] Copying auxiliary datasets and registering uploaded file metadata...")
    source_dir = os.path.join(PROJECT_ROOT, "test_data", "aryan_fintech")
    
    file_specs = [
        (1, cy_eng_id, "aryan_transactions.csv", "transactions.csv", "CSV", "General Ledger", 1097),
        (2, cy_eng_id, "aryan_sales_register.csv", "sales_register.csv", "CSV", "Sales Register", 250),
        (3, cy_eng_id, "aryan_purchase_register.csv", "purchase_register.csv", "CSV", "Purchase Register", 250),
        (4, cy_eng_id, "aryan_bank_statement.csv", "bank_statement.csv", "CSV", "Bank Statement", 200),
        (5, cy_eng_id, "aryan_gst_portal.csv", "gst_portal.csv", "CSV", "GST Data", 200),
        (6, py_eng_id, "aryan_prior_year_transactions.csv", "prior_year_transactions.csv", "CSV", "General Ledger", 400),
    ]

    for fid, eid, dest_name, src_name, ftype, cat, rcount in file_specs:
        src_path = os.path.join(source_dir, src_name)
        dst_path = os.path.join(uploads_dir, dest_name)
        if os.path.exists(src_path):
            shutil.copyfile(src_path, dst_path)

        cursor.execute("""
            INSERT INTO uploaded_files (
                id, engagement_id, file_name, file_type, file_path, source_type,
                data_category, row_count, successful_rows, failed_rows, warning_count,
                uploaded_by, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, 'TEST_FIXTURE', ?, ?, ?, 0, 0, 'admin', ?)
        """, (fid, eid, dest_name, ftype, dst_path, cat, rcount, rcount, now_str))

    # 8. Ingest PY Transactions (400 rows)
    print("[+] Ingesting Prior Year Transactions (400 records)...")
    py_txs = get_prior_year_transactions_for_company("ARYAN")
    for t in py_txs:
        cursor.execute("""
            INSERT INTO transactions (
                engagement_id, file_id, date, voucher_no, invoice_no, ledger, account_group,
                description, debit, credit, amount, party_name, gstin, tax_amount, reference_no,
                transaction_type
            ) VALUES (?, 6, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'GENERAL_LEDGER')
        """, (
            py_eng_id, t["date"], t["voucher_no"], t["invoice_no"], t["ledger"], t["account_group"],
            t["description"], clean_currency(t["debit"]), clean_currency(t["credit"]),
            clean_currency(t["amount"]), t["party_name"], t["party_gstin"],
            clean_currency(t["tax_amount"]), t["reference"]
        ))

    # 9. Ingest CY General Ledger Transactions (1,097 rows)
    print("[+] Ingesting Current Year General Ledger Transactions (1,097 records)...")
    cy_txs = get_transactions_for_company("ARYAN")
    for t in cy_txs:
        cursor.execute("""
            INSERT INTO transactions (
                engagement_id, file_id, date, voucher_no, invoice_no, ledger, account_group,
                description, debit, credit, amount, party_name, gstin, tax_amount, reference_no,
                transaction_type
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'GENERAL_LEDGER')
        """, (
            cy_eng_id, t["date"], t["voucher_no"], t["invoice_no"], t["ledger"], t["account_group"],
            t["description"], clean_currency(t["debit"]), clean_currency(t["credit"]),
            clean_currency(t["amount"]), t["party_name"], t["party_gstin"],
            clean_currency(t["tax_amount"]), t["reference"]
        ))

    # 10. Ingest CY Bank Statement Transactions (200 rows)
    print("[+] Ingesting Bank Statement Transactions (200 records)...")
    bank_csv_path = os.path.join(source_dir, "bank_statement.csv")
    if os.path.exists(bank_csv_path):
        with open(bank_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                cursor.execute("""
                    INSERT INTO transactions (
                        engagement_id, file_id, date, voucher_no, description,
                        debit, credit, amount, party_name, reference_no, bank_ref,
                        transaction_type
                    ) VALUES (?, 4, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'BANK_STATEMENT')
                """, (
                    cy_eng_id, r.get("date"), r.get("voucher_no"), r.get("description"),
                    clean_currency(r.get("debit")), clean_currency(r.get("credit")),
                    clean_currency(r.get("amount")), r.get("party_name"),
                    r.get("reference_no"), r.get("reference_no")
                ))

    # 11. Ingest Purchase Register Transactions (250 rows)
    print("[+] Ingesting Purchase Register Transactions (250 records)...")
    pr_csv_path = os.path.join(source_dir, "purchase_register.csv")
    if os.path.exists(pr_csv_path):
        with open(pr_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                cursor.execute("""
                    INSERT INTO transactions (
                        engagement_id, file_id, date, invoice_no, description,
                        debit, credit, amount, party_name, gstin, tax_amount,
                        transaction_type
                    ) VALUES (?, 3, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, 'PURCHASE_REGISTER')
                """, (
                    cy_eng_id, r.get("invoice_date"), r.get("invoice_number"),
                    f"Purchase from {r.get('supplier')}", clean_currency(r.get("invoice_value")),
                    clean_currency(r.get("invoice_value")), r.get("supplier"),
                    r.get("supplier_gstin"), clean_currency(r.get("total_tax"))
                ))

    # 12. Ingest GST Portal (GSTR-2B) Transactions (200 rows)
    print("[+] Ingesting GST Portal (GSTR-2B) Transactions (200 records)...")
    gst_csv_path = os.path.join(source_dir, "gst_portal.csv")
    if os.path.exists(gst_csv_path):
        with open(gst_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                cursor.execute("""
                    INSERT INTO transactions (
                        engagement_id, file_id, date, invoice_no, description,
                        debit, credit, amount, party_name, gstin, tax_amount,
                        transaction_type
                    ) VALUES (?, 5, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, 'GST_PORTAL')
                """, (
                    cy_eng_id, r.get("invoice_date"), r.get("invoice_number"),
                    f"GSTR-2B Inward supply from {r.get('supplier')}", clean_currency(r.get("invoice_value")),
                    clean_currency(r.get("invoice_value")), r.get("supplier"),
                    r.get("supplier_gstin"), clean_currency(r.get("total_tax"))
                ))

    # 13. Populate Ledgers Summary Table for Both CY and PY
    print("[+] Calculating and populating Ledgers summary table for Trial Balance...")
    for eid in [py_eng_id, cy_eng_id]:
        rows = cursor.execute("""
            SELECT ledger, account_group,
                   COALESCE(SUM(debit), 0.0) as tot_debit,
                   COALESCE(SUM(credit), 0.0) as tot_credit
            FROM transactions
            WHERE engagement_id = ? AND transaction_type = 'GENERAL_LEDGER' AND ledger IS NOT NULL
            GROUP BY ledger, account_group
        """, (eid,)).fetchall()

        for r in rows:
            debit = round(float(r["tot_debit"]), 2)
            credit = round(float(r["tot_credit"]), 2)
            closing = round(debit - credit, 2)
            cursor.execute("""
                INSERT OR REPLACE INTO ledgers (
                    engagement_id, ledger_name, account_group, opening_balance,
                    total_debit, total_credit, closing_balance
                ) VALUES (?, ?, ?, 0.0, ?, ?, ?)
            """, (eid, r["ledger"], r["account_group"], debit, credit, closing))

    # Commit transactions to disk before launching engines that open their own connections
    conn.commit()

    # 14. Execute Bank Reconciliation (BRS)
    print("[+] Running Bank Reconciliation Engine...")
    try:
        from backend.app.services.bank_reconciliation_engine import run_bank_reconciliation
        brs_result = run_bank_reconciliation(
            engagement_id=cy_eng_id,
            bank_ledger_name="HDFC Bank Ltd",
            file_b_id=4,
            title="HDFC Bank Current Account BRS (FY 2025-26)"
        )
        brs_sum = brs_result.get("summary", {})
        print(f"[OK] BRS completed: {brs_sum.get('matched_count', 0)} matched, "
              f"{brs_sum.get('unmatched_bank_count', 0)} unmatched bank items, "
              f"{brs_sum.get('unmatched_book_count', 0)} unmatched book items.")
    except Exception as e:
        print(f"[!] Warning running BRS engine: {e}")

    # 15. Execute GST Reconciliation
    print("[+] Running GST Reconciliation Engine (GSTR-2B vs Purchase Register)...")
    try:
        from backend.app.services.gst_reconciliation_engine import run_gst_reconciliation
        gst_result = run_gst_reconciliation(
            engagement_id=cy_eng_id,
            source_a_file_id=5,
            source_a_type="GSTR-2B (Portal Download)",
            source_b_file_id=3,
            source_b_type="Purchase Register (Books)",
            recon_title="GSTR-2B vs Purchase Register Reconciliation (FY 2025-26)"
        )
        gst_sum = gst_result.get("summary", {})
        print(f"[OK] GST Recon completed: {gst_sum.get('partially_matched_count', 0)} matched/partial, "
              f"{gst_sum.get('missing_in_source_a_count', 0)} unreflected 2B items, "
              f"{gst_sum.get('missing_in_source_b_count', 0)} unrecorded purchases.")
    except Exception as e:
        print(f"[!] Warning running GST recon engine: {e}")

    # 16. Run Hybrid Audit Engine & Centralized Findings Engine
    print("[+] Running Hybrid Audit Engine & Centralized Findings Engine...")
    try:
        from backend.app.audit_engine.engine import HybridAuditEngine
        from backend.app.services.centralized_findings_engine import CentralizedFindingsEngine

        engine = HybridAuditEngine(cy_eng_id)
        results = engine.execute_audit()
        print(f"[OK] Hybrid audit executed: {results.get('findings_count', 0)} findings generated.")

        sync_result = CentralizedFindingsEngine.sync_all_engagement_findings(cy_eng_id)
        print(f"[OK] Centralized findings synchronized: {sync_result.get('total_collected', 0)} total findings.")
    except Exception as e:
        print(f"[!] Warning executing audit engine: {e}")

    # 17. Seed Working Papers
    print("[+] Seeding 6 Substantive Working Papers...")
    wps = [
        {
            "wp_reference": "WP-REV-ARYAN-01",
            "title": "[ARYAN] Revenue Cut-off and Substantive Testing",
            "area": "Revenue",
            "category": "Substantive Testing",
            "description": "Verification of revenue recognition compliance under Ind AS 115, year-end invoice cut-offs, and payment gateway settlement reconciliations.",
            "status": "In Progress",
            "prepared_by": "Staff A (Aryan Engagement Staff)",
            "notes": "Sampled 50 sales transactions across Q1-Q4. Validated API invoicing logs and GST returns agreement."
        },
        {
            "wp_reference": "WP-BNK-ARYAN-01",
            "title": "[ARYAN] Bank Reconciliation and Balance Confirmation",
            "area": "Cash & Bank",
            "category": "Substantive Testing",
            "description": "Substantiation of bank balances against direct bank confirmations (SA 505), inspection of stale cheques, and verification of high-value NEFT transfers.",
            "status": "Prepared",
            "prepared_by": "Auditor A (Aryan Lead Manager)",
            "notes": "100+ transactions matched automatically. Investigating 10 unpresented cheques and direct bank debits."
        },
        {
            "wp_reference": "WP-GST-ARYAN-01",
            "title": "[ARYAN] GST ITC Reconciliations & Rule 36(4) Compliance",
            "area": "Statutory Compliance",
            "category": "Substantive Testing",
            "description": "Verification that all claimed Input Tax Credit appears in GSTR-2B and conforms to Section 16(2)(aa) eligibility criteria under CGST Act.",
            "status": "Under Review",
            "prepared_by": "Staff A (Aryan Engagement Staff)",
            "notes": "Reconciled purchase register against auto-drafted GSTR-2B data. Issued vendor notices for missing invoices."
        },
        {
            "wp_reference": "WP-CSH-ARYAN-01",
            "title": "[ARYAN] Substantive Testing of Cash & Section 40A(3) Compliance",
            "area": "Statutory Compliance",
            "category": "Tax Audit Form 3CD",
            "description": "Physical cash verification, cash book balancing, and testing for Section 40A(3) disallowances exceeding ₹10,000 threshold.",
            "status": "In Progress",
            "prepared_by": "Staff A (Aryan Engagement Staff)",
            "notes": "Identified voucher CPV-ARYAN-01 for ₹55,000 paid in cash for freight delivery. Liable for 100% disallowance under Clause 21(d)."
        },
        {
            "wp_reference": "WP-DUP-ARYAN-01",
            "title": "[ARYAN] Investigation of Duplicate Vendor Invoices & Payments",
            "area": "Internal Controls",
            "category": "Controls Testing",
            "description": "Examination of AP controls regarding duplicate invoice numbers and matching amounts within identical vendor ledgers.",
            "status": "In Progress",
            "prepared_by": "Auditor A (Aryan Lead Manager)",
            "notes": "Vouchers DUP-VCH-ARYAN-1 and DUP-VCH-ARYAN-2 both reference invoice INV-DUP-ARYAN-99 for ₹1,25,000 to AF CyberSecurity Labs Ltd."
        },
        {
            "wp_reference": "WP-FAR-ARYAN-01",
            "title": "[ARYAN] Fixed Assets Register & Depreciation Schedule",
            "area": "Fixed Assets",
            "category": "Substantive Testing",
            "description": "Physical verification records, additions/deletions testing, and depreciation calculation in accordance with Schedule II of Companies Act 2013.",
            "status": "Completed",
            "prepared_by": "Staff A (Aryan Engagement Staff)",
            "notes": "Verified server rack additions, scrap asset sales (₹2,75,000 cash receipt), and computed straight-line depreciation."
        }
    ]

    for wp in wps:
        cursor.execute("""
            INSERT INTO working_papers (
                engagement_id, wp_reference, title, area, category,
                description, status, prepared_by, prepared_date, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cy_eng_id, wp["wp_reference"], wp["title"], wp["area"], wp["category"],
            wp["description"], wp["status"], wp["prepared_by"], now_date,
            wp["notes"], now_str, now_str
        ))

    # 18. Seed Audit Checklists (SA 200, SA 240, SA 500, Companies Act)
    print("[+] Seeding Audit Checklist items...")
    checklists = get_test_checklist_items(cy_eng_id)
    for c in checklists:
        cursor.execute("""
            INSERT INTO audit_checklists (engagement_id, category, item_code, question, guidance, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cy_eng_id, c["category"], c["item_code"], c["question"], c["guidance"], c["status"], now_str))

    # 19. Seed Data Cleaning Logs
    print("[+] Seeding Data Cleaning and Ingestion Logs...")
    cleaning_records = [
        (1, 1092, "amount", "55,000.00", "55000.00", "CURRENCY_NORMALIZATION", 0, 1.0, "Auto-Applied", "Normalized cash freight payment amount to 2 decimal places"),
        (1, 1093, "date", "20/07/2025", "2025-07-20", "DATE_STANDARDIZATION", 0, 1.0, "Auto-Applied", "Standardized DD/MM/YYYY date to ISO YYYY-MM-DD"),
        (2, 1, "customer_gstin", "27aaacaf1001a1z2", "27AAACAF1001A1Z2", "CASE_NORMALIZATION", 0, 1.0, "Auto-Applied", "Normalized sales customer GSTIN to uppercase format"),
        (4, 1, "description", "  NEFT / HDFC99812 / Express Freight   ", "NEFT / HDFC99812 / Express Freight", "WHITESPACE_TRIM", 0, 1.0, "Auto-Applied", "Trimmed superfluous whitespace from bank narration"),
        (5, 1, "taxable_value", "105932.2000", "105932.20", "DECIMAL_PRECISION", 0, 1.0, "Auto-Applied", "Rounded taxable value to 2 decimal places")
    ]
    for fid, rnum, fld, orig, norm, rule, quest, conf, status, comm in cleaning_records:
        cursor.execute("""
            INSERT INTO data_cleaning_logs (
                engagement_id, file_id, row_number, field_name, original_value,
                normalized_value, transformation_rule, is_questionable,
                confidence_score, review_status, auditor_comment, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cy_eng_id, fid, rnum, fld, orig, norm, rule, quest, conf, status, comm, now_str))

    # 20. Seed Sample Audit Reports
    print("[+] Registering Audit Report entries...")
    reports_meta = [
        (cy_eng_id, "Form 3CD Tax Audit Report FY 2025-26", "TAX_AUDIT_3CD", "admin", "reports_generated/Form_3CD_Aryan_Fintech_2025_26.pdf"),
        (cy_eng_id, "Executive Summary & Risk Assessment Memo", "EXECUTIVE_SUMMARY", "auditor_aryan", "reports_generated/Executive_Summary_Aryan_Fintech.pdf"),
        (cy_eng_id, "Bank & GST Reconciliation Discrepancy Statement", "RECONCILIATION_REPORT", "staff_aryan", "reports_generated/Reconciliation_Report_Aryan_Fintech.pdf")
    ]
    for eid, title, rtype, gen_by, fpath in reports_meta:
        cursor.execute("""
            INSERT INTO reports (
                engagement_id, report_title, report_type, generated_by,
                file_path, summary_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (eid, title, rtype, gen_by, fpath, json.dumps({"status": "Final", "pages": 12}), now_str))

    # 21. Build Cryptographic Tamper-Evident Audit Trail (Valid SHA-256 Chain via log_audit_event)
    print("[+] Constructing tamper-evident SHA-256 Audit Trail chain...")
    audit_events = [
        ("INITIALIZE_SCHEMA", "SYSTEM", "Pristine database schema initialized with versioned migrations", "SYSTEM", None),
        ("FIRM_SETUP", "admin", "Configured Chartered Accountant firm profile (Sharma & Associates, FRN: 123456N)", "app_settings", None),
        ("CREATE_USER", "admin", "Provisioned auditor accounts: auditor_aryan, staff_aryan", "users", None),
        ("CREATE_CLIENT", "admin", "Registered client master: Aryan Fintech Pvt. Ltd. (PAN: AAPCA1111A)", "clients", 1),
        ("CREATE_ENGAGEMENT", "admin", "Opened Statutory & Tax Audit Engagement FY 2025-26", "engagements", 2),
        ("IMPORT_GENERAL_LEDGER", "staff_aryan", "Ingested 1,097 General Ledger transactions from aryan_transactions.csv", "uploaded_files", 1),
        ("IMPORT_BANK_STATEMENT", "staff_aryan", "Ingested 200 Bank Statement records from aryan_bank_statement.csv", "uploaded_files", 4),
        ("IMPORT_PURCHASE_REGISTER", "staff_aryan", "Ingested 250 Purchase Register records from aryan_purchase_register.csv", "uploaded_files", 3),
        ("IMPORT_GST_PORTAL", "staff_aryan", "Ingested 200 GSTR-2B records from aryan_gst_portal.csv", "uploaded_files", 5),
        ("CALCULATE_TRIAL_BALANCE", "auditor_aryan", "Generated comprehensive Trial Balance across 22 account heads", "ledgers", None),
        ("EXECUTE_BRS", "auditor_aryan", "Executed automated 4-tier Bank Reconciliation Statement for HDFC Bank", "reconciliations", 1),
        ("EXECUTE_GST_RECON", "auditor_aryan", "Executed GSTR-2B vs Purchase Register statutory tax reconciliation", "reconciliations", 2),
        ("EXECUTE_AUDIT_RULES", "auditor_aryan", "Executed Hybrid Audit Engine: Flagged Section 40A(3), 269ST, and duplicate invoice anomalies", "audit_findings", None),
        ("INITIALIZE_WORKING_PAPERS", "staff_aryan", "Prepared 6 substantive audit working papers across Revenue, Bank, GST, Cash, and Controls", "working_papers", None),
    ]

    for action, username, details, etype, eid in audit_events:
        log_audit_event(
            conn=conn,
            user={"id": 1, "username": username},
            action=action,
            module="AUDIT_TRAIL",
            record_id=eid,
            details=details,
            engagement_id=cy_eng_id,
            entity_type=etype,
            entity_id=eid
        )

    # Verify audit trail integrity
    integrity = verify_audit_trail_integrity(conn)
    print(f"[OK] Audit trail integrity verified: valid = {integrity['valid']}, total_entries = {integrity['total_entries']}")

    conn.commit()
    conn.close()

    print("\n" + "=" * 80)
    print("✨ ARYAN FINTECH PRISTINE CLEAN-ROOM RESET COMPLETE! ✨")
    print("=" * 80)
    print(f"Database Location: {db_path}")
    print("\nClient:")
    print("  - Aryan Fintech Pvt. Ltd. (ID: 1)")
    print("    PAN: AAPCA1111A | GSTIN: 27AAPCA1111A1Z1")
    print("\nEngagements:")
    print("  - Engagement #2: Statutory & Tax Audit FY 2025-26 (In Progress - ACTIVE)")
    print("  - Engagement #1: Statutory Audit FY 2024-25 (Completed - PRIOR YEAR COMPARATIVE)")
    print("\nIngested Operational Datasets:")
    print("  - CY General Ledger: 1,097 transactions (includes Section 40A(3), 269ST, duplicate entries, Benford outliers)")
    print("  - PY General Ledger: 400 transactions (for YoY comparisons and trend analytics)")
    print("  - Bank Statement: 200 records (HDFC Bank Current Account)")
    print("  - Purchase Register: 250 records")
    print("  - Sales Register: 250 records")
    print("  - GSTR-2B Portal Download: 200 records")
    print("\nPre-computed Modules:")
    print("  - Trial Balance & Ledgers: Pre-calculated debit/credit totals across all account heads")
    print("  - Bank Reconciliation (BRS): Completed reconciliation with timing differences")
    print("  - GST Reconciliation: Completed GSTR-2B vs Books reconciliation")
    print("  - Risk & Findings Register: Synchronized statutory findings (Critical, High, Medium, Low)")
    print("  - Working Papers: 6 substantive audit documentation working papers")
    print("  - Audit Checklists: SA 200, SA 240, SA 500, and Tax Audit Form 3CD clauses")
    print("  - Audit Trail: 14 chained events with valid SHA-256 cryptographic hashes")
    print("\nTest User Logins:")
    print("  - Lead Partner / Admin: admin / admin123")
    print("  - Lead Auditor:         auditor_aryan / audit123")
    print("  - Audit Staff:          staff_aryan / staff123")
    print("=" * 80)


if __name__ == "__main__":
    reset_and_seed_aryan_only()
