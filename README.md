# FinAuditPro — Standalone Offline AI-Assisted Audit Assistant

**FinAuditPro** is a standalone, offline-first, AI-assisted auditing desktop
platform tailored specifically for independent Chartered Accountants (CAs),
audit seniors, and audit practitioners in India.

---

## 📚 Complete Documentation Suite

| Document                             | Purpose                                                 | File Link                                                                         |
| :----------------------------------- | :------------------------------------------------------ | :-------------------------------------------------------------------------------- |
| **1. Installation Instructions**     | System requirements, offline prerequisites, setup steps | [01_INSTALLATION_INSTRUCTIONS.md](docs/01_INSTALLATION_INSTRUCTIONS.md)           |
| **2. User Manual**                   | Complete 16-step auditor workflow and module guide      | [02_USER_MANUAL.md](docs/02_USER_MANUAL.md)                                       |
| **3. Developer Documentation**       | Codebase architecture, service extensions, AI interface | [03_DEVELOPER_DOCUMENTATION.md](docs/03_DEVELOPER_DOCUMENTATION.md)               |
| **4. Database Schema Documentation** | Complete SQLite table specifications & triggers         | [04_DATABASE_SCHEMA.md](docs/04_DATABASE_SCHEMA.md)                               |
| **5. Architecture Diagram**          | Mermaid architecture of frontend, backend, AI & DB      | [05_ARCHITECTURE_DIAGRAM.md](docs/05_ARCHITECTURE_DIAGRAM.md)                     |
| **6. API Documentation**             | Full REST API endpoints, methods, and descriptions      | [06_API_DOCUMENTATION.md](docs/06_API_DOCUMENTATION.md)                           |
| **7. Test Report**                   | 118 unit tests report and intentional exceptions matrix | [07_TEST_REPORT.md](docs/07_TEST_REPORT.md)                                       |
| **8. Sample Datasets Guide**         | Details of all 4 sample test files in `sample_files/`   | [08_SAMPLE_DATASETS_GUIDE.md](docs/08_SAMPLE_DATASETS_GUIDE.md)                   |
| **9. Offline AI Setup**              | Ollama, llama.cpp, GGUF setup and Built-in engine       | [09_OFFLINE_AI_SETUP.md](docs/09_OFFLINE_AI_SETUP.md)                             |
| **10. Demonstration Workflow**       | 10-step statutory audit demo script for stakeholders    | [10_PROJECT_DEMONSTRATION_WORKFLOW.md](docs/10_PROJECT_DEMONSTRATION_WORKFLOW.md) |

---

## 🏛️ Project Purpose & Core Architecture

Traditional auditing involves checking voluminous financial data manually, which
is prone to oversight and fatigue. FinAuditPro serves as an **intelligent audit
assistant** that helps auditors detect anomalies, compute balances, perform
statutory tax checks, cross-reconcile bank/GST data, and draft structured audit
observations with quantifiable evidence.

> **Important Principle:** FinAuditPro is an **audit assistant**, not a
> replacement for a Chartered Accountant. It never automatically declares an
> item as "fraud" or "illegal". It flags items as _"Potential anomaly"_,
> _"Exception"_, _"Mismatch"_, _"Missing information"_, or _"Requires auditor
> review"_ and provides the verifiable evidence trail.

### ⚙️ Hybrid Audit Engine

FinAuditPro implements a 3-tier hybrid audit architecture:

```
                          ┌─────────────────────────────┐
                          │   FinAuditPro Desktop UI    │
                          │ (HTML5/CSS3/Vanilla JS SPA) │
                          └──────────────┬──────────────┘
                                         │
                          ┌──────────────▼──────────────┐
                          │    FastAPI Backend Server   │
                          │   (100% Local & Offline)    │
                          └──────────────┬──────────────┘
                                         │
               ┌─────────────────────────┼─────────────────────────┐
               │                         │                         │
┌──────────────▼──────────────┐ ┌────────▼──────────────┐ ┌────────▼──────────────┐
│ 1. Deterministic Rule Engine│ │2. Statistical / ML    │ │3. Local AI Assistant   │
├─────────────────────────────┤ ├───────────────────────┤ ├───────────────────────┤
│• Debit = Credit check       │ │• Benford's Law (1-9)  │ │• Natural Language Q&A │
│• Section 40A(3) (₹10k cash) │ │• Scikit-Learn         │ │• Evidence Explanation │
│• Section 269ST (₹2L cash)   │ │  Isolation Forest     │ │• Form 3CD Clause Tips │
│• GSTIN 15-char validation   │ │• 3-Sigma Z-Score      │ │• Executive Commentary │
│• Duplicate transaction hash │ │• Weekend timing spike │ │• Working Paper Drafts │
│• Date & chronology mismatch │ │• Discretionary lumpsum│ │                       │
└─────────────────────────────┘ └───────────────────────┘ └───────────────────────┘
                                         │
                          ┌──────────────▼──────────────┐
                          │     Local SQLite Database   │
                          │     (`finauditpro.db`)      │
                          └─────────────────────────────┘
```

1. **Deterministic Rule Engine:**
   - Trial Balance mathematical equality ($Total\,Dr == Total\,Cr$)
   - Income Tax Act Section 40A(3) cash payments exceeding ₹10,000 to a person
     in a day (Clause 21(d) Form 3CD)
   - Income Tax Act Section 269ST cash receipts of ₹2,00,000 or more (Clause 31
     Form 3CD)
   - Indian 15-character GSTIN structure validation (2 State + 10 PAN + 1
     Entity + 1 Z + 1 Check Digit)
   - Exact and near-duplicate transaction matching
   - Chronological inconsistencies (Payment date precedes Invoice date)
   - Missing mandatory voucher numbers and narrations on high-value transactions
   - Negative cash or asset balance detection

