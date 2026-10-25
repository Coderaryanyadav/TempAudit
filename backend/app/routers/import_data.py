import os
import shutil
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Response
from fastapi.responses import FileResponse, PlainTextResponse
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
    """Ensures engagement exists and current user has strict authorization to access it."""
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
    
    # Audit Staff must be explicitly assigned as assigned_staff_id or lead_auditor_id
    if role == "Audit Staff":
        user_id = current_user.get("id")
        if eng["assigned_staff_id"] == user_id or eng["lead_auditor_id"] == user_id:
            return eng
        raise HTTPException(status_code=403, detail="Access forbidden: You are not assigned to this engagement.")
        
    raise HTTPException(status_code=403, detail="Access forbidden: Insufficient permissions for this engagement.")

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
    try:
        eng = check_engagement_access(conn, engagement_id, current_user)
    finally:
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

        # WF-002: Idempotency guard - if already imported and not forced, return original import result
        existing_tx = conn.execute(
            "SELECT COUNT(*) as cnt FROM transactions WHERE file_id = ?", (req.file_id,)
        ).fetchone()
        existing_tx_count = existing_tx["cnt"] if existing_tx else 0
        if (file_info.get("successful_rows") or 0) > 0 and existing_tx_count > 0 and not getattr(req, "force_reimport", False):
            val_errors = json.loads(file_info.get("errors_json") or "[]")
            return {
                "status": "success",
                "file_id": req.file_id,
                "file_name": file_info["file_name"],
                "file_type": file_info["file_type"],
                "data_category": file_info.get("data_category") or category,
                "engagement_id": engagement_id,
                "imported_rows": file_info.get("successful_rows") or existing_tx_count,
                "total_rows": file_info.get("row_count") or existing_tx_count,
                "failed_rows": file_info.get("failed_rows") or 0,
                "warning_count": file_info.get("warning_count") or 0,
                "validation_report": {
                    "is_valid": (file_info.get("failed_rows") or 0) == 0,
                    "total_rows": file_info.get("row_count") or existing_tx_count,
                    "successful_rows": file_info.get("successful_rows") or existing_tx_count,
                    "failed_rows": file_info.get("failed_rows") or 0,
                    "warning_count": file_info.get("warning_count") or 0,
                    "errors": val_errors,
                    "warnings": []
                },
                "message": f"File '{file_info['file_name']}' was already imported. Returned existing import record.",
                "idempotent_replay": True
            }

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
            f["filename"] = f.get("file_name") or f.get("filename") or ""
            f["file_name"] = f["filename"]
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
        from backend.app.utils.audit_logger import log_audit_event
        log_audit_event(
            conn=conn,
            action="DELETE_FILE",
            module="IMPORT",
            record_id=file_id,
            user=current_user,
            engagement_id=file_info["engagement_id"],
            details=f"Deleted imported file '{file_info['file_name']}' and its associated transactions.",
            timestamp=now_str
        )

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

