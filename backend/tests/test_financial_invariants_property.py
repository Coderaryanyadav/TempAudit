"""
Comprehensive Property-Based & Deep Boundary Financial Tests (Phase 4 & 5)
Verifies arithmetic invariants, statutory rules, directionality, and threshold boundaries.
"""
import pytest
import random
from backend.app.audit_engine.deterministic import DeterministicAuditEngine

def test_permutation_invariance_of_financial_totals():
    """Property 1: Permuting transaction order must not alter net totals or trial balance differences."""
    base_txs = [
        {"id": 1, "date": "2024-04-10", "ledger": "Sales", "party_name": "Party A", "debit": 0.0, "credit": 125000.50, "amount": 125000.50},
        {"id": 2, "date": "2024-04-11", "ledger": "Purchases", "party_name": "Party B", "debit": 75000.25, "credit": 0.0, "amount": 75000.25},
        {"id": 3, "date": "2024-04-12", "ledger": "Rent Expense", "party_name": "Landlord", "debit": 50000.25, "credit": 0.0, "amount": 50000.25},
    ]
    engine_original = DeterministicAuditEngine(base_txs)
    findings_original = engine_original.run_all_checks()
    tb_original = [f for f in findings_original if f.get("finding_code") == "DET-001"]

    # Permute order 5 times
    for seed in [42, 101, 777, 999, 1234]:
        shuffled = list(base_txs)
        random.Random(seed).shuffle(shuffled)
        engine_permuted = DeterministicAuditEngine(shuffled)
        findings_permuted = engine_permuted.run_all_checks()
        tb_permuted = [f for f in findings_permuted if f.get("finding_code") == "DET-001"]

        assert len(tb_original) == len(tb_permuted)
        if tb_original:
            assert tb_original[0]["evidence"]["difference"] == tb_permuted[0]["evidence"]["difference"]

def test_zero_value_identity_invariance():
    """Property 2: Inserting zero-value transactions must not affect debit-credit totals or trigger cash rules."""
    txs_with_zeros = [
        {"id": 1, "date": "2024-04-10", "ledger": "Sales", "party_name": "Party A", "debit": 0.0, "credit": 50000.0, "amount": 50000.0},
        {"id": 2, "date": "2024-04-10", "ledger": "Cash Account", "party_name": "Zero Vendor", "debit": 0.0, "credit": 0.0, "amount": 0.0, "transaction_type": "Payment"},
        {"id": 3, "date": "2024-04-10", "ledger": "Bank Account", "party_name": "Zero Customer", "debit": 0.0, "credit": 0.0, "amount": 0.0, "transaction_type": "Receipt"}
    ]
    engine = DeterministicAuditEngine(txs_with_zeros)
    findings = engine.run_all_checks()
    sec_40a3 = [f for f in findings if f.get("finding_code") == "DET-TAX-40A3"]
    sec_269st = [f for f in findings if f.get("finding_code") == "DET-TAX-269ST"]
    assert len(sec_40a3) == 0, "Zero payment must not trigger Section 40A(3)"
    assert len(sec_269st) == 0, "Zero receipt must not trigger Section 269ST"

def test_section_40a3_daily_aggregate_across_multiple_vouchers():
    """Property 4: Multiple payments on same date to same person exceeding ₹10,000 in aggregate must be flagged."""
    txs = [
        {
            "id": 101, "date": "2024-05-15", "voucher_no": "CPV-01",
            "ledger": "Cash Account", "party_name": "Transporter Logistics Ltd",
            "transaction_type": "Payment", "voucher_type": "Payment",
            "debit": 6000.0, "credit": 0.0, "amount": 6000.0, "description": "Freight payment Part 1"
        },
        {
            "id": 102, "date": "2024-05-15", "voucher_no": "CPV-02",
            "ledger": "Cash Account", "party_name": "Transporter Logistics Ltd",
            "transaction_type": "Payment", "voucher_type": "Payment",
            "debit": 5500.0, "credit": 0.0, "amount": 5500.0, "description": "Freight payment Part 2"
        }
    ]
    engine = DeterministicAuditEngine(txs)
    findings = engine.run_all_checks()
    sec_40a3 = [f for f in findings if f.get("finding_code") == "DET-TAX-40A3"]
    assert len(sec_40a3) == 1, "Aggregate ₹11,500 must trigger Section 40A(3) disallowance"
    assert sec_40a3[0]["evidence"]["total_cash"] == 11500.0
    assert 101 in sec_40a3[0]["affected_records"]
    assert 102 in sec_40a3[0]["affected_records"]

def test_section_40a3_date_segregation_avoids_false_positive():
    """Property 5: Payments of ₹8,000 on two separate dates to the same person must NOT trigger 40A(3)."""
    txs = [
        {
            "id": 201, "date": "2024-05-15", "voucher_no": "CPV-10",
            "ledger": "Cash in Hand", "party_name": "Consultant Sen",
            "transaction_type": "Payment", "debit": 8000.0, "credit": 0.0, "amount": 8000.0
        },
        {
            "id": 202, "date": "2024-05-16", "voucher_no": "CPV-11",
            "ledger": "Cash in Hand", "party_name": "Consultant Sen",
            "transaction_type": "Payment", "debit": 8000.0, "credit": 0.0, "amount": 8000.0
        }
    ]
    engine = DeterministicAuditEngine(txs)
    findings = engine.run_all_checks()
    sec_40a3 = [f for f in findings if f.get("finding_code") == "DET-TAX-40A3"]
    assert len(sec_40a3) == 0, "Separate dates under threshold must not trigger 40A(3)"

