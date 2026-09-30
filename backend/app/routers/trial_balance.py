import io
import csv
from datetime import datetime
from fastapi import APIRouter, HTTPException, Response
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from backend.app.database import get_db_connection
from backend.app.services.trial_balance_analyzer import analyze_trial_balance, get_ai_explanation_for_exception

router = APIRouter(prefix="/api/trial-balance", tags=["Trial Balance"])

class AIExplainRequest(BaseModel):
    check_id: str
    check_name: Optional[str] = None
    exact_difference: Optional[float] = 0.0
    affected_accounts: Optional[List[str]] = []
    sa_reference: Optional[str] = None

@router.get("/{engagement_id}")
def get_trial_balance(engagement_id: int):
    """
    Returns the comprehensive Trial Balance along with all 12 deterministic audit checks,
    exceptions list, difference calculation, and risk summary.
    """
    result = analyze_trial_balance(engagement_id)
    
    # Maintain backward compatibility with existing frontend `ledgers` field
    ledgers = []
    for a in result.get("accounts", []):
        ledgers.append({
            "ledger": a["ledger"],
            "account_group": a["account_group"],
            "total_debit": a["total_debit"],
            "total_credit": a["total_credit"],
            "opening_balance": a["opening_balance"],
            "closing_balance": a["closing_balance"],
            "closing_debit": a["closing_debit"],
            "closing_credit": a["closing_credit"],
            "transaction_count": a["transaction_count"],
            "first_txn_date": a["first_txn_date"],
            "last_txn_date": a["last_txn_date"]
        })
    result["ledgers"] = ledgers
    return result

@router.get("/{engagement_id}/analysis")
def get_trial_balance_analysis(engagement_id: int):
    """
    Returns only the 12 deterministic audit checks, risk summary, and exception breakdown.
    """
    return analyze_trial_balance(engagement_id)

@router.get("/{engagement_id}/ledger-drilldown")
def get_ledger_drilldown(engagement_id: int, ledger_name: str):
    """
    Returns chronological transaction ledger statement for drilldown inspection.
    """
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT * FROM transactions
        WHERE engagement_id = ? AND ledger = ?
        ORDER BY date ASC, id ASC
    """, (engagement_id, ledger_name)).fetchall()

    transactions = []
    running_balance = 0.0
    total_debit = 0.0
    total_credit = 0.0

    for r in rows:
        t = dict(r)
        dr = float(t.get("debit") or 0.0)
        cr = float(t.get("credit") or 0.0)
        total_debit += dr
        total_credit += cr
        running_balance += (dr - cr)
        t["running_balance"] = round(running_balance, 2)
        transactions.append(t)

    conn.close()
    return {
        "ledger_name": ledger_name,
        "total_transactions": len(transactions),
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "net_balance": round(running_balance, 2),
        "transactions": transactions
    }

@router.post("/{engagement_id}/ai-explain")
def explain_trial_balance_exception(engagement_id: int, req: AIExplainRequest):
    """
    Provides local offline deterministic ICAI audit guidance and Standard on Auditing (SA)
    explanation for any specific trial balance exception.
    """
    return get_ai_explanation_for_exception(
        check_id=req.check_id,
        context_data={
            "check_name": req.check_name,
            "exact_difference": req.exact_difference,
            "affected_accounts": req.affected_accounts,
            "sa_reference": req.sa_reference
        }
    )

@router.get("/{engagement_id}/report/download")
def download_trial_balance_report(engagement_id: int):
    """
    Generates and downloads a complete Trial Balance Analysis Report (CSV format)
    containing summary figures, tally verification, exception log, and account schedule.
    """
    conn = get_db_connection()
    eng = conn.execute("""
        SELECT e.*, c.name as client_name, c.pan as client_pan, c.gstin as client_gstin
        FROM engagements e
        JOIN clients c ON e.client_id = c.id
        WHERE e.id = ?
    """, (engagement_id,)).fetchone()
    conn.close()

    if not eng:
        raise HTTPException(status_code=404, detail="Engagement record not found.")

    analysis = analyze_trial_balance(engagement_id)
    
    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Header Information
    writer.writerow(["FinAuditPro — TRIAL BALANCE ANALYSIS & AUDIT EXCEPTION REPORT"])
    writer.writerow(["Client Name", eng["client_name"]])
    writer.writerow(["Financial Year", f"FY {eng['financial_year']}"])
    writer.writerow(["Audit Type", eng["audit_type"]])
    writer.writerow(["PAN / GSTIN", f"{eng['client_pan']} / {eng['client_gstin']}"])
    writer.writerow(["Report Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])

    # 2. Executive Summary Metrics
    writer.writerow(["--- EXECUTIVE SUMMARY & TALLY VERIFICATION ---"])
    writer.writerow(["Total Debit (₹)", f"{analysis['grand_total_debit']:,.2f}"])
    writer.writerow(["Total Credit (₹)", f"{analysis['grand_total_credit']:,.2f}"])
    writer.writerow(["Exact Difference (₹)", f"{analysis['difference']:,.2f}"])
    writer.writerow(["Status", "TALLIED / BALANCED" if analysis["is_balanced"] else "OUT OF BALANCE (HIGH PRIORITY)"])
    writer.writerow(["Total Accounts", analysis["total_accounts_count"]])
    writer.writerow(["Accounts with Exceptions", analysis["accounts_with_exceptions_count"]])
    writer.writerow(["Overall Risk Rating", analysis["overall_risk_rating"]])
    writer.writerow([])

    # 3. Audit Checks & Exceptions Log
    writer.writerow(["--- TRIAL BALANCE AUDIT EXCEPTIONS LOG ---"])
    writer.writerow(["Check ID", "Check Title", "Severity", "Category", "Description", "SA Reference", "Affected Accounts Count"])
    for ex in analysis.get("exceptions", []):
        writer.writerow([
            ex.get("check_id"),
            ex.get("check_name"),
            ex.get("severity"),
            ex.get("category"),
            ex.get("description"),
            ex.get("sa_reference"),
            ex.get("affected_account_count")
        ])
    writer.writerow([])

    # 4. Account Schedule Detail
    writer.writerow(["--- COMPLETE TRIAL BALANCE ACCOUNT SCHEDULE ---"])
    writer.writerow([
        "Account / Ledger Name",
        "Group / Category",
        "Opening Balance (₹)",
        "Period Debit (₹)",
        "Period Credit (₹)",
        "Net Closing Balance (₹)",
        "Closing Debit (₹)",
        "Closing Credit (₹)",
        "Txn Count",
        "First Date",
        "Last Date"
    ])
    for a in analysis.get("accounts", []):
        writer.writerow([
            a["ledger"],
            a["account_group"],
            f"{a['opening_balance']:.2f}",
            f"{a['total_debit']:.2f}",
            f"{a['total_credit']:.2f}",
            f"{a['closing_balance']:.2f}",
            f"{a['closing_debit']:.2f}",
            f"{a['closing_credit']:.2f}",
            a["transaction_count"],
            a["first_txn_date"] or "",
            a["last_txn_date"] or ""
        ])

    csv_data = output.getvalue()
    filename = f"Trial_Balance_Analysis_{eng['client_name'].replace(' ', '_')}_{eng['financial_year']}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
