"""
Offline AI Assistant Evidence Grounding & Provenance Verification Tests (Phase 7)
Verifies exact ID resolution, refusal to silently fall back on invalid IDs,
provenance attribution, and privacy boundaries.
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from backend.app.database import get_db_connection
from backend.app.services.local_ai_assistant_engine import LocalAIAssistantEngine, MANDATORY_DISCLAIMER

@pytest.fixture
def seeded_ai_engagement():
    """Sets up an isolated engagement with known transactions and findings."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cur = conn.execute("INSERT INTO clients (name, pan, created_at) VALUES ('Evidence Client', 'ABCDE4444D', ?)", (now_str,))
    client_id = cur.lastrowid
    cur = conn.execute("INSERT INTO engagements (client_id, title, financial_year, created_at) VALUES (?, 'Evidence Audit', '2024-25', ?)", (client_id, now_str))
    eng_id = cur.lastrowid

    # 1. Transactions
    cur_tx1 = conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type, description)
        VALUES (?, '2024-05-10', 'V-TEST-9101', 'Freight Outward', 'Express Cargo', 15000.0, 0.0, 15000.0, 'Payment', 'Cash freight charges')
    """, (eng_id,))
    tx1_id = cur_tx1.lastrowid

    cur_tx2 = conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type, description)
        VALUES (?, '2024-05-12', 'V-TEST-9102', 'Scrap Sales', 'Metal Recyclers', 0.0, 250000.0, 250000.0, 'Receipt', 'Cash scrap sale')
    """, (eng_id,))
    tx2_id = cur_tx2.lastrowid

    # 2. Findings
    cur_f1 = conn.execute("""
        INSERT INTO audit_findings (engagement_id, finding_code, category, severity, risk_score, title, description, rule_used, engine_type, status, created_at)
        VALUES (?, 'DET-TAX-40A3', 'Statutory Compliance', 'CRITICAL', 9.0, 'Section 40A(3) Cash Payment', 'Cash freight exceeding 10000', 'Section 40A(3)', 'DETERMINISTIC', 'Open', ?)
    """, (eng_id, now_str))
    f1_id = cur_f1.lastrowid

    cur_f2 = conn.execute("""
        INSERT INTO audit_findings (engagement_id, finding_code, category, severity, risk_score, title, description, rule_used, engine_type, status, created_at)
        VALUES (?, 'DET-TAX-269ST', 'Statutory Compliance', 'CRITICAL', 9.5, 'Section 269ST Cash Receipt', 'Cash receipt of 250000', 'Section 269ST', 'DETERMINISTIC', 'Open', ?)
    """, (eng_id, now_str))
    f2_id = cur_f2.lastrowid

    conn.commit()
    conn.close()
    return {"eng_id": eng_id, "tx1_id": tx1_id, "tx2_id": tx2_id, "f1_id": f1_id, "f2_id": f2_id}

def test_ai_assistant_exact_finding_id_resolution(seeded_ai_engagement):
    """Valid finding_id must resolve strictly to the targeted finding."""
    data = seeded_ai_engagement
    engine = LocalAIAssistantEngine(data["eng_id"])
    res = engine.process_query(query="Draft working paper observation", finding_id=data["f2_id"])

    assert "CREATE_AUDIT_OBSERVATION" in res.get("intent", "")
    assert "DET_TAX_269ST" in res.get("response", "")
    assert res.get("evidence")[0]["finding_id"] == data["f2_id"]
    assert res.get("evidence")[0]["title"] == "Section 269ST Cash Receipt"
    assert res.get("disclaimer") == MANDATORY_DISCLAIMER
    assert res.get("provenance") in ["DETERMINISTIC_RULE", "LOCAL_LLM"]

