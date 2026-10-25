import unittest
from decimal import Decimal
from backend.app.services.duplicate_missing_detector import detect_duplicates_and_gaps
from backend.app.audit_engine.deterministic import DeterministicAuditEngine


class TestAuditRemediationDefects(unittest.TestCase):
    """
    Regression test suite verifying root-cause fixes for DEF-01 to DEF-05:
    - DEF-01: Directionality in exact duplicates and accounting reversals.
    - DEF-02: Temporal window constraints preventing periodic recurring expenses from triggering false-positive duplicates.
    - DEF-03: Opposing debit and credit entries excluded from fuzzy duplicate detection.
    - DEF-04: Trial balance decimal precision preventing floating-point accumulation drift.
    - DEF-05: Statutory second proviso transport threshold under Section 40A(3).
    """

    def test_exact_duplicate_respects_debit_credit_directionality(self):
        """DEF-01: Offset accounting entries (Debit vs Credit) must not be flagged as exact duplicates."""
        txs = [
            {
                "id": 101,
                "date": "2024-06-15",
                "voucher_no": "VCH-099",
                "invoice_no": "INV-099",
                "ledger": "Repairs & Maintenance",
                "party_name": "ABC Engineering",
                "debit": 5000.0,
                "credit": 0.0,
                "amount": 5000.0,
                "description": "Equipment servicing charge"
            },
            {
                "id": 102,
                "date": "2024-06-15",
                "voucher_no": "VCH-099",
                "invoice_no": "INV-099",
                "ledger": "Repairs & Maintenance",
                "party_name": "ABC Engineering",
                "debit": 0.0,
                "credit": 5000.0,
                "amount": 5000.0,
                "description": "Credit note reversal for equipment servicing"
            }
        ]
        res = detect_duplicates_and_gaps(txs)
        exact_groups = [g for g in res["duplicate_groups"] if g["group_type"] == "Exact Duplicate"]
        self.assertEqual(len(exact_groups), 0, "Opposite debit/credit reversals must not be flagged as exact duplicates")

    def test_fuzzy_duplicate_skips_periodic_recurring_monthly_transactions(self):
        """DEF-02: Normal monthly recurring payments (e.g. rent) >21 days apart must not trigger fuzzy duplicate alerts."""
        txs = [
            {
                "id": 201,
                "date": "2024-04-01",
                "voucher_no": "RNT-04",
                "invoice_no": "",
                "ledger": "Office Rent",
                "party_name": "Sunrise Commercial Properties Pvt Ltd",
                "debit": 60000.0,
                "credit": 0.0,
                "amount": 60000.0,
                "description": "Office rent payment for the month of April 2024"
            },
            {
                "id": 202,
                "date": "2024-05-01",
                "voucher_no": "RNT-05",
                "invoice_no": "",
                "ledger": "Office Rent",
                "party_name": "Sunrise Commercial Properties Pvt Ltd",
                "debit": 60000.0,
                "credit": 0.0,
                "amount": 60000.0,
                "description": "Office rent payment for the month of May 2024"
            }
        ]
        res = detect_duplicates_and_gaps(txs)
        fuzzy_groups = [g for g in res["duplicate_groups"] if "Fuzzy" in g["group_type"]]
        self.assertEqual(len(fuzzy_groups), 0, "Monthly recurring rent payments 30 days apart must not be flagged as duplicates")

    def test_fuzzy_duplicate_skips_opposing_debit_credit_entries(self):
        """DEF-03: Opposing debit and credit entries must not be paired as fuzzy duplicates."""
        txs = [
            {
                "id": 301,
                "date": "2024-07-10",
                "voucher_no": "PUR-101",
                "invoice_no": "",
                "ledger": "Raw Materials",
                "party_name": "Apex Suppliers",
                "debit": 45000.0,
                "credit": 0.0,
                "amount": 45000.0,
                "description": "Material purchase batch 101"
            },
            {
                "id": 302,
                "date": "2024-07-12",
                "voucher_no": "PAY-101",
                "invoice_no": "",
                "ledger": "Raw Materials",
                "party_name": "Apex Suppliers",
                "debit": 0.0,
                "credit": 45000.0,
                "amount": 45000.0,
                "description": "Vendor credit adjustment for batch 101"
            }
        ]
        res = detect_duplicates_and_gaps(txs)
        self.assertEqual(len(res["duplicate_groups"]), 0, "Debit purchase and credit adjustment must not be flagged as duplicates")

    def test_deterministic_trial_balance_exact_decimal_precision(self):
        """DEF-04: Trial balance reconciliation engine uses exact Decimal arithmetic to eliminate float drift."""
        # Create 3 transactions whose float sums might suffer precision loss
        txs = [
            {"id": 1, "date": "2024-04-01", "voucher_no": "V1", "ledger": "Sales", "debit": 0.0, "credit": 100.10, "amount": 100.10},
            {"id": 2, "date": "2024-04-01", "voucher_no": "V2", "ledger": "Service", "debit": 0.0, "credit": 200.20, "amount": 200.20},
            {"id": 3, "date": "2024-04-01", "voucher_no": "V3", "ledger": "Bank", "debit": 300.30, "credit": 0.0, "amount": 300.30},
        ]
        engine = DeterministicAuditEngine(txs)
        engine.check_debit_credit_balance()
        tb_findings = [f for f in engine.findings if f["finding_code"] == "DET-TB-001"]
        self.assertEqual(len(tb_findings), 0, "Balanced trial balance with fractional amounts must not report an imbalance")

    def test_configurable_40a3_goods_carriage_transport_threshold(self):
        """DEF-05: Second proviso to Section 40A(3) allows ₹35,000 threshold for transport/goods carriages when configured."""
        config_with_transport = {
            "cash_threshold_40a3": 10000.0,
            "cash_threshold_40a3_transport": 35000.0,
            "cash_threshold_269st": 200000.0
        }
        txs = [
            # Transport cash payment of ₹25,000 (below ₹35,000 second proviso limit)
            {
                "id": 401,
                "date": "2024-08-10",
                "voucher_no": "TR-01",
                "ledger": "Freight & Cartage",
                "party_name": "National Roadlines",
                "debit": 25000.0,
                "credit": 0.0,
                "amount": 25000.0,
                "transaction_type": "Payment",
                "description": "Goods carriage hiring charges"
            },
            # General printing cash payment of ₹15,000 (exceeds ₹10,000 general limit)
            {
                "id": 402,
                "date": "2024-08-10",
                "voucher_no": "PR-01",
                "ledger": "Printing & Stationery",
                "party_name": "Quick Print House",
                "debit": 15000.0,
                "credit": 0.0,
                "amount": 15000.0,
                "transaction_type": "Payment",
                "description": "Office catalog printing in cash"
            }
        ]
        engine = DeterministicAuditEngine(txs, rule_config=config_with_transport)
        findings = engine.run_all_checks()
        f40a3 = [f for f in findings if f["finding_code"] == "DET-TAX-40A3"]
        self.assertEqual(len(f40a3), 1, "Only general printing payment should breach 40A(3), transport should be within ₹35,000 limit")
        self.assertIn("Quick Print House", f40a3[0]["title"])


if __name__ == "__main__":
    unittest.main()
