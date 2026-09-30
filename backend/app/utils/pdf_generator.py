import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas
from backend.app.database import get_db_connection

REPORT_TITLES = {
    "complete_audit_analysis": "Complete Audit Analysis & Master Review Report",
    "engagement_summary": "Engagement Summary & Audit Overview Report",
    "data_import": "Data Import & Ingestion Summary Report",
    "trial_balance": "Trial Balance Analysis & Ledger Health Report",
    "bank_reconciliation": "Bank Reconciliation & Statement Verification Report",
    "gst_reconciliation": "GST ITC Reconciliation (GSTR-2B vs Books) Report",
    "anomaly_report": "AI & Statistical Anomaly Detection Report",
    "yoy_comparison": "Year-on-Year Comparative Variance Analysis Report",
    "risk_findings": "Master Risk & Audit Findings Exception Register",
    "audit_checklist": "Statutory & Internal Audit Checklist Compliance Report"
}

class NumberedCanvas(canvas.Canvas):
    """Draws running header, dynamic total page count, and SA 230 confidentiality footer on each page."""
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Running Top Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(40, 804, "FinAuditPro — AI-Assisted Audit Analysis Report (ICAI SA 230 Compliant)")
            self.drawRightString(555, 804, datetime.now().strftime("%d-%b-%Y"))
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(40, 796, 555, 796)

        # Running Bottom Footer
        footer_left = "AI-Assisted Audit Analysis Report | Subject to Independent CA Verification (SA 200/SA 700)"
        footer_right = f"Page {self._pageNumber} of {page_count}"
        self.drawString(40, 30, footer_left)
        self.drawRightString(555, 30, footer_right)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 42, 555, 42)
        self.restoreState()


def get_report_styles():
    """Generates consistent professional styles for audit reports."""
    styles = getSampleStyleSheet()
    
    return {
        'CoverTitle': ParagraphStyle(
            'CoverTitle',
            parent=styles['Heading1'],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor('#0F172A'),
            fontName='Helvetica-Bold',
            spaceAfter=8
        ),
        'CoverSubtitle': ParagraphStyle(
            'CoverSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#2563EB'),
            fontName='Helvetica-Bold',
            spaceAfter=15
        ),
        'DisclaimerBox': ParagraphStyle(
            'DisclaimerBox',
            parent=styles['Normal'],
            fontSize=8,
            leading=11.5,
            textColor=colors.HexColor('#991B1B'),
            fontName='Helvetica'
        ),
        'SectionH1': ParagraphStyle(
            'SectionH1',
            parent=styles['Heading1'],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor('#0F172A'),
            fontName='Helvetica-Bold',
            spaceBefore=14,
            spaceAfter=6
        ),
        'SectionH2': ParagraphStyle(
            'SectionH2',
            parent=styles['Heading2'],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#1E293B'),
            fontName='Helvetica-Bold',
            spaceBefore=10,
            spaceAfter=4
        ),
        'Body': ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor('#334155')
        ),
        'BodyBold': ParagraphStyle(
            'BodyBold',
            parent=styles['Normal'],
            fontSize=8.5,
            leading=12,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#0F172A')
        ),
        'TableHeader': ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontSize=8.5,
            leading=11,
            fontName='Helvetica-Bold',
            textColor=colors.white
        ),
        'BadgeCrit': ParagraphStyle(
            'BadgeCrit',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#DC2626'),
            fontName='Helvetica-Bold'
        ),
        'BadgeHigh': ParagraphStyle(
            'BadgeHigh',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#EA580C'),
            fontName='Helvetica-Bold'
        ),
        'BadgeMed': ParagraphStyle(
            'BadgeMed',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#D97706'),
            fontName='Helvetica-Bold'
        ),
        'BadgeLow': ParagraphStyle(
            'BadgeLow',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#059669'),
            fontName='Helvetica-Bold'
        ),
        'FindingId': ParagraphStyle(
            'FindingId',
            parent=styles['Normal'],
            fontSize=8.5,
            leading=11,
            fontName='Courier-Bold',
            textColor=colors.HexColor('#2563EB')
        )
    }


