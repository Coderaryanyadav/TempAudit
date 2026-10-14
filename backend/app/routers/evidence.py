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
    """Download evidence only from the upload root after verifying its registered hash."""
    conn = get_db_connection()
    try:
        repo = EvidenceRepository(conn)
        evidence = repo.get_by_id(evidence_id)
        if not evidence:
            raise HTTPException(status_code=404, detail="Evidence record not found.")

        require_engagement_access(evidence["engagement_id"], current_user)
        abs_path = repo.resolve_storage_path(
            evidence.get("storage_path"),
            base_dir=os.path.dirname(BASE_EVIDENCE_DIR),
        )
        if abs_path is None:
            raise HTTPException(
                status_code=409,
                detail="Evidence storage path is invalid or escapes the evidence storage directory.",
            )
        if not os.path.isfile(abs_path):
            raise HTTPException(status_code=404, detail="Physical evidence file not found on disk.")

        sha = hashlib.sha256()
        with open(abs_path, "rb") as evidence_file:
            while chunk := evidence_file.read(65536):
                sha.update(chunk)
        disk_hash = sha.hexdigest()

        if disk_hash != evidence["sha256_hash"]:
            raise HTTPException(
                status_code=409,
                detail="Evidence integrity verification failed; the file may have been modified.",
            )

        return FileResponse(
            path=abs_path,
            filename=os.path.basename(evidence["original_filename"]),
            media_type=evidence["mime_type"],
        )
    finally:
        conn.close()
