import os
import unittest
import json
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.services.data_normalizer import (
    normalize_date,
    normalize_monetary_amount,
    normalize_entity_name,
    normalize_invoice_voucher,
    normalize_gstin,
    normalize_row_data
)

class TestDataCleaningAndNormalization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

        # Login as Admin / Auditor
        res = cls.client.post("/api/auth/login", json={"username": "admin", "password": "adminpassword123"})
        if res.status_code == 200:
            cls.token = res.json()["access_token"]
        else:
            res = cls.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
            cls.token = res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_01_date_normalization(self):
        """Test standardizing multiple date representations to YYYY-MM-DD."""
        # 1. DD/MM/YYYY with ambiguous day/month
        norm, rule, is_q, conf = normalize_date("01/04/2026")
        self.assertEqual(norm, "2026-04-01")
        self.assertEqual(rule, "DATE_INDIAN_DMY_AMBIGUOUS")
        self.assertEqual(is_q, 1)

        # Non-ambiguous day (>12)
        norm, rule, is_q, conf = normalize_date("25/04/2026")
        self.assertEqual(norm, "2026-04-25")
        self.assertEqual(rule, "DATE_DAY_FIRST_DMY")
        self.assertEqual(is_q, 0)
        self.assertEqual(conf, 1.0)

        # 2. ISO YYYY-MM-DD
        norm, rule, is_q, conf = normalize_date("2026-04-01")
        self.assertEqual(norm, "2026-04-01")
        self.assertEqual(rule, "ISO_STANDARD")
        self.assertEqual(is_q, 0)

        # 3. Textual month DD-Mon-YYYY
        norm, rule, is_q, conf = normalize_date("01-Apr-2026")
        self.assertEqual(norm, "2026-04-01")
        self.assertEqual(rule, "DATE_TEXT_MONTH")
        self.assertEqual(is_q, 0)

        # 4. Dot format DD.MM.YYYY
        norm, rule, is_q, conf = normalize_date("15.08.2025")
        self.assertEqual(norm, "2025-08-15")
        self.assertEqual(rule, "DATE_DAY_FIRST_DMY")
        self.assertEqual(is_q, 0)

    def test_02_amount_normalization(self):
        """Test standardizing monetary amounts with Indian currency symbols, commas, and Cr/Dr signs."""
        # Indian Rupee symbol with comma and trailing /-
        num, norm, rule, is_q, conf = normalize_monetary_amount("₹ 1,50,000.00/-")
        self.assertEqual(num, 150000.0)
        self.assertEqual(norm, "150,000.00")
        self.assertEqual(rule, "CURRENCY_SYMBOL_STRIPPED")

        # Rs. with Dr
        num, norm, rule, is_q, conf = normalize_monetary_amount("Rs. 24,500.50 Dr")
        self.assertEqual(num, 24500.5)
        self.assertEqual(norm, "24,500.50")
        self.assertEqual(rule, "DR_NOTATION_NORMALIZED")

        # Rs. with Cr (Negative representation)
        num, norm, rule, is_q, conf = normalize_monetary_amount("Rs. 10,000.00 Cr")
        self.assertEqual(num, -10000.0)
        self.assertEqual(norm, "-10,000.00")
        self.assertEqual(rule, "CR_NOTATION_NORMALIZED")

        # Bracketed negative format: (5,000.00)
        num, norm, rule, is_q, conf = normalize_monetary_amount("(5,000.00)")
        self.assertEqual(num, -5000.0)
        self.assertEqual(norm, "-5,000.00")
        self.assertEqual(rule, "BRACKETED_NEGATIVE_STANDARDIZED")

    def test_03_entity_and_party_name_normalization(self):
        """Test collapsing extra whitespace, uppercase, and legal entity suffix standardization."""
        norm, rule, is_q, conf = normalize_entity_name("  apex   logistics   private   limited  ")
        self.assertEqual(norm, "Apex Logistics Pvt Ltd")
        self.assertEqual(rule, "LEGAL_SUFFIX_PVT_LTD")

        norm, rule, is_q, conf = normalize_entity_name("reliance  industries  limited")
        self.assertEqual(norm, "Reliance Industries Ltd")
        self.assertEqual(rule, "LEGAL_SUFFIX_LTD")

        norm, rule, is_q, conf = normalize_entity_name("sharma  &  brothers  llp")
        self.assertEqual(norm, "Sharma & Brothers LLP")
        self.assertEqual(rule, "LEGAL_SUFFIX_LLP")

    def test_04_invoice_and_gstin_normalization(self):
        """Test voucher/invoice string cleaning and uppercase 15-character GSTIN formatting."""
        # Invoice number formatting
        norm, rule, is_q, conf = normalize_invoice_voucher("  INV / 2026 / 0042  ")
        self.assertEqual(norm, "INV/2026/0042")
        self.assertEqual(rule, "INVOICE_DELIMITER_NORMALIZED")

        # GSTIN formatting
        norm, rule, is_q, conf = normalize_gstin("  27aabcu9603r1zm  ")
        self.assertEqual(norm, "27AABCU9603R1ZM")
        self.assertEqual(rule, "GSTIN_VALIDATED_NORMALIZED")
        self.assertEqual(is_q, 0)
        self.assertEqual(conf, 1.0)

    def test_05_normalize_row_data_layer_preservation(self):
        """Test that normalize_row_data cleanly separates raw input from normalized data."""
        raw_row = {
            "date": "01-Apr-2026",
            "debit": "₹ 75,000.00/-",
            "credit": "0.00",
            "party_name": "  tata   consultancy   services   limited  ",
            "invoice_no": " INV - 2026 - 101 ",
            "gstin": "27aaact2727q1zw",
            "description": "  Audit and assurance professional fees  "
        }

        cleaned, logs = normalize_row_data(raw_row)

        # Raw preserved untouched
        self.assertIn("original_row_json", cleaned)
        orig = json.loads(cleaned["original_row_json"])
        self.assertEqual(orig["date"], "01-Apr-2026")
        self.assertEqual(orig["debit"], "₹ 75,000.00/-")

        # Normalized values
        self.assertEqual(cleaned["date"], "2026-04-01")
        self.assertEqual(cleaned["debit"], 75000.0)
        self.assertEqual(cleaned["party_name"], "Tata Consultancy Services Ltd")
        self.assertEqual(cleaned["invoice_no"], "INV-2026-101")
        self.assertEqual(cleaned["gstin"], "27AAACT2727Q1ZW")
        self.assertEqual(cleaned["description"], "Audit and assurance professional fees")

        # Logs produced
        self.assertTrue(len(logs) >= 5)
        fields_transformed = [l["field_name"] for l in logs]
        self.assertIn("date", fields_transformed)
        self.assertIn("debit", fields_transformed)
        self.assertIn("party_name", fields_transformed)
        self.assertIn("gstin", fields_transformed)

    def test_06_preview_api_endpoint(self):
        """Test POST /api/cleaning/normalize-preview."""
        res = self.client.post("/api/cleaning/normalize-preview", json={
            "field_name": "date",
            "raw_value": "01-Apr-2026"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["normalized_value"], "2026-04-01")
        self.assertEqual(data["transformation_rule"], "DATE_TEXT_MONTH")

    def test_07_review_and_override_workflow(self):
        """Test reviewing, overriding, and reverting a data transformation log."""
        conn = get_db_connection()
        # Find or create an engagement
        eng = conn.execute("SELECT id FROM engagements LIMIT 1").fetchone()
        eng_id = eng["id"] if eng else 1

        # Insert a test transaction with raw input
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, original_row_json)
        VALUES (?, '2026-04-01', 'Legal Expenses', 'ACME PVT LTD', 15000.0, 0.0, 15000.0, 'VR-999', ?)
        """, (eng_id, json.dumps({"party_name": "acme private limited", "amount": "₹ 15,000.00"})))
        txn_id = cur.lastrowid

        # Insert a transformation log
        cur.execute("""
        INSERT INTO data_cleaning_logs (
            engagement_id, transaction_id, row_number, field_name, original_value,
            normalized_value, transformation_rule, is_questionable, confidence_score, review_status, created_at
        ) VALUES (?, ?, 1, 'party_name', 'acme private limited', 'ACME PVT LTD', 'LEGAL_SUFFIX_PVT_LTD', 0, 1.0, 'Auto-Applied', datetime('now'))
        """, (eng_id, txn_id))
        log_id = cur.lastrowid
        conn.commit()
        conn.close()

        # 1. Check summary endpoint
        res = self.client.get(f"/api/cleaning/summary/{eng_id}")
        self.assertEqual(res.status_code, 200)
        summary = res.json()
        self.assertGreaterEqual(summary["total_transformations"], 1)

        # 2. Check list logs endpoint
        res = self.client.get(f"/api/cleaning/logs/{eng_id}")
        self.assertEqual(res.status_code, 200)
        logs_data = res.json()
        self.assertGreaterEqual(logs_data["total"], 1)

        # 3. Auditor overrides transformation
        res = self.client.put(
            f"/api/cleaning/logs/{log_id}/review",
            headers=self.headers,
            json={
                "action": "Overridden",
                "custom_normalized_value": "ACME ENTERPRISES (INDIA) PVT LTD",
                "auditor_comment": "Verified against Board Resolution and Master Data"
            }
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["action"], "Overridden")

        # Verify transaction table synchronized while raw data preserved
        conn = get_db_connection()
        updated_txn = conn.execute("SELECT party_name, original_row_json FROM transactions WHERE id = ?", (txn_id,)).fetchone()
        self.assertEqual(updated_txn["party_name"], "ACME ENTERPRISES (INDIA) PVT LTD")
        raw_dict = json.loads(updated_txn["original_row_json"])
        self.assertEqual(raw_dict["party_name"], "acme private limited") # Untouched!

        # 4. Auditor reverts transformation
        res = self.client.put(
            f"/api/cleaning/logs/{log_id}/review",
            headers=self.headers,
            json={
                "action": "Reverted",
                "auditor_comment": "Reverting to raw source string as requested by CA"
            }
        )
        self.assertEqual(res.status_code, 200)
        reverted_txn = conn.execute("SELECT party_name FROM transactions WHERE id = ?", (txn_id,)).fetchone()
        self.assertEqual(reverted_txn["party_name"], "acme private limited")
        conn.close()

if __name__ == "__main__":
    unittest.main()
