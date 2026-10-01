from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from typing import List, Optional
from backend.app.schemas import EngagementCreate, EngagementUpdate, DuplicateEngagementRequest
from backend.app.auth import get_current_user, require_role, require_engagement_access
from backend.app.database import get_db_connection

router = APIRouter(prefix="/api/engagements", tags=["Audit Engagements Management"])

VALID_AUDIT_TYPES = [
    "Statutory Audit",
    "Internal Audit",
    "Tax Audit",
    "Review",
    "Special Audit",
    "Other"
]

VALID_STATUSES = [
    "Draft",
    "In Progress",
    "Under Review",
    "Completed",
    "Archived"
]

from backend.app.services.dashboard_service import DashboardService

@router.get("/dashboard/summary-stats")
def get_dashboard_summary_stats(
    engagement_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """Provides high-level dashboard metrics across engagements and for active engagement."""
    if engagement_id:
        require_engagement_access(engagement_id, current_user)

    conn = get_db_connection()
    try:
        # 1. Total Active Clients
        active_clients_count = conn.execute("SELECT COUNT(*) as c FROM clients").fetchone()["c"]

        # 2. Total Active Engagements
        active_eng_count = conn.execute("SELECT COUNT(*) as c FROM engagements WHERE status IN ('Draft', 'In Progress', 'Under Review')").fetchone()["c"]
        
        # 3. Pending Reviews
        pending_review_count = conn.execute("SELECT COUNT(*) as c FROM engagements WHERE status = 'Under Review'").fetchone()["c"]
        pending_review_engs = [dict(r) for r in conn.execute("""
            SELECT e.id, e.title, e.financial_year, c.name as client_name
            FROM engagements e
            JOIN clients c ON e.client_id = c.id
            WHERE e.status = 'Under Review'
        """).fetchall()]

        # 4. Completed Engagements
        completed_eng_count = conn.execute("SELECT COUNT(*) as c FROM engagements WHERE status = 'Completed'").fetchone()["c"]

        # 5. Total Archived Engagements
        archived_eng_count = conn.execute("SELECT COUNT(*) as c FROM engagements WHERE status = 'Archived'").fetchone()["c"]

        # 6. Open & High-Risk Findings (For active engagement or overall)
        if engagement_id:
            open_findings_count = conn.execute("SELECT COUNT(*) as c FROM audit_findings WHERE engagement_id = ? AND status IN ('Open', 'In Review')", (engagement_id,)).fetchone()["c"]
            high_risk_findings_count = conn.execute("SELECT COUNT(*) as c FROM audit_findings WHERE engagement_id = ? AND severity IN ('CRITICAL', 'HIGH')", (engagement_id,)).fetchone()["c"]
            crit_findings_count = conn.execute("SELECT COUNT(*) as c FROM audit_findings WHERE engagement_id = ? AND severity = 'CRITICAL'", (engagement_id,)).fetchone()["c"]
            turnover = conn.execute("SELECT SUM(debit) as s FROM transactions WHERE engagement_id = ?", (engagement_id,)).fetchone()["s"] or 0.0
            
            # Unmatched transactions
            unmatched_count = conn.execute("""
                SELECT COUNT(*) as c FROM reconciliation_items ri
                JOIN reconciliations r ON ri.recon_id = r.id
                WHERE r.engagement_id = ? AND (ri.status IN ('Unmatched', 'Suggested') OR ri.match_level = 'UNMATCHED')
            """, (engagement_id,)).fetchone()["c"]
            if unmatched_count == 0:
                recon_summary = conn.execute("SELECT SUM(unmatched_bank_count + unmatched_book_count) as s FROM reconciliations WHERE engagement_id = ?", (engagement_id,)).fetchone()["s"]
                unmatched_count = int(recon_summary or 0)
        else:
            open_findings_count = conn.execute("SELECT COUNT(*) as c FROM audit_findings WHERE status IN ('Open', 'In Review')").fetchone()["c"]
            high_risk_findings_count = conn.execute("SELECT COUNT(*) as c FROM audit_findings WHERE severity IN ('CRITICAL', 'HIGH')").fetchone()["c"]
            crit_findings_count = conn.execute("SELECT COUNT(*) as c FROM audit_findings WHERE severity = 'CRITICAL'").fetchone()["c"]
            turnover = conn.execute("SELECT SUM(debit) as s FROM transactions").fetchone()["s"] or 0.0
            
            unmatched_count = conn.execute("""
                SELECT COUNT(*) as c FROM reconciliation_items WHERE status IN ('Unmatched', 'Suggested') OR match_level = 'UNMATCHED'
            """).fetchone()["c"]
            if unmatched_count == 0:
                recon_summary = conn.execute("SELECT SUM(unmatched_bank_count + unmatched_book_count) as s FROM reconciliations").fetchone()["s"]
                unmatched_count = int(recon_summary or 0)

        return {
            "active_clients_count": active_clients_count,
            "active_engagements_count": active_eng_count,
            "pending_reviews_count": pending_review_count,
            "pending_review_engagements": pending_review_engs,
            "completed_engagements_count": completed_eng_count,
            "archived_engagements_count": archived_eng_count,
            "open_findings_count": open_findings_count,
            "high_risk_findings_count": high_risk_findings_count,
            "critical_findings_count": crit_findings_count,
            "unmatched_transactions_count": unmatched_count,
            "total_turnover_examined": round(turnover, 2)
        }
    finally:
        conn.close()

@router.get("/dashboard/comprehensive")
def get_comprehensive_dashboard_route(
    engagement_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """Returns complete real database metrics across all dashboard cards, sections, charts, and drill-down datasets."""
    if engagement_id:
        require_engagement_access(engagement_id, current_user)
    try:
        return DashboardService.get_comprehensive_dashboard(engagement_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate dashboard metrics: {str(e)}")

@router.get("/{engagement_id}/comprehensive-dashboard")
def get_engagement_comprehensive_dashboard_route(
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Returns comprehensive dashboard data for a specific engagement."""
    require_engagement_access(engagement_id, current_user)
    try:
        return DashboardService.get_comprehensive_dashboard(engagement_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate engagement dashboard: {str(e)}")

@router.get("")
def list_engagements(
    client_id: Optional[int] = None,
    financial_year: Optional[str] = None,
    audit_type: Optional[str] = None,
    status: Optional[str] = None,
    include_archived: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """List engagements with multi-criteria filtering and aggregated metrics."""
    conn = get_db_connection()
    try:
        query = """
            SELECT e.*, c.name as client_name, c.pan as client_pan, c.gstin as client_gstin,
                   c.entity_type as client_entity_type, c.industry as client_industry,
                   u.full_name as lead_auditor_name, s.full_name as assigned_staff_name,
                   COALESCE((SELECT COUNT(*) FROM transactions t WHERE t.engagement_id = e.id), 0) as transactions_count,
                   COALESCE((SELECT COUNT(*) FROM audit_findings f WHERE f.engagement_id = e.id), 0) as findings_count,
                   COALESCE((SELECT COUNT(*) FROM audit_findings f WHERE f.engagement_id = e.id AND f.severity = 'CRITICAL'), 0) as critical_findings_count,
                   COALESCE((SELECT SUM(debit) FROM transactions t WHERE t.engagement_id = e.id), 0.0) as turnover
            FROM engagements e
            JOIN clients c ON e.client_id = c.id
            LEFT JOIN users u ON e.lead_auditor_id = u.id
            LEFT JOIN users s ON e.assigned_staff_id = s.id
            WHERE 1=1
        """
        params = []

        if client_id:
            query += " AND e.client_id = ?"
            params.append(client_id)
        if financial_year:
            query += " AND e.financial_year = ?"
            params.append(financial_year)
        if audit_type and audit_type != "All":
            query += " AND e.audit_type = ?"
            params.append(audit_type)
        if status and status != "All":
            query += " AND e.status = ?"
            params.append(status)
        elif not include_archived:
            query += " AND e.status != 'Archived'"

        # If user is Audit Staff, only return engagements where assigned or lead
        if current_user.get("role") not in ["Admin", "Auditor"]:
            user_id = current_user.get("id")
            query += " AND (e.lead_auditor_id = ? OR e.assigned_staff_id = ?)"
            params.extend([user_id, user_id])

        query += " ORDER BY e.id DESC"
        rows = conn.execute(query, tuple(params)).fetchall()

        engagements = []
        for r in rows:
            e = dict(r)
            e["turnover"] = round(float(e.get("turnover") or 0.0), 2)
            engagements.append(e)

        return engagements
    finally:
        conn.close()

@router.get("/{engagement_id}")
def get_engagement_details(
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Retrieve detailed engagement record with isolated summary metrics."""
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT e.*, c.name as client_name, c.pan as client_pan, c.gstin as client_gstin,
                   c.address as client_address, c.entity_type as client_entity_type,
                   c.industry as client_industry, c.contact_person, c.email as client_email,
                   u.full_name as lead_auditor_name, s.full_name as assigned_staff_name,
                   COALESCE((SELECT COUNT(*) FROM transactions t WHERE t.engagement_id = e.id), 0) as transactions_count,
                   COALESCE((SELECT SUM(debit) FROM transactions t WHERE t.engagement_id = e.id), 0.0) as total_debit,
                   COALESCE((SELECT SUM(credit) FROM transactions t WHERE t.engagement_id = e.id), 0.0) as total_credit,
                   COALESCE((SELECT COUNT(*) FROM audit_findings f WHERE f.engagement_id = e.id), 0) as findings_count,
                   COALESCE((SELECT COUNT(*) FROM audit_findings f WHERE f.engagement_id = e.id AND f.status IN ('Open', 'In Review')), 0) as open_findings,
                   COALESCE((SELECT COUNT(*) FROM audit_findings f WHERE f.engagement_id = e.id AND f.severity = 'CRITICAL'), 0) as critical_findings_count,
                   COALESCE((SELECT COUNT(*) FROM working_papers wp WHERE wp.engagement_id = e.id), 0) as working_papers_count,
                   COALESCE((SELECT COUNT(*) FROM audit_checklists chk WHERE chk.engagement_id = e.id), 0) as checklist_count
            FROM engagements e
            JOIN clients c ON e.client_id = c.id
            LEFT JOIN users u ON e.lead_auditor_id = u.id
            LEFT JOIN users s ON e.assigned_staff_id = s.id
            WHERE e.id = ?
        """, (engagement_id,)).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Engagement not found")

        engagement = dict(row)
        engagement["total_debit"] = round(float(engagement.get("total_debit") or 0.0), 2)
        engagement["total_credit"] = round(float(engagement.get("total_credit") or 0.0), 2)
        return engagement
    finally:
        conn.close()

@router.post("")
def create_engagement(eng_data: EngagementCreate, current_user: dict = Depends(require_role(["Admin", "Auditor"]))):
    """Create a new engagement and initialize standard CARO / 3CD checklists."""
    conn = get_db_connection()
    client = conn.execute("SELECT id, name FROM clients WHERE id = ?", (eng_data.client_id,)).fetchone()
    if not client:
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")

    now_str = datetime.now().isoformat()
    cursor = conn.execute("""
    INSERT INTO engagements (
        client_id, title, audit_type, financial_year, period_start,
        period_end, status, lead_auditor_id, assigned_staff_id, notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        eng_data.client_id,
        eng_data.title.strip(),
        eng_data.audit_type or "Statutory Audit",
        eng_data.financial_year.strip(),
        eng_data.period_start or f"{eng_data.financial_year.split('-')[0]}-04-01",
        eng_data.period_end or f"20{eng_data.financial_year.split('-')[1]}-03-31",
        eng_data.status or "In Progress",
        eng_data.lead_auditor_id or current_user.get("id", 1),
        eng_data.assigned_staff_id,
        eng_data.notes or "",
        now_str,
        now_str
    ))
    new_id = cursor.lastrowid

    # Auto seed standard checklist items
    from backend.app.services.checklist_templates import STANDARD_CHECKLIST_ITEMS
    for item in STANDARD_CHECKLIST_ITEMS:
        conn.execute("""
        INSERT INTO audit_checklists (engagement_id, category, item_code, question, guidance, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'Pending', ?)
        """, (new_id, item["category"], item["item_code"], item["question"], item["guidance"], now_str))

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="CREATE_ENGAGEMENT",
        module="ENGAGEMENTS",
        record_id=new_id,
        engagement_id=new_id,
        new_value={
            "client_id": eng_data.client_id,
            "title": eng_data.title.strip(),
            "audit_type": eng_data.audit_type,
            "financial_year": eng_data.financial_year.strip(),
            "status": eng_data.status or "In Progress"
        },
        details=f"Created engagement '{eng_data.title}' for client '{client['name']}'",
        user=current_user
    )

    conn.commit()
    conn.close()
    return {"id": new_id, "title": eng_data.title, "status": "created"}

@router.put("/{engagement_id}")
def update_engagement(engagement_id: int, eng_data: EngagementUpdate, current_user: dict = Depends(require_role(["Admin", "Auditor"]))):
    """Update engagement configuration, dates, auditor assignments, or notes."""
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    eng = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    if not eng:
        conn.close()
        raise HTTPException(status_code=404, detail="Engagement not found")

    old_eng_data = dict(eng)
    updates = []
    params = []
    new_changes = {}

    if eng_data.title is not None:
        updates.append("title = ?")
        params.append(eng_data.title.strip())
        new_changes["title"] = eng_data.title.strip()

    if eng_data.audit_type is not None:
        updates.append("audit_type = ?")
        params.append(eng_data.audit_type)
        new_changes["audit_type"] = eng_data.audit_type

    if eng_data.financial_year is not None:
        updates.append("financial_year = ?")
        params.append(eng_data.financial_year.strip())
        new_changes["financial_year"] = eng_data.financial_year.strip()

    if eng_data.period_start is not None:
        updates.append("period_start = ?")
        params.append(eng_data.period_start)
        new_changes["period_start"] = eng_data.period_start

    if eng_data.period_end is not None:
        updates.append("period_end = ?")
        params.append(eng_data.period_end)
        new_changes["period_end"] = eng_data.period_end

    if eng_data.lead_auditor_id is not None:
        updates.append("lead_auditor_id = ?")
        params.append(eng_data.lead_auditor_id)
        new_changes["lead_auditor_id"] = eng_data.lead_auditor_id

    if eng_data.assigned_staff_id is not None:
        updates.append("assigned_staff_id = ?")
        params.append(eng_data.assigned_staff_id)
        new_changes["assigned_staff_id"] = eng_data.assigned_staff_id

    if eng_data.status is not None:
        if eng_data.status not in VALID_STATUSES:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Invalid status. Choose from: {VALID_STATUSES}")
        updates.append("status = ?")
        params.append(eng_data.status)
        new_changes["status"] = eng_data.status

    if eng_data.notes is not None:
        updates.append("notes = ?")
        params.append(eng_data.notes.strip())
        new_changes["notes"] = eng_data.notes.strip()

    now_str = datetime.now().isoformat()
    updates.append("updated_at = ?")
    params.append(now_str)

    params.append(engagement_id)
    conn.execute(f"UPDATE engagements SET {', '.join(updates)} WHERE id = ?", tuple(params))

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="DATA_MODIFICATION",
        module="ENGAGEMENTS",
        record_id=engagement_id,
        engagement_id=engagement_id,
        old_value=old_eng_data,
        new_value=new_changes,
        details=f"Modified configuration of engagement '{eng['title']}'",
        user=current_user
    )

    conn.commit()
    conn.close()
    return {"message": "Engagement updated successfully"}

@router.put("/{engagement_id}/status")
def update_engagement_status(engagement_id: int, status: str, current_user: dict = Depends(require_role(["Admin", "Auditor"]))):
    """Change engagement status (Draft, In Progress, Under Review, Completed, Archived)."""
    require_engagement_access(engagement_id, current_user)
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Choose from: {VALID_STATUSES}")

    conn = get_db_connection()
    eng = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    if not eng:
        conn.close()
        raise HTTPException(status_code=404, detail="Engagement not found")

    old_status = eng["status"]
    now_str = datetime.now().isoformat()
    conn.execute("UPDATE engagements SET status = ?, updated_at = ? WHERE id = ?", (status, now_str, engagement_id))

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="DATA_MODIFICATION",
        module="ENGAGEMENTS",
        record_id=engagement_id,
        engagement_id=engagement_id,
        old_value={"status": old_status},
        new_value={"status": status},
        details=f"Changed engagement '{eng['title']}' status from '{old_status}' to '{status}'",
        user=current_user
    )

    conn.commit()
    conn.close()
    return {"message": f"Engagement status updated to {status}", "status": status, "new_status": status}

