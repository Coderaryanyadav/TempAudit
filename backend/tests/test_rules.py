import unittest
from backend.app.audit_engine.deterministic import DeterministicAuditEngine

class TestDeterministicAuditEngine(unittest.TestCase):
    def test_section_40a3_cash_threshold(self):
        transactions = [
            {"id": 1, "date": "2024-05-10", "voucher_no": "V1", "ledger": "Freight (Cash)", "debit": 15000.0, "amount": 15000.0, "party_name": "Transporter A", "transaction_type": "Cash"},
            {"id": 2, "date": "2024-05-10", "voucher_no": "V2", "ledger": "Printing (Cash)", "debit": 4000.0, "amount": 4000.0, "party_name": "Printer B", "transaction_type": "Cash"}
        ]
        engine = DeterministicAuditEngine(transactions)
        findings = engine.run_all_checks()
        codes = [f["finding_code"] for f in findings]
        self.assertIn("DET-TAX-40A3", codes)

    def test_section_269st_cash_receipt(self):
        transactions = [
            {"id": 1, "date": "2024-06-01", "voucher_no": "V10", "ledger": "Cash Sales", "credit": 250000.0, "amount": 250000.0, "party_name": "Buyer X", "transaction_type": "Cash"}
        ]
        engine = DeterministicAuditEngine(transactions)
        findings = engine.run_all_checks()
        codes = [f["finding_code"] for f in findings]
        self.assertIn("DET-TAX-269ST", codes)

    def test_invalid_gstin_detection(self):
        transactions = [
            {"id": 1, "date": "2024-07-01", "voucher_no": "V11", "ledger": "IT Services", "debit": 50000.0, "amount": 50000.0, "party_name": "Supplier Y", "gstin": "27ABC1234"} # Invalid format
        ]
        engine = DeterministicAuditEngine(transactions)
        findings = engine.run_all_checks()
        codes = [f["finding_code"] for f in findings]
        self.assertIn("DET-GST-001", codes)

    def test_duplicate_detection(self):
        transactions = [
            {"id": 1, "date": "2024-08-01", "voucher_no": "V101", "invoice_no": "INV-99", "ledger": "Rent", "debit": 50000.0, "amount": 50000.0, "party_name": "Landlord L"},
            {"id": 2, "date": "2024-08-01", "voucher_no": "V102", "invoice_no": "INV-99", "ledger": "Rent", "debit": 50000.0, "amount": 50000.0, "party_name": "Landlord L"}
        ]
        engine = DeterministicAuditEngine(transactions)
        findings = engine.run_all_checks()
        codes = [f["finding_code"] for f in findings]
        self.assertIn("DET-DUP-01", codes)

if __name__ == "__main__":
    unittest.main()
