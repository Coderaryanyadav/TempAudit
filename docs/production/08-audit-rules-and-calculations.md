# 08 — Audit Rules, Calculations & Statutory Grounding

**Document**: Audit Procedure Specification  
**Application**: FinAuditPro  
**Release**: 1.0.0  

---

## 1. Rule Specification Matrix

### Rule 1: Section 40A(3) — Cash Payment Limitation
- **Statutory Reference**: Section 40A(3) of the Income Tax Act, 1961 read with Rule 6DD.
- **Form 3CD Clause**: Clause 21(d) (*Amounts deemed to be profits and gains under Section 40A(3)*).
- **Threshold**: Exceeding **₹10,000** to a single person in a single day (₹35,000 for transport contractors).
- **Classification Precondition**:
  - Must evaluate transaction directionality.
  - Cash ledger credit = Payment.
  - Cash ledger debit = Receipt (EXCLUDED from 40A(3)).
  - Explicit keywords: `payment`, `paid`, `expense`.
- **Finding Code**: `DET-TAX-40A3`
- **Severity**: HIGH
- **Automated Test**: `backend/tests/test_financial_logic_statutory_rules.py::test_section_40a3_flags_cash_payments_exceeding_10000`

---

### Rule 2: Section 269ST(a) — Cash Receipts (Per Person Per Day)
- **Statutory Reference**: Section 269ST(a) of the Income Tax Act, 1961.
- **Penalty Reference**: Section 271DA (100% penalty of amount received).
- **Form 3CD Clause**: Clause 31 (*Particulars of each receipt in an amount exceeding the limit specified in Section 269ST*).
- **Threshold**: **₹2,00,000 or more** received in cash from a person in a day.
- **Aggregation Key**: `(party, date)`
- **Finding Code**: `DET-TAX-269ST`
- **Severity**: CRITICAL
- **Automated Test**: `backend/tests/test_financial_logic_statutory_rules.py::test_section_269st_aggregates_split_receipts_from_same_person`

---

### Rule 3: Section 269ST(b) & (c) — Cross-Date Single Transaction or Event Aggregation
- **Statutory Reference**: Section 269ST(b) & (c) of the Income Tax Act, 1961.
- **Threshold**: **₹2,00,000 or more** in cash in respect of a single transaction or relating to one event/occasion, even if split across different dates.
- **Aggregation Key**: `(party, invoice_no/reference/event_token)`
- **Narrative Token Extraction**: Scans transaction descriptions for `INV`, `BILL`, `BOOKING`, `CONTR`, `EVENT`, `ADV`, `WEDDING`, `FLAT`, `PLOT`.
- **Deduplication Safeguard**: Does not duplicate findings if transactions were already flagged under daily aggregation.
- **Finding Code**: `DET-TAX-269ST`
- **Severity**: CRITICAL
- **Automated Test**: `backend/tests/test_financial_logic_statutory_rules.py::test_section_269st_aggregates_split_receipts_across_dates_for_single_transaction`

---

### Rule 4: Indian GSTIN Structural Validation
- **Statutory Reference**: Rule 8 of the Central Goods and Services Tax (CGST) Rules, 2017.
- **Structure**: 15 Characters:
  - `[0-9]{2}`: 2-Digit State Code (01 to 38)
  - `[A-Z]{5}[0-9]{4}[A-Z]{1}`: 10-Character PAN
  - `[1-9A-Z]{1}`: Entity Registration Number
  - `Z`: Fixed Alphabet
  - `[0-9A-Z]{1}`: Mod-36 Checksum Character
- **Finding Code**: `DET-GST-FORMAT`
- **Severity**: MEDIUM

---

### Rule 5: Mathematical Trial Balance Equilibrium
- **Standard**: Guidance Note on Audit of Financial Statements (ICAI).
- **Invariant**: $\sum Debit == \sum Credit$.
- **Finding Code**: `DET-TB-UNBALANCED`
- **Severity**: CRITICAL (Blocks unqualified report generation).

---

### Rule 6: Benford's Law First-Digit Analysis (Nigrini Standard)
- **Forensic Standard**: Mark Nigrini Forensic Analytics (Z-score & Mean Absolute Deviation).
- **Methodology**: Evaluates leading digits (1 through 9) against logarithmic probability $P(d) = \log_{10}(1 + 1/d)$.
- **Deviation Thresholds**:
  - Non-Conformity: $MAD > 0.015$
  - Significant Irregularity: $MAD > 0.025$
- **Classification**: Statistical anomaly requiring auditor review, NOT definitive fraud.

---

### Rule 7: Isolation Forest Multi-Variate Anomaly Modeling
- **Algorithm**: Scikit-Learn `IsolationForest` ($n\_estimators=100, contamination=0.03$).
- **Features Extracted**: Normalized Amount, Day of Week, Day of Month, Round-Number Flag.
- **Finding Code**: `STAT-ML-ISOLATION-OUTLIER`
- **Classification**: Statistical outlier flag for substantive testing.
