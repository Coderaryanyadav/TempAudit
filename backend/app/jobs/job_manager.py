import json
import uuid
import threading
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

from backend.app.database import get_db_connection

class JobStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class JobManager:
    """
    Lightweight SQLite-backed background job queue for long-running audit operations.
    Thread-safe and suitable for offline desktop deployments.
    """
    _executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="FinAudit-Worker")
    _cancelled_jobs = set()
    _lock = threading.Lock()

    @classmethod
    def create_job(
        cls,
        job_type: str,
        engagement_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
        created_by: str = "system"
    ) -> str:
        job_id = str(uuid.uuid4())
        now_str = datetime.now().isoformat()
        payload_str = json.dumps(payload or {})

        conn = get_db_connection()
        conn.execute("""
        INSERT INTO background_jobs (
            id, engagement_id, job_type, status, progress,
            payload_json, created_by, created_at
        ) VALUES (?, ?, ?, ?, 0, ?, ?, ?)
        """, (job_id, engagement_id, job_type, JobStatus.QUEUED, payload_str, created_by, now_str))
        conn.close()

        return job_id

    @classmethod
    def get_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM background_jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()
        if not row:
            return None
        res = dict(row)
        try:
            res["payload"] = json.loads(res.get("payload_json") or "{}")
        except Exception:
            res["payload"] = {}
        try:
            res["result"] = json.loads(res.get("result_json") or "{}")
        except Exception:
            res["result"] = {}
        return res

    @classmethod
    def list_jobs(cls, engagement_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        if engagement_id is not None:
            rows = conn.execute(
                "SELECT * FROM background_jobs WHERE engagement_id = ? ORDER BY created_at DESC LIMIT ?",
                (engagement_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM background_jobs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        conn.close()

        results = []
        for r in rows:
            item = dict(r)
            try:
                item["payload"] = json.loads(item.get("payload_json") or "{}")
            except Exception:
                item["payload"] = {}
            try:
                item["result"] = json.loads(item.get("result_json") or "{}")
            except Exception:
                item["result"] = {}
            results.append(item)
        return results

    @classmethod
    def update_progress(cls, job_id: str, progress: int, status: Optional[str] = None):
        now_str = datetime.now().isoformat()
        conn = get_db_connection()
        if status:
            conn.execute(
                "UPDATE background_jobs SET progress = ?, status = ? WHERE id = ?",
                (min(max(progress, 0), 100), status, job_id)
            )
        else:
            conn.execute(
                "UPDATE background_jobs SET progress = ? WHERE id = ?",
                (min(max(progress, 0), 100), job_id)
            )
        conn.close()

    @classmethod
    def cancel_job(cls, job_id: str) -> bool:
        with cls._lock:
            cls._cancelled_jobs.add(job_id)
        now_str = datetime.now().isoformat()
        conn = get_db_connection()
        conn.execute(
            "UPDATE background_jobs SET status = ?, completed_at = ? WHERE id = ? AND status IN (?, ?)",
            (JobStatus.CANCELLED, now_str, job_id, JobStatus.QUEUED, JobStatus.RUNNING)
        )
        conn.close()
        return True

    @classmethod
    def is_cancelled(cls, job_id: str) -> bool:
        with cls._lock:
            if job_id in cls._cancelled_jobs:
                return True
        conn = get_db_connection()
        row = conn.execute("SELECT status FROM background_jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()
        return bool(row and row["status"] == JobStatus.CANCELLED)

    @classmethod
    def submit_task(cls, job_id: str, task_fn: Callable[[str, Dict[str, Any]], Any], payload: Dict[str, Any]):
        """Dispatches the worker function into the thread pool."""
        def runner():
            if cls.is_cancelled(job_id):
                return

            now_str = datetime.now().isoformat()
            conn = get_db_connection()
            conn.execute(
                "UPDATE background_jobs SET status = ?, started_at = ?, progress = 5 WHERE id = ?",
                (JobStatus.RUNNING, now_str, job_id)
            )
            conn.close()

            try:
                result = task_fn(job_id, payload)
                if cls.is_cancelled(job_id):
                    return

                comp_str = datetime.now().isoformat()
                result_json_str = json.dumps(result if isinstance(result, (dict, list)) else {"output": str(result)})
                conn = get_db_connection()
                conn.execute("""
                UPDATE background_jobs
                SET status = ?, progress = 100, result_json = ?, completed_at = ?
                WHERE id = ?
                """, (JobStatus.COMPLETED, result_json_str, comp_str, job_id))
                conn.close()

            except Exception as e:
                err_str = str(e)
                comp_str = datetime.now().isoformat()
                conn = get_db_connection()
                conn.execute("""
                UPDATE background_jobs
                SET status = ?, error_message = ?, completed_at = ?
                WHERE id = ?
                """, (JobStatus.FAILED, err_str, comp_str, job_id))
                conn.close()

        cls._executor.submit(runner)
