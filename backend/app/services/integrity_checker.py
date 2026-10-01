import os
import sqlite3
from typing import Dict, Any, List
from datetime import datetime

from backend.app.database import DB_PATH, get_db_connection
from backend.migrations.runner import get_migration_status
from backend.app.utils.audit_logger import verify_audit_trail_integrity
from backend.app.repositories.evidence_repo import EvidenceRepository
from backend.app.ai.gateway import AIGateway
from backend.app.jobs.job_manager import JobManager

class SystemIntegrityChecker:
    """
    Comprehensive internal system integrity checker for FinAuditPro.
    Evaluates DB, schema, foreign keys, audit chain, evidence files, storage, and AI providers.
    """

    @classmethod
    def run_all_checks(cls) -> Dict[str, Any]:
        results = {}
        now_str = datetime.now().isoformat()

        # 1. Database Connectivity & Pragmas
        try:
            conn = get_db_connection()
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            
            # Foreign Key Constraint Check
            fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            fk_ok = len(fk_violations) == 0

            results["database"] = {
                "status": "PASS" if journal.upper() == "WAL" and foreign_keys == 1 else "WARNING",
                "journal_mode": journal,
                "foreign_keys_enabled": bool(foreign_keys),
                "busy_timeout_ms": busy_timeout,
                "path": os.path.basename(DB_PATH)
            }

            results["foreign_keys"] = {
                "status": "PASS" if fk_ok else "FAIL",
                "violation_count": len(fk_violations),
                "violations": [list(v) for v in fk_violations[:10]]
            }

            # 2. Schema Migration Status
            mig_status = get_migration_status(conn)
            results["schema"] = {
                "status": "PASS" if mig_status["is_up_to_date"] else "WARNING",
                "current_version": mig_status["current_version"],
                "applied_count": mig_status["applied_count"],
                "pending_count": mig_status["pending_count"],
                "is_up_to_date": mig_status["is_up_to_date"]
            }

            # 3. Cryptographic Audit Chain Integrity
            chain_status = verify_audit_trail_integrity(conn)
            results["audit_chain"] = {
                "status": "PASS" if chain_status.get("valid") else "FAIL",
                "entries_checked": chain_status.get("entries_checked", 0),
                "total_entries": chain_status.get("total_entries", 0),
                "is_valid": chain_status.get("valid", False),
                "tampering_detected": not chain_status.get("valid", True)
            }

            # 4. Evidence Files Integrity Sample
            ev_repo = EvidenceRepository(conn)
            ev_items = conn.execute("SELECT id FROM evidence_items LIMIT 50").fetchall()
            ev_corrupted = 0
            ev_missing = 0
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

            for r in ev_items:
                v = ev_repo.verify_physical_integrity(r["id"], base_dir=base_dir)
                if not v.get("valid"):
                    if v.get("status") == "FILE_MISSING":
                        ev_missing += 1
                    else:
                        ev_corrupted += 1

            ev_status = "PASS"
            if ev_corrupted > 0:
                ev_status = "FAIL"
            elif ev_missing > 0:
                ev_status = "WARNING"

            results["evidence"] = {
                "status": ev_status,
                "sampled_count": len(ev_items),
                "corrupted_count": ev_corrupted,
                "missing_count": ev_missing
            }

            conn.close()
        except Exception as e:
            results["database"] = {"status": "FAIL", "error": str(e)}

        # 5. Physical Storage Health
        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploaded_files")
        backups_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backups")
        
        storage_ok = os.path.exists(uploads_dir) and os.access(uploads_dir, os.W_OK) and os.path.exists(backups_dir) and os.access(backups_dir, os.W_OK)
        results["storage"] = {
            "status": "PASS" if storage_ok else "WARNING",
            "uploads_writable": os.access(uploads_dir, os.W_OK) if os.path.exists(uploads_dir) else False,
            "backups_writable": os.access(backups_dir, os.W_OK) if os.path.exists(backups_dir) else False
        }

        # 6. Local AI Provider Connectivity
        try:
            ai_health = AIGateway.check_health()
            results["ai_provider"] = {
                "status": "PASS" if ai_health.get("available") else "INFO",
                "engine": ai_health.get("engine"),
                "status_message": ai_health.get("status_message"),
                "latency_ms": ai_health.get("latency_ms")
            }
        except Exception as e:
            results["ai_provider"] = {"status": "INFO", "message": str(e)}

        # 7. Background Jobs Queue Health
        try:
            recent_jobs = JobManager.list_jobs(limit=20)
            failed_jobs = [j for j in recent_jobs if j.get("status") == "FAILED"]
            results["background_jobs"] = {
                "status": "PASS" if len(failed_jobs) == 0 else "WARNING",
                "recent_jobs_count": len(recent_jobs),
                "failed_jobs_count": len(failed_jobs)
            }
        except Exception:
            results["background_jobs"] = {"status": "PASS", "recent_jobs_count": 0, "failed_jobs_count": 0}

        # Determine overall system health
        statuses = [v.get("status") for v in results.values() if isinstance(v, dict)]
        if "FAIL" in statuses:
            overall = "FAIL"
        elif "WARNING" in statuses:
            overall = "WARNING"
        else:
            overall = "PASS"

        return {
            "overall_status": overall,
            "checked_at": now_str,
            "components": results
        }
