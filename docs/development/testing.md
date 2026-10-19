# Automated Testing & Verification Guide

FinAuditPro incorporates an exhaustive test suite verifying deterministic statutory calculations, financial invariants, authentication security, role separation, backup integrity, and local AI reasoning.

---

## 1. Running Backend Tests (Pytest)

To execute the backend test suite:

```bash
# Activate virtual environment
source venv/bin/activate

# Run all backend tests with pytest
python -m pytest backend/tests -v

# Run with test execution duration profiling
python -m pytest backend/tests -v --durations=10

# Run with code coverage reporting
python -m pytest backend/tests --cov=backend/app --cov-report=term-missing
```

### Key Test Suites Breakdown

| Test File | Focus Area & Verified Invariants |
| :--- | :--- |
| `test_local_ai_assistant.py` | Local AI intent detection, deterministic statutory calculations, and UI response synthesis |
| `test_ai_assistant_evidence_provenance.py` | Exact ID resolution, refusal to silently fall back on invalid IDs, provenance tagging |
| `test_financial_logic_statutory_rules.py` | Indian Income Tax Section 40A(3), Section 269ST, and CGST Section 16(2) compliance |
| `test_trial_balance_analysis.py` | 12-point deterministic trial balance equality and double-entry invariants |
| `test_general_ledger_analysis.py` | 13-point ledger anomaly detection and debit/credit roll-forward verification |
| `test_bank_reconciliation.py` | Multi-strategy BRS matching (exact date, reference, check clearance) |
| `test_gst_reconciliation.py` | 2B vs Purchase Register matching, ITC eligibility, tax variance analysis |
| `test_security_and_financial_invariants.py` | Role-Based Access Control, tenant isolation, and path traversal guards |
| `test_verified_backup_and_integrity_dashboard.py` | HMAC-SHA256 signature enforcement on database backups and restore validation |

---

## 2. Running Frontend Regression Tests (Node.js)

The frontend test scripts verify browser session storage, authentication refresh persistence, and token-authenticated download requests:

```bash
# 1. Verify session storage & refresh token recovery
node frontend/tests/test_login_session_refresh.js

# 2. Verify API client & token-authenticated download handlers
node frontend/tests/test_api_client_and_download_tokens.js
```

---

## 3. End-to-End Workflow Acceptance Test

To execute the automated 24-step end-to-end statutory audit verification:

```bash
python scripts/e2e_full_audit_workflow.py
```

This workflow simulates a real audit journey:
1. First-run onboarding & admin creation
2. Client and engagement provisioning
3. Ingest of general ledger, bank statements, and GSTR-2B datasets
4. Execution of the 12-point trial balance audit engine
5. High-risk transaction detection (Section 40A(3) cash violations)
6. BRS & GST ITC reconciliations
7. Synthesis of statutory working papers and PDF report export
