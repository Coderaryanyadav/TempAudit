import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.environ.get("FINAUDIT_DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "finauditpro.db"))

def _ensure_db_dir():
    db_dir = os.path.dirname(os.path.abspath(DB_PATH))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

def get_db_connection():
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn

def init_db():
    _ensure_db_dir()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Auditor', -- Admin, Auditor, Audit Staff
        password_hash TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        phone TEXT,
        last_login TEXT,
        token_version INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """)

    # Check and migrate columns if necessary
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [col[1] for col in cursor.fetchall()]
    if "last_login" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
    if "phone" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    if "token_version" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 1")

    # Revoked / Blacklisted Tokens (for explicit logout)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS revoked_tokens (
        jti TEXT PRIMARY KEY,
        username TEXT,
        revoked_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )
    """)

    # Clients
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        entity_type TEXT DEFAULT 'Private Limited Company',
        pan TEXT,
        gstin TEXT,
        address TEXT,
        contact_person TEXT,
        email TEXT,
        phone TEXT,
        industry TEXT DEFAULT 'Manufacturing',
        financial_year TEXT DEFAULT '2024-25',
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT
    )
    """)

    # Migrate clients table columns if missing
    cursor.execute("PRAGMA table_info(clients)")
    client_columns = [col[1] for col in cursor.fetchall()]
    if "entity_type" not in client_columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN entity_type TEXT DEFAULT 'Private Limited Company'")
    if "industry" not in client_columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN industry TEXT DEFAULT 'Manufacturing'")
    if "notes" not in client_columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN notes TEXT")
    if "financial_year" not in client_columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN financial_year TEXT DEFAULT '2024-25'")
    if "updated_at" not in client_columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN updated_at TEXT")

    # Engagements
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS engagements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        audit_type TEXT NOT NULL DEFAULT 'Statutory Audit',
        financial_year TEXT NOT NULL,
        period_start TEXT,
        period_end TEXT,
        status TEXT DEFAULT 'In Progress', -- Draft, In Progress, Under Review, Completed, Archived
        lead_auditor_id INTEGER,
        assigned_staff_id INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,

        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE,
        FOREIGN KEY (lead_auditor_id) REFERENCES users (id) ON DELETE SET NULL,
        FOREIGN KEY (assigned_staff_id) REFERENCES users (id) ON DELETE SET NULL
    )
    """)

    # Migrate engagements table columns if missing
    cursor.execute("PRAGMA table_info(engagements)")
    eng_columns = [col[1] for col in cursor.fetchall()]
    if "assigned_staff_id" not in eng_columns:
        cursor.execute("ALTER TABLE engagements ADD COLUMN assigned_staff_id INTEGER")
    if "notes" not in eng_columns:
        cursor.execute("ALTER TABLE engagements ADD COLUMN notes TEXT")
    if "materiality_threshold" not in eng_columns:
        cursor.execute("ALTER TABLE engagements ADD COLUMN materiality_threshold REAL DEFAULT 50000.0")
    if "updated_at" not in eng_columns:
        cursor.execute("ALTER TABLE engagements ADD COLUMN updated_at TEXT")

    # Uploaded Files
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS uploaded_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_type TEXT NOT NULL,
        file_path TEXT NOT NULL,
        data_category TEXT DEFAULT 'General Ledger',
        row_count INTEGER DEFAULT 0,
        successful_rows INTEGER DEFAULT 0,
        failed_rows INTEGER DEFAULT 0,
        warning_count INTEGER DEFAULT 0,
        mapping_json TEXT,
        errors_json TEXT,
        uploaded_by TEXT,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
    )
    """)

    # Migrate uploaded_files table columns if missing
    cursor.execute("PRAGMA table_info(uploaded_files)")
    up_cols = [col[1] for col in cursor.fetchall()]
    if "data_category" not in up_cols:
        cursor.execute("ALTER TABLE uploaded_files ADD COLUMN data_category TEXT DEFAULT 'General Ledger'")
    if "successful_rows" not in up_cols:
        cursor.execute("ALTER TABLE uploaded_files ADD COLUMN successful_rows INTEGER DEFAULT 0")
    if "failed_rows" not in up_cols:
        cursor.execute("ALTER TABLE uploaded_files ADD COLUMN failed_rows INTEGER DEFAULT 0")
    if "warning_count" not in up_cols:
        cursor.execute("ALTER TABLE uploaded_files ADD COLUMN warning_count INTEGER DEFAULT 0")
    if "errors_json" not in up_cols:
        cursor.execute("ALTER TABLE uploaded_files ADD COLUMN errors_json TEXT")

    # Transactions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        file_id INTEGER,
        date TEXT,
        voucher_no TEXT,
        invoice_no TEXT,
        ledger TEXT,
        account_group TEXT, -- Assets, Liabilities, Equity, Revenue, Expense
        description TEXT,
        debit REAL DEFAULT 0.0,
        credit REAL DEFAULT 0.0,
        amount REAL DEFAULT 0.0,
        tax_amount REAL DEFAULT 0.0,
        party_name TEXT,
        gstin TEXT,
        invoice_date TEXT,
        payment_date TEXT,
        reference_no TEXT,
        bank_ref TEXT,
        opening_balance REAL DEFAULT 0.0,
        closing_balance REAL DEFAULT 0.0,
        transaction_type TEXT,
        original_row_json TEXT,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
        FOREIGN KEY (file_id) REFERENCES uploaded_files (id) ON DELETE SET NULL
    )
    """)

    # Migrate transactions table columns if missing
    cursor.execute("PRAGMA table_info(transactions)")
    tx_cols = [col[1] for col in cursor.fetchall()]
    if "tax_amount" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN tax_amount REAL DEFAULT 0.0")
    if "original_row_json" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN original_row_json TEXT")

    # Ledgers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ledgers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        ledger_name TEXT NOT NULL,
        account_group TEXT NOT NULL,
        opening_balance REAL DEFAULT 0.0,
        total_debit REAL DEFAULT 0.0,
        total_credit REAL DEFAULT 0.0,
        closing_balance REAL DEFAULT 0.0,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
        UNIQUE(engagement_id, ledger_name)
    )
    """)

    # Reconciliations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reconciliations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        recon_type TEXT NOT NULL, -- Bank BRS, GST 2B vs Books, Vendor Statement
        title TEXT NOT NULL,
        bank_account_name TEXT,
        status TEXT DEFAULT 'Completed',
        total_bank_tx INTEGER DEFAULT 0,
        total_book_tx INTEGER DEFAULT 0,
        matched_count INTEGER DEFAULT 0,
        unmatched_bank_count INTEGER DEFAULT 0,
        unmatched_book_count INTEGER DEFAULT 0,
        amount_diff_count INTEGER DEFAULT 0,
        manual_confirmed_count INTEGER DEFAULT 0,
        unpresented_cheques_amount REAL DEFAULT 0.0,
        outstanding_deposits_amount REAL DEFAULT 0.0,
        bank_charges_amount REAL DEFAULT 0.0,
        interest_credited_amount REAL DEFAULT 0.0,
        book_balance REAL DEFAULT 0.0,
        bank_balance REAL DEFAULT 0.0,
        adjusted_bank_balance REAL DEFAULT 0.0,
        net_unreconciled_difference REAL DEFAULT 0.0,
        unreconciled_amount REAL DEFAULT 0.0,
        summary_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
    )
    """)

    # Migrate reconciliations table columns if missing
    cursor.execute("PRAGMA table_info(reconciliations)")
    recon_cols = [col[1] for col in cursor.fetchall()]
    for col_name, col_type in [
        ("bank_account_name", "TEXT"),
        ("total_bank_tx", "INTEGER DEFAULT 0"),
        ("total_book_tx", "INTEGER DEFAULT 0"),
        ("unmatched_bank_count", "INTEGER DEFAULT 0"),
        ("unmatched_book_count", "INTEGER DEFAULT 0"),
        ("amount_diff_count", "INTEGER DEFAULT 0"),
        ("manual_confirmed_count", "INTEGER DEFAULT 0"),
        ("unpresented_cheques_amount", "REAL DEFAULT 0.0"),
        ("outstanding_deposits_amount", "REAL DEFAULT 0.0"),
        ("bank_charges_amount", "REAL DEFAULT 0.0"),
        ("interest_credited_amount", "REAL DEFAULT 0.0"),
        ("book_balance", "REAL DEFAULT 0.0"),
        ("bank_balance", "REAL DEFAULT 0.0"),
        ("adjusted_bank_balance", "REAL DEFAULT 0.0"),
        ("net_unreconciled_difference", "REAL DEFAULT 0.0"),
        ("summary_json", "TEXT")
    ]:
        if col_name not in recon_cols:
            cursor.execute(f"ALTER TABLE reconciliations ADD COLUMN {col_name} {col_type}")

    # Reconciliation Items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reconciliation_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recon_id INTEGER NOT NULL,
        bank_tx_id INTEGER,
        book_tx_id INTEGER,
        date_a TEXT,
        date_b TEXT,
        ref_a TEXT,
        ref_b TEXT,
        party_a TEXT,
        party_b TEXT,
        description_a TEXT,
        description_b TEXT,
        amount_a REAL DEFAULT 0.0,
        amount_b REAL DEFAULT 0.0,
        difference REAL DEFAULT 0.0,
        date_diff_days INTEGER DEFAULT 0,
        match_level TEXT DEFAULT 'UNMATCHED', -- EXACT MATCH, HIGH CONFIDENCE, POSSIBLE MATCH, UNMATCHED
        match_score REAL DEFAULT 0.0,
        match_reason TEXT,
        item_type TEXT DEFAULT 'MATCHED', -- MATCHED, UNPRESENTED_CHEQUE, OUTSTANDING_DEPOSIT, BANK_CHARGES, INTEREST_CREDIT, UNRECORDED_BANK_ENTRY, UNRECORDED_BOOK_ENTRY, DUPLICATE_BOOK_ENTRY, DUPLICATE_BANK_ENTRY, AMOUNT_MISMATCH, UNKNOWN_ENTRY
        status TEXT NOT NULL, -- Suggested, Confirmed, Rejected, Manual Matched, Unmatched
        notes TEXT,
        FOREIGN KEY (recon_id) REFERENCES reconciliations (id) ON DELETE CASCADE
    )
    """)

    # Migrate reconciliation_items table columns if missing
    cursor.execute("PRAGMA table_info(reconciliation_items)")
    item_cols = [col[1] for col in cursor.fetchall()]
    for col_name, col_type in [
        ("bank_tx_id", "INTEGER"),
        ("book_tx_id", "INTEGER"),
        ("description_a", "TEXT"),
        ("description_b", "TEXT"),
        ("date_diff_days", "INTEGER DEFAULT 0"),
        ("match_level", "TEXT DEFAULT 'UNMATCHED'"),
        ("match_score", "REAL DEFAULT 0.0"),
        ("match_reason", "TEXT"),
        ("item_type", "TEXT DEFAULT 'MATCHED'"),
        ("tax_a", "REAL DEFAULT 0.0"),
        ("tax_b", "REAL DEFAULT 0.0"),
        ("tax_difference", "REAL DEFAULT 0.0"),
        ("gstin_a", "TEXT"),
        ("gstin_b", "TEXT"),
        ("taxable_a", "REAL DEFAULT 0.0"),
        ("taxable_b", "REAL DEFAULT 0.0"),
        ("taxable_difference", "REAL DEFAULT 0.0"),
        ("cgst_a", "REAL DEFAULT 0.0"),
        ("cgst_b", "REAL DEFAULT 0.0"),
        ("cgst_difference", "REAL DEFAULT 0.0"),
        ("sgst_a", "REAL DEFAULT 0.0"),
        ("sgst_b", "REAL DEFAULT 0.0"),
        ("sgst_difference", "REAL DEFAULT 0.0"),
        ("igst_a", "REAL DEFAULT 0.0"),
        ("igst_b", "REAL DEFAULT 0.0"),
        ("igst_difference", "REAL DEFAULT 0.0"),
        ("match_category", "TEXT DEFAULT 'Mismatched'")
    ]:
        if col_name not in item_cols:
            cursor.execute(f"ALTER TABLE reconciliation_items ADD COLUMN {col_name} {col_type}")

    # GST Configurable Rule Definitions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gst_rule_configurations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_key TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        config_json TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        version TEXT NOT NULL DEFAULT 'v1.0',
        updated_by TEXT DEFAULT 'system',
        updated_at TEXT NOT NULL
    )
    """)

    # Audit Findings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        finding_code TEXT NOT NULL,
        module TEXT DEFAULT 'General',
        category TEXT NOT NULL, -- Statutory Compliance, Accounting Standard, Mathematical, Outlier / ML, Reconciliation, Missing Data, Variance Analysis
        severity TEXT NOT NULL, -- LOW, MEDIUM, HIGH, CRITICAL
        risk_score REAL DEFAULT 0.0,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        affected_records_json TEXT,
        expected_value TEXT,
        actual_value TEXT,
        difference TEXT,
        reason TEXT,
        evidence_json TEXT,
        rule_used TEXT,
        engine_type TEXT NOT NULL, -- DETERMINISTIC, STATISTICAL_ML, LOCAL_AI
        risk_factors_json TEXT,
        ai_explanation TEXT,
        recommended_action TEXT,
        status TEXT DEFAULT 'Open', -- Open, Under Review, Resolved, Waived
        auditor_comment TEXT,
        reviewed_at TEXT,
        reviewed_by TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
    )
    """)

    # Migrate audit_findings table columns if missing
    cursor.execute("PRAGMA table_info(audit_findings)")
    finding_cols = [col[1] for col in cursor.fetchall()]
    for col_name, col_type in [
        ("module", "TEXT DEFAULT 'General'"),
        ("risk_factors_json", "TEXT"),
        ("reviewed_at", "TEXT"),
        ("reviewed_by", "TEXT")
    ]:
        if col_name not in finding_cols:
            cursor.execute(f"ALTER TABLE audit_findings ADD COLUMN {col_name} {col_type}")

    # Audit Checklists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_checklists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        item_code TEXT NOT NULL,
        question TEXT NOT NULL,
        guidance TEXT,
        status TEXT DEFAULT 'Not Started', -- Not Started, In Progress, Completed, Not Applicable, Requires Review
        assigned_staff TEXT,
        evidence TEXT,
        comment TEXT,
        due_date TEXT,
        completed_date TEXT,
        auditor_remarks TEXT,
        reference_wp TEXT,
        checked_by TEXT,
        checked_at TEXT,
        is_custom INTEGER DEFAULT 0,
        risk_finding_id INTEGER,
        created_at TEXT,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("PRAGMA table_info(audit_checklists)")
    chk_columns = [col[1] for col in cursor.fetchall()]
    for col_name, col_type in [
        ("assigned_staff", "TEXT"),
        ("evidence", "TEXT"),
        ("comment", "TEXT"),
        ("due_date", "TEXT"),
        ("completed_date", "TEXT"),
        ("is_custom", "INTEGER DEFAULT 0"),
        ("risk_finding_id", "INTEGER"),
        ("created_at", "TEXT")
    ]:
        if col_name not in chk_columns:
            cursor.execute(f"ALTER TABLE audit_checklists ADD COLUMN {col_name} {col_type}")

    # Working Papers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS working_papers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        wp_reference TEXT NOT NULL,
        title TEXT NOT NULL,
        area TEXT NOT NULL DEFAULT 'General',
        category TEXT,
        description TEXT,
        evidence TEXT,
        attached_files_json TEXT DEFAULT '[]',
        prepared_by TEXT,
        prepared_date TEXT,
        reviewed_by TEXT,
        review_date TEXT,
        status TEXT DEFAULT 'Prepared', -- Prepared, Under Review, Reviewed, Needs Correction
        notes TEXT,
        reviewer_comments_json TEXT DEFAULT '[]',
        linked_findings_json TEXT DEFAULT '[]',
        linked_transactions_json TEXT DEFAULT '[]',
        linked_checklists_json TEXT DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
    )
    """)

    # Migrate working_papers table columns if missing
    cursor.execute("PRAGMA table_info(working_papers)")
    wp_columns = [col[1] for col in cursor.fetchall()]
    for col_name, col_type in [
        ("area", "TEXT DEFAULT 'General'"),
        ("evidence", "TEXT"),
        ("prepared_date", "TEXT"),
        ("review_date", "TEXT"),
        ("notes", "TEXT"),
        ("reviewer_comments_json", "TEXT DEFAULT '[]'"),
        ("linked_findings_json", "TEXT DEFAULT '[]'"),
        ("linked_transactions_json", "TEXT DEFAULT '[]'"),
        ("linked_checklists_json", "TEXT DEFAULT '[]'")
    ]:
        if col_name not in wp_columns:
            cursor.execute(f"ALTER TABLE working_papers ADD COLUMN {col_name} {col_type}")

    # Standardize legacy working paper statuses & populate area if null
    cursor.execute("UPDATE working_papers SET status = 'Prepared' WHERE status = 'Draft' OR status IS NULL OR status = ''")
    cursor.execute("UPDATE working_papers SET status = 'Reviewed' WHERE status = 'Final'")
    cursor.execute("UPDATE working_papers SET area = category WHERE (area IS NULL OR area = 'General' OR area = '') AND category IS NOT NULL AND category != ''")
    cursor.execute("UPDATE working_papers SET attached_files_json = '[]' WHERE attached_files_json IS NULL OR attached_files_json = ''")
    cursor.execute("UPDATE working_papers SET reviewer_comments_json = '[]' WHERE reviewer_comments_json IS NULL OR reviewer_comments_json = ''")
    cursor.execute("UPDATE working_papers SET linked_findings_json = '[]' WHERE linked_findings_json IS NULL OR linked_findings_json = ''")
    cursor.execute("UPDATE working_papers SET linked_transactions_json = '[]' WHERE linked_transactions_json IS NULL OR linked_transactions_json = ''")
    cursor.execute("UPDATE working_papers SET linked_checklists_json = '[]' WHERE linked_checklists_json IS NULL OR linked_checklists_json = ''")


    # Reports
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        report_title TEXT NOT NULL,
        report_type TEXT NOT NULL,
        generated_by TEXT,
        file_path TEXT NOT NULL,
        summary_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
    )
    """)

    # Audit Logs (Append-Only Immutable System with Hash Chaining)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        user_id INTEGER,
        username TEXT,
        action TEXT NOT NULL,
        module TEXT DEFAULT 'General',
        record_id TEXT,
        old_value TEXT,
        new_value TEXT,
        details TEXT,
        engagement_id INTEGER,
        ip_address TEXT,
        entity_type TEXT,
        entity_id INTEGER,
        previous_hash TEXT,
        entry_hash TEXT
    )
    """)

    # Migrate audit_logs columns if missing
    cursor.execute("PRAGMA table_info(audit_logs)")
    audit_cols = [col[1] for col in cursor.fetchall()]
    for col_name, col_type in [
        ("module", "TEXT"),
        ("record_id", "TEXT"),
        ("old_value", "TEXT"),
        ("new_value", "TEXT"),
        ("engagement_id", "INTEGER"),
        ("ip_address", "TEXT"),
        ("username", "TEXT"),
        ("user_id", "INTEGER"),
        ("previous_hash", "TEXT"),
        ("entry_hash", "TEXT")
    ]:
        if col_name not in audit_cols:
            cursor.execute(f"ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type}")


    # Enforce SQLite append-only immutability triggers
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_update
    BEFORE UPDATE ON audit_logs
    BEGIN
        SELECT RAISE(FAIL, 'Audit trail logs are immutable and cannot be modified.');
    END;
    """)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_delete
    BEFORE DELETE ON audit_logs
    BEGIN
        SELECT RAISE(FAIL, 'Audit trail logs are immutable and cannot be deleted.');
    END;
    """)


    # Financial Statement Auditor Explanations & Notes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS financial_statement_explanations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        item_key TEXT NOT NULL,
        financial_year TEXT NOT NULL,
        explanation_category TEXT,
        auditor_explanation TEXT NOT NULL,
        review_status TEXT DEFAULT 'Reviewed', -- In Review, Reviewed, Flagged
        updated_by TEXT DEFAULT 'admin',
        updated_at TEXT NOT NULL,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
        UNIQUE(engagement_id, item_key, financial_year)
    )
    """)

    # App Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT NOT NULL
    )
    """)

    # Duplicate Group Reviews & Auditor Actions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS duplicate_group_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        group_code TEXT NOT NULL,
        group_type TEXT NOT NULL,
        primary_transaction_id INTEGER,
        duplicate_transaction_id INTEGER,
        similarity_pct REAL DEFAULT 100.0,
        detection_reason TEXT,
        status TEXT DEFAULT 'Unreviewed', -- Unreviewed, Confirmed Duplicate, Marked Valid, Ignored
        auditor_comment TEXT,
        reviewed_by TEXT,
        reviewed_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
        UNIQUE(engagement_id, group_code, duplicate_transaction_id)
    )
    """)

    # Missing Sequence Reviews & Auditor Explanations (Invoice, Voucher, Cheque Gaps)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS missing_sequence_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        sequence_type TEXT NOT NULL, -- INVOICE_GAP, VOUCHER_GAP, CHEQUE_GAP
        series_prefix TEXT,
        expected_from TEXT,
        expected_to TEXT,
        missing_count INTEGER DEFAULT 1,
        missing_items_json TEXT,
        severity TEXT DEFAULT 'MEDIUM',
        status TEXT DEFAULT 'Open', -- Open, In Review, Documented / Valid Gap, Resolved
        auditor_comment TEXT,
        reviewed_by TEXT,
        reviewed_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
        UNIQUE(engagement_id, sequence_type, series_prefix, expected_from, expected_to)
    )
    """)

    # Data Cleaning & Normalization Transformation Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_cleaning_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        file_id INTEGER,
        transaction_id INTEGER,
        row_number INTEGER,
        field_name TEXT NOT NULL,
        original_value TEXT,
        normalized_value TEXT,
        transformation_rule TEXT NOT NULL,
        is_questionable INTEGER DEFAULT 0,
        confidence_score REAL DEFAULT 1.0,
        review_status TEXT DEFAULT 'Auto-Applied', -- Auto-Applied, Accepted, Overridden, Reverted
        auditor_comment TEXT,
        reviewed_by TEXT,
        reviewed_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
        FOREIGN KEY (file_id) REFERENCES uploaded_files (id) ON DELETE CASCADE,
        FOREIGN KEY (transaction_id) REFERENCES transactions (id) ON DELETE CASCADE
    )
    """)

    # Anomaly Reviews & Auditor Actions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS anomaly_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        anomaly_id TEXT NOT NULL,
        transaction_id INTEGER,
        pattern_type TEXT,
        level TEXT,
        anomaly_score REAL DEFAULT 0.0,
        severity TEXT DEFAULT 'MEDIUM',
        status TEXT DEFAULT 'Open', -- Open, Confirmed Anomaly, Marked Normal, Ignored
        auditor_comment TEXT,
        ai_memo TEXT,
        reviewed_by TEXT,
        reviewed_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
        UNIQUE(engagement_id, anomaly_id)
    )
    """)
    # YoY Financial Comparison Reviews & Auditor Comments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS yoy_comparison_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER NOT NULL,
        item_key TEXT NOT NULL,
        category TEXT NOT NULL, -- Executive Total, Major Ledger, Party Balance, Operational Metric
        account_name TEXT NOT NULL,
        status TEXT DEFAULT 'Unreviewed', -- Unreviewed, Reviewed, Flagged for Inquiry, Verified
        auditor_comment TEXT,
        ai_reason TEXT,
        reviewed_by TEXT,
        reviewed_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
        UNIQUE(engagement_id, item_key)
    )
    """)
    # Performance & Scale Indexes (Flaw 35)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_engagement ON transactions(engagement_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_engagement_date ON transactions(engagement_id, date, id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_findings_engagement ON audit_findings(engagement_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_engagement ON audit_logs(engagement_id, id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_working_papers_engagement ON working_papers(engagement_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recon_items_recon ON reconciliation_items(recon_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledgers_eng ON ledgers(engagement_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_checklists_eng ON audit_checklists(engagement_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cleaning_eng ON data_cleaning_logs(engagement_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_engagement ON uploaded_files(engagement_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_yoy_reviews_eng ON yoy_comparison_reviews(engagement_id)")

    # Seed Initial Administrator Account if no users exist
    user_count = cursor.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    if user_count == 0:
        from backend.app.auth import hash_password
        admin_hash = hash_password("admin123")
        auditor_hash = hash_password("audit123")
        staff_hash = hash_password("staff123")
        now_str = datetime.now().isoformat()
        cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, email, full_name, role, password_hash, is_active, created_at)
        VALUES (1, 'admin', 'admin@finauditpro.local', 'System Administrator (FCA)', 'Admin', ?, 1, ?)
        """, (admin_hash, now_str))
        
        cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, email, full_name, role, password_hash, is_active, created_at)
        VALUES (2, 'auditor', 'senior@finauditpro.in', 'Rohan Mehta (Senior Audit Manager)', 'Auditor', ?, 1, ?)
        """, (auditor_hash, now_str))

        cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, email, full_name, role, password_hash, is_active, created_at)
        VALUES (3, 'staff', 'assistant@finauditpro.in', 'Pooja Verma (Audit Assistant)', 'Audit Staff', ?, 1, ?)
        """, (staff_hash, now_str))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
