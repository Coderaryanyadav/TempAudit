import json
from datetime import datetime
from typing import List, Dict, Any
from backend.app.audit_engine.deterministic import DeterministicAuditEngine
from backend.app.audit_engine.statistical import StatisticalAuditEngine
from backend.app.audit_engine.local_ai import LocalAIAuditAssistant
from backend.app.database import get_db_connection

class HybridAuditEngine:
    def __init__(self, engagement_id: int):
        self.engagement_id = engagement_id

    def execute_audit(self) -> Dict[str, Any]:
        conn = get_db_connection()
        eng_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (self.engagement_id,)).fetchone()
        if not eng_row:
            conn.close()
            raise ValueError(f"Engagement {self.engagement_id} not found")
        
        engagement = dict(eng_row)
        tx_rows = conn.execute("SELECT * FROM transactions WHERE engagement_id = ?", (self.engagement_id,)).fetchall()
        transactions = [dict(t) for t in tx_rows]

        if not transactions:
            conn.close()
            return {
                "status": "warning",
                "message": "No transactions imported for this engagement yet.",
                "total_transactions": 0,
                "findings_count": 0,
                "findings": []
            }

        # 1. Run Deterministic Rule Engine
        det_engine = DeterministicAuditEngine(transactions, engagement.get("financial_year", "2024-25"))
        det_findings = det_engine.run_all_checks()

        # 2. Run Statistical / Machine Learning Engine
        stat_engine = StatisticalAuditEngine(transactions)
        stat_results = stat_engine.run_all_checks()
        stat_findings = stat_results.get("findings", [])

        all_findings = det_findings + stat_findings

        # Clear existing unreviewed findings for this engagement to prevent duplicate accumulation
        conn.execute("DELETE FROM audit_findings WHERE engagement_id = ? AND status = 'Open'", (self.engagement_id,))

        saved_findings = []
        now_str = datetime.now().isoformat()

        for f in all_findings:
            cursor = conn.execute("""
            INSERT INTO audit_findings (
                engagement_id, finding_code, category, severity, risk_score,
                title, description, affected_records_json, expected_value,
                actual_value, difference, reason, evidence_json, rule_used,
                engine_type, ai_explanation, recommended_action, status,
                auditor_comment, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.engagement_id,
                f.get("finding_code", "GEN-01"),
                f.get("category", "General"),
                f.get("severity", "MEDIUM"),
                f.get("risk_score", 5.0),
                f.get("title", ""),
                f.get("description", ""),
                json.dumps(f.get("affected_records", [])),
                f.get("expected_value", ""),
                f.get("actual_value", ""),
                f.get("difference", ""),
                f.get("reason", ""),
                json.dumps(f.get("evidence", {})),
                f.get("rule_used", ""),
                f.get("engine_type", "DETERMINISTIC"),
                f.get("ai_explanation", ""),
                f.get("recommended_action", ""),
                "Open",
                "",
                now_str
            ))
            f_id = cursor.lastrowid
            f_copy = f.copy()
            f_copy["id"] = f_id
            saved_findings.append(f_copy)

        # Log audit action
        from backend.app.utils.audit_logger import log_audit_event
        log_audit_event(
            conn=conn,
            action="RUN_HYBRID_AUDIT",
            module="Hybrid Audit Engine",
            record_id=self.engagement_id,
            user="system_engine",
            engagement_id=self.engagement_id,
            details=f"Executed hybrid audit engine on {len(transactions)} transactions. Generated {len(saved_findings)} findings.",
            timestamp=now_str
        )

        conn.commit()

        # 3. Generate Local AI Summary
        ai_assistant = LocalAIAuditAssistant(engagement, transactions, saved_findings)
        ai_summary = ai_assistant.generate_audit_summary_narrative()

        conn.close()

        return {
            "status": "success",
            "engagement_id": self.engagement_id,
            "total_transactions": len(transactions),
            "findings_count": len(saved_findings),
            "findings": saved_findings,
            "benford_analysis": stat_results.get("benford_analysis"),
            "ml_summary": stat_results.get("ml_summary"),
            "zscore_summary": stat_results.get("zscore_summary"),
            "weekend_summary": stat_results.get("weekend_summary"),
            "ai_summary": ai_summary
        }
