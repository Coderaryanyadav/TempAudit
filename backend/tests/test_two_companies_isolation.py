"""
Cross-Company and Cross-Engagement Strict Isolation Tests
FinAuditPro - Test Suite

Validates complete separation between:
1. Aryan Fintech Pvt. Ltd. (ARYAN)
2. Hitansh Fintech Pvt. Ltd. (HITANSH)
"""

import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db_connection
from backend.app.auth import create_access_token
from test_data.seed import seed_test_database
from test_data.companies import ARYAN_COMPANY, HITANSH_COMPANY
from backend.app.services.local_ai_assistant_engine import LocalAIAssistantEngine

class TestTwoCompaniesIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.seeds = seed_test_database()
        cls.aryan_cy_id = cls.seeds["aryan"]["cy_engagement_id"]
        cls.hitansh_cy_id = cls.seeds["hitansh"]["cy_engagement_id"]

        # Tokens
        cls.admin_token = create_access_token({"sub": "admin", "role": "Admin", "id": 1, "token_version": 1})
        cls.auditor_token = create_access_token({"sub": "auditor", "role": "Auditor", "id": 2, "token_version": 1})
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}
        cls.auditor_headers = {"Authorization": f"Bearer {cls.auditor_token}"}

    def test_aryan_transactions_cannot_appear_in_hitansh(self):
        """Transactions for Aryan must never leak into Hitansh engagement queries."""
        res_aryan = self.client.get(f"/api/transactions?engagement_id={self.aryan_cy_id}", headers=self.admin_headers)
        self.assertEqual(res_aryan.status_code, 200)
        aryan_items = res_aryan.json()["items"]
        aryan_tx_ids = set(t["id"] for t in aryan_items)

        res_hitansh = self.client.get(f"/api/transactions?engagement_id={self.hitansh_cy_id}", headers=self.admin_headers)
        self.assertEqual(res_hitansh.status_code, 200)
        hitansh_items = res_hitansh.json()["items"]
        hitansh_tx_ids = set(t["id"] for t in hitansh_items)

        # Intersection must be completely empty
        self.assertEqual(len(aryan_tx_ids.intersection(hitansh_tx_ids)), 0)

        # Verify company-specific party names do not leak
        for t in hitansh_items:
            self.assertNotIn("Aryan", str(t.get("party_name", "")))
            self.assertNotIn("AF Enterprise", str(t.get("party_name", "")))

        for t in aryan_items:
            self.assertNotIn("Hitansh", str(t.get("party_name", "")))
            self.assertNotIn("HF Enterprise", str(t.get("party_name", "")))

    def test_aryan_findings_cannot_appear_in_hitansh(self):
        """Audit findings for Aryan must never appear in Hitansh."""
        res_a = self.client.get(f"/api/findings/{self.aryan_cy_id}", headers=self.admin_headers)
        self.assertEqual(res_a.status_code, 200)
        a_findings = res_a.json()

        res_h = self.client.get(f"/api/findings/{self.hitansh_cy_id}", headers=self.admin_headers)
        self.assertEqual(res_h.status_code, 200)
        h_findings = res_h.json()

        a_f_ids = set(f["id"] for f in a_findings)
        h_f_ids = set(f["id"] for f in h_findings)
        self.assertEqual(len(a_f_ids.intersection(h_f_ids)), 0)

        for f in a_findings:
            self.assertIn("[ARYAN]", f["title"])
            self.assertNotIn("HITANSH", f["title"])

        for f in h_findings:
            self.assertIn("[HITANSH]", f["title"])
            self.assertNotIn("ARYAN", f["title"])

    def test_aryan_working_papers_cannot_appear_in_hitansh(self):
        """Working papers must be strictly isolated between companies."""
        res_a = self.client.get(f"/api/working-papers/{self.aryan_cy_id}", headers=self.admin_headers)
        self.assertEqual(res_a.status_code, 200)
        a_wps = res_a.json()["working_papers"]

        res_h = self.client.get(f"/api/working-papers/{self.hitansh_cy_id}", headers=self.admin_headers)
        self.assertEqual(res_h.status_code, 200)
        h_wps = res_h.json()["working_papers"]

        a_wp_refs = set(w["wp_reference"] for w in a_wps)
        h_wp_refs = set(w["wp_reference"] for w in h_wps)
        self.assertEqual(len(a_wp_refs.intersection(h_wp_refs)), 0)

        for w in a_wps:
            self.assertIn("ARYAN", w["wp_reference"])
        for w in h_wps:
            self.assertIn("HITANSH", w["wp_reference"])

    def test_cross_company_working_paper_link_rejected(self):
        """Aryan working paper cannot link to a Hitansh transaction."""
        conn = get_db_connection()
        hitansh_tx = conn.execute("SELECT id FROM transactions WHERE engagement_id = ? LIMIT 1", (self.hitansh_cy_id,)).fetchone()
        conn.close()

        payload = {
            "engagement_id": self.aryan_cy_id,
            "wp_reference": "WP-TEST-ISOLATION-01",
            "title": "Cross-Company Link Test",
            "area": "Revenue",
            "description": "Test isolation",
            "linked_transactions": [hitansh_tx["id"]]
        }
        res = self.client.post(f"/api/working-papers?engagement_id={self.aryan_cy_id}", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("do not belong to this engagement", res.json()["detail"])

    def test_cross_company_custom_finding_rejected(self):
        """Aryan custom finding cannot reference a Hitansh transaction."""
        conn = get_db_connection()
        hitansh_tx = conn.execute("SELECT id FROM transactions WHERE engagement_id = ? LIMIT 1", (self.hitansh_cy_id,)).fetchone()
        conn.close()

        payload = {
            "engagement_id": self.aryan_cy_id,
            "title": "Cross-Company Finding Test",
            "severity": "HIGH",
            "risk_score": 80.0,
            "category": "Statutory Compliance",
            "description": "Attempting cross-company reference",
            "affected_records": [hitansh_tx["id"]]
        }
        res = self.client.post("/api/findings/custom", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("do not belong to this engagement", res.json()["detail"])

    def test_ai_scope_isolation_between_companies(self):
        """Local AI Assistant engine scopes data strictly to the requested company."""
        aryan_ai = LocalAIAssistantEngine(self.aryan_cy_id)
        hitansh_ai = LocalAIAssistantEngine(self.hitansh_cy_id)

        self.assertEqual(aryan_ai.client_info.get("name"), ARYAN_COMPANY["name"])
        self.assertEqual(hitansh_ai.client_info.get("name"), HITANSH_COMPANY["name"])

        # Check loaded transactions are strictly company-scoped
        for t in aryan_ai.transactions:
            self.assertEqual(t["engagement_id"], self.aryan_cy_id)
        for t in hitansh_ai.transactions:
            self.assertEqual(t["engagement_id"], self.hitansh_cy_id)

        # AI Query on Aryan
        res_ai_aryan = aryan_ai.process_query("Show me unusual transactions")
        self.assertIn("Aryan Fintech", res_ai_aryan.get("response", ""))
        self.assertNotIn("Hitansh", res_ai_aryan.get("response", ""))

        # AI Query on Hitansh
        res_ai_hitansh = hitansh_ai.process_query("Show me unusual transactions")
        self.assertIn("Hitansh Fintech", res_ai_hitansh.get("response", ""))
        self.assertNotIn("Aryan", res_ai_hitansh.get("response", ""))

    def test_staff_assignment_authorization_isolation(self):
        """Staff assigned to Aryan cannot access Hitansh, and Staff assigned to Hitansh cannot access Aryan."""
        staff_aryan_token = create_access_token({"sub": "staff_aryan", "role": "Audit Staff", "uid": 3, "token_version": 1})
        staff_hitansh_token = create_access_token({"sub": "staff_hitansh", "role": "Audit Staff", "uid": 5, "token_version": 1})
        
        h_aryan = {"Authorization": f"Bearer {staff_aryan_token}"}
        h_hitansh = {"Authorization": f"Bearer {staff_hitansh_token}"}

        # 1. Staff A accesses Aryan -> 200 OK
        res_a_aryan = self.client.get(f"/api/findings/{self.aryan_cy_id}", headers=h_aryan)
        self.assertEqual(res_a_aryan.status_code, 200)

        # 2. Staff A attempts to access Hitansh -> 403 Forbidden
        res_a_hitansh = self.client.get(f"/api/findings/{self.hitansh_cy_id}", headers=h_aryan)
        self.assertEqual(res_a_hitansh.status_code, 403)

        # 3. Staff B accesses Hitansh -> 200 OK
        res_b_hitansh = self.client.get(f"/api/findings/{self.hitansh_cy_id}", headers=h_hitansh)
        self.assertEqual(res_b_hitansh.status_code, 200)

        # 4. Staff B attempts to access Aryan -> 403 Forbidden
        res_b_aryan = self.client.get(f"/api/findings/{self.aryan_cy_id}", headers=h_hitansh)
        self.assertEqual(res_b_aryan.status_code, 403)

if __name__ == "__main__":
    unittest.main()
