import sqlite3
from typing import List, Dict, Any, Optional
from backend.app.utils.audit_logger import log_audit_event, verify_audit_trail_integrity

class AuditRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def append_event(
        self,
        action: str,
        module: str,
        record_id: Optional[Any] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        details: Optional[str] = None,
        user: Optional[Any] = None,
        engagement_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        timestamp: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None
    ) -> int:
        return log_audit_event(
            conn=self.conn,
            action=action,
            module=module,
            record_id=record_id,
            old_value=old_value,
            new_value=new_value,
            details=details,
            user=user,
            engagement_id=engagement_id,
            ip_address=ip_address,
            timestamp=timestamp,
            entity_type=entity_type,
            entity_id=entity_id
        )

    def verify_integrity(self) -> Dict[str, Any]:
        return verify_audit_trail_integrity(self.conn)

    def list_events(
        self,
        engagement_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
        action: Optional[str] = None,
        module: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params: List[Any] = []
        if engagement_id is not None:
            query += " AND engagement_id = ?"
            params.append(engagement_id)
        if action:
            query += " AND action = ?"
            params.append(action)
        if module:
            query += " AND module = ?"
            params.append(module)
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]
