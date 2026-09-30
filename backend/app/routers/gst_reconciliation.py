import io
import csv
import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from pydantic import BaseModel
from backend.app.auth import get_current_user
from backend.app.database import get_db_connection
from backend.app.services.gst_rule_config import (
    get_all_gst_rules, get_gst_rule, update_gst_rule, reset_gst_rules_to_default
)
from backend.app.services.gst_reconciliation_engine import run_gst_reconciliation

router = APIRouter(prefix="/api/gst-reconciliation", tags=["GST Reconciliation"])

class ExecuteGSTReconRequest(BaseModel):
    engagement_id: int
    source_a_file_id: Optional[int] = None
    source_a_type: str = "GSTR-2B (Portal Download)"
    source_b_file_id: Optional[int] = None
    source_b_type: str = "Purchase Register (Books)"
    ledger_name: Optional[str] = None
    title: Optional[str] = None

class UpdateGSTRuleRequest(BaseModel):
    config: Dict[str, Any]

class ItemActionRequest(BaseModel):
    status: str  # 'Accepted', 'Rejected', 'Marked for review'
    auditor_comment: Optional[str] = None

@router.get("/rules")
def list_gst_rules(current_user: dict = Depends(get_current_user)):
    """Retrieves all configurable GST rule definitions."""
    return get_all_gst_rules()

