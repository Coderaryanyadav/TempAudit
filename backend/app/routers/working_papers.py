import os
import io
import csv
import json
import uuid
import shutil
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form, Response
from fastapi.responses import FileResponse

from backend.app.schemas import (
    WorkingPaperCreate,
    WorkingPaperUpdate,
    WorkingPaperStatusUpdate,
    WorkingPaperCommentCreate,
    WorkingPaperNotesUpdate,
    WorkingPaperLinkUpdate,
    WorkingPaperDeleteRequest
)
from backend.app.auth import get_current_user, require_engagement_access
from backend.app.database import get_db_connection

router = APIRouter(prefix="/api/working-papers", tags=["Working Papers"])

# Define base storage directory for working papers evidence files
BASE_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploaded_files", "working_papers")
os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)

MAX_WP_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

VALID_STATUSES = ["Prepared", "Under Review", "Reviewed", "Needs Correction"]
VALID_AREAS = [
    "General",
    "Cash & Bank",
    "Revenue & Debtors",
    "Purchases & Creditors",
    "Statutory Compliance",
    "Fixed Assets & Depreciation",
    "Inventories",
    "Payroll & Employee Benefits",
    "Borrowings & Finance Costs",
    "Direct & Indirect Taxation",
    "Internal Controls & Governance",
    "Related Party Disclosures",
    "Subsequent Events & Contingencies"
]

def _parse_wp_row(row: dict) -> dict:
    """Helper to parse JSON fields safely and normalize status & area."""
    wp = dict(row)
    for json_col in ["attached_files_json", "reviewer_comments_json", "linked_findings_json", "linked_transactions_json", "linked_checklists_json"]:
        raw = wp.get(json_col)
        parsed_name = json_col.replace("_json", "")
        if parsed_name == "attached_files":
            parsed_name = "attached_files"
        try:
            wp[parsed_name] = json.loads(raw) if raw else []
        except Exception:
            wp[parsed_name] = []

    # Map legacy status
    if wp.get("status") in ["Draft", "Open", None, ""]:
        wp["status"] = "Prepared"
    elif wp.get("status") in ["Final", "Completed"]:
        wp["status"] = "Reviewed"

    if not wp.get("area"):
        wp["area"] = wp.get("category") or "General"

    return wp


