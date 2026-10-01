-- =============================================================================
-- FinAuditPro Complete Database Teardown Script
-- Drops all triggers, views, and tables cleanly
-- =============================================================================

PRAGMA foreign_keys = OFF;

-- Drop Immutability Triggers First
DROP TRIGGER IF EXISTS trg_prevent_audit_log_update;
DROP TRIGGER IF EXISTS trg_prevent_audit_log_delete;

-- Drop All Tables
DROP TABLE IF EXISTS background_jobs;
DROP TABLE IF EXISTS evidence_items;
DROP TABLE IF EXISTS rate_limits;
DROP TABLE IF EXISTS yoy_comparison_reviews;
DROP TABLE IF EXISTS anomaly_reviews;
DROP TABLE IF EXISTS data_cleaning_logs;
DROP TABLE IF EXISTS missing_sequence_reviews;
DROP TABLE IF EXISTS duplicate_group_reviews;
DROP TABLE IF EXISTS app_settings;
DROP TABLE IF EXISTS financial_statement_explanations;
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS reports;
DROP TABLE IF EXISTS working_papers;
DROP TABLE IF EXISTS audit_checklists;
DROP TABLE IF EXISTS audit_findings;
DROP TABLE IF EXISTS gst_rule_configurations;
DROP TABLE IF EXISTS reconciliation_items;
DROP TABLE IF EXISTS reconciliations;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS ledgers;
DROP TABLE IF EXISTS uploaded_files;
DROP TABLE IF EXISTS engagements;
DROP TABLE IF EXISTS clients;
DROP TABLE IF EXISTS revoked_tokens;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS schema_migrations;

-- Clean Up SQLite Internal Storage
VACUUM;
PRAGMA foreign_keys = ON;
