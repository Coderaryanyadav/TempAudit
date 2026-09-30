import io
import csv
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Response

from backend.app.schemas import ChecklistItemUpdate, ChecklistItemCreate, ChecklistGenerateRequest
from backend.app.auth import get_current_user
from backend.app.database import get_db_connection
from backend.app.services.checklist_generator import (
    ChecklistGenerator,
    CHECKLIST_CATEGORIES,
    CHECKLIST_STATUSES
)

router = APIRouter(prefix="/api/checklist", tags=["Audit Checklist"])

@router.get("/{engagement_id}")
def get_checklist(
    engagement_id: int,
    category: Optional[str] = None,
    status: Optional[str] = None,
    assigned_staff: Optional[str] = None,
    search: Optional[str] = None
):
    """
    Retrieves the audit checklist items for an engagement with optional category,
    status, assigned staff, and search query filters.
    """
    conn = get_db_connection()
    query = "SELECT * FROM audit_checklists WHERE engagement_id = ?"
    params = [engagement_id]

    if category:
        query += " AND category = ?"
        params.append(category)

    if status:
        query += " AND status = ?"
        params.append(status)

    if assigned_staff:
        query += " AND assigned_staff LIKE ?"
        params.append(f"%{assigned_staff}%")

    if search:
        search_pat = f"%{search.strip()}%"
        query += " AND (item_code LIKE ? OR question LIKE ? OR guidance LIKE ? OR comment LIKE ? OR evidence LIKE ?)"
        params.extend([search_pat, search_pat, search_pat, search_pat, search_pat])

    query += " ORDER BY category ASC, id ASC"
    rows = conn.execute(query, tuple(params)).fetchall()

    items = []
    for r in rows:
        item = dict(r)
        # Normalize legacy status labels if any exist
        if item.get("status") == "Pending":
            item["status"] = "Not Started"
        elif item.get("status") == "Complied":
            item["status"] = "Completed"
        elif item.get("status") == "Exception":
            item["status"] = "Requires Review"
        items.append(item)

    conn.close()
    return items

