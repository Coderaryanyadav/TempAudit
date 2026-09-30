import os
import shutil
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Response
from fastapi.responses import PlainTextResponse
from backend.app.schemas import ColumnMappingRequest, ValidateMappingRequest
from backend.app.auth import get_current_user, require_role, normalize_role
from backend.app.database import get_db_connection
from backend.app.parsers.excel_csv import (
    read_file_preview,
    validate_imported_dataframe,
    import_and_save_transactions,
    generate_error_report_csv,
    parse_raw_dataframe,
    SUPPORTED_DATA_CATEGORIES
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["Financial Data Import"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploaded_files")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_UPLOAD_SIZE = 50 * 1024 * 1024 # 50 MB maximum upload size limit

def check_engagement_access(conn, engagement_id: int, current_user: dict):
    """Ensures engagement exists and current user has authorization to access it."""
    eng = conn.execute("""
        SELECT e.*, c.name as client_name
        FROM engagements e
        JOIN clients c ON e.client_id = c.id
        WHERE e.id = ?
    """, (engagement_id,)).fetchone()
    
    if not eng:
        raise HTTPException(status_code=404, detail="Selected audit engagement not found.")
    
    role = normalize_role(current_user.get("role"))
    if role in ["Admin", "Auditor"]:
        return eng
    
    # Audit Staff can access assigned engagements or general firm engagements
    if role == "Audit Staff":
        if eng["assigned_staff_id"] and eng["assigned_staff_id"] != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Access forbidden: You are not assigned to this engagement.")
        return eng
        
    return eng

@router.get("/categories")
def get_supported_categories():
    """Returns the list of supported financial data categories."""
    return {"categories": SUPPORTED_DATA_CATEGORIES}

@router.post("/upload")
async def upload_file(
    engagement_id: int = Form(...),
    data_category: Optional[str] = Form("General Ledger"),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role(["Admin", "Auditor", "Audit Staff"]))
):
    """
    Step 3-7 of workflow: Upload file, detect file type, preview data,
    detect columns, and suggest intelligent column mapping with size and access controls.
    """
    original_filename = os.path.basename(file.filename or "uploaded_file")
    file_ext = os.path.splitext(original_filename)[1].lower()

    if file_ext not in [".xlsx", ".xls", ".csv", ".json", ".pdf"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. FinAuditPro supports CSV (.csv), Excel (.xlsx, .xls), PDF (.pdf), and JSON (.json)."
        )

    conn = get_db_connection()
    eng = check_engagement_access(conn, engagement_id, current_user)
    conn.close()

    # Enforce upload size limit and use secure UUID filenames
    unique_id = uuid.uuid4().hex
    saved_filename = f"eng_{engagement_id}_{unique_id}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    try:
        total_bytes = 0
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024): # 1MB chunks
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE:
                    buffer.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    raise HTTPException(status_code=413, detail=f"File exceeds maximum upload limit of {MAX_UPLOAD_SIZE // (1024 * 1024)} MB.")
                buffer.write(chunk)

        # Generate preview first before persisting to database
        preview = read_file_preview(file_path, file_ext, data_category)
    except HTTPException:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        raise
    except Exception as e:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        logger.exception("Error parsing uploaded file %s", original_filename)
        raise HTTPException(status_code=400, detail=f"Could not read or parse the uploaded file: {str(e)}")

    conn = get_db_connection()
    try:
        now_str = datetime.now().isoformat()
        cursor = conn.execute("""
        INSERT INTO uploaded_files (
            engagement_id, file_name, file_type, file_path, data_category,
            row_count, successful_rows, failed_rows, warning_count, uploaded_by, uploaded_at
        ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?)
        """, (
            engagement_id,
            original_filename,
            file_ext,
            file_path,
            data_category or "General Ledger",
            current_user.get("username", "auditor"),
            now_str
        ))
        file_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    return {
        "file_id": file_id,
        "file_name": original_filename,
        "file_type": file_ext,
        "data_category": data_category or "General Ledger",
        "engagement_id": engagement_id,
        "client_name": eng["client_name"],
        "engagement_title": eng["title"],
        "financial_year": eng["financial_year"],
        "columns": preview["columns"],
        "suggested_mapping": preview["suggested_mapping"],
        "mapping_status": preview["mapping_status"],
        "preview_rows": preview["preview_rows"],
        "estimated_rows": preview["estimated_total_rows"],
        "supported_categories": SUPPORTED_DATA_CATEGORIES
    }

