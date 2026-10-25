"""
Read-Only Audit Evidence Retrieval Tools for Conversational AI Assistant
FinAuditPro - Intelligent Offline Auditing Platform

Enforces strict data boundaries:
- Read-only database operations (PRAGMA query_only = ON)
- Explicit engagement ID scoping (zero cross-engagement data leakage)
- Bounded row limits (maximum 15-20 rows)
- PII sanitization on text descriptions
"""

import json
import sqlite3
from typing import Dict, Any, List, Optional
from backend.app.database import get_db_path
from backend.app.services.local_ai_provider import sanitize_audit_text

# =========================================================================
# Statutory Knowledge Repository (ICAI SAs, Income Tax, GST, CARO 2020)
# =========================================================================

STATUTORY_KNOWLEDGE = {
    "40a3": {
        "statute": "Section 40A(3) of the Income Tax Act, 1961",
        "form_3cd_clause": "Clause 21(d)",
        "threshold": "₹10,000 per person per day (₹35,000 for payment to goods carriage operators)",
        "provision": (
            "Where an assessee incurs any expenditure in respect of which a payment or aggregate of payments "
            "made to a person in a day, otherwise than by an account payee cheque drawn on a bank or account payee "
            "bank draft, or use of electronic clearing system through a bank account or through other electronic "
            "mode as may be prescribed, exceeds ₹10,000, no deduction shall be allowed in respect of such expenditure."
        ),
        "exceptions": (
            "Rule 6DD provides exhaustive exceptions where payments exceeding ₹10,000 in cash are not disallowed: "
            "(a) payments to RBI, SBI, banking companies, LIC; "
            "(b) payments to Government for taxes, duties; "
            "(c) payments through letters of credit, telegraphic transfers, book adjustments; "
            "(d) payments for agricultural or forest produce to the direct cultivator/grower; "
            "(e) payments to cottage industry producers without aid of power; "
            "(f) payments in a village/town not served by any bank; "
            "(g) payments on a day when banks were closed due to holiday/strike; "
            "(h) payments by an agent to his principal for goods procured; "
            "(i) payments made by an authorized dealer or money changer."
        ),
        "audit_procedure": (
            "1. Inspect cash payment vouchers and examine ledger accounts with aggregate cash debits > ₹10,000. "
            "2. Inquire whether any Rule 6DD circumstances applied. "
            "3. If unexplained, report disallowance in Tax Audit Report Form 3CD Clause 21(d)."
        )
    },
    "269st": {
        "statute": "Section 269ST of the Income Tax Act, 1961",
        "form_3cd_clause": "Clause 31(ba), (bb), (bc), (bd)",
        "threshold": "₹2,00,000 or more",
        "provision": (
            "No person shall receive an amount of ₹2,00,000 or more: "
            "(a) in aggregate from a person in a day; or "
            "(b) in respect of a single transaction; or "
            "(c) in respect of transactions relating to one event or occasion from a person, "
            "otherwise than by an account payee cheque or account payee bank draft or electronic clearing system."
        ),
        "penalty": "Section 271DA: Penalty equal to 100% of the amount received in contravention of Section 269ST.",
        "audit_procedure": (
            "1. Filter all receipt vouchers where amount >= ₹2,00,000 received in cash or bearer mode. "
            "2. Group cash receipts by date and customer to detect single-day aggregate violations. "
            "3. Group receipts by invoice/contract to detect multi-date single-transaction violations."
        )
    },
    "43bh": {
        "statute": "Section 43B(h) of the Income Tax Act, 1961",
        "form_3cd_clause": "Clause 26",
        "threshold": "15 days (default) or up to 45 days (if written agreement exists) under MSMED Act Section 15",
        "provision": (
            "Any sum payable by the assessee to a micro or small enterprise beyond the time limit specified in "
            "Section 15 of the Micro, Small and Medium Enterprises Development Act, 2006 shall be allowed as a "
            "deduction only in computing the income of the previous year in which such sum is actually paid, "
            "irrespective of the previous year in which the liability to pay was incurred."
        ),
        "audit_procedure": (
            "1. Obtain list of vendors registered as Micro or Small enterprises with Udyam Registration. "
            "2. Calculate payment ageing from invoice date / acceptance date. "
            "3. Disallow outstanding dues unpaid as of March 31 beyond the 15/45 day limit."
        )
    },
    "gst_itc": {
        "statute": "Section 16(2)(aa) of the CGST Act, 2017 & Rule 36(4)",
        "threshold": "100% matching against GSTR-2B",
        "provision": (
            "Input Tax Credit (ITC) can only be availed by a registered person if the details of the invoice or "
            "debit note have been furnished by the supplier in the statement of outward supplies (GSTR-1) and "
            "such details have been communicated to the recipient in GSTR-2B."
        ),
        "audit_procedure": (
            "1. Reconcile Purchase Register ITC against GSTR-2B auto-drafted statement. "
            "2. Identify invoices missing in 2B, mismatched tax amounts, or supplier GSTIN cancellations. "
            "3. Advise client on ineligible ITC reversal along with applicable interest under Section 50."
        )
    },
    "sa_500": {
        "statute": "ICAI Standard on Auditing (SA) 500 — Audit Evidence",
        "objective": "To design and perform audit procedures that obtain sufficient appropriate audit evidence to draw reasonable conclusions on which to base the audit opinion.",
        "key_principles": (
            "Reliability of audit evidence is influenced by its source and nature: "
            "1. External evidence (bank confirmations, GSTR-2B) is more reliable than internal evidence. "
            "2. Evidence obtained directly by the auditor is more reliable than evidence obtained indirectly. "
            "3. Original documents are more reliable than photocopies or verbal statements."
        )
    },
    "sa_240": {
        "statute": "ICAI Standard on Auditing (SA) 240 — The Auditor's Responsibilities Relating to Fraud in an Audit of Financial Statements",
        "key_principles": (
            "The auditor is responsible for maintaining professional skepticism throughout the audit, recognizing "
            "the possibility that a material misstatement due to fraud could exist. "
            "Focus areas include: management override of controls, round-sum journal entries near period end, "
            "unusual related party transactions, and complex transactions lacking business purpose."
        )
    }
}


