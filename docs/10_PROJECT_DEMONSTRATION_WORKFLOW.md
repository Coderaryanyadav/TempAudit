# FinAuditPro - Project Demonstration Workflow

Follow this 10-step auditor walkthrough to conduct an end-to-end statutory and tax audit demonstration of **FinAuditPro**.

---

## 1. Step 1: Login & Role Selection
1. Open the application at `http://127.0.0.1:8000` (or `frontend/index.html`).
2. Log in with your Administrator / Auditor credentials created during setup (or run `python scripts/seed_test_data.py` if setting up an automated test environment).
3. Point out the top navigation bar showing active user name, Role, and the **Offline AI Status** badge.

---

## 2. Step 2: Dashboard Overview
1. Observe the **6 Top KPI Cards**: Active Clients (1), Active Engagements (1), Open Findings (7), High-Risk Findings (2), Unmatched Transactions (1), Pending Reviews (1).
2. Review the **7 Main Dashboard Sections**:
   - Engagement & Client Overview
   - Risk & Severity Distribution Chart
   - Monthly Transaction Volume & Value
   - Reconciliation Status (BRS & GST)
   - Anomaly & Exception Breakdown
   - Year-on-Year Variance Highlights
   - Audit Checklist Progress Gauge
3. **Interactive Drilldown Demonstration:** Click on the **High-Risk Findings = 2** card or chart bar to trigger a live modal filtering only the high-risk statutory breaches.

---

## 3. Step 3: Financial Data Import & Pre-Validation
1. Navigate to **Data Import**.
2. Select the engagement **Statutory & Tax Audit FY 2024-25**.
3. Choose `backend/sample_files/apex_general_ledger_fy2425.xlsx` (or drag & drop).
4. Demonstrate **Pre-Import Structural Validation**: Observe automatic column mapping, date validation, and row integrity checks.
5. Click **Import & Normalize Transactions**.

---

## 4. Step 4: Trial Balance & General Ledger Analysis
1. Navigate to **Trial Balance**:
   - Verify Total Debits (₹48,88,700) = Total Credits (₹48,88,700) with **Zero Difference**.
   - Show automatic categorization into Revenue, Expense, Asset, and Liability.
2. Navigate to **General Ledger**:
   - Filter by ledger *Plant & Machinery Repairs*.
   - Point out the flagged statistical spike of ₹18,50,000 (`PV-289`).

---

## 5. Step 5: Multi-Way Reconciliations
1. **Bank Reconciliation (BRS):**
   - Import `backend/sample_files/apex_bank_statement.csv`.
   - Run Auto-Match. Show matched transactions and point out the unmatched bank debit of ₹3,500 (Annual Folio & Ledger Maintenance Charges).
2. **GST ITC Reconciliation:**
   - Import `backend/sample_files/apex_gstr2b_portal_download.csv`.
   - Reconcile GSTR-2B vs Books. Highlight the missing vendor credit note exception.

---

## 6. Step 6: Anomaly Detection & Rule Engine
1. Navigate to **Audit Rules & Anomalies**.
2. Click **Run Full Audit Scan**.
3. Review the flagged exceptions:
   - **Section 40A(3) Violation:** Voucher `CPV-001` (₹45,000 cash freight).
   - **Section 269ST Violation:** Voucher `CRV-012` (₹2,50,000 cash receipt).
   - **Duplicate Invoices:** Vouchers `PV-108` and `PV-109` for invoice `INV-7744`.
   - **Invalid GSTIN Checksum:** Voucher `PV-145`.
   - **Benford's Law Chart:** First-digit distribution vs theoretical curve.
   - **Isolation Forest ML Score:** Multi-dimensional outlier detection on high repair costs.

---

## 7. Step 7: Year-on-Year Financial Comparison
1. Navigate to **Year-on-Year (YoY)**.
2. Compare FY 2024-25 with Prior Year (FY 2023-24).
3. Point out the **+184.6% spike** in *Plant & Machinery Repairs* exceeding the materiality threshold.
4. Click **Explain Movement** to demonstrate factual AI-assisted analysis grounded strictly in transactional data.

---

## 8. Step 8: Working Papers & Checklist (SA 230 Compliance)
1. Navigate to **Audit Checklist**:
   - Review CARO 2020 and Form 3CD clauses.
   - Mark Clause 21(d) (Section 40A(3) cash expense) as *Non-Compliant* with remarks.
2. Navigate to **Working Papers**:
   - Open `WP-B201` (Bank Confirmation & BRS).
   - Show linked findings, transactions, and reviewer comments.
   - Demonstrate the **Maker-Checker review workflow**: Transition status from `Prepared` to `Reviewed`.

---

## 9. Step 9: Offline Local AI Assistant
1. Open the **AI Assistant** chat drawer.
2. Ask: *"Summarize all high risk cash violations in this engagement"*.
3. Observe instant factual answer citing Voucher `CPV-001` (₹45,000) and Voucher `CRV-012` (₹2,50,000).
4. Highlight that all inferences are processed 100% locally with zero external network calls.

---

## 10. Step 10: PDF Report Generation & Audit Trail
1. Navigate to **Reports**:
   - Select **Complete Audit Analysis Report (Comprehensive)**.
   - Click **Generate PDF Report**.
   - Download and open the crystal-clear PDF containing Executive Summary, Financial Summary, Reconciliation Schedules, Anomaly Register, Checklist Status, and CA Sign-off Block.
2. Navigate to **Audit Trail**:
   - Inspect the immutable chronological event log containing records of every action taken throughout the demo.
3. Navigate to **Settings & Backup**:
   - Click **Create Backup Now** to generate a timestamped SQLite archive.
