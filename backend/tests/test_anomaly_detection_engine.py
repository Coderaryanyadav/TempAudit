import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.services.anomaly_detection_engine import (
    detect_all_anomalies,
    update_anomaly_review,
    generate_ai_anomaly_explanation,
    generate_anomaly_csv_report,
    calculate_benford_mad,
    AUDIT_DISCLAIMER
)

class TestAIAnomalyDetectionEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

        # Authenticate
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

        # Create unique client & engagement
        cur.execute("""
        INSERT INTO clients (name, entity_type, pan, gstin, created_at, updated_at)
        VALUES ('Apex BioPharma India Ltd', 'Public Limited Company', 'AAACB1122C', '27AAACB1122C1Z2', datetime('now'), datetime('now'))
        """)
        self.client_id = cur.lastrowid

        cur.execute("""
        INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
        VALUES (?, 'Statutory & Tax Audit FY 2024-25', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
        """, (self.client_id,))
        self.eng_id = cur.lastrowid

        # Insert representative test dataset covering all 3 Hybrid levels:
        # 1. Section 40A(3) Cash Payment > 10,000 (Tx 1)
        # 2. Section 269ST Cash Receipt >= 2,00,000 (Tx 2)
        # 3. Repeated Round-Number Transactions (Tx 3, 4, 5)
        # 4. Significant Month-End Cutoff Entry (Tx 6)
        # 5. Unusual Weekend Manual JV (Tx 7)
        # 6. Unusual First-Time High-Value Vendor (Tx 8)
        # 7. Statistical Z-Score Outlier (Tx 9)
        # 8. Monthly Category Expense Surge (Tx 10, 11, 12, 13)
        # 9. Daily Velocity Burst (Tx 14, 15, 16, 17, 18, 19, 20 on same date)
        # 10. Standard regular baseline operational transactions (Tx 21-35)
        test_txs = [
            # 1. Section 40A(3) Cash Payment > ₹10k
            (self.eng_id, '2024-05-12', 'Cash in Hand Ledger', 'Local Transporter Logistics', 0.0, 48000.0, 48000.0, 'V-CSH-01', 'INV-CSH-1', 'Cash freight payment without 6DD declaration', 'CHQ-NONE'),
            
            # 2. Section 269ST Cash Receipt >= ₹2L
            (self.eng_id, '2024-05-15', 'Cash in Hand Ledger', 'Direct Scrap Buyer', 250000.0, 0.0, 250000.0, 'V-CSH-02', 'INV-SCRAP-1', 'Cash receipt against factory scrap sale', 'REF-NONE'),

            # 3. Repeated Round Numbers (Consulting Expense)
            (self.eng_id, '2024-06-10', 'Management Consultancy Fees', 'Strategic Advisory Corp', 100000.0, 0.0, 100000.0, 'V-CNS-01', 'INV-CNS-1', 'Round fee retainer', 'REF-001'),
            (self.eng_id, '2024-07-10', 'Management Consultancy Fees', 'Strategic Advisory Corp', 100000.0, 0.0, 100000.0, 'V-CNS-02', 'INV-CNS-2', 'Round fee retainer', 'REF-002'),
            (self.eng_id, '2024-08-10', 'Management Consultancy Fees', 'Strategic Advisory Corp', 100000.0, 0.0, 100000.0, 'V-CNS-03', 'INV-CNS-3', 'Round fee retainer', 'REF-003'),

            # 4. Month-End Cutoff Entry (31st March / 30th June)
            (self.eng_id, '2024-06-30', 'Software Development Expense', 'CloudScale Technologies', 350000.0, 0.0, 350000.0, 'V-SW-99', 'INV-CS-99', 'Quarter-end cloud migration milestone', 'REF-991'),

            # 5. Unusual Weekend Manual Journal Entry (Sunday, 2024-07-07)
            (self.eng_id, '2024-07-07', 'Miscellaneous Expense Ledger', 'Direct Party', 85000.0, 0.0, 85000.0, 'JV-ADJ-07', '', 'Sunday manual rectification entry', 'REF-JV-7'),

            # 6. Unusual First-Time High-Value Vendor
            (self.eng_id, '2024-08-20', 'Marketing & Promotions', 'Nova Media Zenith Agency', 450000.0, 0.0, 450000.0, 'V-MKT-01', 'INV-NOV-1', 'One-time product rebranding campaign', 'REF-NOV-1'),

            # 7. Statistical Z-Score Outlier in Office Supplies (Standard mean ~₹4,000, Outlier ₹1,80,000)
            (self.eng_id, '2024-09-15', 'Office Stationery & Supplies', 'Everest Paper Mart', 180000.0, 0.0, 180000.0, 'V-OFF-99', 'INV-EV-99', 'Bulk executive office stationary purchase', 'REF-EV-1'),
            (self.eng_id, '2024-04-10', 'Office Stationery & Supplies', 'Everest Paper Mart', 4200.0, 0.0, 4200.0, 'V-OFF-01', 'INV-EV-01', 'Regular paper reams', 'REF-EV-2'),
            (self.eng_id, '2024-05-10', 'Office Stationery & Supplies', 'Everest Paper Mart', 3800.0, 0.0, 3800.0, 'V-OFF-02', 'INV-EV-02', 'Printer cartridges', 'REF-EV-3'),
            (self.eng_id, '2024-06-10', 'Office Stationery & Supplies', 'Everest Paper Mart', 4500.0, 0.0, 4500.0, 'V-OFF-03', 'INV-EV-03', 'Files and folders', 'REF-EV-4'),
            (self.eng_id, '2024-07-10', 'Office Stationery & Supplies', 'Everest Paper Mart', 4100.0, 0.0, 4100.0, 'V-OFF-04', 'INV-EV-04', 'Office supplies', 'REF-EV-5'),

            # 8. Monthly Category Surge (Repairs & Maintenance in October ₹6,50,000 vs ~₹20,000)
            (self.eng_id, '2024-04-20', 'Plant Repairs & Maintenance', 'Standard Engineering Works', 22000.0, 0.0, 22000.0, 'V-RPM-1', 'INV-RPM-1', 'Monthly maintenance', 'REF-RPM-1'),
            (self.eng_id, '2024-05-20', 'Plant Repairs & Maintenance', 'Standard Engineering Works', 18000.0, 0.0, 18000.0, 'V-RPM-2', 'INV-RPM-2', 'Monthly maintenance', 'REF-RPM-2'),
            (self.eng_id, '2024-06-20', 'Plant Repairs & Maintenance', 'Standard Engineering Works', 25000.0, 0.0, 25000.0, 'V-RPM-3', 'INV-RPM-3', 'Monthly maintenance', 'REF-RPM-3'),
            (self.eng_id, '2024-10-15', 'Plant Repairs & Maintenance', 'Standard Engineering Works', 650000.0, 0.0, 650000.0, 'V-RPM-9', 'INV-RPM-9', 'Emergency plant overhaul repairs', 'REF-RPM-9'),

            # 9. Daily Velocity Burst (7 transactions on 2024-11-28)
            (self.eng_id, '2024-11-28', 'Travel & Conveyance', 'Staff Member A', 5400.0, 0.0, 5400.0, 'V-TRV-1', 'INV-T-1', 'Local travel claim', 'REF-T-1'),
            (self.eng_id, '2024-11-28', 'Travel & Conveyance', 'Staff Member B', 6200.0, 0.0, 6200.0, 'V-TRV-2', 'INV-T-2', 'Local travel claim', 'REF-T-2'),
            (self.eng_id, '2024-11-28', 'Travel & Conveyance', 'Staff Member C', 4800.0, 0.0, 4800.0, 'V-TRV-3', 'INV-T-3', 'Local travel claim', 'REF-T-3'),
            (self.eng_id, '2024-11-28', 'Travel & Conveyance', 'Staff Member D', 5100.0, 0.0, 5100.0, 'V-TRV-4', 'INV-T-4', 'Local travel claim', 'REF-T-4'),
            (self.eng_id, '2024-11-28', 'Travel & Conveyance', 'Staff Member E', 7300.0, 0.0, 7300.0, 'V-TRV-5', 'INV-T-5', 'Local travel claim', 'REF-T-5'),
            (self.eng_id, '2024-11-28', 'Travel & Conveyance', 'Staff Member F', 6900.0, 0.0, 6900.0, 'V-TRV-6', 'INV-T-6', 'Local travel claim', 'REF-T-6'),
            (self.eng_id, '2024-11-28', 'Travel & Conveyance', 'Staff Member G', 5800.0, 0.0, 5800.0, 'V-TRV-7', 'INV-T-7', 'Local travel claim', 'REF-T-7'),

            # 10. Additional baseline operational transactions
            (self.eng_id, '2024-04-05', 'Electricity & Power', 'Maharashtra State Electricity Board', 34500.0, 0.0, 34500.0, 'V-UT-01', 'INV-EB-1', 'Factory power bill', 'REF-EB-1'),
            (self.eng_id, '2024-05-05', 'Electricity & Power', 'Maharashtra State Electricity Board', 36200.0, 0.0, 36200.0, 'V-UT-02', 'INV-EB-2', 'Factory power bill', 'REF-EB-2'),
            (self.eng_id, '2024-06-05', 'Electricity & Power', 'Maharashtra State Electricity Board', 38100.0, 0.0, 38100.0, 'V-UT-03', 'INV-EB-3', 'Factory power bill', 'REF-EB-3'),
            (self.eng_id, '2024-07-05', 'Electricity & Power', 'Maharashtra State Electricity Board', 35900.0, 0.0, 35900.0, 'V-UT-04', 'INV-EB-4', 'Factory power bill', 'REF-EB-4'),
            (self.eng_id, '2024-08-05', 'Electricity & Power', 'Maharashtra State Electricity Board', 37400.0, 0.0, 37400.0, 'V-UT-05', 'INV-EB-5', 'Factory power bill', 'REF-EB-5'),
            (self.eng_id, '2024-09-05', 'Electricity & Power', 'Maharashtra State Electricity Board', 39000.0, 0.0, 39000.0, 'V-UT-06', 'INV-EB-6', 'Factory power bill', 'REF-EB-6')
        ]

        cur.executemany("""
        INSERT INTO transactions (engagement_id, date, ledger, party_name, debit, credit, amount, voucher_no, invoice_no, description, reference_no)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, test_txs)

        conn.commit()
        conn.close()

    def test_01_benford_law_calculation(self):
        """Test Benford's Law leading digit computation and Mean Absolute Deviation (MAD)."""
        amounts = [102.5, 1400.0, 19500.0, 2400.0, 2800.0, 3100.0, 4200.0, 5500.0, 6200.0, 7800.0, 8900.0, 9500.0] * 5
        mad, conformity, dist = calculate_benford_mad(amounts)
        self.assertIsInstance(mad, float)
        self.assertIn(conformity, ["Close Conformity", "Acceptable Conformity", "Marginally Acceptable", "Non-Conformity (Suspicious Distribution)", "Insufficient Data"])
        if dist:
            self.assertIn(1, dist)
            self.assertIn(9, dist)

    def test_02_level_1_deterministic_anomalies(self):
        """Test Level 1 Deterministic Rules: Section 40A(3), Section 269ST, Round numbers, Month-end, Weekend JVs, First-time vendor."""
        result = detect_all_anomalies(self.eng_id)
        anomalies = result["anomalies"]
        patterns = [a["pattern_type"] for a in anomalies]

        # 1. Section 40A(3)
        self.assertTrue(any("40A(3)" in p for p in patterns))
        cash_40a = next(a for a in anomalies if "40A(3)" in a["pattern_type"])
        self.assertEqual(cash_40a["severity"], "CRITICAL")
        self.assertGreaterEqual(cash_40a["anomaly_score"], 90.0)
        self.assertIn("Local Transporter", cash_40a["explanation"])

        # 2. Section 269ST
        self.assertTrue(any("269ST" in p for p in patterns))
        cash_269 = next(a for a in anomalies if "269ST" in a["pattern_type"])
        self.assertEqual(cash_269["severity"], "CRITICAL")
        self.assertEqual(cash_269["evidence"]["cash_receipt_amount"], 250000.0)

        # 3. Repeated Round Numbers
        self.assertTrue(any("Repeated Round-Number" in p for p in patterns))

        # 4. Month-End Cutoff Clustering
        self.assertTrue(any("Month-End Activity" in p for p in patterns))

        # 5. Weekend Manual JV
        self.assertTrue(any("Unusual Journal Entry" in p for p in patterns))

        # 6. First-Time Vendor Outlier
        self.assertTrue(any("First-Time Outlier" in p for p in patterns))

    def test_03_level_2_statistical_anomalies(self):
        """Test Level 2 Statistical Analysis: Z-Score Outlier, Category Surge, Velocity Spike."""
        result = detect_all_anomalies(self.eng_id)
        anomalies = result["anomalies"]
        patterns = [a["pattern_type"] for a in anomalies]

        # 1. Z-Score Outlier in Office Supplies
        self.assertTrue(any("Z-Score Outlier" in p for p in patterns))
        z_anom = next(a for a in anomalies if "Z-Score Outlier" in a["pattern_type"])
        self.assertGreater(z_anom["evidence"]["z_score"], 1.8)
        self.assertEqual(z_anom["evidence"]["transaction_amount"], 180000.0)

        # 2. Category Monthly Expense Surge in Plant Repairs
        self.assertTrue(any("Category Surge" in p for p in patterns))
        surge_ledgers = [a["evidence"]["ledger"] for a in anomalies if "Category Surge" in a["pattern_type"]]
        self.assertIn("Plant Repairs & Maintenance", surge_ledgers)
        plant_surge = next(a for a in anomalies if "Category Surge" in a["pattern_type"] and a["evidence"]["ledger"] == "Plant Repairs & Maintenance")
        self.assertGreaterEqual(plant_surge["evidence"]["surge_multiplier"], 2.0)

        # 3. Velocity Spike
        self.assertTrue(any("Velocity Spike" in p for p in patterns))

    def test_04_level_3_machine_learning_anomalies(self):
        """Test Level 3 Machine Learning: Isolation Forest & Local Outlier Factor."""
        result = detect_all_anomalies(self.eng_id)
        anomalies = result["anomalies"]
        ml_anomalies = [a for a in anomalies if "LEVEL 3" in a["level"]]

        # Machine Learning models (Isolation Forest / LOF) should flag high multidimensional outliers
        self.assertGreater(len(ml_anomalies), 0)
        top_ml = ml_anomalies[0]
        self.assertIn("algorithm", top_ml["evidence"])
        self.assertGreaterEqual(top_ml["anomaly_score"], 70.0)

    def test_05_audit_terminology_and_safeguards(self):
        """Verify that 'fraud' is never declared and standard audit caution is strictly used."""
        result = detect_all_anomalies(self.eng_id)
        for a in result["anomalies"]:
            # Never state "This is fraud"
            self.assertNotIn("this is fraud", a["explanation"].lower())
            self.assertNotIn("fraudulent transaction", a["explanation"].lower())
            # Strictly includes audit disclaimer
            self.assertIn(AUDIT_DISCLAIMER.lower(), a["explanation"].lower())
            # Actionable review provided
            self.assertTrue(len(a["recommended_review"]) > 10)

    def test_06_auditor_review_and_ai_memo_api(self):
        """Test API endpoints: GET anomalies, PUT review status, POST AI memo, and GET CSV download."""
        # 1. Fetch anomalies via API
        res_get = self.client.get(f"/api/anomalies/{self.eng_id}", headers=self.headers)
        self.assertEqual(res_get.status_code, 200)
        data = res_get.json()
        self.assertGreater(len(data["anomalies"]), 0)
        
        target_anom = data["anomalies"][0]
        anom_id = target_anom["anomaly_id"]

        # 2. Update Review Status to 'Confirmed Anomaly' with working paper remark
        payload = {
            "status": "Confirmed Anomaly",
            "auditor_comment": "Verified with cashier book: cash payment was made without Rule 6DD declaration. Flagged for Form 3CD Clause 21(d)."
        }
        res_put = self.client.put(
            f"/api/anomalies/{self.eng_id}/review/{anom_id}",
            json=payload,
            headers=self.headers
        )
        self.assertEqual(res_put.status_code, 200)
        self.assertTrue(res_put.json()["success"])

        # 3. Generate In-Depth AI Working Paper Memorandum
        res_ai = self.client.post(
            f"/api/anomalies/{self.eng_id}/ai-explain/{anom_id}",
            headers=self.headers
        )
        self.assertEqual(res_ai.status_code, 200)
        ai_data = res_ai.json()
        self.assertIn("FINAUDITPRO — AUDIT WORKING PAPER & AI ANOMALY MEMORANDUM", ai_data["ai_memo"])
        self.assertIn("PROFESSIONAL AUDIT SAFEGUARD", ai_data["ai_memo"])
        self.assertIn("ACTIONABLE SUBSTANTIVE AUDIT PROCEDURES", ai_data["ai_memo"])

        # 4. Re-fetch and verify status & comment persistence
        res_check = self.client.get(f"/api/anomalies/{self.eng_id}", headers=self.headers)
        updated_anom = next(a for a in res_check.json()["anomalies"] if a["anomaly_id"] == anom_id)
        self.assertEqual(updated_anom["status"], "Confirmed Anomaly")
        self.assertEqual(updated_anom["auditor_comment"], payload["auditor_comment"])

        # 5. Download CSV Report
        res_csv = self.client.get(
            f"/api/anomalies/{self.eng_id}/report/download",
            headers=self.headers
        )
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn("text/csv", res_csv.headers.get("content-type", ""))
        self.assertIn("AI_Anomaly_Detection_Report", res_csv.headers.get("content-disposition", ""))
        self.assertIn("FinAuditPro - AI-Assisted Anomaly Detection Audit Report", res_csv.text)
        self.assertIn(anom_id, res_csv.text)

if __name__ == "__main__":
    unittest.main()