@router.post("/validate")
def validate_mapping(
    req: ValidateMappingRequest,
    current_user: dict = Depends(require_role(["Admin", "Auditor", "Audit Staff"]))
):
    """
    Step 9 of workflow: Performs pre-import validation of financial data against mapping
    without persisting to transactions table.
    """
    conn = get_db_connection()
    try:
        file_row = conn.execute("SELECT * FROM uploaded_files WHERE id = ?", (req.file_id,)).fetchone()
        if not file_row:
            raise HTTPException(status_code=404, detail="Uploaded file record not found.")

        file_info = dict(file_row)
        check_engagement_access(conn, file_info["engagement_id"], current_user)
    finally:
        conn.close()

    try:
        df = parse_raw_dataframe(file_info["file_path"], file_info["file_type"])
        df.columns = [str(c).strip() for c in df.columns]
        val_report = validate_imported_dataframe(df, req.column_mapping, req.data_category or file_info["data_category"])
        return {
            "status": "success",
            "file_id": req.file_id,
            "file_name": file_info["file_name"],
            "validation_report": val_report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Validation error for file_id %s", req.file_id)
        raise HTTPException(status_code=500, detail="Data validation failed due to invalid column format or data structure.")

@router.post("/apply-mapping")
def apply_mapping(
    req: ColumnMappingRequest,
    current_user: dict = Depends(require_role(["Admin", "Auditor", "Audit Staff"]))
):
    """
    Step 10-11 of workflow: Validates, imports, saves transactions with original values preserved,
    updates ledgers summary, records import logs, and produces complete import summary.
    """
    conn = get_db_connection()
    try:
        file_row = conn.execute("SELECT * FROM uploaded_files WHERE id = ?", (req.file_id,)).fetchone()
        if not file_row:
            raise HTTPException(status_code=404, detail="Uploaded file record not found.")

        file_info = dict(file_row)
        engagement_id = file_info["engagement_id"]
        check_engagement_access(conn, engagement_id, current_user)

        category = req.data_category or file_info.get("data_category") or "General Ledger"
        import_result = import_and_save_transactions(
            engagement_id=engagement_id,
            file_id=req.file_id,
            file_path=file_info["file_path"],
            file_type=file_info["file_type"],
            mapping=req.column_mapping,
            data_category=category
        )

        from backend.app.utils.audit_logger import log_audit_event
        log_audit_event(
            conn,
            action="FILE_IMPORT",
            module="IMPORT",
            record_id=req.file_id,
            engagement_id=engagement_id,
            new_value={
                "file_id": req.file_id,
                "file_name": file_info["file_name"],
                "file_type": file_info["file_type"],
                "data_category": category,
                "imported_rows": import_result["imported_rows"],
                "total_rows": import_result["total_rows"],
                "failed_rows": import_result["failed_rows"],
                "warning_count": import_result["warning_count"]
            },
            details=f"Imported {import_result['imported_rows']} transactions from '{file_info['file_name']}' ({category}). Warnings: {import_result['warning_count']}, Failed: {import_result['failed_rows']}.",
            user=current_user
        )

        conn.commit()

        return {
            "status": "success",
            "file_id": req.file_id,
            "file_name": file_info["file_name"],
            "file_type": file_info["file_type"],
            "data_category": category,
            "engagement_id": engagement_id,
            "imported_rows": import_result["imported_rows"],
            "total_rows": import_result["total_rows"],
            "failed_rows": import_result["failed_rows"],
            "warning_count": import_result["warning_count"],
            "validation_report": import_result["validation_report"],
            "message": f"Successfully validated and imported {import_result['imported_rows']} financial transactions."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error importing financial records for file_id %s", req.file_id)
        raise HTTPException(status_code=500, detail="Error importing and saving financial records into ledger.")
    finally:
        conn.close()

@router.get("/files/{engagement_id}")
def list_uploaded_files(
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Lists all uploaded financial data files with import logs and error summary for an engagement."""
    conn = get_db_connection()
    try:
        check_engagement_access(conn, engagement_id, current_user)
        rows = conn.execute("SELECT * FROM uploaded_files WHERE engagement_id = ? ORDER BY id DESC", (engagement_id,)).fetchall()
        files = []
        for r in rows:
            f = dict(r)
            f.pop("file_path", None)
            if f.get("errors_json"):
                try:
                    f["errors_data"] = json.loads(f["errors_json"])
                except Exception:
                    f["errors_data"] = {}
            if f.get("mapping_json"):
                try:
                    f["mapping"] = json.loads(f["mapping_json"])
                except Exception:
                    f["mapping"] = {}
            files.append(f)
        return files
    finally:
        conn.close()

@router.get("/errors/{file_id}/download")
def download_error_report(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Generates and downloads CSV error log for a specific file import."""
    conn = get_db_connection()
    try:
        file_row = conn.execute("SELECT * FROM uploaded_files WHERE id = ?", (file_id,)).fetchone()
        if not file_row:
            raise HTTPException(status_code=404, detail="File record not found.")

        file_info = dict(file_row)
        check_engagement_access(conn, file_info["engagement_id"], current_user)
    finally:
        conn.close()

    errors_list = []
    if file_info.get("errors_json"):
        try:
            parsed = json.loads(file_info["errors_json"])
            errors_list.extend(parsed.get("errors", []))
            errors_list.extend(parsed.get("warnings", []))
        except Exception:
            pass

    csv_content = generate_error_report_csv(errors_list)
    safe_name = os.path.splitext(file_info["file_name"])[0]
    filename = f"Import_Errors_{safe_name}_{file_id}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.delete("/files/{file_id}")
def delete_uploaded_file(
    file_id: int,
    current_user: dict = Depends(require_role(["Admin", "Auditor"]))
):
    """Deletes an uploaded file and all its associated imported transactions."""
    conn = get_db_connection()
    try:
        file_row = conn.execute("SELECT * FROM uploaded_files WHERE id = ?", (file_id,)).fetchone()
        if not file_row:
            raise HTTPException(status_code=404, detail="File record not found.")

        file_info = dict(file_row)
        check_engagement_access(conn, file_info["engagement_id"], current_user)
        now_str = datetime.now().isoformat()

        # Delete transactions
        conn.execute("DELETE FROM transactions WHERE file_id = ?", (file_id,))
        # Delete uploaded_files entry
        conn.execute("DELETE FROM uploaded_files WHERE id = ?", (file_id,))

        # Audit log
        conn.execute("""
        INSERT INTO audit_logs (user_id, username, action, entity_type, entity_id, details, timestamp)
        VALUES (?, ?, 'DELETE_FILE', 'engagement', ?, ?, ?)
        """, (
            current_user.get("id"),
            current_user.get("username", "auditor"),
            file_info["engagement_id"],
            f"Deleted imported file '{file_info['file_name']}' and its associated transactions.",
            now_str
        ))

        conn.commit()

        # Remove disk file securely
        try:
            if os.path.exists(file_info["file_path"]):
                os.remove(file_info["file_path"])
        except Exception:
            logger.warning("Could not delete physical file at %s", file_info.get("file_path"))

        return {"message": f"File '{file_info['file_name']}' and its transactions deleted successfully."}
    finally:
        conn.close()

