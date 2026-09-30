import os
import json
from datetime import datetime
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import FileResponse

from backend.app.schemas import GenerateReportRequest
from backend.app.auth import get_current_user
from backend.app.database import get_db_connection
from backend.app.utils.pdf_generator import generate_audit_report_pdf, REPORT_TITLES

router = APIRouter(prefix="/api/reports", tags=["Reports"])

REPORT_DEFINITIONS = [
    {
        "id": "complete_audit_analysis",
        "title": "Complete Audit Analysis & Master Review",
        "description": "Comprehensive 17-section master report with executive summary, reconciliations, findings, anomalies, and working papers.",
        "category": "Master Report",
        "badge": "Comprehensive",
        "icon": "📑"
    },
    {
        "id": "engagement_summary",
        "title": "Engagement Summary",
        "description": "High-level overview of the audit engagement, client information, period, statistics, and quality review.",
        "category": "Executive",
        "badge": "Overview",
        "icon": "📊"
    },
    {
        "id": "data_import",
        "title": "Data Import Summary",
        "description": "Summary of external data sources ingested, general ledger mapping, row counts, and data sanitization status.",
        "category": "Data & Ingestion",
        "badge": "Ingestion",
        "icon": "📥"
    },
    {
        "id": "trial_balance",
        "title": "Trial Balance Analysis",
        "description": "Detailed analysis of Trial Balance heads, debit/credit health, abnormal negative cash/debtor balances, and suspense accounts.",
        "category": "Accounting",
        "badge": "Ledger Health",
        "icon": "⚖️"
    },
    {
        "id": "bank_reconciliation",
        "title": "Bank Reconciliation",
        "description": "Bank balance confirmations, statement matching results, unpresented cheques, uncredited deposits, and BRS exceptions.",
        "category": "Reconciliation",
        "badge": "BRS",
        "icon": "🏦"
    },
    {
        "id": "gst_reconciliation",
        "title": "GST Reconciliation",
        "description": "Input Tax Credit (ITC) reconciliation of GSTR-2B vs Books, tax rate discrepancies, and Section 16(2) compliance.",
        "category": "Taxation",
        "badge": "GST ITC",
        "icon": "🧾"
    },
    {
        "id": "anomaly_report",
        "title": "Anomaly Report",
        "description": "Deterministic rules, Benford's Law distribution analysis, statistical outliers, and machine learning Isolation Forest anomalies.",
        "category": "AI & Analytics",
        "badge": "ML / Outliers",
        "icon": "🧠"
    },
    {
        "id": "yoy_comparison",
        "title": "Year-on-Year Comparison",
        "description": "Multi-year Schedule III comparative Balance Sheet, P&L movements, significant percentage variances, and auditor notes.",
        "category": "Financial Analysis",
        "badge": "Comparative",
        "icon": "📈"
    },
    {
        "id": "risk_findings",
        "title": "Risk & Findings Report",
        "description": "Master exception register sorted by risk score with traceable Finding IDs, root causes, tax disallowances, and recommended actions.",
        "category": "Audit Exceptions",
        "badge": "Findings Register",
        "icon": "⚠️"
    },
    {
        "id": "audit_checklist",
        "title": "Audit Checklist",
        "description": "Execution status across statutory CARO 2020, Tax Audit 3CD, Standards on Auditing (SA), and internal control check items.",
        "category": "Compliance",
        "badge": "Checklist",
        "icon": "✅"
    }
]

@router.get("/types")
def list_report_types():
    """Returns the list of 10 available professional PDF report types."""
    return REPORT_DEFINITIONS

@router.get("/{engagement_id}")
def list_reports(engagement_id: int):
    """Lists all previously generated PDF reports for the engagement."""
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM reports WHERE engagement_id = ? ORDER BY id DESC", (engagement_id,)).fetchall()
    reports = [dict(r) for r in rows]
    conn.close()
    return reports

@router.post("/generate-pdf/{engagement_id}")
def generate_pdf_report(
    engagement_id: int,
    req: Optional[GenerateReportRequest] = None,
    report_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Generates a professional ICAI-compliant PDF report for the specified engagement.
    Supports all 10 specialized report types with traceable Finding IDs and SA 230 review notice.
    """
    selected_type = (req.report_type if req and req.report_type else None) or report_type or "complete_audit_analysis"
    
    if selected_type not in REPORT_TITLES:
        selected_type = "complete_audit_analysis"

    display_title = REPORT_TITLES.get(selected_type, "Audit Analysis Report")

    try:
        pdf_path = generate_audit_report_pdf(engagement_id, report_type=selected_type)
        filename = os.path.basename(pdf_path)

        conn = get_db_connection()
        now_str = datetime.now().isoformat()
        cursor = conn.execute("""
        INSERT INTO reports (engagement_id, report_title, report_type, generated_by, file_path, summary_json, created_at)
        VALUES (?, ?, ?, ?, ?, '{}', ?)
        """, (
            engagement_id,
            filename,
            f"PDF: {display_title}",
            current_user.get("full_name", "Auditor"),
            pdf_path,
            now_str
        ))
        
        report_id = cursor.lastrowid

        from backend.app.utils.audit_logger import log_audit_event
        log_audit_event(
            conn,
            action="REPORT_GENERATION",
            module="REPORTS",
            record_id=report_id,
            engagement_id=engagement_id,
            new_value={
                "report_id": report_id,
                "report_type": selected_type,
                "report_title": display_title,
                "filename": filename
            },
            details=f"Generated PDF [{display_title}] report for Engagement #{engagement_id}: {filename}",
            user=current_user
        )

        conn.commit()
        conn.close()

        return {
            "report_id": report_id,
            "filename": filename,
            "report_type": selected_type,
            "report_title": display_title,
            "download_url": f"/api/reports/download/{report_id}",
            "message": f"Report '{display_title}' generated successfully."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")

@router.get("/download/{report_id}")
def download_report(report_id: int):
    """Downloads the generated PDF report."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Report not found")

    file_path = row["file_path"]
    if not os.path.exists(file_path):
        conn.close()
        raise HTTPException(status_code=404, detail="PDF report file does not exist on disk")

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="REPORT_EXPORT",
        module="REPORTS",
        record_id=report_id,
        engagement_id=row["engagement_id"],
        details=f"Exported / downloaded PDF report '{row['report_title']}'"
    )
    conn.commit()
    conn.close()

    return FileResponse(
        path=file_path,
        filename=row["report_title"] if row["report_title"].endswith(".pdf") else f"{row['report_title']}.pdf",
        media_type="application/pdf"
    )
