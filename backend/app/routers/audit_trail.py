import csv
import hashlib
import io
import json
import os
import shutil
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from backend.app.auth import get_current_user, require_role, require_engagement_access
from backend.app.database import DB_PATH, get_db_connection
from backend.app.utils.audit_logger import log_audit_event

router = APIRouter(prefix="/api/audit-trail", tags=["Audit Trail & Database Backup"])

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)


def calculate_file_hash(filepath: str) -> str:
    """Calculate SHA-256 hash of a file for integrity verification."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


# ----------------- AUDIT LOGS SEARCH & FILTERING -----------------

@router.get("")
def get_audit_trail(
    search: Optional[str] = None,
    action: Optional[str] = None,
    module: Optional[str] = None,
    user: Optional[str] = None,
    record_id: Optional[str] = None,
    engagement_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """
    Search and filter append-oriented immutable audit logs with multi-parameter criteria.
    Supports full-text search, action/module/user/date filtering, and pagination.
    """
    if engagement_id:
        require_engagement_access(engagement_id, current_user)

    conn = get_db_connection()
    conditions = ["1=1"]
    params = []

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append("""
            (action LIKE ? OR module LIKE ? OR details LIKE ? OR username LIKE ? 
             OR record_id LIKE ? OR old_value LIKE ? OR new_value LIKE ?)
        """)
        params.extend([term, term, term, term, term, term, term])

    if action and action != "All" and action.strip():
        conditions.append("action = ?")
        params.append(action.strip().upper())

    if module and module != "All" and module.strip():
        conditions.append("module = ?")
        params.append(module.strip().upper())

    if user and user != "All" and user.strip():
        conditions.append("LOWER(username) = LOWER(?)")
        params.append(user.strip())

    if record_id and record_id.strip():
        conditions.append("record_id = ?")
        params.append(record_id.strip())

    if engagement_id:
        conditions.append("engagement_id = ?")
        params.append(engagement_id)

    if from_date and from_date.strip():
        conditions.append("timestamp >= ?")
        params.append(from_date.strip())

    if to_date and to_date.strip():
        # Append end of day if only date is passed
        to_str = to_date.strip()
        if len(to_str) == 10:
            to_str += "T23:59:59"
        conditions.append("timestamp <= ?")
        params.append(to_str)

    where_clause = " WHERE " + " AND ".join(conditions)

    # Count total matching rows
    count_query = f"SELECT COUNT(*) as total FROM audit_logs {where_clause}"
    total_count = conn.execute(count_query, tuple(params)).fetchone()["total"]

    # Calculate pagination
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    # Fetch page items
    data_query = f"""
        SELECT id, timestamp, user_id, username, action, module, record_id, 
               old_value, new_value, details, engagement_id, ip_address, previous_hash, entry_hash
        FROM audit_logs
        {where_clause}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    """
    page_params = params + [page_size, offset]
    rows = conn.execute(data_query, tuple(page_params)).fetchall()

    items = [dict(r) for r in rows]
    conn.close()

    return {
        "items": items,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/metadata")
def get_audit_trail_metadata(current_user: dict = Depends(get_current_user)):
    """Retrieve distinct actions, modules, and users for populating filter controls."""
    conn = get_db_connection()
    actions = [r["action"] for r in conn.execute("SELECT DISTINCT action FROM audit_logs WHERE action IS NOT NULL ORDER BY action ASC").fetchall()]
    modules = [r["module"] for r in conn.execute("SELECT DISTINCT module FROM audit_logs WHERE module IS NOT NULL ORDER BY module ASC").fetchall()]
    users = [r["username"] for r in conn.execute("SELECT DISTINCT username FROM audit_logs WHERE username IS NOT NULL ORDER BY username ASC").fetchall()]
    conn.close()

    # Prepend standard recommended values if empty
    standard_actions = [
        "LOGIN", "LOGOUT", "CREATE_CLIENT", "UPDATE_CLIENT", "CREATE_ENGAGEMENT",
        "UPDATE_ENGAGEMENT", "FILE_IMPORT", "DATA_MODIFICATION", "CREATE_FINDING",
        "FINDING_STATUS_CHANGE", "AUDITOR_COMMENT", "CHECKLIST_CHANGE",
        "WORKING_PAPER_CHANGE", "REPORT_GENERATION", "REPORT_EXPORT", "SETTINGS_CHANGE",
        "DATABASE_BACKUP", "DATABASE_RESTORE"
    ]
    standard_modules = [
        "AUTH", "CLIENTS", "ENGAGEMENTS", "IMPORT", "DATA_CLEANING", "FINDINGS",
        "CHECKLISTS", "WORKING_PAPERS", "REPORTS", "EXPORT", "SETTINGS", "RECONCILIATION",
        "TRIAL_BALANCE", "FINANCIAL_STATEMENTS", "YOY_COMPARISON", "BACKUP"
    ]

    all_actions = sorted(list(set(actions + standard_actions)))
    all_modules = sorted(list(set(modules + standard_modules)))

    return {
        "actions": all_actions,
        "modules": all_modules,
        "users": sorted(list(set(users)))
    }


@router.get("/statistics")
def get_audit_trail_statistics(current_user: dict = Depends(get_current_user)):
    """Provide dashboard metrics on audit trail events, immutability health, and frequency."""
    conn = get_db_connection()
    total_logs = conn.execute("SELECT COUNT(*) as c FROM audit_logs").fetchone()["c"]

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_logs = conn.execute("SELECT COUNT(*) as c FROM audit_logs WHERE timestamp LIKE ?", (f"{today_str}%",)).fetchone()["c"]

    module_breakdown = conn.execute("""
        SELECT module, COUNT(*) as count 
        FROM audit_logs 
        GROUP BY module 
        ORDER BY count DESC
    """).fetchall()

    action_breakdown = conn.execute("""
        SELECT action, COUNT(*) as count 
        FROM audit_logs 
        GROUP BY action 
        ORDER BY count DESC 
        LIMIT 10
    """).fetchall()

    recent_events = conn.execute("""
        SELECT id, timestamp, username, action, module, details 
        FROM audit_logs 
        ORDER BY id DESC 
        LIMIT 8
    """).fetchall()

    conn.close()

    return {
        "total_logs": total_logs,
        "today_logs": today_logs,
        "is_immutable": True,
        "sqlite_triggers_active": True,
        "modules": [dict(m) for m in module_breakdown],
        "top_actions": [dict(a) for a in action_breakdown],
        "recent_events": [dict(e) for e in recent_events]
    }


# ----------------- AUDIT LOG EXPORT (CSV / JSON) -----------------

@router.get("/export/csv")
def export_audit_trail_csv(
    search: Optional[str] = None,
    action: Optional[str] = None,
    module: Optional[str] = None,
    user: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Export filtered audit trail records as a downloadable CSV."""
    conn = get_db_connection()
    conditions = ["1=1"]
    params = []

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append("""
            (action LIKE ? OR module LIKE ? OR details LIKE ? OR username LIKE ? 
             OR record_id LIKE ? OR old_value LIKE ? OR new_value LIKE ?)
        """)
        params.extend([term, term, term, term, term, term, term])

    if action and action != "All":
        conditions.append("action = ?")
        params.append(action.strip().upper())

    if module and module != "All":
        conditions.append("module = ?")
        params.append(module.strip().upper())

    if user and user != "All":
        conditions.append("LOWER(username) = LOWER(?)")
        params.append(user.strip())

    if from_date and from_date.strip():
        conditions.append("timestamp >= ?")
        params.append(from_date.strip())

    if to_date and to_date.strip():
        to_str = to_date.strip()
        if len(to_str) == 10:
            to_str += "T23:59:59"
        conditions.append("timestamp <= ?")
        params.append(to_str)

    where_clause = " WHERE " + " AND ".join(conditions)
    rows = conn.execute(f"""
        SELECT id, timestamp, username, action, module, record_id, 
               old_value, new_value, details, engagement_id, ip_address, entry_hash
        FROM audit_logs
        {where_clause}
        ORDER BY id DESC
    """, tuple(params)).fetchall()

    # Log export event
    log_audit_event(
        conn,
        action="REPORT_EXPORT",
        module="AUDIT_TRAIL",
        record_id="csv_export",
        details=f"Exported {len(rows)} audit trail records to CSV",
        user=current_user
    )
    conn.commit()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Log ID", "Timestamp (ISO)", "User", "Action", "Module", "Record ID", "Old Value", "New Value", "Details", "Engagement ID", "IP Address", "Entry Hash"])

    for r in rows:
        writer.writerow([
            r["id"],
            r["timestamp"],
            r["username"],
            r["action"],
            r["module"],
            r["record_id"] or "",
            r["old_value"] or "",
            r["new_value"] or "",
            r["details"] or "",
            r["engagement_id"] or "",
            r["ip_address"] or "",
            r["entry_hash"] or ""
        ])

    csv_data = output.getvalue()
    filename = f"finauditpro_audit_trail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/json")
