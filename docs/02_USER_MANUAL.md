# FinAuditPro - End-to-End User Manual

## 1. Introduction & Overview
**FinAuditPro** is an AI-assisted, offline-first statutory and tax audit workstation engineered specifically for Chartered Accountants (CAs), audit managers, and audit assistants. It provides deterministic financial analysis, multi-layered reconciliation, statutory rule checks, statistical anomaly detection, working paper documentation, and audit report generation with zero cloud data transmission.

---

## 2. The Complete 16-Step Audit Workflow

```
LOGIN
  ↓
CLIENT SELECTION / CREATION
  ↓
ENGAGEMENT SETUP
  ↓
IMPORT FINANCIAL DATA (Excel / CSV / JSON / PDF)
  ↓
PRE-IMPORT DATA VALIDATION & COLUMN MAPPING
  ↓
NORMALIZATION & INGESTION
  ↓
TRIAL BALANCE & GENERAL LEDGER ANALYSIS
  ↓
MULTI-WAY RECONCILIATION (Bank BRS, GST ITC, Sales/Purchase)
  ↓
FINANCIAL STATEMENT ANALYSIS (Ratios, Working Capital, Health)
  ↓
ANOMALY DETECTION (Deterministic Rules + Isolation Forest + Benford's Law)
  ↓
YEAR-ON-YEAR (YoY) COMPARISON
  ↓
RISK & FINDINGS MANAGEMENT (Finding IDs, Traceability, Status Workflow)
  ↓
AUDIT CHECKLIST EXECUTION (Companies Act / CARO 2020 / Tax Audit 3CD)
  ↓
WORKING PAPERS DOCUMENTATION (SA 230 Evidence, Maker-Checker Review)
  ↓
LOCAL AI ASSISTANT (Deterministic Fact Retrieval & Explanations)
  ↓
AUDIT REPORT GENERATION (10 Comprehensive Report Types)
  ↓
AUDIT TRAIL & SYSTEM BACKUP
```

---

## 3. Step-by-Step Module Walkthrough

### 3.1 Login & Authentication
1. Enter your assigned username (`admin`, `auditor`, or `staff`) and password.
2. The system issues a secure local JWT token and enforces Role-Based Access Control (RBAC):
   - **Admin / Partner:** Full access, checklist sign-off, working paper final approval, backup/restore, user management.
   - **Auditor / Manager:** Full audit execution, finding management, working paper review.
   - **Audit Staff:** Data import, checklist draft, working paper preparation.

### 3.2 Client & Engagement Selection
1. On the top navigation bar or **Clients** view, select an active client (e.g., *Apex Engineering & Logistics Pvt Ltd*).
2. Select or create the relevant Engagement (e.g., *Statutory & Tax Audit FY 2024-25*).
3. **Data Isolation:** All operations across all modules strictly scope database queries using `client_id` and `engagement_id`.

### 3.3 Data Import & Pre-Validation
1. Navigate to **Data Import**.
2. Drag and drop your General Ledger or Daybook (`.xlsx`, `.csv`, `.json`, `.pdf`).
3. The system executes pre-import structural validations:
   - Date formats (YYYY-MM-DD, DD/MM/YYYY)
   - Numerical integrity (debit/credit values)
   - Mandatory field presence (Voucher No, Date, Ledger, Amount)
4. Confirm column mappings and click **Import Transactions**.

### 3.4 Trial Balance & Ledger Analysis
1. Navigate to **Trial Balance**:
   - Immediate verification of Debit = Credit balance.
   - Identification of abnormal debit/credit balances and unadjusted suspense accounts.
2. Navigate to **General Ledger**:
   - Drill down into specific accounts.
   - Flag round-number manual JVs, Sunday postings, and reverse entries.

### 3.5 Reconciliation Engines
- **Bank Reconciliation (BRS):** Auto-match bank statements against book bank ledgers using exact amount & date tolerance matching. Flag unpresented cheques, uncredited deposits, and unrecorded bank charges.
- **GST Reconciliation (GSTR-2B vs Books):** Compare purchase ledger ITC with GSTR-2B portal downloads. Classify into Exact Match, Tax Mismatch, Supplier Missing in Books, or ITC Not Uploaded by Supplier.
- **Sales & Purchase Reconciliation:** Cross-reconcile revenue and vendor sub-ledgers.

### 3.6 Anomaly Detection & Risk Engine
- **Deterministic Statutory Rules:**
  - **Section 40A(3):** Cash payments exceeding ₹10,000.
  - **Section 269ST:** Cash receipts of ₹2,00,000 or more.
  - **Duplicate Vouchers & Invoices:** Exact and fuzzy text matching.
  - **Invalid / Missing GSTINs:** 15-character statutory checksum validation.
- **Statistical & ML Anomaly Detection:**
  - **Benford's Law:** First-digit distribution deviation test.
  - **Isolation Forest:** Multi-dimensional outlier detection on transaction amounts and frequency.

> **Terminology Policy:** All flagged items are categorized as **"Potential anomaly"** or **"Exception"** (never presumed as "fraud").

### 3.7 Year-on-Year (YoY) Comparison
1. Upload Prior Year General Ledger (FY 2023-24).
2. Inspect variance amounts and percentage movements across Balance Sheet and P&L line items.
3. Automatically flag movements exceeding configurable materiality thresholds (e.g., >20% or >₹1,00,000).

### 3.8 Audit Checklist Execution
1. Navigate to **Audit Checklist**.
2. Pre-populated statutory questionnaires for:
   - Companies Act 2013 & CARO 2020
   - Tax Audit Form 3CD (Clauses 21d, 31, 34, 44)
   - Standards on Auditing (SA 230, SA 315, SA 500, SA 505)
3. Set status (`Compliant`, `Non-Compliant`, `Not Applicable`, `Under Review`), enter remarks, and link relevant findings.

### 3.9 Working Papers Management (SA 230)
1. Navigate to **Working Papers**.
2. Create audit work papers with standard reference codes (e.g., `WP-A101`, `WP-TAX-01`).
3. Maintain direct references to:
   - Finding IDs
   - Transaction IDs
   - Checklist Item IDs
   - Uploaded supporting evidence files
4. Enforce **Maker-Checker review workflow**: `Prepared` → `Under Review` → `Reviewed` / `Needs Correction`.

### 3.10 Local AI Audit Assistant
1. Access the **AI Assistant** panel in the bottom-right or navigation menu.
2. Ask questions such as:
   - *"Show me all cash transactions over ₹10,000"*
   - *"Explain why voucher PV-109 was flagged as a potential anomaly"*
   - *"Summarize major revenue movements between FY 23-24 and FY 24-25"*
3. **Fact-Grounding Safeguard:** The AI generates explanations strictly from ingested database records and deterministic rule results—it never hallucinates or fabricates financial figures.

### 3.11 Audit Report Generation
1. Navigate to **Reports**.
2. Select from 10 professional report templates:
   - Engagement Summary
   - Data Import Summary
   - Trial Balance Analysis
   - Bank Reconciliation Report
   - GST Reconciliation Report
   - Anomaly & Exception Report
   - Year-on-Year Comparison Report
   - Risk & Findings Report
   - Audit Checklist Report
   - Complete Audit Analysis Report (Comprehensive)
3. Download crystal-clear, print-ready PDF reports stamped with unique Finding IDs and CA review blocks.

### 3.12 Audit Trail & Backup
1. Navigate to **Audit Trail** to inspect tamper-resistant logs of every user action (Login, File Import, Finding Creation, Working Paper Sign-off).
2. Navigate to **Settings & Backup** to create timestamped local database backups or restore previous snapshots.
