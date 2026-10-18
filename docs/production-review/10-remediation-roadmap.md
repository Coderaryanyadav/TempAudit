# TempAudit Prioritized Remediation Roadmap

**Audit Baseline:** Commit `1646c4d12ad479ec8cfb0365ba5da23e9d552160`  
**Target Release:** v1.0.1 Patch & v1.1.0 Feature Release

---

## 1. Remediation Schedule & Sprint Overview

| Sprint / Phase | Scope | Target Completion | Target Readiness Score |
| :--- | :--- | :---: | :---: |
| **Immediate (Hotfix 1.0.1)** | DEF-01 (Test isolation) & DEF-02 (Float precision) | 48 Hours | 94 / 100 |
| **Short-Term (Release 1.0.2)** | DEF-03 (269ST counterparty clustering) & SEC-01 (Production secrets) | 1 Week | 97 / 100 |
| **Medium-Term (Release 1.1.0)** | Dual-token refresh rotation, Alembic migrations, Prometheus metrics | 3 Weeks | 100 / 100 |

---

## 2. Prioritized Action Items with Objective Acceptance Criteria

### Priority 1: Sandboxing Test Suite Environment (DEF-01)
- **Problem:** `scripts/e2e_full_audit_workflow.py` mutates `finauditpro.db` on disk, changing the admin password and creating test data in the default development database.
- **Remediation Actions:**
  1. Modify `scripts/e2e_full_audit_workflow.py` to initialize an ephemeral SQLite database file in a temporary folder using `tempfile.TemporaryDirectory()`.
  2. Point `FINAUDIT_DB_PATH` environment variable to this temporary file during test setup.
  3. Initialize schema, run all 24 phases, and clean up the temp directory on exit.
- **Objective Acceptance Criteria:**
  - Running `scripts/e2e_full_audit_workflow.py` does not alter `finauditpro.db`.
  - Running `scripts/test_real_browser_full_journey.py` immediately afterward succeeds with the default seed password `"SecureAdmin2026!"`.

### Priority 2: Standardizing Financial Engine on Exact Decimal Representation (DEF-02)
- **Problem:** `backend/app/audit_engine/deterministic.py` casts currency values using native Python `float()`, creating micro-rounding discrepancy risks on large volume imports.
- **Remediation Actions:**
  1. Import `to_decimal` and `quantize_money` from `backend.app.utils.money` into `backend/app/audit_engine/deterministic.py`.
  2. Replace all instances of `float(...)` in summing loops with `to_decimal(...)` and accumulator `Decimal("0.00")`.
  3. Ensure all variance and threshold calculations maintain 2 decimal places with `ROUND_HALF_UP`.
- **Objective Acceptance Criteria:**
  - Unit test with 500,000 synthetic entries of ₹0.10 debit and ₹0.10 credit produces total debit = ₹50,000.00 and credit = ₹50,000.00 with variance = ₹0.00 (no IEEE-754 epsilon remainder).
  - All existing 231 backend tests pass without modification of baseline expectations.

### Priority 3: Counterparty-Based Section 269ST Clustering (DEF-03)
- **Problem:** Cross-date Section 269ST(b)/(c) cash receipts are only identified if transaction narrations contain specific invoice or event keywords.
- **Remediation Actions:**
  1. Add secondary grouping logic in `check_section_269st_cash_receipts()` that aggregates cash receipts by `(counterparty_name, pan)` across the entire fiscal year.
  2. If the aggregate cash receipts from a single counterparty exceed ₹2,00,000 across multiple dates without matching explicit event keywords, generate an **Advisory / Review Required** finding:
     *"Multiple cash receipts totaling ₹X,XX,XXX from Party Y across period — verify whether receipts relate to a single transaction or single event under Section 269ST(b)/(c)."*
- **Objective Acceptance Criteria:**
  - Ledgers with split payments lacking narration keywords generate an advisory finding directing the auditor to verify the underlying sales contracts.
  - Test case added to `backend/tests/test_statutory_rules.py` verifying multi-date party clustering.

### Priority 4: Production Configuration Enforcement (SEC-01)
- **Problem:** Default development fallback secret key exists if `SECRET_KEY` environment variable is not explicitly provided.
- **Remediation Actions:**
  1. Update `backend/app/core/config.py` to inspect `ENVIRONMENT` or `ENV` variable.
  2. If `ENV == "production"` and `SECRET_KEY == "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY_2026_MIN_32_BYTES"`, raise a fatal `RuntimeError("Production deployment refused: SECRET_KEY must be configured with a random 256-bit string.")`.
- **Objective Acceptance Criteria:**
  - Setting `ENV=production` without setting `SECRET_KEY` halts server startup with explicit error message.
  - Setting `ENV=production` with valid 32-byte secret starts normally.

### Priority 5: SQLite Connection Timeout & Busy Handler (OPS-01)
- **Problem:** Concurrent bulk uploads could encounter lock contention during high write bursts.
- **Remediation Actions:**
  1. In `backend/app/db/session.py`, attach a connect listener to SQLite engine:
     ```python
     @event.listens_for(engine, "connect")
     def set_sqlite_pragma(dbapi_connection, connection_record):
         cursor = dbapi_connection.cursor()
         cursor.execute("PRAGMA busy_timeout = 30000;")
         cursor.close()
     ```
- **Objective Acceptance Criteria:**
  - 20 concurrent simulated file uploads execute without raising `sqlite3.OperationalError: database is locked`.
