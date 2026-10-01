-- 002_performance_indexes.sql
-- Targeted database performance indexes based on actual audit query patterns.

-- 1. Transactions Indexing:
-- Improves: engagement transaction listing, date range slicing, ledger/party grouping, reconciliation lookups
CREATE INDEX IF NOT EXISTS idx_transactions_engagement ON transactions(engagement_id);
CREATE INDEX IF NOT EXISTS idx_transactions_engagement_date ON transactions(engagement_id, date, id);
CREATE INDEX IF NOT EXISTS idx_transactions_engagement_ledger ON transactions(engagement_id, ledger);
CREATE INDEX IF NOT EXISTS idx_transactions_engagement_party ON transactions(engagement_id, party_name);
CREATE INDEX IF NOT EXISTS idx_transactions_file_id ON transactions(file_id);

-- 2. Audit Trail Indexing:
-- Improves: cryptographic hash chain verification, engagement-scoped activity logs, chronological event streaming
CREATE INDEX IF NOT EXISTS idx_audit_logs_engagement ON audit_logs(engagement_id, id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);

-- 3. Working Papers & Evidence Indexing:
-- Improves: working paper lookup, status filtering, area filtering
CREATE INDEX IF NOT EXISTS idx_working_papers_engagement ON working_papers(engagement_id);
CREATE INDEX IF NOT EXISTS idx_working_papers_engagement_ref ON working_papers(engagement_id, wp_reference);
CREATE INDEX IF NOT EXISTS idx_working_papers_area ON working_papers(engagement_id, area);

-- 4. Reconciliations & Items Indexing:
-- Improves: BRS and GST reconciliation item lookups, match score queries, item type filtering
CREATE INDEX IF NOT EXISTS idx_recon_items_recon ON reconciliation_items(recon_id);
CREATE INDEX IF NOT EXISTS idx_recon_items_status ON reconciliation_items(recon_id, status);
CREATE INDEX IF NOT EXISTS idx_reconciliations_engagement ON reconciliations(engagement_id, recon_type);

-- 5. Audit Findings Indexing:
-- Improves: centralized finding queries, severity/category filtering, engagement risk dashboard
CREATE INDEX IF NOT EXISTS idx_findings_engagement ON audit_findings(engagement_id);
CREATE INDEX IF NOT EXISTS idx_findings_engagement_severity ON audit_findings(engagement_id, severity);
CREATE INDEX IF NOT EXISTS idx_findings_code ON audit_findings(engagement_id, finding_code);

-- 6. Files & Data Cleaning & Ledgers:
CREATE INDEX IF NOT EXISTS idx_files_engagement ON uploaded_files(engagement_id);
CREATE INDEX IF NOT EXISTS idx_ledgers_eng ON ledgers(engagement_id);
CREATE INDEX IF NOT EXISTS idx_checklists_eng ON audit_checklists(engagement_id);
CREATE INDEX IF NOT EXISTS idx_cleaning_eng ON data_cleaning_logs(engagement_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_eng ON anomaly_reviews(engagement_id);
CREATE INDEX IF NOT EXISTS idx_yoy_reviews_eng ON yoy_comparison_reviews(engagement_id);