@router.get("/{engagement_id}")
def list_working_papers(
    engagement_id: int,
    area: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    prepared_by: Optional[str] = None,
    reviewed_by: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Returns list of working papers for an engagement with optional filters and
    aggregated summary counts for dashboard metrics.
    """
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    query = "SELECT * FROM working_papers WHERE engagement_id = ?"
    params = [engagement_id]

    if area and area != "All":
        query += " AND (area = ? OR category = ?)"
        params.extend([area, area])

    if status and status != "All":
        query += " AND status = ?"
        params.append(status)

    if prepared_by and prepared_by.strip():
        query += " AND prepared_by LIKE ?"
        params.append(f"%{prepared_by.strip()}%")

    if reviewed_by and reviewed_by.strip():
        query += " AND reviewed_by LIKE ?"
        params.append(f"%{reviewed_by.strip()}%")

    if search and search.strip():
        term = f"%{search.strip()}%"
        query += " AND (wp_reference LIKE ? OR title LIKE ? OR description LIKE ? OR evidence LIKE ? OR notes LIKE ?)"
        params.extend([term, term, term, term, term])

    query += " ORDER BY wp_reference ASC, id ASC"
    rows = conn.execute(query, tuple(params)).fetchall()

    all_wps = [_parse_wp_row(r) for r in rows]

    # Calculate overall summary metrics across the whole engagement (unfiltered)
    all_rows = conn.execute("SELECT status, attached_files_json, linked_findings_json, linked_transactions_json, linked_checklists_json FROM working_papers WHERE engagement_id = ?", (engagement_id,)).fetchall()
    conn.close()

    summary = {
        "total": len(all_rows),
        "prepared": 0,
        "under_review": 0,
        "reviewed": 0,
        "needs_correction": 0,
        "total_files": 0,
        "total_linked_items": 0
    }

    for r in all_rows:
        st = r["status"]
        if st in ["Draft", "Prepared", "Open", None]:
            summary["prepared"] += 1
        elif st == "Under Review":
            summary["under_review"] += 1
        elif st in ["Reviewed", "Final", "Completed"]:
            summary["reviewed"] += 1
        elif st == "Needs Correction":
            summary["needs_correction"] += 1
        else:
            summary["prepared"] += 1

        try:
            files = json.loads(r["attached_files_json"] or "[]")
            summary["total_files"] += len(files)
        except Exception:
            pass

        try:
            lf = json.loads(r["linked_findings_json"] or "[]")
            lt = json.loads(r["linked_transactions_json"] or "[]")
            lc = json.loads(r["linked_checklists_json"] or "[]")
            summary["total_linked_items"] += (len(lf) + len(lt) + len(lc))
        except Exception:
            pass

    return {
        "working_papers": all_wps,
        "summary": summary,
        "available_areas": VALID_AREAS,
        "available_statuses": VALID_STATUSES
    }


@router.get("/detail/{wp_id}")
def get_working_paper_detail(wp_id: int, current_user: dict = Depends(get_current_user)):
    """
    Returns single working paper detail with fully resolved linked findings,
    transactions, checklist items, and full audit logs.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM working_papers WHERE id = ?", (wp_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Working paper not found.")

    wp = _parse_wp_row(row)
    engagement_id = wp["engagement_id"]
    require_engagement_access(engagement_id, current_user)

    # 1. Resolve Linked Findings
    resolved_findings = []
    if wp.get("linked_findings"):
        finding_ids = [int(fid) for fid in wp["linked_findings"] if str(fid).isdigit()]
        if finding_ids:
            placeholders = ",".join("?" for _ in finding_ids)
            f_rows = conn.execute(f"SELECT id, finding_code, title, severity, category, status, risk_score FROM audit_findings WHERE id IN ({placeholders})", tuple(finding_ids)).fetchall()
            resolved_findings = [dict(f) for f in f_rows]

    # 2. Resolve Linked Transactions
    resolved_transactions = []
    if wp.get("linked_transactions"):
        tx_ids = [int(tid) for tid in wp["linked_transactions"] if str(tid).isdigit()]
        if tx_ids:
            placeholders = ",".join("?" for _ in tx_ids)
            t_rows = conn.execute(f"SELECT id, date, voucher_no, invoice_no, ledger, amount, debit, credit, description, party_name FROM transactions WHERE id IN ({placeholders})", tuple(tx_ids)).fetchall()
            resolved_transactions = [dict(t) for t in t_rows]

    # 3. Resolve Linked Checklist Items
    resolved_checklists = []
    if wp.get("linked_checklists"):
        chk_ids = [int(cid) for cid in wp["linked_checklists"] if str(cid).isdigit()]
        if chk_ids:
            placeholders = ",".join("?" for _ in chk_ids)
            c_rows = conn.execute(f"SELECT id, category, item_code, question, status, guidance, assigned_staff FROM audit_checklists WHERE id IN ({placeholders})", tuple(chk_ids)).fetchall()
            resolved_checklists = [dict(c) for c in c_rows]

    # 4. Fetch specific audit trail logs for this WP
    log_rows = conn.execute("""
        SELECT * FROM audit_logs 
        WHERE (entity_type LIKE 'working_paper%' AND (entity_id = ? OR record_id = ?))
           OR (module LIKE 'WORKING_PAPER%' AND record_id = ?)
           OR details LIKE ?
        ORDER BY id DESC LIMIT 50
    """, (wp_id, str(wp_id), str(wp_id), f"%{wp['wp_reference']}%")).fetchall()
    audit_trail = [dict(l) for l in log_rows]

    conn.close()

    wp["resolved_findings"] = resolved_findings
    wp["resolved_transactions"] = resolved_transactions
    wp["resolved_checklists"] = resolved_checklists
    wp["audit_trail"] = audit_trail

    return wp


