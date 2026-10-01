import sqlite3
from typing import List, Dict, Any, Optional

class EngagementRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_by_id(self, engagement_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
        return dict(row) if row else None

    def list_all(self, client_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if client_id:
            rows = self.conn.execute("SELECT * FROM engagements WHERE client_id = ? ORDER BY id DESC", (client_id,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM engagements ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    def create(self, data: Dict[str, Any]) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO engagements (
            client_id, title, audit_type, financial_year, period_start, period_end,
            status, lead_auditor_id, assigned_staff_id, materiality_threshold, notes,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("client_id"),
            data.get("title"),
            data.get("audit_type", "Statutory Audit"),
            data.get("financial_year"),
            data.get("period_start"),
            data.get("period_end"),
            data.get("status", "In Progress"),
            data.get("lead_auditor_id"),
            data.get("assigned_staff_id"),
            data.get("materiality_threshold", 50000.0),
            data.get("notes"),
            data.get("created_at"),
            data.get("updated_at")
        ))
        return cursor.lastrowid