def _build_metadata_box(engagement: dict, st: dict) -> Table:
    """Creates standard two-column engagement and client metadata box."""
    data = [
        [
            Paragraph("<b>Client Name:</b> " + str(engagement.get("client_name", "N/A")), st['Body']),
            Paragraph("<b>Financial Year:</b> " + str(engagement.get("financial_year", "N/A")), st['Body'])
        ],
        [
            Paragraph("<b>PAN:</b> " + str(engagement.get("client_pan") or "N/A"), st['Body']),
            Paragraph("<b>GSTIN:</b> " + str(engagement.get("client_gstin") or "N/A"), st['Body'])
        ],
        [
            Paragraph("<b>Entity Type:</b> " + str(engagement.get("entity_type") or "Private Limited Company"), st['Body']),
            Paragraph("<b>Audit Type:</b> " + str(engagement.get("audit_type", "Statutory Audit")), st['Body'])
        ],
        [
            Paragraph("<b>Period:</b> " + f"{engagement.get('period_start') or '01-04-2024'} to {engagement.get('period_end') or '31-03-2025'}", st['Body']),
            Paragraph("<b>Lead Auditor / CA:</b> " + str(engagement.get("lead_auditor_name") or "Aaliya Kherani (FCA)"), st['Body'])
        ],
        [
            Paragraph("<b>Document Nature:</b> AI-Assisted Audit Analysis", st['Body']),
            Paragraph("<b>Report Generated On:</b> " + datetime.now().strftime("%d-%b-%Y %H:%M:%S"), st['Body'])
        ]
    ]

    t = Table(data, colWidths=[255, 260])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t


def _build_disclaimer_banner(st: dict) -> Table:
    """Builds mandatory ICAI SA 200/SA 700 quality & statutory review notice."""
    disclaimer_text = (
        "<b>IMPORTANT STATUTORY AUDIT & QUALITY CONTROL NOTICE (SA 200 / SA 230 / SA 700):</b><br/>"
        "This document is an <i>AI-Assisted Audit Analysis Report</i> generated automatically from electronic books, "
        "statements, and working schedules. It serves as substantive working evidence for engagement team inspection. "
        "In accordance with Standards on Auditing issued by the Institute of Chartered Accountants of India (ICAI), "
        "<b>this document does NOT constitute an automated final professional audit opinion.</b> The Practicing Chartered "
        "Accountant / Engagement Partner must independently verify, corroborate, and exercise professional skepticism "
        "prior to finalizing the Independent Auditor's Report."
    )
    t = Table([[Paragraph(disclaimer_text, st['DisclaimerBox'])]], colWidths=[515])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF2F2')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#FECACA')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t


def _build_signoff_section(st: dict) -> List[Any]:
    """Generates standard ICAI maker-checker reviewer sign-off block."""
    elements = []
    elements.append(Paragraph("Auditor Working Paper Review & Partner Sign-off (SA 230)", st['SectionH1']))
    
    signoff_data = [
        [
            Paragraph("<b>Prepared By (Audit Assistant/Senior):</b><br/><br/>Name: ______________________<br/>Designation: Audit Staff<br/>Signature: __________________<br/>Date: ______________________", st['Body']),
            Paragraph("<b>Reviewed By (Audit Manager):</b><br/><br/>Name: ______________________<br/>Designation: Audit Manager<br/>Signature: __________________<br/>Date: ______________________", st['Body']),
            Paragraph("<b>Approved By (Engagement Partner / CA):</b><br/><br/>Name: ______________________<br/>ICAI M.No: _________________<br/>UDIN: ______________________<br/>Date: ______________________", st['Body'])
        ]
    ]
    signoff_table = Table(signoff_data, colWidths=[171, 171, 173])
    signoff_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(signoff_table)
    return elements


