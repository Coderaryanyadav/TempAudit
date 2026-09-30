import json
from datetime import datetime
from typing import Any, Dict, Optional, Union


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
    timestamp: Optional[str] = None
) -> int:
    """
    Append an immutable event to the local audit trail.

    Required fields:
    - Timestamp
    - User (username/user_id)
    - Action (LOGIN, LOGOUT, CREATE_CLIENT, DATA_MODIFICATION, etc.)
    - Module (AUTH, CLIENTS, ENGAGEMENTS, IMPORT, FINDINGS, etc.)
    - Record ID
    - Old Value (where applicable)
    - New Value (where applicable)
    """
    now_str = timestamp or datetime.now().isoformat()
    
    user_id = None
    username = "system"
    
    if isinstance(user, dict):
        user_id = user.get("id") or user.get("uid") or user.get("user_id")
        username = user.get("username") or user.get("sub") or "user"
    elif isinstance(user, str) and user.strip():
        username = user.strip()

    action_str = str(action).upper().strip()
    module_str = str(module).upper().strip()
    record_id_str = str(record_id) if record_id is not None else None
    
    # Try to convert record_id to int for entity_id if possible
    entity_id_int = None
    if record_id is not None:
        try:
            entity_id_int = int(record_id)
        except (ValueError, TypeError):
            entity_id_int = None

    old_val_str = serialize_value(old_value)
    new_val_str = serialize_value(new_value)

    cursor = conn.execute("""
        INSERT INTO audit_logs (
            timestamp, user_id, username, action, module, record_id,
            old_value, new_value, details, engagement_id, ip_address,
            entity_type, entity_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        now_str,
        user_id,
        username,
        action_str,
        module_str,
        record_id_str,
        old_val_str,
        new_val_str,
        details or f"{action_str} in {module_str}",
        engagement_id,
        ip_address or "127.0.0.1",
        module_str.lower(),
        entity_id_int
    ))
    return cursor.lastrowid
