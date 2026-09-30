import os
import json
import pandas as pd
from datetime import datetime
from backend.app.database import get_db_connection, init_db
from backend.app.auth import hash_password

SAMPLE_TRANSACTIONS = [
    # Normal operations
    {"date": "2024-04-05", "voucher_no": "VR-2024-001", "invoice_no": "INV-101", "ledger": "Sales Revenue", "account_group": "Revenue", "description": "Domestic sales of industrial machinery parts", "debit": 0.0, "credit": 500000.0, "amount": 500000.0, "party_name": "Bharat Heavy Infra Ltd", "gstin": "27AAACB1234A1Z5", "invoice_date": "2024-04-05", "payment_date": "2024-04-20"},
    {"date": "2024-04-10", "voucher_no": "VR-2024-002", "invoice_no": "PUR-501", "ledger": "Raw Material Purchase", "account_group": "Expense", "description": "Purchase of structural steel grade A", "debit": 354000.0, "credit": 0.0, "amount": 354000.0, "party_name": "Tata Steel Supply Depot", "gstin": "27AAACT1234F1Z8", "invoice_date": "2024-04-08", "payment_date": "2024-04-10"},
    {"date": "2024-04-30", "voucher_no": "VR-2024-003", "invoice_no": "SAL-04", "ledger": "Salaries & Wages", "account_group": "Expense", "description": "Staff salary disbursement for April 2024", "debit": 450000.0, "credit": 0.0, "amount": 450000.0, "party_name": "HDFC Bank Salary Account", "gstin": "", "invoice_date": "2024-04-30", "payment_date": "2024-04-30"},
    {"date": "2024-05-02", "voucher_no": "VR-2024-004", "invoice_no": "RNT-05", "ledger": "Office Rent", "account_group": "Expense", "description": "Factory and corporate office rent for May 2024", "debit": 125000.0, "credit": 0.0, "amount": 125000.0, "party_name": "Kedia Realtors LLP", "gstin": "27AAEFK8899D1ZV", "invoice_date": "2024-05-01", "payment_date": "2024-05-02"},

    # 1. Section 40A(3) Breach: Cash Payment > ₹10,000
    {"date": "2024-05-15", "voucher_no": "CPV-001", "invoice_no": "TRN-909", "ledger": "Freight & Cartage (Cash)", "account_group": "Expense", "description": "Urgent cash payment for inter-state consignment freight", "debit": 45000.0, "credit": 0.0, "amount": 45000.0, "party_name": "Sharma Logistics Express", "gstin": "", "invoice_date": "2024-05-15", "payment_date": "2024-05-15", "transaction_type": "Cash"},

    # 2. Section 269ST Breach: Cash Receipt >= ₹2,00,000
    {"date": "2024-06-02", "voucher_no": "CRV-012", "invoice_no": "SCR-01", "ledger": "Scrap Sales (Cash)", "account_group": "Revenue", "description": "Spot cash receipt for bulk metal scrap liquidation", "debit": 0.0, "credit": 250000.0, "amount": 250000.0, "party_name": "Vikas Scrap Traders", "gstin": "", "invoice_date": "2024-06-02", "payment_date": "2024-06-02", "transaction_type": "Cash"},

    # 3. Duplicate Invoice Entries
    {"date": "2024-06-18", "voucher_no": "PV-108", "invoice_no": "INV-7744", "ledger": "Power & Fuel", "account_group": "Expense", "description": "Backup DG diesel and electricity utility billing", "debit": 118000.0, "credit": 0.0, "amount": 118000.0, "party_name": "Reliance Power Solutions", "gstin": "27AABCR9911C1ZX", "invoice_date": "2024-06-18", "payment_date": "2024-06-20"},
    {"date": "2024-06-18", "voucher_no": "PV-109", "invoice_no": "INV-7744", "ledger": "Power & Fuel", "account_group": "Expense", "description": "Backup DG diesel and electricity utility billing (Duplicate)", "debit": 118000.0, "credit": 0.0, "amount": 118000.0, "party_name": "Reliance Power Solutions", "gstin": "27AABCR9911C1ZX", "invoice_date": "2024-06-18", "payment_date": "2024-06-20"},

    # 4. Invalid GSTIN Format (14 chars instead of 15)
    {"date": "2024-07-05", "voucher_no": "PV-145", "invoice_no": "ZTS-99", "ledger": "IT Software & Cloud Services", "account_group": "Expense", "description": "Annual ERP license and cloud hosting fees", "debit": 88500.0, "credit": 0.0, "amount": 88500.0, "party_name": "Zenith Tech Systems", "gstin": "27AABC1234D1Z", "invoice_date": "2024-07-01", "payment_date": "2024-07-05"},

    # 5. Date Anomaly: Payment date precedes Invoice date
    {"date": "2024-07-20", "voucher_no": "PV-162", "invoice_no": "MN-441", "ledger": "Maintenance Expenses", "account_group": "Expense", "description": "HVAC compressor overhaul servicing", "debit": 65000.0, "credit": 0.0, "amount": 65000.0, "party_name": "Cooling Point Services", "gstin": "27AABCP7766A1ZQ", "invoice_date": "2024-08-10", "payment_date": "2024-07-20"},

    # 6. High Value Round Number with Vague Narration
    {"date": "2024-08-14", "voucher_no": "JV-088", "invoice_no": "ADJ-01", "ledger": "Consultancy & Professional Fees", "account_group": "Expense", "description": "Miscellaneous adjustment and management fees", "debit": 500000.0, "credit": 0.0, "amount": 500000.0, "party_name": "Apex Advisory Services", "gstin": "27AAACP5522K1Z3", "invoice_date": "2024-08-14", "payment_date": "2024-08-14"},

    # 7. Missing Voucher Number on High-Value Entry
    {"date": "2024-09-01", "voucher_no": "", "invoice_no": "DIR-09", "ledger": "Directors Remuneration", "account_group": "Expense", "description": "", "debit": 250000.0, "credit": 0.0, "amount": 250000.0, "party_name": "Rajesh Singhania", "gstin": "", "invoice_date": "2024-09-01", "payment_date": "2024-09-01"},

    # 8. Statistical / ML Spike (Isolation Forest Outlier)
    {"date": "2024-10-12", "voucher_no": "PV-289", "invoice_no": "REP-998", "ledger": "Plant & Machinery Repairs", "account_group": "Expense", "description": "Emergency high-pressure turbine overhaul and turbine rotor reconditioning", "debit": 1850000.0, "credit": 0.0, "amount": 1850000.0, "party_name": "Siemens Precision Engineering", "gstin": "27AAACS4411P1Z9", "invoice_date": "2024-10-10", "payment_date": "2024-10-12"},

    # 9. Sunday High Value Posting (2024-11-17 was Sunday)
    {"date": "2024-11-17", "voucher_no": "PV-312", "invoice_no": "ADV-02", "ledger": "Advertisement & Marketing", "account_group": "Expense", "description": "Print media campaign and exhibition sponsorship", "debit": 175000.0, "credit": 0.0, "amount": 175000.0, "party_name": "Metro Media House", "gstin": "27AABCM6611J1ZK", "invoice_date": "2024-11-17", "payment_date": "2024-11-17"},

    # Further standard records for distribution richness
    {"date": "2024-12-05", "voucher_no": "VR-2024-055", "invoice_no": "INV-188", "ledger": "Sales Revenue", "account_group": "Revenue", "description": "Export sales of engineering components", "debit": 0.0, "credit": 1250000.0, "amount": 1250000.0, "party_name": "Global Tech FZE", "gstin": "", "invoice_date": "2024-12-05", "payment_date": "2024-12-15"},
    {"date": "2024-12-20", "voucher_no": "VR-2024-056", "invoice_no": "PUR-912", "ledger": "Raw Material Purchase", "account_group": "Expense", "description": "Alloy ingots purchase", "debit": 620000.0, "credit": 0.0, "amount": 620000.0, "party_name": "Hindalco Industries Ltd", "gstin": "27AAACH2233M1Z2", "invoice_date": "2024-12-18", "payment_date": "2024-12-20"},
    {"date": "2025-01-15", "voucher_no": "VR-2025-001", "invoice_no": "BNK-01", "ledger": "Bank Interest & Finance Charges", "account_group": "Expense", "description": "Working capital CC limit interest charges", "debit": 48250.0, "credit": 0.0, "amount": 48250.0, "party_name": "State Bank of India", "gstin": "27AAACS0000A1Z1", "invoice_date": "2025-01-15", "payment_date": "2025-01-15"},
    {"date": "2025-02-10", "voucher_no": "VR-2025-014", "invoice_no": "AUD-01", "ledger": "Audit & Legal Fees", "account_group": "Expense", "description": "Interim statutory audit fee provision", "debit": 75000.0, "credit": 0.0, "amount": 75000.0, "party_name": "Kherani & Associates CA", "gstin": "27AAAFF1234A1Z7", "invoice_date": "2025-02-10", "payment_date": "2025-02-10"},
    {"date": "2025-03-25", "voucher_no": "VR-2025-030", "invoice_no": "TEL-03", "ledger": "Telephone & Internet", "account_group": "Expense", "description": "High-speed optical fiber leased line bill", "debit": 18450.0, "credit": 0.0, "amount": 18450.0, "party_name": "Airtel Business Enterprise", "gstin": "27AAACB2233Q1Z6", "invoice_date": "2025-03-20", "payment_date": "2025-03-25"},
    {"date": "2025-03-31", "voucher_no": "VR-2025-031", "invoice_no": "DEP-01", "ledger": "Depreciation Expense", "account_group": "Expense", "description": "Year-end depreciation as per Schedule II Companies Act 2013", "debit": 215000.0, "credit": 0.0, "amount": 215000.0, "party_name": "Accumulated Depreciation", "gstin": "", "invoice_date": "2025-03-31", "payment_date": "2025-03-31"}
]

