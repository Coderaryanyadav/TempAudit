import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.services.duplicate_missing_detector import (
    detect_duplicates_and_gaps,
    update_duplicate_group_review,
    update_sequence_gap_review,
    string_similarity,
    code_similarity,
    extract_sequence_parts,
    extract_cheque_numbers
)

class TestDuplicateMissingDetectionEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

        # Login
        res = cls.client.post("/api/auth/login", json={"username": "admin", "password": "adminpassword123"})
        if res.status_code == 200:
            cls.token = res.json()["access_token"]
        else:
            res = cls.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
            cls.token = res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def setUp(self):
        conn = get_db_connection()
        cur = conn.cursor()

        # Create unique client & engagement
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, gstin, created_at, updated_at)
        VALUES ('Bharat Infotech Solutions Pvt Ltd', 'Private Limited Company', 'AABCB5544F', '27AABCB5544F1Z9', datetime('now'), datetime('now'))
        """)
        self.client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
        VALUES (?, 'Statutory Audit FY 2024-25', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
        """, (self.client_id,))
        self.eng_id = cur.lastrowid

        # Insert test transactions covering:
        # 1. Exact duplicates (Tx 1 & Tx 2)
        # 2. Same Invoice Number (Tx 3 & Tx 4)
        # 3. Same Date + Amount + Party (Tx 5 & Tx 6)
        # 4. Same Reference / UTR (Tx 7 & Tx 8)
        # 5. Fuzzy Duplicate Party Name (Tx 9 & Tx 10)
        # 6. Invoice Sequence Gaps (INV-001, INV-002, INV-005) -> Gap: INV-003, INV-004
        # 7. Voucher Sequence Gaps (V-101, V-102, V-105) -> Gap: V-103, V-104
        # 8. Cheque Sequence Gaps (102450, 102451, 102454) -> Gap: 102452, 102453
        test_txs = [
            # Exact Duplicates (Pair 1)
            (self.eng_id, '2024-05-10', 'Office Expense Ledger', 'Sharma Stationery Mart', 15000.0, 0.0, 15000.0, 'V-EX-01', 'INV-STAT-101', 'Office stationery supplies', 'REF-8801'),
            (self.eng_id, '2024-05-10', 'Office Expense Ledger', 'Sharma Stationery Mart', 15000.0, 0.0, 15000.0, 'V-EX-01', 'INV-STAT-101', 'Office stationery supplies', 'REF-8801'),

            # Same Invoice Number across distinct entries (Pair 2)
            (self.eng_id, '2024-05-14', 'Hardware Purchases', 'Dell India Pvt Ltd', 85000.0, 0.0, 85000.0, 'V-HW-01', 'INV-DELL-9988', 'Laptops for audit team', 'REF-8802'),
            (self.eng_id, '2024-05-18', 'Hardware Purchases', 'Dell India Pvt Ltd', 85000.0, 0.0, 85000.0, 'V-HW-02', 'INV-DELL-9988', 'Duplicate invoice recording', 'REF-8803'),

            # Same Date + Amount + Party (Pair 3)
            (self.eng_id, '2024-06-01', 'Consulting Fees', 'Apex Legal Associates', 50000.0, 0.0, 50000.0, 'V-LEG-01', 'INV-LEG-01', 'Retainer fee June', 'REF-8804'),
            (self.eng_id, '2024-06-01', 'Legal Expenses', 'Apex Legal Associates', 50000.0, 0.0, 50000.0, 'V-LEG-02', 'INV-LEG-02', 'Legal consultancy charges', 'REF-8805'),

            # Same Reference / UTR Number (Pair 4)
            (self.eng_id, '2024-06-15', 'Vendor Payment Account', 'Tata Power Ltd', 0.0, 32000.0, 32000.0, 'V-TP-01', 'INV-TP-1', 'Electricity bill payment', 'UTR-HDFC-991823'),
            (self.eng_id, '2024-06-16', 'Utilities Ledger', 'Tata Power Ltd', 32000.0, 0.0, 32000.0, 'V-TP-02', 'INV-TP-2', 'Power utility payment duplicate UTR', 'UTR-HDFC-991823'),

            # Fuzzy Match: Similar Party Name & Identical Amount (Pair 5)
            (self.eng_id, '2024-07-01', 'Software License Cost', 'M/S Reliance Digital Retail Ltd', 45000.0, 0.0, 45000.0, 'V-SF-01', 'INV-REL-01', 'Antivirus software licenses', 'REF-8806'),
            (self.eng_id, '2024-07-02', 'IT Support Expense', 'Reliance Digital Retail Limited', 45000.0, 0.0, 45000.0, 'V-SF-02', 'INV-REL-02', 'Software maintenance renewal', 'REF-8807'),

            # Sequence Gap Data: Invoices (INV-2024-001, INV-2024-002, INV-2024-005)
            (self.eng_id, '2024-08-01', 'Sales Revenue', 'Customer Alpha', 0.0, 100000.0, 100000.0, 'V-101', 'INV-2024-001', 'Sales billing 1', 'REF-8808'),
            (self.eng_id, '2024-08-02', 'Sales Revenue', 'Customer Beta', 0.0, 120000.0, 120000.0, 'V-102', 'INV-2024-002', 'Sales billing 2', 'REF-8809'),
            (self.eng_id, '2024-08-05', 'Sales Revenue', 'Customer Gamma', 0.0, 150000.0, 150000.0, 'V-105', 'INV-2024-005', 'Sales billing 5', 'REF-8810'),

            # Sequence Gap Data: Cheque Numbers in Description (102450, 102451, 102454)
            (self.eng_id, '2024-09-01', 'Bank Account', 'Vendor Alpha', 0.0, 25000.0, 25000.0, 'V-BK-1', 'INV-1', 'Payment via Cheque 102450', 'CHQ-102450'),
            (self.eng_id, '2024-09-02', 'Bank Account', 'Vendor Beta', 0.0, 30000.0, 30000.0, 'V-BK-2', 'INV-2', 'Payment issued Chq 102451', 'CHQ-102451'),
            (self.eng_id, '2024-09-06', 'Bank Account', 'Vendor Gamma', 0.0, 40000.0, 40000.0, 'V-BK-4', 'INV-4', 'Payment via Cheque 102454', 'CHQ-102454')
        ]

        cur.executemany("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, invoice_no, description, reference_no)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, test_txs)

        conn.commit()
        conn.close()

    def test_01_helper_functions_similarity_and_extraction(self):
        """Test string similarity, code similarity, and sequence extraction helpers."""
        # String similarity
        self.assertGreater(string_similarity("M/s Reliance Digital Retail Ltd", "Reliance Digital Retail Limited"), 0.90)
        self.assertGreater(string_similarity("Infosys Technologies Pvt Ltd", "Infosys Technologies Limited"), 0.90)

        # Code similarity
        self.assertEqual(code_similarity("INV-2024-001", "INV/2024/001"), 1.0)
        self.assertEqual(code_similarity("VOUCH-01", "VOUCH01"), 1.0)

        # Sequence parts extraction
        parts = extract_sequence_parts("INV-2024-0042A")
        self.assertIsNotNone(parts)
        self.assertEqual(parts[0], "INV-2024-")
        self.assertEqual(parts[1], 42)
        self.assertEqual(parts[2], "A")
        self.assertEqual(parts[3], 4)

        # Cheque number extraction
        chqs = extract_cheque_numbers("Payment made via Cheque 102450 and NEFT")
        self.assertIn(102450, chqs)

    def test_02_exact_and_rule_duplicate_detection(self):
        """Test exact duplicates, same invoice numbers, same date+amount+party, and same reference numbers."""
        result = detect_duplicates_and_gaps(self.eng_id)
        dup_groups = result["duplicate_groups"]

        self.assertGreater(len(dup_groups), 0)

        # Group Types Present
        group_types = [g["group_type"] for g in dup_groups]
        self.assertIn("Exact Duplicate", group_types)
        self.assertIn("Same Invoice Number", group_types)
        self.assertIn("Same Date + Amount + Party", group_types)
        self.assertIn("Same Reference Number", group_types)

        # Check Exact Duplicate
        exact_g = next(g for g in dup_groups if g["group_type"] == "Exact Duplicate")
        self.assertEqual(exact_g["similarity_pct"], 100.0)
        self.assertEqual(len(exact_g["transactions"]), 2)
        self.assertEqual(exact_g["transactions"][0]["amount"], 15000.0)
        self.assertEqual(exact_g["transactions"][1]["amount"], 15000.0)

        # Check Same Invoice Number
        inv_g = next(g for g in dup_groups if g["group_type"] == "Same Invoice Number")
        self.assertIn("INV-DELL-9988", inv_g["detection_reason"])

    def test_03_fuzzy_duplicate_detection(self):
        """Test fuzzy duplicate detection for similar party names with same/near amounts."""
        result = detect_duplicates_and_gaps(self.eng_id)
        dup_groups = result["duplicate_groups"]

        # Find fuzzy match group
        fuzzy_g = next((g for g in dup_groups if "Fuzzy" in g["group_type"]), None)
        self.assertIsNotNone(fuzzy_g)
        self.assertGreaterEqual(fuzzy_g["similarity_pct"], 85.0)
        self.assertIn("Reliance Digital", fuzzy_g["detection_reason"])

    def test_04_missing_sequence_gaps_detection(self):
        """Test detecting sequence gaps in Invoice numbers, Voucher numbers, and Cheque numbers."""
        result = detect_duplicates_and_gaps(self.eng_id)
        gaps = result["sequence_gaps"]

        self.assertGreater(len(gaps), 0)

        gap_types = [g["sequence_type"] for g in gaps]
        self.assertIn("INVOICE_GAP", gap_types)
        self.assertIn("VOUCHER_GAP", gap_types)
        self.assertIn("CHEQUE_GAP", gap_types)

        # Check Invoice Gap (INV-2024-001, 002, 005 -> Gap: 003, 004)
        inv_gap = next(g for g in gaps if g["sequence_type"] == "INVOICE_GAP")
        self.assertEqual(inv_gap["missing_count"], 2)
        self.assertEqual(inv_gap["expected_from"], "INV-2024-003")
        self.assertEqual(inv_gap["expected_to"], "INV-2024-004")
        self.assertIn("INV-2024-003", inv_gap["missing_items"])
        self.assertIn("INV-2024-004", inv_gap["missing_items"])

        # Check Cheque Gap (102450, 102451, 102454 -> Gap: 102452, 102453)
        chq_gap = next(g for g in gaps if g["sequence_type"] == "CHEQUE_GAP")
        self.assertEqual(chq_gap["missing_count"], 2)
        self.assertEqual(chq_gap["expected_from"], "102452")
        self.assertEqual(chq_gap["expected_to"], "102453")

        # Verify audit guidance disclaimer is included
        self.assertIn("exceptions", inv_gap["audit_guidance"].lower())

    def test_05_auditor_actions_workflow_api(self):
        """Test confirming a duplicate, marking valid, ignoring, and adding comments."""
        # 1. Fetch groups to get group code
        res_get = self.client.get(f"/api/duplicates-and-gaps/{self.eng_id}", headers=self.headers)
        self.assertEqual(res_get.status_code, 200)
        data = res_get.json()
        self.assertGreater(len(data["duplicate_groups"]), 0)

        group_0 = data["duplicate_groups"][0]
        group_code = group_0["group_code"]

        # 2. Confirm Duplicate with Auditor Comment
        payload = {
            "group_code": group_code,
            "status": "Confirmed Duplicate",
            "auditor_comment": "Verified with vendor ledger: invoice was entered twice due to manual slip on 10th May."
        }

        res_put = self.client.put(
            f"/api/duplicates-and-gaps/{self.eng_id}/duplicate-review",
            json=payload,
            headers=self.headers
        )
        self.assertEqual(res_put.status_code, 200)
        self.assertTrue(res_put.json()["success"])

        # 3. Document Sequence Gap
        gap_payload = {
            "sequence_type": "INVOICE_GAP",
            "series_prefix": "INV-2024-",
            "expected_from": "INV-2024-003",
            "expected_to": "INV-2024-004",
            "status": "Documented / Valid Gap",
            "auditor_comment": "Inspected physical invoice book: INV-003 and INV-004 were cancelled due to printing alignment error; cancellation slips signed by manager."
        }

        res_gap_put = self.client.put(
            f"/api/duplicates-and-gaps/{self.eng_id}/gap-review",
            json=gap_payload,
            headers=self.headers
        )
        self.assertEqual(res_gap_put.status_code, 200)
        self.assertTrue(res_gap_put.json()["success"])

        # 4. Re-fetch and verify persistence
        res_check = self.client.get(f"/api/duplicates-and-gaps/{self.eng_id}", headers=self.headers)
        updated_data = res_check.json()
        
        target_dup = next(g for g in updated_data["duplicate_groups"] if g["group_code"] == group_code)
        self.assertEqual(target_dup["status"], "Confirmed Duplicate")
        self.assertEqual(target_dup["auditor_comment"], payload["auditor_comment"])

        target_gap = next(g for g in updated_data["sequence_gaps"] if g["sequence_type"] == "INVOICE_GAP")
        self.assertEqual(target_gap["status"], "Documented / Valid Gap")
        self.assertEqual(target_gap["auditor_comment"], gap_payload["auditor_comment"])

    def test_06_download_csv_report_endpoint(self):
        """Test downloading Duplicate & Sequence Gaps CSV report."""
        res = self.client.get(
            f"/api/duplicates-and-gaps/{self.eng_id}/report/download",
            headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.headers.get("content-type", ""))
        self.assertIn("Duplicate_and_Sequence_Gaps", res.headers.get("content-disposition", ""))
        
        content = res.text
        self.assertIn("FinAuditPro - Duplicate and Sequence Gap Audit Report", content)
        self.assertIn("SECTION 1: DUPLICATE GROUPS WORKBENCH", content)
        self.assertIn("SECTION 2: MISSING SEQUENCE GAPS", content)
        self.assertIn("INVOICE_GAP", content)

if __name__ == "__main__":
    unittest.main()