2. **Statistical / Machine Learning Engine:**
   - **Benford's Law First-Digit Analysis (Nigrini Forensic Standard):**
     Computes empirical vs theoretical digit distribution and Mean Absolute
     Deviation (MAD).
   - **Isolation Forest (Scikit-Learn):** Unsupervised multi-variate anomaly
     score computation across amount, debit, credit, day-of-week, and
     day-of-month.
   - **3-Sigma Z-Score Univariate Outliers:** Flags entries deviating
     $> 3\sigma$ from historical ledger means.
   - **Weekend & Timing Spikes:** Flags high-value entries booked on non-working
     days (Sundays).

3. **Local AI Engine:**
   - Explains findings with statutory context, expected vs actual values, and
     recommended audit actions.
   - Interactive Natural Language Audit Query Assistant (e.g., _"Show large cash
     transactions above Section 40A(3) limit"_, _"What are the critical
     risks?"_).
   - Generates working paper audit memorandums.
   - **Privacy First:** 100% offline; zero cloud API dependency.

---

## 📂 Navigation & Modules

## 👥 User Roles & Access Control

| Role            | Key Permissions & Responsibilities                                                                                                                                 |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Admin**       | Create users, enable/disable accounts, change roles, reset passwords, view full audit logs, manage database backups and application settings.                      |
| **Auditor**     | Create client masters, create audit engagements, upload & map financial data, execute the Hybrid Audit Engine, review & comment on findings, generate PDF reports. |
| **Audit Staff** | View assigned engagements, execute checklist verification items, perform assigned checks, and draft working paper notes.                                           |

---

## 🔐 Local Authentication & Security

- **100% Offline Authentication:** Zero cloud API or external server reliance.
  All authentication runs locally against SQLite.
- **Cryptographic Password Hashing:** Uses `PBKDF2-HMAC-SHA256` with 100,000
  iterations and random per-user salt. Plain text passwords are never stored or
  logged.
- **Session Management:** Local JSON Web Tokens (JWT) signed with secure local
  secret key. Configurable session timeout and automatic logout.
- **Brute-Force & Lockout Protection:** Exponential lockout cooldown on repeated
  failed attempts with generic authentication error messages.
- **Account Disabling:** Admins can enable or disable user accounts at any time.
  Disabled accounts are immediately blocked from logging in.
- **Self-Disable Protection:** Admins cannot disable or demote their own account
  to prevent administrative lockout.
- **Last Login Tracking:** Records exact local timestamp upon each successful
  authentication.
- **Audit Logging:** Every login, logout, password change, user creation, and
  status toggle is immutably logged to `audit_logs` (Companies Act Rule 11(g)).

---

## 🚀 First-Run Setup & User Onboarding Journey

FinAuditPro implements a first-class, air-gapped first-run onboarding journey:

```
Fresh Installation (0 Users)
            │
            ▼
   First-Launch Detection
   [State A: UNINITIALIZED]
            │
            ▼
  Welcome Splash Screen
  • "Get Started" Wizard
  • "Have an Activation Code?"
            │
            ▼
  Step 1: Create Master Admin Account
  (Role: Admin, Strong Password Policy)
            │
            ▼
  Step 2: CA Firm / Practice Profile
  (Firm Name, ICAI Reg. No., Address, Contact)
            │
            ▼
  Step 3: Session Security & Local AI Shield
  (Session Timeout, Local-Only vs Hybrid AI)
            │
            ▼
  Step 4: Backup Storage Location
  (Automated Snapshot Directory Configuration)
            │
            ▼
  Step 5: Setup Summary & Open Workspace
            │
            ▼
  Auditor Dashboard & Practice Initialization
```

### 🔑 Offline User Activation Flow

For secure multi-auditor desktop deployments without requiring internet email
delivery:

1. **Admin Invites Team Member:** Navigates to _Administration → Users_ and
   enters Full Name, Username, Role, and Designation.
2. **Account Created in `INVITED` State:** System generates a secure
   32-character offline activation token with a 48-hour expiration window.
3. **Activation Token Handover:** The admin securely shares the single-use
   activation code with the staff member.
4. **Local Activation Screen:** The staff member clicks _"Have an activation
   code?"_ on the welcome screen or login dialog.
5. **Set Permanent Password:** The user reviews their profile details, sets
   their secure permanent password, and accepts the audit security notice.
6. **Account Becomes `ACTIVE`:** The token is cryptographically cleared and the
   user is immediately routed to their assigned engagements.

---

## 📖 General Ledger Analysis Module

The **General Ledger (GL) Analysis & Substantive Testing** module provides
comprehensive inspection, multi-attribute filtering, and 13 deterministic
anomaly detection checks:

### 🔎 Search & Filtering Dimensions:

- **Ledger Search:** Filter by specific ledger account head
- **Date Range:** Start date to end date cutoff window
- **Debit Bounds:** Minimum and maximum debit amounts
- **Credit Bounds:** Minimum and maximum credit amounts
- **Party Filtering:** Filter by vendor/customer name with autocompletion
- **Voucher Filtering:** Direct voucher number search
- **Amount Filtering:** Minimum and maximum transaction amount
- **Narration Keyword Search:** Substring search across transaction descriptions
  and memos

### ⚡ 13 Deterministic Anomaly Checks:

1. `GL_01_DUPLICATE_ENTRY`: Potential Duplicate Entries (matching date, ledger,
   party, Dr/Cr)
2. `GL_02_REPEATED_AMOUNT`: Unusually Repeated Identical Amounts in short
   timeframes
3. `GL_03_BACKDATED_ENTRY`: Potential Backdated / Delayed Posting Transactions
4. `GL_04_WEEKEND_POSTING`: Sunday / Weekend Entries (Non-routine postings)
5. `GL_05_OUT_OF_PERIOD`: Transactions outside the active financial year /
   engagement cutoff
6. `GL_06_MANUAL_JOURNAL`: Non-routine Manual Journal Adjustments &
   Rectification Entries
7. `GL_07_LARGE_TRANSACTION`: High-value Outlier Transactions (>=95th percentile
   materiality)
8. `GL_08_ROUND_NUMBER`: Exact Round-Number Transactions (multiples of ₹50,000 /
   ₹1,00,000)
9. `GL_09_UNUSUAL_FREQUENCY`: Unusual Daily Velocity Spikes & Batch Dumping
10. `GL_10_REVERSAL_ENTRY`: Potential Reversal / Cancellation Matching Pairs
11. `GL_11_MISSING_REFERENCE`: Missing Voucher, Invoice, or Documentary
    Reference
12. `GL_12_DEBIT_WITHOUT_CREDIT`: One-Sided Debit / Unbalanced Journal Vouchers
13. `GL_13_CREDIT_WITHOUT_DEBIT`: One-Sided Credit / Unbalanced Journal Vouchers

### 📋 Standardized Anomaly Output Display:

Every flagged transaction displays:

- **Transaction:** ID, Date, Voucher #, Ledger, Party, Amount, Running Balance
- **Reason:** Clear, precise explanation of why it was flagged
- **Rule:** Rule code (e.g., `GL_01_DUPLICATE_ENTRY`) & human-readable rule name
- **Evidence:** Exact matching identifiers, amounts, voucher numbers
- **Risk:** Severity badge (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) and Risk Score
  (1-100)
- **Recommended Review:** Concrete auditor substantive procedures (e.g. SA 240,
  SA 500, SA 520)

> _Adherence to Professional Standards: The system never declares fraud; all
> findings are labeled as "Requires review" or "Potential anomaly"._

---

## 🏦 Bank Reconciliation Statement (BRS) Module

The **Bank Reconciliation Engine** automates the cross-comparison between
internal Cash Book bank ledgers and external bank statements:

### ⚡ 4-Tier Automated Matching Levels:

1. **EXACT MATCH (100% Confidence):** Exact amount match, direction match (Book
   Cr = Bank Dr / Book Dr = Bank Cr), identical cheque/reference number, and
   same-day or 1-day clearance.
2. **HIGH CONFIDENCE (80%–95% Confidence):** Exact amount match with normal 2 to
   7 days transit lag, fuzzy party name or narration token similarity
   $\ge 30\%$.
3. **POSSIBLE MATCH (50%–79% Confidence):** Extended transit lag (8–30 days) or
   minor amount difference ($\le ₹100$, e.g. bank deduction/service charge) with
   verified party match.
4. **UNMATCHED:** Standalone book or bank items requiring substantive
   investigation.

### 🔎 Anomaly & Timing Exception Detection:

- **Unpresented Cheques:** Payments/cheques issued in books but not presented
  for clearance in bank statement.
- **Outstanding Deposits:** Cheques/receipts deposited in books but not yet
  credited/cleared by bank.
- **Direct Bank Charges:** Automatic bank debits (charges, SMS alert fees, AMC,
  penalties) missing from Cash Book.
- **Direct Interest Credited:** Savings/FD auto-sweep interest credited by bank
  missing from Cash Book.
- **Amount & Date Discrepancies:** Quantified fee deductions and clearance
  transit delays.
- **Duplicate & Unknown Entries:** Duplicate payments or bank entries with
  missing client narrations.

### 📋 Standardized Match Display:

Every match candidate presents:

- **Bank Transaction:** Date, Ref/Chq, Description, Amount
- **Book Transaction:** Date, Voucher/Ref, Party/Ledger, Narration, Amount
- **Amount Difference:** Exact discrepancy (e.g. ₹0.00 or variance)
- **Date Difference:** Transit clearance lag in calendar days
- **Match Reason:** Clear audit explanation
- **Confidence Level:** Exact (100%), High (90%), Possible (65%)

### 🛡️ Auditor Workflow & Integrity:

- **Non-Destructive:** Never automatically deletes or modifies financial
  records.
- **Manual Confirm / Reject:** Auditor can accept or reject suggested matches
  with 1 click.
- **Manual Match Workbench:** Allows auditor to manually pair arbitrary
  unmatched book and bank items with working-paper remarks.
- **ICAI Standard BRS Schedule:** Roll-forward computation reconciling Closing
  Bank Balance $\to$ Adjusted Bank Balance $\to$ Cash Book Ledger Balance.
- **CSV Export:** Downloadable formal Bank Reconciliation Statement.

---

## 📊 Sales & Purchase Reconciliation Module

The **Sales & Purchase Reconciliation** engine performs comprehensive,
deterministic 11-point cross-comparison between:

1. **Sales Register / Purchase Register** (Source A)
2. **General Ledger / Party Accounts** (Source B)
3. **Available Tax / GST Data** (GSTIN, Rates, GSTR-1 / GSTR-2B filing figures)

### 🔍 11 Exception Categories Detected:

1. **Missing Invoices:** Invoices present in the register but missing in the
   general ledger, or vouchers posted in the ledger missing from the register.
2. **Duplicate Invoices:** Same invoice number or voucher recorded multiple
   times.
3. **Invoice Amount Differences:** Taxable or gross invoice value mismatches
   between register and ledger accounts.
4. **Tax Amount Differences:** GST amounts booked in register vs ledger vs
   statutory tax slabs (5%, 12%, 18%, 28%).
5. **Date Differences:** Timing disparities and cutoff anomalies exceeding
   standard accounting grace periods (>15 days).
6. **Party Mismatches:** Trade name vs legal party mismatches or misallocated
   customer/vendor accounts.
7. **Invoice Number Mismatches:** Typographical or prefix formatting variances.
8. **Missing GSTIN:** B2B invoices missing valid 15-character GSTINs.
9. **Duplicate GSTIN/Invoice Combinations:** Identical GSTIN + invoice number
   pairs booked repeatedly.
10. **Credit Note Mismatches:** Sales returns / credit note adjustments under
    Section 34 of the CGST Act.
11. **Debit Note Mismatches:** Purchase returns / debit note adjustments.

### 📋 Standardized Exception Display:

For every identified exception and reconciled item, the workbench displays:

- **Invoice Number:** Reference number from Register / Ledger
- **Party Name:** Counterparty legal / trade name
- **Register Amount:** Gross and tax amounts recorded in the register
- **Ledger Amount:** Gross and tax amounts posted in the general ledger
- **Difference:** Exact quantified gross difference (₹)
- **Tax Difference:** Net variance between register tax and ledger tax (₹)
- **Date Difference:** Difference in days between register date and posting date
- **Status:** _Suggested_, _Accepted_, _Rejected_, or _Marked for review_

### 🛡️ Auditor Actions & Report Generation:

- **Accept:** Confirm valid exception or reconciled item.
- **Reject:** Dismiss false positives with audit justification.
- **Mark for Review:** Flag items pending client explanation.
- **Add Auditor Comment:** Persist working-paper notes and observations.
- **Reconciliation Report Export:** Download full reconciliation report as CSV.

---

## 🧾 GST Audit Reconciliation & Configurable Rule Framework

The **GST Reconciliation** engine is built specifically for Indian statutory and
tax audit workflows (e.g. GSTR-2B vs Purchase Register, GSTR-1 vs Sales
Register, GSTR-3B vs Books).

### ⚙️ Independent Configurable Rule Framework:

To prevent hard-coded tax claims, all tax rules are maintained in a configurable
database repository and can be updated independently from application code:

- **Value & Tax Tolerances:** Configurable numeric variance thresholds (default
  ₹5.00 for taxable value and ₹2.00 per tax head).
- **Date Cutoff Disparity:** Permitted transit delay (default 30 days cutoff).
- **Fuzzy Matching Rules:** Dynamic prefix stripping, leading zero cleaning, and
  token similarity thresholds (85% invoice / 70% party).
- **GSTIN Structure Validation:** 15-character statutory format regex and valid
  2-digit state code validation.
- **Recognized Tax Slabs:** Active rate slabs
  `[0%, 0.25%, 3%, 5%, 12%, 18%, 28%]`.
- **Place of Supply Logic:** Inter-state (IGST) vs Intra-state (CGST+SGST equal
  split) compliance checks.
- **Section 16(2)(aa) ITC Compliance:** Mandatory reflection in GSTR-2B for
  eligible ITC claims.

### 🔍 Checks Performed:

- **GSTIN mismatch:** Identifies counterparty registration discrepancies or
  state code errors.
- **Invoice number mismatch:** Resolves prefix and zero variances via fuzzy
  token analysis.
- **Invoice date mismatch:** Identifies out-of-period invoices crossing return
  filing deadlines.
- **Taxable value difference:** Compares base taxable amounts between Source A
  and Source B.
- **CGST, SGST, IGST differences:** Compares individual tax head amounts.
- **Total invoice value difference:** Detects gross invoice amount variances.
- **Missing invoices:** Identifies invoices missing in Source A (e.g. supplier
  unfiled) or missing in Source B (unbooked in books).
- **Duplicate invoices:** Detects duplicate filings on portal or duplicate
  voucher postings.
- **Credit Note & Debit Note mismatches:** Section 34 adjustments verification.

### 📊 Standardized Match Categorization:

- **Matched:** Full match across GSTIN, Invoice #, Date, and Taxable/Tax figures
  within tolerance.
- **Partially matched:** Minor round-off differences or acceptable transit
  delay.
- **Mismatched:** Discrepancies in tax rates, wrong tax heads, or gross value
  variances.
- **Missing in source A:** Invoices booked in Books but absent from GSTR-2B /
  Portal.
- **Missing in source B:** Invoices reflected on GST Portal but unrecorded in
  Books.

### 📋 Display of Actual Values from Both Sources:

Every line item in the GST workbench displays side-by-side:

- **Source A (Portal):** Invoice #, Date, GSTIN, Party, Taxable Value, CGST,
  SGST, IGST, Total Value.
- **Source B (Books):** Invoice #, Date, GSTIN, Party, Taxable Value, CGST,
  SGST, IGST, Total Value.
- **Quantified Differences:** Taxable Diff, CGST Diff, SGST Diff, IGST Diff,
  Total Value Diff.
- **Audit Findings:** _"GST reconciliation exception"_, _"Potential mismatch"_,
  _"Requires auditor review"_.

---

## 📊 Financial Statement Analysis & SA 520 Analytical Review

The **Financial Statement Analysis** module implements deterministic statutory
financial ratio calculations, multi-year comparative analytics (Schedule III
Balance Sheet & Statement of Profit and Loss), Cash Flow Statement derivation
(Indirect Method AS 3), and significant movement detection.

### 🔢 Deterministic Financial Ratios

1. **Liquidity Ratios:**
   - **Current Ratio:**
     $\frac{\text{Current Assets}}{\text{Current Liabilities}}$ (ICAI Benchmark:
     $\ge 1.33\text{x}$)
   - **Quick Ratio (Acid Test):**
     $\frac{\text{Current Assets} - \text{Inventories}}{\text{Current Liabilities}}$
     (Benchmark: $\ge 1.00\text{x}$)
2. **Solvency & Capital Efficiency:**
   - **Debt-to-Equity Ratio:** $\frac{\text{Total Debt}}{\text{Total Equity}}$
     (Benchmark: $\le 2.00\text{x}$)
   - **Return on Capital Employed (ROCE):**
     $\frac{\text{EBIT}}{\text{Total Assets} - \text{Current Liabilities}} \times 100$
     (Benchmark: $\ge 15\%$)
   - **Return on Equity (ROE):**
     $\frac{\text{PAT}}{\text{Total Equity}} \times 100$
3. **Profitability Margins:**
   - **Gross Profit Margin (%):**
     $\frac{\text{Gross Profit}}{\text{Revenue}} \times 100$
   - **Operating Profit Margin (%):**
     $\frac{\text{Operating EBIT}}{\text{Revenue}} \times 100$
   - **Net Profit Margin (%):** $\frac{\text{PAT}}{\text{Revenue}} \times 100$
4. **Activity & Working Capital Cycles:**
   - **Debtors / Receivable Turnover:**
     $\frac{\text{Revenue}}{\text{Trade Receivables}}$ and **Days Sales
     Outstanding (DSO)** ($\frac{365}{\text{Debtors Turnover}}$)
   - **Inventory Turnover Ratio:** $\frac{\text{COGS}}{\text{Inventories}}$ and
     **Days Sales in Inventory (DSI)** ($\frac{365}{\text{Inventory Turnover}}$)
   - **Creditors / Payable Turnover:**
     $\frac{\text{COGS}}{\text{Trade Payables}}$ and **Days Payable Outstanding
     (DPO)** ($\frac{365}{\text{Payables Turnover}}$)
   - **Working Capital Turnover:**
     $\frac{\text{Revenue}}{\text{Current Assets} - \text{Current Liabilities}}$
   - **Cash Conversion Cycle (CCC):** $\text{DSO} + \text{DSI} - \text{DPO}$

### 🔍 Significant Movement & SA 520 Workbench

- **Variance Threshold:** Automatically flags items where $|\Delta\%| \ge 20\%$
  or $|\Delta| \ge ₹5,00,000$.
- **Audit-Compliant Vocabulary:** Strictly uses _"Significant movement"_,
  _"Unusual change"_, _"Requires auditor review"_, or _"Normal variance"_
  without premature fraud claims.
- **Suggested Business Drivers:** Provides contextual explanation categories
  (e.g. raw material commodity inflation, distributor expansion, credit term
  relaxation, capacity utilization).
- **Auditor Working Paper Notes:** Allows auditors to enter, update, and persist
  SA 520 inquiry notes and review statuses directly to the database.

---

## 🔍 Duplicate & Missing Transaction Detection Engine

The **Duplicate & Missing Transaction Detection Engine** provides deep
substantive testing to uncover duplicate postings, unrecorded gaps, and sequence
breaks in audit datasets:

### ⚡ Comprehensive Duplicate Checks:

1. **Exact Duplicate:** Identical date, ledger, party name, debit, credit,
   amount, voucher number, and invoice number (100% Match).
2. **Same Invoice Number:** Distinct transactions sharing the exact same invoice
   number across different postings or dates.
3. **Same Voucher Number:** Disparate entries sharing identical voucher numbers
   with different debit/credit legs.
4. **Same Date + Amount + Party:** Potential duplicate billings or split
   invoices with different voucher IDs.
5. **Same Reference / Transaction ID:** Duplicate bank UTRs, RTGS reference
   codes, or transaction IDs.
6. **Fuzzy Duplicate Detection:**
   - **Similar Party Name ($\ge 85\%$ string similarity) + Identical/Near
     Amount:** Identifies trade name aliases, spelling variances (e.g. _M/S
     Reliance Digital Retail Ltd_ vs _Reliance Digital Retail Limited_), and
     typo duplications.
   - **Similar Invoice Pattern ($\ge 85\%$ normalized pattern similarity):**
     Detects slash vs hyphen differences (e.g. `INV-2024-001` vs `INV/2024/001`)
     with similar financial figures.
   - **Similar Narration / Description ($\ge 85\%$ token similarity) + Identical
     Amount:** Uncovers duplicate journal memos.

### 📋 Duplicate Groups Display & Audit Actions:

- **Duplicate Groups Workbench:** Groups duplicate pairs into distinct group
  identifiers (e.g., `Group #D001`, `Group #D002`).
- **Side-by-Side Comparison:** Displays Transaction A (Reference) vs Transaction
  B (Potential Duplicate) with similarity percentage, quantified financial
  exposure, and detailed reason.
- **Safety First — Never Auto-Delete:** Financial records are **never**
  automatically modified or deleted.
- **Auditor Decision Workflow:**
  - **Confirm Duplicate:** Confirms entry duplication and logs auditor
    verification findings.
  - **Mark as Valid:** Dismisses false positives (e.g., monthly recurring
    retainers, distinct contract tranches).
  - **Ignore:** Sets item aside from active exception counts.
  - **Add Auditor Comment:** Persists SA 230 working-paper documentation.

### 🔢 Missing Transaction & Sequence Gap Checks:

- **Document Series Tracking:** Automatically extracts prefixes, zero-padded
  integer sequences, and suffixes across:
  - **Invoice Numbers** (e.g., `INV-2024-001`, `INV-2024-002`, `INV-2024-005`
    $\to$ Missing `INV-2024-003`, `INV-2024-004`).
  - **Voucher Numbers** (e.g., `V-101`, `V-102`, `V-105` $\to$ Missing `V-103`,
    `V-104`).
  - **Cheque Numbers** (6-digit Indian bank instrument numbering extracted from
    narrations, references, and vouchers).
- **Audit Guidance & Professional Standards:** Sequence gaps are explicitly
  flagged as _exceptions requiring inquiry_ (e.g. cancelled leaves, spoiled
  documents, multi-branch series) rather than conclusive proof of unrecorded
  transactions or fraud.
- **Auditor Documentation Workflow:** Allows documenting valid reasons (e.g.,
  _"Cancelled invoice book page confirmed"_, _"Spoiled cheque leaf inspected"_).

---

## 🤖 AI-Assisted Anomaly Detection Engine (Hybrid 3-Tier Architecture)

The **AI-Assisted Anomaly Detection Engine** provides deep forensic inspection
of financial ledger transactions by integrating three progressive layers of
detection:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   HYBRID ANOMALY DETECTION ENGINE                      │
├──────────────────────────┬──────────────────────────┬──────────────────┤
│ LEVEL 1: DETERMINISTIC   │ LEVEL 2: STATISTICAL     │ LEVEL 3: LOCAL ML│
├──────────────────────────┼──────────────────────────┼──────────────────┤
│• Section 40A(3) (>₹10k)  │• Ledger Z-Scores (>2.8σ) │• Isolation Forest│
│• Section 269ST (≥₹2L)    │• Extreme IQR Bounds      │• Local Outlier   │
│• Repeated Round Numbers  │• Benford's Law (MAD)     │  Factor (LOF)    │
│• Month-End Cutoff Spikes │• Monthly Expense Surges  │• DBSCAN Noise    │
│• Weekend / Off-Hour JVs  │• Daily Velocity Bursts   │  Clustering      │
│• First-Time Vendor Spikes│                          │• Multidimensional│
└──────────────────────────┴──────────────────────────┴──────────────────┘
```

### ⚡ Anomaly Patterns Detected:

1. **Unusually Large Transaction:** Surpasses 95th/99th percentile materiality,
   Extreme IQR ($Q_3 + 3.0 \times IQR$), or Ledger Z-Score ($Z > 2.8\sigma$).
2. **Unusual Number of Transactions:** High daily transaction velocity burst
   exceeding $3\times$ daily baseline average.
3. **Sudden Increase in Expense:** Month-over-month ledger category surge
   exceeding $100\%$ or $2.5\times$ moving average.
4. **Unusual Vendor Activity:** Single-transaction high-value vendor (>
   ₹1,50,000) or isolated counterparty without historical baseline.
5. **Unusual Journal Entry:** High-value manual journal adjustments posted on
   weekends or non-working days.
6. **Significant Month-End Activity:** Concentration of high-value postings in
   the final 3 days of a month/quarter (Cutoff Risk under SA 500).
7. **Repeated Round-Number Transactions:** Repetitive round-figure postings
   (multiples of ₹50,000 / ₹1,00,000).
8. **Behavior Significantly Different from Historical Pattern:** Multivariate
   machine learning isolation (Isolation Forest anomaly score $\ge 70/100$,
   Local Outlier Factor density deviation, DBSCAN spatial noise).

### 📋 Standardized Anomaly Output Schema:

Every detected anomaly produces:

- **Anomaly ID:** Unique identifier (e.g., `ANOM-001`, `ANOM-002`)
- **Transaction ID & Details:** Date, Voucher #, Invoice #, Ledger, Party Name,
  Amount, Debit/Credit, Narration
- **Anomaly Score:** Normalized quantitative risk score (0.0 to 100.0)
- **Severity:** `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`
- **Detected Pattern:** Standardized audit pattern category
- **Evidence:** Structured dictionary with exact mathematical values (Mean, Std,
  Z-score, IQR cutoff, tree depth, sample size)
- **Explanation:** Explainable CA-oriented narrative generated from empirical
  evidence
- **Recommended Review:** Actionable substantive audit procedure (SA 240, SA
  315, SA 500, SA 520)
- **Status & Working Paper Remarks:** `Open`, `Confirmed Anomaly`,
  `Marked Normal / Valid`, `Ignored`

### 🛡️ Critical Audit Principle & Safeguard:

> **Strict Professional Standard:** _Anomaly does not equal fraud._ The engine
> never automatically claims _"This is fraud."_ Instead, it strictly outputs:
> **"Potential anomaly detected. Auditor review recommended."** and provides an
> instant one-click **AI Working Paper Memorandum** generator.

---

## 📈 Year-on-Year (YoY) Financial Comparison Module

The **Year-on-Year Financial Comparison** module enables auditors to perform
analytical review procedures (SA 520) across two financial years (Current Year
vs Previous Year):

### 🔍 4-Tier Comparative Scope:

1. **Executive Financial Heads:**
   - Revenue from Operations & Other Income
   - Cost of Goods Sold (COGS) & Material Consumption
   - Employee Benefit Expenses, Finance Costs, Depreciation & Other Operating
     Expenses
   - Gross Profit, Operating Profit (EBITDA), Profit Before Tax (PBT), Profit
     After Tax (PAT)
   - Fixed Assets, Trade Receivables, Cash in Hand, Bank Balances, Inventory,
     Current Assets, Total Assets
   - Long-Term Debt, Trade Payables, Current Liabilities, Total Equity & Net
     Worth
2. **Major Ledger Accounts:**
   - Full comparative ledger trial balances sorted by absolute variance.
3. **Party Balances:**
   - Counterparty-level concentration, customer turnover, and supplier
     exposures.
4. **Operational Volumes:**
   - Total transaction count, Debit volume, Credit volume, Average ticket size,
     Active ledgers count, Active counterparties count.

### ⚙️ Configurable Variance Thresholds:

Auditors can customize materiality and variance trigger thresholds on demand
rather than relying on a hard-coded static percentage:

- **Preset Buttons:** `5%`, `10%`, `15%`, `20%`, or custom user input.
- **Materiality Cutoff:** Dynamic minimum rupee threshold to filter immaterial
  line items.
- **Significant-Only Toggle:** Instantly isolate items breaching configured
  tolerance.

### 🤖 Factual AI Reasoning & Strict Zero-Hallucination Safeguard:

- Analyzes underlying transaction postings, newly introduced counterparties,
  volume changes, and voucher patterns to explain large movements.
- **Never invents or assumes reasons.**
- If evidence is insufficient, strictly outputs:
  > _"Insufficient data to determine the reason."_

### 📋 Working Paper & Reporting Features:

- Save and edit per-line **Auditor Comments** and review status (`Unreviewed`,
  `In Review`, `Verified`, `Exception Noted`).
- **Export CSV:** One-click download of the complete comparative analytical
  review schedule.

---

## ⚡ Centralized Audit Risk & Findings Module

The **Audit Risk & Findings Repository** serves as FinAuditPro's centralized
exception management clearinghouse. Every audit anomaly, variance, or compliance
breach across all 8 subsystems automatically enters this centralized register:

```
┌────────────────────────────────────────────────────────────────────────┐
│               CENTRALIZED AUDIT FINDINGS REPOSITORY                    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
 ┌───────────────────────┬──────────┴────────────┬────────────────────────┐
 │ • Statutory Tax Rules │ • Duplicates & Gaps   │ • ML Anomaly Engine    │
 │ • Year-on-Year Variances • Trial Balance Imbalance • Bank BRS Exceptions │
 │ • GST 2B ITC Discrepancy • GL Abnormal Balances • Manual Observations   │
 └───────────────────────┴───────────────────────┴────────────────────────┘
```

### 🎯 Core Finding Attributes

Each centralized finding tracks:

- **Finding ID:** Monospace identifier (e.g., `FIND-TAX-001`, `FIND-DUP-001`,
  `FIND-ANOM-001`, `FIND-YOY-001`, `FIND-BRS-001`, `FIND-GST-001`)
- **Engagement:** Selected audit engagement reference
- **Module & Category:** Module origin and classification
  (`Statutory Compliance`, `Accounting Standard`, `Reconciliation`,
  `Variance Analysis`, etc.)
- **Severity Tier:** `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- **Explainable Risk Score:** 1.0 to 10.0 scale, calculated strictly through
  deterministic mathematical factors
- **Title & Description:** Plain-language summary and factual audit exception
  description
- **Evidence & Affected Transactions:** Linked transaction IDs, voucher codes,
  amounts, and source records
- **Rule Used:** Auditing standard or statutory rule applied (e.g.
  `Income Tax Act Section 40A(3)`, `SA 520 Variance Rule`, `SA 505 BRS Mandate`)
- **AI Explanation & Recommended Action:** Detailed calculation breakdown and
  ICAI recommended substantive procedures
- **Auditor Working Paper & Status:** `Open`, `Under Review`, `Resolved`,
  `Waived` with reviewer sign-off, comment, and review timestamp

### 🧮 Explainable Deterministic Risk Scoring Formula

Risk scores are **never arbitrarily hallucinated by AI**. The score is strictly
computed using 8 deterministic financial and audit factors:

$$\text{Risk Score} = \text{Base Severity Weight} + \text{Amount Impact} + \text{Repetition Impact} + \text{Volume Impact} + \text{Diff \% Impact} + \text{Quality Penalty} + \text{Historical Penalty}$$

1. **Base Severity Weight:** `CRITICAL` = +7.0, `HIGH` = +5.0, `MEDIUM` = +3.0,
   `LOW` = +1.5
2. **Amount vs Materiality Benchmark:** Ratio of cumulative exposure to
   engagement materiality threshold ($+0.1$ to $+2.0$)
3. **Repetition / Frequency Multiplier:** Count of repeated occurrences across
   the period ($+0.4$ to $+1.0$)
4. **Number of Affected Records:** Count of distinct transaction IDs impacted
   ($+0.3$ to $+1.0$)
5. **Difference Percentage Factor:** Percentage magnitude of variance or
   mismatch ($+0.2$ to $+1.0$)
6. **Data Quality Impact:** Format errors, unclassified heads, missing
   identifiers ($+0.5$)
7. **Historical Behavior Impact:** Recurring anomalies or prior period
   weaknesses ($+0.5$)

### 📊 Executive Dashboard Metrics

The findings dashboard displays real-time summary cards:

- **Total Findings:** Cumulative exception count
- **Open Findings:** Active findings requiring review
- **High Risk:** Findings with score $\ge 6.5$ or High Severity
- **Critical:** Findings with score $\ge 8.5$ or Critical Severity
- **Under Review:** Findings with active auditor inquiry
- **Resolved:** Remediated or adjusted findings

---

## 🚀 Getting Started & Installation

### Prerequisites

- Python 3.10+ (Tested on Python 3.12)
- Modern web browser (Chrome, Edge, Firefox)

### Installation

```bash
# Clone or navigate to the project directory
cd c:\Users\sbmpc.student\Desktop\Audit

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

**Option 1: Using the Python launcher**

```bash
python run.py
```

**Option 2: Using the Windows batch script** Double-click `start.bat` or run:

```cmd
start.bat
```

The application will start on `http://127.0.0.1:8000` and automatically open in
your default browser.

---

## 📋 Dynamic Audit Checklist & Substantive Workprogram (15 Categories)

The **Audit Checklist Module** provides a comprehensive, SA 200 / SA 230 / CARO
2020 / Form 3CD compliant workprogram engine designed specifically for Indian
audit engagements. Rather than a static, one-size-fits-all checklist,
workprograms are dynamically generated and tailored to each engagement's
specific risk profile.

### ⚙️ Dynamic Tailoring Parameters

Audit procedures are generated according to:

1. **Client Legal Entity Type:** Private Limited, Public Limited
   (Listed/Unlisted), LLP, Partnership, Sole Proprietorship, Trust/Society
   (adjusts Companies Act, CARO, and entity-specific reporting standards).
2. **Audit Type / Mandate:** Statutory Audit (Companies Act 2013 + CARO 2020),
   Tax Audit (Income Tax Act 1961 Form 3CD), Internal Audit & IFC testing, GST
   Audit (GSTR-9C), Transfer Pricing (Form 3CEB).
3. **Financial Year:** Period cutoffs, applicable MCA notifications, and tax
   rate schedules.
4. **Selected In-Scope Modules:** General Ledger & Vouching, Bank Reconciliation
   (BRS), GST Verification (GSTR-2B/3B), Duplicates & Sequence Gaps, ML Anomaly
   Detection, Fixed Asset Register.
5. **Integrated Risk Findings:** Automated risk findings (High-Risk and Critical
   findings from anomaly engines, duplicate checks, and reconciliation
   discrepancies) dynamically spawn corresponding substantive verification
   procedures.

### 🗂️ 15 Standardized Audit Categories

The module covers standard procedures across all 15 audit dimensions:

1. **Planning:** Engagement acceptance, independence declarations (SQC 1),
   preliminary analytical review, and materiality determination (SA 320).
2. **Internal Controls:** Walkthrough tests, segregation of duties, ERP access
   authorization, and IFC over Financial Reporting (IFCoFR).
3. **Cash & Bank:** Bank confirmations under SA 505, stale cheque review,
   uncredited remittances, Section 269ST cash receipts verification.
4. **Receivables:** Negative balance reviews, age-wise classification, direct
   balance confirmations, credit loss provisioning under Ind AS 109 / AS 7.
5. **Payables:** Trade creditor confirmations, MSMED Act 45-day payment
   compliance, debit balances in creditor ledgers, cut-off verification.
6. **Inventory:** Physical stock verification (SA 501), valuation testing (lower
   of cost or NRV per AS 2 / Ind AS 2), slow-moving and non-moving analysis.
7. **Fixed Assets:** Physical verification records (CARO Clause i), title deeds
   examination, depreciation rates under Schedule II / Section 32, impairment
   indicators (AS 28).
8. **Revenue:** Revenue recognition criteria (AS 9 / Ind AS 115), sales cutoff
   tests around balance sheet date, circular transactions, and GSTR-1 turnover
   reconciliation.
9. **Expenses:** Section 40A(3) cash expense disallowance (>₹10,000),
   personal/non-business expenditure identification, abnormal month-on-month
   expense surges.
10. **Loans:** Section 185/186 compliance for loans to directors, bank loan
    covenant compliance, sanction letter verification, external credit ratings.
11. **Related Parties:** Identification of all related parties under AS 18 / Ind
    AS 24, Section 188 board/shareholder approval scrutiny, arm's length pricing
    analysis.
12. **Payroll:** Statutory deductions (PF, ESI, PT), timely deposit before due
    dates, director remuneration ceilings under Section 197 / Schedule V.
13. **Tax/GST:** Advance tax calculations, TDS/TCS deduction & deposit
    compliance, Section 16(2)(aa) GSTR-2B vs 3B input tax credit eligibility,
    tax audit clause reporting.
14. **Financial Statements:** Schedule III presentation, disclosure compliance,
    grouping and classification verification, notes to accounts scrutiny.
15. **Closing Procedures:** Subsequent events review (SA 560), going concern
    assessment (SA 570), management representation letter (SA 580), trial
    balance closing entries.

### 📝 Each Checklist Item Schema

Every procedure tracks:

- **Checklist ID:** Standardized or custom alphanumeric code (e.g., `PLAN-01`,
  `CASH-01`, `CUST-INV-01`, `RISK-FIND-102`).
- **Category:** One of the 15 standard audit categories.
- **Question / Procedure:** Clear audit verification instructions and standard
  references.
- **Status:** Current operational state.
- **Assigned Staff:** Audit team member responsible for execution.
- **Evidence:** Cross-reference to working papers, certificates, vouchers, or
  bank statements.
- **Comment:** Auditor conclusions, observations, or client explanations.
- **Due Date:** Scheduled completion deadline.
- **Completed Date:** Verified sign-off date.

### 🚦 5 Standard Statuses

- `Not Started`: Newly generated or unallocated procedure.
- `In Progress`: Active fieldwork and testing currently underway.
- `Requires Review`: Flagged exception or risk-finding-linked item requiring
  partner/senior review.
- `Completed`: Auditor verified and signed off with working paper evidence.
- `Not Applicable`: Scope exclusion with audit justification.

### ✍️ Custom Checklist Items & Extensibility

Auditors can easily add bespoke checklist procedures for unique client
transactions, industry-specific regulations, or special investigations. Custom
items are clearly tagged with a `CUSTOM` badge and can be reviewed, edited, or
removed.

### 🛡️ Strict AI Completion Boundary (SA 200 / 230)

In adherence to **SA 200 (Overall Objectives of the Independent Auditor)** and
**SA 230 (Audit Documentation)**:

> **Checklist items are NEVER automatically marked 'Completed' based only on AI
> or automated scripts.**

- Automatically imported risk findings enter the checklist strictly with the
  status **`Requires Review`**.
- Standard template procedures initialize as **`Not Started`**.
- A procedure can **only** transition to **`Completed`** through manual auditor
  sign-off with documented working paper evidence.

---

## 🧪 Testing

Run the automated test suite using pytest:

```bash
python -m pytest backend/tests -v
```

The test suite contains over 118 unit tests verifying:

- Deterministic rules (40A(3), 269ST, GSTIN, Duplicates)
- Statistical engine (Benford's Law, Isolation Forest)
- FastAPI REST endpoints
- PDF report generation
- Local AI Q&A engine
- Complete end-to-end data processing workflow
- Idempotency and database trigger protections
- Report generation logic

---

## 🔒 Data Privacy & Security

- **100% Offline:** No client financial data is transmitted over the internet.
- **Local Storage:** SQLite database stored locally in `finauditpro.db`.
- **Role-Based Access:** Admin, Auditor, and Staff permission tiers.
- **Audit Trail:** Immutable activity logs per MCA / Companies Act Rule 11(g).
- **One-Click Backup:** Export/import full encrypted/timestamped database dumps.

# 
