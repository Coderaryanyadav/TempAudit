import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from backend.app.schemas import CleaningLogReviewRequest, NormalizationPreviewRequest
from backend.app.auth import get_current_user, require_role, require_engagement_access
from backend.app.database import get_db_connection
from backend.app.services.data_normalizer import (
    normalize_date,
    normalize_monetary_amount,
    normalize_entity_name,
    normalize_invoice_voucher,
    normalize_gstin
)

router = APIRouter(prefix="/api/cleaning", tags=["Data Cleaning & Normalization"])

@router.get("/summary/{engagement_id}")
def get_cleaning_summary(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """Returns aggregated summary metrics of all automatic and reviewed data transformations."""
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    
    total = conn.execute("SELECT COUNT(*) as c FROM data_cleaning_logs WHERE engagement_id = ?", (engagement_id,)).fetchone()["c"]
    questionable = conn.execute("SELECT COUNT(*) as c FROM data_cleaning_logs WHERE engagement_id = ? AND is_questionable = 1", (engagement_id,)).fetchone()["c"]
    reviewed = conn.execute("SELECT COUNT(*) as c FROM data_cleaning_logs WHERE engagement_id = ? AND review_status != 'Auto-Applied'", (engagement_id,)).fetchone()["c"]

    # Field breakdown
    field_rows = conn.execute("""
        SELECT field_name, COUNT(*) as count, SUM(is_questionable) as quest_count
        FROM data_cleaning_logs
        WHERE engagement_id = ?
        GROUP BY field_name
        ORDER BY count DESC
    """, (engagement_id,)).fetchall()
    field_breakdown = [dict(r) for r in field_rows]

    # Rule breakdown
    rule_rows = conn.execute("""
        SELECT transformation_rule, COUNT(*) as count
        FROM data_cleaning_logs
        WHERE engagement_id = ?
        GROUP BY transformation_rule
        ORDER BY count DESC
    """, (engagement_id,)).fetchall()
    rule_breakdown = [dict(r) for r in rule_rows]

    conn.close()

    return {
        "engagement_id": engagement_id,
        "total_transformations": total,
        "questionable_count": questionable,
        "reviewed_count": reviewed,
        "auto_applied_count": total - reviewed,
        "field_breakdown": field_breakdown,
        "rule_breakdown": rule_breakdown
    }

@router.get("/logs/{engagement_id}")
def list_cleaning_logs(
    engagement_id: int,
    field_name: Optional[str] = None,
    is_questionable: Optional[int] = None,
    transformation_rule: Optional[str] = None,
    review_status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Lists data cleaning and normalization transformation logs with multi-criteria filtering."""
    require_engagement_access(engagement_id, current_user)
    limit = min(max(1, limit), 500)
    offset = max(0, offset)
    conn = get_db_connection()
    query = """
        SELECT l.*, f.file_name, t.voucher_no as txn_voucher, t.ledger as txn_ledger
        FROM data_cleaning_logs l
        LEFT JOIN uploaded_files f ON l.file_id = f.id
        LEFT JOIN transactions t ON l.transaction_id = t.id
        WHERE l.engagement_id = ?
    """
    params = [engagement_id]

    if field_name and field_name != "All":
        query += " AND l.field_name = ?"
        params.append(field_name)

    if is_questionable is not None:
        query += " AND l.is_questionable = ?"
        params.append(is_questionable)

    if transformation_rule and transformation_rule != "All":
        query += " AND l.transformation_rule = ?"
        params.append(transformation_rule)

    if review_status and review_status != "All":
        query += " AND l.review_status = ?"
        params.append(review_status)

    if search:
        query += " AND (l.original_value LIKE ? OR l.normalized_value LIKE ? OR l.transformation_rule LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])

    # Count total matching
    count_query = f"SELECT COUNT(*) as cnt FROM ({query})"
    total_matching = conn.execute(count_query, tuple(params)).fetchone()["cnt"]

    query += " ORDER BY l.is_questionable DESC, l.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, tuple(params)).fetchall()
    logs = [dict(r) for r in rows]
    conn.close()

    return {
        "engagement_id": engagement_id,
        "total": total_matching,
        "limit": limit,
        "offset": offset,
        "logs": logs
    }

@router.put("/logs/{log_id}/review")
def review_cleaning_log(
    log_id: int,
    req: CleaningLogReviewRequest,
    current_user: dict = Depends(require_role(["Admin", "Auditor"]))
):
    """
    Allows the auditor to review, accept, override, or revert an automatic normalization transformation.
    Updates the database record and synchronizes the active transaction.
    """
    if req.action not in ["Accepted", "Overridden", "Reverted"]:
        raise HTTPException(status_code=400, detail="Action must be 'Accepted', 'Overridden', or 'Reverted'.")

    conn = get_db_connection()
    log_row = conn.execute("SELECT * FROM data_cleaning_logs WHERE id = ?", (log_id,)).fetchone()
    if not log_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Cleaning log record not found.")

    log = dict(log_row)
    require_engagement_access(log["engagement_id"], current_user)
    now_str = datetime.now().isoformat()

    new_normalized_val = log["normalized_value"]
    if req.action == "Reverted":
        new_normalized_val = log["original_value"]
    elif req.action == "Overridden" and req.custom_normalized_value is not None:
        new_normalized_val = req.custom_normalized_value.strip()

    # Update cleaning log record
    conn.execute("""
    UPDATE data_cleaning_logs SET
        normalized_value = ?,
        review_status = ?,
        auditor_comment = ?,
        reviewed_by = ?,
        reviewed_at = ?
    WHERE id = ?
    """, (
        new_normalized_val,
        req.action,
        req.auditor_comment or log.get("auditor_comment", ""),
        current_user.get("full_name") or current_user.get("username", "Auditor"),
        now_str,
        log_id
    ))

    # Synchronize transaction record if linked
    if log.get("transaction_id") and log.get("field_name"):
        field = log["field_name"]
        tx_id = log["transaction_id"]
        
        # Valid column check
        valid_cols = ["date", "ledger", "party_name", "voucher_no", "invoice_no", "gstin", "description", "debit", "credit", "amount"]
        if field in valid_cols:
            if field in ["debit", "credit", "amount"]:
                try:
                    num_val = float(str(new_normalized_val).replace(",", "").strip())
                    conn.execute(f"UPDATE transactions SET {field} = ? WHERE id = ?", (num_val, tx_id))
                except Exception:
                    pass
            else:
                conn.execute(f"UPDATE transactions SET {field} = ? WHERE id = ?", (new_normalized_val, tx_id))

    # Audit log
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action="REVIEW_NORMALIZATION",
        module="DATA_CLEANING",
        record_id=log_id,
        user=current_user,
        engagement_id=log.get("engagement_id"),
        details=f"Auditor reviewed transformation #{log_id} ({log['field_name']}): {req.action}. Value set to '{new_normalized_val}'.",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "log_id": log_id,
        "action": req.action,
        "normalized_value": new_normalized_val,
        "message": f"Transformation #{log_id} has been {req.action.lower()}."
    }

@router.post("/normalize-preview")
def test_normalization_preview(req: NormalizationPreviewRequest, current_user: dict = Depends(get_current_user)):
    """
    Interactive test tool for auditors to preview how a raw string is deterministically
    cleaned and transformed according to FinAuditPro normalization rules.
    """
    field = req.field_name.lower().strip()
    raw = req.raw_value

    if field in ["date", "txn_date", "voucher_date", "invoice_date", "payment_date"]:
        norm, rule, is_quest, conf = normalize_date(raw)
    elif field in ["amount", "debit", "credit", "tax", "tax_amount", "balance"]:
        num_val, norm, rule, is_quest, conf = normalize_monetary_amount(raw)
    elif field in ["ledger", "party_name", "party", "account", "customer", "vendor"]:
        norm, rule, is_quest, conf = normalize_entity_name(raw)
    elif field in ["voucher_no", "invoice_no", "ref_no", "reference"]:
        norm, rule, is_quest, conf = normalize_invoice_voucher(raw)
    elif field in ["gstin", "gst"]:
        norm, rule, is_quest, conf = normalize_gstin(raw)
    else:
        norm = raw.strip()
        rule = "DEFAULT_WHITESPACE_TRIM"
        is_quest = 0
        conf = 1.0

    return {
        "field_name": field,
        "original_value": raw,
        "normalized_value": norm,
        "transformation_rule": rule,
        "is_questionable": is_quest,
        "confidence_score": conf,
        "is_transformed": (str(raw).strip() != str(norm).strip())
    }
