import os
import json
import tarfile
import hashlib
import sqlite3
import shutil
import uuid
from datetime import datetime
from pathlib import PurePosixPath
from typing import Dict, Any, Optional, Tuple

from backend.app.database import get_db_connection, get_db_path
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
        bundle_name = f"finauditpro_verified_backup_{timestamp}_{uuid.uuid4().hex[:8]}.finpkg"
        bundle_path = os.path.join(BACKUP_DIR, bundle_name)

        # 1. Consistent DB Snapshot using SQLite Online Backup API
        temp_dir = os.path.join(BACKUP_DIR, f"temp_{uuid.uuid4().hex[:8]}")
        os.makedirs(temp_dir, exist_ok=True)
        temp_db = os.path.join(temp_dir, "finauditpro.db")

        db_path = get_db_path()
        src_conn = sqlite3.connect(db_path)
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
    def _safe_extract_tar(cls, archive: tarfile.TarFile, target_dir: str) -> None:
        """Extract only regular backup members under known paths; reject links and traversal."""
        root = os.path.realpath(target_dir)
        members = archive.getmembers()
        seen = set()
        total_size = 0
        max_members = 100_000
        max_total_size = 2 * 1024 * 1024 * 1024  # 2 GiB decompressed safety limit

        if len(members) > max_members:
            raise ValueError("Backup archive contains too many entries.")

        for member in members:
            raw_name = member.name or ""
            normalized_input = raw_name.rstrip("/")
            if (
                not normalized_input
                or raw_name.startswith(("/", "\\"))
                or "\\" in raw_name
                or ":" in normalized_input.split("/")[0]
            ):
                raise ValueError("Backup archive contains an unsafe member path.")

            raw_parts = normalized_input.split("/")
            if any(part in {"", ".", ".."} for part in raw_parts):
                raise ValueError("Backup archive contains a path traversal entry.")

            member_path = PurePosixPath(normalized_input)
            normalized_name = member_path.as_posix()
            allowed = (
                normalized_name in {"manifest.json", "finauditpro.db", "uploaded_files"}
                or normalized_name.startswith("uploaded_files/")
            )
            if not allowed:
                raise ValueError("Backup archive contains an unexpected file path.")
            if normalized_name in seen:
                raise ValueError("Backup archive contains duplicate member paths.")
            seen.add(normalized_name)

            # Reject symbolic links, hard links, devices, FIFOs and other special members.
            if not (member.isdir() or member.isfile()):
                raise ValueError("Backup archive may contain only regular files and directories.")

            destination = os.path.realpath(os.path.join(root, *member_path.parts))
            if os.path.commonpath([root, destination]) != root:
                raise ValueError("Backup archive member escapes the extraction directory.")

            if member.isdir():
                os.makedirs(destination, exist_ok=True)
                continue

            total_size += member.size
            if member.size < 0 or total_size > max_total_size:
                raise ValueError("Backup archive exceeds the allowed uncompressed size.")

            os.makedirs(os.path.dirname(destination), exist_ok=True)
            source_file = archive.extractfile(member)
            if source_file is None:
                raise ValueError("Backup archive contains an unreadable file entry.")
            with source_file, open(destination, "xb") as destination_file:
                shutil.copyfileobj(source_file, destination_file)

        for required in ("manifest.json", "finauditpro.db"):
            path = os.path.join(root, required)
            if required not in seen or not os.path.isfile(path):
                raise ValueError(f"Backup archive is missing root-level {required}.")


    @classmethod
    def validate_bundle(cls, bundle_path: str, retain_extracted_files: bool = False) -> Dict[str, Any]:
        """Validate bundle paths, manifest checksum, database checksum and SQLite integrity."""
        if not os.path.exists(bundle_path):
            return {"valid": False, "error": "Backup bundle file not found."}

        temp_dir = os.path.join(BACKUP_DIR, f"val_{uuid.uuid4().hex}")
        os.makedirs(temp_dir, exist_ok=False)
        preserve_extraction = False
        try:
            with tarfile.open(bundle_path, "r:gz") as archive:
                cls._safe_extract_tar(archive, temp_dir)

            manifest_file = os.path.join(temp_dir, "manifest.json")
            with open(manifest_file, "r", encoding="utf-8") as manifest_handle:
                manifest = json.load(manifest_handle)
            if not isinstance(manifest, dict):
                raise ValueError("Backup manifest must be a JSON object.")

            claimed_manifest_checksum = manifest.get("manifest_checksum")
            unsigned_manifest = dict(manifest)
            unsigned_manifest["manifest_checksum"] = ""
            expected_manifest_checksum = hashlib.sha256(
                json.dumps(unsigned_manifest, indent=2).encode("utf-8")
            ).hexdigest()
            if not claimed_manifest_checksum or claimed_manifest_checksum != expected_manifest_checksum:
                raise ValueError("Backup manifest checksum validation failed.")

            db_file = os.path.join(temp_dir, "finauditpro.db")
            actual_db_hash = compute_file_sha256(db_file)
            if actual_db_hash != manifest.get("database_sha256"):
                raise ValueError("Backup database checksum validation failed.")

            conn = sqlite3.connect(db_file)
            try:
                quick_check = conn.execute("PRAGMA quick_check").fetchone()
                if not quick_check or quick_check[0] != "ok":
                    raise ValueError("Backup SQLite database failed PRAGMA quick_check.")
                tables = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                }
                if not {"users", "app_settings"}.issubset(tables):
                    raise ValueError("Backup SQLite database is missing core application tables.")
            finally:
                conn.close()

            result = {
                "valid": True,
                "manifest": manifest,
                "database_sha256": actual_db_hash,
            }
            if retain_extracted_files:
                preserve_extraction = True
                result["extracted_path"] = temp_dir
            return result
        except Exception as exc:
            return {"valid": False, "error": f"Backup archive validation failed: {exc}"}
        finally:
            if not preserve_extraction:
                shutil.rmtree(temp_dir, ignore_errors=True)


    @classmethod
    def restore_verified_bundle(cls, bundle_path: str, user: Any = None) -> Dict[str, Any]:
        """Validate and restore database plus evidence, preserving an emergency snapshot."""
        validation = cls.validate_bundle(bundle_path, retain_extracted_files=True)
        if not validation.get("valid"):
            raise ValueError(f"Backup validation failed: {validation.get('error')}")

        extracted = validation.get("extracted_path")
        manifest = validation.get("manifest")
        if not extracted or not os.path.isdir(extracted):
            raise ValueError("Validated backup extraction directory is missing.")

        try:
            # 1. Take safety snapshot of current active DB.
            safety_ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            safety_filename = f"pre_restore_safety_{safety_ts}_{uuid.uuid4().hex[:6]}.db"
            safety_filepath = os.path.join(BACKUP_DIR, safety_filename)
            current_db_path = get_db_path()
            if os.path.exists(current_db_path):
                src_conn = sqlite3.connect(current_db_path)
                snap_conn = sqlite3.connect(safety_filepath)
                try:
                    src_conn.backup(snap_conn)
                finally:
                    snap_conn.close()
                    src_conn.close()

            # 2. Restore DB using SQLite Online Backup API.
            restored_db = os.path.join(extracted, "finauditpro.db")
            backup_src = sqlite3.connect(restored_db)
            active_target = sqlite3.connect(current_db_path)
            try:
                backup_src.backup(active_target)
            finally:
                active_target.close()
                backup_src.close()

            # 3. Restore uploaded evidence additively; links were rejected by safe extraction.
            extracted_uploads = os.path.join(extracted, "uploaded_files")
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            target_uploads = os.path.join(project_root, "uploaded_files")
            if os.path.exists(extracted_uploads):
                os.makedirs(target_uploads, exist_ok=True)
                for item in os.listdir(extracted_uploads):
                    source_path = os.path.join(extracted_uploads, item)
                    destination_path = os.path.join(target_uploads, item)
                    if os.path.isdir(source_path):
                        shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(source_path, destination_path)

            from backend.app.database import init_db
            init_db()

            return {
                "status": "SUCCESS",
                "restored_manifest": manifest,
                "safety_snapshot": safety_filename,
                "message": "Database and evidence restored successfully with verified integrity.",
            }
        finally:
            shutil.rmtree(extracted, ignore_errors=True)