def test_ai_assistant_invalid_finding_id_refuses_silent_fallback(seeded_ai_engagement):
    """Invalid finding_id must NOT silently fall back to an unrelated finding."""
    data = seeded_ai_engagement
    engine = LocalAIAssistantEngine(data["eng_id"])
    res = engine.process_query(query="Draft observation", finding_id=999999)

    assert "could not be resolved from active audit findings" in res.get("response", "")
    assert "999999" in res.get("response", "")
    assert "DET_TAX_40A3" not in res.get("response", ""), "Must not silently substitute first finding"

def test_ai_assistant_exact_transaction_id_resolution(seeded_ai_engagement):
    """Valid transaction_id must resolve strictly to the requested voucher."""
    data = seeded_ai_engagement
    engine = LocalAIAssistantEngine(data["eng_id"])
    res = engine.process_query(query="Why was this flagged?", transaction_id=data["tx1_id"])

    assert "EXPLAIN_FLAGGED_TRANSACTION" in res.get("intent", "")
    assert "V-TEST-9101" in res.get("response", "")
    assert "Freight Outward" in res.get("response", "")
    assert "15,000" in res.get("response", "")

def test_ai_assistant_invalid_transaction_id_refuses_silent_fallback(seeded_ai_engagement):
    """Invalid transaction_id must return unresolvable notice without substituting another voucher."""
    data = seeded_ai_engagement
    engine = LocalAIAssistantEngine(data["eng_id"])
    res = engine.process_query(query="Explain this transaction", transaction_id=888888)

    assert "could not be resolved" in res.get("response", "")
    assert "888888" in res.get("response", "")
    assert "V-TEST-9101" not in res.get("response", "")

def test_ai_assistant_provenance_attribution_with_mocked_llm(seeded_ai_engagement):
    """Verifies that when local LLM is available, provenance is tagged as LOCAL_LLM."""
    data = seeded_ai_engagement
    engine = LocalAIAssistantEngine(data["eng_id"])

    mock_provider = MagicMock()
    mock_provider.check_health.return_value = (True, "Running", "qwen2.5-coder")
    mock_provider.generate.return_value = {
        "text": "Based on the statutory records, this client adheres to relevant accounting standards.",
        "model": "qwen2.5-coder",
        "provenance": "LOCAL_LLM"
    }

    with patch("backend.app.services.local_ai_provider.LocalAIModelManager.get_active_provider", return_value=mock_provider), \
         patch("backend.app.services.local_ai_provider.LocalAIModelManager.get_config", return_value={"is_enabled": True, "engine": "LMStudio", "model_name": "qwen2.5-coder"}):
        res = engine.process_query(query="What is the general accounting status of this engagement?")
        assert res.get("provenance") == "LOCAL_LLM"
        assert "Based on the statutory records" in res.get("response", "")

def test_ai_assistant_refusal_not_overwritten_by_mocked_llm(seeded_ai_engagement):
    """
    CRITICAL REPRODUCER TEST:
    When user requests explanation for nonexistent transaction ID (e.g. 999999),
    even if an LLM is active and returns hallucinated compliance ('No issues found. Everything is compliant'),
    the assistant MUST NOT overwrite the deterministic refusal.
    """
    data = seeded_ai_engagement
    engine = LocalAIAssistantEngine(data["eng_id"])

    mock_provider = MagicMock()
    mock_provider.check_health.return_value = (True, "Running", "qwen2.5-coder")
    mock_provider.generate.return_value = {
        "text": "No issues found. Everything is compliant.",
        "model": "qwen2.5-coder",
        "provenance": "LOCAL_LLM"
    }

    with patch("backend.app.services.local_ai_provider.LocalAIModelManager.get_active_provider", return_value=mock_provider), \
         patch("backend.app.services.local_ai_provider.LocalAIModelManager.get_config", return_value={"is_enabled": True, "engine": "LMStudio", "model_name": "qwen2.5-coder"}):
        res = engine.process_query(query="Explain this transaction", transaction_id=999999)
        assert "could not be resolved" in res.get("response", "")
        assert "999999" in res.get("response", "")
        assert "Everything is compliant" not in res.get("response", "")
        assert res.get("provenance") == "DETERMINISTIC_RULE"

