import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.services.local_ai_assistant_engine import (
    LocalAIAssistantEngine,
    detect_intent,
    MANDATORY_DISCLAIMER
)

class TestLocalAIAuditAssistant(unittest.TestCase):
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
        VALUES ('Apex Meridian Global Enterprises Ltd', 'Public Limited Company', 'AAACA1234D', '27AAACA1234D1Z5', datetime('now'), datetime('now'))
        """)
        self.client_id = cur.lastrowid

        # Create Previous Year Engagement (2023-24)
        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
        VALUES (?, 'Statutory Audit FY 2023-24', 'Statutory Audit', '2023-24', datetime('now'), datetime('now'))
        """, (self.client_id,))
        self.py_eng_id = cur.lastrowid

        # Create Current Year Engagement (2024-25)
        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
        VALUES (?, 'Statutory Audit FY 2024-25', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
        """, (self.client_id,))
        self.cy_eng_id = cur.lastrowid

        # PY Transactions
        py_txs = [
            (self.py_eng_id, '2023-06-15', 'Sales Revenue', 'Alpha Retailers', 0.0, 1000000.0, 1000000.0, 'V-PY-01', 'INV-P1', 'Sales billing', 'REF-P1'),
            (self.py_eng_id, '2023-07-20', 'Raw Material Purchases', 'Steel Corp', 500000.0, 0.0, 500000.0, 'V-PY-02', 'INV-P2', 'Raw materials', 'REF-P2'),
            (self.py_eng_id, '2023-08-31', 'Salaries & Wages Expense', 'Payroll', 200000.0, 0.0, 200000.0, 'V-PY-03', 'INV-P3', 'Staff salary', 'REF-P3'),
        ]

        # CY Transactions (including anomalies and cash limit violations)
        cy_txs = [
            # Normal Sales Revenue
            (self.cy_eng_id, '2024-06-15', 'Sales Revenue', 'Alpha Retailers', 0.0, 1800000.0, 1800000.0, 'V-CY-01', 'INV-C1', 'Sales billing', 'REF-C1'),
            # Raw Material Purchases
            (self.cy_eng_id, '2024-07-20', 'Raw Material Purchases', 'Steel Corp', 850000.0, 0.0, 850000.0, 'V-CY-02', 'INV-C2', 'Raw materials', 'REF-C2'),
            # Section 40A(3) Cash Payment Violation (₹65,000 in cash > ₹10,000)
            (self.cy_eng_id, '2024-08-10', 'Cash in Hand', 'Direct Vendor', 65000.0, 0.0, 65000.0, 'V-CY-03', 'INV-C3', 'Cash payment for urgent machine parts', 'REF-C3'),
            # Bank Entries
            (self.cy_eng_id, '2024-09-05', 'HDFC Bank Current Account', 'Direct Client', 450000.0, 0.0, 450000.0, 'V-CY-04', 'INV-C4', 'Cheque deposit unpresented', 'REF-C4'),
            # Unusually large round sum voucher / Statistical outlier
            (self.cy_eng_id, '2024-10-15', 'Consulting & Legal Expenses', 'Apex Advisory Services', 500000.0, 0.0, 500000.0, 'V-CY-05', 'INV-C5', 'Lumpsum retainer fees', 'REF-C5')
        ]

        cur.executemany("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, invoice_no, description, reference_no)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, py_txs + cy_txs)

        # Insert findings
        cur.execute("""
        INSERT INTO audit_findings (engagement_id, engine_type, finding_code, title, severity, category, description, expected_value, actual_value, risk_score, rule_used, recommended_action, reason, created_at)
        VALUES (?, 'DETERMINISTIC_RULES', 'F-40A3-01', 'Cash Payment Exceeding Section 40A(3) Limit', 'CRITICAL', 'Income Tax Act', 'Cash payment of ₹65,000 exceeds statutory ceiling of ₹10,000.', 'Payment via Account Payee cheque / electronic mode', 'Direct cash payment of ₹65,000.00', 9.5, 'Income Tax Act Section 40A(3)', 'Disallow expense under Clause 21(d) Form 3CD', 'Cash payment to vendor above ₹10,000 threshold', datetime('now'))
        """, (self.cy_eng_id,))
        self.finding_id = cur.lastrowid

        conn.commit()
        conn.close()

    def test_01_intent_detection(self):
        """Test accurate offline intent detection across all required audit questions."""
        self.assertEqual(detect_intent("Show me unusual transactions."), "UNUSUAL_TRANSACTIONS")
        self.assertEqual(detect_intent("Find outliers and anomalies"), "UNUSUAL_TRANSACTIONS")
        self.assertEqual(detect_intent("Why was this transaction flagged?"), "EXPLAIN_FLAGGED_TRANSACTION")
        self.assertEqual(detect_intent("Why is voucher V-CY-03 flagged?"), "EXPLAIN_FLAGGED_TRANSACTION")
        self.assertEqual(detect_intent("Which ledgers have the largest year-on-year changes?"), "YOY_CHANGES")
        self.assertEqual(detect_intent("Show unmatched bank transactions."), "UNMATCHED_BANK")
        self.assertEqual(detect_intent("Summarize the major audit exceptions."), "SUMMARIZE_EXCEPTIONS")
        self.assertEqual(detect_intent("Which accounts require review?"), "ACCOUNTS_REQUIRE_REVIEW")
        self.assertEqual(detect_intent("Explain this reconciliation difference."), "EXPLAIN_RECONCILIATION")
        self.assertEqual(detect_intent("Create an audit observation from this finding."), "CREATE_AUDIT_OBSERVATION")
        self.assertEqual(detect_intent("Summarize this client's financial movement."), "FINANCIAL_MOVEMENT")

    def test_02_unusual_transactions_query(self):
        """Test 'Show me unusual transactions.' query returns deterministic anomalies and evidence."""
        engine = LocalAIAssistantEngine(self.cy_eng_id)
        res = engine.process_query("Show me unusual transactions.")

        self.assertEqual(res["intent"], "UNUSUAL_TRANSACTIONS")
        self.assertEqual(res["disclaimer"], MANDATORY_DISCLAIMER)
        self.assertIn("Unusual Transaction", res["response"])
        self.assertGreaterEqual(res["calculated_metrics"]["total_transactions"], 5)
        self.assertGreater(len(res["evidence"]), 0)
        self.assertGreater(len(res["source_transactions"]), 0)

        # Inspect evidence item structure
        first_ev = res["evidence"][0]
        self.assertIn("voucher_no", first_ev)
        self.assertIn("amount", first_ev)
        self.assertIn("rule_or_pattern", first_ev)

    def test_03_explain_flagged_transaction_query(self):
        """Test 'Why was this transaction flagged?' provides statutory violation breakdown."""
        engine = LocalAIAssistantEngine(self.cy_eng_id)
        res = engine.process_query("Why was voucher V-CY-03 flagged?", voucher_no="V-CY-03")

        self.assertEqual(res["intent"], "EXPLAIN_FLAGGED_TRANSACTION")
        self.assertEqual(res["disclaimer"], MANDATORY_DISCLAIMER)
        self.assertIn("V-CY-03", res["response"])
        self.assertIn("40A(3)", res["response"])
        self.assertEqual(len(res["source_transactions"]), 1)
        self.assertEqual(res["source_transactions"][0]["voucher_no"], "V-CY-03")

    def test_04_yoy_changes_query(self):
        """Test 'Which ledgers have the largest year-on-year changes?' computes exact variances."""
        engine = LocalAIAssistantEngine(self.cy_eng_id)
        res = engine.process_query("Which ledgers have the largest year-on-year changes?")

        self.assertEqual(res["intent"], "YOY_CHANGES")
        self.assertEqual(res["disclaimer"], MANDATORY_DISCLAIMER)
        self.assertIn("Year-on-Year", res["response"])
        self.assertIn("Sales Revenue", res["response"])
        self.assertGreater(len(res["evidence"]), 0)

        # Check that evidence has numeric differences calculated
        sales_ev = next((e for e in res["evidence"] if "Sales" in e["account_name"]), None)
        self.assertIsNotNone(sales_ev)
        self.assertEqual(sales_ev["previous_year"], 1000000.0)
        self.assertEqual(sales_ev["current_year"], 1800000.0)
        self.assertEqual(sales_ev["absolute_difference"], 800000.0)

    def test_05_unmatched_bank_and_review_accounts_queries(self):
        """Test bank transactions and accounts requiring review queries."""
        engine = LocalAIAssistantEngine(self.cy_eng_id)
        
        # Bank Query
        res_bank = engine.process_query("Show unmatched bank transactions.")
        self.assertEqual(res_bank["intent"], "UNMATCHED_BANK")
        self.assertEqual(res_bank["disclaimer"], MANDATORY_DISCLAIMER)
        self.assertIn("Bank Reconciliation", res_bank["response"])

        # Accounts Requiring Review Query
        res_acc = engine.process_query("Which accounts require review?")
        self.assertEqual(res_acc["intent"], "ACCOUNTS_REQUIRE_REVIEW")
        self.assertIn("Accounts & Ledgers Requiring", res_acc["response"])

    def test_06_audit_observation_and_financial_movement(self):
        """Test creating working paper audit observation and summarizing financial movement."""
        engine = LocalAIAssistantEngine(self.cy_eng_id)

        # Observation
        res_obs = engine.process_query("Create an audit observation from this finding.", finding_id=self.finding_id)
        self.assertEqual(res_obs["intent"], "CREATE_AUDIT_OBSERVATION")
        self.assertIn("Condition", res_obs["response"])
        self.assertIn("Criteria", res_obs["response"])
        self.assertIn("Cause", res_obs["response"])
        self.assertIn("Effect", res_obs["response"])
        self.assertIn("Recommendation", res_obs["response"])

        # Financial Movement
        res_mov = engine.process_query("Summarize this client's financial movement.")
        self.assertEqual(res_mov["intent"], "FINANCIAL_MOVEMENT")
        self.assertIn("Operating Performance", res_mov["response"])

    def test_07_api_assistant_endpoints(self):
        """Test FastAPI assistant endpoints (POST query, GET summary, GET suggested-prompts)."""
        # 1. Query endpoint
        res = self.client.post("/api/assistant/query", json={
            "engagement_id": self.cy_eng_id,
            "query": "Summarize the major audit exceptions."
        }, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["intent"], "SUMMARIZE_EXCEPTIONS")
        self.assertEqual(data["disclaimer"], MANDATORY_DISCLAIMER)

        # 2. Summary endpoint
        res_sum = self.client.get(f"/api/assistant/summary/{self.cy_eng_id}", headers=self.headers)
        self.assertEqual(res_sum.status_code, 200)
        sum_data = res_sum.json()
        self.assertIn("narrative", sum_data)
        self.assertEqual(sum_data["disclaimer"], MANDATORY_DISCLAIMER)

        # 3. Suggested Prompts endpoint
        res_prompts = self.client.get(f"/api/assistant/suggested-prompts/{self.cy_eng_id}", headers=self.headers)
        self.assertEqual(res_prompts.status_code, 200)
        p_data = res_prompts.json()
        self.assertGreaterEqual(len(p_data["prompts"]), 8)
        self.assertEqual(p_data["disclaimer"], MANDATORY_DISCLAIMER)

if __name__ == "__main__":
    unittest.main()
