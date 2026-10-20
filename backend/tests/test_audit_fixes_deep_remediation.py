"""
Deep Audit Remediation Regression Tests:
- SEC-001: Strict settings allowlist; internal secrets (jwt_secret_key) never returned to any user.
- DATA-001: Section 269ST does not falsely merge unrelated receipts across dates on generic narration keywords like 'advance'.
- DATA-002: Dynamic statutory/configured threshold control (cash_threshold_40a3 & cash_threshold_269st).
- DATA-003: Section 40A(3) counterparty identity resolution distinguishes confirmed payees from unresolved ledger aggregations.
- AUTH-005: Case-insensitive login rate limiting (Admin vs admin vs ADMIN).
- CFG-001: Zero-dependency .env parsing and environment loading.
"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import get_db_connection, init_db
from backend.app.auth import create_access_token, get_jwt_secret
from backend.app.audit_engine.deterministic import (
    DeterministicAuditEngine,
    DEFAULT_40A3_THRESHOLD,
    DEFAULT_269ST_THRESHOLD,
    get_audit_rule_config,
)
from backend.app.env import load_dotenv


client = TestClient(app)


def setup_module(module):
    init_db()


# ------------------------------------------------------------------------------
# SEC-001: Settings Secret Non-Disclosure
# ------------------------------------------------------------------------------

def test_settings_never_discloses_jwt_signing_secret():
    """Prove that GET /api/settings never exposes jwt_secret_key or internal secrets, even if present in DB."""
    conn = get_db_connection()
    conn.execute("""
        INSERT OR REPLACE INTO users (id, username, email, full_name, password_hash, role, is_active, token_version, created_at)
        VALUES (88888, 'auditor_test_user', 'auditor_test@finauditpro.local', 'Auditor Test', 'testhash', 'Auditor', 1, 1, '2026-10-20T00:00:00')
    """)
    # Malicious or legacy injection into app_settings
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('jwt_secret_key', '\"super_secret_signing_key_12345\"', '2026-10-20T00:00:00')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('master_key', '\"hidden_master_credential\"', '2026-10-20T00:00:00')")
    conn.commit()
    conn.close()

    # Authenticate as ordinary Auditor (non-admin)
    token = create_access_token({"sub": "auditor_test_user", "role": "Auditor", "uid": 88888, "token_version": 1})
    resp = client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    settings = data.get("settings", {})

    # Critical assertions
    assert "jwt_secret_key" not in settings, "P0 finding: jwt_secret_key must NEVER be exposed in settings response"
    assert "master_key" not in settings
    assert "secret" not in settings

    # Clean up test artifact from DB
    conn = get_db_connection()
    conn.execute("DELETE FROM app_settings WHERE key IN ('jwt_secret_key', 'master_key')")
    conn.execute("DELETE FROM users WHERE id = 88888")
    conn.commit()
    conn.close()


def test_jwt_secret_isolated_in_internal_system_secrets():
    """Verify that get_jwt_secret isolates secret in internal_system_secrets and migrates legacy rows."""
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('jwt_secret_key', 'legacy_db_secret_9999', '2026-10-20T00:00:00')")
    conn.commit()
    conn.close()

    # Clear cached secret and env var to force reading DB
    import backend.app.auth as auth_mod
    saved_cache = auth_mod._CACHED_JWT_SECRET
    saved_env = os.environ.pop("FINAUDIT_SECRET_KEY", None)
    auth_mod._CACHED_JWT_SECRET = None
    try:
        secret = auth_mod.get_jwt_secret()
        assert secret is not None

        # Verify it migrated from app_settings to internal_system_secrets
        conn = get_db_connection()
        legacy_row = conn.execute("SELECT value FROM app_settings WHERE key = 'jwt_secret_key'").fetchone()
        assert legacy_row is None, "Legacy jwt_secret_key must be removed from app_settings"

        internal_row = conn.execute("SELECT value FROM internal_system_secrets WHERE key = 'jwt_secret_key'").fetchone()
        assert internal_row is not None, "Secret must be stored in internal_system_secrets table"
        conn.close()
    finally:
        auth_mod._CACHED_JWT_SECRET = saved_cache
        if saved_env is not None:
            os.environ["FINAUDIT_SECRET_KEY"] = saved_env


# ------------------------------------------------------------------------------
# DATA-001: Section 269ST Narration Heuristics Non-Merging
# ------------------------------------------------------------------------------

def test_section_269st_does_not_merge_unrelated_advances_across_dates():
    """
    DATA-001: Two independent advances of ₹1,20,000 on different dates without an explicit invoice/contract ID.
    Must NOT be merged into a synthetic 'EVENT-ADVANCE' across dates.
    Each is <= ₹2,00,000 on its date, so no Section 269ST breach should be raised.
    """
    transactions = [
        {
            "id": 901,
            "date": "2024-04-15",
            "voucher_no": "REC-04-01",
            "ledger": "Cash in hand",
            "party_name": "ABC Corporation",
            "transaction_type": "Receipt",
            "voucher_type": "Receipt",
            "debit": 120000.0,
            "credit": 0.0,
            "amount": 120000.0,
            "description": "Advance cash received for routine consultancy"
        },
        {
            "id": 902,
            "date": "2024-09-20",
            "voucher_no": "REC-09-01",
            "ledger": "Cash in hand",
            "party_name": "ABC Corporation",
            "transaction_type": "Receipt",
            "voucher_type": "Receipt",
            "debit": 120000.0,
            "credit": 0.0,
            "amount": 120000.0,
            "description": "Advance cash received for tax planning services"
        }
    ]
    engine = DeterministicAuditEngine(transactions)
    findings = engine.run_all_checks()
    sec_269st_findings = [f for f in findings if f.get("finding_code") == "DET-TAX-269ST"]
    assert len(sec_269st_findings) == 0, "Unrelated advances without contract/invoice ID must not be merged across dates"


def test_section_269st_merges_when_explicit_reference_code_present():
    """Section 269ST(b)/(c) correctly merges across dates when explicit reference code matches."""
    transactions = [
        {
            "id": 903,
            "date": "2024-05-10",
            "voucher_no": "REC-05-01",
            "ledger": "Cash in hand",
            "party_name": "XYZ Realty",
            "transaction_type": "Receipt",
            "voucher_type": "Receipt",
            "debit": 130000.0,
            "credit": 0.0,
            "amount": 130000.0,
            "description": "Part payment cash for Flat Booking BOOKING-FLAT-401"
        },
        {
            "id": 904,
            "date": "2024-07-15",
            "voucher_no": "REC-07-01",
            "ledger": "Cash in hand",
            "party_name": "XYZ Realty",
            "transaction_type": "Receipt",
            "voucher_type": "Receipt",
            "debit": 110000.0,
            "credit": 0.0,
            "amount": 110000.0,
            "description": "Final cash payment for Flat Booking BOOKING-FLAT-401"
        }
    ]
    engine = DeterministicAuditEngine(transactions)
    findings = engine.run_all_checks()
    sec_269st_findings = [f for f in findings if f.get("finding_code") == "DET-TAX-269ST"]
    assert len(sec_269st_findings) == 1, "Must merge across dates for shared reference code BOOKING-FLAT-401"
    assert sec_269st_findings[0]["evidence"]["amount"] == 240000.0
    # Penalty text should mention Section 273B reasonable cause
    assert "273B" in sec_269st_findings[0]["reason"]


# ------------------------------------------------------------------------------
# DATA-002: Dynamic Threshold Configuration
# ------------------------------------------------------------------------------

def test_configurable_thresholds_honored_by_engine():
    """Verify that custom rule_config thresholds are honored by DeterministicAuditEngine."""
    txs = [
        {
            "id": 910,
            "date": "2024-05-01",
            "voucher_no": "PAY-01",
            "ledger": "General Cash",
            "party_name": "Vendor A",
            "transaction_type": "Payment",
            "voucher_type": "Payment",
            "debit": 15000.0,
            "credit": 0.0,
            "amount": 15000.0,
            "description": "Vendor cash payment"
        }
    ]
    # Under standard 10,000 threshold: triggers
    eng_default = DeterministicAuditEngine(txs, rule_config={"cash_threshold_40a3": 10000.0})
    findings_def = eng_default.run_all_checks()
    assert len([f for f in findings_def if f.get("finding_code") == "DET-TAX-40A3"]) == 1

    # Under raised 20,000 threshold: does NOT trigger
    eng_custom = DeterministicAuditEngine(txs, rule_config={"cash_threshold_40a3": 20000.0})
    findings_cust = eng_custom.run_all_checks()
    assert len([f for f in findings_cust if f.get("finding_code") == "DET-TAX-40A3"]) == 0


# ------------------------------------------------------------------------------
# DATA-003: Section 40A(3) Counterparty Identity Resolution
# ------------------------------------------------------------------------------

def test_section_40a3_unresolved_counterparty_creates_review_candidate():
    """
    DATA-003: Multiple small cash vouchers under an expense ledger without individual payee names
    must create a DET-TAX-40A3-UNRESOLVED review candidate rather than asserting a single-person violation.
    """
    transactions = [
        {
            "id": 920,
            "date": "2024-06-01",
            "voucher_no": "EXP-01",
            "ledger": "Office Expenses (Cash)",
            "party_name": "",  # missing payee
            "transaction_type": "Payment",
            "voucher_type": "Payment",
            "debit": 6000.0,
            "credit": 0.0,
            "amount": 6000.0,
            "description": "Refreshments and office cleaning"
        },
        {
            "id": 921,
            "date": "2024-06-01",
            "voucher_no": "EXP-02",
            "ledger": "Office Expenses (Cash)",
            "party_name": "",  # missing payee
            "transaction_type": "Payment",
            "voucher_type": "Payment",
            "debit": 7000.0,
            "credit": 0.0,
            "amount": 7000.0,
            "description": "Courier and stationery supplies"
        }
    ]
    engine = DeterministicAuditEngine(transactions)
    findings = engine.run_all_checks()
    unresolved_findings = [f for f in findings if f.get("finding_code") == "DET-TAX-40A3-UNRESOLVED"]
    assert len(unresolved_findings) == 1, "Must generate review candidate for unresolved payees sharing ledger"
    assert unresolved_findings[0]["evidence"]["is_review_candidate"] is True
    assert unresolved_findings[0]["evidence"]["total_cash"] == 13000.0

    # Ensure it did NOT create a confirmed DET-TAX-40A3 breach claiming single payee violation
    confirmed_40a3 = [f for f in findings if f.get("finding_code") == "DET-TAX-40A3"]
    assert len(confirmed_40a3) == 0


# ------------------------------------------------------------------------------
# AUTH-005: Case-Insensitive Login Rate Limiting
# ------------------------------------------------------------------------------

def test_login_rate_limiting_is_case_insensitive():
    """Verify that login rate limits normalize keys to lowercase so case variations share the counter."""
    from backend.app.routers.auth import _check_login_rate_limit, _record_login_failure, _clear_login_failures
    test_user = "testratelimituser"
    _clear_login_failures(test_user)

    # Record 9 failures with mixed cases: 'TestRateLimitUser', 'TESTRATELIMITUSER', 'testratelimituser'
    for _ in range(3):
        _record_login_failure("TestRateLimitUser")
        _record_login_failure("TESTRATELIMITUSER")
        _record_login_failure("testratelimituser")

    # 10th failure
    _record_login_failure("tEsTrAtElImItUsEr")

    # Check that another attempt with any casing raises 429
    with pytest.raises(Exception) as excinfo:
        _check_login_rate_limit("TESTRATELIMITUSER")
    assert "429" in str(excinfo.value) or excinfo.value.status_code == 429

    _clear_login_failures(test_user)


# ------------------------------------------------------------------------------
# CFG-001: Zero-Dependency .env Loading
# ------------------------------------------------------------------------------

def test_load_dotenv_parses_variables():
    """Verify load_dotenv reads keys into os.environ without overwriting existing keys."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("# Sample env file\n")
        f.write("TEST_NEW_KEY_CUSTOM_ABC=123456\n")
        f.write("TEST_EXISTING_KEY_XYZ=original_val\n")
        temp_path = f.name

    try:
        os.environ["TEST_EXISTING_KEY_XYZ"] = "dont_override"
        loaded = load_dotenv(temp_path)
        assert loaded is True
        assert os.environ.get("TEST_NEW_KEY_CUSTOM_ABC") == "123456"
        assert os.environ.get("TEST_EXISTING_KEY_XYZ") == "dont_override"
    finally:
        os.remove(temp_path)
        os.environ.pop("TEST_NEW_KEY_CUSTOM_ABC", None)
        os.environ.pop("TEST_EXISTING_KEY_XYZ", None)
