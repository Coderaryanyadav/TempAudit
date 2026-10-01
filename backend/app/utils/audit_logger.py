import json
import hashlib
import threading
from datetime import datetime
from typing import Any, Dict, Optional, Union
from backend.app.database import get_db_connection

_AUDIT_LOG_MUTEX = threading.Lock()

def serialize_value(val: Any) -> Optional[str]:
    """Serialize an audit value (dict, list, primitive) to clean JSON string."""
    if val is None:
        return None
    if isinstance(val, str):
        return val
    try:
        return json.dumps(val, default=str, ensure_ascii=False)
    except Exception:
        return str(val)

def log_audit_event(
    conn,
    action: str,
    module: str,
    record_id: Optional[Union[str, int]] = None,
    old_value: Optional[Any] = None,
    new_value: Optional[Any] = None,
    details: Optional[str] = None,
    user: Optional[Union[Dict[str, Any], str]] = None,
    engagement_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    timestamp: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None
) -> int:
    """
    Append an immutable event to the local audit trail with SHA-256 cryptographic hash chaining.
    Serialized via a mutex lock to ensure continuous integrity under high concurrency.
    """
    now_str = timestamp or datetime.now().isoformat()
    
    user_id = None
    username = "system"
    
    if isinstance(user, dict):
        user_id = user.get("id") or user.get("uid") or user.get("user_id")
        username = user.get("username") or user.get("sub") or "user"
    elif isinstance(user, str) and user.strip():
        username = user.strip()

    action_str = str(action).strip()
    module_str = str(module).upper().strip()
    record_id_str = str(record_id) if record_id is not None else None
    
    entity_id_int = entity_id
    if entity_id_int is None and record_id is not None:
        try:
            entity_id_int = int(record_id)
        except (ValueError, TypeError):
            entity_id_int = None

    resolved_entity_type = entity_type or (module_str.lower().rstrip('s') if module_str.lower().endswith("papers") or module_str.lower().endswith("users") else module_str.lower())

    old_val_str = serialize_value(old_value)
    new_val_str = serialize_value(new_value)
    details_str = details or f"{action_str} in {module_str}"
    client_ip = ip_address if ip_address else None

    with _AUDIT_LOG_MUTEX:
        # Get previous entry's hash for cryptographic chaining
        try:
            last_log = conn.execute("SELECT entry_hash FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()
            prev_hash = last_log["entry_hash"] if last_log and last_log["entry_hash"] else "GENESIS_HASH_00000000000000000000000000000000"
        except Exception:
            prev_hash = "GENESIS_HASH_00000000000000000000000000000000"

        hash_payload = f"{prev_hash}|{now_str}|{user_id}|{username}|{action_str}|{module_str}|{record_id_str}|{old_val_str}|{new_val_str}|{details_str}|{engagement_id}"
        entry_hash = hashlib.sha256(hash_payload.encode('utf-8')).hexdigest()

        cursor = conn.execute("""
            INSERT INTO audit_logs (
                timestamp, user_id, username, action, module, record_id,
                old_value, new_value, details, engagement_id, ip_address,
                entity_type, entity_id, previous_hash, entry_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_str,
            user_id,
            username,
            action_str,
            module_str,
            record_id_str,
            old_val_str,
            new_val_str,
            details_str,
            engagement_id,
            client_ip,
            resolved_entity_type,
            entity_id_int,
            prev_hash,
            entry_hash
        ))
        row_id = cursor.lastrowid

    return row_id

def verify_audit_trail_integrity(conn=None) -> Dict[str, Any]:
    """
    Verifies the cryptographic SHA-256 hash chain of the entire audit trail from genesis to latest event.
    Returns proof of validity and details of any tampering or chain breaks.
    """
    close_at_end = False
    if conn is None:
        conn = get_db_connection()
        close_at_end = True

    try:
        rows = conn.execute("SELECT * FROM audit_logs ORDER BY id ASC").fetchall()
        expected_prev_hash = "GENESIS_HASH_00000000000000000000000000000000"
        entries_checked = 0

        for r in rows:
            entries_checked += 1
            actual_prev = r["previous_hash"] or "GENESIS_HASH_00000000000000000000000000000000"

            if actual_prev != expected_prev_hash:
                return {
                    "valid": False,
                    "entries_checked": entries_checked,
                    "total_entries": len(rows),
                    "first_invalid_entry": {
                        "id": r["id"],
                        "action": r["action"],
                        "timestamp": r["timestamp"],
                        "expected_previous_hash": expected_prev_hash,
                        "actual_previous_hash": actual_prev,
                        "reason": "PREVIOUS_HASH_MISMATCH"
                    }
                }

            # Recompute entry hash
            user_id = r["user_id"]
            username = r["username"]
            action_str = r["action"]
            module_str = r["module"]
            record_id_str = r["record_id"]
            old_val_str = r["old_value"]
            new_val_str = r["new_value"]
            details_str = r["details"]
            engagement_id = r["engagement_id"]
            now_str = r["timestamp"]

            hash_payload = f"{actual_prev}|{now_str}|{user_id}|{username}|{action_str}|{module_str}|{record_id_str}|{old_val_str}|{new_val_str}|{details_str}|{engagement_id}"
            recomputed = hashlib.sha256(hash_payload.encode('utf-8')).hexdigest()

            if r["entry_hash"] != recomputed:
                return {
                    "valid": False,
                    "entries_checked": entries_checked,
                    "total_entries": len(rows),
                    "first_invalid_entry": {
                        "id": r["id"],
                        "action": r["action"],
                        "timestamp": r["timestamp"],
                        "expected_entry_hash": recomputed,
                        "actual_entry_hash": r["entry_hash"],
                        "reason": "ENTRY_HASH_TAMPERED_OR_CORRUPTED"
                    }
                }

            expected_prev_hash = r["entry_hash"]

        return {
            "valid": True,
            "entries_checked": entries_checked,
            "total_entries": len(rows),
            "first_invalid_entry": None,
            "status": "CHAIN_INTEGRITY_VERIFIED"
        }
    finally:
        if close_at_end:
            conn.close()
