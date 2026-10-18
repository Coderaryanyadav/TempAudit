"""
Regression tests for Phase 2: Financial Logic, Statutory Rules, and Audit Evidence
"""
import pytest
from backend.app.audit_engine.deterministic import DeterministicAuditEngine

def test_section_40a3_strictly_payment_only():
    """A cash receipt of ₹15,000 must NOT trigger Section 40A(3) expenditure disallowance."""
    transactions = [
        {
            "id": 1,
            "date": "2024-05-10",
            "voucher_no": "REC-001",
            "ledger": "Cash Account",
            "party_name": "Customer Ramesh",
            "transaction_type": "Receipt",
            "voucher_type": "Receipt",
            "debit": 0.0,
            "credit": 15000.0,
            "amount": 15000.0,
            "description": "Cash receipt against sales invoice"
        }
    ]
    engine = DeterministicAuditEngine(transactions)
    findings = engine.run_all_checks()
    sec_40a3_findings = [f for f in findings if f.get("finding_code") == "DET-TAX-40A3"]
    assert len(sec_40a3_findings) == 0, "Receipt must not trigger 40A(3) expenditure rule"

def test_section_40a3_triggers_on_cash_payment_above_10000():
    """A cash payment of ₹15,000 must trigger Section 40A(3)."""
    transactions = [
        {
            "id": 2,
            "date": "2024-05-10",
            "voucher_no": "PAY-001",
            "ledger": "Cash Account",
            "party_name": "Supplier Sharma",
            "transaction_type": "Payment",
            "voucher_type": "Payment",
            "debit": 15000.0,
            "credit": 0.0,
            "amount": 15000.0,
            "description": "Cash payment for office repairs"
        }
    ]
    engine = DeterministicAuditEngine(transactions)
    findings = engine.run_all_checks()
    sec_40a3_findings = [f for f in findings if f.get("finding_code") == "DET-TAX-40A3"]
    assert len(sec_40a3_findings) == 1
    assert sec_40a3_findings[0]["evidence"]["total_cash"] == 15000.0

def test_section_269st_strictly_receipt_only():
    """A cash payment/debit of ₹2,50,000 must NOT trigger Section 269ST cash receipt violation."""
    transactions = [
        {
            "id": 3,
            "date": "2024-06-15",
            "voucher_no": "PAY-002",
            "ledger": "Cash Account",
            "party_name": "Machinery Vendor",
            "transaction_type": "Payment",
            "voucher_type": "Payment",
            "debit": 250000.0,
            "credit": 0.0,
            "amount": 250000.0,
            "description": "Payment for workshop tools"
        }
    ]
    engine = DeterministicAuditEngine(transactions)
    findings = engine.run_all_checks()
    sec_269st_findings = [f for f in findings if f.get("finding_code") == "DET-TAX-269ST"]
    assert len(sec_269st_findings) == 0, "Payment must not trigger Section 269ST receipt rule"

def test_section_269st_triggers_on_cash_receipt_above_200000():
    """A cash credit/receipt of ₹2,50,000 must trigger Section 269ST."""
    transactions = [
        {
            "id": 4,
            "date": "2024-06-15",
            "voucher_no": "REC-002",
            "ledger": "Cash Account",
            "party_name": "Property Buyer",
            "transaction_type": "Receipt",
            "voucher_type": "Receipt",
            "debit": 0.0,
            "credit": 250000.0,
            "amount": 250000.0,
            "description": "Advance received in cash"
        }
    ]
    engine = DeterministicAuditEngine(transactions)
    findings = engine.run_all_checks()
    sec_269st_findings = [f for f in findings if f.get("finding_code") == "DET-TAX-269ST"]
    assert len(sec_269st_findings) == 1
    assert sec_269st_findings[0]["evidence"]["amount"] == 250000.0

def test_threshold_boundaries():
    """Transactions at ₹10,000 or below do NOT trigger 40A(3)."""
    transactions = [
        {
            "id": 5,
            "date": "2024-07-01",
            "voucher_no": "PAY-003",
            "ledger": "Cash in hand",
            "party_name": "Stationery Shop",
            "debit": 10000.0,
            "credit": 0.0,
            "amount": 10000.0,
            "transaction_type": "Payment"
        }
    ]
    engine = DeterministicAuditEngine(transactions)
    findings = engine.run_all_checks()
    sec_40a3 = [f for f in findings if f.get("finding_code") == "DET-TAX-40A3"]
    assert len(sec_40a3) == 0, "Payment exactly at ₹10,000 is permitted under Section 40A(3)"