@router.post("")
def create_working_paper(
    wp_data: WorkingPaperCreate,
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Creates a new working paper in the engagement and registers an audit trail record.
    """
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    now_str = datetime.now().isoformat()
    prep_date = wp_data.prepared_date or datetime.now().strftime("%Y-%m-%d")
    prep_by = wp_data.prepared_by or current_user.get("full_name", "Auditor")
    area = wp_data.area or wp_data.category or "General"

    # Verify reference uniqueness within this engagement
    existing = conn.execute(
        "SELECT id FROM working_papers WHERE engagement_id = ? AND wp_reference = ?",
        (engagement_id, wp_data.wp_reference.strip())
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Working Paper reference '{wp_data.wp_reference}' already exists for this engagement."
        )

    # Validate cross-engagement link integrity
    if wp_data.linked_findings:
        f_ids = [int(x) for x in wp_data.linked_findings if str(x).isdigit()]
        if f_ids:
            cnt = conn.execute(f"SELECT COUNT(*) as c FROM audit_findings WHERE engagement_id = ? AND id IN ({','.join('?' for _ in f_ids)})", (engagement_id, *f_ids)).fetchone()["c"]
            if cnt != len(f_ids):
                conn.close()
                raise HTTPException(status_code=400, detail="One or more linked findings do not belong to this engagement.")

    if wp_data.linked_transactions:
        t_ids = [int(x) for x in wp_data.linked_transactions if str(x).isdigit()]
        if t_ids:
            cnt = conn.execute(f"SELECT COUNT(*) as c FROM transactions WHERE engagement_id = ? AND id IN ({','.join('?' for _ in t_ids)})", (engagement_id, *t_ids)).fetchone()["c"]
            if cnt != len(t_ids):
                conn.close()
                raise HTTPException(status_code=400, detail="One or more linked transactions do not belong to this engagement.")

    if wp_data.linked_checklists:
        c_ids = [int(x) for x in wp_data.linked_checklists if str(x).isdigit()]
        if c_ids:
            cnt = conn.execute(f"SELECT COUNT(*) as c FROM audit_checklists WHERE engagement_id = ? AND id IN ({','.join('?' for _ in c_ids)})", (engagement_id, *c_ids)).fetchone()["c"]
            if cnt != len(c_ids):
                conn.close()
                raise HTTPException(status_code=400, detail="One or more linked checklists do not belong to this engagement.")

    linked_f_json = json.dumps(wp_data.linked_findings or [])
    linked_t_json = json.dumps(wp_data.linked_transactions or [])
    linked_c_json = json.dumps(wp_data.linked_checklists or [])

    cursor = conn.execute("""
    INSERT INTO working_papers (
        engagement_id, wp_reference, title, area, category, description,
        evidence, notes, attached_files_json, prepared_by, prepared_date,
        reviewed_by, review_date, status, reviewer_comments_json,
        linked_findings_json, linked_transactions_json, linked_checklists_json,
        created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, '', '', ?, '[]', ?, ?, ?, ?, ?)
    """, (
        engagement_id, wp_data.wp_reference.strip(), wp_data.title.strip(),
        area, area, wp_data.description or "", wp_data.evidence or "",
        wp_data.notes or "", prep_by, prep_date,
        wp_data.status or "Prepared",
        linked_f_json, linked_t_json, linked_c_json,
        now_str, now_str
    ))
    new_id = cursor.lastrowid

    # Log to audit trail
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="CREATE_WORKING_PAPER",
        module="WORKING_PAPERS",
        record_id=new_id,
        engagement_id=engagement_id,
        new_value={
            "wp_reference": wp_data.wp_reference.strip(),
            "title": wp_data.title.strip(),
            "area": area,
            "prepared_by": prep_by,
            "status": wp_data.status or "Prepared"
        },
        details=f"Created Working Paper [{wp_data.wp_reference}]: '{wp_data.title}' (Area: {area}, Prepared By: {prep_by})",
        user=current_user
    )

    conn.commit()
    conn.close()

    return {
        "id": new_id,
        "wp_reference": wp_data.wp_reference,
        "title": wp_data.title,
        "status": wp_data.status or "Prepared",
        "message": "Working paper created successfully."
    }


@router.put("/{wp_id}")
def update_working_paper(
    wp_id: int,
    wp_data: WorkingPaperUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Updates details of an existing working paper and records an audit log.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM working_papers WHERE id = ?", (wp_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Working paper not found.")

    curr = dict(row)
    require_engagement_access(curr["engagement_id"], current_user)
    now_str = datetime.now().isoformat()

    updates = []
    params = []
    changes = []

    if wp_data.wp_reference is not None and wp_data.wp_reference.strip():
        new_ref = wp_data.wp_reference.strip()
        if new_ref != curr["wp_reference"]:
            # Check collision
            dup = conn.execute("SELECT id FROM working_papers WHERE engagement_id = ? AND wp_reference = ? AND id != ?", (curr["engagement_id"], new_ref, wp_id)).fetchone()
            if dup:
                conn.close()
                raise HTTPException(status_code=400, detail=f"Reference '{new_ref}' is already in use by another working paper.")
            updates.append("wp_reference = ?")
            params.append(new_ref)
            changes.append(f"WP Ref: {curr['wp_reference']} -> {new_ref}")

    if wp_data.title is not None and wp_data.title.strip():
        updates.append("title = ?")
        params.append(wp_data.title.strip())
        if wp_data.title.strip() != curr["title"]:
            changes.append(f"Title: {curr['title']} -> {wp_data.title.strip()}")

    if wp_data.area is not None:
        updates.append("area = ?")
        updates.append("category = ?")
        params.extend([wp_data.area, wp_data.area])
        if wp_data.area != curr.get("area"):
            changes.append(f"Area: {curr.get('area')} -> {wp_data.area}")

    if wp_data.description is not None:
        updates.append("description = ?")
        params.append(wp_data.description)
        changes.append("Updated Description")

    if wp_data.evidence is not None:
        updates.append("evidence = ?")
        params.append(wp_data.evidence)
        changes.append("Updated Evidence Summary")

    if wp_data.notes is not None:
        updates.append("notes = ?")
        params.append(wp_data.notes)
        changes.append("Updated Notes")

    if wp_data.prepared_by is not None:
        updates.append("prepared_by = ?")
        params.append(wp_data.prepared_by)

    if wp_data.prepared_date is not None:
        updates.append("prepared_date = ?")
        params.append(wp_data.prepared_date)

    if wp_data.reviewed_by is not None:
        updates.append("reviewed_by = ?")
        params.append(wp_data.reviewed_by)

    if wp_data.review_date is not None:
        updates.append("review_date = ?")
        params.append(wp_data.review_date)

    if wp_data.status is not None:
        updates.append("status = ?")
        params.append(wp_data.status)
        if wp_data.status != curr["status"]:
            changes.append(f"Status: {curr['status']} -> {wp_data.status}")

    if wp_data.linked_findings is not None:
        updates.append("linked_findings_json = ?")
        params.append(json.dumps(wp_data.linked_findings))
        changes.append(f"Linked Findings ({len(wp_data.linked_findings)})")

    if wp_data.linked_transactions is not None:
        updates.append("linked_transactions_json = ?")
        params.append(json.dumps(wp_data.linked_transactions))
        changes.append(f"Linked Transactions ({len(wp_data.linked_transactions)})")

    if wp_data.linked_checklists is not None:
        updates.append("linked_checklists_json = ?")
        params.append(json.dumps(wp_data.linked_checklists))
        changes.append(f"Linked Checklists ({len(wp_data.linked_checklists)})")

    updates.append("updated_at = ?")
    params.append(now_str)
    params.append(wp_id)

    conn.execute(f"UPDATE working_papers SET {', '.join(updates)} WHERE id = ?", tuple(params))

    # Audit log
    change_desc = "; ".join(changes) if changes else "Updated working paper metadata"
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="UPDATE_WORKING_PAPER",
        module="WORKING_PAPERS",
        record_id=wp_id,
        engagement_id=curr.get("engagement_id"),
        old_value=curr,
        details=f"Updated Working Paper [{curr['wp_reference']}]: {change_desc}",
        user=current_user
    )

    conn.commit()
    conn.close()

    return {"status": "success", "message": "Working paper updated successfully."}


from pathlib import Path

def resolve_safe_evidence_path(wp_id: int, file_ref: str) -> Path:
    """
    Safely resolves and verifies that the file is strictly contained within the intended WP directory.
    Prevents path traversal attacks.
    """
    clean_name = os.path.basename(file_ref)
    target_dir = (Path(BASE_UPLOAD_DIR) / f"wp_{wp_id}").resolve()
    target_path = (target_dir / clean_name).resolve()
    base_resolved = Path(BASE_UPLOAD_DIR).resolve()

    if not target_path.is_relative_to(base_resolved):
        raise HTTPException(status_code=400, detail="Invalid evidence file path traversal detected.")
    return target_path


@router.post("/{wp_id}/upload-document")
async def upload_supporting_document(
    wp_id: int,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Uploads a supporting evidence document (PDF, Excel, Word, Image, CSV, etc.)
    and attaches it to the working paper.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM working_papers WHERE id = ?", (wp_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Working paper not found.")

    wp = _parse_wp_row(row)
    require_engagement_access(wp["engagement_id"], current_user)
    now_str = datetime.now().isoformat()

    # Read and validate file size (bounded to 50 MB)
    content = await file.read(MAX_WP_FILE_SIZE + 1)
    file_size = len(content)
    if file_size > MAX_WP_FILE_SIZE:
        conn.close()
        raise HTTPException(status_code=413, detail="File size exceeds maximum limit of 50 MB.")

    import hashlib
    sha256_hash = hashlib.sha256(content).hexdigest()

    original_name = os.path.basename(file.filename or "evidence.bin")
    file_ext = Path(original_name).suffix.lower()
    stored_filename = f"{uuid.uuid4().hex}{file_ext}"

    dest_path = resolve_safe_evidence_path(wp_id, stored_filename)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(dest_path, "wb") as f:
        f.write(content)

    rel_path = f"uploaded_files/working_papers/wp_{wp_id}/{stored_filename}"
    doc_id = str(uuid.uuid4())[:8]

    # Check for existing version with same original name
    attached_files = wp.get("attached_files") or []
    matching_existing = [d for d in attached_files if d.get("name") == original_name]
    doc_version = len(matching_existing) + 1
    parent_id = matching_existing[-1].get("id") if matching_existing else None

    new_doc = {
        "id": doc_id,
        "name": original_name,
        "file_name": stored_filename,
        "file_path": rel_path,
        "size_bytes": file_size,
        "size_display": f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.2f} MB",
        "content_type": file.content_type or "application/octet-stream",
        "sha256_hash": sha256_hash,
        "version": doc_version,
        "parent_id": parent_id,
        "description": description or "",
        "uploaded_by": current_user.get("full_name", "Auditor"),
        "uploaded_at": now_str
    }

    attached_files.append(new_doc)

    # Register in immutable evidence_items table
    try:
        from backend.app.repositories.evidence_repo import EvidenceRepository
        ev_repo = EvidenceRepository(conn)
        ev_repo.register_evidence(
            engagement_id=wp["engagement_id"],
            working_paper_id=wp_id,
            filename=stored_filename,
            original_filename=original_name,
            storage_path=rel_path,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            sha256_hash=sha256_hash,
            version=doc_version,
            uploaded_by=current_user.get("full_name", "Auditor")
        )
    except Exception:
        pass

    conn.execute(
        "UPDATE working_papers SET attached_files_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(attached_files), now_str, wp_id)
    )

    # Audit log
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action="UPLOAD_WP_EVIDENCE",
        module="WORKING_PAPERS",
        record_id=wp_id,
        user=current_user,
        engagement_id=wp["engagement_id"],
        details=f"Uploaded supporting document '{original_name}' (v{doc_version}, SHA-256: {sha256_hash[:12]}..., {new_doc['size_display']}) to WP [{wp['wp_reference']}]",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "document": new_doc,
        "message": f"Document '{original_name}' (v{doc_version}) uploaded and cryptographically indexed successfully."
    }


@router.delete("/{wp_id}/document/{doc_id}")
def delete_supporting_document(
    wp_id: int,
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Removes a supporting evidence file from the working paper and logs the audit event.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM working_papers WHERE id = ?", (wp_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Working paper not found.")

    wp = _parse_wp_row(row)
    require_engagement_access(wp["engagement_id"], current_user)
    now_str = datetime.now().isoformat()

    attached_files = wp.get("attached_files") or []
    removed_doc = None
    remaining_files = []

    for doc in attached_files:
        if str(doc.get("id")) == str(doc_id) or doc.get("file_name") == doc_id:
            removed_doc = doc
        else:
            remaining_files.append(doc)

    if not removed_doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found on this working paper.")

    # Remove file from disk if present using safe resolved path
    try:
        stored_name = removed_doc.get("file_name") or os.path.basename(removed_doc.get("file_path", ""))
        full_path = resolve_safe_evidence_path(wp_id, stored_name)
        if full_path.exists():
            full_path.unlink()
    except Exception:
        pass

    conn.execute(
        "UPDATE working_papers SET attached_files_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(remaining_files), now_str, wp_id)
    )

    # Audit log
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action="REMOVE_WP_EVIDENCE",
        module="WORKING_PAPERS",
        record_id=wp_id,
        user=current_user,
        engagement_id=wp["engagement_id"],
        details=f"Removed supporting document '{removed_doc.get('name')}' from WP [{wp['wp_reference']}]",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {"status": "success", "message": "Document removed successfully."}


@router.get("/download-file/{wp_id}/{doc_id}")
def download_working_paper_document(wp_id: int, doc_id: str, current_user: dict = Depends(get_current_user)):
    """
    Downloads or streams an attached supporting document with path traversal protection.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM working_papers WHERE id = ?", (wp_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Working paper not found.")

    wp = _parse_wp_row(row)
    require_engagement_access(wp["engagement_id"], current_user)

    target_doc = None
    for doc in wp.get("attached_files", []):
        if str(doc.get("id")) == str(doc_id) or doc.get("file_name") == doc_id:
            target_doc = doc
            break

    if not target_doc:
        raise HTTPException(status_code=404, detail="Document file not found.")

    stored_name = target_doc.get("file_name") or os.path.basename(target_doc.get("file_path", ""))
    full_path = resolve_safe_evidence_path(wp_id, stored_name)

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File content not found on server disk.")

    return FileResponse(
        path=str(full_path),
        filename=target_doc.get("name", full_path.name),
        media_type=target_doc.get("content_type", "application/octet-stream")
    )


