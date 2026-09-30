import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db_connection, init_db
from backend.app.auth import create_access_token
from backend.app.services.local_ai_provider import (
    sanitize_audit_text,
    LocalAIModelManager,
    LMStudioProvider,
    BuiltinDeterministicAIProvider
)

class TestOfflineAIModelManager(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        init_db()
        self.auditor_token = create_access_token(data={"sub": "admin", "role": "Admin", "id": 1})

    def test_01_privacy_guard_data_sanitizer(self):
        """Test strict redaction of PAN, GSTIN, Bank Accounts, Phone, Email, and Client Names."""
        raw_text = (
            "Verified statutory payment by Apex Engineering & Logistics Pvt Ltd "
            "with PAN AAAFE1234G and GSTIN 27AAAFE1234G1Z8. "
            "Disbursement made from HDFC Bank A/c 50200012345678 IFSC HDFC0000123 "
            "contact partner at accounts@apexengineering.com or +91 98200 12345."
        )

        sanitized, stats = sanitize_audit_text(raw_text, client_name="Apex Engineering & Logistics Pvt Ltd")

        # Verify that all sensitive items are redacted
        self.assertNotIn("AAAFE1234G", sanitized)
        self.assertNotIn("27AAAFE1234G1Z8", sanitized)
        self.assertNotIn("50200012345678", sanitized)
        self.assertNotIn("accounts@apexengineering.com", sanitized)
        self.assertNotIn("Apex Engineering & Logistics Pvt Ltd", sanitized)

        self.assertIn("[PAN_REDACTED]", sanitized)
        self.assertIn("[GSTIN_REDACTED]", sanitized)
        self.assertIn("[BANK_ACCT_REDACTED]", sanitized)
        self.assertIn("[ENTITY_UNDER_AUDIT]", sanitized)
        self.assertIn("[EMAIL_REDACTED]", sanitized)

        self.assertEqual(stats["pan"], 1)
        self.assertEqual(stats["gstin"], 1)
        self.assertEqual(stats["bank_account"], 1)
        self.assertEqual(stats["client_name"], 1)

    def test_02_get_ai_manager_status(self):
        """Test retrieval of Local AI Model Manager status and LM Studio configuration."""
        res = self.client.get("/api/ai-manager/status", headers={"Authorization": f"Bearer {self.auditor_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("is_enabled", data)
        self.assertIn("engine", data)
        self.assertIn("model_name", data)
        self.assertIn("model_status", data)
        self.assertIn("model_location", data)
        self.assertIn("ram_vram_requirement", data)
        self.assertIn("context_size", data)
        self.assertIn("temperature", data)
        self.assertIn("offline_mode_active", data)
        self.assertIn("fallback_notice", data)
        self.assertEqual(data["offline_mode_active"], True)
        self.assertIn("available_engines", data)

    def test_03_update_ai_settings_and_audit_logging(self):
        """Test saving LM Studio settings and logging to immutable audit trail."""
        update_payload = {
            "is_enabled": True,
            "engine": "LMStudio",
            "model_name": "meta-llama-3-8b-instruct",
            "model_location": "http://localhost:1234",
            "ram_vram_requirement": "8 GB RAM / 4 GB VRAM",
            "context_size": 4096,
            "temperature": 0.15
        }

        res = self.client.post(
            "/api/ai-manager/settings",
            json=update_payload,
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        saved = res.json()
        self.assertEqual(saved["engine"], "LMStudio")
        self.assertEqual(saved["model_name"], "meta-llama-3-8b-instruct")
        self.assertEqual(saved["context_size"], 4096)
        self.assertEqual(saved["temperature"], 0.15)

        # Verify audit log entry
        conn = get_db_connection()
        log = conn.execute("""
            SELECT * FROM audit_logs 
            WHERE module = 'AI_MODEL_MANAGER' AND action = 'SETTINGS_CHANGE'
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        conn.close()

        self.assertIsNotNone(log)
        self.assertEqual(log["record_id"], "local_ai_settings")

    def test_04_test_connection_and_fallback_guarantee(self):
        """Test live connection check and verify deterministic fallback if LM Studio is offline."""
        res = self.client.post("/api/ai-manager/test-connection", headers={"Authorization": f"Bearer {self.auditor_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("is_available", data)
        self.assertIn("status_message", data)
        self.assertIn("latency_ms", data)
        self.assertIn("available_models", data)

    def test_05_safe_generation_with_deterministic_fallback(self):
        """Test safe prompt execution falls back gracefully to built-in reasoner without error."""
        gen_payload = {
            "prompt": "Evaluate Section 40A(3) cash expense for PAN AAAFE1234G invoice of Rs 45,000",
            "system_prompt": "You are an ICAI Statutory Auditor.",
            "client_name": "Apex Engineering"
        }
        res = self.client.post("/api/ai-manager/generate", json=gen_payload, headers={"Authorization": f"Bearer {self.auditor_token}"})
        self.assertEqual(res.status_code, 200)
        result = res.json()

        self.assertIn("text", result)
        self.assertIn("redaction_stats", result)
        self.assertIn("success", result)
        self.assertTrue(result["success"])
        # Verify prompt was sanitized
        self.assertGreaterEqual(result["redaction_stats"].get("pan", 0), 1)

    def test_06_builtin_deterministic_reasoner_guarantee(self):
        """Test that the built-in deterministic provider operates completely offline with zero daemons."""
        provider = BuiltinDeterministicAIProvider()
        health, msg, lat = provider.check_health()
        self.assertTrue(health)
        self.assertIn("100% offline", msg)

        res = provider.generate("Summarize findings for cash breach")
        self.assertTrue(res["success"])
        self.assertIn("Section 40A(3)", res["text"])

    def test_07_lm_studio_provider_interface(self):
        """Test LMStudioProvider class initialization and interface methods."""
        provider = LMStudioProvider(endpoint="http://localhost:1234", model_name="test-model")
        self.assertEqual(provider.get_engine_name(), "LM Studio (Local Server)")
        models = provider.get_available_models()
        self.assertIsInstance(models, list)

    def test_08_test_ai_prompt_endpoint(self):
        """Test /api/ai-manager/test-ai endpoint."""
        res = self.client.post("/api/ai-manager/test-ai", json={"prompt": "Verify audit assistant"}, headers={"Authorization": f"Bearer {self.auditor_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("response", data)

if __name__ == "__main__":
    unittest.main()