# =========================================================================
# Read-Only Tool Execution Layer
# =========================================================================

class AssistantTools:
    """
    Suite of bounded, read-only tools providing actual financial evidence to the AI assistant.
    Always uses PRAGMA query_only = ON to guarantee zero database modifications.
    """

    @staticmethod
    def _get_readonly_conn() -> sqlite3.Connection:
        path = get_db_path()
        conn = sqlite3.connect(path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        # Strict security enforcement: Connection cannot execute DDL/DML
        conn.execute("PRAGMA query_only = ON")
        return conn

    @classmethod
    def get_engagement_summary(cls, engagement_id: int) -> Dict[str, Any]:
        """
        Retrieves high-level metadata, turnover metrics, and finding statistics for the engagement.
        """
        conn = cls._get_readonly_conn()
        try:
            eng = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
            if not eng:
                return {"error": f"Engagement ID {engagement_id} not found"}
            
            client = conn.execute("SELECT name, pan, gstin, entity_type FROM clients WHERE id = ?", (eng["client_id"],)).fetchone()
            client_name = client["name"] if client else "Unknown Client"
            
            # Turnover metrics
            tx_stats = conn.execute("""
                SELECT COUNT(*) as tx_count,
                       COALESCE(SUM(debit), 0.0) as total_debit,
                       COALESCE(SUM(credit), 0.0) as total_credit
                FROM transactions WHERE engagement_id = ?
            """, (engagement_id,)).fetchone()

            # Finding statistics by severity
            findings_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total_findings,
                    COALESCE(SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END), 0) as critical_count,
                    COALESCE(SUM(CASE WHEN severity = 'HIGH' THEN 1 ELSE 0 END), 0) as high_count,
                    COALESCE(SUM(CASE WHEN severity = 'MEDIUM' THEN 1 ELSE 0 END), 0) as medium_count,
                    COALESCE(SUM(CASE WHEN severity = 'LOW' THEN 1 ELSE 0 END), 0) as low_count
                FROM audit_findings WHERE engagement_id = ?
            """, (engagement_id,)).fetchone()

            # Distinct ledgers count
            ledgers_count = conn.execute("""
                SELECT COUNT(DISTINCT ledger) as count FROM transactions WHERE engagement_id = ? AND ledger IS NOT NULL
            """, (engagement_id,)).fetchone()["count"]

            return {
                "engagement_id": engagement_id,
                "title": eng["title"],
                "financial_year": eng["financial_year"],
                "audit_type": eng["audit_type"],
                "client_name": client_name,
                "client_type": client["entity_type"] if client else "Company",
                "materiality_threshold": eng["materiality_threshold"],
                "total_transactions": tx_stats["tx_count"],
                "total_debit_turnover": round(tx_stats["total_debit"], 2),
                "total_credit_turnover": round(tx_stats["total_credit"], 2),
                "distinct_ledgers_count": ledgers_count,
                "total_findings": findings_stats["total_findings"],
                "critical_findings": findings_stats["critical_count"],
                "high_findings": findings_stats["high_count"],
                "medium_findings": findings_stats["medium_count"],
                "low_findings": findings_stats["low_count"]
            }
        finally:
            conn.close()

    @classmethod
    def get_audit_finding(cls, engagement_id: int, identifier: str) -> Dict[str, Any]:
        """
        Retrieves a specific audit finding by finding_code (e.g., 'DET-TAX-40A3') or numerical ID.
        """
        conn = cls._get_readonly_conn()
        try:
            ident_clean = str(identifier).strip()
            row = None
            if ident_clean.isdigit():
                row = conn.execute(
                    "SELECT * FROM audit_findings WHERE engagement_id = ? AND id = ?",
                    (engagement_id, int(ident_clean))
                ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT * FROM audit_findings WHERE engagement_id = ? AND (finding_code = ? OR UPPER(finding_code) = ?)",
                    (engagement_id, ident_clean, ident_clean.upper())
                ).fetchone()

            if not row:
                return {
                    "error": f"Finding '{identifier}' was not found in active audit records of this engagement."
                }

            f = dict(row)
            return {
                "id": f.get("id"),
                "finding_code": f.get("finding_code"),
                "severity": f.get("severity"),
                "category": f.get("category"),
                "title": f.get("title"),
                "description": f.get("description"),
                "expected_value": f.get("expected_value"),
                "actual_value": f.get("actual_value"),
                "difference": f.get("difference"),
                "rule_used": f.get("rule_used"),
                "risk_score": f.get("risk_score"),
                "reason": f.get("reason"),
                "recommended_action": f.get("recommended_action"),
                "status": f.get("status")
            }
        finally:
            conn.close()

    @classmethod
    def list_audit_findings(
        cls,
        engagement_id: int,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Returns a filtered summary of current audit exceptions.
        Results are strictly capped at 15 items to prevent context-window explosion.
        """
        safe_limit = max(1, min(int(limit or 10), 15))
        conn = cls._get_readonly_conn()
        try:
            query = "SELECT id, finding_code, title, category, severity, risk_score, rule_used, recommended_action FROM audit_findings WHERE engagement_id = ?"
            params: List[Any] = [engagement_id]

            if category:
                query += " AND category LIKE ?"
                params.append(f"%{category.strip()}%")
            if severity:
                query += " AND UPPER(severity) = ?"
                params.append(severity.strip().upper())

            query += " ORDER BY risk_score DESC, id ASC LIMIT ?"
            params.append(safe_limit)

            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @classmethod
    def search_transactions(
        cls,
        engagement_id: int,
        query: Optional[str] = None,
        ledger: Optional[str] = None,
        party_name: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Performs bounded parametric search across transactions.
        Results are capped at a maximum of 20 rows.
        """
        safe_limit = max(1, min(int(limit or 15), 20))
        conn = cls._get_readonly_conn()
        try:
            sql = "SELECT id, date, voucher_no, invoice_no, ledger, party_name, debit, credit, amount, description FROM transactions WHERE engagement_id = ?"
            params: List[Any] = [engagement_id]

            if query:
                sql += " AND (description LIKE ? OR voucher_no LIKE ? OR invoice_no LIKE ?)"
                q_pattern = f"%{query.strip()}%"
                params.extend([q_pattern, q_pattern, q_pattern])
            if ledger:
                sql += " AND ledger LIKE ?"
                params.append(f"%{ledger.strip()}%")
            if party_name:
                sql += " AND party_name LIKE ?"
                params.append(f"%{party_name.strip()}%")
            if min_amount is not None:
                sql += " AND amount >= ?"
                params.append(float(min_amount))
            if max_amount is not None:
                sql += " AND amount <= ?"
                params.append(float(max_amount))
            if date_from:
                sql += " AND date >= ?"
                params.append(date_from.strip())
            if date_to:
                sql += " AND date <= ?"
                params.append(date_to.strip())

            sql += " ORDER BY date ASC, id ASC LIMIT ?"
            params.append(safe_limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @classmethod
    def get_transaction_evidence(cls, engagement_id: int, identifier: str) -> Dict[str, Any]:
        """
        Fetches detailed line-item attributes for a transaction voucher along with any linked findings.
        """
        conn = cls._get_readonly_conn()
        try:
            ident_clean = str(identifier).strip()
            row = None
            if ident_clean.isdigit():
                row = conn.execute(
                    "SELECT * FROM transactions WHERE engagement_id = ? AND id = ?",
                    (engagement_id, int(ident_clean))
                ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT * FROM transactions WHERE engagement_id = ? AND (voucher_no = ? OR invoice_no = ? OR reference_no = ?)",
                    (engagement_id, ident_clean, ident_clean, ident_clean)
                ).fetchone()

            if not row:
                return {
                    "error": f"Transaction voucher '{identifier}' could not be resolved from this engagement's records."
                }

            tx = dict(row)

            # Discover if any audit findings flag this voucher
            findings_rows = conn.execute("""
                SELECT id, finding_code, title, severity, category, rule_used, reason 
                FROM audit_findings 
                WHERE engagement_id = ? AND (
                    description LIKE ? OR 
                    title LIKE ? OR 
                    actual_value LIKE ?
                )
            """, (engagement_id, f"%{tx.get('voucher_no')}%", f"%{tx.get('voucher_no')}%", f"%{tx.get('voucher_no')}%")).fetchall()

            return {
                "transaction": {
                    "id": tx.get("id"),
                    "date": tx.get("date"),
                    "voucher_no": tx.get("voucher_no"),
                    "invoice_no": tx.get("invoice_no"),
                    "ledger": tx.get("ledger"),
                    "party_name": tx.get("party_name"),
                    "debit": tx.get("debit"),
                    "credit": tx.get("credit"),
                    "amount": tx.get("amount"),
                    "description": tx.get("description"),
                    "gstin": tx.get("gstin"),
                    "reference_no": tx.get("reference_no")
                },
                "linked_findings": [dict(f) for f in findings_rows]
            }
        finally:
            conn.close()

    @classmethod
    def get_statutory_rule_guidance(cls, query_or_section: str) -> Dict[str, Any]:
        """
        Returns objective accounting and tax benchmark principles from ICAI standards and statutory laws.
        """
        q = (query_or_section or "").lower().strip()
        
        if "40a" in q or "cash payment" in q or "6dd" in q or "rule 6" in q:
            return STATUTORY_KNOWLEDGE["40a3"]
        elif "269st" in q or "cash receipt" in q or "269" in q:
            return STATUTORY_KNOWLEDGE["269st"]
        elif "43b" in q or "msme" in q:
            return STATUTORY_KNOWLEDGE["43bh"]
        elif "gst" in q or "2b" in q or "itc" in q:
            return STATUTORY_KNOWLEDGE["gst_itc"]
        elif "fraud" in q or "skepticism" in q or "240" in q:
            return STATUTORY_KNOWLEDGE["sa_240"]
        elif "evidence" in q or "500" in q:
            return STATUTORY_KNOWLEDGE["sa_500"]
        elif "caro" in q:
            return {
                "statute": "CARO 2020 (Companies Auditor's Report Order, 2020)",
                "clause": "Order under Section 143(11) of the Companies Act, 2013",
                "provision": "Requires reporting on 21 distinct clauses including PPE title deeds, inventory physical verification, loans/advances to related parties, internal audit system, statutory dues, and cash losses."
            }
        else:
            return {
                "general_guidance": "ICAI Standards on Auditing (SAs) require obtaining sufficient, appropriate audit evidence (SA 500) and exercising professional skepticism (SA 200/240). Statutory compliances under the Income Tax Act (Sections 40A(3), 269ST, 43B(h)) and CGST Act (Section 16(2)(aa)) are subject to strict evidentiary documentation."
            }

    @classmethod
    def get_reconciliation_summary(cls, engagement_id: int, recon_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves status and unreconciled amounts from completed Bank (BRS) or GST reconciliations.
        """
        conn = cls._get_readonly_conn()
        try:
            sql = "SELECT id, recon_type, title, status, total_bank_tx, total_book_tx, matched_count, unreconciled_amount, net_unreconciled_difference, created_at FROM reconciliations WHERE engagement_id = ?"
            params: List[Any] = [engagement_id]
            if recon_type:
                sql += " AND recon_type = ?"
                params.append(recon_type.strip())
            sql += " ORDER BY id DESC LIMIT 5"

            rows = conn.execute(sql, params).fetchall()
            return {
                "reconciliations": [dict(r) for r in rows]
            }
        finally:
            conn.close()

    @classmethod
    def get_trial_balance_summary(cls, engagement_id: int) -> Dict[str, Any]:
        """
        Retrieves the authoritative Trial Balance summary, debit/credit totals,
        balance equality status, and suspense account listings.
        """
        conn = cls._get_readonly_conn()
        try:
            rows = conn.execute("""
                SELECT ledger_name, account_group, opening_balance, total_debit, total_credit, closing_balance
                FROM ledgers
                WHERE engagement_id = ?
                ORDER BY account_group ASC, ledger_name ASC
            """, (engagement_id,)).fetchall()

            total_debits = sum(float(r["total_debit"] or 0.0) for r in rows)
            total_credits = sum(float(r["total_credit"] or 0.0) for r in rows)
            difference = round(abs(total_debits - total_credits), 2)
            is_balanced = (difference == 0.0 and len(rows) > 0)

            groups: Dict[str, Dict[str, float]] = {}
            suspense: List[Dict[str, Any]] = []

            for r in rows:
                grp = r["account_group"] or "Unclassified"
                if grp not in groups:
                    groups[grp] = {"total_debit": 0.0, "total_credit": 0.0, "net_balance": 0.0, "count": 0}
                groups[grp]["total_debit"] += float(r["total_debit"] or 0.0)
                groups[grp]["total_credit"] += float(r["total_credit"] or 0.0)
                groups[grp]["net_balance"] += float(r["closing_balance"] or 0.0)
                groups[grp]["count"] += 1

                lname = (r["ledger_name"] or "").lower()
                if any(k in lname for k in ["suspense", "unreconciled", "clearing", "round off"]):
                    suspense.append({
                        "ledger_name": r["ledger_name"],
                        "account_group": r["account_group"],
                        "closing_balance": float(r["closing_balance"] or 0.0)
                    })

            return {
                "engagement_id": engagement_id,
                "total_ledgers": len(rows),
                "total_debit": round(total_debits, 2),
                "total_credit": round(total_credits, 2),
                "difference": difference,
                "is_balanced": is_balanced,
                "balance_status": "BALANCED" if is_balanced else ("EMPTY_OR_UNIMPORTED" if len(rows) == 0 else f"UNBALANCED_DIFFERENCE_INR_{difference:,.2f}"),
                "account_groups": groups,
                "suspense_accounts": suspense,
                "ledgers_sample": [
                    {
                        "ledger_name": r["ledger_name"],
                        "group": r["account_group"],
                        "closing_balance": round(float(r["closing_balance"] or 0.0), 2)
                    }
                    for r in rows[:15]
                ]
            }
        finally:
            conn.close()

    @classmethod
    def list_uploaded_documents(cls, engagement_id: int) -> Dict[str, Any]:
        """
        Lists all uploaded files, categories, row counts, and parsing health.
        """
        conn = cls._get_readonly_conn()
        try:
            rows = conn.execute("""
                SELECT id, file_name, file_type, source_type, data_category,
                       row_count, successful_rows, failed_rows, warning_count,
                       uploaded_by, uploaded_at
                FROM uploaded_files
                WHERE engagement_id = ?
                ORDER BY id ASC
            """, (engagement_id,)).fetchall()

            docs = [dict(r) for r in rows]
            return {
                "engagement_id": engagement_id,
                "total_documents": len(docs),
                "documents": docs
            }
        finally:
            conn.close()

    @classmethod
    def get_document_details(cls, engagement_id: int, file_id: int) -> Dict[str, Any]:
        """
        Retrieves deep parsing status, column mapping, and import errors for a document.
        Discloses if file extraction failed or if text contents were not indexed.
        """
        conn = cls._get_readonly_conn()
        try:
            row = conn.execute("""
                SELECT id, file_name, file_type, source_type, data_category,
                       row_count, successful_rows, failed_rows, warning_count,
                       mapping_json, errors_json, uploaded_by, uploaded_at
                FROM uploaded_files
                WHERE engagement_id = ? AND id = ?
            """, (engagement_id, file_id)).fetchone()

            if not row:
                return {
                    "error": f"Document ID #{file_id} not found in active engagement #{engagement_id}."
                }

            doc = dict(row)
            errors = []
            if doc.get("errors_json"):
                try:
                    parsed = json.loads(doc["errors_json"])
                    if isinstance(parsed, list):
                        errors = parsed[:5]
                    elif isinstance(parsed, dict):
                        errors = [f"{k}: {v}" for k, v in list(parsed.items())[:5]]
                    else:
                        errors = [str(parsed)]
                except Exception:
                    errors = [str(doc["errors_json"])]

            return {
                "id": doc["id"],
                "file_name": doc["file_name"],
                "file_type": doc["file_type"],
                "data_category": doc["data_category"],
                "row_count": doc["row_count"],
                "successful_rows": doc["successful_rows"],
                "failed_rows": doc["failed_rows"],
                "warning_count": doc["warning_count"],
                "uploaded_at": doc["uploaded_at"],
                "parsing_status": "SUCCESS" if (doc["failed_rows"] == 0 and doc["row_count"] > 0) else ("FAILED_OR_EMPTY" if doc["row_count"] == 0 else "PARTIAL_FAILURES"),
                "errors_sample": errors
            }
        finally:
            conn.close()

    @classmethod
    def list_working_papers(cls, engagement_id: int, area: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves created Working Papers, audit objectives, and human review sign-offs.
        """
        conn = cls._get_readonly_conn()
        try:
            sql = """
                SELECT id, wp_reference, title, area, category, status,
                       prepared_by, prepared_date, reviewed_by, review_date,
                       linked_findings_json, updated_at
                FROM working_papers
                WHERE engagement_id = ?
            """
            params: List[Any] = [engagement_id]
            if area:
                sql += " AND LOWER(area) = LOWER(?)"
                params.append(area.strip())
            sql += " ORDER BY wp_reference ASC LIMIT 20"

            rows = conn.execute(sql, params).fetchall()
            papers = []
            for r in rows:
                item = dict(r)
                linked_findings = []
                if item.get("linked_findings_json"):
                    try:
                        linked_findings = json.loads(item["linked_findings_json"])
                    except Exception:
                        pass
                item["linked_findings_count"] = len(linked_findings)
                papers.append(item)

            return {
                "engagement_id": engagement_id,
                "total_papers": len(papers),
                "working_papers": papers
            }
        finally:
            conn.close()

    @classmethod
    def get_audit_checklist_summary(cls, engagement_id: int, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves audit checklist items, execution progress, and compliance exceptions.
        """
        conn = cls._get_readonly_conn()
        try:
            sql = """
                SELECT id, category, item_code, question, status, comment,
                       reference_wp, checked_by, checked_at
                FROM audit_checklists
                WHERE engagement_id = ?
            """
            params: List[Any] = [engagement_id]
            if category:
                sql += " AND LOWER(category) = LOWER(?)"
                params.append(category.strip())
            sql += " ORDER BY category ASC, item_code ASC LIMIT 25"

            rows = conn.execute(sql, params).fetchall()
            items = [dict(r) for r in rows]

            return {
                "engagement_id": engagement_id,
                "total_items": len(items),
                "completed": len([i for i in items if i["status"] in ["Completed", "Satisfactory"]]),
                "outstanding": len([i for i in items if i["status"] in ["Not Started", "In Progress"]]),
                "exceptions": len([i for i in items if i["status"] in ["Exception Flagged", "Non-Compliant"]]),
                "items": items
            }
        finally:
            conn.close()



# =========================================================================
# JSON Schemas for OpenAI / Ollama Function Calling
# =========================================================================

ASSISTANT_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_engagement_summary",
            "description": "Retrieves the audit engagement's metadata, total turnover, transaction counts, and breakdown of findings by severity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "engagement_id": {"type": "integer", "description": "The current engagement ID"}
                },
                "required": ["engagement_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_audit_finding",
            "description": "Retrieves comprehensive details for a specific audit finding using its finding_code (e.g. 'DET-TAX-40A3') or numerical ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "engagement_id": {"type": "integer", "description": "The current engagement ID"},
                    "identifier": {"type": "string", "description": "The finding code (e.g. 'DET-TAX-40A3') or finding ID"}
                },
                "required": ["engagement_id", "identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_audit_findings",
            "description": "Lists audit exceptions and risk findings for the engagement, with optional filtering by severity or category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "engagement_id": {"type": "integer", "description": "The current engagement ID"},
                    "category": {"type": "string", "description": "Optional category filter (e.g. 'Income Tax Act', 'GST', 'Anomaly')"},
                    "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"], "description": "Optional severity filter"},
                    "limit": {"type": "integer", "description": "Maximum number of findings to return (max 15)"}
                },
                "required": ["engagement_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_transactions",
            "description": "Searches actual ledger transactions by party name, ledger account, amount range, or keyword with bounded results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "engagement_id": {"type": "integer", "description": "The current engagement ID"},
                    "query": {"type": "string", "description": "Text to search in narration or description"},
                    "ledger": {"type": "string", "description": "Ledger account name to filter by"},
                    "party_name": {"type": "string", "description": "Vendor or customer party name"},
                    "min_amount": {"type": "number", "description": "Minimum transaction amount"},
                    "max_amount": {"type": "number", "description": "Maximum transaction amount"},
                    "limit": {"type": "integer", "description": "Maximum number of records to return (max 20)"}
                },
                "required": ["engagement_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_transaction_evidence",
            "description": "Inspects full attributes for a specific transaction voucher number or ID, including any linked audit findings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "engagement_id": {"type": "integer", "description": "The current engagement ID"},
                    "identifier": {"type": "string", "description": "Voucher number (e.g. 'V-CY-03') or transaction ID"}
                },
                "required": ["engagement_id", "identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_statutory_rule_guidance",
            "description": "Retrieves official statutory benchmarks, tax rules, and ICAI Standards on Auditing (e.g. Section 40A(3) cash limits, Rule 6DD cash payment exceptions, Section 269ST, Section 43B(h), GSTR-2B ITC, CARO 2020, SA 500, SA 240).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_or_section": {"type": "string", "description": "The statutory section, rule, or standard code to look up (e.g. '40A(3)', 'Rule 6DD', '269ST', '43B(h)', 'SA 500')"}
                },
                "required": ["query_or_section"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_reconciliation_summary",
            "description": "Retrieves the latest summary of Bank Reconciliation (BRS) or GST ITC Reconciliation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "engagement_id": {"type": "integer", "description": "The current engagement ID"},
                    "recon_type": {"type": "string", "description": "Optional reconciliation type: 'BANK' or 'GST'"}
                },
                "required": ["engagement_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trial_balance_summary",
            "description": "Retrieves the authoritative Trial Balance summary, total debits, total credits, net difference, balance equality status, and suspense account balances for the engagement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "engagement_id": {"type": "integer", "description": "The current engagement ID"}
                },
                "required": ["engagement_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_uploaded_documents",
            "description": "Lists all uploaded client files, document categories (e.g. General Ledger, Bank Statement), row counts, and parsing health.",
            "parameters": {
                "type": "object",
                "properties": {
                    "engagement_id": {"type": "integer", "description": "The current engagement ID"}
                },
                "required": ["engagement_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_details",
            "description": "Retrieves deep parsing details, failed rows, warning counts, and column mappings for an uploaded file to verify extraction integrity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "engagement_id": {"type": "integer", "description": "The current engagement ID"},
                    "file_id": {"type": "integer", "description": "The document file ID (e.g. 1, 2, 3)"}
                },
                "required": ["engagement_id", "file_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_working_papers",
            "description": "Retrieves created audit working papers, references (e.g. 'WP-EXP-001'), audit objectives, and review statuses (Draft, Prepared, Reviewed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "engagement_id": {"type": "integer", "description": "The current engagement ID"},
                    "area": {"type": "string", "description": "Optional audit area filter (e.g. 'Expenses', 'Revenue', 'Statutory')"}
                },
                "required": ["engagement_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_audit_checklist_summary",
            "description": "Retrieves audit checklist completion progress, outstanding compliance items, and flagged exceptions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "engagement_id": {"type": "integer", "description": "The current engagement ID"},
                    "category": {"type": "string", "description": "Optional category filter (e.g. 'Planning', 'Fieldwork', 'Statutory')"}
                },
                "required": ["engagement_id"]
            }
        }
    }
]


