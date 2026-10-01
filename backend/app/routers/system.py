import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.auth import get_current_user, require_role
from backend.app.services.integrity_checker import SystemIntegrityChecker
from backend.app.services.backup_service import BackupService, BACKUP_DIR
from backend.app.database import get_db_connection
from backend.app.utils.audit_logger import log_audit_event

router = APIRouter(prefix="/api/system", tags=["System Diagnostics & Integrity"])

@router.get("/integrity")
def get_system_integrity(current_user: dict = Depends(get_current_user)):
    """
    Returns diagnostic health check of the offline system:
    Database connectivity, WAL mode, foreign keys, schema version, audit chain, evidence integrity.
    """
    return SystemIntegrityChecker.run_all_checks()

@router.post("/backup/verified-bundle")
def create_verified_backup_bundle(current_user: dict = Depends(require_role(["Admin"]))):
    """
    Admin: Creates a full manifest-backed backup bundle containing database, evidence files, and checksums.
    """
    bundle_path, manifest = BackupService.create_verified_bundle(created_by=current_user.get("full_name", "Admin"))
    
    conn = get_db_connection()
    try:
        log_audit_event(
            conn=conn,
            action="CREATE_VERIFIED_BACKUP",
            module="BACKUP",
            record_id=manifest.get("bundle_file"),
            new_value=manifest,
            details=f"Created verified backup bundle {manifest.get('bundle_file')} ({manifest.get('bundle_size_kb')} KB)",
            user=current_user
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "status": "success",
        "message": "Verified backup bundle created successfully.",
        "manifest": manifest,
        "download_url": f"/api/audit-trail/backup/download/{manifest.get('bundle_file')}"
    }

@router.post("/backup/restore-verified-bundle/{filename}")
def restore_verified_backup_bundle(
    filename: str,
    current_user: dict = Depends(require_role(["Admin"]))
):
    """
    Admin: Validates and restores a manifest-backed backup bundle.
    """
    safe_name = os.path.basename(filename)
    bundle_path = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.exists(bundle_path):
        raise HTTPException(status_code=404, detail="Backup bundle file not found.")

    try:
        result = BackupService.restore_verified_bundle(bundle_path, user=current_user)
        
        conn = get_db_connection()
        try:
            log_audit_event(
                conn=conn,
                action="RESTORE_VERIFIED_BACKUP",
                module="BACKUP",
                record_id=safe_name,
                new_value=result,
                details=f"Restored verified backup bundle {safe_name}. Safety snapshot: {result.get('safety_snapshot')}",
                user=current_user
            )
            conn.commit()
        finally:
            conn.close()

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