@router.get("/{engagement_id}/summary")
def get_checklist_summary(engagement_id: int):
    """
    Returns executive metrics for the audit checklist:
    Total items, counts by category (all 15 categories), counts by status, and completion %.
    """
    try:
        summary = ChecklistGenerator.get_checklist_summary(engagement_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate checklist summary: {str(e)}")

@router.post("/{engagement_id}/generate")
def generate_checklist(
    engagement_id: int,
    gen_req: Optional[ChecklistGenerateRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Generates or refreshes the audit checklist according to:
    - Client type
    - Audit type
    - Financial year
    - Selected modules
    - Detected Risk findings (automatically flags relevant substantive procedures as 'Requires Review')
    """
    req_dict = gen_req.model_dump() if gen_req else {}
    try:
        result = ChecklistGenerator.generate_checklist(
            engagement_id=engagement_id,
            client_type=req_dict.get("client_type"),
            audit_type=req_dict.get("audit_type"),
            financial_year=req_dict.get("financial_year"),
            selected_modules=req_dict.get("selected_modules"),
            regenerate=req_dict.get("regenerate", False)
        )

        now_str = datetime.now().isoformat()
        conn = get_db_connection()
        conn.execute("""
        INSERT INTO audit_logs (username, action, entity_type, entity_id, details, timestamp)
        VALUES (?, 'GENERATE_CHECKLIST', 'engagement', ?, ?, ?)
        """, (
            current_user.get("username", "admin"),
            engagement_id,
            f"Generated audit checklist ({result['total_items']} items, {result['risk_finding_procedures_count']} risk-linked)",
            now_str
        ))
        conn.commit()
        conn.close()

        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate checklist: {str(e)}")

@router.post("/{engagement_id}/custom")
def create_custom_checklist_item(
    engagement_id: int,
    item_in: ChecklistItemCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Allows the auditor to create custom checklist procedures under any of the 15 categories.
    """
    conn = get_db_connection()
    eng_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    if not eng_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Engagement not found")

    # Generate custom item code if not provided
    now_str = datetime.now().isoformat()
    if not item_in.item_code:
        count_custom = conn.execute(
            "SELECT COUNT(*) as c FROM audit_checklists WHERE engagement_id = ? AND is_custom = 1",
            (engagement_id,)
        ).fetchone()["c"]
        item_code = f"CHK-CUST-{count_custom + 1:03d}"
    else:
        item_code = item_in.item_code

    # Validate status
    status = item_in.status if item_in.status in CHECKLIST_STATUSES else "Not Started"

    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO audit_checklists (
        engagement_id, category, item_code, question, guidance, status,
        assigned_staff, evidence, comment, due_date, completed_date,
        is_custom, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        engagement_id,
        item_in.category,
        item_code,
        item_in.question,
        item_in.guidance or "Custom auditor procedure",
        status,
        item_in.assigned_staff or current_user.get("full_name") or "Auditor",
        item_in.evidence or "",
        item_in.comment or "",
        item_in.due_date,
        None,
        now_str
    ))
    new_id = cursor.lastrowid

    conn.execute("""
    INSERT INTO audit_logs (username, action, entity_type, entity_id, details, timestamp)
    VALUES (?, 'CREATE_CUSTOM_CHECKLIST', 'checklist_item', ?, ?, ?)
    """, (
        current_user.get("username", "admin"),
        new_id,
        f"Created custom checklist item {item_code} in category '{item_in.category}'",
        now_str
    ))

    conn.commit()
    conn.close()

    return {
        "message": "Custom checklist item created successfully",
        "id": new_id,
        "item_code": item_code
    }

@router.put("/item/{item_id}")
def update_checklist_item(
    item_id: int,
    update_data: ChecklistItemUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Updates status, assigned staff, evidence, comment, due date, or completed date.
    Enforces that auditor must sign off; AI never marks completed.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM audit_checklists WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Checklist item not found")

    updates = []
    params = []
    now_str = datetime.now().isoformat()
    reviewer_name = current_user.get("full_name") or current_user.get("username", "Auditor")

    if update_data.status is not None:
        status_clean = update_data.status.strip()
        if status_clean not in CHECKLIST_STATUSES:
            # Map legacy if needed
            if status_clean == "Pending":
                status_clean = "Not Started"
            elif status_clean == "Complied":
                status_clean = "Completed"
            elif status_clean == "Exception":
                status_clean = "Requires Review"
            else:
                status_clean = "In Progress"

        updates.append("status = ?")
        params.append(status_clean)

        # If marking Completed and no completed_date passed, record current date
        if status_clean == "Completed" and not update_data.completed_date:
            updates.append("completed_date = ?")
            params.append(datetime.now().strftime("%Y-%m-%d"))
        elif status_clean != "Completed" and update_data.completed_date is None:
            # If changing from completed to not started / in progress, clear completed_date
            updates.append("completed_date = NULL")

    if update_data.assigned_staff is not None:
        updates.append("assigned_staff = ?")
        params.append(update_data.assigned_staff)

    if update_data.evidence is not None:
        updates.append("evidence = ?")
        params.append(update_data.evidence)

    if update_data.comment is not None:
        updates.append("comment = ?")
        params.append(update_data.comment)

    if update_data.auditor_remarks is not None:
        updates.append("auditor_remarks = ?")
        params.append(update_data.auditor_remarks)

    if update_data.reference_wp is not None:
        updates.append("reference_wp = ?")
        params.append(update_data.reference_wp)

    if update_data.due_date is not None:
        updates.append("due_date = ?")
        params.append(update_data.due_date)

    if update_data.completed_date is not None:
        updates.append("completed_date = ?")
        params.append(update_data.completed_date)

    # Record checked by & checked at
    updates.append("checked_by = ?")
    params.append(reviewer_name)
    updates.append("checked_at = ?")
    params.append(now_str)

    if updates:
        params.append(item_id)
        conn.execute(f"UPDATE audit_checklists SET {', '.join(updates)} WHERE id = ?", tuple(params))

        from backend.app.utils.audit_logger import log_audit_event
        # If status changed
        if update_data.status is not None and update_data.status != row["status"]:
            log_audit_event(
                conn,
                action="CHECKLIST_CHANGE",
                module="CHECKLISTS",
                record_id=item_id,
                engagement_id=row["engagement_id"],
                old_value={"status": row["status"]},
                new_value={"status": update_data.status},
                details=f"Changed checklist item {row['item_code']} status from '{row['status']}' to '{update_data.status}'",
                user=current_user
            )

        row_dict = dict(row)
        # If comment or remarks changed
        if (update_data.comment is not None and update_data.comment != row_dict.get("comment")) or \
           (update_data.auditor_remarks is not None and update_data.auditor_remarks != row_dict.get("auditor_remarks")):
            log_audit_event(
                conn,
                action="AUDITOR_COMMENT",
                module="CHECKLISTS",
                record_id=item_id,
                engagement_id=row["engagement_id"],
                old_value={"comment": row_dict.get("comment"), "remarks": row_dict.get("auditor_remarks")},
                new_value={"comment": update_data.comment, "remarks": update_data.auditor_remarks},
                details=f"Auditor comment/remarks added on checklist item {row['item_code']}",
                user=current_user
            )

        conn.commit()

    conn.close()
    return {"message": "Checklist item updated successfully", "id": item_id}

@router.delete("/item/{item_id}")
def delete_checklist_item(item_id: int, current_user: dict = Depends(get_current_user)):
    """Deletes a checklist procedure."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM audit_checklists WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Checklist item not found")

    conn.execute("DELETE FROM audit_checklists WHERE id = ?", (item_id,))
    
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="CHECKLIST_CHANGE",
        module="CHECKLISTS",
        record_id=item_id,
        engagement_id=row["engagement_id"],
        old_value=dict(row),
        details=f"Deleted checklist item {row['item_code']} ({row['category']})",
        user=current_user
    )

    conn.commit()
    conn.close()
    return {"message": "Checklist item deleted successfully"}

@router.get("/{engagement_id}/export/csv")
def export_checklist_csv(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """Exports full audit checklist register to CSV."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT item_code, category, question, guidance, status, assigned_staff,
               evidence, comment, due_date, completed_date, checked_by, checked_at
        FROM audit_checklists
        WHERE engagement_id = ?
        ORDER BY category ASC, id ASC
    """, (engagement_id,)).fetchall()

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="REPORT_EXPORT",
        module="CHECKLISTS",
        record_id=engagement_id,
        engagement_id=engagement_id,
        details=f"Exported {len(rows)} checklist items to CSV",
        user=current_user
    )
    conn.commit()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Checklist ID", "Category", "Question/Procedure", "Guidance", "Status",
        "Assigned Staff", "Evidence", "Comment", "Due Date", "Completed Date",
        "Auditor Sign-Off", "Sign-Off Timestamp"
    ])

    for r in rows:
        st = r["status"]
        if st == "Pending":
            st = "Not Started"
        writer.writerow([
            r["item_code"],
            r["category"],
            r["question"],
            r["guidance"] or "",
            st,
            r["assigned_staff"] or "",
            r["evidence"] or "",
            r["comment"] or "",
            r["due_date"] or "",
            r["completed_date"] or "",
            r["checked_by"] or "",
            r["checked_at"] or ""
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=audit_checklist_engagement_{engagement_id}.csv"}
    )