@router.get("/file/{file_id}/preview")
def preview_uploaded_file(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Returns top 50 parsed preview records and schema details for an uploaded file."""
    conn = get_db_connection()
    try:
        file_row = conn.execute("SELECT * FROM uploaded_files WHERE id = ?", (file_id,)).fetchone()
        if not file_row:
            raise HTTPException(status_code=404, detail="File record not found.")

        file_info = dict(file_row)
        check_engagement_access(conn, file_info["engagement_id"], current_user)
        
        # First try fetching from transactions if already imported
        tx_rows = conn.execute(
            "SELECT date, voucher_no, ledger, party_name, description, debit, credit, amount FROM transactions WHERE file_id = ? LIMIT 50",
            (file_id,)
        ).fetchall()
        
        if tx_rows:
            rows = [dict(r) for r in tx_rows]
            columns = ["date", "voucher_no", "ledger", "party_name", "description", "debit", "credit", "amount"]
        else:
            # Fall back to reading raw file preview
            file_path = file_info.get("file_path")
            if file_path and os.path.exists(file_path):
                raw_preview = read_file_preview(file_path, file_info.get("file_type", ".csv"), file_info.get("data_category"))
                columns = raw_preview.get("columns", [])
                rows = raw_preview.get("preview_rows", [])
            else:
                columns = []
                rows = []

        return {
            "file_id": file_id,
            "file_name": file_info.get("file_name"),
            "file_type": file_info.get("file_type"),
            "data_category": file_info.get("data_category"),
            "row_count": file_info.get("row_count", 0),
            "successful_rows": file_info.get("successful_rows", 0),
            "failed_rows": file_info.get("failed_rows", 0),
            "warning_count": file_info.get("warning_count", 0),
            "uploaded_by": file_info.get("uploaded_by"),
            "uploaded_at": file_info.get("uploaded_at"),
            "columns": columns,
            "preview_rows": rows
        }
    finally:
        conn.close()

@router.get("/file/{file_id}/download")
def download_uploaded_file(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Downloads the physical uploaded financial data file."""
    conn = get_db_connection()
    try:
        file_row = conn.execute("SELECT * FROM uploaded_files WHERE id = ?", (file_id,)).fetchone()
        if not file_row:
            raise HTTPException(status_code=404, detail="File record not found.")

        file_info = dict(file_row)
        check_engagement_access(conn, file_info["engagement_id"], current_user)
        file_path = file_info.get("file_path")

        if not file_path or not os.path.exists(file_path):
            # If transactions exist, synthesize CSV on the fly
            tx_rows = conn.execute(
                "SELECT date, voucher_no, ledger, party_name, description, debit, credit, amount FROM transactions WHERE file_id = ?",
                (file_id,)
            ).fetchall()
            if not tx_rows:
                raise HTTPException(status_code=404, detail="Physical file not found on disk.")
            import csv
            import io
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=["date", "voucher_no", "ledger", "party_name", "description", "debit", "credit", "amount"])
            writer.writeheader()
            for r in tx_rows:
                writer.writerow(dict(r))
            safe_name = os.path.basename(file_info.get("file_name", f"file_{file_id}.csv"))
            return Response(
                content=buf.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{safe_name}"'}
            )

        safe_name = os.path.basename(file_info.get("file_name", f"file_{file_id}"))
        return FileResponse(
            path=file_path,
            filename=safe_name,
            media_type="application/octet-stream"
        )
    finally:
        conn.close()

