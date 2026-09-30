import unittest
import time
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db_connection, init_db
from backend.app.auth import create_access_token

class TestComprehensiveDashboard(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        init_db()
        self.run_id = str(int(time.time()))[-4:]
        self.auditor_token = create_access_token(data={"sub": "auditor", "role": "Auditor", "id": 2})

    def test_01_dashboard_summary_stats_cards(self):
        """Test that summary-stats returns all 6 required top card metrics."""
        res = self.client.get(
            "/api/engagements/dashboard/summary-stats",
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        # 6 Top Cards Verification
        self.assertIn("active_clients_count", data)
        self.assertIn("active_engagements_count", data)
        self.assertIn("open_findings_count", data)
        self.assertIn("high_risk_findings_count", data)
        self.assertIn("unmatched_transactions_count", data)
        self.assertIn("pending_reviews_count", data)

        self.assertIsInstance(data["active_clients_count"], int)
        self.assertIsInstance(data["active_engagements_count"], int)
        self.assertIsInstance(data["open_findings_count"], int)
        self.assertIsInstance(data["high_risk_findings_count"], int)
        self.assertIsInstance(data["unmatched_transactions_count"], int)
        self.assertIsInstance(data["pending_reviews_count"], int)

    def test_02_comprehensive_dashboard_structure(self):
        """Test comprehensive dashboard endpoint returning all 7 main sections and real DB charts."""
        res = self.client.get(
            "/api/engagements/dashboard/comprehensive?engagement_id=1",
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        dash = res.json()

        # 1. Top Cards
        self.assertIn("top_cards", dash)
        top = dash["top_cards"]
        self.assertIn("active_clients_count", top)
        self.assertIn("active_engagements_count", top)
        self.assertIn("open_findings_count", top)
        self.assertIn("high_risk_findings_count", top)
        self.assertIn("unmatched_transactions_count", top)
        self.assertIn("pending_reviews_count", top)

        # 2. Section 1: Engagement Overview
        self.assertIn("engagement_overview", dash)
        eng_ov = dash["engagement_overview"]
        self.assertIn("engagement", eng_ov)
        self.assertIn("total_files", eng_ov)
        self.assertIn("total_transactions", eng_ov)
        self.assertIn("total_debit_turnover", eng_ov)
        self.assertIn("total_credit_turnover", eng_ov)
        self.assertIn("total_turnover_examined", eng_ov)

        # 3. Section 2: Risk Overview & Severity / Area Distribution
        self.assertIn("risk_overview", dash)
        risk = dash["risk_overview"]
        self.assertIn("severity_counts", risk)
        self.assertIn("CRITICAL", risk["severity_counts"])
        self.assertIn("HIGH", risk["severity_counts"])
        self.assertIn("MEDIUM", risk["severity_counts"])
        self.assertIn("LOW", risk["severity_counts"])
        self.assertIn("engine_counts", risk)
        self.assertIn("area_counts", risk)
        self.assertIn("average_risk_score", risk)
        self.assertIn("risk_posture", risk)

        # 4. Section 3: Recent Findings
        self.assertIn("recent_findings", dash)
        findings = dash["recent_findings"]
        self.assertIsInstance(findings, list)
        if len(findings) > 0:
            f = findings[0]
            self.assertIn("id", f)
            self.assertIn("finding_code", f)
            self.assertIn("title", f)
            self.assertIn("severity", f)

        # 5. Section 4: Reconciliation Status
        self.assertIn("reconciliation_status", dash)
        recon = dash["reconciliation_status"]
        self.assertIn("matched_items", recon)
        self.assertIn("unmatched_bank_items", recon)
        self.assertIn("unmatched_book_items", recon)
        self.assertIn("amount_mismatches", recon)
        self.assertIn("reconciliations", recon)

        # 6. Section 5: Anomaly Summary (Benford & ML)
        self.assertIn("anomaly_summary", dash)
        anomaly = dash["anomaly_summary"]
        self.assertIn("benford_status", anomaly)
        self.assertIn("benford_mad", anomaly)
        self.assertIn("benford_digits", anomaly)
        self.assertEqual(len(anomaly["benford_digits"]), 9) # Digits 1 to 9
        self.assertIn("ml_outliers_count", anomaly)
        self.assertIn("round_sum_count", anomaly)
        self.assertIn("weekend_count", anomaly)

        # 7. Section 6: YoY Summary
        self.assertIn("yoy_summary", dash)
        self.assertIsInstance(dash["yoy_summary"], list)

        # 8. Section 7: Checklist Progress
        self.assertIn("checklist_progress", dash)
        chk = dash["checklist_progress"]
        self.assertIn("completion_pct", chk)
        self.assertIn("completed_count", chk)
        self.assertIn("category_progress", chk)

        # 9. Monthly Trends (Volume & Value)
        self.assertIn("monthly_trends", dash)
        trends = dash["monthly_trends"]
        self.assertIsInstance(trends, list)
        if len(trends) > 0:
            m = trends[0]
            self.assertIn("month", m)
            self.assertIn("month_label", m)
            self.assertIn("transaction_count", m)
            self.assertIn("total_value", m)

    def test_03_drill_down_consistency_with_database(self):
        """Test that numbers on the dashboard match 100% with direct SQLite database queries."""
        conn = get_db_connection()
        eng_id = 1
        
        # Verify transaction count and turnover
        db_tx = conn.execute("SELECT COUNT(*) as c, SUM(debit) as deb, SUM(credit) as cred FROM transactions WHERE engagement_id = ?", (eng_id,)).fetchone()
        
        # Verify findings counts
        db_findings_crit = conn.execute("SELECT COUNT(*) as c FROM audit_findings WHERE engagement_id = ? AND severity = 'CRITICAL'", (eng_id,)).fetchone()["c"]
        db_findings_high = conn.execute("SELECT COUNT(*) as c FROM audit_findings WHERE engagement_id = ? AND severity = 'HIGH'", (eng_id,)).fetchone()["c"]
        conn.close()

        res = self.client.get(
            f"/api/engagements/dashboard/comprehensive?engagement_id={eng_id}",
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        dash = res.json()

        self.assertEqual(dash["engagement_overview"]["total_transactions"], db_tx["c"])
        self.assertEqual(dash["risk_overview"]["severity_counts"]["CRITICAL"], db_findings_crit)
        self.assertEqual(dash["risk_overview"]["severity_counts"]["HIGH"], db_findings_high)

if __name__ == "__main__":
    unittest.main()
