import os
import hashlib
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime

class EvidenceRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def register_evidence(
        self,
        engagement_id: int,
        filename: str,
        original_filename: str,
        storage_path: str,
        file_size: int,
        mime_type: str,
        sha256_hash: str,
        uploaded_by: str,
        working_paper_id: Optional[int] = None,
        parent_evidence_id: Optional[int] = None,
        replacement_reason: Optional[str] = None,
        version: int = 1
    ) -> int:
        now_str = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO evidence_items (
            engagement_id, working_paper_id, filename, original_filename,
            storage_path, file_size, mime_type, sha256_hash, version,
            parent_evidence_id, replacement_reason, uploaded_by, uploaded_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
        """, (
            engagement_id, working_paper_id, filename, original_filename,
            storage_path, file_size, mime_type, sha256_hash, version,
            parent_evidence_id, replacement_reason, uploaded_by, now_str
        ))
        
        # If this is a new version superseding an old one, mark parent as SUPERSEDED
        if parent_evidence_id:
            cursor.execute(
                "UPDATE evidence_items SET status = 'SUPERSEDED' WHERE id = ?",
                (parent_evidence_id,)
            )
            
        return cursor.lastrowid

    def get_by_id(self, evidence_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute("SELECT * FROM evidence_items WHERE id = ?", (evidence_id,)).fetchone()
        return dict(row) if row else None

    def list_by_engagement(self, engagement_id: int) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM evidence_items WHERE engagement_id = ? ORDER BY id DESC",
            (engagement_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def list_by_working_paper(self, wp_id: int) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM evidence_items WHERE working_paper_id = ? ORDER BY version ASC, id ASC",
            (wp_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def resolve_storage_path(storage_path: str, base_dir: Optional[str] = None) -> Optional[str]:
        """Resolve only relative evidence paths contained by the uploaded_files root.

        `base_dir` is the backend directory that contains uploaded_files. Absolute,
        parent-relative, Windows-style, and symlink-escaped paths are rejected.
        """
        if not isinstance(storage_path, str) or not storage_path.strip():
            return None
        raw_path = storage_path.strip()
        if os.path.isabs(raw_path) or raw_path.startswith(("/", "\\")) or "\\" in raw_path:
            return None
        raw_parts = raw_path.split("/")
        if any(part in {"", ".", ".."} for part in raw_parts) or ":" in raw_parts[0]:
            return None

        backend_dir = base_dir or os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        evidence_root = os.path.realpath(os.path.join(backend_dir, "uploaded_files"))
        candidate = os.path.realpath(os.path.join(backend_dir, raw_path))
        try:
            if os.path.commonpath([evidence_root, candidate]) != evidence_root:
                return None
        except ValueError:
            return None
        return candidate

    def verify_physical_integrity(self, evidence_id: int, base_dir: Optional[str] = None) -> Dict[str, Any]:
        """Verify a registered evidence file without following paths outside uploaded_files."""
        row = self.get_by_id(evidence_id)
        if not row:
            return {"status": "NOT_FOUND", "valid": False, "error": "Evidence record does not exist."}

        abs_path = self.resolve_storage_path(row.get("storage_path"), base_dir=base_dir)
        if abs_path is None:
            return {
                "status": "INVALID_PATH",
                "valid": False,
                "evidence_id": evidence_id,
                "expected_hash": row.get("sha256_hash"),
                "actual_hash": None,
                "error": "Evidence storage path is invalid or escapes the evidence storage directory.",
            }

        if not os.path.isfile(abs_path):
            return {
                "status": "FILE_MISSING",
                "valid": False,
                "evidence_id": evidence_id,
                "expected_hash": row["sha256_hash"],
                "actual_hash": None,
                "path": abs_path,
                "error": "Evidence file does not exist on disk.",
            }

        sha = hashlib.sha256()
        with open(abs_path, "rb") as evidence_file:
            while chunk := evidence_file.read(65536):
                sha.update(chunk)
        disk_hash = sha.hexdigest()
        is_intact = disk_hash == row["sha256_hash"]
        return {
            "status": "VALID" if is_intact else "CORRUPTED",
            "valid": is_intact,
            "evidence_id": evidence_id,
            "expected_hash": row["sha256_hash"],
            "actual_hash": disk_hash,
            "path": abs_path,
            "version": row["version"],
        }