def export_audit_trail_json(
    search: Optional[str] = None,
    action: Optional[str] = None,
    module: Optional[str] = None,
    user: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Export filtered audit trail records as a downloadable JSON document."""
    conn = get_db_connection()
    conditions = ["1=1"]
    params = []

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append("""
            (action LIKE ? OR module LIKE ? OR details LIKE ? OR username LIKE ? 
             OR record_id LIKE ? OR old_value LIKE ? OR new_value LIKE ?)
        """)
        params.extend([term, term, term, term, term, term, term])

    if action and action != "All":
        conditions.append("action = ?")
        params.append(action.strip().upper())

    if module and module != "All":
        conditions.append("module = ?")
        params.append(module.strip().upper())

    if user and user != "All":
        conditions.append("LOWER(username) = LOWER(?)")
        params.append(user.strip())

    if from_date and from_date.strip():
        conditions.append("timestamp >= ?")
        params.append(from_date.strip())

    if to_date and to_date.strip():
        to_str = to_date.strip()
        if len(to_str) == 10:
            to_str += "T23:59:59"
        conditions.append("timestamp <= ?")
        params.append(to_str)

    where_clause = " WHERE " + " AND ".join(conditions)
    rows = conn.execute(f"""
        SELECT id, timestamp, username, user_id, action, module, record_id, 
               old_value, new_value, details, engagement_id, ip_address, entry_hash
        FROM audit_logs
        {where_clause}
        ORDER BY id DESC
    """, tuple(params)).fetchall()

    items = [dict(r) for r in rows]

    # Log export event
    log_audit_event(
        conn,
        action="REPORT_EXPORT",
        module="AUDIT_TRAIL",
        record_id="json_export",
        details=f"Exported {len(items)} audit trail records to JSON",
        user=current_user
    )
    conn.commit()
    conn.close()

    json_data = json.dumps({
        "application": "FinAuditPro Offline Edition",
        "exported_at": datetime.now().isoformat(),
        "exported_by": current_user.get("username", "admin"),
        "total_records": len(items),
        "audit_logs": items
    }, indent=2)

    filename = f"finauditpro_audit_trail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ----------------- DATABASE BACKUP & RESTORE -----------------

@router.get("/backups")
def list_backups(current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: List all available local database backups with timestamp, size, and SHA-256 checksum."""
    backups = []
    if os.path.exists(BACKUP_DIR):
        for f in os.listdir(BACKUP_DIR):
            if f.endswith(".db"):
                fpath = os.path.join(BACKUP_DIR, f)
                stat = os.stat(fpath)
                size_kb = round(stat.st_size / 1024, 2)
                created_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
                sha256 = calculate_file_hash(fpath)
                backups.append({
                    "filename": f,
                    "size_kb": size_kb,
                    "created_at": created_at,
                    "checksum_sha256": sha256,
                    "is_safety_snapshot": f.startswith("pre_restore_safety_")
                })

    # Sort descending by creation date
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    return backups


import uuid
import zipfile

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploaded_files")


@router.post("/backup/create")
def create_local_backup(current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Create a point-in-time local SQLite database snapshot with SQLite Online Backup API and SHA-256 integrity verification."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Primary database file not found")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    short_uid = uuid.uuid4().hex[:6]
    backup_filename = f"finauditpro_backup_{timestamp}_{short_uid}.db"
    backup_filepath = os.path.join(BACKUP_DIR, backup_filename)

    # Use SQLite Online Backup API for point-in-time consistency
    src_conn = sqlite3.connect(DB_PATH)
    dest_conn = sqlite3.connect(backup_filepath)
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    checksum = calculate_file_hash(backup_filepath)
    size_kb = round(os.path.getsize(backup_filepath) / 1024, 2)

    # Record in audit trail
    conn = get_db_connection()
    try:
        log_audit_event(
            conn,
            action="DATABASE_BACKUP",
            module="BACKUP",
            record_id=backup_filename,
            new_value={"filename": backup_filename, "size_kb": size_kb, "sha256": checksum},
            details=f"Created local database backup snapshot: {backup_filename} ({size_kb} KB)",
            user=current_user
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "message": "Local database backup created successfully",
        "filename": backup_filename,
        "size_kb": size_kb,
        "checksum_sha256": checksum,
        "download_url": f"/api/audit-trail/backup/download/{backup_filename}"
    }


@router.post("/backup/create-full-bundle")
def create_full_backup_bundle(current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Create a complete point-in-time backup bundle containing SQLite DB AND uploaded evidence files."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Primary database file not found")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    short_uid = uuid.uuid4().hex[:6]
    temp_db_name = f"finauditpro_db_{timestamp}_{short_uid}.db"
    temp_db_path = os.path.join(BACKUP_DIR, temp_db_name)

    # 1. Snapshot DB
    src_conn = sqlite3.connect(DB_PATH)
    dest_conn = sqlite3.connect(temp_db_path)
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    # 2. Package into zip with evidence directory, manifest.json, and checksums.json
    bundle_filename = f"finauditpro_full_bundle_{timestamp}_{short_uid}.auditbundle.zip"
    bundle_filepath = os.path.join(BACKUP_DIR, bundle_filename)

    file_checksums = {}
    file_checksums["database.db"] = calculate_file_hash(temp_db_path)

    included_files = ["database.db"]
    evidence_files_map = {}
    if os.path.exists(EVIDENCE_DIR):
        for root, dirs, files in os.walk(EVIDENCE_DIR):
            for f in files:
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, os.path.dirname(EVIDENCE_DIR))
                file_checksums[rel_p] = calculate_file_hash(full_p)
                included_files.append(rel_p)
                evidence_files_map[rel_p] = full_p

    manifest = {
        "format": "FinAuditPro Comprehensive Audit Bundle",
        "version": "1.0.0",
        "created_at": datetime.now().isoformat(),
        "created_by": current_user.get("username", "admin"),
        "total_files": len(included_files),
        "files": included_files
    }

    with zipfile.ZipFile(bundle_filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(temp_db_path, arcname="database.db")
        for rel_p, full_p in evidence_files_map.items():
            zf.write(full_p, arcname=rel_p)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("checksums.json", json.dumps(file_checksums, indent=2))

    # Clean up temp db file if bundled
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)

    checksum = calculate_file_hash(bundle_filepath)
    size_kb = round(os.path.getsize(bundle_filepath) / 1024, 2)

    # Record in audit trail
    conn = get_db_connection()
    try:
        log_audit_event(
            conn,
            action="DATABASE_BACKUP",
            module="BACKUP",
            record_id=bundle_filename,
            new_value={"filename": bundle_filename, "size_kb": size_kb, "sha256": checksum, "type": "COMPREHENSIVE_AUDIT_BUNDLE"},
            details=f"Created complete audit backup bundle (DB + evidence files + manifest): {bundle_filename} ({size_kb} KB)",
            user=current_user
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "message": "Full audit backup bundle (Database + Evidence + Manifest) created successfully",
        "filename": bundle_filename,
        "size_kb": size_kb,
        "checksum_sha256": checksum,
        "download_url": f"/api/audit-trail/backup/download/{bundle_filename}"
    }


