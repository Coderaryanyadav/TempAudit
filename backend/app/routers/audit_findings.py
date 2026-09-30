import io
import csv
import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from backend.app.schemas import FindingUpdate, FindingCreateCustom
from backend.app.auth import get_current_user, require_engagement_access
from backend.app.database import get_db_connection
from backend.app.audit_engine.engine import HybridAuditEngine
from backend.app.services.centralized_findings_engine import CentralizedFindingsEngine

router = APIRouter(prefix="/api/findings", tags=["Audit Findings & Risk Management"])

@router.post("/run-engine/{engagement_id}")
def run_hybrid_audit(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """Triggers hybrid audit engine and synchronizes into centralized findings."""
    require_engagement_access(engagement_id, current_user)
    try:
        engine = HybridAuditEngine(engagement_id)
        results = engine.execute_audit()
        # Also trigger full centralized synchronization
        CentralizedFindingsEngine.sync_all_engagement_findings(engagement_id)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit Engine failed: {str(e)}")

@router.post("/{engagement_id}/sync")
def sync_all_findings(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """
    Centralized Ingestion: Pulls audit exceptions from all modules
    (Tax Rules, Duplicate/Missing Sequences, Hybrid ML Anomalies, YoY Variances,
     Trial Balance, General Ledger, BRS, and GST Reconciliations) and calculates
    deterministic explainable risk scores.
    """
    require_engagement_access(engagement_id, current_user)
    try:
        sync_result = CentralizedFindingsEngine.sync_all_engagement_findings(engagement_id)
        return {
            "status": "success",
            "message": f"Synchronized {sync_result['total_collected']} findings from all audit modules.",
            "data": sync_result
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to synchronize findings: {str(e)}")

@router.get("/{engagement_id}/dashboard-summary")
def get_findings_dashboard_summary(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """
    Returns executive metrics for the findings dashboard:
    Total Findings, Open Findings, High Risk, Critical, Resolved, Under Review,
    and breakdowns by module & severity.
    """
    require_engagement_access(engagement_id, current_user)
    try:
        summary = CentralizedFindingsEngine.get_dashboard_summary(engagement_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dashboard summary: {str(e)}")

@router.get("/{engagement_id}")
def get_findings(
    engagement_id: int,
    severity: Optional[str] = None,
    module: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    engine_type: Optional[str] = None,
    search: Optional[str] = None,
    min_risk_score: Optional[float] = None,
    max_risk_score: Optional[float] = None,
    sort_by: Optional[str] = Query("risk_score_desc", description="risk_score_desc, severity_desc, created_desc, id_asc"),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves centralized audit findings with comprehensive filtering, search, and sorting.
    """
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    query = "SELECT * FROM audit_findings WHERE engagement_id = ?"
    params = [engagement_id]

    if severity:
        query += " AND UPPER(severity) = ?"
        params.append(severity.upper())
    if module:
        query += " AND module = ?"
        params.append(module)
    if category:
        query += " AND category = ?"
        params.append(category)
    if status:
        query += " AND status = ?"
        params.append(status)
    if engine_type:
        query += " AND engine_type = ?"
        params.append(engine_type)
    if min_risk_score is not None:
        query += " AND risk_score >= ?"
        params.append(min_risk_score)
    if max_risk_score is not None:
        query += " AND risk_score <= ?"
        params.append(max_risk_score)
    if search:
        search_pattern = f"%{search.strip()}%"
        query += " AND (finding_code LIKE ? OR title LIKE ? OR description LIKE ? OR rule_used LIKE ? OR reason LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern, search_pattern])

    # Sorting
    if sort_by == "risk_score_desc":
        query += " ORDER BY risk_score DESC, id ASC"
    elif sort_by == "severity_desc":
        query += """ ORDER BY 
            CASE UPPER(severity) 
                WHEN 'CRITICAL' THEN 1 
                WHEN 'HIGH' THEN 2 
                WHEN 'MEDIUM' THEN 3 
                WHEN 'LOW' THEN 4 
                ELSE 5 
            END ASC, risk_score DESC"""
    elif sort_by == "created_desc":
        query += " ORDER BY created_at DESC, id DESC"
    elif sort_by == "id_asc":
        query += " ORDER BY id ASC"
    else:
        query += " ORDER BY risk_score DESC, id ASC"

    rows = conn.execute(query, tuple(params)).fetchall()

    findings = []
    for r in rows:
        f = dict(r)
        # Parse JSON fields safely
        try:
            f["affected_records"] = json.loads(f.get("affected_records_json") or "[]")
        except Exception:
            f["affected_records"] = []
        try:
            f["evidence"] = json.loads(f.get("evidence_json") or "{}")
        except Exception:
            f["evidence"] = {}
        try:
            f["risk_factors"] = json.loads(f.get("risk_factors_json") or "{}")
        except Exception:
            f["risk_factors"] = {}
        findings.append(f)

    conn.close()
    return findings

@router.get("/detail/{finding_id}")
def get_finding_detail(finding_id: int, current_user: dict = Depends(get_current_user)):
    """Retrieves single finding detail with full affected transaction records and evidence."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM audit_findings WHERE id = ?", (finding_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Finding not found")

    finding = dict(row)
    require_engagement_access(finding["engagement_id"], current_user)
    try:
        finding["affected_records"] = json.loads(finding.get("affected_records_json") or "[]")
    except Exception:
        finding["affected_records"] = []
    try:
        finding["evidence"] = json.loads(finding.get("evidence_json") or "{}")
    except Exception:
        finding["evidence"] = {}
    try:
        finding["risk_factors"] = json.loads(finding.get("risk_factors_json") or "{}")
    except Exception:
        finding["risk_factors"] = {}

    # Fetch affected transactions
    aff_txs = []
    if finding["affected_records"]:
        placeholders = ",".join("?" for _ in finding["affected_records"])
        try:
            tx_rows = conn.execute(f"SELECT * FROM transactions WHERE id IN ({placeholders})", tuple(finding["affected_records"])).fetchall()
            aff_txs = [dict(t) for t in tx_rows]
        except Exception:
            aff_txs = []
    finding["affected_transactions"] = aff_txs

    conn.close()
    return finding

@router.put("/detail/{finding_id}")
@router.put("/item/{finding_id}")
def update_finding(finding_id: int, update_data: FindingUpdate, current_user: dict = Depends(get_current_user)):
    """Updates status, auditor_comment, reviewed_at, and reviewed_by for a finding."""
    conn = get_db_connection()
    finding_row = conn.execute("SELECT * FROM audit_findings WHERE id = ?", (finding_id,)).fetchone()
    if not finding_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Finding not found")

    require_engagement_access(finding_row["engagement_id"], current_user)

    updates = []
    params = []
    now_str = datetime.now().isoformat()
    reviewer_name = update_data.reviewed_by or current_user.get("username", "admin")

    if update_data.status:
        updates.append("status = ?")
        params.append(update_data.status)
        updates.append("reviewed_at = ?")
        params.append(now_str)
        updates.append("reviewed_by = ?")
        params.append(reviewer_name)

    if update_data.auditor_comment is not None:
        updates.append("auditor_comment = ?")
        params.append(update_data.auditor_comment)
        if "reviewed_at = ?" not in updates:
            updates.append("reviewed_at = ?")
            params.append(now_str)
            updates.append("reviewed_by = ?")
            params.append(reviewer_name)

    if updates:
        params.append(finding_id)
        conn.execute(f"UPDATE audit_findings SET {', '.join(updates)} WHERE id = ?", tuple(params))
        
        from backend.app.utils.audit_logger import log_audit_event
        # If status changed
        if update_data.status and update_data.status != finding_row["status"]:
            log_audit_event(
                conn,
                action="FINDING_STATUS_CHANGE",
                module="FINDINGS",
                record_id=finding_id,
                engagement_id=finding_row["engagement_id"],
                old_value={"status": finding_row["status"]},
                new_value={"status": update_data.status},
                details=f"Changed finding {finding_row['finding_code']} status from '{finding_row['status']}' to '{update_data.status}'",
                user=current_user
            )

        # If auditor comment was provided/changed
        if update_data.auditor_comment is not None and update_data.auditor_comment != finding_row["auditor_comment"]:
            log_audit_event(
                conn,
                action="AUDITOR_COMMENT",
                module="FINDINGS",
                record_id=finding_id,
                engagement_id=finding_row["engagement_id"],
                old_value={"auditor_comment": finding_row["auditor_comment"]},
                new_value={"auditor_comment": update_data.auditor_comment},
                details=f"Added/updated auditor comment on finding {finding_row['finding_code']}",
                user=current_user
            )

        conn.commit()

    conn.close()
    return {"message": "Finding updated successfully", "finding_id": finding_id}

@router.post("/item/{finding_id}/ai-explain")
def get_finding_ai_explanation(finding_id: int, current_user: dict = Depends(get_current_user)):
    """
    Generates / refreshes an explainable deterministic AI audit observation and
    ICAI recommended substantive procedure based on the finding's facts and risk factors.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM audit_findings WHERE id = ?", (finding_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Finding not found")

    finding = dict(row)
    require_engagement_access(finding["engagement_id"], current_user)
    try:
        risk_factors = json.loads(finding.get("risk_factors_json") or "{}")
    except Exception:
        risk_factors = {}

    score = finding.get("risk_score") or 5.0
    sev = (finding.get("severity") or "MEDIUM").upper()
    title = finding.get("title") or "Audit Exception"
    module = finding.get("module") or "General"
    rule = finding.get("rule_used") or "Standard Audit Procedure"

    explanation_lines = [
        f"### Audit Risk Assessment & Explainability Analysis",
        f"**Finding ID**: `{finding.get('finding_code')}` | **Module**: {module} | **Severity**: {sev} | **Deterministic Risk Score**: {score}/10.0",
        "",
        f"#### Deterministic Factor Breakdown:",
        f"- **Base Severity Weight**: {risk_factors.get('base_weight', 3.0)} ({sev})",
        f"- **Financial Exposure**: ₹{risk_factors.get('amount', 0):,.2f} vs Materiality Benchmark of ₹{risk_factors.get('materiality_threshold', 50000):,.2f} (+{risk_factors.get('amount_impact', 0.0)} impact)",
        f"- **Affected Records / Frequency**: {risk_factors.get('affected_records_count', 1)} record(s), frequency multiplier: {risk_factors.get('frequency', 1)} (+{risk_factors.get('records_impact', 0.0)} / +{risk_factors.get('repetition_impact', 0.0)})",
        f"- **Variance / Discrepancy %**: {risk_factors.get('difference_pct', 0.0):.1f}% (+{risk_factors.get('difference_impact', 0.0)})",
        f"- **Data Quality & Historical Flag**: Quality Penalty: +{risk_factors.get('data_quality_impact', 0.0)}, Historical Pattern: +{risk_factors.get('historical_impact', 0.0)}",
        f"- **Formula Calculation**: `{risk_factors.get('equation', f'Calculated Score: {score}/10.0')}`",
        "",
        f"#### Statutory & Auditing Standard Reference:",
        f"This finding operates under **{rule}**. Under Indian Auditing Standards (SA 240 / SA 315 / SA 500 / SA 520), this risk score of {score}/10.0 mandates the auditor to evaluate whether this exception constitutes an isolated posting error or a systemic internal control deficiency.",
        "",
        f"#### Recommended Substantive Audit Procedures:",
        f"1. **Document Inspection**: Inspect primary source documentation, signed invoices, payment vouchers, and vendor bank confirmations.",
        f"2. **Management Inquiry**: Issue written management inquiry regarding rationale for `{title}`.",
        f"3. **Financial Statement Impact**: Quantify total potential misstatement and assess if adjustment journal entry is required."
    ]

    full_ai_explanation = "\n".join(explanation_lines)

    # Update in DB
    conn.execute("UPDATE audit_findings SET ai_explanation = ? WHERE id = ?", (full_ai_explanation, finding_id))
    conn.commit()
    conn.close()

    return {
        "finding_id": finding_id,
        "finding_code": finding.get("finding_code"),
        "risk_score": score,
        "severity": sev,
        "ai_explanation": full_ai_explanation,
        "risk_factors": risk_factors
    }

@router.post("/custom")
def create_custom_finding(finding_in: FindingCreateCustom, current_user: dict = Depends(get_current_user)):
    """Allows an auditor to record a manual audit observation with deterministic risk calculation."""
    require_engagement_access(finding_in.engagement_id, current_user)
    conn = get_db_connection()
    eng_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (finding_in.engagement_id,)).fetchone()
    if not eng_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Engagement not found")

    # Validate that affected records belong to this engagement
    if finding_in.affected_records:
        t_ids = [int(x) for x in finding_in.affected_records if str(x).isdigit()]
        if t_ids:
            cnt = conn.execute(f"SELECT COUNT(*) as c FROM transactions WHERE engagement_id = ? AND id IN ({','.join('?' for _ in t_ids)})", (finding_in.engagement_id, *t_ids)).fetchone()["c"]
            if cnt != len(t_ids):
                conn.close()
                raise HTTPException(status_code=400, detail="One or more affected records do not belong to this engagement.")

    eng_dict = dict(eng_row)
    materiality_thresh = float(eng_dict.get("materiality_threshold") or 50000.0)
    code = finding_in.finding_code or f"FIND-MANUAL-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Calculate deterministic risk score
    aff_count = len(finding_in.affected_records or [])
    score, factors, explanation = CentralizedFindingsEngine.calculate_deterministic_risk_score(
        severity=finding_in.severity,
        amount=0.0,
        materiality_threshold=materiality_thresh,
        frequency=1,
        repetition_count=1,
        data_quality_issue=False,
        difference_pct=0.0,
        historical_repeat=False,
        affected_records_count=aff_count
    )

    now_str = datetime.now().isoformat()
    reviewer_name = current_user.get("username", "admin")

    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO audit_findings (
        engagement_id, finding_code, module, category, severity, risk_score,
        title, description, affected_records_json, expected_value, actual_value,
        difference, reason, evidence_json, rule_used, engine_type, risk_factors_json,
        ai_explanation, recommended_action, status, auditor_comment, reviewed_at,
        reviewed_by, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'LOCAL_AI', ?, ?, ?, 'Open', ?, ?, ?, ?)
    """, (
        finding_in.engagement_id,
        code,
        finding_in.module or "Manual Audit",
        finding_in.category,
        finding_in.severity.upper(),
        score,
        finding_in.title,
        finding_in.description,
        json.dumps(finding_in.affected_records or []),
        str(finding_in.expected_value or ""),
        str(finding_in.actual_value or ""),
        str(finding_in.difference or ""),
        "Manual auditor observation",
        json.dumps({}),
        finding_in.rule_used or "Manual Review",
        json.dumps(factors),
        explanation,
        finding_in.recommended_action or "Review documentation and verify ledger postings.",
        finding_in.auditor_comment,
        now_str if finding_in.auditor_comment else None,
        reviewer_name if finding_in.auditor_comment else None,
        now_str
    ))

    new_id = cursor.lastrowid

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="CREATE_FINDING",
        module="FINDINGS",
        record_id=new_id,
        engagement_id=finding_in.engagement_id,
        new_value={
            "finding_code": code,
            "title": finding_in.title,
            "module": finding_in.module or "Manual Audit",
            "severity": finding_in.severity.upper(),
            "risk_score": score,
            "rule_used": finding_in.rule_used or "Manual Review"
        },
        details=f"Created manual finding '{finding_in.title}' ({code})",
        user=current_user
    )

    conn.commit()
    conn.close()

    return {"message": "Manual finding created successfully", "finding_id": new_id, "finding_code": code, "risk_score": score}

@router.get("/{engagement_id}/export/csv")
def export_findings_csv(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """Exports complete audit findings register to CSV."""
    require_engagement_access(engagement_id, current_user)
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT finding_code, module, category, severity, risk_score, title, description,
               expected_value, actual_value, difference, rule_used, engine_type,
               recommended_action, auditor_comment, status, reviewed_by, reviewed_at, created_at
        FROM audit_findings
        WHERE engagement_id = ?
        ORDER BY risk_score DESC, id ASC
    """, (engagement_id,)).fetchall()

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="REPORT_EXPORT",
        module="FINDINGS",
        record_id=engagement_id,
        engagement_id=engagement_id,
        details=f"Exported {len(rows)} audit findings to CSV",
        user=current_user
    )
    conn.commit()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Finding ID", "Module", "Category", "Severity", "Risk Score (1-10)", "Title",
        "Description", "Expected Value", "Actual Value", "Difference", "Rule Used",
        "Engine Type", "Recommended Action", "Auditor Comment", "Status",
        "Reviewer", "Reviewed Date", "Created Date"
    ])

    for r in rows:
        writer.writerow([
            r["finding_code"],
            r["module"],
            r["category"],
            r["severity"],
            r["risk_score"],
            r["title"],
            r["description"],
            r["expected_value"],
            r["actual_value"],
            r["difference"],
            r["rule_used"],
            r["engine_type"],
            r["recommended_action"],
            r["auditor_comment"] or "",
            r["status"],
            r["reviewed_by"] or "",
            r["reviewed_at"] or "",
            r["created_at"]
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=audit_findings_engagement_{engagement_id}.csv"}
    )