@router.get("/templates/{category}/download")
def download_sample_template(category: str):
    """Downloads a pre-formatted sample CSV template for the selected financial data category."""
    import io
    import csv

    cat_norm = category.lower().replace("_", " ").strip()
    buf = io.StringIO()

    if "bank" in cat_norm:
        fieldnames = ["Date", "Description / Narration", "Cheque / Ref No", "Withdrawal (Debit)", "Deposit (Credit)", "Balance"]
        sample_rows = [
            {"Date": "2025-04-05", "Description / Narration": "NEFT Inward - Client Settlement", "Cheque / Ref No": "NEFT123456", "Withdrawal (Debit)": "", "Deposit (Credit)": "250000.00", "Balance": "1250000.00"},
            {"Date": "2025-04-10", "Description / Narration": "Vendor Payment - Server Infra", "Cheque / Ref No": "CHQ004521", "Withdrawal (Debit)": "45000.00", "Deposit (Credit)": "", "Balance": "1205000.00"},
            {"Date": "2025-04-15", "Description / Narration": "Bank Charges & SMS Alert Fees", "Cheque / Ref No": "TXN987654", "Withdrawal (Debit)": "1500.00", "Deposit (Credit)": "", "Balance": "1203500.00"}
        ]
        filename = "Sample_Bank_Statement_Template.csv"
    elif "sales" in cat_norm:
        fieldnames = ["Invoice Date", "Invoice No", "Customer Name", "Customer GSTIN", "Taxable Value", "CGST", "SGST", "IGST", "Total Amount"]
        sample_rows = [
            {"Invoice Date": "2025-04-02", "Invoice No": "INV-2025-001", "Customer Name": "Enterprise Client Alpha", "Customer GSTIN": "27AAACB1234D1Z5", "Taxable Value": "100000.00", "CGST": "9000.00", "SGST": "9000.00", "IGST": "0.00", "Total Amount": "118000.00"},
            {"Invoice Date": "2025-04-12", "Invoice No": "INV-2025-002", "Customer Name": "Overseas Partner Beta", "Customer GSTIN": "URP", "Taxable Value": "250000.00", "CGST": "0.00", "SGST": "0.00", "IGST": "45000.00", "Total Amount": "295000.00"}
        ]
        filename = "Sample_Sales_Register_Template.csv"
    elif "purchase" in cat_norm or "gst" in cat_norm:
        fieldnames = ["Bill Date", "Invoice No", "Vendor Name", "Supplier GSTIN", "Taxable Value", "CGST", "SGST", "IGST", "Total Amount"]
        sample_rows = [
            {"Bill Date": "2025-04-04", "Invoice No": "PUR-2025-010", "Vendor Name": "Cloud Services Provider", "Supplier GSTIN": "29AABCB5678E1Z2", "Taxable Value": "50000.00", "CGST": "4500.00", "SGST": "4500.00", "IGST": "0.00", "Total Amount": "59000.00"},
            {"Bill Date": "2025-04-18", "Invoice No": "PUR-2025-011", "Vendor Name": "Office Supplies Corp", "Supplier GSTIN": "27AACCB9999F1Z1", "Taxable Value": "12000.00", "CGST": "1080.00", "SGST": "1080.00", "IGST": "0.00", "Total Amount": "14160.00"}
        ]
        filename = "Sample_Purchase_Register_Template.csv"
    elif "trial" in cat_norm:
        fieldnames = ["Account Code", "Ledger Name", "Group / Classification", "Opening Balance", "Debit Movement", "Credit Movement", "Closing Balance"]
        sample_rows = [
            {"Account Code": "1001", "Ledger Name": "Cash in Hand", "Group / Classification": "Current Assets", "Opening Balance": "50000.00", "Debit Movement": "120000.00", "Credit Movement": "90000.00", "Closing Balance": "80000.00"},
            {"Account Code": "2001", "Ledger Name": "Sales Revenue", "Group / Classification": "Revenue", "Opening Balance": "0.00", "Debit Movement": "0.00", "Credit Movement": "1500000.00", "Closing Balance": "1500000.00"}
        ]
        filename = "Sample_Trial_Balance_Template.csv"
    else:
        # General Ledger
        fieldnames = ["Date", "Voucher No", "Ledger", "Party Name", "Description", "Debit", "Credit", "Amount"]
        sample_rows = [
            {"Date": "2025-04-02", "Voucher No": "JV-001", "Ledger": "Consulting Fees", "Party Name": "Alpha Advisers", "Description": "Consulting charges for legal compliance", "Debit": "25000.00", "Credit": "0.00", "Amount": "25000.00"},
            {"Date": "2025-04-05", "Voucher No": "BNK-001", "Ledger": "HDFC Bank Ltd", "Party Name": "Alpha Advisers", "Description": "Payment via NEFT for consulting", "Debit": "0.00", "Credit": "25000.00", "Amount": "25000.00"},
            {"Date": "2025-04-12", "Voucher No": "SAL-001", "Ledger": "Sales Revenue", "Party Name": "Enterprise Client 1", "Description": "Software SaaS license billing", "Debit": "0.00", "Credit": "100000.00", "Amount": "100000.00"}
        ]
        filename = "Sample_General_Ledger_Template.csv"

    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(sample_rows)

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

