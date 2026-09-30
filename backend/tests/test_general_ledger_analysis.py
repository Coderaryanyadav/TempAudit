import os
import unittest
import json
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.services.general_ledger_analyzer import analyze_general_ledger

class TestGeneralLedgerAnalysisModule(unittest.TestCase):
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

    def test_01_gl_duplicate_entries_and_repeated_amounts(self):
        """Test detection of duplicate entries (GL_01) and repeated amounts (GL_02)."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, gstin, created_at)
        VALUES ('GL Test Client 1', 'Private Limited Company', 'GLPAN1234F', '27GLPAN1234F1Z5', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
        VALUES (?, 'GL Audit 2024-25', 'Statutory Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        # Insert duplicate transactions (same date, ledger, party, amount)
        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description)
        VALUES 
        (?, '2024-05-10', 'Professional Fees', 'Apex Legal Consultants', 45000.0, 0.0, 45000.0, 'V-101', 'Legal retainer'),
        (?, '2024-05-10', 'Professional Fees', 'Apex Legal Consultants', 45000.0, 0.0, 45000.0, 'V-102', 'Legal retainer'),
        (?, '2024-05-15', 'Professional Fees', 'Apex Legal Consultants', 45000.0, 0.0, 45000.0, 'V-103', 'Legal retainer')
        """, (eng_id, eng_id, eng_id))
        conn.commit()
        conn.close()

        # Run analysis
        result = analyze_general_ledger(eng_id)
        self.assertEqual(result["total_transactions"], 3)
        self.assertGreater(result["flagged_transactions_count"], 0)

        # Check for GL_01_DUPLICATE_ENTRY and GL_02_REPEATED_AMOUNT
        rule_codes = [a["rule"] for a in result["anomalies"]]
        self.assertIn("GL_01_DUPLICATE_ENTRY", rule_codes)
        self.assertIn("GL_02_REPEATED_AMOUNT", rule_codes)

        # Verify terminology compliance: no fraud words
        for a in result["anomalies"]:
            self.assertNotIn("fraud", a["reason"].lower())
            self.assertNotIn("illegal", a["reason"].lower())
            self.assertIn(a["severity"], ["CRITICAL", "HIGH", "MEDIUM", "LOW"])

    def test_02_gl_weekend_and_out_of_period(self):
        """Test detection of Sunday / weekend postings (GL_04) and out-of-period dates (GL_05)."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, created_at)
        VALUES ('GL Test Client 2', 'Partnership', 'GLPAN5678F', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
        VALUES (?, 'GL Audit Cutoff 2024-25', 'Internal Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        # 2024-05-12 is Sunday (GL_04)
        # 2025-04-15 is Outside Period FY 2024-25 (GL_05)
        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description)
        VALUES 
        (?, '2024-05-12', 'Office Expenses', 'Sunday Mart', 15000.0, 0.0, 15000.0, 'V-SUN-1', 'Sunday hardware repairs'),
        (?, '2025-04-15', 'Sales Revenue', 'Future Client Ltd', 0.0, 85000.0, 85000.0, 'V-FUT-1', 'Post cutoff sale')
        """, (eng_id, eng_id))
        conn.commit()
        conn.close()

        result = analyze_general_ledger(eng_id)
        rule_codes = [a["rule"] for a in result["anomalies"]]
        self.assertIn("GL_04_WEEKEND_POSTING", rule_codes)
        self.assertIn("GL_05_OUT_OF_PERIOD", rule_codes)

    def test_03_gl_round_numbers_manual_jvs_and_large_txns(self):
        """Test round number (GL_08), manual journal entry (GL_06), and large transaction (GL_07)."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, created_at)
        VALUES ('GL Test Client 3', 'Private Limited Company', 'GLPAN9012F', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
        VALUES (?, 'GL Audit Substantive 2024-25', 'Statutory Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        # Large round amount JV entry
        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description)
        VALUES 
        (?, '2024-06-20', 'Consulting Expense', 'Alpha Advisers', 1000000.0, 0.0, 1000000.0, 'JV-042', 'Manual rectification adjustment of consulting fees')
        """, (eng_id,))
        conn.commit()
        conn.close()

        result = analyze_general_ledger(eng_id)
        rule_codes = [a["rule"] for a in result["anomalies"]]
        self.assertIn("GL_06_MANUAL_JOURNAL", rule_codes)
        self.assertIn("GL_07_LARGE_TRANSACTION", rule_codes)
        self.assertIn("GL_08_ROUND_NUMBER", rule_codes)

    def test_04_gl_reversal_entries_and_unbalanced_vouchers(self):
        """Test reversal entry pairs (GL_10) and one-sided vouchers (GL_12, GL_13)."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, created_at)
        VALUES ('GL Test Client 4', 'LLP', 'GLPAN3456F', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
        VALUES (?, 'GL Audit Offsets 2024-25', 'Statutory Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        # Reversal pair (Dr 75,000 on June 1, Cr 75,000 on June 10 in same ledger)
        # Unbalanced voucher 'VCH-UNBAL-1' (Dr 120,000 with Cr 0)
        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description)
        VALUES 
        (?, '2024-06-01', 'Vendor A/c', 'ABC Suppliers', 75000.0, 0.0, 75000.0, 'V-INV-1', 'Goods purchase'),
        (?, '2024-06-10', 'Vendor A/c', 'ABC Suppliers', 0.0, 75000.0, 75000.0, 'V-REV-1', 'Invoice cancellation reversal'),
        (?, '2024-07-05', 'Machinery A/c', 'Plant Supplier', 120000.0, 0.0, 120000.0, 'VCH-UNBAL-1', 'One-sided asset addition')
        """, (eng_id, eng_id, eng_id))
        conn.commit()
        conn.close()

        result = analyze_general_ledger(eng_id)
        rule_codes = [a["rule"] for a in result["anomalies"]]
        self.assertIn("GL_10_REVERSAL_ENTRY", rule_codes)
        self.assertIn("GL_12_DEBIT_WITHOUT_CREDIT", rule_codes)

    def test_05_gl_api_endpoints_and_filtering(self):
        """Test API endpoints: analysis, ledgers list, parties list, and multi-attribute filters."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, created_at)
        VALUES ('GL Test API Client', 'Private Limited Company', 'GLPAN7890F', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
        VALUES (?, 'GL API Testing FY 2024-25', 'Statutory Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description)
        VALUES 
        (?, '2024-04-10', 'Freight & Carriage', 'Blue Dart Express', 12500.0, 0.0, 12500.0, 'VCH-FR-01', 'Courier charges'),
        (?, '2024-05-12', 'Printing & Stationery', 'Paper Mart', 8000.0, 0.0, 8000.0, 'VCH-ST-02', 'Office registers'),
        (?, '2024-06-15', 'Sales Revenue', 'Reliance Retail', 0.0, 350000.0, 350000.0, 'VCH-SL-03', 'Product delivery')
        """, (eng_id, eng_id, eng_id))
        conn.commit()
        conn.close()

        # 1. Test distinct ledgers endpoint
        res = self.client.get(f"/api/transactions/ledgers-list/{eng_id}", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        ledgers = res.json()["ledgers"]
        self.assertIn("Freight & Carriage", ledgers)
        self.assertIn("Sales Revenue", ledgers)

        # 2. Test distinct parties endpoint
        res = self.client.get(f"/api/transactions/parties-list/{eng_id}", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        parties = res.json()["parties"]
        self.assertIn("Blue Dart Express", parties)
        self.assertIn("Reliance Retail", parties)

        # 3. Test GL Analysis endpoint with filter (ledger = 'Sales Revenue')
        res = self.client.get(f"/api/transactions/analysis/{eng_id}?ledger=Sales%20Revenue", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_transactions"], 1)
        self.assertEqual(data["transactions"][0]["ledger"], "Sales Revenue")

        # 4. Test amount filter (min_amount = 300000)
        res = self.client.get(f"/api/transactions/analysis/{eng_id}?min_amount=300000", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_transactions"], 1)
        self.assertEqual(data["transactions"][0]["amount"], 350000.0)

        # 5. Test date filter
        res = self.client.get(f"/api/transactions/analysis/{eng_id}?start_date=2024-05-01&end_date=2024-05-31", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_transactions"], 1)
        self.assertEqual(data["transactions"][0]["ledger"], "Printing & Stationery")

    def test_06_gl_download_report_csv(self):
        """Test downloading General Ledger Analysis Report as CSV."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, created_at)
        VALUES ('GL CSV Test Client', 'Private Limited Company', 'GLCSV1234F', datetime('now'))
        """)
        client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, period_start, period_end, created_at, updated_at)
        VALUES (?, 'GL CSV Audit 2024-25', 'Statutory Audit', '2024-25', '2024-04-01', '2025-03-31', datetime('now'), datetime('now'))
        """, (client_id,))
        eng_id = cur.lastrowid

        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, description)
        VALUES 
        (?, '2024-05-12', 'Sunday Mart Ledger', 'Sunday Mart', 50000.0, 0.0, 50000.0, 'V-SUN-99', 'Sunday round amount')
        """, (eng_id,))
        conn.commit()
        conn.close()

        res = self.client.get(f"/api/transactions/report/{eng_id}/download", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.headers.get("content-type", ""))
        self.assertIn("FinAuditPro - General Ledger Analysis & Anomaly Report", res.text)
        self.assertIn("Sunday Mart Ledger", res.text)

if __name__ == "__main__":
    unittest.main()
