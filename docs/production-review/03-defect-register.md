# TempAudit Defect Register

This register details all defects identified during the independent due-diligence audit of TempAudit.

**Audit Baseline:** Commit `1646c4d12ad479ec8cfb0365ba5da23e9d552160`  
**Total Identified Defects:** 4 (0 P0, 1 P1, 2 P2, 1 P3)

---

## Defect Summary Table

| Defect ID | Title | Severity | Affected Component | Status |
| :--- | :--- | :---: | :--- | :---: |
| **DEF-01** | Test Suite Mutation of Live Database Admin Password | **P1 (High)** | Testing / Deployment Scripts | Open |
| **DEF-02** | Floating-Point Arithmetic Accumulation in Rule Engine | **P2 (Medium)** | Financial Engine (`deterministic.py`) | Open |
| **DEF-03** | Section 269ST Cross-Date Aggregation Heuristic Reliance | **P2 (Medium)** | Statutory Rule Engine | Open |
| **DEF-04** | Built-in Container Subagent Playwright Azure CDN Deprecation | **P3 (Low)** | Tooling / Subagent Driver | Resolved Locally |

---

## Detailed Defect Records

### DEF-01: Test Suite Mutation of Live Database Admin Password
- **Defect ID:** `DEF-01`
- **Severity:** **P1 (High)**
- **Affected Component:** `scripts/e2e_full_audit_workflow.py`, `backend/app/db/session.py`
- **Evidence & Reproduction Steps:**
  1. Initialize fresh application instance with default admin password `"SecureAdmin2026!"`.
  2. Execute `PYTHONPATH=. ./venv/bin/python scripts/e2e_full_audit_workflow.py`.
  3. Script completes, having executed a password change step to `"MasterSecurePassphrase2026!"` directly against `finauditpro.db`.
  4. Attempt subsequent login via browser or `scripts/test_real_browser_deep_input.py` using original default credentials.
  5. Authentication fails with HTTP 401 Unauthorized.
- **Expected Behavior:** Test suites and E2E automation scripts must execute within isolated, ephemeral databases (e.g., in `/tmp` or memory) and must never alter the production or default development database credentials.
- **Actual Behavior:** Script operates on the default database file `finauditpro.db`, overwriting the admin credentials on disk.
- **Impact:** Breaks subsequent independent test scripts, CI pipelines, and developer onboarding unless credentials are known to have drifted.
- **Root Cause:** Script connects to the default SQLAlchemy engine URL without overriding `FINAUDIT_DB_PATH` in the execution environment.
- **Recommended Fix:** In `scripts/e2e_full_audit_workflow.py`, create a temporary SQLite database using `tempfile.NamedTemporaryFile`, set `os.environ["FINAUDIT_DB_PATH"] = temp_db.name`, run initialization, execute the workflow, and destroy the temp file in a `finally` block.
- **Regression Test Required:** Run `scripts/e2e_full_audit_workflow.py`, then immediately run `scripts/test_real_browser_full_journey.py` with default credentials; both must pass without cross-interference.
- **Verification Status:** Verified & Documented.

---

### DEF-02: Floating-Point Arithmetic Accumulation in Rule Engine
- **Defect ID:** `DEF-02`
- **Severity:** **P2 (Medium)**
- **Affected Component:** `backend/app/audit_engine/deterministic.py` (lines 30, 64, 120, 210)
- **Evidence & Reproduction Steps:**
  1. Inspect `backend/app/audit_engine/deterministic.py`:
     ```python
     total_debit = sum(float(t.get('debit') or 0.0) for t in transactions)
     total_credit = sum(float(t.get('credit') or 0.0) for t in transactions)
     ```
  2. Synthesize an enterprise ledger with 250,000 transactions where debit amounts end in `.10` and credit amounts end in `.10`.
  3. Compute sum using standard IEEE-754 double-precision float vs Python `Decimal`.
  4. Difference accumulates to non-zero fractional cents/paise due to binary floating-point representation limits.