@router.get("/{wp_id}/verify-document/{doc_id}")
def verify_working_paper_document(wp_id: int, doc_id: str, current_user: dict = Depends(get_current_user)):
    """
    Verifies the SHA-256 integrity of a working paper attachment against disk storage.
    """
    import hashlib
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM working_papers WHERE id = ?", (wp_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Working paper not found.")

    wp = _parse_wp_row(row)
    require_engagement_access(wp["engagement_id"], current_user)

    target_doc = None
    for doc in wp.get("attached_files", []):
        if str(doc.get("id")) == str(doc_id) or doc.get("file_name") == doc_id:
            target_doc = doc
            break

    if not target_doc:
        raise HTTPException(status_code=404, detail="Document file not found.")

    stored_name = target_doc.get("file_name") or os.path.basename(target_doc.get("file_path", ""))
    full_path = resolve_safe_evidence_path(wp_id, stored_name)

    if not full_path.exists():
        return {
            "valid": False,
            "status": "FILE_MISSING",
            "doc_id": doc_id,
            "filename": target_doc.get("name"),
            "error": "File missing on physical server storage."
        }

    sha = hashlib.sha256()
    with open(full_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    actual_hash = sha.hexdigest()
    expected_hash = target_doc.get("sha256_hash")

    is_valid = True if not expected_hash else (actual_hash == expected_hash)

    return {
        "valid": is_valid,
        "status": "VALID" if is_valid else "CORRUPTED",
        "doc_id": doc_id,
        "filename": target_doc.get("name"),
        "version": target_doc.get("version", 1),
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
        "file_size": full_path.stat().st_size
    }


@router.post("/{wp_id}/comments")
def add_reviewer_comment(
    wp_id: int,
    comment_data: WorkingPaperCommentCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Adds a reviewer comment to the working paper discussion log.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM working_papers WHERE id = ?", (wp_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Working paper not found.")

    wp = _parse_wp_row(row)
    require_engagement_access(wp["engagement_id"], current_user)
    now_str = datetime.now().isoformat()
    author = comment_data.author or current_user.get("full_name", "Auditor")

    new_comment = {
        "id": str(uuid.uuid4())[:8],
        "author": author,
        "username": current_user.get("username", "user"),
        "role": current_user.get("role", "Auditor"),
        "comment": comment_data.comment.strip(),
        "created_at": now_str
    }

    comments = wp.get("reviewer_comments") or []
    comments.append(new_comment)

    conn.execute(
        "UPDATE working_papers SET reviewer_comments_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(comments), now_str, wp_id)
    )

    # Audit log
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action="ADD_WP_COMMENT",
        module="WORKING_PAPERS",
        record_id=wp_id,
        user=current_user,
        engagement_id=wp["engagement_id"],
        details=f"Added reviewer comment to WP [{wp['wp_reference']}]: \"{comment_data.comment.strip()[:60]}...\"",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {"status": "success", "comment": new_comment}


@router.post("/{wp_id}/notes")
def update_working_paper_notes(
    wp_id: int,
    notes_data: WorkingPaperNotesUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Updates the internal working paper notes and records an audit log.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM working_papers WHERE id = ?", (wp_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Working paper not found.")

    wp = _parse_wp_row(row)
    require_engagement_access(wp["engagement_id"], current_user)
    now_str = datetime.now().isoformat()

    conn.execute(
        "UPDATE working_papers SET notes = ?, updated_at = ? WHERE id = ?",
        (notes_data.notes, now_str, wp_id)
    )

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action="UPDATE_WP_NOTES",
        module="WORKING_PAPERS",
        record_id=wp_id,
        user=current_user,
        engagement_id=wp["engagement_id"],
        details=f"Updated working notes on WP [{wp['wp_reference']}]",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {"status": "success", "message": "Working notes saved."}


@router.post("/{wp_id}/status")
def update_working_paper_status(
    wp_id: int,
    status_data: WorkingPaperStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Transitions the working paper status (Prepared, Under Review, Reviewed, Needs Correction).
    When marked as 'Reviewed', automatically records reviewer name and review timestamp.
    """
    if status_data.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status_data.status}'. Must be one of: {', '.join(VALID_STATUSES)}"
        )

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM working_papers WHERE id = ?", (wp_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Working paper not found.")

    wp = _parse_wp_row(row)
    require_engagement_access(wp["engagement_id"], current_user)
    old_status = wp["status"]
    new_status = status_data.status
    now_str = datetime.now().isoformat()
    today_str = datetime.now().strftime("%Y-%m-%d")

    reviewer = status_data.reviewed_by or wp.get("reviewed_by") or current_user.get("full_name", "Reviewer Partner")
    rev_date = status_data.review_date or wp.get("review_date") or today_str

    if new_status == "Reviewed":
        reviewer = status_data.reviewed_by or current_user.get("full_name", "Reviewer Partner")
        rev_date = status_data.review_date or today_str

    comments = wp.get("reviewer_comments") or []
    if status_data.comment and status_data.comment.strip():
        comments.append({
            "id": str(uuid.uuid4())[:8],
            "author": current_user.get("full_name", "Auditor"),
            "username": current_user.get("username", "user"),
            "role": current_user.get("role", "Auditor"),
            "comment": f"Status changed to [{new_status}]: {status_data.comment.strip()}",
            "created_at": now_str
        })

    conn.execute("""
    UPDATE working_papers 
    SET status = ?, reviewed_by = ?, review_date = ?, reviewer_comments_json = ?, updated_at = ?
    WHERE id = ?
    """, (
        new_status,
        reviewer if new_status == "Reviewed" else (wp.get("reviewed_by") or ""),
        rev_date if new_status == "Reviewed" else (wp.get("review_date") or ""),
        json.dumps(comments),
        now_str,
        wp_id
    ))

    # Audit log
    action_name = "MARK_WP_REVIEWED" if new_status == "Reviewed" else "CHANGE_WP_STATUS"
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action=action_name,
        module="WORKING_PAPERS",
        record_id=wp_id,
        user=current_user,
        engagement_id=wp["engagement_id"],
        details=f"Status changed from '{old_status}' to '{new_status}' on WP [{wp['wp_reference']}] (Reviewer: {reviewer}, Date: {rev_date})",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "new_status": new_status,
        "reviewed_by": reviewer if new_status == "Reviewed" else "",
        "review_date": rev_date if new_status == "Reviewed" else "",
        "message": f"Working paper marked as '{new_status}'."
    }


@router.post("/{wp_id}/links")
def update_working_paper_link(
    wp_id: int,
    link_data: WorkingPaperLinkUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Links or unlinks an audit finding, transaction, or checklist item to the working paper.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM working_papers WHERE id = ?", (wp_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Working paper not found.")

    wp = _parse_wp_row(row)
    require_engagement_access(wp["engagement_id"], current_user)
    now_str = datetime.now().isoformat()
    ltype = link_data.link_type.lower()
    action = link_data.action.lower()
    item_id = link_data.item_id

    json_col = ""
    field_list = []
    item_label = ""

    if ltype == "finding":
        json_col = "linked_findings_json"
        field_list = wp.get("linked_findings") or []
        item_label = f"Finding #{item_id}"
    elif ltype == "transaction":
        json_col = "linked_transactions_json"
        field_list = wp.get("linked_transactions") or []
        item_label = f"Transaction #{item_id}"
    elif ltype == "checklist":
        json_col = "linked_checklists_json"
        field_list = wp.get("linked_checklists") or []
        item_label = f"Checklist Item #{item_id}"
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid link_type. Must be 'finding', 'transaction', or 'checklist'.")

    # Perform link or unlink
    if action == "link":
        # Verify object belongs to the same engagement
        if ltype == "finding":
            valid = conn.execute("SELECT id FROM audit_findings WHERE id = ? AND engagement_id = ?", (item_id, wp["engagement_id"])).fetchone()
            if not valid:
                conn.close()
                raise HTTPException(status_code=400, detail="Finding does not belong to this engagement.")
        elif ltype == "transaction":
            valid = conn.execute("SELECT id FROM transactions WHERE id = ? AND engagement_id = ?", (item_id, wp["engagement_id"])).fetchone()
            if not valid:
                conn.close()
                raise HTTPException(status_code=400, detail="Transaction does not belong to this engagement.")
        elif ltype == "checklist":
            valid = conn.execute("SELECT id FROM audit_checklists WHERE id = ? AND engagement_id = ?", (item_id, wp["engagement_id"])).fetchone()
            if not valid:
                conn.close()
                raise HTTPException(status_code=400, detail="Checklist item does not belong to this engagement.")

        if item_id not in field_list:
            field_list.append(item_id)
        if ltype == "checklist":
            conn.execute("UPDATE audit_checklists SET reference_wp = ? WHERE id = ?", (wp["wp_reference"], item_id))
    elif action == "unlink":
        field_list = [fid for fid in field_list if fid != item_id]
        if ltype == "checklist":
            conn.execute("UPDATE audit_checklists SET reference_wp = '' WHERE id = ? AND reference_wp = ?", (item_id, wp["wp_reference"]))
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'link' or 'unlink'.")

    conn.execute(
        f"UPDATE working_papers SET {json_col} = ?, updated_at = ? WHERE id = ?",
        (json.dumps(field_list), now_str, wp_id)
    )

    # Audit log
    audit_action = "LINK_WP_ITEM" if action == "link" else "UNLINK_WP_ITEM"
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action=audit_action,
        module="WORKING_PAPERS",
        record_id=wp_id,
        user=current_user,
        engagement_id=wp["engagement_id"],
        details=f"{action.capitalize()}ed {item_label} to WP [{wp['wp_reference']}]",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "action": action,
        "link_type": ltype,
        "updated_links": field_list
    }


@router.delete("/{wp_id}")
def delete_working_paper(
    wp_id: int,
    req: WorkingPaperDeleteRequest = WorkingPaperDeleteRequest(),
    reason: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Deletes a working paper while strictly maintaining a complete audit trail.
    Enforces justification logging for reviewed working papers to prevent unrecorded deletions.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM working_papers WHERE id = ?", (wp_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Working paper not found.")

    wp = _parse_wp_row(row)
    require_engagement_access(wp["engagement_id"], current_user)
    now_str = datetime.now().isoformat()
    deletion_reason = (req.reason or reason or "").strip()
    is_reviewed = (wp.get("status") == "Reviewed")

    # Enforce mandatory justification when deleting a reviewed working paper
    if is_reviewed and not deletion_reason:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Mandatory Audit Requirement: Reviewed working papers cannot be deleted without a recorded justification / reason in the audit trail."
        )

    # Log comprehensive audit trail record before deletion
    log_action = "DELETE_REVIEWED_WORKING_PAPER" if is_reviewed else "DELETE_WORKING_PAPER"
    log_details = (
        f"DELETED WORKING PAPER [{wp['wp_reference']}]: '{wp['title']}' | "
        f"Status: {wp.get('status')} | Area: {wp.get('area')} | "
        f"Prepared by: {wp.get('prepared_by')} on {wp.get('prepared_date')} | "
        f"Reviewed by: {wp.get('reviewed_by')} on {wp.get('review_date')} | "
        f"Attached Docs: {len(wp.get('attached_files', []))} | "
        f"Linked Findings: {len(wp.get('linked_findings', []))} | "
        f"Reason / Justification: {deletion_reason or 'Direct deletion requested'}"
    )

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action=log_action,
        module="WORKING_PAPERS",
        record_id=wp_id,
        user=current_user,
        engagement_id=wp["engagement_id"],
        details=log_details,
        timestamp=now_str
    )

    # Delete row
    conn.execute("DELETE FROM working_papers WHERE id = ?", (wp_id,))
    conn.commit()
    conn.close()

    # Clean up attachment files from disk
    try:
        wp_folder = os.path.join(BASE_UPLOAD_DIR, f"wp_{wp_id}")
        if os.path.exists(wp_folder):
            shutil.rmtree(wp_folder)
    except Exception:
        pass

    return {
        "status": "success",
        "wp_reference": wp["wp_reference"],
        "message": f"Working paper '{wp['wp_reference']}' deleted and action recorded in audit log."
    }


@router.get("/{engagement_id}/linkable-items")
def get_linkable_items(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """
    Returns available findings, transactions, and checklist items for this engagement
    to populate selection pickers in the UI.
    """
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()

    # 1. Findings
    findings_rows = conn.execute("""
        SELECT id, finding_code, title, severity, category, status, risk_score
        FROM audit_findings
        WHERE engagement_id = ?
        ORDER BY risk_score DESC, id DESC
    """, (engagement_id,)).fetchall()
    findings = [dict(f) for f in findings_rows]

    # 2. Checklist Items
    chk_rows = conn.execute("""
        SELECT id, category, item_code, question, status, reference_wp
        FROM audit_checklists
        WHERE engagement_id = ?
        ORDER BY category ASC, item_code ASC
    """, (engagement_id,)).fetchall()
    checklists = [dict(c) for c in chk_rows]

    # 3. Transactions (Top 300 recent / significant)
    tx_rows = conn.execute("""
        SELECT id, date, voucher_no, invoice_no, ledger, amount, debit, credit, description, party_name
        FROM transactions
        WHERE engagement_id = ?
        ORDER BY id DESC LIMIT 300
    """, (engagement_id,)).fetchall()
    transactions = [dict(t) for t in tx_rows]

    conn.close()

    return {
        "findings": findings,
        "checklists": checklists,
        "transactions": transactions
    }


@router.get("/{engagement_id}/export/csv")
def export_working_papers_csv(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """
    Generates an SA 230 compliant CSV Working Papers Index & Register for the engagement.
    """
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT * FROM working_papers 
        WHERE engagement_id = ? 
        ORDER BY wp_reference ASC
    """, (engagement_id,)).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "WP Reference",
        "Title",
        "Audit Area",
        "Status",
        "Prepared By",
        "Prepared Date",
        "Reviewed By",
        "Review Date",
        "Description",
        "Evidence Summary",
        "Supporting Files Count",
        "Linked Findings Count",
        "Linked Transactions Count",
        "Linked Checklists Count",
        "Notes",
        "Created At",
        "Updated At"
    ])

    for r in rows:
        wp = _parse_wp_row(r)
        writer.writerow([
            wp.get("wp_reference", ""),
            wp.get("title", ""),
            wp.get("area", ""),
            wp.get("status", ""),
            wp.get("prepared_by", ""),
            wp.get("prepared_date", ""),
            wp.get("reviewed_by", ""),
            wp.get("review_date", ""),
            wp.get("description", ""),
            wp.get("evidence", ""),
            len(wp.get("attached_files", [])),
            len(wp.get("linked_findings", [])),
            len(wp.get("linked_transactions", [])),
            len(wp.get("linked_checklists", [])),
            wp.get("notes", ""),
            wp.get("created_at", ""),
            wp.get("updated_at", "")
        ])

    csv_content = output.getvalue()
    output.close()

    filename = f"working_papers_index_eng_{engagement_id}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
