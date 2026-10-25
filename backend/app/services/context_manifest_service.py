"""
Context Manifest Service for Conversational AI Assistant
FinAuditPro - Intelligent Offline Auditing Platform

Constructs a compact, deterministic, authoritative pre-flight manifest
of the complete engagement file (Client identity, FY, Trial Balance status,
Uploaded Documents inventory, Working Papers, Checklists, Findings,
and Freshness Fingerprint) prior to local AI model generation.
"""

import hashlib
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.app.database import get_db_path


class ContextManifestService:
    """
    Constructs an authoritative pre-flight context manifest from SQLite.
    Guarantees that the conversational AI understands the active client,
    reporting period, available data, missing data, and workflow state.
    """

    @staticmethod
    def _get_readonly_conn() -> sqlite3.Connection:
        db_path = get_db_path()
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        return conn

    @classmethod
    def compute_engagement_fingerprint(cls, engagement_id: int) -> str:
        """
        Computes a deterministic SHA-256 fingerprint of the current engagement data.
        Detects if transactions, findings, ledgers, uploaded files, working papers,
        or checklists were mutated since a conversation turn started.
        """
        conn = cls._get_readonly_conn()
        try:
            cur = conn.cursor()
            components = [f"eng:{engagement_id}"]

            # 1. Transactions
            r = cur.execute(
                "SELECT COUNT(*), COALESCE(MAX(id), 0), COALESCE(SUM(amount), 0) FROM transactions WHERE engagement_id = ?",
                (engagement_id,)
            ).fetchone()
            components.append(f"tx:{r[0]}:{r[1]}:{float(r[2]):.2f}")

            # 2. Findings
            r = cur.execute(
                "SELECT COUNT(*), COALESCE(MAX(id), 0), COALESCE(SUM(risk_score), 0) FROM audit_findings WHERE engagement_id = ?",
                (engagement_id,)
            ).fetchone()
            components.append(f"fd:{r[0]}:{r[1]}:{float(r[2]):.2f}")

            # 3. Uploaded Files
            r = cur.execute(
                "SELECT COUNT(*), COALESCE(MAX(id), 0) FROM uploaded_files WHERE engagement_id = ?",
                (engagement_id,)
            ).fetchone()
            components.append(f"uf:{r[0]}:{r[1]}")

            # 4. Ledgers
            r = cur.execute(
                "SELECT COUNT(*), COALESCE(MAX(id), 0), COALESCE(SUM(closing_balance), 0) FROM ledgers WHERE engagement_id = ?",
                (engagement_id,)
            ).fetchone()
            components.append(f"ld:{r[0]}:{r[1]}:{float(r[2]):.2f}")

            # 5. Working Papers
            r = cur.execute(
                "SELECT COUNT(*), COALESCE(MAX(id), 0) FROM working_papers WHERE engagement_id = ?",
                (engagement_id,)
            ).fetchone()
            components.append(f"wp:{r[0]}:{r[1]}")

            # 6. Audit Checklists
            r = cur.execute(
                "SELECT COUNT(*), COALESCE(MAX(id), 0) FROM audit_checklists WHERE engagement_id = ?",
                (engagement_id,)
            ).fetchone()
            components.append(f"cl:{r[0]}:{r[1]}")

            raw = "|".join(components)
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        finally:
            conn.close()

    @classmethod
    def generate_context_manifest(cls, engagement_id: int) -> Dict[str, Any]:
        """
        Builds the canonical engagement context manifest containing:
        - Engagement & Client Identity
        - Reporting Period & Framework
        - Trial Balance Balance Status & Suspense Accounts
        - Uploaded Document Inventory & Parse Health
        - Working Papers & Review Progress
        - Audit Checklists & Outstanding Compliance Items
        - Centralized Risk Findings Summary
        - Deterministic Data Freshness Fingerprint
        """
        conn = cls._get_readonly_conn()
        try:
            cur = conn.cursor()

            # 1. Engagement & Client Identity
            eng_row = cur.execute("""
                SELECT e.id, e.title, e.financial_year, e.audit_type, e.status AS eng_status,
                       e.materiality_threshold,
                       c.id AS client_id, c.name AS client_name, c.pan, c.gstin
                FROM engagements e
                JOIN clients c ON e.client_id = c.id
                WHERE e.id = ?
            """, (engagement_id,)).fetchone()

            if not eng_row:
                return {
                    "status": "NOT_FOUND",
                    "engagement_id": engagement_id,
                    "error": f"Engagement ID {engagement_id} not found."
                }

            eng = dict(eng_row)

            # 2. Trial Balance & Ledgers Summary
            tb_rows = cur.execute("""
                SELECT ledger_name, account_group, opening_balance, total_debit, total_credit, closing_balance
                FROM ledgers
                WHERE engagement_id = ?
            """, (engagement_id,)).fetchall()

            total_tb_ledgers = len(tb_rows)
            tb_total_debit = sum(float(r["total_debit"] or 0.0) for r in tb_rows)
            tb_total_credit = sum(float(r["total_credit"] or 0.0) for r in tb_rows)
            tb_difference = round(abs(tb_total_debit - tb_total_credit), 2)
            tb_balanced = (tb_difference == 0.0 and total_tb_ledgers > 0)

            suspense_ledgers = [
                {"name": r["ledger_name"], "balance": float(r["closing_balance"] or 0.0)}
                for r in tb_rows
                if any(k in (r["ledger_name"] or "").lower() for k in ["suspense", "unreconciled", "clearing", "round off"])
            ]

            # 3. Uploaded Files Inventory
            files_rows = cur.execute("""
                SELECT id, file_name, file_type, data_category, row_count, successful_rows, failed_rows, warning_count, uploaded_at
                FROM uploaded_files
                WHERE engagement_id = ?
                ORDER BY id ASC
            """, (engagement_id,)).fetchall()

            doc_inventory = [dict(f) for f in files_rows]
            total_docs = len(doc_inventory)
            failed_docs = [d for d in doc_inventory if (d.get("failed_rows") or 0) > 0]

            # 4. Working Papers Summary
            wp_rows = cur.execute("""
                SELECT id, wp_reference, title, area, status, prepared_by, reviewed_by
                FROM working_papers
                WHERE engagement_id = ?
                ORDER BY wp_reference ASC
            """, (engagement_id,)).fetchall()

            wp_list = [dict(w) for w in wp_rows]
            total_wps = len(wp_list)
            wps_by_status = {
                "Reviewed": len([w for w in wp_list if w["status"] == "Reviewed"]),
                "Prepared": len([w for w in wp_list if w["status"] in ["Prepared", "Draft"]]),
            }

            # 5. Audit Checklist Summary
            cl_rows = cur.execute("""
                SELECT category, item_code, status
                FROM audit_checklists
                WHERE engagement_id = ?
            """, (engagement_id,)).fetchall()

            total_checklists = len(cl_rows)
            cl_completed = len([c for c in cl_rows if c["status"] in ["Completed", "Satisfactory"]])
            cl_outstanding = len([c for c in cl_rows if c["status"] in ["Not Started", "In Progress", "Pending Review"]])
            cl_non_compliant = len([c for c in cl_rows if c["status"] in ["Exception Flagged", "Non-Compliant"]])

            # 6. Centralized Findings Summary
            fd_rows = cur.execute("""
                SELECT severity, status FROM audit_findings WHERE engagement_id = ?
            """, (engagement_id,)).fetchall()

            total_findings = len(fd_rows)
            findings_open = len([f for f in fd_rows if f["status"] == "Open"])
            findings_resolved = len([f for f in fd_rows if f["status"] == "Resolved"])
            crit_findings = len([f for f in fd_rows if f["severity"] == "CRITICAL"])
            high_findings = len([f for f in fd_rows if f["severity"] == "HIGH"])
            med_findings = len([f for f in fd_rows if f["severity"] == "MEDIUM"])

            # 7. Total Transactions Count
            tx_count_row = cur.execute(
                "SELECT COUNT(*) FROM transactions WHERE engagement_id = ?",
                (engagement_id,)
            ).fetchone()
            total_tx = tx_count_row[0] if tx_count_row else 0

            # 8. Data Freshness Fingerprint
            freshness_hash = cls.compute_engagement_fingerprint(engagement_id)

            manifest_data = {
                "status": "READY",
                "engagement_id": engagement_id,
                "client_id": eng["client_id"],
                "client_name": eng["client_name"],
                "pan": eng["pan"],
                "gstin": eng["gstin"],
                "financial_year": eng["financial_year"],
                "audit_type": eng["audit_type"],
                "engagement_status": eng["eng_status"],
                "materiality_threshold": float(eng.get("materiality_threshold") or 0.0),
                "reporting_framework": eng.get("reporting_framework") or "ICAI / Companies Act 2013",
                "total_transactions": total_tx,
                "trial_balance": {
                    "total_ledgers": total_tb_ledgers,
                    "total_debit": tb_total_debit,
                    "total_credit": tb_total_credit,
                    "difference": tb_difference,
                    "is_balanced": tb_balanced,
                    "suspense_accounts": suspense_ledgers
                },
                "documents": {
                    "total_files": total_docs,
                    "items": doc_inventory,
                    "has_failed_rows": len(failed_docs) > 0,
                    "failed_files_count": len(failed_docs)
                },
                "working_papers": {
                    "total_count": total_wps,
                    "reviewed_count": wps_by_status.get("Reviewed", 0),
                    "pending_count": wps_by_status.get("Prepared", 0),
                    "items": wp_list
                },
                "checklists": {
                    "total_items": total_checklists,
                    "completed_count": cl_completed,
                    "outstanding_count": cl_outstanding,
                    "non_compliant_count": cl_non_compliant
                },
                "findings": {
                    "total": total_findings,
                    "open": findings_open,
                    "resolved": findings_resolved,
                    "critical": crit_findings,
                    "high": high_findings,
                    "medium": med_findings
                },
                "freshness_fingerprint": freshness_hash
            }

            # Build markdown representation for model system prompt
            manifest_data["markdown"] = cls._build_markdown_block(manifest_data)
            return manifest_data
        finally:
            conn.close()

    @classmethod
    def _build_markdown_block(cls, data: Dict[str, Any]) -> str:
        """Formats the manifest as a compact Markdown block for LLM prompt ingestion."""
        tb = data["trial_balance"]
        docs = data["documents"]
        wps = data["working_papers"]
        cls_info = data["checklists"]
        fds = data["findings"]

        tb_status_text = "BALANCED (₹0.00 difference)" if tb["is_balanced"] else f"OUT OF BALANCE by ₹{tb['difference']:,.2f}"
        if tb["total_ledgers"] == 0:
            tb_status_text = "NOT IMPORTED / EMPTY"

        doc_summary_lines = []
        if docs["items"]:
            for d in docs["items"][:6]:
                doc_summary_lines.append(
                    f"  - [Doc #{d['id']}] {d['file_name']} ({d['data_category']}, {d['row_count']} rows, failed: {d['failed_rows']})"
                )
            if len(docs["items"]) > 6:
                doc_summary_lines.append(f"  - ...and {len(docs['items']) - 6} more document(s).")
        else:
            doc_summary_lines.append("  - No files uploaded yet.")

        wp_summary_lines = []
        if wps["items"]:
            for w in wps["items"][:5]:
                wp_summary_lines.append(f"  - [WP: {w['wp_reference']}] {w['title']} (Status: {w['status']}, Area: {w['area']})")
            if len(wps["items"]) > 5:
                wp_summary_lines.append(f"  - ...and {len(wps['items']) - 5} more working paper(s).")
        else:
            wp_summary_lines.append("  - No working papers created yet.")

        lines = [
            "### CANONICAL ENGAGEMENT MANIFEST (AUTHORITATIVE PRE-FLIGHT AUDIT STATE)",
            f"- **Client Entity:** {data['client_name']} (PAN: {data['pan'] or 'N/A'}, GSTIN: {data['gstin'] or 'N/A'})",
            f"- **Financial Year & Scope:** FY {data['financial_year']} | Audit Type: {data['audit_type']} | Status: {data['engagement_status']}",
            f"- **Materiality Threshold:** ₹{data['materiality_threshold']:,.2f} | Framework: {data['reporting_framework']}",
            f"- **Data Freshness Fingerprint:** `{data['freshness_fingerprint']}`",
            f"- **Transactions Loaded:** {data['total_transactions']:,} records",
            f"- **Trial Balance State:** {tb_status_text} (Dr: ₹{tb['total_debit']:,.2f}, Cr: ₹{tb['total_credit']:,.2f}, Ledgers: {tb['total_ledgers']})",
            f"- **Suspense / Clearing Ledgers:** {len(tb['suspense_accounts'])} active suspense account(s)",
            f"- **Uploaded Documents Inventory ({docs['total_files']} files):**",
            *doc_summary_lines,
            f"- **Working Papers ({wps['total_count']} papers, {wps['reviewed_count']} reviewed):**",
            *wp_summary_lines,
            f"- **Audit Checklists:** {cls_info['total_items']} items ({cls_info['completed_count']} completed, {cls_info['outstanding_count']} outstanding, {cls_info['non_compliant_count']} exceptions)",
            f"- **Centralized Audit Exceptions ({fds['total']} total):** {fds['open']} Open, {fds['resolved']} Resolved | CRITICAL: {fds['critical']}, HIGH: {fds['high']}, MEDIUM: {fds['medium']}",
            "---",
            "MANDATORY AUDIT GROUNDING RULES:",
            "1. Ground all client statements strictly on the verified client and FY above. Never mix up client identities.",
            "2. If an uploaded document has failed rows or was never parsed, state this explicitly. Do not invent contents.",
            "3. If a trial balance is out of balance, disclose the discrepancy instead of assuming it balances.",
            "4. Use read-only tools to fetch detailed evidence (vouchers, working papers, checklists) before drawing conclusions.",
        ]
        return "\n".join(lines)
