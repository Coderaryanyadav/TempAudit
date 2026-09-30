# FinAuditPro - Database Schema Documentation

FinAuditPro utilizes an ACID-compliant local **SQLite** database (`backend/finauditpro.db`).

---

## 1. Entity Relationship Overview

```
[users] ──(1:N)── [engagements] ──(1:N)── [transactions]
                       │                     │
                       ├──(1:N)── [findings] ◄┘ (Linked by transaction_id)
                       │             │
                       ├──(1:N)── [working_papers] ◄── Linked findings/txns/checklists
                       │             │
                       ├──(1:N)── [audit_checklists]
                       │
                       └──(1:N)── [reports]

[clients] ──(1:N)── [engagements]

[audit_logs] ── Independent append-only tamper-resistant system ledger
```

---

## 2. Table Specifications

### 2.1 `users`
Stores auditor credentials and role definitions.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `username` (TEXT UNIQUE NOT NULL)
- `email` (TEXT)
- `full_name` (TEXT NOT NULL)
- `role` (TEXT NOT NULL): `'Admin'`, `'Auditor'`, `'Audit Staff'`
- `password_hash` (TEXT NOT NULL)
- `is_active` (INTEGER DEFAULT 1)
- `phone` (TEXT)
- `last_login` (TEXT)
- `created_at` (TEXT)

### 2.2 `clients`
Multi-tenant master records for corporate and individual audit entities.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `name` (TEXT NOT NULL)
- `pan` (TEXT NOT NULL)
- `gstin` (TEXT)
- `entity_type` (TEXT): `'Private Limited Company'`, `'Public Limited'`, `'LLP'`, `'Partnership'`, `'Proprietorship'`
- `contact_person` (TEXT)
- `email` (TEXT)
- `phone` (TEXT)
- `address` (TEXT)
- `created_at` (TEXT), `updated_at` (TEXT)

### 2.3 `engagements`
Audit engagements scoped to a specific financial year and client.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `client_id` (INTEGER NOT NULL REFERENCES `clients(id)`)
- `title` (TEXT NOT NULL)
- `audit_type` (TEXT NOT NULL): `'Statutory Audit'`, `'Tax Audit'`, `'Internal Audit'`, `'Concurrent Audit'`
- `financial_year` (TEXT NOT NULL): e.g., `'2024-25'`
- `period_start` (TEXT NOT NULL), `period_end` (TEXT NOT NULL)
- `status` (TEXT DEFAULT `'Planning'`): `'Planning'`, `'In Progress'`, `'Under Review'`, `'Completed'`, `'Archived'`
- `lead_auditor_id` (INTEGER REFERENCES `users(id)`)
- `created_at` (TEXT), `updated_at` (TEXT)

### 2.4 `transactions`
Normalized daybook and ledger transactions ingested from financial systems.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `engagement_id` (INTEGER NOT NULL REFERENCES `engagements(id)`)
- `date` (TEXT NOT NULL)
- `voucher_no` (TEXT)
- `invoice_no` (TEXT)
- `ledger` (TEXT NOT NULL)
- `account_group` (TEXT): `'Asset'`, `'Liability'`, `'Equity'`, `'Revenue'`, `'Expense'`
- `description` (TEXT)
- `debit` (REAL DEFAULT 0.0)
- `credit` (REAL DEFAULT 0.0)
- `amount` (REAL DEFAULT 0.0)
- `party_name` (TEXT)
- `gstin` (TEXT)
- `invoice_date` (TEXT), `payment_date` (TEXT)
- `transaction_type` (TEXT): `'Journal'`, `'Payment'`, `'Receipt'`, `'Sales'`, `'Purchase'`, `'Cash'`
- `is_flagged` (INTEGER DEFAULT 0)
- `anomaly_score` (REAL DEFAULT 0.0)