def test_section_40a3_counterparty_segregation():
    """Property 6: Payments of ₹8,000 on the same date to two different persons must NOT trigger 40A(3)."""
    txs = [
        {
            "id": 301, "date": "2024-05-15", "voucher_no": "CPV-20",
            "ledger": "Petty Cash", "party_name": "Vendor A",
            "transaction_type": "Payment", "debit": 8000.0, "credit": 0.0, "amount": 8000.0
        },
        {
            "id": 302, "date": "2024-05-15", "voucher_no": "CPV-21",
            "ledger": "Petty Cash", "party_name": "Vendor B",
            "transaction_type": "Payment", "debit": 8000.0, "credit": 0.0, "amount": 8000.0
        }
    ]
    engine = DeterministicAuditEngine(txs)
    findings = engine.run_all_checks()
    sec_40a3 = [f for f in findings if f.get("finding_code") == "DET-TAX-40A3"]
    assert len(sec_40a3) == 0, "Different vendors on same day must not aggregate"

def test_section_269st_exact_threshold_boundary():
    """Property 7: Receipt of ₹1,99,999.99 passes; ₹2,00,000.00 triggers Section 269ST."""
    # Under boundary
    engine_under = DeterministicAuditEngine([{
        "id": 401, "date": "2024-06-01", "voucher_no": "CRV-01",
        "ledger": "Cash Account", "party_name": "Buyer Alpha",
        "transaction_type": "Receipt", "credit": 199999.99, "debit": 0.0, "amount": 199999.99
    }])
    findings_under = [f for f in engine_under.run_all_checks() if f.get("finding_code") == "DET-TAX-269ST"]
    assert len(findings_under) == 0, "₹1,99,999.99 is strictly below ₹2,00,000 threshold"

    # Exactly at boundary
    engine_exact = DeterministicAuditEngine([{
        "id": 402, "date": "2024-06-01", "voucher_no": "CRV-02",
        "ledger": "Cash Account", "party_name": "Buyer Alpha",
        "transaction_type": "Receipt", "credit": 200000.00, "debit": 0.0, "amount": 200000.00
    }])
    findings_exact = [f for f in engine_exact.run_all_checks() if f.get("finding_code") == "DET-TAX-269ST"]
    assert len(findings_exact) == 1, "₹200,000.00 must trigger Section 269ST violation"

def test_round_number_spike_detection_accuracy():
    """Property 8: Flag exact round number JVs of ₹1,00,000+ while ignoring irregular figures."""
    txs = [
        {"id": 501, "date": "2024-06-10", "voucher_no": "JV-01", "ledger": "Legal Fees", "amount": 500000.0, "debit": 500000.0, "credit": 0.0, "voucher_type": "Journal"},
        {"id": 502, "date": "2024-06-10", "voucher_no": "JV-02", "ledger": "Printing", "amount": 500123.45, "debit": 500123.45, "credit": 0.0, "voucher_type": "Journal"}
    ]
    engine = DeterministicAuditEngine(txs)
    findings = engine.run_all_checks()
    round_findings = [f for f in findings if f.get("finding_code") == "DET-ROUND-001"]
    assert len(round_findings) == 1
    assert 501 in round_findings[0]["affected_records"]
    assert 502 not in round_findings[0]["affected_records"]

def test_gstin_syntax_validation():
    """Property 9: Statutory 15-character GSTIN structure validation."""
    txs = [
        {"id": 601, "gstin": "27AABCU9603R1ZM", "amount": 50000.0, "party_name": "Valid Vendor"},
        {"id": 602, "gstin": "27AABCU9603R1Z", "amount": 50000.0, "party_name": "Short 14-char"},
        {"id": 603, "gstin": "27AABCU9603R1Z99", "amount": 50000.0, "party_name": "Long 16-char"},
        {"id": 604, "gstin": "99INVALIDGSTIN!", "amount": 50000.0, "party_name": "Malformed Special Chars"}
    ]
    engine = DeterministicAuditEngine(txs)
    findings = engine.run_all_checks()
    gst_findings = [f for f in findings if f.get("finding_code") == "DET-GST-001"]
    flagged_ids = [r for f in gst_findings for r in f["affected_records"]]

    assert 601 not in flagged_ids, "Valid GSTIN must not be flagged"
    assert 602 in flagged_ids, "14-char GSTIN must be flagged"
    assert 603 in flagged_ids, "16-char GSTIN must be flagged"
    assert 604 in flagged_ids, "Malformed GSTIN must be flagged"

def test_engine_idempotency_without_state_leakage():
    """Property 10: Repeated execution on identical dataset must produce identical findings without state leakage."""
    dataset = [
        {"id": 1, "date": "2024-04-01", "ledger": "Cash Account", "party_name": "Vendor A", "transaction_type": "Payment", "debit": 15000.0, "credit": 0.0, "amount": 15000.0},
        {"id": 2, "date": "2024-04-01", "ledger": "Cash Account", "party_name": "Customer B", "transaction_type": "Receipt", "credit": 250000.0, "debit": 0.0, "amount": 250000.0}
    ]
    engine = DeterministicAuditEngine(dataset)
    runs = [engine.run_all_checks() for _ in range(5)]

    for run in runs[1:]:
        assert len(run) == len(runs[0])
        assert [f["finding_code"] for f in run] == [f["finding_code"] for f in runs[0]]
        assert [f["affected_records"] for f in run] == [f["affected_records"] for f in runs[0]]
