"""High-impact regression tests for authentication and verified backup safety."""

import io
import os
import tarfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.auth import create_access_token
from backend.app.database import get_db_connection
from backend.app.main import app
from backend.app.routers.auth import _activation_token_is_expired
from backend.app.services.backup_service import BACKUP_DIR, BackupService

client = TestClient(app)


def _update_user(username: str, **values) -> None:
    allowed = {"status", "is_active", "activation_token", "activation_expires_at"}
    if set(values) - allowed:
        raise AssertionError("Unexpected test update field")
    conn = get_db_connection()
    try:
        assignments = ", ".join(f"{key} = ?" for key in values)
        conn.execute(
            f"UPDATE users SET {assignments} WHERE username = ?",
            (*values.values(), username),
        )
        conn.commit()
    finally:
        conn.close()


def test_activation_expiry_helper_fails_closed():
    assert _activation_token_is_expired(None) is True
    assert _activation_token_is_expired("not-a-timestamp") is True
    assert _activation_token_is_expired(
        (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    ) is True
    assert _activation_token_is_expired(
        (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    ) is False


def test_expired_activation_token_cannot_activate_account():
    token = "audit-expired-" + uuid.uuid4().hex
    _update_user(
        "auditor",
        status="INVITED",
        is_active=0,
        activation_token=token,
        activation_expires_at=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
    )
    try:
        response = client.post(
            "/api/auth/activate-user",
            json={"activation_token": token, "password": "StrongTestPassword2026!"},
        )
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()
    finally:
        _update_user(
            "auditor",
            status="ACTIVE",
            is_active=1,
            activation_token=None,
            activation_expires_at=None,
        )


def test_malformed_activation_expiry_is_not_reported_as_valid():
    token = "audit-malformed-" + uuid.uuid4().hex
    _update_user(
        "auditor",
        status="INVITED",
        is_active=0,
        activation_token=token,
        activation_expires_at="not-a-timestamp",
    )
    try:
        response = client.get(f"/api/auth/activation-info/{token}")
        assert response.status_code == 200
        assert response.json()["is_valid"] is False
    finally:
        _update_user(
            "auditor",
            status="ACTIVE",
            is_active=1,
            activation_token=None,
            activation_expires_at=None,
        )


def test_locked_account_cannot_login_even_if_is_active_is_true():
    _update_user("admin", status="LOCKED", is_active=1)
    try:
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 403
        assert "locked" in response.json()["detail"].lower()
    finally:
        _update_user("admin", status="ACTIVE", is_active=1)


def test_future_token_version_is_rejected():
    token = create_access_token({
        "sub": "admin",
        "role": "Admin",
        "uid": 1,
        "token_version": 999999,
    })
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_verified_backup_rejects_path_traversal(tmp_path):
    archive_path = tmp_path / "malicious.finpkg"
    escaped_name = "escaped-" + uuid.uuid4().hex + ".txt"
    escaped_path = os.path.join(BACKUP_DIR, escaped_name)

    def add_bytes(archive, name, payload):
        info = tarfile.TarInfo(name=name)
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    try:
        with tarfile.open(archive_path, mode="w:gz") as archive:
            add_bytes(archive, "manifest.json", b"{}")
            add_bytes(archive, "finauditpro.db", b"not-a-real-sqlite-database")
            add_bytes(archive, "../" + escaped_name, b"outside extraction directory")

        result = BackupService.validate_bundle(str(archive_path))
        assert result["valid"] is False
        assert "path traversal" in result["error"].lower()
        assert not os.path.exists(escaped_path)
    finally:
        if os.path.exists(escaped_path):
            os.remove(escaped_path)


def test_root_compose_requires_an_explicit_jwt_secret():
    project_root = Path(__file__).resolve().parents[2]
    compose = (project_root / "compose.yaml").read_text(encoding="utf-8")
    assert "FINAUDIT_SECRET_KEY: ${FINAUDIT_SECRET_KEY:?Set FINAUDIT_SECRET_KEY" in compose
    assert "c9d79e627e7813a37c8440ddc4d27f5a455c14243828a1c8f15499f1702d4e68" not in compose
