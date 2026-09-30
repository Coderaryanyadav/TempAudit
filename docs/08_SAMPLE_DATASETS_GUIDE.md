# FinAuditPro - Sample Datasets & Test Scenarios

FinAuditPro includes realistic sample test files located in `backend/sample_files/`. These files can be used to test the end-to-end audit workflow from ingestion to final report generation.

---

## 1. Directory Structure

```
backend/sample_files/
├── apex_general_ledger_fy2425.xlsx    # Full General Ledger for FY 2024-25 (Excel)
├── apex_general_ledger_fy2425.csv     # Full General Ledger for FY 2024-25 (CSV)
├── apex_bank_statement.csv            # HDFC Current Account Statement for BRS
├── apex_gstr2b_portal_download.csv    # Official GSTR-2B GST Portal Export for ITC matching
└── apex_prior_year_gl_fy2324.csv      # Prior Year (FY 2023-24) GL for YoY Variance Analysis
```

---

## 2. Injected Test Scenarios & Expectations

### Dataset 1: `apex_general_ledger_fy2425.xlsx` / `.csv`
Contains 17 normalized transactions representing real-world business operations, intentionally embedded with classic audit exceptions:

1. **Section 40A(3) Cash Payment Violation:**
   - **Voucher:** `CPV-001` | **Amount:** ₹45,000 | **Party:** Sharma Logistics Express
   - **Expected Detection:** Flagged by Deterministic Rule Engine as a High-Risk Statutory Compliance exception.
2. **Section 269ST Cash Receipt Violation:**
   - **Voucher:** `CRV-012` | **Amount:** ₹2,50,000 | **Party:** Vikas Scrap Traders
   - **Expected Detection:** Flagged as High-Risk Tax Audit exception.
3. **Duplicate Invoice Number:**
   - **Vouchers:** `PV-108` and `PV-109` | **Invoice:** `INV-7744` | **Amount:** ₹1,18,000
   - **Expected Detection:** Flagged as Duplicate Invoice / Double-Booking Exception.
4. **Invalid GSTIN Checksum:**
   - **Voucher:** `PV-145` | **GSTIN:** `27AABC1234D1Z` (14 characters instead of 15)
   - **Expected Detection:** Flagged under GST Statutory Validation.
5. **Inverted Payment Date:**
   - **Voucher:** `PV-162` | **Invoice Date:** 2024-08-10 | **Payment Date:** 2024-07-20
   - **Expected Detection:** Flagged as Date Anomaly.
6. **Round Number High-Value JV:**
   - **Voucher:** `JV-088` | **Amount:** ₹5,00,000 | **Ledger:** Consultancy & Professional Fees
   - **Expected Detection:** Flagged by GL Analysis.
7. **Missing Voucher Number:**
   - **Invoice:** `DIR-09` | **Amount:** ₹2,50,000 | **Ledger:** Directors Remuneration
   - **Expected Detection:** Flagged as Missing Sequential Documentation.
8. **Statistical Outlier (Isolation Forest Spike):**
   - **Voucher:** `PV-289` | **Amount:** ₹18,50,000 | **Ledger:** Plant & Machinery Repairs
   - **Expected Detection:** Flagged by Machine Learning Outlier Detection.
9. **Weekend / Sunday Posting:**
   - **Voucher:** `PV-312` | **Date:** 2024-11-17 (Sunday) | **Amount:** ₹1,75,000
   - **Expected Detection:** Flagged by GL Timeline Analysis.

---

### Dataset 2: `apex_bank_statement.csv`
Contains 6 bank transactions for **HDFC Bank Current Account**:
- Exact matching credits: Inward remittance of ₹5,00,000 from Bharat Heavy Infra Ltd.
- Exact matching debits: Cheque clearings of ₹3,54,000, salary payments of ₹4,50,000, and rent of ₹125,000.
- **Intentional Exception:** Unrecorded bank debit of ₹3,500 (`CHG-BANK` - Annual Folio & Ledger Maintenance Charges) present in bank statement but missing in general ledger.

---

### Dataset 3: `apex_gstr2b_portal_download.csv`
Contains 6 supplier invoices uploaded to the GST Portal:
- Confirms ITC eligibility for structural steel, office rent, repair services, and marketing.
- **Intentional Exception:** Vendor invoice `INV-7744` for Reliance Power Solutions is reflected in Books but exhibits a tax breakdown variance when cross-reconciled against portal download.

---

### Dataset 4: `apex_prior_year_gl_fy2324.csv`
Contains prior year line-item balances for comparative analysis:
- **Sales Revenue:** FY 23-24 (₹14,00,000) vs FY 24-25 (₹17,50,000) → +25.0% movement.
- **Plant & Machinery Repairs:** FY 23-24 (₹6,50,000) vs FY 24-25 (₹18,50,000) → **+184.6% movement** (Automatically flagged as high-variance operational exception).

---

## 3. Regenerating Sample Files
To regenerate fresh copies of all sample datasets at any time, run:
```bash
python -m backend.app.utils.sample_data
```
