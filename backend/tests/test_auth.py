import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth import hash_password, verify_password
from test_data.seed import seed_test_database

class TestUserManagementAndAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_test_database()
        cls.client = TestClient(app)

    def test_password_hashing_and_verification(self):
        pwd = "AuditSecretPassword2026!"
        pwd_hash = hash_password(pwd)
        self.assertTrue(verify_password(pwd, pwd_hash))
        self.assertFalse(verify_password("WrongPassword123", pwd_hash))

    def test_login_success_and_last_login_tracking(self):
        res = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["username"], "admin")
        self.assertEqual(data["user"]["role"], "Admin")
        self.assertIsNotNone(data["user"]["last_login"])

    def test_login_failure_wrong_password(self):
        res = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wrong_password_xyz"
        })
        self.assertEqual(res.status_code, 401)

    def test_get_me_profile_and_permissions(self):
        # Login as Admin
        login_res = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        token = login_res.json()["access_token"]
        
        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["username"], "admin")
        self.assertTrue(data["permissions"]["can_manage_users"])

    def test_auditor_permissions(self):
        # Login as Auditor
        login_res = self.client.post("/api/auth/login", json={
            "username": "auditor",
            "password": "audit123"
        })
        token = login_res.json()["access_token"]
        
        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["role"], "Auditor")
        self.assertFalse(data["permissions"]["can_manage_users"])
        self.assertTrue(data["permissions"]["can_create_clients"])

    def test_admin_create_and_manage_user_lifecycle(self):
        # Login as Admin
        login_res = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        admin_token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. Create User
        import uuid
        uid_suffix = uuid.uuid4().hex[:6]
        new_username = f"user_{uid_suffix}"
        create_res = self.client.post("/api/auth/users", json={
            "username": new_username,
            "full_name": "Vikram Joshi (Staff)",
            "email": f"vikram_{uid_suffix}@testaudit.in",
            "phone": "+91 98200 99887",
            "role": "Audit Staff",
            "password": "initialPassword123"
        }, headers=headers)
        self.assertEqual(create_res.status_code, 200)
        user_id = create_res.json()["user_id"]

        # 2. Login as new user
        user_login = self.client.post("/api/auth/login", json={
            "username": new_username,
            "password": "initialPassword123"
        })
        self.assertEqual(user_login.status_code, 200)
        user_token = user_login.json()["access_token"]

        # 3. Change password
        chg_pwd = self.client.post("/api/auth/change-password", json={
            "old_password": "initialPassword123",
            "new_password": "newSecurePassword456"
        }, headers={"Authorization": f"Bearer {user_token}"})
        self.assertEqual(chg_pwd.status_code, 200)

        # 4. Login with updated password
        user_relogin = self.client.post("/api/auth/login", json={
            "username": new_username,
            "password": "newSecurePassword456"
        })
        self.assertEqual(user_relogin.status_code, 200)

        # 5. Admin changes role to Auditor
        role_upd = self.client.put(f"/api/auth/users/{user_id}", json={
            "role": "Auditor"
        }, headers=headers)
        self.assertEqual(role_upd.status_code, 200)

        # 6. Admin disables account
        disable_res = self.client.put(f"/api/auth/users/{user_id}/status", json={
            "is_active": False
        }, headers=headers)
        self.assertEqual(disable_res.status_code, 200)

        # 7. Disabled user should fail login
        disabled_login = self.client.post("/api/auth/login", json={
            "username": new_username,
            "password": "newSecurePassword456"
        })
        self.assertEqual(disabled_login.status_code, 403)

        # 8. Admin cannot disable own account
        self_disable = self.client.put("/api/auth/users/1/status", json={
            "is_active": False
        }, headers=headers)
        self.assertEqual(self_disable.status_code, 400)

    def test_activation_token_lifecycle_and_expiry(self):
        """Verifies expired, malformed, valid, and reused activation tokens."""
        from datetime import datetime, timedelta
        from backend.app.database import get_db_connection
        conn = get_db_connection()
        now = datetime.now()
        expired_ts = (now - timedelta(hours=2)).isoformat()
        future_ts = (now + timedelta(hours=24)).isoformat()

        # 1. User with expired activation token
        conn.execute("""
            INSERT INTO users (username, email, full_name, role, password_hash, status, is_active, activation_token, activation_expires_at, created_at)
            VALUES ('expired_user', 'expired@audit.com', 'Expired User', 'Auditor', 'temp_hash', 'INVITED', 0, 'TOKEN_EXPIRED_123', ?, ?)
        """, (expired_ts, now.isoformat()))

        # 2. User with malformed expiry timestamp
        conn.execute("""
            INSERT INTO users (username, email, full_name, role, password_hash, status, is_active, activation_token, activation_expires_at, created_at)
            VALUES ('malformed_user', 'malformed@audit.com', 'Malformed User', 'Auditor', 'temp_hash', 'INVITED', 0, 'TOKEN_MALFORMED_456', 'NOT_AN_ISO_DATE', ?)
        """, (now.isoformat(),))

        # 3. User with valid activation token
        conn.execute("""
            INSERT INTO users (username, email, full_name, role, password_hash, status, is_active, activation_token, activation_expires_at, created_at)
            VALUES ('valid_user', 'valid@audit.com', 'Valid User', 'Auditor', 'temp_hash', 'INVITED', 0, 'TOKEN_VALID_789', ?, ?)
        """, (future_ts, now.isoformat()))
        conn.commit()
        conn.close()

        # Test A: Verify endpoint recognizes expired token
        v_exp = self.client.get("/api/auth/activation-info/TOKEN_EXPIRED_123")
        self.assertEqual(v_exp.status_code, 200)
        self.assertTrue(v_exp.json()["expired"])
        self.assertFalse(v_exp.json()["is_valid"])

        # Test B: Activate with expired token must be rejected with 400
        act_exp = self.client.post("/api/auth/activate-user", json={
            "activation_token": "TOKEN_EXPIRED_123",
            "password": "ValidPassword123!"
        })
        self.assertEqual(act_exp.status_code, 400)
        self.assertIn("Activation token has expired", act_exp.json()["detail"])

        # Test C: Activate with malformed expiry must be rejected with 400
        act_mal = self.client.post("/api/auth/activate-user", json={
            "activation_token": "TOKEN_MALFORMED_456",
            "password": "ValidPassword123!"
        })
        self.assertEqual(act_mal.status_code, 400)
        self.assertIn("invalid expiry metadata", act_mal.json()["detail"])

        # Test D: Activate with valid token must succeed
        act_valid = self.client.post("/api/auth/activate-user", json={
            "activation_token": "TOKEN_VALID_789",
            "password": "ValidPassword123!"
        })
        self.assertEqual(act_valid.status_code, 200)
        self.assertIn("access_token", act_valid.json())

        # Test E: Reusing the token must fail with 404 (token invalidated)
        act_reuse = self.client.post("/api/auth/activate-user", json={
            "activation_token": "TOKEN_VALID_789",
            "password": "ValidPassword123!"
        })
        self.assertEqual(act_reuse.status_code, 404)

if __name__ == "__main__":
    unittest.main()
