import os
import json
import tarfile
import hashlib
import sqlite3
import shutil
import uuid
import hmac
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

from backend.app.database import get_db_connection, get_db_path
from backend.migrations.runner import get_migration_status

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

def compute_file_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file on disk."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

def compute_canonical_manifest_checksum(manifest_dict: Dict[str, Any]) -> str:
    """
    Computes deterministic SHA-256 over canonical JSON representation of manifest metadata,
    excluding dynamic wrapper properties (manifest_checksum, manifest_signature, bundle_file, bundle_size_kb, bundle_sha256).
    """
    excluded_keys = {"manifest_checksum", "manifest_signature", "bundle_file", "bundle_size_kb", "bundle_sha256"}
    clean_manifest = {k: v for k, v in manifest_dict.items() if k not in excluded_keys}
    canonical_bytes = json.dumps(clean_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()

def get_backup_signing_key() -> bytes:
    """
    Retrieves the dedicated backup signing key, strictly failing closed if unavailable.
    Prioritizes dedicated FINAUDIT_BACKUP_SIGNING_KEY / FINAUDIT_BACKUP_KEY, or derives
    a domain-separated backup key from explicit FINAUDIT_SECRET_KEY in environment.
    Never uses a hardcoded fallback or silently reuses arbitrary app tokens.
    """
    # 1. Dedicated backup signing key
    dedicated_key = os.environ.get("FINAUDIT_BACKUP_SIGNING_KEY") or os.environ.get("FINAUDIT_BACKUP_KEY")
    if dedicated_key and len(dedicated_key.strip()) >= 16:
        return dedicated_key.strip().encode("utf-8")

    # 2. Explicit server secret key from environment with domain separation
    env_secret = os.environ.get("FINAUDIT_SECRET_KEY") or os.environ.get("SECRET_KEY")
    if env_secret and len(env_secret.strip()) >= 16:
        return hmac.new(
            env_secret.strip().encode("utf-8"),
            b"FinAuditPro::BackupSigning::v1",
            hashlib.sha256
        ).digest()

    # 3. Dedicated backup key stored in database app_settings
    try:
        conn = get_db_connection()
        row = conn.execute("SELECT value FROM app_settings WHERE key = 'backup_signing_key'").fetchone()
        conn.close()
        if row and row["value"] and len(row["value"].strip()) >= 16:
            return row["value"].strip().encode("utf-8")
    except Exception:
        pass

    # Fail closed: No valid dedicated or environment signing key configured
    raise RuntimeError(
        "Critical Security Error: No valid backup signing key configured. "
        "Set FINAUDIT_BACKUP_SIGNING_KEY or FINAUDIT_SECRET_KEY in environment."
    )

def get_backup_verification_keys() -> List[bytes]:
    """
    Returns list of active and previous keys for signature verification,
    supporting key rotation and backwards-compatible verification of older backups.
    """
    keys = []
    try:
        keys.append(get_backup_signing_key())
    except RuntimeError:
        pass

    # Rotated/previous keys configured via comma-separated env var
    previous_keys = os.environ.get("FINAUDIT_BACKUP_SIGNING_KEYS_PREVIOUS", "")
    for k in previous_keys.split(","):
        k = k.strip()
        if len(k) >= 16:
            keys.append(k.encode("utf-8"))

    if not keys:
        raise RuntimeError(
            "Critical Security Error: No backup signing or verification keys available. "
            "Set FINAUDIT_BACKUP_SIGNING_KEY or FINAUDIT_SECRET_KEY."
        )
    return keys

def compute_manifest_signature(manifest_dict: Dict[str, Any], signing_key: Optional[bytes] = None) -> str:
    """
    Computes cryptographic HMAC-SHA256 signature using the active backup signing key,
    authenticating the creator and preventing unauthorized manifest forgery or tampering.
    """
    key = signing_key or get_backup_signing_key()
    excluded_keys = {"manifest_checksum", "manifest_signature", "bundle_file", "bundle_size_kb", "bundle_sha256"}
    clean_manifest = {k: v for k, v in manifest_dict.items() if k not in excluded_keys}
    canonical_bytes = json.dumps(clean_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key, canonical_bytes, hashlib.sha256).hexdigest()

def verify_manifest_signature(manifest_dict: Dict[str, Any]) -> bool:
    """
    Verifies manifest HMAC signature against current key and rotated verification keys.
    """
    recorded_sig = manifest_dict.get("manifest_signature")
    if not recorded_sig:
        return False

    keys = get_backup_verification_keys()
    for key in keys:
        expected_sig = compute_manifest_signature(manifest_dict, signing_key=key)
        if hmac.compare_digest(recorded_sig, expected_sig):
            return True
    return False

class BackupService:
    """
    Verified Manifest-Driven Backup & Restore Engine.
    Bundles SQLite database, deterministic evidence files inventory, and cryptographic HMAC-SHA256 manifest.
    """

    @classmethod
    def create_verified_bundle(cls, created_by: str = "Admin") -> Tuple[str, Dict[str, Any]]:
        """
        Creates a complete manifest-backed `.finpkg` / `.tar.gz` archive.
        Inventories and signs all evidence files and the database snapshot.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bundle_name = f"finauditpro_verified_backup_{timestamp}.finpkg"
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

        # 3. Deterministic Evidence Files Inventory
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        uploads_dir = os.path.join(base_dir, "uploaded_files")
        evidence_inventory = []

        if os.path.exists(uploads_dir):
            for root, _, files in os.walk(uploads_dir):
                for f in files:
                    filepath = os.path.join(root, f)
                    rel_path = os.path.relpath(filepath, uploads_dir).replace("\\", "/")
                    if ".." in rel_path or rel_path.startswith("/"):
                        continue
                    evidence_inventory.append({
                        "path": rel_path,
                        "size_bytes": os.path.getsize(filepath),
                        "sha256": compute_file_sha256(filepath)
                    })
        # Sort deterministically by relative path
        evidence_inventory.sort(key=lambda x: x["path"])

        # 4. Create Manifest with Canonical Checksum & HMAC Signature
        manifest = {
            "backup_version": 2,
            "app_version": "1.0.0",
            "schema_version": schema_version,
            "created_at": datetime.now().isoformat(),
            "created_by": created_by,
            "database_sha256": db_sha256,
            "engagement_count": eng_count,
            "client_count": client_count,
            "evidence_count": evidence_count,
            "transaction_count": tx_count,
            "evidence_files": evidence_inventory,
            "evidence_files_count": len(evidence_inventory)
        }
        manifest["manifest_checksum"] = compute_canonical_manifest_checksum(manifest)
        manifest["manifest_signature"] = compute_manifest_signature(manifest)

        manifest_file = os.path.join(temp_dir, "manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)

        # 5. Pack tar.gz bundle
        with tarfile.open(bundle_path, "w:gz") as tar:
            tar.add(temp_db, arcname="finauditpro.db")
            tar.add(manifest_file, arcname="manifest.json")

            # Add uploaded_files if present
            if os.path.exists(uploads_dir) and evidence_inventory:
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
        Validates backup bundle structure, canonical manifest checksum, cryptographic signature,
        database integrity, and every individual evidence file checksum before restoration.
        """
        if not os.path.exists(bundle_path):
            return {"valid": False, "error": "Backup bundle file not found."}

        temp_dir = os.path.join(BACKUP_DIR, f"val_{uuid.uuid4().hex[:8]}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            with tarfile.open(bundle_path, "r:gz") as tar:
                names = tar.getnames()
                if "manifest.json" not in names or "finauditpro.db" not in names:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return {"valid": False, "error": "Invalid backup archive: missing manifest.json or finauditpro.db"}

                # Path traversal, link, device, and malicious member validation
                abs_temp_dir = os.path.abspath(temp_dir)
                for member in tar.getmembers():
                    member_path = os.path.abspath(os.path.join(temp_dir, member.name))
                    if not member_path.startswith(abs_temp_dir + os.sep) and member_path != abs_temp_dir:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return {"valid": False, "error": f"Security violation: Archive member '{member.name}' contains path traversal."}
                    if member.islnk() or member.issym() or member.ischr() or member.isblk() or member.isfifo():
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return {"valid": False, "error": f"Security violation: Archive member '{member.name}' contains unsafe link or device node."}
                    if member.name.startswith("/") or ".." in member.name:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return {"valid": False, "error": f"Security violation: Archive member '{member.name}' contains illegal path."}

                # Safe extraction with deprecation-free filter on Python 3.12+
                if hasattr(tarfile, 'data_filter'):
                    tar.extractall(path=temp_dir, filter='data')
                else:
                    tar.extractall(path=temp_dir)

            # 1. Validate manifest.json existence, canonical checksum & cryptographic signature
            manifest_file = os.path.join(temp_dir, "manifest.json")
            if not os.path.exists(manifest_file):
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {"valid": False, "error": "manifest.json missing after extraction."}

            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            recorded_manifest_checksum = manifest.get("manifest_checksum")
            if not recorded_manifest_checksum:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {"valid": False, "error": "Manifest verification failed: missing manifest_checksum."}

            expected_manifest_checksum = compute_canonical_manifest_checksum(manifest)
            if recorded_manifest_checksum != expected_manifest_checksum:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {
                    "valid": False,
                    "error": "Manifest integrity violation: recorded checksum does not match computed checksum."
                }

            # Verify cryptographic signature using active or rotated keys
            recorded_sig = manifest.get("manifest_signature")
            if not recorded_sig:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {"valid": False, "error": "Manifest verification failed: missing cryptographic manifest_signature."}

            try:
                sig_valid = verify_manifest_signature(manifest)
            except RuntimeError as e:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {"valid": False, "error": f"Cryptographic verification error: {str(e)}"}

            if not sig_valid:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {
                    "valid": False,
                    "error": "Cryptographic authenticity violation: manifest signature mismatch (backup not signed by authorized key)."
                }

            # 2. Validate database file existence and checksum
            db_file = os.path.join(temp_dir, "finauditpro.db")
            if not os.path.exists(db_file):
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {"valid": False, "error": "Database file finauditpro.db missing from extracted backup."}

            actual_db_hash = compute_file_sha256(db_file)
            if actual_db_hash != manifest.get("database_sha256"):
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {
                    "valid": False,
                    "error": f"Database checksum mismatch: expected {manifest.get('database_sha256')} got {actual_db_hash}"
                }

            # 3. Test sqlite connectivity
            conn = sqlite3.connect(db_file)
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            conn.close()

            # 4. Validate Evidence Files Inventory & Individual SHA-256 Checksums
            manifest_evidence = manifest.get("evidence_files", [])
            extracted_uploads = os.path.join(temp_dir, "uploaded_files")

            if manifest_evidence:
                if not os.path.exists(extracted_uploads):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return {
                        "valid": False,
                        "error": "Evidence integrity violation: Archive manifest contains evidence inventory, but uploaded_files directory is missing."
                    }

                manifest_paths = set()
                for item in manifest_evidence:
                    rel_p = item.get("path")
                    exp_size = item.get("size_bytes")
                    exp_hash = item.get("sha256")
                    manifest_paths.add(rel_p)

                    full_p = os.path.join(extracted_uploads, rel_p)
                    # Verify no path traversal in manifested path
                    abs_full_p = os.path.abspath(full_p)
                    abs_extracted_uploads = os.path.abspath(extracted_uploads)
                    if not abs_full_p.startswith(abs_extracted_uploads + os.sep):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return {
                            "valid": False,
                            "error": f"Security violation: Evidence file path '{rel_p}' traverses outside uploaded_files."
                        }

                    if not os.path.exists(full_p):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return {
                            "valid": False,
                            "error": f"Evidence integrity violation: Manifested evidence file '{rel_p}' missing from archive."
                        }

                    actual_size = os.path.getsize(full_p)
                    if actual_size != exp_size:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return {
                            "valid": False,
                            "error": f"Evidence integrity violation: File size mismatch for '{rel_p}'. Expected {exp_size}, got {actual_size}."
                        }

                    actual_hash = compute_file_sha256(full_p)
                    if actual_hash != exp_hash:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return {
                            "valid": False,
                            "error": f"Evidence integrity violation: SHA-256 mismatch for '{rel_p}'. File content has been modified or corrupted."
                        }

                # Verify no rogue / unmanifested files exist in uploaded_files
                for root, _, files in os.walk(extracted_uploads):
                    for f in files:
                        disk_p = os.path.join(root, f)
                        rel_disk_p = os.path.relpath(disk_p, extracted_uploads).replace("\\", "/")
                        if rel_disk_p not in manifest_paths:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            return {
                                "valid": False,
                                "error": f"Evidence security violation: Unmanifested or rogue evidence file '{rel_disk_p}' detected in archive."
                            }
            elif os.path.exists(extracted_uploads):
                # Archive has uploaded_files directory but manifest listed 0 evidence files
                unmanifested_files = []
                for root, _, files in os.walk(extracted_uploads):
                    for f in files:
                        unmanifested_files.append(os.path.relpath(os.path.join(root, f), extracted_uploads).replace("\\", "/"))
                if unmanifested_files:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return {
                        "valid": False,
                        "error": f"Evidence security violation: Unmanifested evidence files detected in archive: {unmanifested_files[:3]}."
                    }

            return {
                "valid": True,
                "manifest": manifest,
                "database_sha256": actual_db_hash,
                "manifest_checksum": recorded_manifest_checksum,
                "extracted_path": temp_dir
            }
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return {"valid": False, "error": f"Archive extraction / validation failed: {str(e)}"}

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

        try:
            # 1. Take safety snapshot of current active DB
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

            # 2. Restore DB using Online Backup API
            restored_db = os.path.join(extracted, "finauditpro.db")
            backup_src = sqlite3.connect(restored_db)
            active_target = sqlite3.connect(current_db_path)
            try:
                backup_src.backup(active_target)
            finally:
                active_target.close()
                backup_src.close()

            # 3. Restore uploaded_files if present and verified in archive
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

            # 4. Run migrations/init_db to verify schema consistency
            from backend.app.database import init_db
            init_db()

            return {
                "status": "SUCCESS",
                "restored_manifest": manifest,
                "safety_snapshot": safety_filename,
                "message": "Database and evidence restored successfully with verified integrity."
            }
        finally:
            # Clean up temp extraction directory in all cases
            shutil.rmtree(extracted, ignore_errors=True)
