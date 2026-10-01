import os
import hashlib
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from datetime import datetime

from backend.app.auth import get_current_user, require_engagement_access
from backend.app.database import get_db_connection
from backend.app.repositories.evidence_repo import EvidenceRepository
from backend.app.utils.audit_logger import log_audit_event

router = APIRouter(prefix="/api/evidence", tags=["Evidence Management"])

BASE_EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploaded_files")

@router.get("/engagement/{engagement_id}")
def list_engagement_evidence(
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Lists all immutable evidence artifacts registered for an engagement."""
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    repo = EvidenceRepository(conn)
    items = repo.list_by_engagement(engagement_id)
    conn.close()
    return {"engagement_id": engagement_id, "evidence_count": len(items), "evidence_items": items}

@router.get("/verify/{evidence_id}")
def verify_evidence_hash(
    evidence_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Verifies physical SHA-256 integrity against immutable database record.
    Detects any file tampering or corruption.
    """
    conn = get_db_connection()
    repo = EvidenceRepository(conn)
    evidence = repo.get_by_id(evidence_id)
    if not evidence:
        conn.close()
        raise HTTPException(status_code=404, detail="Evidence record not found.")

    require_engagement_access(evidence["engagement_id"], current_user)
    result = repo.verify_physical_integrity(evidence_id, base_dir=os.path.dirname(BASE_EVIDENCE_DIR))
    conn.close()
    return result

@router.get("/download/{evidence_id}")
def download_evidence(
    evidence_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Downloads evidence artifact verifying hash integrity prior to streaming."""
    conn = get_db_connection()
    repo = EvidenceRepository(conn)
    evidence = repo.get_by_id(evidence_id)
    if not evidence:
        conn.close()
        raise HTTPException(status_code=404, detail="Evidence record not found.")

    require_engagement_access(evidence["engagement_id"], current_user)
    
    storage_path = evidence["storage_path"]
    if os.path.isabs(storage_path):
        abs_path = storage_path
    else:
        abs_path = os.path.join(os.path.dirname(BASE_EVIDENCE_DIR), storage_path)

    if not os.path.exists(abs_path):
        conn.close()
        raise HTTPException(status_code=404, detail="Physical evidence file not found on disk.")

    # Integrity verification
    sha = hashlib.sha256()
    with open(abs_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    disk_hash = sha.hexdigest()

    if disk_hash != evidence["sha256_hash"]:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Evidence Integrity Failure: Expected SHA-256 {evidence['sha256_hash']} but disk file has {disk_hash}"
        )

    conn.close()
    return FileResponse(
        path=abs_path,
        filename=evidence["original_filename"],
        media_type=evidence["mime_type"]
    )
