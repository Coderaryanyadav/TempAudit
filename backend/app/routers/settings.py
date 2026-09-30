import json
import os
import shutil
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.auth import get_current_user, require_role
from backend.app.database import DB_PATH, get_db_connection
from backend.app.utils.audit_logger import log_audit_event

router = APIRouter(prefix="/api/settings", tags=["Settings & Application Config"])

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)


class SettingUpdateItem(BaseModel):
    key: str
    value: Any


class BulkSettingsUpdate(BaseModel):
    settings: Dict[str, Any]


DEFAULT_SETTINGS = {
    "firm_name": "Sharma & Associates, Chartered Accountants",
    "firm_icai_reg": "FRN-012948N",
    "materiality_percentage": 0.5,
    "materiality_benchmark": "Turnover",
    "cash_threshold_40a3": 10000.0,
    "cash_threshold_269st": 200000.0,
    "gst_turnover_threshold": 20000000.0,
    "benford_confidence_level": 0.95,
    "isolation_forest_contamination": 0.05,
    "auto_backup_enabled": True,
    "backup_retention_days": 30,
    "session_timeout_minutes": 60,
    "strict_maker_checker": True
}


def _enforce_backup_retention(retention_days: int = 30):
    """Deletes backup files older than retention_days."""
    try:
        if not os.path.exists(BACKUP_DIR) or retention_days <= 0:
            return
        now = time.time()
        max_age_seconds = retention_days * 86400
        for f in os.listdir(BACKUP_DIR):
            fpath = os.path.join(BACKUP_DIR, f)
            if os.path.isfile(fpath) and (f.startswith("finauditpro_backup_") or f.endswith(".db")):
                if (now - os.path.getmtime(fpath)) > max_age_seconds:
                    try:
                        os.remove(fpath)
                    except OSError:
                        pass
    except Exception:
        pass


@router.get("")
def get_all_settings(current_user: dict = Depends(get_current_user)):
    """Retrieve all application settings merged with defaults."""
    conn = get_db_connection()
    rows = conn.execute("SELECT key, value, updated_at FROM app_settings").fetchall()
    conn.close()

    stored = {}
    for r in rows:
        try:
            stored[r["key"]] = json.loads(r["value"])
        except Exception:
            stored[r["key"]] = r["value"]

    merged = {**DEFAULT_SETTINGS, **stored}
    return {
        "settings": merged,
        "defaults": DEFAULT_SETTINGS
    }


@router.post("")
def update_settings(
    update_req: BulkSettingsUpdate,
    current_user: dict = Depends(require_role(["Admin"]))
):
    """
    Admin: Update system and audit engine configuration settings.
    Records SETTINGS_CHANGE in the append-only audit trail with Old and New values.
    """
    conn = get_db_connection()
    now_str = datetime.now().isoformat()
    old_settings = {}
    new_settings = {}

    for k, v in update_req.settings.items():
        # Get existing value
        existing = conn.execute("SELECT value FROM app_settings WHERE key = ?", (k,)).fetchone()
        if existing:
            try:
                old_val = json.loads(existing["value"])
            except Exception:
                old_val = existing["value"]
        else:
            old_val = DEFAULT_SETTINGS.get(k)

        val_str = json.dumps(v) if isinstance(v, (dict, list, bool, int, float)) else str(v)

        conn.execute("""
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (k, val_str, now_str))

        old_settings[k] = old_val
        new_settings[k] = v

    # Record audit log
    log_audit_event(
        conn,
        action="SETTINGS_CHANGE",
        module="SETTINGS",
        record_id="app_configuration",
        old_value=old_settings,
        new_value=new_settings,
        details=f"Updated {len(new_settings)} application configuration settings",
        user=current_user
    )

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": "Configuration settings saved successfully.",
        "updated_keys": list(new_settings.keys())
    }


@router.get("/system-info")
def get_system_info(current_user: dict = Depends(get_current_user)):
    """Returns local host environment status, database statistics, and offline certification."""
    conn = get_db_connection()
    user_count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    client_count = conn.execute("SELECT COUNT(*) as c FROM clients").fetchone()["c"]
    eng_count = conn.execute("SELECT COUNT(*) as c FROM engagements").fetchone()["c"]
    tx_count = conn.execute("SELECT COUNT(*) as c FROM transactions").fetchone()["c"]
    finding_count = conn.execute("SELECT COUNT(*) as c FROM audit_findings").fetchone()["c"]
    wp_count = conn.execute("SELECT COUNT(*) as c FROM working_papers").fetchone()["c"]
    audit_log_count = conn.execute("SELECT COUNT(*) as c FROM audit_logs").fetchone()["c"]
    conn.close()

    db_size_kb = round(os.path.getsize(DB_PATH) / 1024, 2) if os.path.exists(DB_PATH) else 0

    return {
        "app_name": "FinAuditPro",
        "version": "1.0.0 (Offline Desktop Edition)",
        "mode": "100% Offline (Local SQLite Database)",
        "database_engine": "SQLite 3 (Immutable Audit Trail Enabled)",
        "database_path": os.path.basename(DB_PATH),
        "database_size_kb": db_size_kb,
        "statistics": {
            "users": user_count,
            "clients": client_count,
            "engagements": eng_count,
            "total_transactions": tx_count,
            "audit_findings": finding_count,
            "working_papers": wp_count,
            "audit_logs": audit_log_count
        }
    }


@router.post("/backup")
def create_backup(current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Creates a timestamped local SQLite backup using SQLite Online Backup API and records an audit trail entry."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Database file not found")

    # Fetch retention setting
    conn_s = get_db_connection()
    ret_row = conn_s.execute("SELECT value FROM app_settings WHERE key = 'backup_retention_days'").fetchone()
    conn_s.close()
    try:
        ret_days = int(json.loads(ret_row["value"])) if ret_row else 30
    except Exception:
        ret_days = 30

    _enforce_backup_retention(ret_days)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"finauditpro_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_file)

    # Use SQLite Online Backup API for point-in-time consistency
    src_conn = sqlite3.connect(DB_PATH)
    dest_conn = sqlite3.connect(backup_path)
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    size_kb = round(os.path.getsize(backup_path) / 1024, 2)

    conn = get_db_connection()
    try:
        log_audit_event(
            conn,
            action="DATABASE_BACKUP",
            module="BACKUP",
            record_id=backup_file,
            new_value={"backup_file": backup_file, "size_kb": size_kb},
            details=f"Created database backup snapshot: {backup_file} ({size_kb} KB)",
            user=current_user
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "message": "Database backup created successfully",
        "backup_file": backup_file,
        "size_kb": size_kb,
        "download_url": f"/api/audit-trail/backup/download/{backup_file}"
    }


@router.get("/backup/download/{filename}")
def download_backup(filename: str, current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Downloads a local database backup file."""
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(BACKUP_DIR, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Backup file not found")

    conn = get_db_connection()
    try:
        log_audit_event(
            conn,
            action="REPORT_EXPORT",
            module="BACKUP",
            record_id=safe_filename,
            details=f"Downloaded database backup file: {safe_filename}",
            user=current_user
        )
        conn.commit()
    finally:
        conn.close()

    return FileResponse(path=file_path, filename=safe_filename, media_type="application/octet-stream")
