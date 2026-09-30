import unittest
import json
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.services.bank_reconciliation_engine import run_bank_reconciliation

class TestBankReconciliationModule(unittest.TestCase):
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

    def test_01_exact_and_high_confidence_brs_matching(self):
        """Test exact match (100%), high confidence match, unpresented cheques, and bank charges."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, gstin, created_at)
        VALUES ('BRS Test Client 1', 'Private Limited Company', 'BRSPAN1234F', '27BRSPAN1234F1Z5', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
        VALUES (?, 'BRS Audit 2024-25', 'Statutory Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        # Insert Cash Book / Bank Ledger transactions:
        # 1. Payment with exact cheque #102450 (Rs 50,000)
        # 2. High confidence payment (Rs 24,500)
        # 3. Unpresented cheque (Rs 80,000)
        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description, transaction_type)
        VALUES 
        (?, '2024-05-10', 'HDFC Bank Account', 'Tech Supplies Ltd', 0.0, 50000.0, 50000.0, 'V-CHQ-1', 'Payment via Cheque 102450', 'BOOK'),
        (?, '2024-05-15', 'HDFC Bank Account', 'Reliance Digital', 0.0, 24500.0, 24500.0, 'V-NEFT-2', 'Office equipment purchase', 'BOOK'),
        (?, '2024-05-28', 'HDFC Bank Account', 'Vendor Unpresented', 0.0, 80000.0, 80000.0, 'V-CHQ-3', 'Cheque issued unpresented', 'BOOK'),
        (?, '2024-05-11', 'HDFC Bank Account', 'Tech Supplies Ltd', 50000.0, 0.0, 50000.0, 'CHQ 102450', 'CHQ 102450 Tech Supplies Ltd', 'BANK_STATEMENT'),
        (?, '2024-05-16', 'HDFC Bank Account', 'Reliance Digital', 24500.0, 0.0, 24500.0, 'NEFT-REL-99', 'NEFT Reliance Digital', 'BANK_STATEMENT')
        """, (eng_id, eng_id, eng_id, eng_id, eng_id))
        conn.commit()
        conn.close()

        # Run Bank Reconciliation Engine
        result = run_bank_reconciliation(
            engagement_id=eng_id,
            bank_ledger_name="HDFC Bank Account",
            title="HDFC Bank BRS FY 2024-25"
        )

        summary = result["summary"]
        self.assertGreater(summary["total_book_tx"], 0)
        self.assertGreater(summary["matched_count"], 0)
        self.assertGreater(summary["unpresented_cheques_amount"], 0)
        self.assertGreaterEqual(summary["bank_charges_amount"], 0)

        # Verify matching levels exist in items
        items = result["items"]
        match_levels = [i["match_level"] for i in items]
        self.assertIn("EXACT MATCH", match_levels)

        # Check for unpresented cheque detection
        unpresented = [i for i in items if i["item_type"] == "UNPRESENTED_CHEQUE"]
        self.assertTrue(len(unpresented) > 0)
        self.assertEqual(unpresented[0]["amount_a"], 80000.0)

    def test_02_reconciliation_api_endpoints(self):
        """Test API endpoints: list, get details with filters, confirm match, reject match, and manual match."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, created_at)
        VALUES ('BRS API Test Client', 'Private Limited Company', 'BRSAPI1234F', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
        VALUES (?, 'BRS API Engagement', 'Statutory Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description)
        VALUES 
        (?, '2024-04-10', 'SBI Current Account', 'Apex Logistics', 120000.0, 0.0, 120000.0, 'V-REC-1', 'Customer deposit received'),
        (?, '2024-04-15', 'SBI Current Account', 'Office Landlord', 0.0, 35000.0, 35000.0, 'V-RENT-2', 'Rent payment')
        """, (eng_id, eng_id))
        conn.commit()
        conn.close()

        # 1. Test bank ledgers list endpoint
        res = self.client.get(f"/api/reconciliation/bank-ledgers/{eng_id}", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("SBI Current Account", res.json()["bank_ledgers"])

        # 2. Test execute BRS endpoint
        res = self.client.post("/api/reconciliation/execute", headers=self.headers, json={
            "engagement_id": eng_id,
            "bank_ledger_name": "SBI Current Account",
            "title": "SBI Current Account BRS"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        recon_id = data["recon_id"]

        # 3. Test list reconciliations endpoint
        res = self.client.get(f"/api/reconciliation/{eng_id}", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        recons = res.json()
        self.assertTrue(len(recons) > 0)
        self.assertEqual(recons[0]["id"], recon_id)

        # 4. Test get details endpoint
        res = self.client.get(f"/api/reconciliation/details/{recon_id}", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        details = res.json()
        self.assertEqual(details["id"], recon_id)
        self.assertTrue(len(details["items"]) > 0)

        item_id = details["items"][0]["id"]

        # 5. Test confirm match endpoint
        res = self.client.put(f"/api/reconciliation/{recon_id}/items/{item_id}/confirm", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

        # 6. Test reject match endpoint
        res = self.client.put(f"/api/reconciliation/{recon_id}/items/{item_id}/reject", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

    def test_03_manual_matching_workflow(self):
        """Test manually pairing an unmatched book item and an unmatched bank item."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, created_at)
        VALUES ('BRS Manual Match Client', 'Partnership', 'BRSMM1234F', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
        VALUES (?, 'BRS MM Audit', 'Internal Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description)
        VALUES 
        (?, '2024-06-01', 'Axis Bank Account', 'Custom Party A', 50000.0, 0.0, 50000.0, 'V-MAN-1', 'Deposit item in books')
        """, (eng_id,))
        conn.commit()
        conn.close()

        res = self.client.post("/api/reconciliation/execute", headers=self.headers, json={
            "engagement_id": eng_id,
            "bank_ledger_name": "Axis Bank Account",
            "title": "Axis Bank BRS"
        })
        recon_id = res.json()["recon_id"]

        # Insert a deliberate unmatched book item and unmatched bank item
        conn = get_db_connection()
        c1 = conn.execute("""
        INSERT INTO reconciliation_items (recon_id, date_a, ref_a, party_a, amount_a, status, match_level)
        VALUES (?, '2024-06-10', 'VCH-BOOK-99', 'Vendor Special', 75000.0, 'Unmatched', 'UNMATCHED')
        """, (recon_id,))
        book_item_id = c1.lastrowid

        c2 = conn.execute("""
        INSERT INTO reconciliation_items (recon_id, date_b, ref_b, party_b, amount_b, status, match_level)
        VALUES (?, '2024-06-14', 'TXN-BANK-88', 'Vendor Special P Ltd', 75000.0, 'Unmatched', 'UNMATCHED')
        """, (recon_id,))
        bank_item_id = c2.lastrowid
        conn.commit()
        conn.close()

        # Execute manual match via API
        res = self.client.post(f"/api/reconciliation/{recon_id}/manual-match", headers=self.headers, json={
            "book_item_id": book_item_id,
            "bank_item_id": bank_item_id,
            "auditor_notes": "Auditor verified contra voucher reference and 4-day transit delay."
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

        # Verify manual matched record exists in details
        res = self.client.get(f"/api/reconciliation/details/{recon_id}", headers=self.headers)
        details = res.json()
        statuses = [i["status"] for i in details["items"]]
        self.assertIn("Manual Matched", statuses)

    def test_04_download_brs_csv_report(self):
        """Test downloading Bank Reconciliation Statement (BRS) as CSV."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, created_at)
        VALUES ('BRS CSV Client', 'Private Limited Company', 'BRSCSV1234F', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
        VALUES (?, 'BRS CSV Audit', 'Statutory Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description)
        VALUES 
        (?, '2024-05-12', 'Kotak Bank Account', 'Vendor Kotak', 0.0, 95000.0, 95000.0, 'V-KTK-1', 'Payment')
        """, (eng_id,))
        conn.commit()
        conn.close()

        res = self.client.post("/api/reconciliation/execute", headers=self.headers, json={
            "engagement_id": eng_id,
            "bank_ledger_name": "Kotak Bank Account",
            "title": "Kotak Bank BRS Statement"
        })
        recon_id = res.json()["recon_id"]

        # Download report
        res = self.client.get(f"/api/reconciliation/{recon_id}/report/download", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.headers.get("content-type", ""))
        self.assertIn("FinAuditPro - Bank Reconciliation Statement (BRS)", res.text)
        self.assertIn("--- BANK RECONCILIATION SUMMARY COMPUTATION ---", res.text)
        self.assertIn("Kotak Bank Account", res.text)

if __name__ == "__main__":
    unittest.main()