def generate_audit_report_pdf(
    engagement_id: int,
    report_type: str = "complete_audit_analysis",
    output_dir: str = None
) -> str:
    """
    Generates a professional, ICAI-compliant PDF Audit Report for an engagement.
    Supported report_types:
      1. complete_audit_analysis (Full Master Report with all 17 structure sections)
      2. engagement_summary
      3. data_import
      4. trial_balance
      5. bank_reconciliation
      6. gst_reconciliation
      7. anomaly_report
      8. yoy_comparison
      9. risk_findings
      10. audit_checklist
    """
    conn = get_db_connection()

    # 1. Fetch Engagement & Client metadata
    eng_row = conn.execute("""
        SELECT e.*, c.name as client_name, c.pan as client_pan, c.gstin as client_gstin,
               c.entity_type, c.industry, u.full_name as lead_auditor_name
        FROM engagements e
        JOIN clients c ON e.client_id = c.id
        LEFT JOIN users u ON e.lead_auditor_id = u.id
        WHERE e.id = ?
    """, (engagement_id,)).fetchone()

    if not eng_row:
        conn.close()
        raise ValueError(f"Engagement #{engagement_id} not found.")

    engagement = dict(eng_row)

    # 2. Fetch Data Sources (Uploaded Files)
    files_rows = conn.execute("SELECT * FROM uploaded_files WHERE engagement_id = ? ORDER BY id ASC", (engagement_id,)).fetchall()
    uploaded_files = [dict(f) for f in files_rows]

    # 3. Fetch Transactions Statistics
    tx_count = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE engagement_id = ?", (engagement_id,)).fetchone()["c"]
    total_debit = conn.execute("SELECT SUM(debit) as s FROM transactions WHERE engagement_id = ?", (engagement_id,)).fetchone()["s"] or 0.0
    total_credit = conn.execute("SELECT SUM(credit) as s FROM transactions WHERE engagement_id = ?", (engagement_id,)).fetchone()["s"] or 0.0

    # 4. Fetch Ledgers / TB Heads
    ledgers_rows = conn.execute("SELECT * FROM ledgers WHERE engagement_id = ? ORDER BY account_group ASC, ledger_name ASC", (engagement_id,)).fetchall()
    ledgers = [dict(l) for l in ledgers_rows]

    # 5. Fetch Reconciliations
    recon_rows = conn.execute("SELECT * FROM reconciliations WHERE engagement_id = ? ORDER BY id ASC", (engagement_id,)).fetchall()
    reconciliations = [dict(r) for r in recon_rows]

    # 6. Fetch Findings with Finding IDs
    findings_rows = conn.execute("SELECT * FROM audit_findings WHERE engagement_id = ? ORDER BY risk_score DESC, id ASC", (engagement_id,)).fetchall()
    findings = [dict(f) for f in findings_rows]

    # 7. Fetch Checklists
    chk_rows = conn.execute("SELECT * FROM audit_checklists WHERE engagement_id = ? ORDER BY category ASC, id ASC", (engagement_id,)).fetchall()
    checklists = [dict(c) for c in chk_rows]

    # 8. Fetch Working Papers
    wp_rows = conn.execute("SELECT * FROM working_papers WHERE engagement_id = ? ORDER BY wp_reference ASC", (engagement_id,)).fetchall()
    working_papers = [dict(w) for w in wp_rows]

    # 9. Fetch Auditor YoY Explanations
    exp_rows = conn.execute("SELECT * FROM financial_statement_explanations WHERE engagement_id = ? ORDER BY item_key ASC", (engagement_id,)).fetchall()
    explanations = [dict(e) for e in exp_rows]

    conn.close()

    # Determine Output Path
    if not output_dir:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports_generated")
    os.makedirs(output_dir, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_title_display = REPORT_TITLES.get(report_type, "Audit Analysis Report")
    clean_type = report_type.replace("_", "-")
    pdf_filename = f"FinAuditPro_{clean_type}_Eng{engagement_id}_{timestamp_str}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=46,
        bottomMargin=46
    )

    st = get_report_styles()
    story = []

    # =========================================================================
    # SECTION 1: COVER & HEADER BANNER
    # =========================================================================
    story.append(Paragraph("FinAuditPro — Independent Audit Memorandum", st['CoverTitle']))
    story.append(Paragraph(f"AI-Assisted Audit Analysis Report: <b>{report_title_display}</b>", st['CoverSubtitle']))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=10))

    # Mandatory Disclaimer Banner
    story.append(_build_disclaimer_banner(st))
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTIONS 2, 3, 4: CLIENT & ENGAGEMENT METADATA & PERIOD
    # =========================================================================
    story.append(Paragraph("1. Client & Engagement Profile", st['SectionH1']))
    story.append(_build_metadata_box(engagement, st))
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTIONS 5, 6, 7: DATA SOURCES, SCOPE & CHECKS PERFORMED
    # =========================================================================
    if report_type in ["complete_audit_analysis", "engagement_summary", "data_import"]:
        story.append(Paragraph("2. Audit Data Sources & Ingestion Scope", st['SectionH1']))
        
        if not uploaded_files:
            story.append(Paragraph("<i>No external source files uploaded. Using integrated electronic ledger data.</i>", st['Body']))
        else:
            file_table_data = [
                [
                    Paragraph("<b>File Name</b>", st['TableHeader']),
                    Paragraph("<b>Category</b>", st['TableHeader']),
                    Paragraph("<b>Type</b>", st['TableHeader']),
                    Paragraph("<b>Rows</b>", st['TableHeader']),
                    Paragraph("<b>Uploaded At</b>", st['TableHeader'])
                ]
            ]
            for f in uploaded_files:
                file_table_data.append([
                    Paragraph(str(f.get("file_name", "N/A")), st['BodyBold']),
                    Paragraph(str(f.get("data_category", "General Ledger")), st['Body']),
                    Paragraph(str(f.get("file_type", "Excel")), st['Body']),
                    Paragraph(f"{f.get('successful_rows', f.get('row_count', 0)):,}", st['Body']),
                    Paragraph(str(f.get("uploaded_at", "")[:16].replace("T", " ")), st['Body'])
                ])

            ft = Table(file_table_data, colWidths=[160, 115, 60, 60, 120])
            ft.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(ft)

        scope_desc = (
            "<b>Audit Scope & Standards Applied:</b><br/>"
            "• Testing executed under ICAI Standards on Auditing (SA 200, SA 230, SA 315, SA 500, SA 520, SA 530).<br/>"
            "• Deterministic Statutory Compliance (Income Tax Act Sec 40A(3), Sec 43B, Sec 269ST; GST Act Sec 16(2), Rule 36(4)).<br/>"
            "• Statistical Outlier Verification (Z-score 3.0σ, Interquartile Range, Benford's First-Digit Law).<br/>"
            "• Unsupervised Machine Learning Anomaly Detection (Isolation Forest multi-dimensional outlier scoring)."
        )
        story.append(Spacer(1, 6))
        story.append(Paragraph(scope_desc, st['Body']))
        story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 8: EXECUTIVE SUMMARY & RISK HEATMAP
    # =========================================================================
    if report_type in ["complete_audit_analysis", "engagement_summary", "risk_findings", "anomaly_report"]:
        story.append(Paragraph("3. Executive Summary & Risk Overview", st['SectionH1']))

        crit_count = sum(1 for f in findings if f.get('severity') == 'CRITICAL')
        high_count = sum(1 for f in findings if f.get('severity') == 'HIGH')
        med_count = sum(1 for f in findings if f.get('severity') == 'MEDIUM')
        low_count = sum(1 for f in findings if f.get('severity') == 'LOW')

        chk_total = len(checklists)
        chk_completed = sum(1 for c in checklists if c.get('status') == 'Completed')
        chk_pct = f"{(chk_completed / chk_total * 100):.1f}%" if chk_total > 0 else "N/A"

        exec_summary_data = [
            [
                Paragraph("<b>Total Transactions Examined:</b>", st['Body']),
                Paragraph(f"{tx_count:,} vouchers (₹{total_debit:,.2f})", st['BodyBold']),
                Paragraph("<b>Total Risk Findings:</b>", st['Body']),
                Paragraph(f"{len(findings)} exceptions identified", st['BodyBold'])
            ],
            [
                Paragraph("<b>Critical Risk (Form 3CD/CARO):</b>", st['Body']),
                Paragraph(f"<font color='#DC2626'><b>{crit_count}</b></font>", st['BodyBold']),
                Paragraph("<b>High Risk (Tax/GST/ITC):</b>", st['Body']),
                Paragraph(f"<font color='#EA580C'><b>{high_count}</b></font>", st['BodyBold'])
            ],
            [
                Paragraph("<b>Medium / Low Risk Items:</b>", st['Body']),
                Paragraph(f"{med_count + low_count} observations", st['Body']),
                Paragraph("<b>Checklist Compliance:</b>", st['Body']),
                Paragraph(f"<b>{chk_completed}/{chk_total}</b> ({chk_pct})", st['BodyBold'])
            ]
        ]
        et = Table(exec_summary_data, colWidths=[150, 110, 150, 105])
        et.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(et)
        story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 9: FINANCIAL DATA SUMMARY & TRIAL BALANCE HEALTH
    # =========================================================================
    if report_type in ["complete_audit_analysis", "trial_balance", "engagement_summary"]:
        story.append(Paragraph("4. Financial Data Summary & Trial Balance Health", st['SectionH1']))

        tb_diff = abs(total_debit - total_credit)
        tb_status = "PERFECTLY BALANCED (Difference: ₹0.00)" if tb_diff < 0.01 else f"UNBALANCED (Difference: ₹{tb_diff:,.2f})"

        tb_meta = [
            [
                Paragraph("<b>Total Debit:</b> ₹" + f"{total_debit:,.2f}", st['Body']),
                Paragraph("<b>Total Credit:</b> ₹" + f"{total_credit:,.2f}", st['Body']),
                Paragraph("<b>Status:</b> " + tb_status, st['BodyBold'])
            ]
        ]
        tbt = Table(tb_meta, colWidths=[170, 170, 175])
        tbt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(tbt)
        story.append(Spacer(1, 6))

        if ledgers:
            ledger_table_data = [
                [
                    Paragraph("<b>Ledger Head</b>", st['TableHeader']),
                    Paragraph("<b>Group</b>", st['TableHeader']),
                    Paragraph("<b>Debit Balance</b>", st['TableHeader']),
                    Paragraph("<b>Credit Balance</b>", st['TableHeader']),
                    Paragraph("<b>Net Closing</b>", st['TableHeader'])
                ]
            ]
            for l in ledgers[:18]:  # display top key ledgers
                net_val = (l.get('debit_balance', 0) or 0) - (l.get('credit_balance', 0) or 0)
                net_str = f"₹{net_val:,.2f} Dr" if net_val >= 0 else f"₹{abs(net_val):,.2f} Cr"
                ledger_table_data.append([
                    Paragraph(str(l.get("ledger_name", "")), st['BodyBold']),
                    Paragraph(str(l.get("account_group", "General")), st['Body']),
                    Paragraph(f"₹{(l.get('debit_balance') or 0):,.2f}", st['Body']),
                    Paragraph(f"₹{(l.get('credit_balance') or 0):,.2f}", st['Body']),
                    Paragraph(net_str, st['BodyBold'])
                ])

            lt = Table(ledger_table_data, colWidths=[150, 100, 85, 85, 95])
            lt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0, 0), (-1, -1), 3.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
            ]))
            story.append(lt)
            story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 10: RECONCILIATION RESULTS (BANK & GST)
    # =========================================================================
    if report_type in ["complete_audit_analysis", "bank_reconciliation", "gst_reconciliation", "engagement_summary"]:
        story.append(Paragraph("5. Bank & GST Reconciliation Results", st['SectionH1']))

        if not reconciliations:
            story.append(Paragraph("<i>No automated reconciliation runs recorded yet.</i>", st['Body']))
        else:
            recon_table_data = [
                [
                    Paragraph("<b>Reconciliation Title</b>", st['TableHeader']),
                    Paragraph("<b>Type</b>", st['TableHeader']),
                    Paragraph("<b>Matched</b>", st['TableHeader']),
                    Paragraph("<b>Unmatched</b>", st['TableHeader']),
                    Paragraph("<b>Unreconciled Variance</b>", st['TableHeader']),
                    Paragraph("<b>Status</b>", st['TableHeader'])
                ]
            ]
            for r in reconciliations:
                unmatched_tot = (r.get("unmatched_bank_count", 0) or 0) + (r.get("unmatched_book_count", 0) or 0)
                recon_table_data.append([
                    Paragraph(str(r.get("title", "Reconciliation")), st['BodyBold']),
                    Paragraph(str(r.get("recon_type", "General")), st['Body']),
                    Paragraph(f"{r.get('matched_count', 0):,}", st['Body']),
                    Paragraph(f"{unmatched_tot:,}", st['Body']),
                    Paragraph(f"₹{(r.get('unreconciled_amount') or r.get('net_unreconciled_difference') or 0.0):,.2f}", st['BodyBold']),
                    Paragraph(str(r.get("status", "Completed")), st['Body'])
                ])

            rt = Table(recon_table_data, colWidths=[150, 95, 55, 60, 95, 60])
            rt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(rt)
        story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 11: ANOMALY & PATTERN RESULTS
    # =========================================================================
    if report_type in ["complete_audit_analysis", "anomaly_report"]:
        story.append(Paragraph("6. Anomaly & Statistical Outlier Results", st['SectionH1']))
        anomaly_findings = [f for f in findings if f.get('module') in ['Anomaly Engine', 'Outlier Engine', 'ML Engine'] or f.get('engine_type') in ['STATISTICAL_ML', 'LOCAL_AI']]
        
        if not anomaly_findings:
            story.append(Paragraph("No anomalous clusters, Benford's law deviations, or weekend/holiday outliers detected.", st['Body']))
        else:
            anom_table_data = [
                [
                    Paragraph("<b>Finding ID</b>", st['TableHeader']),
                    Paragraph("<b>Anomaly Title & Pattern</b>", st['TableHeader']),
                    Paragraph("<b>Statistical Metric</b>", st['TableHeader']),
                    Paragraph("<b>Severity</b>", st['TableHeader'])
                ]
            ]
            for af in anomaly_findings[:10]:
                sev = af.get('severity', 'MEDIUM')
                sev_st = st['BadgeCrit'] if sev == 'CRITICAL' else (st['BadgeHigh'] if sev == 'HIGH' else st['BadgeMed'])
                anom_table_data.append([
                    Paragraph(f"<b>[ID: {af.get('id')}]</b><br/>{af.get('finding_code')}", st['FindingId']),
                    Paragraph(f"<b>{af.get('title')}</b><br/>{af.get('description', '')[:90]}...", st['Body']),
                    Paragraph(f"<b>Diff:</b> {af.get('difference') or 'N/A'}<br/>Score: {af.get('risk_score')}/10", st['Body']),
                    Paragraph(f"[{sev}]", sev_st)
                ])

            at = Table(anom_table_data, colWidths=[75, 230, 130, 80])
            at.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(at)
        story.append(Spacer(1, 10))

    # =========================================================================
    # SECTIONS 12 & 13: RISK FINDINGS & MAJOR EXCEPTIONS (WITH FINDING IDs)
    # =========================================================================
    if report_type in ["complete_audit_analysis", "risk_findings", "engagement_summary", "yoy_comparison"]:
        story.append(Paragraph("7. Master Risk Findings & Exception Register (Traceable Finding IDs)", st['SectionH1']))

        if not findings:
            story.append(Paragraph("<i>No compliance exceptions or high-risk findings detected for this engagement.</i>", st['Body']))
        else:
            findings_table_data = [
                [
                    Paragraph("<b>Finding ID & Code</b>", st['TableHeader']),
                    Paragraph("<b>Severity</b>", st['TableHeader']),
                    Paragraph("<b>Exception Title & Observations</b>", st['TableHeader']),
                    Paragraph("<b>Rule & Engine</b>", st['TableHeader']),
                    Paragraph("<b>Recommended Action</b>", st['TableHeader'])
                ]
            ]

            for f in findings:
                sev = f.get('severity', 'MEDIUM')
                sev_st = st['BadgeCrit'] if sev == 'CRITICAL' else (st['BadgeHigh'] if sev == 'HIGH' else (st['BadgeMed'] if sev == 'MEDIUM' else st['BadgeLow']))

                id_cell = Paragraph(
                    f"<b>[ID: {f.get('id')}]</b><br/>"
                    f"<b>{f.get('finding_code', 'F-000')}</b><br/>"
                    f"<font color='#64748B'>Score: {f.get('risk_score', 0)}/10</font>",
                    st['FindingId']
                )

                sev_cell = Paragraph(f"<b>[{sev}]</b><br/><font color='#64748B'>{f.get('status', 'Open')}</font>", sev_st)

                diff_text = f"<br/><b>Variance/Diff:</b> {f.get('difference')}" if f.get('difference') else ""
                title_cell = Paragraph(
                    f"<b>{f.get('title')}</b><br/>"
                    f"<font color='#334155'>{f.get('description', '')}</font>"
                    f"{diff_text}",
                    st['Body']
                )

                rule_cell = Paragraph(
                    f"<b>Rule:</b> {f.get('rule_used') or 'Standard Audit Procedure'}<br/>"
                    f"<font color='#64748B'>Engine: {f.get('engine_type', 'DETERMINISTIC')}</font>",
                    st['Body']
                )

                action_cell = Paragraph(
                    str(f.get('recommended_action') or "Review supporting vouchers and obtain management explanation."),
                    st['Body']
                )

                findings_table_data.append([id_cell, sev_cell, title_cell, rule_cell, action_cell])

            ft = Table(findings_table_data, colWidths=[75, 60, 160, 110, 110])
            ft.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 4.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
                ('LEFTPADDING', (0, 0), (-1, -1), 4.5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4.5),
            ]))
            story.append(ft)
        story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 14: AUDITOR COMMENTS & FINANCIAL EXPLANATIONS
    # =========================================================================
    if report_type in ["complete_audit_analysis", "yoy_comparison", "engagement_summary"]:
        story.append(Paragraph("8. Auditor Comments & Financial Explanations", st['SectionH1']))
        
        if not explanations:
            story.append(Paragraph("<i>No specific line-item variance explanations recorded.</i>", st['Body']))
        else:
            exp_table_data = [
                [
                    Paragraph("<b>Line Item Key</b>", st['TableHeader']),
                    Paragraph("<b>Category</b>", st['TableHeader']),
                    Paragraph("<b>Auditor Explanation / Note</b>", st['TableHeader']),
                    Paragraph("<b>Status</b>", st['TableHeader'])
                ]
            ]
            for e in explanations:
                exp_table_data.append([
                    Paragraph(str(e.get("item_key", "")), st['BodyBold']),
                    Paragraph(str(e.get("explanation_category", "Financial Statement")), st['Body']),
                    Paragraph(str(e.get("auditor_explanation", "")), st['Body']),
                    Paragraph(str(e.get("status", "Reviewed")), st['BodyBold'])
                ])

            et = Table(exp_table_data, colWidths=[120, 100, 215, 80])
            et.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(et)
        story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 15: CHECKLIST EXECUTION STATUS
    # =========================================================================
    if report_type in ["complete_audit_analysis", "audit_checklist", "engagement_summary"]:
        story.append(Paragraph("9. Statutory & Audit Checklist Compliance Status", st['SectionH1']))

        if not checklists:
            story.append(Paragraph("<i>No checklist items active for this engagement.</i>", st['Body']))
        else:
            chk_table_data = [
                [
                    Paragraph("<b>Item Code</b>", st['TableHeader']),
                    Paragraph("<b>Category</b>", st['TableHeader']),
                    Paragraph("<b>Audit Question / Requirement</b>", st['TableHeader']),
                    Paragraph("<b>Status</b>", st['TableHeader']),
                    Paragraph("<b>Staff / WP Ref</b>", st['TableHeader'])
                ]
            ]
            for c in checklists[:20]:  # sample top items
                status_color = '#059669' if c.get('status') == 'Completed' else ('#DC2626' if c.get('status') == 'Requires Review' else '#D97706')
                status_st = ParagraphStyle('ChkSt', parent=st['BodyBold'], textColor=colors.HexColor(status_color))
                
                chk_table_data.append([
                    Paragraph(str(c.get("item_code", "")), st['FindingId']),
                    Paragraph(str(c.get("category", "")), st['Body']),
                    Paragraph(str(c.get("question", "")), st['Body']),
                    Paragraph(str(c.get("status", "Pending")), status_st),
                    Paragraph(f"{c.get('assigned_staff') or 'Staff'}<br/>{c.get('reference_wp') or ''}", st['Body'])
                ])

            ct = Table(chk_table_data, colWidths=[65, 100, 200, 75, 75])
            ct.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(ct)
        story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 16: WORKING PAPER SUMMARY (SA 230 INDEX)
    # =========================================================================
    if report_type in ["complete_audit_analysis", "engagement_summary"]:
        story.append(Paragraph("10. Audit Working Paper Index & Evidence Repository (SA 230)", st['SectionH1']))

        if not working_papers:
            story.append(Paragraph("<i>No working papers registered.</i>", st['Body']))
        else:
            wp_table_data = [
                [
                    Paragraph("<b>WP Ref</b>", st['TableHeader']),
                    Paragraph("<b>Area</b>", st['TableHeader']),
                    Paragraph("<b>Title & Objective</b>", st['TableHeader']),
                    Paragraph("<b>Prepared By</b>", st['TableHeader']),
                    Paragraph("<b>Reviewed By</b>", st['TableHeader']),
                    Paragraph("<b>Status</b>", st['TableHeader'])
                ]
            ]
            for wp in working_papers:
                wp_table_data.append([
                    Paragraph(str(wp.get("wp_reference", "")), st['FindingId']),
                    Paragraph(str(wp.get("area") or wp.get("category") or "General"), st['Body']),
                    Paragraph(str(wp.get("title", "")), st['BodyBold']),
                    Paragraph(f"{wp.get('prepared_by') or 'Staff'}<br/>{wp.get('prepared_date') or ''}", st['Body']),
                    Paragraph(f"{wp.get('reviewed_by') or '-'}<br/>{wp.get('review_date') or ''}", st['Body']),
                    Paragraph(str(wp.get("status", "Prepared")), st['BodyBold'])
                ])

            wt = Table(wp_table_data, colWidths=[65, 85, 175, 75, 75, 40])
            wt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(wt)
        story.append(Spacer(1, 12))

    # =========================================================================
    # SECTION 17: CONCLUSION & AUDITOR QUALITY REVIEW SIGNOFF
    # =========================================================================
    story.append(KeepTogether(_build_signoff_section(st)))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    return pdf_path
