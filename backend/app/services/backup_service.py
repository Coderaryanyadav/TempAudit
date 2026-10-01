import os
import json
import tarfile
import hashlib
import sqlite3
import shutil
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from backend.app.database import DB_PATH, get_db_connection
from backend.migrations.runner import get_migration_status

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

def compute_file_sha256(filepath: str) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

class BackupService:
    """
    Verified Manifest-Driven Backup & Restore Engine.
    Bundles SQLite database, evidence files, and cryptographic manifest with SHA-256 validation.
    """

    @classmethod
    def create_verified_bundle(cls, created_by: str = "Admin") -> Tuple[str, Dict[str, Any]]:
        """
        Creates a complete manifest-backed `.finpkg` / `.tar.gz` archive.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bundle_name = f"finauditpro_verified_backup_{timestamp}.finpkg"
        bundle_path = os.path.join(BACKUP_DIR, bundle_name)

        # 1. Consistent DB Snapshot using SQLite Online Backup API
        temp_dir = os.path.join(BACKUP_DIR, f"temp_{uuid.uuid4().hex[:8]}")
        os.makedirs(temp_dir, exist_ok=True)
        temp_db = os.path.join(temp_dir, "finauditpro.db")

        src_conn = sqlite3.connect(DB_PATH)
        dst_conn = sqlite3.connect(temp_db)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        db_sha256 = compute_file_sha256(temp_db)

        # 2. Extract counts & schema version
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        eng_count = conn.execute("SELECT COUNT(*) as c FROM engagements").fetchone()["c"]
        client_count = conn.execute("SELECT COUNT(*) as c FROM clients").fetchone()["c"]
        evidence_count = conn.execute("SELECT COUNT(*) as c FROM evidence_items").fetchone()["c"]
        tx_count = conn.execute("SELECT COUNT(*) as c FROM transactions").fetchone()["c"]
        mig_status = get_migration_status(conn)
        schema_version = mig_status.get("current_version", "001")
        conn.close()

        # 3. Create Manifest
        manifest = {
            "backup_version": 1,
            "app_version": "1.0.0",
            "schema_version": schema_version,
            "created_at": datetime.now().isoformat(),
            "created_by": created_by,
            "database_sha256": db_sha256,
            "engagement_count": eng_count,
            "client_count": client_count,
            "evidence_count": evidence_count,
            "transaction_count": tx_count,
            "manifest_checksum": ""
        }

        manifest_file = os.path.join(temp_dir, "manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        manifest["manifest_checksum"] = compute_file_sha256(manifest_file)
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # 4. Pack tar.gz bundle
        with tarfile.open(bundle_path, "w:gz") as tar:
            tar.add(temp_db, arcname="finauditpro.db")
            tar.add(manifest_file, arcname="manifest.json")

            # Add uploaded_files if present
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            uploads_dir = os.path.join(base_dir, "uploaded_files")
            if os.path.exists(uploads_dir):
                tar.add(uploads_dir, arcname="uploaded_files")

        shutil.rmtree(temp_dir, ignore_errors=True)

        bundle_size_kb = round(os.path.getsize(bundle_path) / 1024, 2)
        bundle_sha256 = compute_file_sha256(bundle_path)

        manifest["bundle_file"] = bundle_name
        manifest["bundle_size_kb"] = bundle_size_kb
        manifest["bundle_sha256"] = bundle_sha256

        return bundle_path, manifest

    @classmethod
    def validate_bundle(cls, bundle_path: str) -> Dict[str, Any]:
        """
        Validates backup bundle structure, manifest, and database integrity before restoration.
        """
        if not os.path.exists(bundle_path):
            return {"valid": False, "error": "Backup bundle file not found."}

        temp_dir = os.path.join(BACKUP_DIR, f"val_{uuid.uuid4().hex[:8]}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            with tarfile.open(bundle_path, "r:gz") as tar:
                names = tar.getnames()
                if "manifest.json" not in names or "finauditpro.db" not in names:
                    return {"valid": False, "error": "Invalid backup archive: missing manifest.json or finauditpro.db"}
                tar.extractall(path=temp_dir)

            manifest_file = os.path.join(temp_dir, "manifest.json")
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            db_file = os.path.join(temp_dir, "finauditpro.db")
            actual_db_hash = compute_file_sha256(db_file)

            if actual_db_hash != manifest.get("database_sha256"):
                return {
                    "valid": False,
                    "error": f"Database checksum mismatch: expected {manifest.get('database_sha256')} got {actual_db_hash}"
                }

            # Test sqlite connectivity
            conn = sqlite3.connect(db_file)
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            conn.close()

            return {
                "valid": True,
                "manifest": manifest,
                "database_sha256": actual_db_hash,
                "extracted_path": temp_dir
            }
        except Exception as e:
            return {"valid": False, "error": f"Archive extraction / validation failed: {str(e)}"}
        finally:
            # Note: caller will clean up temp_dir if used, otherwise remove
            pass

    @classmethod
    def restore_verified_bundle(cls, bundle_path: str, user: Any = None) -> Dict[str, Any]:
        """
        Validates bundle and restores database + evidence safely with automatic safety snapshot.
        """
        val = cls.validate_bundle(bundle_path)
        if not val.get("valid"):
            raise ValueError(f"Backup validation failed: {val.get('error')}")

        extracted = val.get("extracted_path")
        manifest = val.get("manifest")

        # 1. Take safety snapshot of current active DB
        safety_ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        safety_filename = f"pre_restore_safety_{safety_ts}_{uuid.uuid4().hex[:6]}.db"
        safety_filepath = os.path.join(BACKUP_DIR, safety_filename)
        if os.path.exists(DB_PATH):
            src_conn = sqlite3.connect(DB_PATH)
            snap_conn = sqlite3.connect(safety_filepath)
            try:
                src_conn.backup(snap_conn)
            finally:
                snap_conn.close()
                src_conn.close()

        # 2. Restore DB using Online Backup API
        restored_db = os.path.join(extracted, "finauditpro.db")
        backup_src = sqlite3.connect(restored_db)
        active_target = sqlite3.connect(DB_PATH)
        try:
            backup_src.backup(active_target)
        finally:
            active_target.close()
            backup_src.close()

        # 3. Restore uploaded_files if present in archive
        extracted_uploads = os.path.join(extracted, "uploaded_files")
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        target_uploads = os.path.join(base_dir, "uploaded_files")
        if os.path.exists(extracted_uploads):
            os.makedirs(target_uploads, exist_ok=True)
            for item in os.listdir(extracted_uploads):
                s = os.path.join(extracted_uploads, item)
                d = os.path.join(target_uploads, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

        # 4. Clean up temp extraction
        shutil.rmtree(extracted, ignore_errors=True)

        # 5. Run migrations/init_db to verify schema consistency
        from backend.app.database import init_db
        init_db()

        return {
            "status": "SUCCESS",
            "restored_manifest": manifest,
            "safety_snapshot": safety_filename,
            "message": "Database and evidence restored successfully with verified integrity."
        }