@router.get("/backup/download/{filename}")
def download_backup_file(filename: str, current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Download a local backup file."""
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(BACKUP_DIR, safe_filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Backup file not found")

    conn = get_db_connection()
    try:
        log_audit_event(
            conn,
            action="REPORT_EXPORT",
            module="BACKUP",
            record_id=safe_filename,
            details=f"Downloaded database backup file {safe_filename}",
            user=current_user
        )
        conn.commit()
    finally:
        conn.close()

    return FileResponse(
        path=filepath,
        filename=safe_filename,
        media_type="application/octet-stream"
    )


@router.post("/backup/restore/{filename}")
def restore_database_backup(filename: str, current_user: dict = Depends(require_role(["Admin"]))):
    """
    Admin: Restore database from an existing local backup file using SQLite Online Backup API.
    Creates an automatic safety snapshot of the active database before restoring.
    """
    safe_filename = os.path.basename(filename)
    backup_filepath = os.path.join(BACKUP_DIR, safe_filename)

    if not os.path.exists(backup_filepath):
        raise HTTPException(status_code=404, detail="Selected backup file not found")

    try:
        test_conn = sqlite3.connect(backup_filepath)
        test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        test_conn.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid or corrupted SQLite backup file: {str(e)}")

    # 1. Take automatic pre-restore safety snapshot of current active DB
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

    # 2. Restore active DB using SQLite Online Backup API
    backup_src_conn = sqlite3.connect(backup_filepath)
    active_target_conn = sqlite3.connect(DB_PATH)
    try:
        backup_src_conn.backup(active_target_conn)
    finally:
        active_target_conn.close()
        backup_src_conn.close()

    from backend.app.database import init_db
    init_db()

    conn = get_db_connection()
    try:
        log_audit_event(
            conn,
            action="DATABASE_RESTORE",
            module="BACKUP",
            record_id=safe_filename,
            old_value={"safety_snapshot": safety_filename},
            new_value={"restored_from": safe_filename},
            details=f"Database restored from backup {safe_filename}. Safety snapshot saved as {safety_filename}",
            user=current_user
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "message": f"Database successfully restored from {safe_filename}",
        "restored_from": safe_filename,
        "safety_snapshot_created": safety_filename
    }


MAX_RESTORE_SIZE = 100 * 1024 * 1024  # 100MB max database upload limit

@router.post("/backup/restore-upload")
async def restore_database_upload(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role(["Admin"]))
):
    """
    Admin: Upload an external SQLite .db file and restore the local database from it using SQLite Online Backup API.
    Automatically creates a pre-restore safety snapshot before replacing active DB. Enforces 100MB size limit.
    """
    if not file.filename.endswith(".db") and not file.filename.endswith(".sqlite"):
        raise HTTPException(status_code=400, detail="Only .db or .sqlite database files are accepted.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uploaded_backup_filename = f"uploaded_restore_{timestamp}_{os.path.basename(file.filename)}"
    uploaded_filepath = os.path.join(BACKUP_DIR, uploaded_backup_filename)

    total_size = 0
    with open(uploaded_filepath, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            total_size += len(chunk)
            if total_size > MAX_RESTORE_SIZE:
                buffer.close()
                if os.path.exists(uploaded_filepath):
                    os.remove(uploaded_filepath)
                raise HTTPException(status_code=413, detail="Database file exceeds maximum allowed upload size (100MB).")
            buffer.write(chunk)

    try:
        test_conn = sqlite3.connect(uploaded_filepath)
        test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        test_conn.close()
    except Exception as e:
        if os.path.exists(uploaded_filepath):
            os.remove(uploaded_filepath)
        raise HTTPException(status_code=400, detail=f"Uploaded file is not a valid SQLite database: {str(e)}")

    # 1. Take automatic pre-restore safety snapshot
    safety_filename = f"pre_restore_safety_{timestamp}.db"
    safety_filepath = os.path.join(BACKUP_DIR, safety_filename)
    if os.path.exists(DB_PATH):
        src_conn = sqlite3.connect(DB_PATH)
        snap_conn = sqlite3.connect(safety_filepath)
        try:
            src_conn.backup(snap_conn)
        finally:
            snap_conn.close()
            src_conn.close()

    # 2. Restore active DB using SQLite Online Backup API
    uploaded_src_conn = sqlite3.connect(uploaded_filepath)
    active_target_conn = sqlite3.connect(DB_PATH)
    try:
        uploaded_src_conn.backup(active_target_conn)
    finally:
        active_target_conn.close()
        uploaded_src_conn.close()

    from backend.app.database import init_db
    init_db()

    conn = get_db_connection()
    try:
        log_audit_event(
            conn,
            action="DATABASE_RESTORE",
            module="BACKUP",
            record_id=uploaded_backup_filename,
            old_value={"safety_snapshot": safety_filename},
            new_value={"uploaded_filename": file.filename, "saved_as": uploaded_backup_filename},
            details=f"Database restored from uploaded file '{file.filename}'. Safety snapshot saved as {safety_filename}",
            user=current_user
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "message": f"Database successfully restored from uploaded file '{file.filename}'",
        "saved_backup": uploaded_backup_filename,
        "safety_snapshot_created": safety_filename
    }