@router.put("/rules/{rule_key}")
def update_gst_rule_endpoint(
    rule_key: str,
    req: UpdateGSTRuleRequest,
    current_user: dict = Depends(get_current_user)
):
    """Updates the parameter configuration for a specific GST rule."""
    try:
        username = current_user.get("username", "admin")
        res = update_gst_rule(rule_key, req.config, updated_by=username)
        return {"success": True, "message": f"Rule '{rule_key}' updated successfully.", "data": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/rules/reset")
def reset_gst_rules_endpoint(current_user: dict = Depends(get_current_user)):
    """Resets all configurable GST rules to factory standard."""
    try:
        username = current_user.get("username", "admin")
        reset_gst_rules_to_default(updated_by=username)
        return {"success": True, "message": "All GST rules have been reset to factory defaults."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/execute")
def execute_gst_reconciliation_endpoint(
    req: ExecuteGSTReconRequest,
    current_user: dict = Depends(get_current_user)
):
    """Executes configurable GST reconciliation across selected datasets."""
    try:
        username = current_user.get("username", "admin")
        res = run_gst_reconciliation(
            engagement_id=req.engagement_id,
            source_a_file_id=req.source_a_file_id,
            source_a_type=req.source_a_type,
            source_b_file_id=req.source_b_file_id,
            source_b_type=req.source_b_type,
            ledger_name=req.ledger_name,
            recon_title=req.title,
            created_by=username
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GST Reconciliation Error: {str(e)}")

@router.get("/{recon_id}")
def get_gst_reconciliation_details(
    recon_id: int,
    match_category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
):
    """Fetches details and items for a specific GST reconciliation session."""
    conn = get_db_connection()
    recon_row = conn.execute("SELECT * FROM reconciliations WHERE id = ?", (recon_id,)).fetchone()
    if not recon_row:
        conn.close()
        raise HTTPException(status_code=404, detail="GST Reconciliation session not found")

    recon = dict(recon_row)

    query = "SELECT * FROM reconciliation_items WHERE recon_id = ?"
    params = [recon_id]

    if match_category and match_category != "ALL":
        query += " AND match_category = ?"
        params.append(match_category)
    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query += " AND (ref_a LIKE ? OR ref_b LIKE ? OR party_a LIKE ? OR party_b LIKE ? OR gstin_a LIKE ? OR gstin_b LIKE ? OR notes LIKE ? OR match_reason LIKE ?)"
        params.extend([term, term, term, term, term, term, term, term])

    query += " ORDER BY CASE match_category WHEN 'Mismatched' THEN 1 WHEN 'Missing in source A' THEN 2 WHEN 'Missing in source B' THEN 3 WHEN 'Partially matched' THEN 4 ELSE 5 END, id ASC"

    items_rows = conn.execute(query, tuple(params)).fetchall()
    recon["items"] = [dict(r) for r in items_rows]
    conn.close()
    return recon

@router.put("/{recon_id}/items/{item_id}/action")
def update_gst_item_action(
    recon_id: int,
    item_id: int,
    req: ItemActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Applies auditor review status and working-paper comments."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM reconciliation_items WHERE id = ? AND recon_id = ?", (item_id, recon_id)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")

    new_status = req.status
    if new_status not in ["Accepted", "Rejected", "Marked for review", "Suggested"]:
        new_status = "Accepted"

    conn.execute("""
        UPDATE reconciliation_items 
        SET status = ?, notes = COALESCE(?, notes)
        WHERE id = ?
    """, (new_status, req.auditor_comment, item_id))

    conn.commit()
    conn.close()
    return {"success": True, "message": f"GST Item status updated to '{new_status}'."}

@router.get("/{recon_id}/report/download")
def download_gst_reconciliation_report(recon_id: int):
    """Generates and downloads a detailed CSV GST Reconciliation report with both source values."""
    conn = get_db_connection()
    recon_row = conn.execute("SELECT * FROM reconciliations WHERE id = ?", (recon_id,)).fetchone()
    if not recon_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    recon = dict(recon_row)
    items = [dict(r) for r in conn.execute("SELECT * FROM reconciliation_items WHERE recon_id = ? ORDER BY id ASC", (recon_id,)).fetchall()]
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    # Report Header & Executive Metadata
    writer.writerow(["FinAuditPro - Goods & Services Tax (GST) Audit Reconciliation Report"])
    writer.writerow(["Title", recon["title"]])
    writer.writerow(["Dataset Scope", recon["bank_account_name"]])
    writer.writerow(["Date Generated", recon["created_at"]])
    writer.writerow(["Status", recon["status"]])
    writer.writerow(["Total Source A Invoices", recon["total_bank_tx"]])
    writer.writerow(["Total Source B Invoices", recon["total_book_tx"]])
    writer.writerow(["Matched Count", recon["matched_count"]])
    writer.writerow(["Discrepancies", recon["amount_diff_count"]])
    writer.writerow(["Total Source A Amount (INR)", recon["bank_balance"]])
    writer.writerow(["Total Source B Amount (INR)", recon["book_balance"]])
    writer.writerow(["Net Value Variance (INR)", recon["net_unreconciled_difference"]])
    writer.writerow(["Net Tax Variance (INR)", recon["unreconciled_amount"]])
    writer.writerow([])

    # Table Header with actual values from both sources
    writer.writerow([
        "Match Category",
        "Source A Invoice No",
        "Source B Invoice No",
        "Source A Date",
        "Source B Date",
        "Date Diff (Days)",
        "Source A GSTIN",
        "Source B GSTIN",
        "Source A Party Name",
        "Source B Party Name",
        "Source A Taxable Value (INR)",
        "Source B Taxable Value (INR)",
        "Taxable Value Diff (INR)",
        "Source A CGST (INR)",
        "Source B CGST (INR)",
        "CGST Diff (INR)",
        "Source A SGST (INR)",
        "Source B SGST (INR)",
        "SGST Diff (INR)",
        "Source A IGST (INR)",
        "Source B IGST (INR)",
        "IGST Diff (INR)",
        "Source A Total Value (INR)",
        "Source B Total Value (INR)",
        "Total Value Diff (INR)",
        "Reconciliation Finding & Audit Observation",
        "Auditor Review Status",
        "Auditor Working Paper Notes"
    ])

    for itm in items:
        writer.writerow([
            itm.get("match_category") or "Mismatched",
            itm.get("ref_a") or "",
            itm.get("ref_b") or "",
            itm.get("date_a") or "",
            itm.get("date_b") or "",
            itm.get("date_diff_days") or 0,
            itm.get("gstin_a") or "",
            itm.get("gstin_b") or "",
            itm.get("party_a") or "",
            itm.get("party_b") or "",
            itm.get("taxable_a") or 0.0,
            itm.get("taxable_b") or 0.0,
            itm.get("taxable_difference") or 0.0,
            itm.get("cgst_a") or 0.0,
            itm.get("cgst_b") or 0.0,
            itm.get("cgst_difference") or 0.0,
            itm.get("sgst_a") or 0.0,
            itm.get("sgst_b") or 0.0,
            itm.get("sgst_difference") or 0.0,
            itm.get("igst_a") or 0.0,
            itm.get("igst_b") or 0.0,
            itm.get("igst_difference") or 0.0,
            itm.get("amount_a") or 0.0,
            itm.get("amount_b") or 0.0,
            itm.get("difference") or 0.0,
            itm.get("match_reason") or "",
            itm.get("status") or "",
            itm.get("notes") or ""
        ])

    csv_data = output.getvalue()
    filename = f"GST_Reconciliation_Report_{recon_id}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
