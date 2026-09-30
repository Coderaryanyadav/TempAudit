"""
Zero Fabrication & Data Provenance Test Suite
FinAuditPro - Test Suite

Asserts that:
1. When financial data is missing, calculations report 0.0, MISSING, NOT_AVAILABLE,
   and NEVER synthesize arbitrary multipliers (* 0.60, * 0.84, * 0.08, etc.).
2. Every major audit engine outputs verifiable data provenance metadata.
"""

import unittest
from datetime import datetime
from backend.app.database import get_db_connection, init_db
from backend.app.services.financial_statement_analysis_engine import run_financial_statement_analysis
from backend.app.services.gst_reconciliation_engine import run_gst_reconciliation
from backend.app.services.bank_reconciliation_engine import run_bank_reconciliation
from backend.app.services.sales_purchase_reconciliation_engine import run_sales_purchase_reconciliation
from backend.app.services.trial_balance_analyzer import analyze_trial_balance
from backend.app.services.yoy_comparison_engine import run_yoy_comparison

class TestZeroFabricationAndProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        conn = get_db_connection()
        now_str = datetime.now().isoformat()

        # Create clean isolated test client & engagement with sparse data
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO clients (name, pan, gstin, entity_type, contact_person, email, phone, address, created_at, updated_at)
            VALUES ('Zero Fab Test Corp', 'AAACZ0000Z', '27AAACZ0000Z1Z5', 'Private Limited Company', 'Tester', 'test@zero.fab', '123', 'Mumbai', ?, ?)
        """, (now_str, now_str))
        cls.client_id = cur.lastrowid

        # Current Year engagement (FY 2025-26) with ONLY Revenue transaction (No COGS, No Cash, No Fixed Assets)
        cur.execute("""
            INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, status, lead_auditor_id, assigned_staff_id, created_at, updated_at)
            VALUES (?, 'Revenue Only Audit', 'Statutory Audit', '2025-26', '2025-04-01', '2026-03-31', 'In Progress', 1, 2, ?, ?)
        """, (cls.client_id, now_str, now_str))
        cls.rev_only_eng_id = cur.lastrowid

        # Insert only a single revenue transaction of ₹10,00,000
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, voucher_no, invoice_no, ledger, account_group, description, debit, credit, amount)
            VALUES (?, '2025-05-10', 'V-REV-1', 'INV-001', 'Sales Revenue', 'Revenue', 'Platform software sales', 0.0, 1000000.0, 1000000.0)
        """, (cls.rev_only_eng_id,))

        # Empty engagement (0 transactions)
        cur.execute("""
            INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, status, lead_auditor_id, assigned_staff_id, created_at, updated_at)
            VALUES (?, 'Empty Audit', 'Statutory Audit', '2025-26', '2025-04-01', '2026-03-31', 'In Progress', 1, 2, ?, ?)
        """, (cls.client_id, now_str, now_str))
        cls.empty_eng_id = cur.lastrowid

        conn.commit()
        conn.close()

    def test_missing_cogs_and_assets_not_fabricated(self):
        """When COGS, Cash, Debtors, Fixed Assets are missing, engine must NOT synthesize them from revenue."""
        fs_res = run_financial_statement_analysis(self.rev_only_eng_id)

        pnl = fs_res["profit_and_loss"]["current_year"]
        bs = fs_res["balance_sheet"]["current_year"]

        # Revenue is ₹10,00,000
        self.assertEqual(pnl["revenue"], 1000000.0)

        # COGS must be 0.0 (NOT 60% of revenue i.e. ₹6,00,000)
        self.assertEqual(pnl["cogs"], 0.0)

        # Employee expenses must be 0.0 (NOT 12% of revenue i.e. ₹1,20,000)
        self.assertEqual(pnl["employee_expenses"], 0.0)

        # Cash & Bank must be 0.0 (NOT 8% of revenue i.e. ₹80,000)
        self.assertEqual(bs["cash_bank"], 0.0)

        # Debtors must be 0.0 (NOT 18% of revenue i.e. ₹1,80,000)
        self.assertEqual(bs["trade_debtors"], 0.0)

        # Fixed assets must be 0.0 (NOT 45% of revenue i.e. ₹4,50,000)
        self.assertEqual(bs["fixed_assets_ppe"], 0.0)

        # Provenance verification
        self.assertIn("provenance", fs_res)
        prov = fs_res["provenance"]
        self.assertEqual(prov["data_status"], "ACTUAL")
        self.assertEqual(prov["previous_year_data_status"], "NOT_AVAILABLE")

    def test_missing_py_data_reports_not_available(self):
        """When previous year engagement does not exist, YoY engine must not fabricate PY with 0.84 multipliers."""
        yoy_res = run_yoy_comparison(self.rev_only_eng_id)

        self.assertIn("provenance", yoy_res)
        self.assertEqual(yoy_res["provenance"]["data_status"], "MISSING_PY")
        self.assertIsNone(yoy_res["previous_engagement_id"])

        # Check that PY figures in executive comparison are strictly 0.0 (not synthetic)
        for item in yoy_res["executive_comparison"]:
            self.assertEqual(item["previous_year"], 0.0)

    def test_empty_engagement_provenance(self):
        """When engagement has 0 transactions, provenance reports MISSING."""
        fs_empty = run_financial_statement_analysis(self.empty_eng_id)
        self.assertEqual(fs_empty["provenance"]["data_status"], "MISSING")
        self.assertEqual(fs_empty["profit_and_loss"]["current_year"]["revenue"], 0.0)

        tb_empty = analyze_trial_balance(self.empty_eng_id)
        self.assertEqual(tb_empty["provenance"]["data_status"], "MISSING")
        self.assertEqual(tb_empty["grand_total_debit"], 0.0)

        brs_empty = run_bank_reconciliation(self.empty_eng_id)
        self.assertEqual(brs_empty["provenance"]["data_status"], "MISSING")
        self.assertEqual(brs_empty["summary"]["total_book_tx"], 0)
        self.assertEqual(brs_empty["summary"]["total_bank_tx"], 0)

        gst_empty = run_gst_reconciliation(self.empty_eng_id)
        self.assertEqual(gst_empty["provenance"]["data_status"], "MISSING")
        self.assertEqual(gst_empty["summary"]["total_source_a_invoices"], 0)

        sp_empty = run_sales_purchase_reconciliation(self.empty_eng_id)
        self.assertEqual(sp_empty["provenance"]["data_status"], "MISSING")
        self.assertEqual(sp_empty["summary"]["total_register_invoices"], 0)

if __name__ == "__main__":
    unittest.main()
