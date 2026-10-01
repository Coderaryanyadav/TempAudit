import pytest
from backend.app.ai.context_builder import AIContextBoundary
from backend.app.ai.gateway import AIGateway
from backend.app.services.local_ai_provider import sanitize_audit_text, BuiltinDeterministicAIProvider

def test_ai_pii_sanitization_and_redaction():
    """Verify PAN, GSTIN, Bank Accounts, Phone, and Email are redacted before sending to AI."""
    raw_text = (
        "Client Rajesh Infotech Pvt Ltd (PAN: ABCDE1234F, GSTIN: 27ABCDE1234F1Z5) "
        "transferred ₹50,000 to Account No 987654321098, IFSC HDFC0001234. "
        "Contact: rajesh@infotech.com, Phone +91 9876543210."
    )
    sanitized, counts = sanitize_audit_text(raw_text, client_name="Rajesh Infotech Pvt Ltd")

    assert "ABCDE1234F" not in sanitized
    assert "[PAN_REDACTED]" in sanitized or "[GSTIN_REDACTED]" in sanitized
    assert "987654321098" not in sanitized
    assert "[BANK_ACCT_REDACTED]" in sanitized
    assert "rajesh@infotech.com" not in sanitized
    assert "[EMAIL_REDACTED]" in sanitized
    assert "[ENTITY_UNDER_AUDIT]" in sanitized

def test_ai_context_boundary_scoping_and_limits():
    """Verify engagement context boundary builder enforces character and record truncation limits."""
    transactions = [
        {"date": "2025-05-01", "ledger": "Printing Expense", "amount": 1500.0, "description": f"Office Stationery Batch {i}"}
        for i in range(100)
    ]
    context, meta = AIContextBoundary.build_engagement_context(
        engagement_id=1,
        client_name="Apex Corp",
        financial_year="2025-26",
        task_type="Expense Outlier Review",
        relevant_data={"transactions": transactions},
        max_records=20
    )

    assert meta["engagement_id"] == 1
    assert meta["char_count"] < 12000
    assert "AUDIT ENGAGEMENT SCOPE: FY 2025-26" in context
    assert "Sampled 20 records" in context

def test_ai_gateway_advisory_mode():
    """Verify AI Gateway returns advisory-only structured output."""
    res = AIGateway.generate_advisory_analysis(
        engagement_id=1,
        client_name="Acme Ltd",
        financial_year="2025-26",
        task_prompt="Review high value cash expenditure under Section 40A(3)"
    )

    assert res["is_advisory_only"] is True
    assert "analysis" in res
    assert len(res["analysis"]) > 0
    assert "boundary_meta" in res
