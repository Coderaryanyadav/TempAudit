import io
import csv
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from backend.app.auth import get_current_user, require_engagement_access
from backend.app.database import get_db_connection
from backend.app.services.financial_statement_analysis_engine import run_financial_statement_analysis

router = APIRouter(prefix="/api/financial-statements", tags=["Financial Statements"])

class SaveExplanationRequest(BaseModel):
    item_key: str
    explanation_category: Optional[str] = None
    auditor_explanation: str
    review_status: str = "Reviewed"  # 'In Review', 'Reviewed', 'Flagged'

@router.get("/{engagement_id}")
def get_financial_statements(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """Generates Schedule III Balance Sheet, P&L, Cash Flow, and deterministic ratio comparison."""
    require_engagement_access(engagement_id, current_user)
    try:
        return run_financial_statement_analysis(engagement_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Financial Statement Analysis Error: {str(e)}")

@router.put("/{engagement_id}/explanation")
def save_auditor_explanation(
    engagement_id: int,
    req: SaveExplanationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Saves or updates an auditor's working-paper explanation for a significant movement."""
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    eng_row = conn.execute("SELECT financial_year FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    if not eng_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Engagement not found")

    fy = eng_row["financial_year"] or "2024-25"
    now_str = datetime.now().isoformat()
    username = current_user.get("username", "admin")

    conn.execute("""
        INSERT INTO financial_statement_explanations (
            engagement_id, item_key, financial_year, explanation_category,
            auditor_explanation, review_status, updated_by, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(engagement_id, item_key, financial_year) DO UPDATE SET
            explanation_category = excluded.explanation_category,
            auditor_explanation = excluded.auditor_explanation,
            review_status = excluded.review_status,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at
    """, (
        engagement_id, req.item_key, fy, req.explanation_category,
        req.auditor_explanation, req.review_status, username, now_str
    ))

    # Log in audit trail
    conn.execute("""
        INSERT INTO audit_logs (username, action, entity_type, entity_id, details, timestamp)
        VALUES (?, 'SAVE_FS_EXPLANATION', 'financial_statement_explanations', ?, ?, ?)
    """, (username, engagement_id, f"Saved explanation for '{req.item_key}': {req.auditor_explanation[:80]}...", now_str))

    conn.commit()
    conn.close()
    return {"success": True, "message": "Auditor explanation saved successfully."}

@router.get("/{engagement_id}/report/download")
def download_financial_analysis_report(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """Generates and downloads a comprehensive CSV Financial Statement Analysis report."""
    require_engagement_access(engagement_id, current_user)
    try:
        data = run_financial_statement_analysis(engagement_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cy_fy = data["financial_year_current"]
    py_fy = data["financial_year_previous"]
    ratios = data["ratios"]
    pnl = data["profit_and_loss"]
    bs = data["balance_sheet"]
    cf = data["cash_flow_statement"]
    comparisons = data["comparisons"]
    summary = data["summary"]

    output = io.StringIO()
    writer = csv.writer(output)

    # Header & Executive Summary
    writer.writerow(["FinAuditPro - Financial Statement & Ratio Analysis Report"])
    writer.writerow(["Current Financial Year", cy_fy])
    writer.writerow(["Previous Financial Year", py_fy])
    writer.writerow(["Date Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow(["Significant Movements Detected", summary["significant_movements_count"]])
    writer.writerow([])
    writer.writerow(["--- EXECUTIVE MANAGEMENT & AUDIT COMMENTARY ---"])
    writer.writerow([summary["management_commentary"]])
    writer.writerow([])

    # Deterministic Ratios Section
    writer.writerow(["--- DETERMINISTIC RATIO ANALYSIS ---"])
    writer.writerow(["Ratio Name", f"Current Year ({cy_fy})", f"Previous Year ({py_fy})", "Absolute Difference", "Percentage Change (%)", "ICAI Benchmark / Standard"])
    ratio_labels = [
        ("current_ratio", "Current Ratio (x)", "1.33x - 2.0x"),
        ("quick_ratio", "Quick Ratio (Acid Test) (x)", "1.0x"),
        ("debt_equity_ratio", "Debt-to-Equity Ratio (x)", "< 2.0x"),
        ("gross_profit_margin_pct", "Gross Profit Margin (%)", "Industry Average"),
        ("net_profit_margin_pct", "Net Profit Margin (%)", "Positive Trend"),
        ("operating_margin_pct", "Operating Profit Margin (%)", "Positive Trend"),
        ("receivable_turnover", "Debtors / Receivable Turnover (times)", "> 6.0x"),
        ("dso_days", "Days Sales Outstanding (DSO in days)", "< 60 days"),
        ("inventory_turnover", "Inventory Turnover (times)", "> 4.0x"),
        ("dsi_days", "Days Sales in Inventory (DSI in days)", "< 90 days"),
        ("payable_turnover", "Creditors / Payable Turnover (times)", "MSMEDA 45d"),
        ("dpo_days", "Days Payable Outstanding (DPO in days)", "45 days"),
        ("return_on_capital_employed_pct", "Return on Capital Employed (ROCE %)", "> 15%"),
        ("return_on_equity_pct", "Return on Equity (ROE %)", "> 12%"),
        ("working_capital_turnover", "Working Capital Turnover (times)", "> 5.0x")
    ]
    for r_key, r_name, bench in ratio_labels:
        cy_v = ratios["current_year"].get(r_key, 0.0)
        py_v = ratios["previous_year"].get(r_key, 0.0)
        diff = round(cy_v - py_v, 2)
        pct = round(((cy_v - py_v) / abs(py_v) * 100.0) if abs(py_v) > 0 else 0.0, 2)
        writer.writerow([r_name, cy_v, py_v, diff, f"{pct}%", bench])
    writer.writerow([])

    # Significant Movements & Variance Matrix
    writer.writerow(["--- SIGNIFICANT MOVEMENTS & AUDITOR EXPLANATIONS ---"])
    writer.writerow([
        "Metric / Account Head",
        "Category",
        f"CY ({cy_fy})",
        f"PY ({py_fy})",
        "Absolute Difference",
        "Percentage Change (%)",
        "Audit Status / Finding",
        "Explanation Category",
        "Auditor Working Paper Explanation",
        "Review Status"
    ])
    for c in comparisons:
        writer.writerow([
            c["metric_name"],
            c["category"],
            c["current_year_value"],
            c["previous_year_value"],
            c["absolute_difference"],
            f"{c['percentage_difference']}%",
            c["audit_verdict"],
            c["selected_category"],
            c["auditor_explanation"],
            c["review_status"]
        ])
    writer.writerow([])

    # Cash Flow Statement Summary
    writer.writerow(["--- CASH FLOW STATEMENT (INDIRECT METHOD) ---"])
    writer.writerow(["Cash Flow Activity", f"Amount in INR ({cy_fy})"])
    writer.writerow(["Cash Flow from Operating Activities (CFO)", cf["cash_flow_operating"]])
    writer.writerow(["Cash Flow from Investing Activities (CFI)", cf["cash_flow_investing"]])
    writer.writerow(["Cash Flow from Financing Activities (CFF)", cf["cash_flow_financing"]])
    writer.writerow(["Net Increase / Decrease in Cash", cf["net_cash_flow"]])
    writer.writerow(["Opening Cash & Bank Balance", cf["opening_cash_balance"]])
    writer.writerow(["Closing Cash & Bank Balance", cf["closing_cash_balance"]])

    csv_data = output.getvalue()
    filename = f"Financial_Statement_Analysis_{engagement_id}_{cy_fy.replace('-', '_')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
