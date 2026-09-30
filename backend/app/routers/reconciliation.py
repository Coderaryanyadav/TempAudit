import io
import csv
import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from pydantic import BaseModel
from backend.app.auth import get_current_user
from backend.app.database import get_db_connection
from backend.app.services.bank_reconciliation_engine import run_bank_reconciliation

router = APIRouter(prefix="/api/reconciliation", tags=["Reconciliation"])

class ExecuteBRSRequest(BaseModel):
    engagement_id: int
    bank_ledger_name: Optional[str] = None
    file_b_id: Optional[int] = None
    title: Optional[str] = None

class ManualMatchRequest(BaseModel):
    book_item_id: int
    bank_item_id: int
    auditor_notes: Optional[str] = None

@router.get("/{engagement_id}")
def list_reconciliations(engagement_id: int):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM reconciliations WHERE engagement_id = ? ORDER BY id DESC",
        (engagement_id,)
    ).fetchall()
    recons = [dict(r) for r in rows]
    conn.close()
    return recons

@router.get("/bank-ledgers/{engagement_id}")
def get_bank_ledgers(engagement_id: int):
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT DISTINCT ledger FROM transactions 
        WHERE engagement_id = ? AND ledger IS NOT NULL AND ledger != ''
        ORDER BY ledger ASC
    """, (engagement_id,)).fetchall()
    all_ledgers = [r["ledger"] for r in rows]
    
    # Filter bank-like ledgers first
    bank_ledgers = [l for l in all_ledgers if any(k in l.lower() for k in ["bank", "hdfc", "sbi", "icici", "axis", "kotak", "current", "savings", "c/a", "s/a"])]
    if not bank_ledgers:
        bank_ledgers = all_ledgers
    conn.close()
    return {"bank_ledgers": bank_ledgers, "all_ledgers": all_ledgers}

@router.get("/details/{recon_id}")
def get_reconciliation_details(
    recon_id: int,
    match_level: Optional[str] = None,
    item_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
):
    conn = get_db_connection()
    recon_row = conn.execute("SELECT * FROM reconciliations WHERE id = ?", (recon_id,)).fetchone()
    if not recon_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    
    recon = dict(recon_row)
    
    query = "SELECT * FROM reconciliation_items WHERE recon_id = ?"
    params = [recon_id]

    if match_level and match_level != "ALL":
        query += " AND match_level = ?"
        params.append(match_level)
    if item_type and item_type != "ALL":
        query += " AND item_type = ?"
        params.append(item_type)
    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query += " AND (party_a LIKE ? OR party_b LIKE ? OR description_a LIKE ? OR description_b LIKE ? OR ref_a LIKE ? OR ref_b LIKE ? OR match_reason LIKE ?)"
        params.extend([term, term, term, term, term, term, term])

    query += " ORDER BY CASE status WHEN 'Suggested' THEN 1 WHEN 'Unmatched' THEN 2 WHEN 'Manual Matched' THEN 3 WHEN 'Confirmed' THEN 4 ELSE 5 END, id ASC"

    items_rows = conn.execute(query, tuple(params)).fetchall()
    recon["items"] = [dict(i) for i in items_rows]
    conn.close()
    return recon

@router.post("/execute")
def execute_reconciliation_endpoint(
    req: ExecuteBRSRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        res = run_bank_reconciliation(
            engagement_id=req.engagement_id,
            bank_ledger_name=req.bank_ledger_name,
            file_b_id=req.file_b_id,
            title=req.title,
            created_by=current_user.get("username", "admin")
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BRS Execution Error: {str(e)}")

@router.put("/{recon_id}/items/{item_id}/confirm")
def confirm_match_item(
    recon_id: int,
    item_id: int,
    current_user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM reconciliation_items WHERE id = ? AND recon_id = ?", (item_id, recon_id)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Reconciliation item not found")
    
    conn.execute("UPDATE reconciliation_items SET status = 'Confirmed', notes = 'Manually confirmed by auditor' WHERE id = ?", (item_id,))
    
    # Update manual_confirmed_count in reconciliations table
    conn.execute("""
        UPDATE reconciliations
        SET manual_confirmed_count = (SELECT COUNT(*) FROM reconciliation_items WHERE recon_id = ? AND status = 'Confirmed')
        WHERE id = ?
    """, (recon_id, recon_id))
    
    conn.commit()
    conn.close()
    return {"success": True, "message": "Match confirmed successfully."}

@router.put("/{recon_id}/items/{item_id}/reject")
def reject_match_item(
    recon_id: int,
    item_id: int,
    current_user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM reconciliation_items WHERE id = ? AND recon_id = ?", (item_id, recon_id)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Reconciliation item not found")
    
    conn.execute("UPDATE reconciliation_items SET status = 'Rejected', match_level = 'UNMATCHED', notes = 'Match rejected by auditor - items unlinked' WHERE id = ?", (item_id,))
    
    conn.commit()
    conn.close()
    return {"success": True, "message": "Match rejected. Items unlinked."}

@router.post("/{recon_id}/manual-match")
def manual_match_items(
    recon_id: int,
    req: ManualMatchRequest,
    current_user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    book_item = conn.execute("SELECT * FROM reconciliation_items WHERE id = ? AND recon_id = ?", (req.book_item_id, recon_id)).fetchone()
    bank_item = conn.execute("SELECT * FROM reconciliation_items WHERE id = ? AND recon_id = ?", (req.bank_item_id, recon_id)).fetchone()
    
    if not book_item or not bank_item:
        conn.close()
        raise HTTPException(status_code=404, detail="One or both reconciliation items not found")
    
    amt_a = float(book_item["amount_a"] or 0.0)
    amt_b = float(bank_item["amount_b"] or 0.0)
    diff = round(abs(amt_a - amt_b), 2)
    
    # Create unified manually matched record
    conn.execute("""
        INSERT INTO reconciliation_items (
            recon_id, book_tx_id, bank_tx_id, date_a, date_b, ref_a, ref_b,
            party_a, party_b, description_a, description_b, amount_a, amount_b,
            difference, match_level, match_score, match_reason, item_type, status, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'EXACT MATCH', 100.0, 'Manually matched and verified by auditor', 'MATCHED', 'Manual Matched', ?)
    """, (
        recon_id, book_item["book_tx_id"], bank_item["bank_tx_id"],
        book_item["date_a"], bank_item["date_b"], book_item["ref_a"], bank_item["ref_b"],
        book_item["party_a"], bank_item["party_b"], book_item["description_a"], bank_item["description_b"],
        amt_a, amt_b, diff, req.auditor_notes or "Auditor confirmed manual cross-matching"
    ))
    
    # Delete original unmatched records
    conn.execute("DELETE FROM reconciliation_items WHERE id IN (?, ?)", (req.book_item_id, req.bank_item_id))
    
    # Update reconciliation summary counts
    conn.execute("""
        UPDATE reconciliations
        SET matched_count = (SELECT COUNT(*) FROM reconciliation_items WHERE recon_id = ? AND status IN ('Confirmed', 'Manual Matched', 'Suggested')),
            unmatched_bank_count = (SELECT COUNT(*) FROM reconciliation_items WHERE recon_id = ? AND status = 'Unmatched' AND amount_a = 0),
            unmatched_book_count = (SELECT COUNT(*) FROM reconciliation_items WHERE recon_id = ? AND status = 'Unmatched' AND amount_b = 0)
        WHERE id = ?
    """, (recon_id, recon_id, recon_id, recon_id))
    
    conn.commit()
    conn.close()
    return {"success": True, "message": "Manual match created successfully."}

@router.get("/{recon_id}/report/download")
def download_brs_report(recon_id: int):
    conn = get_db_connection()
    recon_row = conn.execute("SELECT * FROM reconciliations WHERE id = ?", (recon_id,)).fetchone()
    if not recon_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    
    recon = dict(recon_row)
    items = [dict(r) for r in conn.execute("SELECT * FROM reconciliation_items WHERE recon_id = ? ORDER BY status ASC, id ASC", (recon_id,)).fetchall()]
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header / Meta
    writer.writerow(["FinAuditPro - Bank Reconciliation Statement (BRS)"])
    writer.writerow(["Reconciliation Title", recon["title"]])
    writer.writerow(["Bank Account Ledger", recon["bank_account_name"]])
    writer.writerow(["Date Generated", recon["created_at"]])
    writer.writerow(["Status", recon["status"]])
    writer.writerow([])

    # BRS Roll-Forward Summary Schedule
    writer.writerow(["--- BANK RECONCILIATION SUMMARY COMPUTATION ---"])
    writer.writerow(["Balance as per Bank Statement", recon["bank_balance"]])
    writer.writerow(["Less: Cheques issued but not presented for payment", recon["unpresented_cheques_amount"]])
    writer.writerow(["Add: Cheques deposited but not credited by bank", recon["outstanding_deposits_amount"]])
    writer.writerow(["Add: Direct bank charges not entered in cash book", recon["bank_charges_amount"]])
    writer.writerow(["Less: Direct interest credited not entered in cash book", recon["interest_credited_amount"]])
    writer.writerow(["Adjusted Bank Statement Balance", recon["adjusted_bank_balance"]])
    writer.writerow(["Balance as per Cash Book (Ledger)", recon["book_balance"]])
    writer.writerow(["Net Unreconciled Variance", recon["net_unreconciled_difference"]])
    writer.writerow([])

    # Transactions Schedule Table
    writer.writerow([
        "Item ID",
        "Match Level",
        "Confidence Score",
        "Item Category / Type",
        "Book Date",
        "Book Voucher/Ref",
        "Book Party / Ledger",
        "Book Narration",
        "Book Amount (INR)",
        "Bank Date",
        "Bank Ref",
        "Bank Description",
        "Bank Amount (INR)",
        "Amount Difference",
        "Date Delay (Days)",
        "Match Reason",
        "Status",
        "Auditor Remarks"
    ])

    for itm in items:
        writer.writerow([
            itm["id"],
            itm["match_level"],
            f"{itm['match_score']}%",
            itm["item_type"],
            itm["date_a"] or "",
            itm["ref_a"] or "",
            itm["party_a"] or "",
            itm["description_a"] or "",
            itm["amount_a"] or 0.0,
            itm["date_b"] or "",
            itm["ref_b"] or "",
            itm["party_b"] or itm["description_b"] or "",
            itm["amount_b"] or 0.0,
            itm["difference"] or 0.0,
            itm["date_diff_days"] or 0,
            itm["match_reason"] or "",
            itm["status"] or "",
            itm["notes"] or ""
        ])

    csv_data = output.getvalue()
    filename = f"BRS_Report_{recon_id}_{recon['bank_account_name'].replace(' ', '_')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ---------------------------------------------------------------------------
# SALES & PURCHASE RECONCILIATION ENDPOINTS
# ---------------------------------------------------------------------------

class ExecuteSalesPurchaseRequest(BaseModel):
    engagement_id: int
    recon_type: str = "Sales Reconciliation"  # 'Sales Reconciliation' or 'Purchase Reconciliation'
    register_file_id: Optional[int] = None
    ledger_name: Optional[str] = None
    title: Optional[str] = None

class ItemActionRequest(BaseModel):
    status: str  # 'Accepted', 'Rejected', 'Marked for review'
    auditor_comment: Optional[str] = None

@router.post("/sales-purchase/execute")
def execute_sales_purchase_recon(
    req: ExecuteSalesPurchaseRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        from backend.app.services.sales_purchase_reconciliation_engine import run_sales_purchase_reconciliation
        res = run_sales_purchase_reconciliation(
            engagement_id=req.engagement_id,
            recon_type=req.recon_type,
            register_file_id=req.register_file_id,
            ledger_name=req.ledger_name,
            title=req.title,
            created_by=current_user.get("username", "admin")
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sales/Purchase Recon Error: {str(e)}")

@router.get("/sales-purchase/{recon_id}")
def get_sales_purchase_details(
    recon_id: int,
    exception_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
):
    conn = get_db_connection()
    recon_row = conn.execute("SELECT * FROM reconciliations WHERE id = ?", (recon_id,)).fetchone()
    if not recon_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Reconciliation session not found")
    
    recon = dict(recon_row)

    query = "SELECT * FROM reconciliation_items WHERE recon_id = ?"
    params = [recon_id]

    if exception_type and exception_type != "ALL":
        query += " AND item_type = ?"
        params.append(exception_type)
    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query += " AND (ref_a LIKE ? OR party_a LIKE ? OR gstin_a LIKE ? OR notes LIKE ? OR match_reason LIKE ?)"
        params.extend([term, term, term, term, term])

    query += " ORDER BY CASE status WHEN 'Marked for review' THEN 1 WHEN 'Suggested' THEN 2 WHEN 'Accepted' THEN 3 ELSE 4 END, id ASC"

    rows = conn.execute(query, tuple(params)).fetchall()
    recon["items"] = [dict(r) for r in rows]
    conn.close()
    return recon

@router.put("/sales-purchase/{recon_id}/items/{item_id}/action")
def update_sales_purchase_item_action(
    recon_id: int,
    item_id: int,
    req: ItemActionRequest,
    current_user: dict = Depends(get_current_user)
):
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
    return {"success": True, "message": f"Item updated to '{new_status}'."}

@router.get("/sales-purchase/{recon_id}/report/download")
def download_sales_purchase_report(recon_id: int):
    conn = get_db_connection()
    recon_row = conn.execute("SELECT * FROM reconciliations WHERE id = ?", (recon_id,)).fetchone()
    if not recon_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    
    recon = dict(recon_row)
    items = [dict(r) for r in conn.execute("SELECT * FROM reconciliation_items WHERE recon_id = ? ORDER BY status ASC, id ASC", (recon_id,)).fetchall()]
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header / Meta
    writer.writerow([f"FinAuditPro - {recon['recon_type']} Audit Report"])
    writer.writerow(["Title", recon["title"]])
    writer.writerow(["Date Generated", recon["created_at"]])
    writer.writerow(["Total Register Invoices", recon["total_bank_tx"]])
    writer.writerow(["Total Ledger Invoices", recon["total_book_tx"]])
    writer.writerow(["Matched Invoices", recon["matched_count"]])
    writer.writerow(["Discrepancies", recon["amount_diff_count"]])
    writer.writerow(["Total Ledger Amount (INR)", recon["book_balance"]])
    writer.writerow(["Total Register Amount (INR)", recon["bank_balance"]])
    writer.writerow(["Net Amount Variance (INR)", recon["net_unreconciled_difference"]])
    writer.writerow(["Net Tax Variance (INR)", recon["unreconciled_amount"]])
    writer.writerow([])

    # Table of Reconciled Items & Exceptions
    writer.writerow([
        "Invoice Number",
        "Party Name",
        "Register Amount (INR)",
        "Ledger Amount (INR)",
        "Difference (INR)",
        "Register Tax (INR)",
        "Ledger Tax (INR)",
        "Tax Difference (INR)",
        "Register Date",
        "Ledger Date",
        "Date Difference (Days)",
        "GSTIN (Register)",
        "GSTIN (Ledger)",
        "Exception Category",
        "Match / Audit Reason",
        "Status",
        "Auditor Comment"
    ])

    for itm in items:
        writer.writerow([
            itm["ref_a"] or itm["ref_b"] or "",
            itm["party_a"] or itm["party_b"] or "",
            itm["amount_a"] or 0.0,
            itm["amount_b"] or 0.0,
            itm["difference"] or 0.0,
            itm["tax_a"] or 0.0,
            itm["tax_b"] or 0.0,
            itm["tax_difference"] or 0.0,
            itm["date_a"] or "",
            itm["date_b"] or "",
            itm["date_diff_days"] or 0,
            itm["gstin_a"] or "",
            itm["gstin_b"] or "",
            itm["item_type"] or "",
            itm["match_reason"] or "",
            itm["status"] or "",
            itm["notes"] or ""
        ])

    csv_data = output.getvalue()
    filename = f"{recon['recon_type'].replace(' ', '_')}_Report_{recon_id}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


