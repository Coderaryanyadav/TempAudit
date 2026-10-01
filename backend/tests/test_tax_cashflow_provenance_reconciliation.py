import unittest
from datetime import datetime
from backend.app.database import init_db, get_db_connection
from backend.app.services.financial_statement_analysis_engine import (
    run_financial_statement_analysis,
    safe_div
)
from backend.app.services.bank_reconciliation_engine import run_bank_reconciliation

class TestTaxCashflowProvenanceReconciliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create client
        cur.execute("""
            INSERT INTO clients (name, entity_type, pan, created_at)
            VALUES ('Tax & Invariant Audit Client Ltd', 'Public Limited Company', 'TXINV9988G', datetime('now'))
        """)
        self.client_id = cur.lastrowid

        # Create CY Engagement
        cur.execute("""
            INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
            VALUES (?, 'Audit FY 2024-25', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
        """, (self.client_id,))
        self.cy_eng_id = cur.lastrowid

        # Create PY Engagement
        cur.execute("""
            INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
            VALUES (?, 'Audit FY 2023-24', 'Statutory Audit', '2023-24', datetime('now'), datetime('now'))
        """, (self.client_id,))
        self.py_eng_id = cur.lastrowid

        conn.commit()
        conn.close()

    def test_01_actual_tax_ledger_derivation_without_25_pct_assumption(self):
        """Verify tax expense is derived strictly from actual transaction vouchers and never assumed at 25%."""
        conn = get_db_connection()
        cur = conn.cursor()

        # Revenue = 10,00,000, Expenses = 4,00,000 -> PBT = 6,00,000
        # Actual Current Tax Provision = 1,82,000 (30.33%), Deferred Tax = 37,000
        # Total Tax = 2,19,000, PAT = 6,00,000 - 2,19,000 = 3,81,000
        txs = [
            (self.cy_eng_id, '2024-05-10', 'Sales Revenue', 'Revenue', 0.0, 1000000.0, 1000000.0, 'V-1'),
            (self.cy_eng_id, '2024-05-15', 'Operating Purchases', 'Expenses', 400000.0, 0.0, 400000.0, 'V-2'),
            (self.cy_eng_id, '2024-06-01', 'Current Tax Expense / Provision for Tax', 'Expenses', 182000.0, 0.0, 182000.0, 'V-TAX-1'),
            (self.cy_eng_id, '2024-06-01', 'Deferred Tax Expense', 'Expenses', 37000.0, 0.0, 37000.0, 'V-TAX-2'),
            (self.cy_eng_id, '2024-04-01', 'HDFC Bank Account', 'Current Assets', 381000.0, 0.0, 381000.0, 'V-BNK'),
            (self.cy_eng_id, '2024-04-01', 'Provision for Income Tax', 'Current Liabilities', 0.0, 219000.0, 219000.0, 'V-TAX-PAY'),
            (self.cy_eng_id, '2024-04-01', 'Equity Share Capital', 'Equity', 0.0, 162000.0, 162000.0, 'V-EQ')
        ]
        cur.executemany("""
            INSERT INTO transactions (engagement_id, date, ledger, account_group, debit, credit, amount, voucher_no)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, txs)
        conn.commit()
        conn.close()

        res = run_financial_statement_analysis(self.cy_eng_id)
        pnl = res["profit_and_loss"]["current_year"]
        
        self.assertEqual(pnl["revenue"], 1000000.0)
        self.assertEqual(pnl["pbt"], 600000.0)
        # Tax should be exactly 1,82,000 + 37,000 = 2,19,000 (NOT 25% of 6,00,000 which is 1,50,000)
        self.assertEqual(pnl["tax_expense"], 219000.0)
        self.assertEqual(pnl["pat"], 381000.0)
        self.assertEqual(pnl["tax_data_status"], "ACTUAL_LEDGER")

    def test_02_undefined_ratios_return_none(self):
        """Verify division by zero returns None (null) and not 0.0 for undefined metrics."""
        self.assertIsNone(safe_div(1000.0, 0.0, None))
        self.assertIsNone(safe_div(0.0, 0.0, None))
        self.assertIsNone(safe_div(None, 100.0, None))
        self.assertEqual(safe_div(100.0, 50.0, None), 2.0)

        conn = get_db_connection()
        cur = conn.cursor()
        # Clean test engagement with Zero Liabilities
        cur.execute("""
            INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
            VALUES (?, 'Audit Zero CL FY 2024-25', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
        """, (self.client_id,))
        zero_cl_eng = cur.lastrowid

        # Only Assets & Revenue (No liabilities)
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, ledger, account_group, debit, credit, amount, voucher_no)
            VALUES 
            (?, '2024-05-10', 'Sales Revenue', 'Revenue', 0.0, 5000000.0, 5000000.0, 'V-1'),
            (?, '2024-04-01', 'Bank Balance', 'Current Assets', 5000000.0, 0.0, 5000000.0, 'V-2')
        """, (zero_cl_eng, zero_cl_eng))
        conn.commit()
        conn.close()

        res = run_financial_statement_analysis(zero_cl_eng)
        ratios = res["ratios"]["current_year"]
        
        # When CL is 0.0, current_ratio and quick_ratio must be None
        self.assertIsNone(ratios["current_ratio"])
        self.assertIsNone(ratios["quick_ratio"])
        # When debtors are 0.0, receivable turnover and DSO must be None
        self.assertIsNone(ratios["receivable_turnover"])
        self.assertIsNone(ratios["dso_days"])

    def test_03_indirect_cash_flow_reconciliation_equation(self):
        """Verify indirect cash flow statement reconciles opening + net_change == closing_cash with invariant checks."""
        conn = get_db_connection()
        cur = conn.cursor()

        # PY Data (Opening Balance): Cash = 1,00,000, PPE = 5,00,000, Share Capital = 6,00,000
        py_txs = [
            (self.py_eng_id, '2023-04-01', 'Cash and Bank', 'Current Assets', 100000.0, 0.0, 100000.0, 'PY-1'),
            (self.py_eng_id, '2023-04-01', 'Plant & Machinery', 'Fixed Assets', 500000.0, 0.0, 500000.0, 'PY-2'),
            (self.py_eng_id, '2023-04-01', 'Share Capital', 'Equity', 0.0, 600000.0, 600000.0, 'PY-3')
        ]
        cur.executemany("""
            INSERT INTO transactions (engagement_id, date, ledger, account_group, debit, credit, amount, voucher_no)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, py_txs)

        # CY Data: Revenue = 10,00,000, Dep = 50,000, Cash = 4,00,000, PPE = 7,00,000, Equity = 11,00,000
        # PBT = 9,50,000 (CFO = 9,50,000 + 50,000 = 10,00,000)
        # Capex = 7,00,000 - 5,00,000 + 50,000 = 2,50,000 (CFI = -2,50,000)
        # Financing: Equity issue = 5,00,000 - 0 = 5,00,000 (CFF = -4,50,000 dividends/changes or +0)
        cy_txs = [
            (self.cy_eng_id, '2024-05-10', 'Sales Revenue', 'Revenue', 0.0, 1000000.0, 1000000.0, 'CY-1'),
            (self.cy_eng_id, '2024-05-15', 'Depreciation Expense', 'Expenses', 50000.0, 0.0, 50000.0, 'CY-2'),
            (self.cy_eng_id, '2024-04-01', 'Cash and Bank', 'Current Assets', 350000.0, 0.0, 350000.0, 'CY-3'),
            (self.cy_eng_id, '2024-04-01', 'Plant & Machinery', 'Fixed Assets', 750000.0, 0.0, 750000.0, 'CY-4'),
            (self.cy_eng_id, '2024-04-01', 'Share Capital', 'Equity', 0.0, 150000.0, 150000.0, 'CY-5')
        ]
        cur.executemany("""
            INSERT INTO transactions (engagement_id, date, ledger, account_group, debit, credit, amount, voucher_no)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, cy_txs)
        conn.commit()
        conn.close()

        res = run_financial_statement_analysis(self.cy_eng_id)
        cf = res["cash_flow_statement"]
        
        self.assertEqual(cf["status"], "COMPUTED")
        self.assertIn("cash_flow_reconciles", cf)
        self.assertIn("reconciliation_difference", cf)
        self.assertEqual(cf["opening_cash_balance"], 100000.0)
        self.assertEqual(cf["closing_cash_balance"], 350000.0)

    def test_04_contra_accounts_and_capital_purchases(self):
        """Verify sales returns reduce revenue, purchase returns reduce cogs, and capital purchases route to PPE."""
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
            VALUES (?, 'Audit Contra FY 2024-25', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
        """, (self.client_id,))
        contra_eng = cur.lastrowid

        txs = [
            (contra_eng, '2024-05-10', 'Domestic Sales', 'Revenue', 0.0, 1000000.0, 1000000.0, 'V-1'),
            (contra_eng, '2024-05-12', 'Sales Return / Return Inward', 'Revenue', 50000.0, 0.0, 50000.0, 'V-2'),
            (contra_eng, '2024-05-15', 'Raw Material Purchases', 'Expenses', 400000.0, 0.0, 400000.0, 'V-3'),
            (contra_eng, '2024-05-18', 'Purchase Return / Return Outward', 'Expenses', 0.0, 30000.0, 30000.0, 'V-4'),
            (contra_eng, '2024-05-20', 'Capital Machinery Purchase', 'Fixed Assets', 250000.0, 0.0, 250000.0, 'V-5'),
        ]
        cur.executemany("""
            INSERT INTO transactions (engagement_id, date, ledger, account_group, debit, credit, amount, voucher_no)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, txs)
        conn.commit()
        conn.close()

        res = run_financial_statement_analysis(contra_eng)
        pnl = res["profit_and_loss"]["current_year"]
        bs = res["balance_sheet"]["current_year"]

        # Net Revenue = 10,00,000 - 50,000 (Sales Return) = 9,50,000
        self.assertEqual(pnl["revenue"], 950000.0)
        # Net COGS = 4,00,000 - 30,000 (Purchase Return) = 3,70,000
        self.assertEqual(pnl["cogs"], 370000.0)
        # Capital Machinery Purchase is PPE (Fixed Assets), NOT an operating expense
        self.assertEqual(bs["fixed_assets_ppe"], 250000.0)

    def test_05_brs_ambiguous_matches_require_review(self):
        """Verify ambiguous duplicate candidates are marked for review and not prematurely excluded from unmatched population."""
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
            VALUES (?, 'Audit BRS Ambiguity FY 2024-25', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
        """, (self.client_id,))
        brs_eng = cur.lastrowid

        # Insert 2 identical book payments to 'Vendor Ambiguous' for ₹50,000 without distinct cheque #
        # And 1 bank debit of ₹50,000
        cur.execute("""
            INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description, transaction_type)
            VALUES 
            (?, '2024-05-10', 'ICICI Bank', 'Vendor Ambiguous', 0.0, 50000.0, 50000.0, 'V-1', 'Payment 1', 'BOOK'),
            (?, '2024-05-10', 'ICICI Bank', 'Vendor Ambiguous', 0.0, 50000.0, 50000.0, 'V-2', 'Payment 2', 'BOOK'),
            (?, '2024-05-10', 'ICICI Bank', 'Vendor Ambiguous', 50000.0, 0.0, 50000.0, 'BK-1', 'Bank Debit', 'BANK_STATEMENT')
        """, (brs_eng, brs_eng, brs_eng))
        conn.commit()
        conn.close()

        res = run_bank_reconciliation(
            engagement_id=brs_eng,
            bank_ledger_name="ICICI Bank",
            title="ICICI Bank Ambiguity Test BRS"
        )
        summary = res["summary"]
        self.assertGreater(summary["ambiguous_candidates_count"], 0)

        # Ambiguous items should have status "Review Required"
        amb_items = [i for i in res["items"] if i.get("item_type") == "AMBIGUOUS_CANDIDATE"]
        self.assertGreater(len(amb_items), 0)
        self.assertEqual(amb_items[0]["status"], "Review Required")

if __name__ == "__main__":
    unittest.main()