STANDARD_CHECKLIST_ITEMS = [
    # Statutory / Companies Act / CARO
    {"category": "Companies Act 2013 & CARO 2020", "item_code": "CARO-01", "question": "Whether the company is maintaining proper records showing full particulars of Property, Plant and Equipment?", "guidance": "Clause (i)(a) of CARO 2020. Verify Fixed Asset Register with physical verification records."},
    {"category": "Companies Act 2013 & CARO 2020", "item_code": "CARO-02", "question": "Whether physical verification of inventory has been conducted at reasonable intervals by the management?", "guidance": "Clause (ii)(a) of CARO 2020. Confirm coverage, frequency, and discrepancy treatment."},
    {"category": "Companies Act 2013 & CARO 2020", "item_code": "CARO-03", "question": "Whether the company has maintained audit trail feature throughout the financial year without tampering?", "guidance": "Section 143(3)(j) read with Rule 11(g) of Companies (Audit and Auditors) Rules."},

    # Tax Audit (Form 3CD)
    {"category": "Tax Audit (Form 3CD)", "item_code": "3CD-21D", "question": "Whether any cash payment exceeding ₹10,000 was made in contravention of Section 40A(3)?", "guidance": "Clause 21(d) of Form 3CD. Cross-verify with FinAuditPro Deterministic Rule engine findings."},
    {"category": "Tax Audit (Form 3CD)", "item_code": "3CD-31", "question": "Particulars of each loan, deposit, or receipt exceeding ₹2,00,000 received otherwise than by banking channels u/s 269ST?", "guidance": "Clause 31 of Form 3CD. Check Section 269ST exceptions."},
    {"category": "Tax Audit (Form 3CD)", "item_code": "3CD-34", "question": "Whether the assessee is required to deduct or collect tax (TDS/TCS) as per the provisions of Chapter XVII-B?", "guidance": "Clause 34 of Form 3CD. Verify Form 26Q/27Q reconciliation."},
    {"category": "Tax Audit (Form 3CD)", "item_code": "3CD-44", "question": "Break-up of total expenditure of entities registered and not registered under the GST?", "guidance": "Clause 44 of Form 3CD. Reconcile GSTR-9 / 3B."}
]

