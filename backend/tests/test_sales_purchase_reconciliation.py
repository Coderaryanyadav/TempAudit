import io
import csv
import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.services.sales_purchase_reconciliation_engine import run_sales_purchase_reconciliation

class TestSalesPurchaseReconciliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

        # Authenticate test client
        res = cls.client.post("/api/auth/login", json={"username": "admin", "password": "adminpassword123"})
        if res.status_code == 200:
            cls.token = res.json()["access_token"]
        else:
            res = cls.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
            cls.token = res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def setUp(self):
        # Create a fresh client and engagement for each test
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO clients (name, entity_type, pan, gstin, created_at)
            VALUES ('Recon Test Client Corp', 'Private Limited Company', 'RECON1234F', '27RECON1234F1Z5', datetime('now'))
        """)
        self.client_id = cur.lastrowid

        cur.execute("""
            INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
            VALUES (?, 'Reconciliation Audit 2024-25', 'Statutory Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (self.client_id,))
        self.eng_id = cur.lastrowid
        conn.commit()
        conn.close()

    def test_01_sales_reconciliation_engine_deterministic(self):
        """Test sales reconciliation engine execution with simulated register & standard exceptions."""
        conn = get_db_connection()
        cur = conn.cursor()
        # Insert Sales Register File
        cur.execute("""
            INSERT INTO uploaded_files (engagement_id, file_name, file_type, file_path, data_category, row_count, uploaded_at)
            VALUES (?, 'Sales_Register_Q1.xlsx', 'xlsx', 'Sales_Register_Q1.xlsx', 'Sales Register', 4, datetime('now'))
        """, (self.eng_id,))
        file_id = cur.lastrowid

        # Insert Sales Register transactions (Source A)
        cur.execute("""
            INSERT INTO transactions (engagement_id, file_id, date, ledger, party_name, credit, amount, voucher_no, invoice_no, gstin, tax_amount)
            VALUES 
            (?, ?, '2024-04-10', 'Sales Register', 'Apex Retail Ltd', 50000.0, 50000.0, 'V-SAL-001', 'INV-2024-001', '27AAACA1234A1Z1', 9000.0),
            (?, ?, '2024-04-15', 'Sales Register', 'Zenith Logistics', 125000.0, 125000.0, 'V-SAL-002', 'INV-2024-002', '27BBBCA5678B1Z2', 22500.0),
            (?, ?, '2024-04-20', 'Sales Register', 'Global Traders', 75000.0, 75000.0, 'V-SAL-003', 'INV-2024-003', '27CCCCA9999C1Z3', 13500.0),
            (?, ?, '2024-04-20', 'Sales Register', 'Global Traders', 75000.0, 75000.0, 'V-SAL-003', 'INV-2024-003', '27CCCCA9999C1Z3', 13500.0)
        """, (self.eng_id, file_id, self.eng_id, file_id, self.eng_id, file_id, self.eng_id, file_id))

        # Insert General Ledger transactions (Source B)
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, ledger, party_name, credit, amount, voucher_no, invoice_no, gstin, tax_amount)
            VALUES 
            (?, '2024-04-10', 'Sales Revenue Account', 'Apex Retail Ltd', 50000.0, 50000.0, 'V-SAL-001', 'INV-2024-001', '27AAACA1234A1Z1', 9000.0),
            (?, '2024-04-15', 'Sales Revenue Account', 'Zenith Logistics', 120000.0, 120000.0, 'V-SAL-002', 'INV-2024-002', '27BBBCA5678B1Z2', 21600.0),
            (?, '2024-04-20', 'Domestic Sales', 'Global Traders', 75000.0, 75000.0, 'V-SAL-003', 'INV-2024-003', '27CCCCA9999C1Z3', 13500.0)
        """, (self.eng_id, self.eng_id, self.eng_id))
        conn.commit()
        conn.close()

        result = run_sales_purchase_reconciliation(
            engagement_id=self.eng_id,
            recon_type="Sales Reconciliation",
            register_file_id=file_id,
            title="Sales Register vs Revenue Ledger Recon"
        )

        self.assertIn("recon_id", result)
        self.assertEqual(result["recon_type"], "Sales Reconciliation")
        summary = result["summary"]
        self.assertGreater(summary["total_register_invoices"], 0)
        self.assertGreater(summary["total_ledger_invoices"], 0)
        self.assertGreater(summary["matched_count"], 0)
        self.assertGreater(summary["discrepancy_count"], 0)

        # Check that exceptions cover required categories
        exceptions = result["exceptions"]
        ex_types = {e["exception_type"] for e in exceptions}
        self.assertIn("MATCHED", ex_types)
        self.assertTrue(any(t in ex_types for t in ["AMOUNT_DIFFERENCE", "MISSING_IN_LEDGER", "DUPLICATE_INVOICE", "TAX_DIFFERENCE"]))

    def test_02_purchase_reconciliation_engine_with_uploaded_files(self):
        """Test purchase reconciliation comparing uploaded register file against expense ledger."""
        conn = get_db_connection()
        cur = conn.cursor()

        # Insert Register File
        cur.execute("""
            INSERT INTO uploaded_files (engagement_id, file_name, file_type, file_path, data_category, row_count, uploaded_at)
            VALUES (?, 'Purchase_Register_Q1.xlsx', 'xlsx', 'sample_path.xlsx', 'Purchase Register', 6, datetime('now'))
        """, (self.eng_id,))
        file_id = cur.lastrowid

        # Insert Purchase Register transactions (Source A)
        cur.execute("""
            INSERT INTO transactions (engagement_id, file_id, date, ledger, party_name, debit, amount, invoice_no, gstin, tax_amount)
            VALUES 
            (?, ?, '2024-05-05', 'Raw Material Purchases', 'Steel Suppliers Inc', 200000.0, 200000.0, 'PUR-001', '27AAACS1111A1Z1', 36000.0),
            (?, ?, '2024-05-10', 'Raw Material Purchases', 'Alpha Components', 100000.0, 100000.0, 'PUR-002', '27AAACA2222B1Z2', 18000.0),
            (?, ?, '2024-05-12', 'Raw Material Purchases', 'Alpha Components', 100000.0, 100000.0, 'PUR-002', '27AAACA2222B1Z2', 18000.0), -- Duplicate
            (?, ?, '2024-05-15', 'Raw Material Purchases', 'Beta Logistics', 45000.0, 45000.0, 'PUR-003', '', 8100.0), -- Missing GSTIN
            (?, ?, '2024-05-20', 'Raw Material Purchases', 'Delta Packaging', 80000.0, 80000.0, 'PUR-004', '27AAACD4444D1Z4', 14400.0),
            (?, ?, '2024-05-25', 'Purchase Returns', 'Steel Suppliers Inc', -20000.0, 20000.0, 'DN-001', '27AAACS1111A1Z1', -3600.0) -- Debit Note
        """, (self.eng_id, file_id, self.eng_id, file_id, self.eng_id, file_id, self.eng_id, file_id, self.eng_id, file_id, self.eng_id, file_id))

        # Insert General Ledger transactions (Source B)
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, amount, invoice_no, gstin, tax_amount)
            VALUES 
            (?, '2024-05-05', 'Purchase Expense Account', 'Steel Suppliers Inc', 200000.0, 200000.0, 'PUR-001', '27AAACS1111A1Z1', 36000.0),
            (?, '2024-05-10', 'Purchase Expense Account', 'Alpha Components', 100000.0, 100000.0, 'PUR-002', '27AAACA2222B1Z2', 18000.0),
            (?, '2024-05-15', 'Purchase Expense Account', 'Beta Logistics', 45000.0, 45000.0, 'PUR-003', '', 8100.0),
            (?, '2024-05-20', 'Purchase Expense Account', 'Delta Packaging', 85000.0, 85000.0, 'PUR-004', '27AAACD4444D1Z4', 12000.0) -- Amount & Tax Diff
        """, (self.eng_id, self.eng_id, self.eng_id, self.eng_id))
        conn.commit()
        conn.close()

        result = run_sales_purchase_reconciliation(
            engagement_id=self.eng_id,
            recon_type="Purchase Reconciliation",
            register_file_id=file_id,
            ledger_name="Purchase Expense Account",
            title="Q1 Purchase Register vs Ledger Reconciliation"
        )

        self.assertEqual(result["recon_type"], "Purchase Reconciliation")
        self.assertEqual(result["summary"]["total_register_invoices"], 6)
        self.assertEqual(result["summary"]["total_ledger_invoices"], 4)
        
        exceptions = result["exceptions"]
        ex_types = {e["exception_type"] for e in exceptions}
        self.assertIn("DUPLICATE_INVOICE", ex_types)
        self.assertIn("MISSING_GSTIN", ex_types)
        self.assertTrue(any(t in ex_types for t in ["AMOUNT_DIFFERENCE", "TAX_DIFFERENCE"]))
        self.assertTrue(any(t in ex_types for t in ["DEBIT_NOTE_MISMATCH", "MISSING_IN_LEDGER"]))

    def test_03_api_execute_and_get_details(self):
        """Test POST /api/reconciliation/sales-purchase/execute and GET /api/reconciliation/sales-purchase/{recon_id}."""
        # Insert sample transactions
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, ledger, party_name, credit, amount, voucher_no, invoice_no, gstin, tax_amount)
            VALUES 
            (?, '2024-06-01', 'Sales Account', 'Client Alpha', 150000.0, 150000.0, 'V-101', 'INV-101', '27AAAAA1111A1Z1', 27000.0),
            (?, '2024-06-05', 'Sales Account', 'Client Beta', 80000.0, 80000.0, 'V-102', 'INV-102', '27BBBBB2222B1Z2', 14400.0)
        """, (self.eng_id, self.eng_id))
        conn.commit()
        conn.close()

        payload = {
            "engagement_id": self.eng_id,
            "recon_type": "Sales Reconciliation",
            "title": "API Automated Sales Recon"
        }

        # 1. Execute
        res = self.client.post("/api/reconciliation/sales-purchase/execute", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        recon_id = data["recon_id"]
        self.assertGreater(recon_id, 0)
        self.assertIn("summary", data)

        # 2. Get Details
        detail_res = self.client.get(f"/api/reconciliation/sales-purchase/{recon_id}", headers=self.headers)
        self.assertEqual(detail_res.status_code, 200)
        detail_data = detail_res.json()
        self.assertEqual(detail_data["id"], recon_id)
        self.assertIn("items", detail_data)
        self.assertGreater(len(detail_data["items"]), 0)

        # 3. Test Filters
        filtered_res = self.client.get(f"/api/reconciliation/sales-purchase/{recon_id}?status=Suggested", headers=self.headers)
        self.assertEqual(filtered_res.status_code, 200)

        search_res = self.client.get(f"/api/reconciliation/sales-purchase/{recon_id}?search=INV", headers=self.headers)
        self.assertEqual(search_res.status_code, 200)

    def test_04_auditor_actions_workflow(self):
        """Test Accept, Reject, Mark for review, and Add auditor comment on reconciliation items."""
        # Insert sample transactions and execute
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, ledger, party_name, credit, amount, voucher_no, invoice_no, gstin, tax_amount)
            VALUES (?, '2024-07-01', 'Sales Account', 'Action Test Party', 60000.0, 60000.0, 'V-ACT-1', 'INV-ACT-1', '27ACTAA1111A1Z1', 10800.0)
        """, (self.eng_id,))
        conn.commit()
        conn.close()

        exec_res = self.client.post("/api/reconciliation/sales-purchase/execute", json={
            "engagement_id": self.eng_id,
            "recon_type": "Sales Reconciliation",
            "title": "Action Test Recon"
        }, headers=self.headers)
        recon_id = exec_res.json()["recon_id"]

        detail_res = self.client.get(f"/api/reconciliation/sales-purchase/{recon_id}", headers=self.headers)
        items = detail_res.json()["items"]
        self.assertGreater(len(items), 0)
        first_item_id = items[0]["id"]

        # Action 1: Accept
        act_res = self.client.put(
            f"/api/reconciliation/sales-purchase/{recon_id}/items/{first_item_id}/action",
            json={"status": "Accepted", "auditor_comment": "Verified against e-Way bill #998877; variance accepted."},
            headers=self.headers
        )
        self.assertEqual(act_res.status_code, 200)
        self.assertTrue(act_res.json()["success"])

        # Verify status in database
        check_res = self.client.get(f"/api/reconciliation/sales-purchase/{recon_id}", headers=self.headers)
        updated_item = next(i for i in check_res.json()["items"] if i["id"] == first_item_id)
        self.assertEqual(updated_item["status"], "Accepted")
        self.assertIn("e-Way bill", updated_item["notes"])

        # Action 2: Reject
        act_res2 = self.client.put(
            f"/api/reconciliation/sales-purchase/{recon_id}/items/{first_item_id}/action",
            json={"status": "Rejected", "auditor_comment": "False positive entry confirmed."},
            headers=self.headers
        )
        self.assertEqual(act_res2.status_code, 200)

        # Action 3: Mark for review
        act_res3 = self.client.put(
            f"/api/reconciliation/sales-purchase/{recon_id}/items/{first_item_id}/action",
            json={"status": "Marked for review", "auditor_comment": "Pending clarification from client CFO."},
            headers=self.headers
        )
        self.assertEqual(act_res3.status_code, 200)

    def test_05_download_reconciliation_csv_report(self):
        """Test GET /api/reconciliation/sales-purchase/{recon_id}/report/download returns formatted CSV."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, amount, invoice_no, gstin, tax_amount)
            VALUES (?, '2024-08-01', 'Purchase Account', 'Export Test Supplier', 95000.0, 95000.0, 'PUR-EXP-1', '27EXPSS1111A1Z1', 17100.0)
        """, (self.eng_id,))
        conn.commit()
        conn.close()

        exec_res = self.client.post("/api/reconciliation/sales-purchase/execute", json={
            "engagement_id": self.eng_id,
            "recon_type": "Purchase Reconciliation",
            "title": "CSV Report Export Test"
        }, headers=self.headers)
        recon_id = exec_res.json()["recon_id"]

        report_res = self.client.get(f"/api/reconciliation/sales-purchase/{recon_id}/report/download", headers=self.headers)
        self.assertEqual(report_res.status_code, 200)
        self.assertIn("text/csv", report_res.headers.get("content-type", ""))
        self.assertIn("attachment; filename=", report_res.headers.get("content-disposition", ""))

        csv_content = report_res.text
        self.assertIn("FinAuditPro", csv_content)
        self.assertIn("Invoice Number", csv_content)
        self.assertIn("Register Amount (INR)", csv_content)
        self.assertIn("Ledger Amount (INR)", csv_content)
        self.assertIn("Difference (INR)", csv_content)
        self.assertIn("Tax Difference (INR)", csv_content)

        # Parse CSV to verify valid structure
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        self.assertGreater(len(rows), 5)

if __name__ == "__main__":
    unittest.main()