def test_section_40a3_cash_ledger_debit_receipt_not_flagged():
    """
    CRITICAL REPRODUCER TEST:
    A ₹15,000 transaction with Ledger: 'Cash in hand', Description: 'Cash receipt against sales invoice',
    Transaction type: 'Receipt', Debit: 15000, Credit: 0.
    In double-entry accounting, debiting cash is a cash RECEIPT, not a payment/expenditure.
    Must NOT trigger Section 40A(3).
    """
    transactions = [
        {
            "id": 101,
            "date": "2024-05-10",
            "voucher_no": "REC-CASH-001",
            "ledger": "Cash in hand",
            "party_name": "Retail Buyer",
            "transaction_type": "Receipt",
            "voucher_type": "Receipt",
            "debit": 15000.0,
            "credit": 0.0,
            "amount": 15000.0,
            "description": "Cash receipt against sales invoice"
        }
    ]
    engine = DeterministicAuditEngine(transactions)
    findings = engine.run_all_checks()
    sec_40a3 = [f for f in findings if f.get("finding_code") == "DET-TAX-40A3"]
    assert len(sec_40a3) == 0, "Cash asset ledger debit (cash receipt) must not trigger Section 40A(3) expenditure disallowance"

def test_section_269st_aggregates_split_receipts_from_same_person():
    """
    CRITICAL REPRODUCER TEST:
    Two cash receipts of ₹1,50,000 each from the same person on the same day.
    Combined amount is ₹3,00,000, which exceeds ₹2,00,000 threshold under Section 269ST.
    Must generate a single aggregated Section 269ST finding linking both records.
    """
    transactions = [
        {
            "id": 201,
            "date": "2024-06-20",
            "voucher_no": "REC-SPLIT-01",
            "ledger": "Cash in hand",
            "party_name": "Suresh Real Estate",
            "transaction_type": "Receipt",
            "voucher_type": "Receipt",
            "debit": 150000.0,
            "credit": 0.0,
            "amount": 150000.0,
            "description": "Part cash receipt installment 1"
        },
        {
            "id": 202,
            "date": "2024-06-20",
            "voucher_no": "REC-SPLIT-02",
            "ledger": "Cash in hand",
            "party_name": "Suresh Real Estate",
            "transaction_type": "Receipt",
            "voucher_type": "Receipt",
            "debit": 150000.0,
            "credit": 0.0,
            "amount": 150000.0,
            "description": "Part cash receipt installment 2"
        }
    ]
    engine = DeterministicAuditEngine(transactions)
    findings = engine.run_all_checks()
    sec_269st = [f for f in findings if f.get("finding_code") == "DET-TAX-269ST"]
    assert len(sec_269st) == 1, "Must generate exactly 1 aggregated Section 269ST finding for split receipts"
    finding = sec_269st[0]
    assert finding["evidence"]["amount"] == 300000.0
    assert finding["evidence"]["split_receipts_count"] == 2
    assert 201 in finding["affected_records"]
    assert 202 in finding["affected_records"]

def test_section_269st_aggregates_split_receipts_across_dates_for_single_transaction():
    """
    CRITICAL STATUTORY COMPLIANCE TEST:
    Section 269ST(b) & (c) prohibit receiving ₹2,00,000 or more in cash in respect of a single transaction
    or event, EVEN IF split across different dates.
    Two cash receipts of ₹1,20,000 each on June 10 and June 15 against invoice 'INV-PROP-900'.
    Aggregate cash received for this transaction is ₹2,40,000 (> ₹2,00,000 threshold).
    Must generate a Section 269ST finding linking both records across dates.
    """
    transactions = [
        {
            "id": 301,
            "date": "2024-06-10",
            "voucher_no": "REC-CROSS-01",
            "invoice_no": "INV-PROP-900",
            "ledger": "Cash in hand",
            "party_name": "Mehta Developers",
            "transaction_type": "Receipt",
            "voucher_type": "Receipt",
            "debit": 120000.0,
            "credit": 0.0,
            "amount": 120000.0,
            "description": "Advance part cash for flat booking INV-PROP-900"
        },
        {
            "id": 302,
            "date": "2024-06-15",
            "voucher_no": "REC-CROSS-02",
            "invoice_no": "INV-PROP-900",
            "ledger": "Cash in hand",
            "party_name": "Mehta Developers",
            "transaction_type": "Receipt",
            "voucher_type": "Receipt",
            "debit": 120000.0,
            "credit": 0.0,
            "amount": 120000.0,
            "description": "Final part cash for flat booking INV-PROP-900"
        }
    ]
    engine = DeterministicAuditEngine(transactions)
    findings = engine.run_all_checks()
    sec_269st = [f for f in findings if f.get("finding_code") == "DET-TAX-269ST"]
    assert len(sec_269st) == 1, "Must generate exactly 1 aggregated Section 269ST finding for receipts across dates against single invoice"
    finding = sec_269st[0]
    assert finding["evidence"]["amount"] == 240000.0
    assert finding["evidence"]["is_aggregated_across_dates"] is True
    assert 301 in finding["affected_records"]
    assert 302 in finding["affected_records"]


