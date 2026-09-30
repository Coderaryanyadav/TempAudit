import csv
import io
from fastapi import APIRouter, HTTPException, Query, Response, Depends
from typing import List, Optional
from backend.app.auth import get_current_user, require_engagement_access
from backend.app.database import get_db_connection
from backend.app.services.general_ledger_analyzer import analyze_general_ledger

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])

@router.get("")
def get_transactions(
    engagement_id: int,
    ledger: Optional[str] = None,
    party: Optional[str] = None,
    voucher_no: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    min_debit: Optional[float] = None,
    max_debit: Optional[float] = None,
    min_credit: Optional[float] = None,
    max_credit: Optional[float] = None,
    limit: int = 200,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    require_engagement_access(engagement_id, current_user)
    limit = min(max(1, limit), 500)
    offset = max(0, offset)

    conn = get_db_connection()
    query = "SELECT * FROM transactions WHERE engagement_id = ?"
    params = [engagement_id]

    if ledger and ledger != "All" and ledger.strip():
        query += " AND ledger = ?"
        params.append(ledger.strip())
    if party and party.strip():
        query += " AND party_name LIKE ?"
        params.append(f"%{party.strip()}%")
    if voucher_no and voucher_no.strip():
        query += " AND voucher_no LIKE ?"
        params.append(f"%{voucher_no.strip()}%")
    if search and search.strip():
        term = f"%{search.strip()}%"
        query += " AND (description LIKE ? OR voucher_no LIKE ? OR invoice_no LIKE ? OR party_name LIKE ? OR ledger LIKE ?)"
        params.extend([term, term, term, term, term])
    if start_date and start_date.strip():
        query += " AND date >= ?"
        params.append(start_date.strip())
    if end_date and end_date.strip():
        query += " AND date <= ?"
        params.append(end_date.strip())
    if min_amount is not None:
        query += " AND (amount >= ? OR debit >= ? OR credit >= ?)"
        params.extend([min_amount, min_amount, min_amount])
    if max_amount is not None:
        query += " AND (amount <= ? AND (debit <= ? OR credit <= ?))"
        params.extend([max_amount, max_amount, max_amount])
    if min_debit is not None:
        query += " AND debit >= ?"
        params.append(min_debit)
    if max_debit is not None:
        query += " AND debit <= ?"
        params.append(max_debit)
    if min_credit is not None:
        query += " AND credit >= ?"
        params.append(min_credit)
    if max_credit is not None:
        query += " AND credit <= ?"
        params.append(max_credit)

    total_count = conn.execute(f"SELECT COUNT(*) as c FROM ({query})", tuple(params)).fetchone()["c"]

    query += " ORDER BY date ASC, id ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, tuple(params)).fetchall()
    transactions = [dict(r) for r in rows]
    conn.close()

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "items": transactions
    }

@router.get("/analysis/{engagement_id}")
def get_general_ledger_analysis(
    engagement_id: int,
    ledger: Optional[str] = None,
    party: Optional[str] = None,
    voucher_no: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    min_debit: Optional[float] = None,
    max_debit: Optional[float] = None,
    min_credit: Optional[float] = None,
    max_credit: Optional[float] = None,
    anomaly_rule: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    require_engagement_access(engagement_id, current_user)
    try:
        result = analyze_general_ledger(
            engagement_id=engagement_id,
            ledger=ledger,
            party=party,
            voucher_no=voucher_no,
            search=search,
            start_date=start_date,
            end_date=end_date,
            min_amount=min_amount,
            max_amount=max_amount,
            min_debit=min_debit,
            max_debit=max_debit,
            min_credit=min_credit,
            max_credit=max_credit,
            anomaly_rule=anomaly_rule
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GL Analysis Error: {str(e)}")

@router.get("/ledgers-list/{engagement_id}")
def get_distinct_ledgers(engagement_id: int, current_user: dict = Depends(get_current_user)):
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT DISTINCT ledger FROM transactions WHERE engagement_id = ? AND ledger IS NOT NULL AND ledger != '' ORDER BY ledger ASC",
        (engagement_id,)
    ).fetchall()
    ledgers = [r["ledger"] for r in rows]
    conn.close()
    return {"ledgers": ledgers}

@router.get("/parties-list/{engagement_id}")
def get_distinct_parties(engagement_id: int, current_user: dict = Depends(get_current_user)):
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT DISTINCT party_name FROM transactions WHERE engagement_id = ? AND party_name IS NOT NULL AND party_name != '' ORDER BY party_name ASC",
        (engagement_id,)
    ).fetchall()
    parties = [r["party_name"] for r in rows]
    conn.close()
    return {"parties": parties}

@router.get("/report/{engagement_id}/download")
def download_gl_analysis_report(
    engagement_id: int,
    ledger: Optional[str] = None,
    party: Optional[str] = None,
    voucher_no: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    anomaly_rule: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    require_engagement_access(engagement_id, current_user)
    analysis = analyze_general_ledger(
        engagement_id=engagement_id,
        ledger=ledger,
        party=party,
        voucher_no=voucher_no,
        search=search,
        start_date=start_date,
        end_date=end_date,
        anomaly_rule=anomaly_rule
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header / Meta
    writer.writerow(["FinAuditPro - General Ledger Analysis & Anomaly Report"])
    writer.writerow(["Engagement ID", engagement_id])
    writer.writerow(["Total Transactions", analysis["total_transactions"]])
    writer.writerow(["Flagged Items (Requires Review)", analysis["flagged_transactions_count"]])
    writer.writerow(["Total Anomalies", analysis["total_anomalies_count"]])
    writer.writerow(["Total Debit", analysis["total_debit"]])
    writer.writerow(["Total Credit", analysis["total_credit"]])
    writer.writerow([])

    # Table of Detected Anomalies
    writer.writerow([
        "Transaction ID",
        "Date",
        "Voucher No",
        "Ledger",
        "Party Name",
        "Debit (INR)",
        "Credit (INR)",
        "Narration",
        "Rule Code",
        "Rule Name",
        "Severity / Risk",
        "Reason / Anomaly Description",
        "Evidence",
        "Recommended Review"
    ])

    for a in analysis.get("anomalies", []):
        t = a.get("transaction") or {}
        writer.writerow([
            a.get("transaction_id", t.get("id")),
            t.get("date", ""),
            t.get("voucher_no", ""),
            t.get("ledger", ""),
            t.get("party_name", ""),
            t.get("debit", 0.0),
            t.get("credit", 0.0),
            t.get("description", ""),
            a.get("rule", ""),
            a.get("rule_name", ""),
            f"{a.get('severity', 'MEDIUM')} (Score: {a.get('risk_score', 0)})",
            a.get("reason", ""),
            a.get("evidence", ""),
            a.get("recommended_review", "")
        ])

    csv_data = output.getvalue()
    filename = f"GL_Analysis_Report_Engagement_{engagement_id}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/{transaction_id}")
def get_transaction(transaction_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Transaction not found")
    tx = dict(row)
    conn.close()
    require_engagement_access(tx["engagement_id"], current_user)
    return tx

