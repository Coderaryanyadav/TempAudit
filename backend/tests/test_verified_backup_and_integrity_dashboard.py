import os
import sqlite3
import pytest
from backend.app.services.backup_service import BackupService
from backend.app.services.integrity_checker import SystemIntegrityChecker
from backend.app.database import init_db, DB_PATH

def test_system_integrity_diagnostics():
    """Verify integrity diagnostic checks return comprehensive status."""
    init_db()
    report = SystemIntegrityChecker.run_all_checks()

    assert "overall_status" in report
    assert report["overall_status"] in ("PASS", "WARNING")
    assert "components" in report
    assert "database" in report["components"]
    assert "foreign_keys" in report["components"]
    assert "schema" in report["components"]
    assert "audit_chain" in report["components"]
    assert "evidence" in report["components"]

def test_verified_backup_bundle_lifecycle(tmp_path):
    """Verify manifest creation, bundle validation, and safe restoration."""
    init_db()

    # 1. Create bundle
    bundle_path, manifest = BackupService.create_verified_bundle(created_by="AdminAutomatedTest")
    assert os.path.exists(bundle_path)
    assert manifest["backup_version"] == 1
    assert manifest["database_sha256"] != ""
    assert manifest["schema_version"] != ""

    # 2. Validate bundle before restore
    val = BackupService.validate_bundle(bundle_path)
    assert val["valid"] is True
    assert val["manifest"]["database_sha256"] == manifest["database_sha256"]

    # 3. Restore verified bundle
    res = BackupService.restore_verified_bundle(bundle_path)
    assert res["status"] == "SUCCESS"
    assert res["safety_snapshot"] is not None

    # Clean up bundle
    if os.path.exists(bundle_path):
        os.remove(bundle_path)