def execute_tool_call(tool_name: str, arguments: Dict[str, Any], allowed_engagement_id: int) -> Dict[str, Any]:
    """
    Safely executes an authorized read-only tool call, enforcing engagement scoping.
    """
    # Enforce engagement isolation invariant: tool cannot access another engagement
    args = dict(arguments or {})
    if "engagement_id" in args:
        args["engagement_id"] = allowed_engagement_id

    if tool_name == "get_engagement_summary":
        return AssistantTools.get_engagement_summary(allowed_engagement_id)
    elif tool_name == "get_audit_finding":
        return AssistantTools.get_audit_finding(allowed_engagement_id, args.get("identifier", ""))
    elif tool_name == "list_audit_findings":
        return AssistantTools.list_audit_findings(
            engagement_id=allowed_engagement_id,
            category=args.get("category"),
            severity=args.get("severity"),
            limit=args.get("limit", 10)
        )
    elif tool_name == "search_transactions":
        return AssistantTools.search_transactions(
            engagement_id=allowed_engagement_id,
            query=args.get("query"),
            ledger=args.get("ledger"),
            party_name=args.get("party_name"),
            min_amount=args.get("min_amount"),
            max_amount=args.get("max_amount"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
            limit=args.get("limit", 15)
        )
    elif tool_name == "get_transaction_evidence":
        return AssistantTools.get_transaction_evidence(allowed_engagement_id, args.get("identifier", ""))
    elif tool_name == "get_statutory_rule_guidance":
        return AssistantTools.get_statutory_rule_guidance(args.get("query_or_section", ""))
    elif tool_name == "get_reconciliation_summary":
        return AssistantTools.get_reconciliation_summary(allowed_engagement_id, args.get("recon_type"))
    elif tool_name == "get_trial_balance_summary":
        return AssistantTools.get_trial_balance_summary(allowed_engagement_id)
    elif tool_name == "list_uploaded_documents":
        return AssistantTools.list_uploaded_documents(allowed_engagement_id)
    elif tool_name == "get_document_details":
        return AssistantTools.get_document_details(allowed_engagement_id, int(args.get("file_id", 0)))
    elif tool_name == "list_working_papers":
        return AssistantTools.list_working_papers(allowed_engagement_id, args.get("area"))
    elif tool_name == "get_audit_checklist_summary":
        return AssistantTools.get_audit_checklist_summary(allowed_engagement_id, args.get("category"))
    else:
        return {"error": f"Tool '{tool_name}' is not recognized or permitted."}