### 2.5 `findings`
Centralized repository of all rule breaches, reconciliation variances, and statistical outliers.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `engagement_id` (INTEGER NOT NULL REFERENCES `engagements(id)`)
- `finding_code` (TEXT UNIQUE)
- `rule_name` (TEXT NOT NULL)
- `module` (TEXT NOT NULL): `'Deterministic Rules'`, `'ML Outliers'`, `'Bank Reconciliation'`, `'GST Reconciliation'`, `'YoY Comparison'`
- `category` (TEXT NOT NULL): `'Statutory Compliance'`, `'Tax Audit'`, `'Reconciliation'`, `'Internal Controls'`
- `severity` (TEXT NOT NULL): `'High'`, `'Medium'`, `'Low'`, `'Info'`
- `title` (TEXT NOT NULL)
- `description` (TEXT NOT NULL)
- `evidence` (TEXT NOT NULL)
- `transaction_id` (INTEGER REFERENCES `transactions(id)`)
- `amount_involved` (REAL DEFAULT 0.0)
- `status` (TEXT DEFAULT `'Open'`): `'Open'`, `'In Progress'`, `'Resolved'`, `'Accepted Risk'`, `'False Positive'`
- `auditor_notes` (TEXT)
- `created_at` (TEXT), `updated_at` (TEXT)

### 2.6 `working_papers`
Statutory audit documentation in compliance with Standard on Auditing (SA) 230.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `engagement_id` (INTEGER NOT NULL REFERENCES `engagements(id)`)
- `wp_reference` (TEXT NOT NULL)
- `title` (TEXT NOT NULL)
- `area` / `category` (TEXT NOT NULL)
- `description` (TEXT)
- `evidence` (TEXT)
- `notes` (TEXT)
- `attached_files_json` (TEXT DEFAULT `'[]'`)
- `prepared_by` (TEXT NOT NULL), `prepared_date` (TEXT NOT NULL)
- `reviewed_by` (TEXT), `review_date` (TEXT)
- `status` (TEXT DEFAULT `'Prepared'`): `'Prepared'`, `'Under Review'`, `'Reviewed'`, `'Needs Correction'`
- `reviewer_comments_json` (TEXT DEFAULT `'[]'`)
- `linked_findings_json` (TEXT DEFAULT `'[]'`)
- `linked_transactions_json` (TEXT DEFAULT `'[]'`)
- `linked_checklists_json` (TEXT DEFAULT `'[]'`)
- `created_at` (TEXT), `updated_at` (TEXT)

### 2.7 `audit_checklists`
Statutory and regulatory audit checklist questionnaire.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `engagement_id` (INTEGER NOT NULL REFERENCES `engagements(id)`)
- `category` (TEXT NOT NULL)
- `item_code` (TEXT NOT NULL)
- `question` (TEXT NOT NULL)
- `guidance` (TEXT)
- `status` (TEXT DEFAULT `'Pending'`): `'Compliant'`, `'Non-Compliant'`, `'Not Applicable'`, `'Under Review'`, `'Pending'`
- `auditor_remarks` (TEXT)
- `checked_by` (TEXT), `checked_at` (TEXT)

### 2.8 `audit_logs` (Immutable Append-Only Ledger)
Tamper-resistant audit trail protected by SQLite database triggers.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `timestamp` (TEXT NOT NULL)
- `user_id` (INTEGER)
- `username` (TEXT NOT NULL)
- `action` (TEXT NOT NULL)
- `module` (TEXT NOT NULL)
- `record_id` (TEXT)
- `old_value` (TEXT)
- `new_value` (TEXT)
- `ip_address` (TEXT DEFAULT `'127.0.0.1'`)

---

## 3. Database Triggers (Immutability Enforcers)
The following triggers are permanently compiled into the SQLite database to prevent tampering with `audit_logs`:
```sql
CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_update
BEFORE UPDATE ON audit_logs
BEGIN
    SELECT RAISE(FAIL, 'Audit log entries cannot be modified - immutable audit trail enforced.');
END;

CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_delete
BEFORE DELETE ON audit_logs
BEGIN
    SELECT RAISE(FAIL, 'Audit log entries cannot be deleted - immutable audit trail enforced.');
END;
```
