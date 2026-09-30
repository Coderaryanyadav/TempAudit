import re
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from typing import List, Optional
from backend.app.schemas import ClientCreate, ClientUpdate
from backend.app.auth import get_current_user, require_role
from backend.app.database import get_db_connection

router = APIRouter(prefix="/api/clients", tags=["Client Master Management"])

PAN_REGEX = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
GSTIN_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"

VALID_ENTITY_TYPES = [
    "Proprietorship",
    "Partnership",
    "LLP",
    "Private Limited Company",
    "Public Limited Company",
    "Trust",
    "Society",
    "NGO",
    "Other"
]

@router.get("")
def list_clients(
    search: Optional[str] = None,
    entity_type: Optional[str] = None,
    industry: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List all client profiles with search across name, PAN, GSTIN, entity type, and industry."""
    conn = get_db_connection()
    try:
        query = """
            SELECT c.*,
                   COUNT(e.id) as engagements_count,
                   SUM(CASE WHEN e.status NOT IN ('Completed', 'Archived') AND e.id IS NOT NULL THEN 1 ELSE 0 END) as active_engagements,
                   GROUP_CONCAT(DISTINCT e.financial_year) as fy_concat
            FROM clients c
            LEFT JOIN engagements e ON c.id = e.client_id
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND (c.name LIKE ? OR c.pan LIKE ? OR c.gstin LIKE ? OR c.contact_person LIKE ? OR c.industry LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term, term, term])

        if entity_type and entity_type != "All":
            query += " AND c.entity_type = ?"
            params.append(entity_type)

        if industry and industry != "All":
            query += " AND c.industry = ?"
            params.append(industry)

        query += " GROUP BY c.id ORDER BY c.id DESC"
        rows = conn.execute(query, tuple(params)).fetchall()

        clients = []
        for r in rows:
            c = dict(r)
            c["engagements_count"] = c.get("engagements_count") or 0
            c["active_engagements"] = c.get("active_engagements") or 0
            fy_str = c.pop("fy_concat", "") or ""
            c["financial_years"] = [fy.strip() for fy in fy_str.split(",") if fy.strip()] if fy_str else []
            clients.append(c)

        return clients
    finally:
        conn.close()

@router.get("/{client_id}")
def get_client(
    client_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Retrieve full client profile with associated engagement history and previous years using single aggregated query."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Client not found")

        client = dict(row)
        eng_rows = conn.execute("""
            SELECT e.*, 
                   u.full_name as lead_auditor_name, 
                   s.full_name as assigned_staff_name,
                   COALESCE((SELECT COUNT(*) FROM transactions t WHERE t.engagement_id = e.id), 0) as transactions_count,
                   COALESCE((SELECT COUNT(*) FROM audit_findings f WHERE f.engagement_id = e.id), 0) as findings_count,
                   COALESCE((SELECT COUNT(*) FROM audit_findings f WHERE f.engagement_id = e.id AND f.severity = 'CRITICAL'), 0) as critical_findings_count
            FROM engagements e
            LEFT JOIN users u ON e.lead_auditor_id = u.id
            LEFT JOIN users s ON e.assigned_staff_id = s.id
            WHERE e.client_id = ?
            ORDER BY e.financial_year DESC, e.id DESC
        """, (client_id,)).fetchall()

        client["engagements"] = [dict(e) for e in eng_rows]
        return client
    finally:
        conn.close()