def seed_sample_database():
    """Initializes and seeds database with realistic sample client, engagement, transactions, and checklists."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Seed Users
    cursor.execute("SELECT COUNT(*) as c FROM users").fetchone()
    admin_hash = hash_password("admin123")
    auditor_hash = hash_password("audit123")
    staff_hash = hash_password("staff123")
    now_str = datetime.now().isoformat()

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

    # 2. Seed Client
    cursor.execute("""
    INSERT OR REPLACE INTO clients (id, name, pan, gstin, entity_type, contact_person, email, phone, address, created_at, updated_at)
    VALUES (1, 'Apex Engineering & Logistics Pvt Ltd', 'AABCA1234D', '27AABCA1234D1ZP', 'Private Limited Company', 'Rajesh Singhania (Director)', 'accounts@apexengineering.com', '+91 98200 12345', 'Plot 42, MIDC Industrial Area, Andheri East, Mumbai 400093', ?, ?)
    """, (now_str, now_str))

    # 3. Seed Engagement
    cursor.execute("""
    INSERT OR REPLACE INTO engagements (id, client_id, title, audit_type, financial_year, period_start, period_end, status, lead_auditor_id, created_at, updated_at)
    VALUES (1, 1, 'Statutory & Tax Audit FY 2024-25', 'Statutory Audit', '2024-25', '2024-04-01', '2025-03-31', 'In Progress', 1, ?, ?)
    """, (now_str, now_str))

    # 4. Seed Transactions
    cursor.execute("SELECT COUNT(*) as c FROM transactions WHERE engagement_id = 1")
    if cursor.fetchone()["c"] == 0:
        for t in SAMPLE_TRANSACTIONS:
            debit = float(t.get("debit", 0.0))
            credit = float(t.get("credit", 0.0))
            amount = float(t.get("amount", max(debit, credit)))
            cursor.execute("""
            INSERT INTO transactions (
                engagement_id, date, voucher_no, invoice_no, ledger, account_group,
                description, debit, credit, amount, party_name, gstin,
                invoice_date, payment_date, transaction_type
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                t["date"], t["voucher_no"], t["invoice_no"], t["ledger"], t["account_group"],
                t["description"], debit, credit, amount, t["party_name"], t.get("gstin", ""),
                t.get("invoice_date", t["date"]), t.get("payment_date", t["date"]), t.get("transaction_type", "Journal")
            ))

    # 5. Seed Checklist Items
    cursor.execute("SELECT COUNT(*) as c FROM audit_checklists WHERE engagement_id = 1")
    if cursor.fetchone()["c"] == 0:
        for item in STANDARD_CHECKLIST_ITEMS:
            cursor.execute("""
            INSERT INTO audit_checklists (
                engagement_id, category, item_code, question, guidance, status, auditor_remarks, checked_by, checked_at
            ) VALUES (1, ?, ?, ?, ?, 'Pending', '', 'Pooja Verma', ?)
            """, (
                item["category"], item["item_code"], item["question"], item["guidance"], now_str
            ))

    # 6. Seed Working Paper
    # 6. Seed Working Papers
    cursor.execute("SELECT COUNT(*) as c FROM working_papers WHERE engagement_id = 1")
    if cursor.fetchone()["c"] == 0:
        cursor.execute("""
        INSERT INTO working_papers (
            engagement_id, wp_reference, title, area, category, description,
            evidence, notes, attached_files_json, prepared_by, prepared_date,
            reviewed_by, review_date, status, reviewer_comments_json,
            linked_findings_json, linked_transactions_json, linked_checklists_json,
            created_at, updated_at
        ) VALUES (
            1, 'WP-A101', 'Understanding Entity & Internal Control Environment',
            'Internal Controls & Governance', 'Internal Controls & Governance',
            'Documentation of corporate governance, IT controls (Tally Prime), and bank signatories.',
            'Verified board resolutions dated 15-May-2024 and internal control walkthrough documentation.',
            'Internal control environment found satisfactory. Segregation of duties maintained for maker-checker payment approvals.',
            '[]', 'Pooja Verma', '2024-04-12', 'Aaliya Kherani', '2024-04-18', 'Reviewed',
            '[{"id": "c1", "author": "Aaliya Kherani", "username": "aaliya.kherani", "role": "Auditor", "comment": "Walkthrough verified and approved as compliant with SA 315.", "created_at": "2024-04-18T14:30:00"}]',
            '[]', '[]', '[]', ?, ?
        )
        """, (now_str, now_str))

        cursor.execute("""
        INSERT INTO working_papers (
            engagement_id, wp_reference, title, area, category, description,
            evidence, notes, attached_files_json, prepared_by, prepared_date,
            reviewed_by, review_date, status, reviewer_comments_json,
            linked_findings_json, linked_transactions_json, linked_checklists_json,
            created_at, updated_at
        ) VALUES (
            1, 'WP-B201', 'Bank Balance Confirmations & Reconciliation Verification',
            'Cash & Bank', 'Cash & Bank',
            'Verification of bank balance confirmations and outstanding items in HDFC Current Account.',
            'Obtained direct bank confirmation certificate as of 31-03-2025 and BRS statement.',
            'Unpresented cheques totaling Rs. 3,54,000 cleared in April 2025 bank statement. No stale cheques identified.',
            '[]', 'Pooja Verma', '2024-05-10', 'Aaliya Kherani', '', 'Under Review',
            '[{"id": "c2", "author": "Aaliya Kherani", "username": "aaliya.kherani", "role": "Auditor", "comment": "Please cross-verify bank charges ledger entries against statement.", "created_at": "2024-05-11T10:15:00"}]',
            '[]', '[2, 5]', '[2]', ?, ?
        )
        """, (now_str, now_str))

        cursor.execute("""
        INSERT INTO working_papers (
            engagement_id, wp_reference, title, area, category, description,
            evidence, notes, attached_files_json, prepared_by, prepared_date,
            reviewed_by, review_date, status, reviewer_comments_json,
            linked_findings_json, linked_transactions_json, linked_checklists_json,
            created_at, updated_at
        ) VALUES (
            1, 'WP-TAX-01', 'GST ITC GSTR-2B vs Books Reconciliation Audit Note',
            'Direct & Indirect Taxation', 'Direct & Indirect Taxation',
            'Analysis of input tax credit availed in GSTR-3B vs eligible credit in GSTR-2B.',
            'GSTR-2B portal download and purchase register matching schedule.',
            'Identified 2 supplier invoices where ITC claimed but not uploaded by vendor. Communicated to management for follow-up.',
            '[]', 'Pooja Verma', '2024-05-15', '', '', 'Prepared',
            '[]', '[1]', '[1, 3]', '[3]', ?, ?
        )
        """, (now_str, now_str))


    conn.commit()
    conn.close()

    # Export sample Excel & CSV files to sample_files/ directory
    export_sample_files()

