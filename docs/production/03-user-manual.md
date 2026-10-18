# 03 — Comprehensive User Manual

**Application**: FinAuditPro  
**Document**: Standard Operating Procedure & Workflow Guide  
**Release**: 1.0.0 Production  

---

## 1. Initial Installation & Launch

### Launching on macOS / Linux
1. Open Terminal and navigate to the project root:
   ```bash
   cd /path/to/TempAudit-main
   ```
2. Execute the verified setup script (creates virtual environment and installs dependencies):
   ```bash
   ./initialize/setup_mac.sh
   ```
3. Start the application server:
   ```bash
   ./initialize/start_mac.sh
   ```
4. Open your web browser and navigate to: `http://127.0.0.1:8000`.

---

## 2. Authentication & First-Run Setup

### Creating Administrator Credentials via CLI
If launching for the first time, you can create the master administrator directly from the command line:
```bash
./venv/bin/python scripts/create_admin.py \
  --username admin \
  --password "YourSecurePassword2026!" \
  --email "partner@cafirm.local" \
  --name "CA Rajeshwar Sharma"
```

### Logging In via Browser
1. In the login modal, enter your `Username` and `Password`.
2. Ensure **Remember session** is checked.
3. Click **Secure Offline Sign In**.
4. The system issues a signed JWT token, stores it safely in browser local storage, and loads the active workspace.
5. **Session Persistence**: If you refresh the page or open a new browser tab, your authenticated session is restored automatically without prompting for login.

---

## 3. Client & Engagement Scoping

### Creating a Client
1. In the left navigation sidebar, click **Clients** (`#view-clients`).
2. Click **+ Add Client**.
3. Enter Client Details:
   - **Company Name**: e.g., `Apex Engineering Pvt Ltd`
   - **PAN**: e.g., `AABCA1234D` (10-character alphanumeric)
   - **GSTIN**: e.g., `27AABCA1234D1ZP` (15-character statutory format)
   - **Entity Type**: Select from dropdown (*Private Limited, Public Limited, LLP, Partnership, Proprietorship*).
4. Click **Save Client**.

### Creating an Audit Engagement
1. Click **Engagements** (`#view-engagements`).
2. Click **+ New Engagement**.
3. Select the Client, specify the **Audit Title** (*Statutory Audit FY 2024-25*), **Audit Type**, and **Financial Year** (*2024-25*).
4. Once created, select the engagement in the top bar dropdown: **Active Engagement: Apex Engineering Pvt Ltd - Statutory Audit FY 2024-25**. All subsequent operations will be strictly scoped to this engagement.

---

## 4. Financial Data Import & Column Mapping

1. Click **Data Import** in the sidebar.
2. Select **Data Category**:
   - `General Ledger`
   - `Sales Register`
   - `Purchase Register`
   - `Bank Statement`
   - `GSTR-2B`
3. Drag and drop your `.csv` or `.xlsx` file into the upload zone (maximum 50 MB per file).
4. **Intelligent Column Mapping**:
   The engine automatically detects header aliases:
   - *Date* → `date`, `voucher_date`, `txn_date`
   - *Voucher / Ref* → `voucher_no`, `vch_no`, `reference`
   - *Debit / Credit / Amount* → `debit`, `credit`, `amount`
   - *Party Name* → `party_name`, `ledger_name`, `particulars`
5. Click **Validate & Ingest**. If any row contains formatting errors (e.g. invalid date or malformed numbers), an error summary and downloadable error CSV will be provided without creating corrupt partial records.

---

## 5. Running Audit Procedures & Inspecting Findings

1. Click **Risk & Findings** (`#view-findings`).
2. Click **Run Audit Engine**. The engine performs:
   - **Section 40A(3)** cash payment limit checks (> ₹10,000).
   - **Section 269ST** cash receipt aggregation (daily and single-transaction cross-date).
   - Mathematical trial balance balance checks.
   - Benford's Law distribution analysis.
   - Isolation Forest statistical outlier scores.
3. Review the findings list:
   - Click any finding to inspect its **Source Transactions**, **Calculated Difference**, and **Form 3CD Clause Recommendation**.
   - Update finding status: `Under Review`, `Resolved`, `Waived`, or `Escalated`.

---

## 6. Bank Reconciliation Statement (BRS)

1. Click **Reconciliation (BRS/2B)**.
2. Under Bank Reconciliation, select your **Book Bank Ledger** (e.g. `HDFC Bank Account`).
3. The system pairs book entries against imported bank statements across 4 matching passes:
   - **Pass 1**: Exact Amount + Cheque Number Match (100% confidence)
   - **Pass 2**: Clearance Delay Match (1-7 days bank clearance window)
   - **Pass 3**: Date + Amount Match
   - **Pass 4**: Unmatched Exceptions (Unpresented Cheques, Outstanding Deposits, Direct Bank Charges)
4. Confirm suggested matches or manually link entries with the **Manual Match** button.

---

## 7. Generating Executive Audit Reports

1. Click **Audit Reports (PDF)** (`#view-reports`).
2. Select the Report Template:
   - *Complete Audit Analysis Report*
   - *Tax Audit Form 3CD Clause Pack*
   - *Bank Reconciliation Statement Summary*
   - *Internal Controls & Anomaly Findings Memo*
3. Click **Generate PDF**.
4. Click **Download Report**. The system signs the download request with your active authentication token and downloads a clean, printable PDF document.

---

## 8. Backup & Disaster Recovery

1. Click **Settings & Backup** (`#view-settings`).
2. Click **Create Snapshot Backup**.
3. A verified SQLite database archive is created in `backend/backups/`.
4. To restore: Select a previous backup from the list, click **Validate & Restore**. The application verifies table schemas, creates a safety rollback point, and restores active data safely.
