import os
import unittest
import json
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.services.trial_balance_analyzer import analyze_trial_balance, get_ai_explanation_for_exception

class TestTrialBalanceAnalysisModule(unittest.TestCase):
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

    def test_01_deterministic_balanced_tb(self):
        """Test analyzing a perfectly balanced trial balance."""
        conn = get_db_connection()
        # Create unique test client & engagement
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, gstin, created_at)
        VALUES ('TB Test Balanced Client', 'Private Limited Company', 'AAACB1234F', '27AAACB1234F1Z5', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
        VALUES (?, 'Statutory Audit 2024-25', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        # Insert balanced double-entry transactions (Total Dr: 50,000, Total Cr: 50,000)
        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, account_group, debit, credit, amount, voucher_no)
        VALUES 
        (?, '2024-04-10', 'HDFC Bank Account', 'Assets', 50000.0, 0.0, 50000.0, 'V-1'),
        (?, '2024-04-10', 'Sales Revenue', 'Revenue', 0.0, 50000.0, 50000.0, 'V-1')
        """, (eng_id, eng_id))
        conn.commit()
        conn.close()

        # Run analysis service
        result = analyze_trial_balance(eng_id)
        self.assertTrue(result["is_balanced"])
        self.assertEqual(result["grand_total_debit"], 50000.0)
        self.assertEqual(result["grand_total_credit"], 50000.0)
        self.assertEqual(result["difference"], 0.0)
        self.assertEqual(result["overall_risk_rating"], "LOW")

        # Test API endpoint
        res = self.client.get(f"/api/trial-balance/{eng_id}", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_balanced"])
        self.assertEqual(data["difference"], 0.0)
        self.assertEqual(len(data["accounts"]), 2)

    def test_02_deterministic_unbalanced_tb_high_priority_exception(self):
        """Test that Total Debit != Total Credit generates a CRITICAL/HIGH exception showing exact difference."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, gstin, created_at)
        VALUES ('TB Test Unbalanced Client', 'Partnership', 'AABFP1234D', '27AABFP1234D1Z2', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
        VALUES (?, 'Statutory Audit 2024-25', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        # Insert unbalanced transactions: Debit: 1,50,000, Credit: 1,20,000 (Diff: 30,000)
        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, account_group, debit, credit, amount, voucher_no)
        VALUES 
        (?, '2024-05-01', 'Plant & Machinery', 'Assets', 150000.0, 0.0, 150000.0, 'VR-01'),
        (?, '2024-05-01', 'Vendor Payable', 'Liabilities', 0.0, 120000.0, 120000.0, 'VR-01')
        """, (eng_id, eng_id))
        conn.commit()
        conn.close()

        result = analyze_trial_balance(eng_id)
        self.assertFalse(result["is_balanced"])
        self.assertEqual(result["grand_total_debit"], 150000.0)
        self.assertEqual(result["grand_total_credit"], 120000.0)
        self.assertEqual(result["difference"], 30000.0)
        self.assertEqual(result["overall_risk_rating"], "CRITICAL")

        # Verify high priority exception generated
        ex_tally = next((e for e in result["exceptions"] if e["check_id"] == "CHK_01_TB_TALLY"), None)
        self.assertIsNotNone(ex_tally)
        self.assertEqual(ex_tally["severity"], "CRITICAL")
        self.assertEqual(ex_tally["exact_difference"], 30000.0)
        self.assertIn("Plant & Machinery", ex_tally["affected_accounts"])

    def test_03_unusual_balances_and_suspense_detection(self):
        """Test detecting abnormal negative balances (Cash in Hand credit, Debtors credit) and Suspense heads."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, gstin, created_at)
        VALUES ('TB Anomaly Client', 'Proprietorship', 'BNZPK9999Q', '27BNZPK9999Q1Z4', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
        VALUES (?, 'Tax Audit 2024-25', 'Tax Audit', '2024-25', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        # Insert:
        # 1. Cash in Hand with negative balance (Debit 10,000, Credit 35,000 -> Closing -25,000)
        # 2. Suspense Account with parked balance (Debit 25,000, Credit 0)
        # 3. Trade Debtors with abnormal credit (Credit 50,000)
        # 4. Sales with debit 50,000
        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, account_group, debit, credit, amount, voucher_no)
        VALUES 
        (?, '2024-06-01', 'Petty Cash A/c', 'Assets', 10000.0, 35000.0, 35000.0, 'V-10'),
        (?, '2024-06-02', 'Suspense Account', 'Liabilities', 25000.0, 0.0, 25000.0, 'V-11'),
        (?, '2024-06-03', 'Sundry Debtors - Acme', 'Assets', 0.0, 50000.0, 50000.0, 'V-12'),
        (?, '2024-06-03', 'Sales Revenue', 'Revenue', 50000.0, 0.0, 50000.0, 'V-13')
        """, (eng_id, eng_id, eng_id, eng_id))
        conn.commit()
        conn.close()

        result = analyze_trial_balance(eng_id)

        # 1. Check Unusual Balances
        unusual_ex = next((e for e in result["exceptions"] if e["check_id"] == "CHK_04_UNUSUAL_BALANCES"), None)
        self.assertIsNotNone(unusual_ex)
        self.assertEqual(unusual_ex["severity"], "HIGH")
        affected_names = [a.lower() for a in unusual_ex["affected_accounts"]]
        self.assertTrue(any("cash" in a for a in affected_names))

        # 2. Check Suspense Accounts
        suspense_ex = next((e for e in result["exceptions"] if e["check_id"] == "CHK_08_SUSPENSE_ACCOUNTS"), None)
        self.assertIsNotNone(suspense_ex)
        self.assertIn("Suspense Account", suspense_ex["affected_accounts"])

    def test_04_ledger_drilldown_endpoint(self):
        """Test GET /api/trial-balance/{engagement_id}/ledger-drilldown."""
        conn = get_db_connection()
        eng = conn.execute("SELECT id FROM engagements LIMIT 1").fetchone()
        eng_id = eng["id"]

        # Clean up any existing records for this test ledger
        conn.execute("DELETE FROM transactions WHERE engagement_id = ? AND ledger = 'HDFC Bank Drilldown'", (eng_id,))

        # Insert sample transactions for HDFC Bank
        conn.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, debit, credit, voucher_no, party_name, description)
        VALUES 
        (?, '2024-04-01', 'HDFC Bank Drilldown', 10000.0, 0.0, 'VR-01', 'Customer A', 'Opening Receipt'),
        (?, '2024-04-05', 'HDFC Bank Drilldown', 0.0, 4000.0, 'VR-02', 'Vendor B', 'Payment')
        """, (eng_id, eng_id))
        conn.commit()
        conn.close()

        res = self.client.get(
            f"/api/trial-balance/{eng_id}/ledger-drilldown?ledger_name=HDFC Bank Drilldown",
            headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["ledger_name"], "HDFC Bank Drilldown")
        self.assertEqual(data["total_transactions"], 2)
        self.assertEqual(data["net_balance"], 6000.0)
        self.assertEqual(data["transactions"][0]["running_balance"], 10000.0)
        self.assertEqual(data["transactions"][1]["running_balance"], 6000.0)

    def test_05_ai_explanation_endpoint(self):
        """Test POST /api/trial-balance/{engagement_id}/ai-explain returns deterministic ICAI guidance."""
        conn = get_db_connection()
        eng = conn.execute("SELECT id FROM engagements LIMIT 1").fetchone()
        eng_id = eng["id"]
        conn.close()

        res = self.client.post(
            f"/api/trial-balance/{eng_id}/ai-explain",
            headers=self.headers,
            json={
                "check_id": "CHK_01_TB_TALLY",
                "check_name": "Trial Balance Out of Balance",
                "exact_difference": 30000.0,
                "affected_accounts": ["Plant & Machinery", "Vendor Payable"],
                "sa_reference": "SA 500"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["check_id"], "CHK_01_TB_TALLY")
        self.assertIn("Ind AS 1 / AS 1", data["explanation"])
        self.assertTrue(len(data["suggested_audit_procedures"]) >= 3)
        self.assertIn("Deterministic", data["compliance_note"])

    def test_06_download_trial_balance_csv_report(self):
        """Test GET /api/trial-balance/{engagement_id}/report/download."""
        conn = get_db_connection()
        eng = conn.execute("SELECT id FROM engagements LIMIT 1").fetchone()
        eng_id = eng["id"]
        conn.close()

        res = self.client.get(
            f"/api/trial-balance/{eng_id}/report/download",
            headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.headers["content-type"])
        self.assertIn("TRIAL BALANCE ANALYSIS & AUDIT EXCEPTION REPORT", res.text)
        self.assertIn("EXECUTIVE SUMMARY", res.text)
        self.assertIn("TRIAL BALANCE AUDIT EXCEPTIONS LOG", res.text)

if __name__ == "__main__":
    unittest.main()
