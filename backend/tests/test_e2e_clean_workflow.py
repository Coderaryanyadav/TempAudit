import os
import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db

class TestE2ECleanWorkflow(unittest.TestCase):
    def setUp(self):
        # Reset to clean database
        if os.path.exists("backend/finauditpro.db"):
            try:
                os.remove("backend/finauditpro.db")
            except Exception:
                pass
        init_db()
        self.client = TestClient(app)

    def test_complete_clean_audit_workflow(self):
        # 1. Login with initial admin credentials
        res = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(res.status_code, 200)
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Check Empty Dashboard (0 clients, 0 findings, 0 transactions)
        dash = self.client.get("/api/engagements/dashboard/comprehensive", headers=headers).json()
        self.assertEqual(dash["top_cards"]["active_clients_count"], 0)
        self.assertEqual(dash["top_cards"]["open_findings_count"], 0)

        # 3. Create Client & Engagement
        c_res = self.client.post(
            "/api/clients",
            json={
                "name": "Apex Engineering Pvt Ltd",
                "pan": "AABCA1234D",
                "gstin": "27AABCA1234D1ZP",
                "entity_type": "Private Limited Company"
            },
            headers=headers
        )
        self.assertEqual(c_res.status_code, 200)
        client_id = c_res.json()["id"]

        e_res = self.client.post(
            "/api/engagements",
            json={
                "client_id": client_id,
                "title": "Statutory Audit FY 2024-25",
                "audit_type": "Statutory Audit",
                "financial_year": "2024-25"
            },
            headers=headers
        )
        self.assertEqual(e_res.status_code, 200)
        eng_id = e_res.json()["id"]

        # 4. Import Sample General Ledger
        with open("backend/sample_files/apex_general_ledger_fy2425.csv", "rb") as f:
            upload_res = self.client.post(
                "/api/import/upload",
                data={"engagement_id": str(eng_id), "data_category": "General Ledger"},
                files={"file": ("apex_gl.csv", f, "text/csv")},
                headers=headers
            )
        self.assertEqual(upload_res.status_code, 200)
        file_id = upload_res.json()["file_id"]

        map_res = self.client.post(
            "/api/import/apply-mapping",
            json={
                "file_id": file_id,
                "column_mapping": {
                    "date": "date",
                    "voucher_no": "voucher_no",
                    "invoice_no": "invoice_no",
                    "ledger": "ledger",
                    "account_group": "account_group",
                    "debit": "debit",
                    "credit": "credit",
                    "amount": "amount",
                    "party_name": "party_name",
                    "gstin": "gstin",
                    "description": "description"
                },
                "data_category": "General Ledger"
            },
            headers=headers
        )
        self.assertEqual(map_res.status_code, 200)

        # 5. Execute Anomaly & Statutory Rule Engine
        scan_res = self.client.post(f"/api/findings/run-engine/{eng_id}", headers=headers)
        self.assertEqual(scan_res.status_code, 200)
        findings_res = self.client.get(f"/api/findings/{eng_id}", headers=headers)
        self.assertEqual(findings_res.status_code, 200)
        self.assertGreater(len(findings_res.json()), 0)

        # 6. Check Trial Balance
        tb_res = self.client.get(f"/api/trial-balance/{eng_id}", headers=headers)
        self.assertEqual(tb_res.status_code, 200)
        self.assertGreater(tb_res.json().get("grand_total_debit", 0), 0)

        # 7. Check LM Studio Local AI Status
        ai_status = self.client.get("/api/ai-manager/status", headers=headers).json()
        self.assertEqual(ai_status["engine"], "LMStudio")
        self.assertEqual(ai_status["model_location"], "http://localhost:1234")

        # 8. Generate Master PDF Report
        rep_res = self.client.post(
            f"/api/reports/generate-pdf/{eng_id}",
            json={"report_type": "complete_audit_analysis"},
            headers=headers
        )
        self.assertEqual(rep_res.status_code, 200)
        self.assertIn("report_id", rep_res.json())

if __name__ == "__main__":
    unittest.main()