@router.post("/duplicate")
def duplicate_engagement_structure(req: DuplicateEngagementRequest, current_user: dict = Depends(require_role(["Admin", "Auditor"]))):
    """
    Duplicates the audit engagement structure from a prior financial year into a new year.
    Clones checklists and working paper templates while keeping transaction data clean and isolated.
    """
    require_engagement_access(req.source_engagement_id, current_user)
    conn = get_db_connection()
    src_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (req.source_engagement_id,)).fetchone()
    if not src_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Source engagement not found")

    src_eng = dict(src_row)
    now_str = datetime.now().isoformat()

    # Generate title if not given
    new_title = req.title or f"{src_eng['audit_type']} FY {req.target_financial_year}"
    target_fy = req.target_financial_year.strip()

    # Create new engagement
    cursor = conn.execute("""
    INSERT INTO engagements (
        client_id, title, audit_type, financial_year, period_start,
        period_end, status, lead_auditor_id, assigned_staff_id, notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, 'Draft', ?, ?, ?, ?, ?)
    """, (
        src_eng["client_id"],
        new_title,
        src_eng["audit_type"],
        target_fy,
        f"{target_fy.split('-')[0]}-04-01",
        f"20{target_fy.split('-')[1]}-03-31",
        src_eng["lead_auditor_id"],
        src_eng["assigned_staff_id"],
        f"Cloned audit structure from FY {src_eng['financial_year']}",
        now_str,
        now_str
    ))
    new_engagement_id = cursor.lastrowid

    cloned_checklists = 0
    cloned_wps = 0

    # 1. Clone Checklists (Reset status to Pending)
    if req.copy_checklists:
        src_checklists = conn.execute("SELECT * FROM audit_checklists WHERE engagement_id = ?", (req.source_engagement_id,)).fetchall()
        for chk in src_checklists:
            conn.execute("""
            INSERT INTO audit_checklists (
                engagement_id, category, item_code, question, guidance, status, auditor_remarks, reference_wp, created_at
            ) VALUES (?, ?, ?, ?, ?, 'Pending', '', '', ?)
            """, (new_engagement_id, chk["category"], chk["item_code"], chk["question"], chk["guidance"], now_str))
            cloned_checklists += 1

    # 2. Clone Working Paper Templates (Reset status to Prepared)
    if req.copy_working_paper_templates:
        src_wps = conn.execute("SELECT * FROM working_papers WHERE engagement_id = ?", (req.source_engagement_id,)).fetchall()
        for wp in src_wps:
            wp_dict = dict(wp)
            area_val = wp_dict.get("area") or wp_dict.get("category") or "General"
            conn.execute("""
            INSERT INTO working_papers (
                engagement_id, wp_reference, title, area, category, description,
                evidence, notes, attached_files_json, prepared_by, prepared_date, reviewed_by, review_date, status,
                reviewer_comments_json, linked_findings_json, linked_transactions_json, linked_checklists_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, '', '', 'Prepared', '[]', '[]', '[]', '[]', ?, ?)
            """, (
                new_engagement_id, wp_dict["wp_reference"], wp_dict["title"], area_val, wp_dict.get("category"),
                wp_dict.get("description"), wp_dict.get("evidence"), wp_dict.get("notes"),
                current_user.get("full_name", "Auditor"), now_str[:10], now_str, now_str
            ))
            cloned_wps += 1

    # Log action
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action="DUPLICATE_ENGAGEMENT",
        module="ENGAGEMENTS",
        record_id=new_engagement_id,
        user=current_user,
        engagement_id=new_engagement_id,
        details=f"Duplicated structure from Engagement #{req.source_engagement_id} (FY {src_eng['financial_year']}) to FY {target_fy}: {cloned_checklists} checklists, {cloned_wps} WPs.",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "new_engagement_id": new_engagement_id,
        "title": new_title,
        "financial_year": target_fy,
        "cloned_checklists": cloned_checklists,
        "cloned_working_papers": cloned_wps,
        "message": f"Successfully created new engagement for FY {target_fy} with cloned audit structures."
    }
