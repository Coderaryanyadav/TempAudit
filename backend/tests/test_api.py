import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from test_data.seed import seed_test_database

class TestFinAuditAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_test_database()
        cls.client = TestClient(app)
        login_res = cls.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        token = login_res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {token}"}

    def test_health_endpoint(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["mode"], "offline")

    def test_clients_list(self):
        res = self.client.get("/api/clients", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)
        self.assertGreater(len(res.json()), 0)

    def test_engagements_list(self):
        res = self.client.get("/api/engagements", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)
        self.assertGreater(len(res.json()), 0)

    def test_trial_balance(self):
        res = self.client.get("/api/trial-balance/1", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("grand_total_debit", data)
        self.assertIn("ledgers", data)

    def test_run_audit_engine(self):
        res = self.client.post("/api/findings/run-engine/1", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertGreater(data["findings_count"], 0)

    def test_local_ai_assistant_query(self):
        res = self.client.post("/api/assistant/query", json={
            "engagement_id": 1,
            "query": "Show large cash transactions above Section 40A(3) limit"
        }, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("response", data)
        self.assertIn("Section 40A(3)", data["response"])

    def test_pdf_report_generation(self):
        res = self.client.post("/api/reports/generate-pdf/1", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("download_url", data)

if __name__ == "__main__":
    unittest.main()
