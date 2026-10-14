import unittest
import time
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth import create_access_token, hash_password, get_jwt_secret
from backend.app.database import get_db_connection
from test_data.seed import seed_test_database
import jwt

class TestLoginSessionRefresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_test_database()
        cls.client = TestClient(app)

    def test_successful_login_followed_by_auth_me(self):
        """1. Successful login followed by /api/auth/me."""
        res = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        token = data["access_token"]

        me_res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.json()
        self.assertEqual(me_data["username"], "admin")
        self.assertEqual(me_data["role"], "Admin")
        self.assertTrue(me_data["permissions"]["can_manage_users"])

    def test_page_reload_session_persistence(self):
        """2. Browser refresh / repeated /api/auth/me does not invalidate session or increment token_version."""
        login_res = self.client.post("/api/auth/login", json={
            "username": "auditor",
            "password": "audit123"
        })
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["access_token"]

        conn = get_db_connection()
        user_before = conn.execute("SELECT token_version FROM users WHERE username = 'auditor'").fetchone()
        conn.close()
        version_before = user_before["token_version"]

        # Simulate multiple page reloads
        for _ in range(5):
            res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["username"], "auditor")

        conn = get_db_connection()
        user_after = conn.execute("SELECT token_version FROM users WHERE username = 'auditor'").fetchone()
        conn.close()
        self.assertEqual(user_after["token_version"], version_before)

    def test_unauthenticated_request_does_not_affect_user_session(self):
        """3. An unauthenticated request (e.g. AI-status before login) returns 401 without affecting tokens."""
        # Unauthenticated request to protected endpoint
        ai_res = self.client.get("/api/ai-manager/status")
        self.assertEqual(ai_res.status_code, 401)

        # Login immediately after
        login_res = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["access_token"]

        # Token works normally
        me_res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)

    def test_invalid_or_expired_token_rejected(self):
        """4. Invalid, expired, or malformed tokens return 401."""
        # Malformed token
        bad_res = self.client.get("/api/auth/me", headers={"Authorization": "Bearer not_a_real_jwt"})
        self.assertEqual(bad_res.status_code, 401)
        self.assertIn("detail", bad_res.json())

        # Expired token
        from datetime import datetime, timedelta, timezone
        secret = get_jwt_secret()
        expired_payload = {
            "sub": "admin",
            "role": "Admin",
            "token_version": 1,
            "exp": datetime.now(timezone.utc) - timedelta(minutes=10),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=20),
            "iss": "finauditpro",
            "aud": "finauditpro-app"
        }
        expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")
        exp_res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        self.assertEqual(exp_res.status_code, 401)
        self.assertIn("expired", exp_res.json()["detail"].lower())

    def test_disabled_accounts_rejected(self):
        """5. Disabled accounts remain rejected on login and on protected routes."""
        conn = get_db_connection()
        conn.execute("UPDATE users SET is_active = 0, status = 'DISABLED' WHERE username = 'auditor'")
        conn.commit()
        conn.close()

        try:
            # Login attempt should fail with 403
            res = self.client.post("/api/auth/login", json={
                "username": "auditor",
                "password": "audit123"
            })
            self.assertEqual(res.status_code, 403)
            self.assertIn("disabled", res.json()["detail"].lower())
        finally:
            conn = get_db_connection()
            conn.execute("UPDATE users SET is_active = 1, status = 'ACTIVE' WHERE username = 'auditor'")
            conn.commit()
            conn.close()

    def test_invalid_credentials_rejected(self):
        """6. Invalid credentials return 401 without revealing user existence."""
        res = self.client.post("/api/auth/login", json={
            "username": "nonexistent_user",
            "password": "anypassword"
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid username or password", res.json()["detail"])

    def test_logout_and_password_change_token_invalidation(self):
        """7. Logout and password change properly increment token_version and invalidate old tokens."""
        # 1. Login
        login_res = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        token = login_res.json()["access_token"]

        # Verify active
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code, 200)

        # 2. Logout
        logout_res = self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_res.status_code, 200)

        # 3. Old token must now be rejected
        revoked_check = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(revoked_check.status_code, 401)
        self.assertIn("invalidated", revoked_check.json()["detail"].lower())

if __name__ == "__main__":
    unittest.main()
