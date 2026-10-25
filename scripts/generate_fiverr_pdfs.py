import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        # Header
        self.drawString(54, 842 - 36, "FinAuditPro Enterprise | AI-Assisted Financial Audit Suite")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 842 - 42, 595 - 54, 842 - 42)
        # Footer
        self.line(54, 45, 595 - 54, 45)
        self.drawString(54, 32, "Confidential - Prepared for Client Evaluation & Delivery")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(595 - 54, 32, page_str)
        self.restoreState()

def build_pdf_1(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        spaceAfter=15
    )
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=14,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8
    )
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    )
    table_hdr = ParagraphStyle(
        'TableHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.white
    )

    story = []

    # Title Banner
    story.append(Spacer(1, 10))
    story.append(Paragraph("FinAuditPro: Solution Architecture & Technical Guide", title_style))
    story.append(Paragraph("Enterprise Client Technical Deliverable & Deployment Documentation | Prepared for Fiverr Client Project", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceBefore=2, spaceAfter=14))

    # Executive Overview
    story.append(Paragraph("1. Executive Summary & Value Proposition", h2_style))
    story.append(Paragraph(
        "<b>FinAuditPro</b> is an intelligent, offline-capable, enterprise-grade statutory audit and financial risk surveillance platform. "
        "Engineered specifically for certified chartered accountants, audit firms, and corporate controllers, it eliminates "
        "hours of manual verification by automating 3-way reconciliation (Bank, Ledger, GST), Benford's Law anomaly detection, "
        "and duplicate transaction identification while upholding 100% data residency and bank-grade privacy.",
        body_style
    ))

    # Core Specifications Table
    story.append(Paragraph("2. Technical Stack & Architecture", h2_style))
    spec_data = [
        [Paragraph("Component", table_hdr), Paragraph("Technology / Framework", table_hdr), Paragraph("Implementation Details", table_hdr)],
        [Paragraph("Backend Core", table_cell), Paragraph("Python 3.10+ / FastAPI", table_cell), Paragraph("High-throughput REST API with Pydantic validation & PyJWT security", table_cell)],
        [Paragraph("Database Engine", table_cell), Paragraph("SQLite (WAL Mode Enabled)", table_cell), Paragraph("Zero-configuration offline storage with foreign keys & ACID compliance", table_cell)],
        [Paragraph("Analytics Engine", table_cell), Paragraph("NumPy, SciPy, Scikit-Learn", table_cell), Paragraph("Benford distribution z-score, Isolation Forest outlier modeling", table_cell)],
        [Paragraph("Frontend Client", table_cell), Paragraph("Vanilla JS, HTML5, Custom CSS", table_cell), Paragraph("Zero external CDN dependencies, glassmorphism UI & live charts", table_cell)],
        [Paragraph("Reporting Engine", table_cell), Paragraph("ReportLab 5.0+ Engine", table_cell), Paragraph("Dynamic vector PDF generation with audit working-paper tables", table_cell)],
    ]
    t_spec = Table(spec_data, colWidths=[110, 140, 237])
    t_spec.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#F8FAFC"), colors.white]),
    ]))
    story.append(t_spec)

    # Core Modules
    story.append(Paragraph("3. Core Functional Modules", h2_style))
    module_data = [
        [Paragraph("Module", table_hdr), Paragraph("Key Features", table_hdr), Paragraph("Audit & Regulatory Value", table_hdr)],
        [Paragraph("3-Way Reconciliation", table_cell), Paragraph("Cross-checks Bank statement vs General Ledger vs GST portal invoices.", table_cell), Paragraph("Detects unrecorded expenses, timing mismatches, and missed Input Tax Credit (ITC).", table_cell)],
        [Paragraph("Benford's Law Engine", table_cell), Paragraph("Analyzes first-digit logarithmic distributions across all transaction amounts.", table_cell), Paragraph("Flags deliberate invoice fabrication, fraud, and synthetic transaction tampering.", table_cell)],
        [Paragraph("Duplicate Detector", table_cell), Paragraph("Detects identical amounts, duplicate invoice references, and inverted double-postings.", table_cell), Paragraph("Prevents accidental double vendor payments and fraudulent reimbursement claims.", table_cell)],
        [Paragraph("Sampling Generator", table_cell), Paragraph("Monetary Unit Sampling (MUS), Stratified Random, and High-Risk sampling.", table_cell), Paragraph("Complies with ISA 530 & ICAI Standards on Auditing (SA 530) guidelines.", table_cell)],
    ]
    t_mod = Table(module_data, colWidths=[110, 187, 190])
    t_mod.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0D9488")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#F0FDFA"), colors.white]),
    ]))
    story.append(t_mod)

    # Quick Setup & Operational Instructions
    story.append(Paragraph("4. Quick Start & Execution Guide", h2_style))
    story.append(Paragraph(
        "<b>Step 1 - Environment Activation:</b> Run <code>source venv/bin/activate</code> (or <code>start.bat</code> on Windows).<br/>"
        "<b>Step 2 - Launch Application:</b> Run <code>python run.py</code> to initialize the SQLite database schema and launch server on <code>http://127.0.0.1:8000</code>.<br/>"
        "<b>Step 3 - Authentication:</b> Log in with credentials: Username: <code>admin</code> | Password: <code>SecureAdmin2026!</code>.<br/>"
        "<b>Step 4 - Audit Workflow:</b> Create an Engagement &rarr; Import CSV/Excel trial balances &rarr; Run AI anomaly scans &rarr; Export sign-off PDF report.",
        body_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[✓] Created PDF 1: {output_path}")

def build_pdf_2(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle2',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSub2',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12
    )
    h2_style = ParagraphStyle(
        'DocH2_2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=10,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        'DocBody2',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6
    )
    table_cell = ParagraphStyle(
        'TableCell2',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#1E293B")
    )
    table_hdr = ParagraphStyle(
        'TableHdr2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.white
    )

    story = []

    # Title & Metadata Banner
    story.append(Spacer(1, 10))
    story.append(Paragraph("INDEPENDENT STATUTORY AUDIT & RECONCILIATION REPORT", title_style))
    story.append(Paragraph("Sample Audit Engagement Deliverable | Aryan Fintech Solutions Pvt. Ltd. | FY 2025-26", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#DC2626"), spaceBefore=2, spaceAfter=10))

    # Engagement Info Card
    meta_data = [
        [Paragraph("<b>Client Name:</b> Aryan Fintech Solutions Pvt. Ltd.", table_cell), Paragraph("<b>Engagement Ref:</b> ENG-2026-0891-STAT", table_cell)],
        [Paragraph("<b>Audit Period:</b> 01-Apr-2025 to 31-Mar-2026", table_cell), Paragraph("<b>Lead Auditor:</b> Senior Chartered Accountant (Admin)", table_cell)],
        [Paragraph("<b>Audit Opinion:</b> Qualified Opinion (Exceptions Flagged)", table_cell), Paragraph("<b>Standard Followed:</b> Standards on Auditing (SA 200-705)", table_cell)],
    ]
    t_meta = Table(meta_data, colWidths=[243, 244])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 8))

    # Audit Scope & Executive Summary
    story.append(Paragraph("1. Audit Findings & Anomaly Summary", h2_style))
    story.append(Paragraph(
        "We have conducted an automated and substantive financial audit of Aryan Fintech Solutions Pvt. Ltd. "
        "utilizing the FinAuditPro algorithmic surveillance suite. During the engagement, 1,248 transactions "
        "aggregating to INR 48,920,400 were analyzed against bank statements, general ledger balances, and GSTR-2B returns. "
        "A total of <b>3 high-risk exceptions</b> were identified requiring management rectification or provision adjustment.",
        body_style
    ))

    # Findings Table
    findings_data = [
        [Paragraph("Ref ID", table_hdr), Paragraph("Risk Level", table_hdr), Paragraph("Audit Test", table_hdr), Paragraph("Discrepancy Details", table_hdr), Paragraph("Impact (INR)", table_hdr)],
        [Paragraph("FND-0101", table_cell), Paragraph("<font color='#DC2626'><b>HIGH</b></font>", table_cell), Paragraph("Bank 3-Way Rec", table_cell), Paragraph("Unreconciled bank outflow dated 14-Jan-2026 missing corresponding vendor invoice in purchase register.", table_cell), Paragraph("₹ 4,50,000", table_cell)],
        [Paragraph("FND-0102", table_cell), Paragraph("<font color='#DC2626'><b>HIGH</b></font>", table_cell), Paragraph("GST Rec (2B vs GL)", table_cell), Paragraph("ITC claimed in GSTR-3B for vendor GSTIN 07AABCT8921K1ZX not appearing in GSTR-2B inward supplies.", table_cell), Paragraph("₹ 1,82,400", table_cell)],
        [Paragraph("FND-0103", table_cell), Paragraph("<font color='#D97706'><b>MEDIUM</b></font>", table_cell), Paragraph("Benford Anomaly", table_cell), Paragraph("Abnormal spike in transactions starting with digit '9' in petty cash disbursements (z-score > 3.8).", table_cell), Paragraph("₹ 87,500", table_cell)],
        [Paragraph("FND-0104", table_cell), Paragraph("<font color='#2563EB'><b>LOW</b></font>", table_cell), Paragraph("Duplicate Scan", table_cell), Paragraph("Duplicate payment reference voucher #VP-902 posted twice within 24 hours to office supplies vendor.", table_cell), Paragraph("₹ 14,200", table_cell)],
    ]
    t_fnd = Table(findings_data, colWidths=[48, 55, 84, 220, 80])
    t_fnd.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FEF2F2"), colors.white]),
    ]))
    story.append(t_fnd)

    # Substantive Bank Reconciliation Sample
    story.append(Paragraph("2. Substantive Bank Reconciliation Schedule", h2_style))
    recon_data = [
        [Paragraph("Particulars / Narration", table_hdr), Paragraph("Date", table_hdr), Paragraph("Ref Voucher", table_hdr), Paragraph("GL Balance (INR)", table_hdr), Paragraph("Bank Balance (INR)", table_hdr), Paragraph("Variance", table_hdr)],
        [Paragraph("Balance as per Bank Statement (HDFC Bank)", table_cell), Paragraph("31-Mar-2026", table_cell), Paragraph("STMT-9901", table_cell), Paragraph("-", table_cell), Paragraph("₹ 1,28,45,210.00", table_cell), Paragraph("-", table_cell)],
        [Paragraph("<i>Add:</i> Cheques deposited but not credited", table_cell), Paragraph("28-Mar-2026", table_cell), Paragraph("CHQ-448102", table_cell), Paragraph("₹ 6,20,000.00", table_cell), Paragraph("-", table_cell), Paragraph("+ ₹ 6,20,000.00", table_cell)],
        [Paragraph("<i>Less:</i> Cheques issued but not presented", table_cell), Paragraph("30-Mar-2026", table_cell), Paragraph("CHQ-551904", table_cell), Paragraph("₹ 3,75,000.00", table_cell), Paragraph("-", table_cell), Paragraph("- ₹ 3,75,000.00", table_cell)],
        [Paragraph("<i>Less:</i> Direct bank debit (unrecorded charges)", table_cell), Paragraph("31-Mar-2026", table_cell), Paragraph("BK-DR-118", table_cell), Paragraph("-", table_cell), Paragraph("₹ 12,450.00", table_cell), Paragraph("- ₹ 12,450.00", table_cell)],
        [Paragraph("<b>Adjusted Balance as per General Ledger</b>", table_cell), Paragraph("31-Mar-2026", table_cell), Paragraph("AUDIT-ADJ", table_cell), Paragraph("<b>₹ 1,30,77,760.00</b>", table_cell), Paragraph("<b>₹ 1,30,77,760.00</b>", table_cell), Paragraph("<b>RECONCILED</b>", table_cell)],
    ]
    t_rec = Table(recon_data, colWidths=[157, 55, 65, 75, 75, 60])
    t_rec.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.HexColor("#F8FAFC"), colors.white]),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#DCFCE7")),
    ]))
    story.append(t_rec)

    # Auditor Conclusion & Signatures
    story.append(Paragraph("3. Auditor Conclusion & Certification", h2_style))
    story.append(Paragraph(
        "Subject to the reconciliation adjustments identified above, in our opinion and to the best of our information "
        "and according to the explanations given to us, the financial statements present fairly, in all material respects, "
        "the financial position of the Company as of March 31, 2026.",
        body_style
    ))
    story.append(Spacer(1, 10))

    sig_data = [
        [Paragraph("<b>For & on behalf of Statutory Audit Team:</b>", table_cell), Paragraph("<b>Acknowledged by Client Representative:</b>", table_cell)],
        [Paragraph("<br/><br/>__________________________________<br/><b>Lead Auditor (FCA, CPA)</b><br/>Membership No: 084920<br/>FinAuditPro Audit Technologies", table_cell),
         Paragraph("<br/><br/>__________________________________<br/><b>Managing Director / CFO</b><br/>Aryan Fintech Solutions Pvt. Ltd.<br/>Date: 25-Oct-2026", table_cell)]
    ]
    t_sig = Table(sig_data, colWidths=[243, 244])
    t_sig.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(KeepTogether(t_sig))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[✓] Created PDF 2: {output_path}")

if __name__ == "__main__":
    out_dir = "/Users/aryan/Desktop/PROJECTS/TempAudit-main/fiverr_deliverables"
    os.makedirs(out_dir, exist_ok=True)
    pdf1 = os.path.join(out_dir, "FinAuditPro_Project_Technical_Overview.pdf")
    pdf2 = os.path.join(out_dir, "FinAuditPro_Sample_Statutory_Audit_Report.pdf")
    build_pdf_1(pdf1)
    build_pdf_2(pdf2)
