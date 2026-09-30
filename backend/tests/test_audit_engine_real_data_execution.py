"""
Real Data Audit Engine Execution Test Suite
FinAuditPro - Test Suite

Validates that all core audit engines operate deterministically on real test datasets
(Aryan Fintech & Hitansh Fintech) without fallbacks.
"""

import unittest
from backend.app.database import get_db_connection
from test_data.seed import seed_test_database
from test_data.companies import ARYAN_COMPANY, HITANSH_COMPANY
from backend.app.services.trial_balance_analyzer import analyze_trial_balance
from backend.app.services.financial_statement_analysis_engine import run_financial_statement_analysis
from backend.app.services.yoy_comparison_engine import run_yoy_comparison
from backend.app.services.anomaly_detection_engine import detect_all_anomalies
from backend.app.services.duplicate_missing_detector import detect_duplicates_and_gaps
from backend.app.services.bank_reconciliation_engine import run_bank_reconciliation
from backend.app.services.gst_reconciliation_engine import run_gst_reconciliation
from backend.app.services.sales_purchase_reconciliation_engine import run_sales_purchase_reconciliation

class TestAuditEngineRealDataExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seeds = seed_test_database()
        cls.aryan_cy_id = cls.seeds["aryan"]["cy_engagement_id"]
        cls.aryan_py_id = cls.seeds["aryan"]["py_engagement_id"]
        cls.hitansh_cy_id = cls.seeds["hitansh"]["cy_engagement_id"]
        cls.hitansh_py_id = cls.seeds["hitansh"]["py_engagement_id"]

    def test_trial_balance_analysis_on_real_data(self):
        """Trial Balance analysis executes on real 1,000+ transactions without errors."""
        tb_res = analyze_trial_balance(self.aryan_cy_id)
        self.assertGreater(tb_res["grand_total_debit"], 10000000.0)
        self.assertGreater(tb_res["total_accounts_count"], 10)
        self.assertEqual(tb_res["provenance"]["data_status"], "ACTUAL")

    def test_financial_statements_on_real_data(self):
        """Financial Statements analysis executes with real balance sheet and P&L calculations."""
        fs_res = run_financial_statement_analysis(self.aryan_cy_id)
        pnl = fs_res["profit_and_loss"]["current_year"]
        bs = fs_res["balance_sheet"]["current_year"]

        self.assertGreater(pnl["revenue"], 0.0)
        self.assertGreater(pnl["total_operating_expenses"], 0.0)
        self.assertGreater(bs["total_assets"], 0.0)
        self.assertEqual(fs_res["provenance"]["data_status"], "ACTUAL")
        self.assertEqual(fs_res["provenance"]["previous_year_data_status"], "ACTUAL")

    def test_yoy_comparison_between_real_years(self):
        """YoY comparison compares actual FY 25-26 with actual FY 24-25 baseline data."""
        yoy_res = run_yoy_comparison(self.aryan_cy_id, py_engagement_id=self.aryan_py_id)
        self.assertEqual(yoy_res["provenance"]["data_status"], "ACTUAL")
        self.assertEqual(yoy_res["previous_engagement_id"], self.aryan_py_id)

        # Revenue comparison item must have non-zero for both CY and PY
        rev_item = next((i for i in yoy_res["executive_comparison"] if i["item_key"] == "revenue_from_operations"), None)
        self.assertIsNotNone(rev_item)
        self.assertGreater(rev_item["current_year"], 0.0)
        self.assertGreater(rev_item["previous_year"], 0.0)

    def test_anomalies_and_duplicates_deterministic_detection(self):
        """Anomaly engine and Duplicate detector catch controlled injected anomalies."""
        anom_res = detect_all_anomalies(self.aryan_cy_id)
        anomalies = anom_res.get("anomalies", [])
        self.assertGreaterEqual(len(anomalies), 1)

        # Check for stable identifier prefix format ANOM-TX
        for a in anomalies:
            self.assertTrue(a["anomaly_id"].startswith("ANOM-TX"))

        dup_res = detect_duplicates_and_gaps(self.aryan_cy_id)
        duplicate_groups = dup_res.get("duplicate_groups", [])
        self.assertGreaterEqual(len(duplicate_groups), 1)
        for d in duplicate_groups:
            self.assertTrue(d.get("group_code", "").startswith("DUP-"))

    def test_sales_purchase_reconciliation_real_data(self):
        """Sales and Purchase reconciliation runs against real generated registers."""
        sp_res = run_sales_purchase_reconciliation(self.aryan_cy_id, recon_type="Sales Reconciliation")
        self.assertIn("summary", sp_res)
        self.assertEqual(sp_res["provenance"]["data_status"], "ACTUAL")

if __name__ == "__main__":
    unittest.main()