- **Expected Behavior:** All financial calculations must strictly use exact decimal representation (`Decimal` from `decimal` module, quantized to 2 decimal places) as defined in `backend/app/utils/money.py`.
- **Actual Behavior:** Native Python `float()` casting is used in multiple aggregation loops, risking micro-rounding inaccuracies on large data volumes.
- **Impact:** False positive double-entry balance mismatch warnings or fractional discrepancy in trial balance totals on large client files.
- **Root Cause:** Developer convenience using built-in `float()` instead of `quantize_money(to_decimal(val))` utility helper.
- **Recommended Fix:** Import `to_decimal` and `quantize_money` from `backend.app.utils.money` and replace all `float(...)` calls in `deterministic.py`.
- **Regression Test Required:** Unit test computing sum of 100,000 transactions with fractional amounts, verifying exact equality with `Decimal("0.00")`.
- **Verification Status:** Open / High-Priority Code Fix.

---

### DEF-03: Section 269ST Cross-Date Aggregation Heuristic Reliance
- **Defect ID:** `DEF-03`
- **Severity:** **P2 (Medium)**
- **Affected Component:** `backend/app/audit_engine/deterministic.py` (`check_section_269st_cash_receipts`)
- **Evidence & Reproduction Steps:**
  1. Import two cash receipt transactions from the same customer (Party: "Mehta Builders", PAN: "AABCM9876K"):
     - Transaction 1: Date 2026-05-10, Amount ₹1,20,000, Narration: "On account payment".
     - Transaction 2: Date 2026-05-15, Amount ₹1,30,000, Narration: "Part clearance of outstanding".
  2. Both receipts relate to the same sales contract, aggregating to ₹2,50,000 (> ₹2,00,000 threshold under Section 269ST(b)).
  3. Execute statutory audit rules.
  4. Neither single-day amount exceeds ₹2,00,000, and neither narration contains explicit invoice numbers or event keywords like "wedding" or "catering".
  5. The rule engine does not flag a 269ST finding for this multi-date sequence.
- **Expected Behavior:** Rule engine should cluster cash receipts by counterparty name or PAN across the entire financial year and flag aggregate cash receipts exceeding ₹2 Lakh for partner review, even if narrations lack specific keywords.
- **Actual Behavior:** Cross-date aggregation strictly depends on regex matching for invoice references (`INV-...`) or specific occasion terms.
- **Impact:** Potential failure to identify split cash receipts during tax audit Form 3CD preparation, creating client penalty risk.
- **Root Cause:** Narrow regex heuristic for conditions 269ST(b) and (c) without fallback counterparty aggregation.
- **Recommended Fix:** Implement secondary grouping by `party_name` / `counterparty_id` across the period, emitting an advisory finding: "Aggregate cash receipts from single party exceed ₹2 Lakh across period — verify whether relating to single transaction/event."
- **Regression Test Required:** Test case in `test_statutory_rules.py` verifying detection of multi-date cash receipts grouped by vendor/customer name.
- **Verification Status:** Open / Statutory Review Required.

---

### DEF-04: Built-in Container Subagent Playwright Azure CDN Deprecation
- **Defect ID:** `DEF-04`
- **Severity:** **P3 (Low)**
- **Affected Component:** IDE Subagent Browser Runtime (`playwright-go`)
- **Evidence & Reproduction Steps:**
  1. Launch IDE browser subagent in containerized developer environment.
  2. Driver downloader attempts HTTP GET to `https://playwright.azureedge.net/builds/driver/playwright-1.57.0-mac-arm64.zip`.
  3. Azure CDN returns HTTP 404 Not Found (Microsoft migrated Playwright driver distributions to GitHub releases and Cloudflare storage).
  4. Subagent halts with driver download failure.
- **Expected Behavior:** Subagent uses local system Chrome or current driver mirrors.
- **Actual Behavior:** Fails trying to reach deprecated Azure CDN URL.
- **Impact:** Limited to built-in IDE subagent browser automation; does not affect application runtime, python-playwright, or end-users.
- **Root Cause:** Hardcoded upstream download URL in third-party Go wrapper library.
- **Recommended Fix:** Local cache seeding completed: seeded `/Users/aryan/Library/Caches/ms-playwright-go/1.57.0/` with Node driver package. Python Playwright test scripts connect directly to native Chrome (`/Applications/Google Chrome.app`).
- **Regression Test Required:** `scripts/test_real_browser_full_journey.py` executes natively without network driver downloads.
- **Verification Status:** Resolved locally in test harness.
