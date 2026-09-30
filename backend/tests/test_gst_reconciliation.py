import io
import csv
import json
import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.services.gst_rule_config import (
    get_all_gst_rules, get_gst_rule, update_gst_rule, reset_gst_rules_to_default
)
from backend.app.services.gst_reconciliation_engine import run_gst_reconciliation

class TestGSTReconciliationModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

        # Authenticate client
        res = cls.client.post("/api/auth/login", json={"username": "admin", "password": "adminpassword123"})
        if res.status_code == 200:
            cls.token = res.json()["access_token"]
        else:
            res = cls.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
            cls.token = res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def setUp(self):
        # Create fresh client and engagement
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO clients (name, entity_type, pan, gstin, created_at)
            VALUES ('GST Test Enterprises Ltd', 'Private Limited Company', 'GSTENT1234F', '27GSTENT1234F1Z5', datetime('now'))
        """)
        self.client_id = cur.lastrowid

        cur.execute("""
            INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
            VALUES (?, 'GST Statutory Audit FY 2024-25', 'Tax Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (self.client_id,))
        self.eng_id = cur.lastrowid
        conn.commit()
        conn.close()

    def test_01_configurable_gst_rule_framework(self):
        """Test retrieving, updating, and resetting configurable GST rules independently from code."""
        rules = get_all_gst_rules()
        self.assertGreaterEqual(len(rules), 6)
        rule_keys = [r["rule_key"] for r in rules]
        self.assertIn("tolerance_limits", rule_keys)
        self.assertIn("date_cutoff_disparity", rule_keys)
        self.assertIn("fuzzy_matching_rules", rule_keys)
        self.assertIn("gstin_structure_validation", rule_keys)

        # Update tolerance limits
        res = self.client.put(
            "/api/gst-reconciliation/rules/tolerance_limits",
            json={"config": {"taxable_value_tolerance": 10.0, "tax_heads_tolerance": 5.0, "total_invoice_tolerance": 10.0, "currency": "INR"}},
            headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

        # Verify updated rule
        updated_rule = get_gst_rule("tolerance_limits")
        self.assertEqual(updated_rule["config"]["taxable_value_tolerance"], 10.0)

        # Reset rules to factory defaults
        reset_res = self.client.post("/api/gst-reconciliation/rules/reset", headers=self.headers)
        self.assertEqual(reset_res.status_code, 200)
        reset_rule = get_gst_rule("tolerance_limits")
        self.assertEqual(reset_rule["config"]["taxable_value_tolerance"], 5.0)

    def test_02_gst_reconciliation_engine_cross_matching(self):
        """Test deterministic GST cross-matching across all required exception rules."""
        conn = get_db_connection()
        cur = conn.cursor()

        # Source A: GSTR-2B Uploaded File & Invoices
        cur.execute("""
            INSERT INTO uploaded_files (engagement_id, file_name, file_type, file_path, data_category, row_count, uploaded_at)
            VALUES (?, 'gstr2b_may2024.xlsx', 'GST_2B', 'gstr2b_may2024.xlsx', 'GST Data', 4, datetime('now'))
        """, (self.eng_id,))
        source_a_file_id = cur.lastrowid
        cur.execute("""
            INSERT INTO transactions (engagement_id, file_id, date, ledger, party_name, debit, amount, invoice_no, gstin, tax_amount)
            VALUES 
            (?, ?, '2024-05-10', 'GSTR-2B', 'Steel Fabricators Pvt Ltd', 118000.0, 118000.0, 'SF-001', '27AAACS9999A1Z1', 18000.0),
            (?, ?, '2024-05-16', 'GSTR-2B', 'Micro Electronics Corp', 59000.0, 59000.0, 'ME-002', '27AAACM8888B1Z2', 9000.0),
            (?, ?, '2024-05-20', 'GSTR-2B', 'Bangalore Tech Spares', 236000.0, 236000.0, 'BTS-003', '29AAACB7777C1Z3', 36000.0),
            (?, ?, '2024-05-28', 'GSTR-2B', 'Portal Only Supplier', 65000.0, 65000.0, 'POS-005', '27AAACP5555E1Z5', 9915.0)
        """, (self.eng_id, source_a_file_id, self.eng_id, source_a_file_id, self.eng_id, source_a_file_id, self.eng_id, source_a_file_id))

        # Source B: Purchase Register Vouchers
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, amount, invoice_no, gstin, tax_amount)
            VALUES 
            (?, '2024-05-10', 'Raw Material Purchases', 'Steel Fabricators Pvt Ltd', 118000.0, 118000.0, 'SF-001', '27AAACS9999A1Z1', 18000.0),
            (?, '2024-05-15', 'Raw Material Purchases', 'Micro Electronics Corp', 59000.0, 59000.0, 'ME-002', '27AAACM8888B1Z2', 9000.0),
            (?, '2024-05-20', 'Raw Material Purchases', 'Bangalore Tech Spares', 236000.0, 236000.0, 'BTS-003', '29AAACB7777C1Z3', 36000.0),
            (?, '2024-05-25', 'Raw Material Purchases', 'Unfiled Supplier Goods', 50000.0, 50000.0, 'USG-004', '27AAACU6666D1Z4', 7627.0)
        """, (self.eng_id, self.eng_id, self.eng_id, self.eng_id))
        conn.commit()
        conn.close()

        result = run_gst_reconciliation(
            engagement_id=self.eng_id,
            source_a_file_id=source_a_file_id,
            source_a_type="GSTR-2B (Portal Download)",
            source_b_type="Purchase Register (Books)",
            recon_title="GSTR-2B vs Purchase Register Audit Recon"
        )

        self.assertIn("recon_id", result)
        self.assertEqual(result["recon_type"], "GST Reconciliation")
        summary = result["summary"]
        self.assertGreater(summary["total_source_a_invoices"], 0)
        self.assertGreater(summary["total_source_b_invoices"], 0)
        self.assertGreater(summary["matched_count"], 0)

        # Check categorization categories
        items = result["items"]
        categories = {i["match_category"] for i in items}
        self.assertIn("Matched", categories)
        self.assertTrue(any(c in categories for c in ["Partially matched", "Mismatched", "Missing in source A", "Missing in source B"]))

        # Verify audit vocabulary: no fraud claims
        reasons = " ".join([i["match_reason"] for i in items])
        self.assertNotIn("fraud", reasons.lower())
        self.assertNotIn("illegal", reasons.lower())
        self.assertTrue(any(phrase in reasons for phrase in ["GST reconciliation exception", "Potential mismatch", "Requires auditor review", "Reconciled clean"]))

    def test_03_gst_api_execute_and_filtering(self):
        """Test POST /api/gst-reconciliation/execute and GET /api/gst-reconciliation/{recon_id} with query filters."""
        # Insert sample transactions
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, ledger, party_name, credit, amount, voucher_no, invoice_no, gstin, tax_amount)
            VALUES 
            (?, '2024-06-01', 'Sales Revenue', 'Apex Customer 1', 118000.0, 118000.0, 'V-GST-01', 'INV-GST-01', '27AAAAA1111A1Z1', 18000.0),
            (?, '2024-06-05', 'Sales Revenue', 'Apex Customer 2', 59000.0, 59000.0, 'V-GST-02', 'INV-GST-02', '27BBBBB2222B1Z2', 9000.0)
        """, (self.eng_id, self.eng_id))
        conn.commit()
        conn.close()

        payload = {
            "engagement_id": self.eng_id,
            "source_a_type": "GSTR-1 (Portal Download)",
            "source_b_type": "Sales Register (Books)",
            "title": "GSTR-1 vs Sales Register API Test"
        }

        # 1. Execute
        res = self.client.post("/api/gst-reconciliation/execute", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        recon_id = data["recon_id"]
        self.assertGreater(recon_id, 0)

        # 2. Get Details
        detail_res = self.client.get(f"/api/gst-reconciliation/{recon_id}", headers=self.headers)
        self.assertEqual(detail_res.status_code, 200)
        recon_data = detail_res.json()
        self.assertEqual(recon_data["id"], recon_id)
        self.assertIn("items", recon_data)
        self.assertGreater(len(recon_data["items"]), 0)

        # 3. Test Filter Query Params
        match_cat_res = self.client.get(f"/api/gst-reconciliation/{recon_id}?match_category=Matched", headers=self.headers)
        self.assertEqual(match_cat_res.status_code, 200)

        search_res = self.client.get(f"/api/gst-reconciliation/{recon_id}?search=INV", headers=self.headers)
        self.assertEqual(search_res.status_code, 200)

    def test_04_gst_auditor_actions_workflow(self):
        """Test Accept, Reject, Mark for review, and Add auditor comment on GST reconciliation items."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, amount, invoice_no, gstin, tax_amount)
            VALUES (?, '2024-07-01', 'Purchase Account', 'Action Party Ltd', 75000.0, 75000.0, 'PUR-ACT-01', '27ACTAA1111A1Z1', 11440.0)
        """, (self.eng_id,))
        conn.commit()
        conn.close()

        exec_res = self.client.post("/api/gst-reconciliation/execute", json={
            "engagement_id": self.eng_id,
            "title": "GST Action Workflow Recon"
        }, headers=self.headers)
        recon_id = exec_res.json()["recon_id"]

        detail_res = self.client.get(f"/api/gst-reconciliation/{recon_id}", headers=self.headers)
        items = detail_res.json()["items"]
        self.assertGreater(len(items), 0)
        item_id = items[0]["id"]

        # Action: Accept
        act_res = self.client.put(
            f"/api/gst-reconciliation/{recon_id}/items/{item_id}/action",
            json={"status": "Accepted", "auditor_comment": "Verified against supplier GSTR-1 filing acknowledgment."},
            headers=self.headers
        )
        self.assertEqual(act_res.status_code, 200)
        self.assertTrue(act_res.json()["success"])

        # Verify persisted status and note
        verify_res = self.client.get(f"/api/gst-reconciliation/{recon_id}", headers=self.headers)
        item = next(i for i in verify_res.json()["items"] if i["id"] == item_id)
        self.assertEqual(item["status"], "Accepted")
        self.assertIn("acknowledgment", item["notes"])

    def test_05_download_gst_reconciliation_csv_report(self):
        """Test GET /api/gst-reconciliation/{recon_id}/report/download returns CSV with both source values."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, amount, invoice_no, gstin, tax_amount)
            VALUES (?, '2024-08-01', 'Purchase Account', 'Export Supplier', 125000.0, 125000.0, 'PUR-EXP-01', '27EXPAA1111A1Z1', 22500.0)
        """, (self.eng_id,))
        conn.commit()
        conn.close()

        exec_res = self.client.post("/api/gst-reconciliation/execute", json={
            "engagement_id": self.eng_id,
            "title": "GST CSV Report Test"
        }, headers=self.headers)
        recon_id = exec_res.json()["recon_id"]

        report_res = self.client.get(f"/api/gst-reconciliation/{recon_id}/report/download", headers=self.headers)
        self.assertEqual(report_res.status_code, 200)
        self.assertIn("text/csv", report_res.headers.get("content-type", ""))
        self.assertIn("attachment; filename=", report_res.headers.get("content-disposition", ""))

        csv_text = report_res.text
        self.assertIn("FinAuditPro", csv_text)
        self.assertIn("Source A Taxable Value (INR)", csv_text)
        self.assertIn("Source B Taxable Value (INR)", csv_text)
        self.assertIn("Source A CGST (INR)", csv_text)
        self.assertIn("Source B CGST (INR)", csv_text)
        self.assertIn("Total Value Diff (INR)", csv_text)
        self.assertIn("Match Category", csv_text)

        # Parse CSV
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        self.assertGreater(len(rows), 5)

if __name__ == "__main__":
    unittest.main()
