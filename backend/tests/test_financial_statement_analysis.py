import os
import unittest
import json
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.services.financial_statement_analysis_engine import (
    run_financial_statement_analysis,
    calculate_change,
    get_possible_explanations,
    safe_div
)

class TestFinancialStatementAnalysisModule(unittest.TestCase):
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
        
        # Create test client
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, gstin, created_at)
        VALUES ('Apex Financials Corp Pvt Ltd', 'Private Limited Company', 'AAPCA9988F', '27AAPCA9988F1Z2', datetime('now'))
        """)
        self.client_id = cur.lastrowid

        # Create CY Engagement
        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
        VALUES (?, 'Statutory Audit FY 2024-25', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
        """, (self.client_id,))
        self.cy_eng_id = cur.lastrowid

        # Insert detailed CY Ledgers
        # Total Revenue: 1,00,00,000
        # COGS / Purchases: 60,00,000 -> GP: 40,00,000 (40%)
        # Salaries: 15,00,000
        # Depreciation: 3,00,000
        # Interest / Finance: 2,00,000
        # Other Expenses: 5,00,000
        # EBITDA: 20,00,000, EBIT: 17,00,000, EBT: 15,00,000, Tax: 3,75,000, PAT: 11,25,000 (11.25%)
        # Assets: PPE = 25,00,000, Inventory = 12,00,000, Debtors = 20,00,000, Cash = 8,00,000. Total Assets = 65,00,000
        # Liabilities: Equity = 30,00,000, Long Debt = 15,00,000, Creditors = 14,00,000, Short Borrowing = 6,00,000. Total = 65,00,000
        # Current Assets = 40,00,000. Current Liab = 20,00,000. CR = 2.0x, Quick = 1.40x
        txs = [
            # Revenue & P&L
            (self.cy_eng_id, '2024-05-10', 'Sales Revenue - Domestic', 'Revenue', 0.0, 10000000.0, 10000000.0, 'V-REV'),
            (self.cy_eng_id, '2024-05-15', 'Raw Material Purchases / COGS', 'Cost of Goods Sold', 6000000.0, 0.0, 6000000.0, 'V-PUR'),
            (self.cy_eng_id, '2024-06-01', 'Salaries and Wages', 'Expenses', 1500000.0, 0.0, 1500000.0, 'V-SAL'),
            (self.cy_eng_id, '2024-06-01', 'Depreciation Expense', 'Expenses', 300000.0, 0.0, 300000.0, 'V-DEP'),
            (self.cy_eng_id, '2024-06-01', 'Bank Interest and Finance Charges', 'Expenses', 200000.0, 0.0, 200000.0, 'V-INT'),
            (self.cy_eng_id, '2024-06-01', 'Administrative & Selling Expenses', 'Expenses', 500000.0, 0.0, 500000.0, 'V-ADM'),
            
            # Balance Sheet Assets
            (self.cy_eng_id, '2024-04-01', 'Plant and Machinery & PPE', 'Fixed Assets', 2500000.0, 0.0, 2500000.0, 'V-PPE'),
            (self.cy_eng_id, '2024-04-01', 'Closing Stock / Inventories', 'Current Assets', 1200000.0, 0.0, 1200000.0, 'V-INV'),
            (self.cy_eng_id, '2024-04-01', 'Sundry Debtors / Trade Receivables', 'Current Assets', 2000000.0, 0.0, 2000000.0, 'V-REC'),
            (self.cy_eng_id, '2024-04-01', 'HDFC Current Bank Account', 'Current Assets', 800000.0, 0.0, 800000.0, 'V-BNK'),

            # Balance Sheet Liabilities & Equity
            (self.cy_eng_id, '2024-04-01', 'Equity Share Capital & Reserves', 'Equity', 0.0, 3000000.0, 3000000.0, 'V-EQ'),
            (self.cy_eng_id, '2024-04-01', 'Term Loan from Bank', 'Non-Current Liabilities', 0.0, 1500000.0, 1500000.0, 'V-TL'),
            (self.cy_eng_id, '2024-04-01', 'Sundry Creditors / Trade Payables', 'Current Liabilities', 0.0, 1400000.0, 1400000.0, 'V-CR'),
            (self.cy_eng_id, '2024-04-01', 'Bank Cash Credit (OD/CC)', 'Current Liabilities', 0.0, 600000.0, 600000.0, 'V-OD')
        ]

        cur.executemany("""
        INSERT INTO transactions (engagement_id, date, ledger, account_group, debit, credit, amount, voucher_no)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, txs)

        conn.commit()
        conn.close()

    def test_01_deterministic_ratio_calculations(self):
        """Test exact calculation of liquidity, solvency, profitability, and activity ratios (zero-assumptions)."""
        analysis = run_financial_statement_analysis(self.cy_eng_id)
        cy_ratios = analysis["ratios"]["current_year"]
        
        # 1. Current Ratio: CA (40L) / CL (20L) = 2.0
        self.assertAlmostEqual(cy_ratios["current_ratio"], 2.0, places=2)

        # 2. Quick Ratio: (CA - Inv 12L) / CL (20L) = 28L / 20L = 1.40
        self.assertAlmostEqual(cy_ratios["quick_ratio"], 1.40, places=2)

        # 3. Debt-Equity Ratio: Total Debt (15L + 6L = 21L) / Total Equity (30L + 15L PAT = 45L) = 0.47
        self.assertAlmostEqual(cy_ratios["debt_equity_ratio"], 0.47, places=2)

        # 4. Gross Profit Margin: GP (40L) / Rev (100L) = 40.0%
        self.assertAlmostEqual(cy_ratios["gross_profit_margin_pct"], 40.0, places=2)

        # 5. Operating Margin: EBIT (17L) / Rev (100L) = 17.0%
        self.assertAlmostEqual(cy_ratios["operating_margin_pct"], 17.0, places=2)

        # 6. Net Profit Margin: PAT (15.0L) / Rev (100L) = 15.0% (No artificial 25% tax assumption)
        self.assertAlmostEqual(cy_ratios["net_profit_margin_pct"], 15.0, places=2)

        # 7. Turnover Ratios
        # Receivable Turnover = Rev (100L) / Debtors (20L) = 5.0x (DSO = 365 / 5 = 73 days)
        self.assertAlmostEqual(cy_ratios["receivable_turnover"], 5.0, places=2)
        self.assertAlmostEqual(cy_ratios["dso_days"], 73.0, places=1)

        # Inventory Turnover = COGS (60L) / Inv (12L) = 5.0x (DSI = 365 / 5 = 73 days)
        self.assertAlmostEqual(cy_ratios["inventory_turnover"], 5.0, places=2)
        self.assertAlmostEqual(cy_ratios["dsi_days"], 73.0, places=1)

        # Payable Turnover = COGS (60L) / Creditors (14L) = 4.29x
        self.assertAlmostEqual(cy_ratios["payable_turnover"], 4.29, places=2)

    def test_02_schedule_iii_balance_sheet_and_pnl_structure(self):
        """Test Schedule III classification for Balance Sheet, P&L, and Cash Flow Statement."""
        analysis = run_financial_statement_analysis(self.cy_eng_id)
        
        # P&L checks
        pnl = analysis["profit_and_loss"]["current_year"]
        self.assertEqual(pnl["revenue"], 10000000.0)
        self.assertEqual(pnl["cogs"], 6000000.0)
        self.assertEqual(pnl["gross_profit"], 4000000.0)
        self.assertEqual(pnl["employee_expenses"], 1500000.0)
        self.assertEqual(pnl["depreciation"], 300000.0)
        self.assertEqual(pnl["finance_costs"], 200000.0)
        self.assertEqual(pnl["ebitda"], 2000000.0)
        self.assertEqual(pnl["ebit"], 1700000.0)
        self.assertEqual(pnl["pbt"], 1500000.0)
        self.assertEqual(pnl["tax_expense"], 0.0)  # No fake 25% tax
        self.assertEqual(pnl["pat"], 1500000.0)

        # Balance Sheet checks
        bs = analysis["balance_sheet"]["current_year"]
        self.assertEqual(bs["total_assets"], 6500000.0)
        self.assertEqual(bs["total_current_assets"], 4000000.0)
        self.assertEqual(bs["total_current_liabilities"], 2000000.0)
        self.assertIn("balance_sheet_status", bs)

        # Cash Flow Statement checks (Standalone CY returns status and closing cash)
        cf = analysis["cash_flow_statement"]
        self.assertEqual(cf["status"], "INSUFFICIENT_PRIOR_YEAR_DATA")
        self.assertEqual(cf["closing_cash_balance"], 800000.0)

    def test_03_comparative_multi_year_and_significant_movement(self):
        """Test CY vs PY variance detection with audit-compliant terminology (no fraud labels)."""
        analysis = run_financial_statement_analysis(self.cy_eng_id)
        comparisons = analysis["comparisons"]

        self.assertGreater(len(comparisons), 0)
        
        # Check audit verdicts format: strictly "Significant movement", "Unusual change", "Requires auditor review", "Normal variance", "No prior year data", or "No prior baseline"
        allowed_verdicts = {"Significant movement", "Unusual change", "Requires auditor review", "Normal variance", "Stable trend", "No prior year data", "No prior baseline"}
        for comp in comparisons:
            self.assertIn(comp["audit_verdict"], allowed_verdicts)
            self.assertNotIn("fraud", comp["audit_verdict"].lower())
            self.assertIn("current_year_value", comp)
            self.assertIn("previous_year_value", comp)
            self.assertIn("absolute_difference", comp)
            self.assertIn("percentage_difference", comp)
            self.assertIsInstance(comp["possible_explanation_categories"], list)

    def test_04_save_and_retrieve_auditor_explanation(self):
        """Test persisting auditor explanation and working paper notes."""
        payload = {
            "item_key": "revenue",
            "explanation_category": "Expansion into new market territories / distributor addition",
            "auditor_explanation": "Verified management representation and 15 sample sales contracts with new South India distributors.",
            "review_status": "Reviewed & Documented"
        }

        res = self.client.put(
            f"/api/financial-statements/{self.cy_eng_id}/explanation",
            json=payload,
            headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        resp_json = res.json()
        self.assertTrue(resp_json["success"])

        # Re-fetch financial statement analysis and confirm explanation is populated
        res_get = self.client.get(f"/api/financial-statements/{self.cy_eng_id}", headers=self.headers)
        self.assertEqual(res_get.status_code, 200)
        data = res_get.json()
        
        rev_item = next(c for c in data["comparisons"] if c["item_key"] == "revenue")
        self.assertEqual(rev_item["auditor_explanation"], payload["auditor_explanation"])
        self.assertEqual(rev_item["selected_category"], payload["explanation_category"])
        self.assertEqual(rev_item["review_status"], payload["review_status"])

    def test_05_download_financial_statements_csv_report(self):
        """Test downloading comparative financial statements and ratios CSV report."""
        res = self.client.get(
            f"/api/financial-statements/{self.cy_eng_id}/report/download",
            headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.headers.get("content-type", ""))
        self.assertIn("Financial_Statement_Analysis", res.headers.get("content-disposition", ""))
        
        content = res.text
        self.assertIn("FinAuditPro - Financial Statement", content)
        self.assertIn("Current Ratio", content)
        self.assertIn("Revenue from Operations", content)
        self.assertIn("Net Profit Margin", content)

    def test_06_actual_multi_year_engagements_comparison(self):
        """Test comparison when client has two explicit distinct engagements (FY 23-24 and FY 24-25)."""
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create PY engagement
        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
        VALUES (?, 'Statutory Audit FY 2023-24', 'Statutory Audit', '2023-24', datetime('now'), datetime('now'))
        """, (self.client_id,))
        py_eng_id = cur.lastrowid

        # Insert PY Transactions: Revenue = 80,00,000, COGS = 50,00,000
        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, account_group, debit, credit, amount, voucher_no)
        VALUES 
        (?, '2023-05-10', 'Sales Revenue', 'Revenue', 0.0, 8000000.0, 8000000.0, 'V-PY-REV'),
        (?, '2023-05-15', 'Raw Material Purchases', 'Cost of Goods Sold', 5000000.0, 0.0, 5000000.0, 'V-PY-PUR')
        """, (py_eng_id, py_eng_id))
        conn.commit()
        conn.close()

        # Run analysis for CY engagement
        analysis = run_financial_statement_analysis(self.cy_eng_id)
        self.assertEqual(analysis["financial_year_current"], "2024-25")
        self.assertEqual(analysis["financial_year_previous"], "2023-24")

        # Revenue should compare CY (100L) vs PY (80L) -> +25%
        rev_item = next(c for c in analysis["comparisons"] if c["item_key"] == "revenue")
        self.assertEqual(rev_item["current_year_value"], 10000000.0)
        self.assertEqual(rev_item["previous_year_value"], 8000000.0)
        self.assertEqual(rev_item["absolute_difference"], 2000000.0)
        self.assertEqual(rev_item["percentage_difference"], 25.0)
        self.assertTrue(rev_item["is_significant"])

if __name__ == "__main__":
    unittest.main()
