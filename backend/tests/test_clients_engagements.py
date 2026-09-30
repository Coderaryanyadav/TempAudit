import unittest
import os
import time
import sqlite3
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db_connection, init_db
from backend.app.auth import create_access_token

class TestClientEngagementManagement(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        init_db()
        
        # Unique identifier for this test run
        self.run_id = str(int(time.time()))[-4:]
        
        # Create admin token and auditor token
        self.admin_token = create_access_token(data={"sub": "admin", "role": "Admin", "id": 1})
        self.auditor_token = create_access_token(data={"sub": "auditor", "role": "Auditor", "id": 2})
        self.staff_token = create_access_token(data={"sub": "staff", "role": "Audit Staff", "id": 3})

    def test_01_create_client_with_validations(self):
        """Test client creation with PAN and GSTIN format validations."""
        # 1. Invalid PAN format
        bad_pan_payload = {
            "name": "Invalid PAN Enterprise",
            "entity_type": "Proprietorship",
            "pan": "INVALID123",
            "financial_year": "2024-25"
        }
        res = self.client.post(
            "/api/clients",
            json=bad_pan_payload,
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid PAN format", res.json()["detail"])

        # 2. Invalid GSTIN format
        bad_gstin_payload = {
            "name": "Invalid GSTIN Enterprise",
            "entity_type": "LLP",
            "pan": "AAACL1234F",
            "gstin": "27AAACL1234F",  # Too short
            "financial_year": "2024-25"
        }
        res = self.client.post(
            "/api/clients",
            json=bad_gstin_payload,
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid GSTIN format", res.json()["detail"])

        # 3. Valid Client Creation
        unique_pan = f"AAAFE{self.run_id}G"
        unique_gstin = f"27AAAFE{self.run_id}G1Z8"
        valid_payload = {
            "name": f"Apex Engineering LLP {self.run_id}",
            "entity_type": "LLP",
            "pan": unique_pan,
            "gstin": unique_gstin,
            "industry": "Manufacturing",
            "financial_year": "2024-25",
            "contact_person": "Vikram Mehta",
            "email": "v.mehta@apexeng.in",
            "phone": "9876543210",
            "address": "402 Industrial Area, Pune, Maharashtra 411018",
            "notes": "Plant and Machinery additions in Q3."
        }
        res = self.client.post(
            "/api/clients",
            json=valid_payload,
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        client_id = res.json()["id"]
        self.assertTrue(client_id > 0)

        # 4. Duplicate PAN validation
        res_dup = self.client.post(
            "/api/clients",
            json=valid_payload,
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res_dup.status_code, 400)
        self.assertIn("already exists", res_dup.json()["detail"])

    def test_02_client_search_and_filter(self):
        """Test search and filter capabilities across entity types and industries."""
        # Create a specific search target (5 letters + 4 digits + 1 letter)
        pan_target = f"SRCHA{self.run_id}A"
        self.client.post(
            "/api/clients",
            json={
                "name": f"Search Target Pvt Ltd {self.run_id}",
                "entity_type": "LLP",
                "pan": pan_target,
                "industry": "Healthcare & Pharma",
                "financial_year": "2024-25"
            },
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )

        # Search by PAN
        res = self.client.get(
            f"/api/clients?search={pan_target}",
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        clients = res.json()
        self.assertTrue(any(c["pan"] == pan_target for c in clients))

        # Filter by Entity Type
        res_entity = self.client.get(
            "/api/clients?entity_type=LLP",
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res_entity.status_code, 200)
        self.assertTrue(all(c["entity_type"] == "LLP" for c in res_entity.json()))

    def test_03_create_and_manage_engagement(self):
        """Test engagement creation, isolation, and status lifecycle."""
        # Get or create client
        clients = self.client.get("/api/clients", headers={"Authorization": f"Bearer {self.auditor_token}"}).json()
        client_id = clients[0]["id"]

        # Create Engagement
        eng_payload = {
            "client_id": client_id,
            "title": "Tax Audit FY 2024-25",
            "audit_type": "Tax Audit",
            "financial_year": "2024-25",
            "period_start": "2024-04-01",
            "period_end": "2025-03-31",
            "lead_auditor_id": 2,
            "assigned_staff_id": 3,
            "status": "In Progress",
            "notes": "Form 3CD clauses 13, 21, 26, 34 focus."
        }
        res = self.client.post(
            "/api/engagements",
            json=eng_payload,
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        eng_id = res.json()["id"]

        # Retrieve Engagement
        detail = self.client.get(
            f"/api/engagements/{eng_id}",
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        ).json()
        self.assertEqual(detail["title"], "Tax Audit FY 2024-25")
        self.assertEqual(detail["status"], "In Progress")

        # Update Status to Under Review
        status_res = self.client.put(
            f"/api/engagements/{eng_id}/status?status=Under Review",
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(status_res.status_code, 200)
        self.assertEqual(status_res.json()["new_status"], "Under Review")

    def test_04_duplicate_engagement_structure(self):
        """Test duplication of audit structure into a new financial year with data isolation."""
        # Get existing engagements
        engs = self.client.get("/api/engagements", headers={"Authorization": f"Bearer {self.auditor_token}"}).json()
        self.assertTrue(len(engs) > 0)
        source_eng_id = engs[0]["id"]

        dup_payload = {
            "source_engagement_id": source_eng_id,
            "target_financial_year": "2025-26",
            "title": f"Statutory Audit FY 2025-26 {self.run_id}",
            "copy_checklists": True,
            "copy_working_paper_templates": True
        }
        res = self.client.post(
            "/api/engagements/duplicate",
            json=dup_payload,
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        new_eng_id = data["new_engagement_id"]
        self.assertEqual(data["financial_year"], "2025-26")

        # Verify new engagement details
        new_eng = self.client.get(
            f"/api/engagements/{new_eng_id}",
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        ).json()
        self.assertEqual(new_eng["financial_year"], "2025-26")
        self.assertEqual(new_eng["status"], "Draft")

        # Verify data isolation: New engagement must have 0 transactions
        conn = get_db_connection()
        tx_count = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE engagement_id = ?", (new_eng_id,)).fetchone()["c"]
        self.assertEqual(tx_count, 0)

        # Checklists must be cloned
        chk_count = conn.execute("SELECT COUNT(*) as c FROM audit_checklists WHERE engagement_id = ?", (new_eng_id,)).fetchone()["c"]
        self.assertTrue(chk_count > 0)
        # All cloned checklists must be reset to 'Pending'
        non_pending = conn.execute("SELECT COUNT(*) as c FROM audit_checklists WHERE engagement_id = ? AND status != 'Pending'", (new_eng_id,)).fetchone()["c"]
        self.assertEqual(non_pending, 0)
        conn.close()

    def test_05_dashboard_summary_metrics(self):
        """Test 5 core dashboard metric cards calculation."""
        res = self.client.get(
            "/api/engagements/dashboard/summary-stats",
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        stats = res.json()

        # Check for presence of all 5 required dashboard metrics
        self.assertIn("active_engagements_count", stats)
        self.assertIn("pending_reviews_count", stats)
        self.assertIn("open_findings_count", stats)
        self.assertIn("high_risk_findings_count", stats)
        self.assertIn("completed_engagements_count", stats)

        self.assertIsInstance(stats["active_engagements_count"], int)
        self.assertIsInstance(stats["pending_reviews_count"], int)
        self.assertIsInstance(stats["open_findings_count"], int)
        self.assertIsInstance(stats["high_risk_findings_count"], int)
        self.assertIsInstance(stats["completed_engagements_count"], int)

    def test_06_client_multi_year_history_timeline(self):
        """Test multi-year history timeline retrieval for a client."""
        clients = self.client.get("/api/clients", headers={"Authorization": f"Bearer {self.auditor_token}"}).json()
        client_id = clients[0]["id"]

        res = self.client.get(
            f"/api/clients/{client_id}/history",
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        history = res.json()
        self.assertIn("client", history)
        self.assertIn("timeline", history)
        self.assertIn("total_engagements", history)
        self.assertTrue(isinstance(history["timeline"], list))

if __name__ == "__main__":
    unittest.main()
