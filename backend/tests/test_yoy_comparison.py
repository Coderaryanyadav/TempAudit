import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.services.yoy_comparison_engine import (
    run_yoy_comparison,
    explain_yoy_movement_factually,
    save_yoy_auditor_comment,
    generate_yoy_csv_report,
    INSUFFICIENT_DATA_MSG
)

class TestYoYFinancialComparisonModule(unittest.TestCase):
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

        # Create Client
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, gstin, created_at, updated_at)
        VALUES ('Zenith Dynamics Industrial Ltd', 'Public Limited Company', 'AAACZ7788D', '27AAACZ7788D1Z8', datetime('now'), datetime('now'))
        """)
        self.client_id = cur.lastrowid

        # Create Previous Year (PY: 2023-24) Engagement
        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
        VALUES (?, 'Statutory Audit FY 2023-24', 'Statutory Audit', '2023-24', datetime('now'), datetime('now'))
        """, (self.client_id,))
        self.py_eng_id = cur.lastrowid

        # Create Current Year (CY: 2024-25) Engagement
        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
        VALUES (?, 'Statutory Audit FY 2024-25', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
        """, (self.client_id,))
        self.cy_eng_id = cur.lastrowid

        # PY Transactions (2023-24)
        py_txs = [
            # Revenue (₹10,00,000)
            (self.py_eng_id, '2023-06-15', 'Sales Revenue', 'Alpha Retailers', 0.0, 600000.0, 600000.0, 'V-PY-01', 'INV-P-01', 'Sales billing', 'REF-P1'),
            (self.py_eng_id, '2023-11-20', 'Sales Revenue', 'Beta Traders', 0.0, 400000.0, 400000.0, 'V-PY-02', 'INV-P-02', 'Sales billing', 'REF-P2'),
            # COGS / Purchases (₹5,00,000)
            (self.py_eng_id, '2023-07-10', 'Raw Material Purchases', 'Global Steel Corp', 500000.0, 0.0, 500000.0, 'V-PY-03', 'INV-P-03', 'Steel procurement', 'REF-P3'),
            # Salaries (₹2,00,000)
            (self.py_eng_id, '2023-08-31', 'Salaries & Wages Expense', 'Staff Payroll', 200000.0, 0.0, 200000.0, 'V-PY-04', 'INV-P-04', 'Staff salaries', 'REF-P4'),
            # Debtors (₹3,00,000)
            (self.py_eng_id, '2023-09-10', 'Trade Receivables (Debtors)', 'Alpha Retailers', 300000.0, 0.0, 300000.0, 'V-PY-05', 'INV-P-05', 'Debtor balance', 'REF-P5'),
            # Cash & Bank (₹2,50,000)
            (self.py_eng_id, '2023-10-05', 'Bank Balance Account', 'HDFC Bank', 200000.0, 0.0, 200000.0, 'V-PY-06', 'INV-P-06', 'Bank deposit', 'REF-P6'),
            (self.py_eng_id, '2023-10-05', 'Cash in Hand', 'Direct Cash', 50000.0, 0.0, 50000.0, 'V-PY-07', 'INV-P-07', 'Cash balance', 'REF-P7')
        ]

        # CY Transactions (2024-25)
        cy_txs = [
            # Revenue (₹16,00,000 - 60% Growth)
            (self.cy_eng_id, '2024-06-15', 'Sales Revenue', 'Alpha Retailers', 0.0, 700000.0, 700000.0, 'V-CY-01', 'INV-C-01', 'Sales billing', 'REF-C1'),
            (self.cy_eng_id, '2024-09-20', 'Sales Revenue', 'Beta Traders', 0.0, 400000.0, 400000.0, 'V-CY-02', 'INV-C-02', 'Sales billing', 'REF-C2'),
            (self.cy_eng_id, '2024-12-10', 'Sales Revenue', 'Gamma Enterprises', 0.0, 500000.0, 500000.0, 'V-CY-03', 'INV-C-03', 'New client contract billing', 'REF-C3'),
            # COGS / Purchases (₹9,50,000 - 90% Growth)
            (self.cy_eng_id, '2024-07-10', 'Raw Material Purchases', 'Global Steel Corp', 650000.0, 0.0, 650000.0, 'V-CY-04', 'INV-C-04', 'Steel procurement', 'REF-C4'),
            (self.cy_eng_id, '2024-11-15', 'Raw Material Purchases', 'Apex Alloys Ltd', 300000.0, 0.0, 300000.0, 'V-CY-05', 'INV-C-05', 'Alloy procurement', 'REF-C5'),
            # Salaries (₹2,50,000 - 25% Growth)
            (self.cy_eng_id, '2024-08-31', 'Salaries & Wages Expense', 'Staff Payroll', 250000.0, 0.0, 250000.0, 'V-CY-06', 'INV-C-06', 'Staff salaries', 'REF-C6'),
            # Debtors (₹4,50,000 - 50% Growth)
            (self.cy_eng_id, '2024-09-10', 'Trade Receivables (Debtors)', 'Alpha Retailers', 450000.0, 0.0, 450000.0, 'V-CY-07', 'INV-C-07', 'Debtor balance', 'REF-C7'),
            # Cash & Bank (₹3,80,000)
            (self.cy_eng_id, '2024-10-05', 'Bank Balance Account', 'HDFC Bank', 300000.0, 0.0, 300000.0, 'V-CY-08', 'INV-C-08', 'Bank deposit', 'REF-C8'),
            (self.cy_eng_id, '2024-10-05', 'Cash in Hand', 'Direct Cash', 80000.0, 0.0, 80000.0, 'V-CY-09', 'INV-C-09', 'Cash balance', 'REF-C9')
        ]

        cur.executemany("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, invoice_no, description, reference_no)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, py_txs + cy_txs)

        conn.commit()
        conn.close()

    def test_01_yoy_comparison_calculation_and_executive_totals(self):
        """Test YoY comparison calculation for Revenue, Expenses, Profit, Assets, Cash, Bank, Receivables."""
        result = run_yoy_comparison(self.cy_eng_id, py_engagement_id=self.py_eng_id, threshold_pct=10.0)
        
        self.assertEqual(result["current_financial_year"], "2024-25")
        self.assertEqual(result["previous_financial_year"], "2023-24")

        exec_items = result["executive_comparison"]
        self.assertGreater(len(exec_items), 0)

        # 1. Revenue check: PY 10,00,000 -> CY 16,00,000 (+60%)
        rev = next(i for i in exec_items if i["item_key"] == "revenue_from_operations")
        self.assertEqual(rev["previous_year"], 1000000.0)
        self.assertEqual(rev["current_year"], 1600000.0)
        self.assertEqual(rev["absolute_difference"], 600000.0)
        self.assertEqual(rev["percentage_difference"], 60.0)
        self.assertEqual(rev["movement_direction"], "Increase")
        self.assertTrue(rev["is_significant"])

        # 2. Material Cost / COGS check: PY 5,00,000 -> CY 9,50,000 (+90%)
        cogs = next(i for i in exec_items if i["item_key"] == "cogs")
        self.assertEqual(cogs["previous_year"], 500000.0)
        self.assertEqual(cogs["current_year"], 950000.0)
        self.assertEqual(cogs["percentage_difference"], 90.0)
        self.assertEqual(cogs["movement_direction"], "Increase")

        # 3. Cash in Hand: PY 50,000 -> CY 80,000 (+60%)
        cash = next(i for i in exec_items if i["item_key"] == "cash_in_hand")
        self.assertEqual(cash["previous_year"], 50000.0)
        self.assertEqual(cash["current_year"], 80000.0)
        self.assertEqual(cash["percentage_difference"], 60.0)

        # 4. Bank Balances: PY 2,00,000 -> CY 3,00,000 (+50%)
        bank = next(i for i in exec_items if i["item_key"] == "bank_balances")
        self.assertEqual(bank["previous_year"], 200000.0)
        self.assertEqual(bank["current_year"], 300000.0)
        self.assertEqual(bank["percentage_difference"], 50.0)

    def test_02_configurable_thresholds(self):
        """Test configuring threshold dynamically (5%, 10%, 15%, 20%)."""
        # At 10% threshold, Salaries (25% increase) is significant
        res_10 = run_yoy_comparison(self.cy_eng_id, py_engagement_id=self.py_eng_id, threshold_pct=10.0, materiality_threshold=20000.0)
        sal_10 = next(i for i in res_10["executive_comparison"] if i["item_key"] == "employee_benefit_expenses")
        self.assertTrue(sal_10["is_significant"])

        # At 30% threshold, Salaries (25% increase) is NOT significant
        res_30 = run_yoy_comparison(self.cy_eng_id, py_engagement_id=self.py_eng_id, threshold_pct=30.0, materiality_threshold=20000.0)
        sal_30 = next(i for i in res_30["executive_comparison"] if i["item_key"] == "employee_benefit_expenses")
        self.assertFalse(sal_30["is_significant"])

        # Verify summary counts vary with threshold
        self.assertGreaterEqual(res_10["summary"]["significant_movements_count"], res_30["summary"]["significant_movements_count"])

    def test_03_major_ledgers_and_party_balances(self):
        """Test Major Ledgers and Party Balances comparison sections."""
        result = run_yoy_comparison(self.cy_eng_id, py_engagement_id=self.py_eng_id, threshold_pct=10.0)

        ledgers = result["major_ledgers_comparison"]
        self.assertGreater(len(ledgers), 0)
        l_names = [l["account_name"] for l in ledgers]
        self.assertIn("Sales Revenue", l_names)
        self.assertIn("Raw Material Purchases", l_names)

        parties = result["party_comparison"]
        self.assertGreater(len(parties), 0)
        p_names = [p["account_name"] for p in parties]
        self.assertIn("Alpha Retailers", p_names)
        self.assertIn("Global Steel Corp", p_names)

    def test_04_operational_transaction_volumes(self):
        """Test operational volume comparison (transaction count, debit volume, credit volume, average size)."""
        result = run_yoy_comparison(self.cy_eng_id, py_engagement_id=self.py_eng_id, threshold_pct=10.0)
        vols = result["volume_comparison"]
        self.assertGreater(len(vols), 0)

        tx_cnt = next(i for i in vols if i["item_key"] == "total_transaction_count")
        self.assertEqual(tx_cnt["previous_year"], 7.0)
        self.assertEqual(tx_cnt["current_year"], 9.0)
        self.assertEqual(tx_cnt["movement_direction"], "Increase")

    def test_05_factual_ai_explanation_and_safeguards(self):
        """Test that AI explains reasons based strictly on available data and returns fallback when insufficient."""
        # 1. Available data explanation for Revenue (substantiated by 'Gamma Enterprises' new client billing)
        exp_res = explain_yoy_movement_factually(self.cy_eng_id, "revenue_from_operations", threshold_pct=10.0)
        self.assertTrue(exp_res["is_sufficient"])
        self.assertIn("Sales Revenue", exp_res["ai_reason"])
        self.assertNotIn("fraud", exp_res["ai_reason"].lower())

        # 2. Available data explanation for Ledger 'Raw Material Purchases' (substantiated by new vendor 'Apex Alloys Ltd')
        l_key = "LEDGER_RAW_MATERIAL_PURCHASES"
        exp_l_res = explain_yoy_movement_factually(self.cy_eng_id, l_key, threshold_pct=10.0)
        self.assertTrue(exp_l_res["is_sufficient"])
        self.assertIn("Apex Alloys", exp_l_res["ai_reason"])

        # 3. Insufficient data test: Dummy/Unrecorded head
        conn = get_db_connection()
        # Insert a ledger without transaction details
        conn.execute("INSERT INTO ledgers (engagement_id, ledger_name, account_group, opening_balance, closing_balance) VALUES (?, 'Unsubstantiated Head', 'Expense', 0, 100000)", (self.cy_eng_id,))
        conn.commit()
        conn.close()

        exp_dummy = explain_yoy_movement_factually(self.cy_eng_id, "LEDGER_UNSUBSTANTIATED_HEAD", threshold_pct=10.0)
        self.assertFalse(exp_dummy["is_sufficient"])
        self.assertEqual(exp_dummy["ai_reason"], INSUFFICIENT_DATA_MSG)

    def test_06_auditor_comment_and_api_workflow(self):
        """Test API endpoints: GET YoY comparison, PUT comment, POST AI explain, and GET CSV download."""
        # 1. Fetch comparison via API
        res_get = self.client.get(
            f"/api/yoy-comparison/{self.cy_eng_id}?py_engagement_id={self.py_eng_id}&threshold_pct=15.0",
            headers=self.headers
        )
        self.assertEqual(res_get.status_code, 200)
        data = res_get.json()
        self.assertEqual(data["configured_threshold_pct"], 15.0)

        # 2. Save Auditor Working Paper Comment
        comment_payload = {
            "item_key": "revenue_from_operations",
            "category": "Executive Total",
            "account_name": "Revenue from Operations",
            "status": "Verified",
            "auditor_comment": "Verified with sales register and GSTR-1: 60% revenue growth is driven by expansion into Western region with Gamma Enterprises contract."
        }
        res_put = self.client.put(
            f"/api/yoy-comparison/{self.cy_eng_id}/comment",
            json=comment_payload,
            headers=self.headers
        )
        self.assertEqual(res_put.status_code, 200)
        self.assertTrue(res_put.json()["success"])

        # 3. Request AI Explanation via API
        res_ai = self.client.post(
            f"/api/yoy-comparison/{self.cy_eng_id}/ai-explain",
            json={"item_key": "revenue_from_operations", "threshold_pct": 15.0},
            headers=self.headers
        )
        self.assertEqual(res_ai.status_code, 200)
        self.assertTrue(res_ai.json()["is_sufficient"])

        # 4. Re-fetch and check comment persistence
        res_check = self.client.get(
            f"/api/yoy-comparison/{self.cy_eng_id}?py_engagement_id={self.py_eng_id}",
            headers=self.headers
        )
        rev_item = next(i for i in res_check.json()["executive_comparison"] if i["item_key"] == "revenue_from_operations")
        self.assertEqual(rev_item["status"], "Verified")
        self.assertEqual(rev_item["auditor_comment"], comment_payload["auditor_comment"])

        # 5. Download CSV Report
        res_csv = self.client.get(
            f"/api/yoy-comparison/{self.cy_eng_id}/report/download?py_engagement_id={self.py_eng_id}&threshold_pct=15.0",
            headers=self.headers
        )
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn("text/csv", res_csv.headers.get("content-type", ""))
        self.assertIn("YoY_Financial_Comparison", res_csv.headers.get("content-disposition", ""))
        self.assertIn("FinAuditPro - Year-on-Year Financial Comparison Audit Report", res_csv.text)
        self.assertIn("Revenue from Operations", res_csv.text)

if __name__ == "__main__":
    unittest.main()