def export_sample_files():
    """Generates sample .xlsx and .csv files in sample_files folder for testing file import."""
    sample_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sample_files")
    os.makedirs(sample_dir, exist_ok=True)

    # 1. Current Year General Ledger (Excel & CSV)
    df = pd.DataFrame(SAMPLE_TRANSACTIONS)
    excel_path = os.path.join(sample_dir, "apex_general_ledger_fy2425.xlsx")
    df.to_excel(excel_path, index=False)

    csv_path = os.path.join(sample_dir, "apex_general_ledger_fy2425.csv")
    df.to_csv(csv_path, index=False)

    # 2. Bank Statement Sample for BRS Reconciliation
    bank_records = [
        {"Date": "2024-04-05", "Cheque / Ref No": "NEFT-101", "Particulars": "Bharat Heavy Infra Ltd - Inward Remittance", "Withdrawal (Dr)": 0.0, "Deposit (Cr)": 500000.0, "Balance": 500000.0},
        {"Date": "2024-04-10", "Cheque / Ref No": "CHQ-8801", "Particulars": "Tata Steel Supply Depot - Cheque Clearing", "Withdrawal (Dr)": 354000.0, "Deposit (Cr)": 0.0, "Balance": 146000.0},
        {"Date": "2024-04-30", "Cheque / Ref No": "SAL-04-EFT", "Particulars": "Bulk Salary Transfer April 2024", "Withdrawal (Dr)": 450000.0, "Deposit (Cr)": 0.0, "Balance": -304000.0},
        {"Date": "2024-05-02", "Cheque / Ref No": "RTGS-992", "Particulars": "Kedia Realtors LLP - Office Rent", "Withdrawal (Dr)": 125000.0, "Deposit (Cr)": 0.0, "Balance": -429000.0},
        {"Date": "2024-05-31", "Cheque / Ref No": "CHG-BANK", "Particulars": "HDFC Bank Annual Folio & Ledger Maintenance Charges (Potential anomaly / Unrecorded)", "Withdrawal (Dr)": 3500.0, "Deposit (Cr)": 0.0, "Balance": -432500.0},
        {"Date": "2024-06-20", "Cheque / Ref No": "CHQ-8809", "Particulars": "Reliance Power Solutions - Diesel Payment", "Withdrawal (Dr)": 118000.0, "Deposit (Cr)": 0.0, "Balance": -550500.0}
    ]
    bank_df = pd.DataFrame(bank_records)
    bank_csv_path = os.path.join(sample_dir, "apex_bank_statement.csv")
    bank_df.to_csv(bank_csv_path, index=False)

    # 3. GSTR-2B Portal Download Sample
    gstr2b_records = [
        {"GSTIN of Supplier": "27AAACT1234F1Z8", "Trade Name": "Tata Steel Supply Depot", "Invoice Number": "PUR-501", "Invoice Date": "2024-04-08", "Invoice Value": 354000.0, "Taxable Value": 300000.0, "CGST": 27000.0, "SGST": 27000.0, "IGST": 0.0, "ITC Available": "Yes"},
        {"GSTIN of Supplier": "27AAEFK8899D1ZV", "Trade Name": "Kedia Realtors LLP", "Invoice Number": "RNT-05", "Invoice Date": "2024-05-01", "Invoice Value": 125000.0, "Taxable Value": 105932.0, "CGST": 9534.0, "SGST": 9534.0, "IGST": 0.0, "ITC Available": "Yes"},
        {"GSTIN of Supplier": "27AABCR9911C1ZX", "Trade Name": "Reliance Power Solutions", "Invoice Number": "INV-7744", "Invoice Date": "2024-06-18", "Invoice Value": 118000.0, "Taxable Value": 100000.0, "CGST": 9000.0, "SGST": 9000.0, "IGST": 0.0, "ITC Available": "Yes"},
        {"GSTIN of Supplier": "27AAACS4411P1Z9", "Trade Name": "Siemens Precision Engineering", "Invoice Number": "REP-998", "Invoice Date": "2024-10-10", "Invoice Value": 1850000.0, "Taxable Value": 1567796.0, "CGST": 141102.0, "SGST": 141102.0, "IGST": 0.0, "ITC Available": "Yes"},
        {"GSTIN of Supplier": "27AABCM6611J1ZK", "Trade Name": "Metro Media House", "Invoice Number": "ADV-02", "Invoice Date": "2024-11-17", "Invoice Value": 175000.0, "Taxable Value": 148305.0, "CGST": 13347.5, "SGST": 13347.5, "IGST": 0.0, "ITC Available": "Yes"},
        {"GSTIN of Supplier": "27AAACH2233M1Z2", "Trade Name": "Hindalco Industries Ltd", "Invoice Number": "PUR-912", "Invoice Date": "2024-12-18", "Invoice Value": 620000.0, "Taxable Value": 525423.0, "CGST": 47288.5, "SGST": 47288.5, "IGST": 0.0, "ITC Available": "Yes"}
    ]
    gstr2b_df = pd.DataFrame(gstr2b_records)
    gstr2b_csv_path = os.path.join(sample_dir, "apex_gstr2b_portal_download.csv")
    gstr2b_df.to_csv(gstr2b_csv_path, index=False)

    # 4. Prior Year General Ledger (FY 2023-24) for YoY Comparison
    py_gl_records = [
        {"date": "2023-05-10", "voucher_no": "PY-01", "invoice_no": "PY-INV-01", "ledger": "Sales Revenue", "account_group": "Revenue", "debit": 0.0, "credit": 1400000.0, "amount": 1400000.0, "party_name": "Bharat Heavy Infra Ltd"},
        {"date": "2023-06-15", "voucher_no": "PY-02", "invoice_no": "PY-PUR-01", "ledger": "Raw Material Purchase", "account_group": "Expense", "debit": 850000.0, "credit": 0.0, "amount": 850000.0, "party_name": "Tata Steel Supply Depot"},
        {"date": "2023-07-30", "voucher_no": "PY-03", "invoice_no": "PY-SAL-01", "ledger": "Salaries & Wages", "account_group": "Expense", "debit": 380000.0, "credit": 0.0, "amount": 380000.0, "party_name": "HDFC Bank Salary Account"},
        {"date": "2023-08-12", "voucher_no": "PY-04", "invoice_no": "PY-RNT-01", "ledger": "Office Rent", "account_group": "Expense", "debit": 110000.0, "credit": 0.0, "amount": 110000.0, "party_name": "Kedia Realtors LLP"},
        {"date": "2023-09-20", "voucher_no": "PY-05", "invoice_no": "PY-POW-01", "ledger": "Power & Fuel", "account_group": "Expense", "debit": 82000.0, "credit": 0.0, "amount": 82000.0, "party_name": "Reliance Power Solutions"},
        {"date": "2023-10-15", "voucher_no": "PY-06", "invoice_no": "PY-REP-01", "ledger": "Plant & Machinery Repairs", "account_group": "Expense", "debit": 650000.0, "credit": 0.0, "amount": 650000.0, "party_name": "Siemens Precision Engineering"},
        {"date": "2023-11-20", "voucher_no": "PY-07", "invoice_no": "PY-ADV-01", "ledger": "Advertisement & Marketing", "account_group": "Expense", "debit": 120000.0, "credit": 0.0, "amount": 120000.0, "party_name": "Metro Media House"}
    ]
    py_df = pd.DataFrame(py_gl_records)
    py_csv_path = os.path.join(sample_dir, "apex_prior_year_gl_fy2324.csv")
    py_df.to_csv(py_csv_path, index=False)

    print("Sample test files created at:", sample_dir)

if __name__ == "__main__":
    seed_sample_database()
