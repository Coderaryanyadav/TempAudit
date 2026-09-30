import json
from datetime import datetime
from typing import Any, Dict, Optional, Union


import hashlib

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
    Append an immutable event to the local audit trail with SHA-256 cryptographic hash chaining.
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
    
    entity_id_int = None
    if record_id is not None:
        try:
            entity_id_int = int(record_id)
        except (ValueError, TypeError):
            entity_id_int = None

    old_val_str = serialize_value(old_value)
    new_val_str = serialize_value(new_value)
    details_str = details or f"{action_str} in {module_str}"

    # Get previous entry's hash for cryptographic chaining (Flaw 43)
    try:
        last_log = conn.execute("SELECT entry_hash FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()
        prev_hash = last_log["entry_hash"] if last_log and last_log["entry_hash"] else "GENESIS_HASH_00000000000000000000000000000000"
    except Exception:
        prev_hash = "GENESIS_HASH_00000000000000000000000000000000"

    hash_payload = f"{prev_hash}|{now_str}|{user_id}|{username}|{action_str}|{module_str}|{record_id_str}|{old_val_str}|{new_val_str}|{details_str}|{engagement_id}"
    entry_hash = hashlib.sha256(hash_payload.encode('utf-8')).hexdigest()

    # Do not fabricate IP (Flaw 42)
    client_ip = ip_address if ip_address else None

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
        module_str.lower(),
        entity_id_int,
        prev_hash,
        entry_hash
    ))
    return cursor.lastrowid