@router.post("")
def create_client(client_data: ClientCreate, current_user: dict = Depends(require_role(["Admin", "Auditor"]))):
    """Create a new client master record with PAN & GSTIN validation."""
    pan = (client_data.pan or "").strip().upper()
    gstin = (client_data.gstin or "").strip().upper()

    if pan and not re.match(PAN_REGEX, pan):
        raise HTTPException(status_code=400, detail="Invalid PAN format. Standard format: 5 letters + 4 numbers + 1 letter (e.g., AABCA1234D).")

    if gstin and not re.match(GSTIN_REGEX, gstin):
        raise HTTPException(status_code=400, detail="Invalid GSTIN format. Standard format: 15 alphanumeric characters (e.g., 27AABCA1234D1ZP).")

    conn = get_db_connection()
    now_str = datetime.now().isoformat()

    # Check PAN uniqueness if entered
    if pan:
        existing = conn.execute("SELECT id, name FROM clients WHERE pan = ?", (pan,)).fetchone()
        if existing:
            conn.close()
            raise HTTPException(status_code=400, detail=f"A client with PAN '{pan}' already exists: {existing['name']}.")

    cursor = conn.execute("""
    INSERT INTO clients (
        name, entity_type, pan, gstin, address, contact_person,
        email, phone, industry, financial_year, notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_data.name.strip(),
        client_data.entity_type or "Private Limited Company",
        pan or None,
        gstin or None,
        client_data.address or "",
        client_data.contact_person or "",
        client_data.email or "",
        client_data.phone or "",
        client_data.industry or "Manufacturing",
        client_data.financial_year or "2024-25",
        client_data.notes or "",
        now_str,
        now_str
    ))
    new_id = cursor.lastrowid

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="CREATE_CLIENT",
        module="CLIENTS",
        record_id=new_id,
        new_value={
            "name": client_data.name.strip(),
            "entity_type": client_data.entity_type,
            "pan": pan,
            "gstin": gstin,
            "industry": client_data.industry
        },
        details=f"Created client master '{client_data.name}' (PAN: {pan or 'N/A'})",
        user=current_user
    )

    conn.commit()
    conn.close()
    return {"id": new_id, "name": client_data.name, "status": "created"}

@router.put("/{client_id}")
def update_client(client_id: int, update_data: ClientUpdate, current_user: dict = Depends(require_role(["Admin", "Auditor"]))):
    """Update client master record."""
    conn = get_db_connection()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")

    old_client_data = dict(client)
    updates = []
    params = []
    new_changes = {}

    if update_data.name is not None:
        updates.append("name = ?")
        params.append(update_data.name.strip())
        new_changes["name"] = update_data.name.strip()

    if update_data.entity_type is not None:
        updates.append("entity_type = ?")
        params.append(update_data.entity_type)
        new_changes["entity_type"] = update_data.entity_type

    if update_data.pan is not None:
        pan = update_data.pan.strip().upper()
        if pan and not re.match(PAN_REGEX, pan):
            conn.close()
            raise HTTPException(status_code=400, detail="Invalid PAN format (e.g. AABCA1234D)")
        updates.append("pan = ?")
        params.append(pan or None)
        new_changes["pan"] = pan or None

    if update_data.gstin is not None:
        gstin = update_data.gstin.strip().upper()
        if gstin and not re.match(GSTIN_REGEX, gstin):
            conn.close()
            raise HTTPException(status_code=400, detail="Invalid GSTIN format (15 characters)")
        updates.append("gstin = ?")
        params.append(gstin or None)
        new_changes["gstin"] = gstin or None

    if update_data.address is not None:
        updates.append("address = ?")
        params.append(update_data.address.strip())
        new_changes["address"] = update_data.address.strip()

    if update_data.contact_person is not None:
        updates.append("contact_person = ?")
        params.append(update_data.contact_person.strip())
        new_changes["contact_person"] = update_data.contact_person.strip()

    if update_data.email is not None:
        updates.append("email = ?")
        params.append(update_data.email.strip())
        new_changes["email"] = update_data.email.strip()

    if update_data.phone is not None:
        updates.append("phone = ?")
        params.append(update_data.phone.strip())
        new_changes["phone"] = update_data.phone.strip()

    if update_data.industry is not None:
        updates.append("industry = ?")
        params.append(update_data.industry)
        new_changes["industry"] = update_data.industry

    if update_data.financial_year is not None:
        updates.append("financial_year = ?")
        params.append(update_data.financial_year)
        new_changes["financial_year"] = update_data.financial_year

    if update_data.notes is not None:
        updates.append("notes = ?")
        params.append(update_data.notes.strip())
        new_changes["notes"] = update_data.notes.strip()

    now_str = datetime.now().isoformat()
    updates.append("updated_at = ?")
    params.append(now_str)

    params.append(client_id)
    conn.execute(f"UPDATE clients SET {', '.join(updates)} WHERE id = ?", tuple(params))

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn,
        action="DATA_MODIFICATION",
        module="CLIENTS",
        record_id=client_id,
        old_value=old_client_data,
        new_value=new_changes,
        details=f"Modified client master '{client['name']}' details",
        user=current_user
    )

    conn.commit()
    conn.close()
    return {"message": "Client updated successfully", "client_id": client_id}

@router.get("/{client_id}/history")
def get_client_history(
    client_id: int,
    current_user: dict = Depends(get_current_user)
):
    """View previous years' audit engagements for a specific client using single aggregated query."""
    conn = get_db_connection()
    try:
        client_row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not client_row:
            raise HTTPException(status_code=404, detail="Client not found")

        eng_rows = conn.execute("""
            SELECT e.*, 
                   u.full_name as lead_auditor_name,
                   COALESCE((SELECT SUM(debit) FROM transactions t WHERE t.engagement_id = e.id), 0.0) as turnover,
                   COALESCE((SELECT COUNT(*) FROM audit_findings f WHERE f.engagement_id = e.id), 0) as total_findings,
                   COALESCE((SELECT COUNT(*) FROM audit_findings f WHERE f.engagement_id = e.id AND f.severity = 'CRITICAL'), 0) as critical_findings
            FROM engagements e
            LEFT JOIN users u ON e.lead_auditor_id = u.id
            WHERE e.client_id = ?
            ORDER BY e.financial_year DESC, e.id DESC
        """, (client_id,)).fetchall()

        timeline = []
        for r in eng_rows:
            e = dict(r)
            e["turnover"] = round(float(e.get("turnover") or 0.0), 2)
            timeline.append(e)

        return {
            "client": dict(client_row),
            "history": timeline,
            "timeline": timeline,
            "total_engagements": len(timeline)
        }
    finally:
        conn.close()
