-- 001_initial_schema.sql
-- FinAuditPro Core Schema Definition

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'Auditor',
    password_hash TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    phone TEXT,
    last_login TEXT,
    token_version INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,
    username TEXT,
    revoked_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

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
);

CREATE TABLE IF NOT EXISTS engagements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    audit_type TEXT NOT NULL DEFAULT 'Statutory Audit',
    financial_year TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    status TEXT DEFAULT 'In Progress',
    lead_auditor_id INTEGER,
    assigned_staff_id INTEGER,
    materiality_threshold REAL DEFAULT 50000.0,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE,
    FOREIGN KEY (lead_auditor_id) REFERENCES users (id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_staff_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS uploaded_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    source_type TEXT DEFAULT 'USER_UPLOAD',
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
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    file_id INTEGER,
    date TEXT,
    voucher_no TEXT,
    invoice_no TEXT,
    ledger TEXT,
    account_group TEXT,
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
);

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
);

CREATE TABLE IF NOT EXISTS reconciliations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    recon_type TEXT NOT NULL,
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
);

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
    match_level TEXT DEFAULT 'UNMATCHED',
    match_score REAL DEFAULT 0.0,
    match_reason TEXT,
    item_type TEXT DEFAULT 'MATCHED',
    tax_a REAL DEFAULT 0.0,
    tax_b REAL DEFAULT 0.0,
    tax_difference REAL DEFAULT 0.0,
    gstin_a TEXT,
    gstin_b TEXT,
    taxable_a REAL DEFAULT 0.0,
    taxable_b REAL DEFAULT 0.0,
    taxable_difference REAL DEFAULT 0.0,
    cgst_a REAL DEFAULT 0.0,
    cgst_b REAL DEFAULT 0.0,
    cgst_difference REAL DEFAULT 0.0,
    sgst_a REAL DEFAULT 0.0,
    sgst_b REAL DEFAULT 0.0,
    sgst_difference REAL DEFAULT 0.0,
    igst_a REAL DEFAULT 0.0,
    igst_b REAL DEFAULT 0.0,
    igst_difference REAL DEFAULT 0.0,
    match_category TEXT DEFAULT 'Mismatched',
    status TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (recon_id) REFERENCES reconciliations (id) ON DELETE CASCADE
);

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
);

CREATE TABLE IF NOT EXISTS audit_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    finding_code TEXT NOT NULL,
    module TEXT DEFAULT 'General',
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
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
    engine_type TEXT NOT NULL,
    risk_factors_json TEXT,
    ai_explanation TEXT,
    recommended_action TEXT,
    status TEXT DEFAULT 'Open',
    auditor_comment TEXT,
    reviewed_at TEXT,
    reviewed_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_checklists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    item_code TEXT NOT NULL,
    question TEXT NOT NULL,
    guidance TEXT,
    status TEXT DEFAULT 'Not Started',
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
);

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
    status TEXT DEFAULT 'Prepared',
    notes TEXT,
    reviewer_comments_json TEXT DEFAULT '[]',
    linked_findings_json TEXT DEFAULT '[]',
    linked_transactions_json TEXT DEFAULT '[]',
    linked_checklists_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
);

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
);

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
);

CREATE TABLE IF NOT EXISTS financial_statement_explanations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    item_key TEXT NOT NULL,
    financial_year TEXT NOT NULL,
    explanation_category TEXT,
    auditor_explanation TEXT NOT NULL,
    review_status TEXT DEFAULT 'Reviewed',
    updated_by TEXT DEFAULT 'admin',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
    UNIQUE(engagement_id, item_key, financial_year)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS duplicate_group_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    group_code TEXT NOT NULL,
    group_type TEXT NOT NULL,
    primary_transaction_id INTEGER,
    duplicate_transaction_id INTEGER,
    similarity_pct REAL DEFAULT 100.0,
    detection_reason TEXT,
    status TEXT DEFAULT 'Unreviewed',
    auditor_comment TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
    UNIQUE(engagement_id, group_code, duplicate_transaction_id)
);

CREATE TABLE IF NOT EXISTS missing_sequence_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    sequence_type TEXT NOT NULL,
    series_prefix TEXT,
    expected_from TEXT,
    expected_to TEXT,
    missing_count INTEGER DEFAULT 1,
    missing_items_json TEXT,
    severity TEXT DEFAULT 'MEDIUM',
    status TEXT DEFAULT 'Open',
    auditor_comment TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
    UNIQUE(engagement_id, sequence_type, series_prefix, expected_from, expected_to)
);

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
    review_status TEXT DEFAULT 'Auto-Applied',
    auditor_comment TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES uploaded_files (id) ON DELETE CASCADE,
    FOREIGN KEY (transaction_id) REFERENCES transactions (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS anomaly_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    anomaly_id TEXT NOT NULL,
    transaction_id INTEGER,
    pattern_type TEXT,
    level TEXT,
    anomaly_score REAL DEFAULT 0.0,
    severity TEXT DEFAULT 'MEDIUM',
    status TEXT DEFAULT 'Open',
    auditor_comment TEXT,
    ai_memo TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
    UNIQUE(engagement_id, anomaly_id)
);

CREATE TABLE IF NOT EXISTS yoy_comparison_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    item_key TEXT NOT NULL,
    category TEXT NOT NULL,
    account_name TEXT NOT NULL,
    status TEXT DEFAULT 'Unreviewed',
    auditor_comment TEXT,
    ai_reason TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
    UNIQUE(engagement_id, item_key)
);

-- Audit log immutability triggers
CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_update
BEFORE UPDATE ON audit_logs
BEGIN
    SELECT RAISE(FAIL, 'Audit trail logs are immutable and cannot be modified.');
END;

CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_delete
BEFORE DELETE ON audit_logs
BEGIN
    SELECT RAISE(FAIL, 'Audit trail logs are immutable and cannot be deleted.');
END;
