import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from backend.app.database import get_db_connection

logger = logging.getLogger(__name__)

SEVERITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

SEVERITY_BASE_WEIGHTS = {
    "CRITICAL": 7.0,
    "HIGH": 5.0,
    "MEDIUM": 3.0,
    "LOW": 1.5
}

class CentralizedFindingsEngine:
    """
    Centralized Audit Risk & Findings Engine for FinAuditPro.
    Aggregates audit exceptions across all audit modules and computes
    100% explainable, deterministic risk scores based on explicit financial & audit drivers.
    """

    @staticmethod
    def calculate_deterministic_risk_score(
        severity: str,
        amount: float = 0.0,
        materiality_threshold: float = 50000.0,
        frequency: int = 1,
        repetition_count: int = 1,
        data_quality_issue: bool = False,
        data_quality_details: str = "",
        difference_pct: float = 0.0,
        historical_repeat: bool = False,
        historical_details: str = "",
        affected_records_count: int = 1
    ) -> Tuple[float, Dict[str, Any], str]:
        """
        Calculates an explainable, deterministic risk score on a 1.0 to 10.0 scale.
        
        Deterministic Factors Evaluated:
        1. Base Severity Weight (LOW=1.5, MEDIUM=3.0, HIGH=5.0, CRITICAL=7.0)
        2. Amount vs Materiality Ratio (Up to +2.0)
        3. Frequency / Repetition (Up to +1.0)
        4. Number of Affected Records (Up to +1.0)
        5. Difference Percentage (Up to +1.0)
        6. Data Quality Impact (+0.5 if compromised)
        7. Historical Behavior / Prior Pattern (+0.5 if recurring)
        
        Returns:
            (final_risk_score, risk_factors_dict, ai_explanation)
        """
        severity_clean = str(severity).upper() if severity else "MEDIUM"
        if severity_clean not in SEVERITY_BASE_WEIGHTS:
            severity_clean = "MEDIUM"

        base_weight = SEVERITY_BASE_WEIGHTS[severity_clean]

        # 1. Amount vs Materiality Factor
        amount_impact = 0.0
        amount_ratio = 0.0
        mat_thresh = max(1.0, float(materiality_threshold or 50000.0))
        amt_val = abs(float(amount or 0.0))

        if amt_val > 0:
            amount_ratio = amt_val / mat_thresh
            if amount_ratio >= 5.0:
                amount_impact = 2.0
            elif amount_ratio >= 2.0:
                amount_impact = 1.5
            elif amount_ratio >= 1.0:
                amount_impact = 1.0
            elif amount_ratio >= 0.5:
                amount_impact = 0.6
            elif amount_ratio >= 0.1:
                amount_impact = 0.3
            else:
                amount_impact = 0.1

        # 2. Frequency / Repetition Factor
        effective_freq = max(1, int(frequency or 1), int(repetition_count or 1))
        freq_impact = 0.0
        if effective_freq >= 10:
            freq_impact = 1.0
        elif effective_freq >= 5:
            freq_impact = 0.7
        elif effective_freq >= 2:
            freq_impact = 0.4

        # 3. Affected Records Count Factor
        aff_count = max(1, int(affected_records_count or 1))
        records_impact = 0.0
        if aff_count >= 10:
            records_impact = 1.0
        elif aff_count >= 5:
            records_impact = 0.6
        elif aff_count >= 2:
            records_impact = 0.3

        # 4. Difference Percentage Factor
        diff_val = abs(float(difference_pct or 0.0))
        diff_impact = 0.0
        if diff_val >= 50.0:
            diff_impact = 1.0
        elif diff_val >= 25.0:
            diff_impact = 0.7
        elif diff_val >= 10.0:
            diff_impact = 0.4
        elif diff_val >= 5.0:
            diff_impact = 0.2

        # 5. Data Quality Factor
        quality_impact = 0.5 if data_quality_issue else 0.0

        # 6. Historical Behavior / Prior Period Factor
        history_impact = 0.5 if historical_repeat else 0.0

        # Raw Score Sum
        raw_score = (
            base_weight +
            amount_impact +
            freq_impact +
            records_impact +
            diff_impact +
            quality_impact +
            history_impact
        )

        final_score = round(min(10.0, max(1.0, raw_score)), 1)

        # Build Explainable Factor Breakdown Object
        factors_dict = {
            "base_severity": severity_clean,
            "base_weight": base_weight,
            "amount": amt_val,
            "materiality_threshold": mat_thresh,
            "amount_to_materiality_ratio": round(amount_ratio, 2),
            "amount_impact": amount_impact,
            "frequency": effective_freq,
            "repetition_impact": freq_impact,
            "affected_records_count": aff_count,
            "records_impact": records_impact,
            "difference_pct": round(diff_val, 2),
            "difference_impact": diff_impact,
            "data_quality_issue": bool(data_quality_issue),
            "data_quality_details": data_quality_details or ("None identified" if not data_quality_issue else "Data anomaly noted"),
            "data_quality_impact": quality_impact,
            "historical_repeat": bool(historical_repeat),
            "historical_details": historical_details or ("No prior recurring history" if not historical_repeat else "Recurring historical behavior noted"),
            "historical_impact": history_impact,
            "raw_calculated_score": round(raw_score, 2),
            "final_risk_score": final_score,
            "equation": (
                f"Base({base_weight}) + Amount({amount_impact}) + Frequency({freq_impact}) + "
                f"Records({records_impact}) + Diff%({diff_impact}) + Quality({quality_impact}) + "
                f"History({history_impact}) = {final_score}/10.0"
            )
        }

        # Build Plain-English AI Explanation
        explanation_lines = [
            f"Deterministic Risk Score: {final_score}/10.0 ({severity_clean} Severity Tier).",
            f"1. Base Factor: Initial baseline of {base_weight} based on {severity_clean} statutory/audit severity classification.",
        ]
        if amt_val > 0:
            explanation_lines.append(
                f"2. Materiality & Exposure: Cumulative financial exposure of ₹{amt_val:,.2f} represents {amount_ratio:.1f}x of the materiality threshold (₹{mat_thresh:,.2f}), adding +{amount_impact} to the risk score."
            )
        else:
            explanation_lines.append(
                f"2. Materiality & Exposure: No direct transactional financial difference identified (+0.0)."
            )

        if effective_freq > 1 or aff_count > 1:
            explanation_lines.append(
                f"3. Frequency & Volume: Identified across {effective_freq} instances and {aff_count} affected records (frequency impact +{freq_impact}, record impact +{records_impact})."
            )

        if diff_val > 0:
            explanation_lines.append(
                f"4. Variance/Discrepancy: Variance of {diff_val:.1f}% identified (+{diff_impact})."
            )

        if data_quality_issue:
            explanation_lines.append(
                f"5. Data Quality: Data inconsistency or formatting irregularity detected ({data_quality_details}), adding +{quality_impact} risk penalty."
            )

        if historical_repeat:
            explanation_lines.append(
                f"6. Historical Pattern: Recurring behavior or repeat discrepancy observed (+{history_impact})."
            )

        ai_explanation = "\n".join(explanation_lines)
        return final_score, factors_dict, ai_explanation

    @classmethod
    def sync_all_engagement_findings(cls, engagement_id: int) -> Dict[str, Any]:
        """
        Gathers, standardizes, evaluates, and synchronizes exceptions from all audit engines
        into the centralized `audit_findings` repository.
        """
        conn = get_db_connection()
        eng_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
        if not eng_row:
            conn.close()
            raise ValueError(f"Engagement #{engagement_id} not found.")

        eng_dict = dict(eng_row)
        materiality_thresh = float(eng_dict.get("materiality_threshold") or 50000.0)

        # Existing findings map: finding_code -> row
        existing_findings_rows = conn.execute(
            "SELECT * FROM audit_findings WHERE engagement_id = ?",
            (engagement_id,)
        ).fetchall()
        existing_map = {r["finding_code"]: dict(r) for r in existing_findings_rows}

        collected_findings: List[Dict[str, Any]] = []

        # 1. Collect Tax & Statutory Rule Exceptions + Statistical Anomalies
        collected_findings.extend(cls._collect_statutory_and_statistical_findings(conn, engagement_id, materiality_thresh))

        # 2. Collect Duplicate & Sequence Gap Exceptions
        collected_findings.extend(cls._collect_duplicate_sequence_findings(conn, engagement_id, materiality_thresh))

        # 3. Collect Hybrid Anomaly Exceptions (L1 Rules, L2 Statistical, L3 ML Isolation Forest)
        collected_findings.extend(cls._collect_hybrid_anomaly_findings(conn, engagement_id, materiality_thresh))

        # 4. Collect YoY Variance Findings
        collected_findings.extend(cls._collect_yoy_variance_findings(conn, engagement_id, materiality_thresh))

        # 5. Collect Trial Balance Exceptions (Unbalanced TB, Non-zero Suspense, Negative Accounts)
        collected_findings.extend(cls._collect_trial_balance_findings(conn, engagement_id, materiality_thresh))

        # 6. Collect Bank Reconciliation Exceptions (Unreconciled BRS, Stale Cheques, Amount Differences)
        collected_findings.extend(cls._collect_bank_recon_findings(conn, engagement_id, materiality_thresh))

        # 7. Collect GST / Sales-Purchase Reconciliation Exceptions
        collected_findings.extend(cls._collect_gst_recon_findings(conn, engagement_id, materiality_thresh))

        now_str = datetime.now().isoformat()
        inserted_count = 0
        updated_count = 0
        module_counts: Dict[str, int] = {}
        severity_counts: Dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}

        for finding in collected_findings:
            code = finding["finding_code"]
            module_name = finding.get("module", "General")
            severity_name = finding.get("severity", "MEDIUM").upper()
            module_counts[module_name] = module_counts.get(module_name, 0) + 1
            severity_counts[severity_name] = severity_counts.get(severity_name, 0) + 1

            # Prepare JSON fields
            affected_json = json.dumps(finding.get("affected_records", []))
            evidence_json = json.dumps(finding.get("evidence", {}))
            risk_factors_json = json.dumps(finding.get("risk_factors", {}))

            if code in existing_map:
                # Update finding while preserving existing auditor review, comment, and status
                curr = existing_map[code]
                status_to_keep = curr.get("status") or "Open"
                comment_to_keep = curr.get("auditor_comment")
                reviewed_at_to_keep = curr.get("reviewed_at")
                reviewed_by_to_keep = curr.get("reviewed_by")

                conn.execute("""
                    UPDATE audit_findings
                    SET module = ?, category = ?, severity = ?, risk_score = ?, title = ?, description = ?,
                        affected_records_json = ?, expected_value = ?, actual_value = ?, difference = ?,
                        reason = ?, evidence_json = ?, rule_used = ?, engine_type = ?, risk_factors_json = ?,
                        ai_explanation = ?, recommended_action = ?
                    WHERE id = ?
                """, (
                    module_name,
                    finding.get("category", "General Audit"),
                    severity_name,
                    finding.get("risk_score", 5.0),
                    finding.get("title", "Audit Finding"),
                    finding.get("description", ""),
                    affected_json,
                    str(finding.get("expected_value") or ""),
                    str(finding.get("actual_value") or ""),
                    str(finding.get("difference") or ""),
                    finding.get("reason", ""),
                    evidence_json,
                    finding.get("rule_used", ""),
                    finding.get("engine_type", "DETERMINISTIC"),
                    risk_factors_json,
                    finding.get("ai_explanation", ""),
                    finding.get("recommended_action", ""),
                    curr["id"]
                ))
                updated_count += 1
            else:
                # Insert fresh finding
                conn.execute("""
                    INSERT INTO audit_findings (
                        engagement_id, finding_code, module, category, severity, risk_score,
                        title, description, affected_records_json, expected_value, actual_value,
                        difference, reason, evidence_json, rule_used, engine_type, risk_factors_json,
                        ai_explanation, recommended_action, status, auditor_comment, reviewed_at,
                        reviewed_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', NULL, NULL, NULL, ?)
                """, (
                    engagement_id,
                    code,
                    module_name,
                    finding.get("category", "General Audit"),
                    severity_name,
                    finding.get("risk_score", 5.0),
                    finding.get("title", "Audit Finding"),
                    finding.get("description", ""),
                    affected_json,
                    str(finding.get("expected_value") or ""),
                    str(finding.get("actual_value") or ""),
                    str(finding.get("difference") or ""),
                    finding.get("reason", ""),
                    evidence_json,
                    finding.get("rule_used", ""),
                    finding.get("engine_type", "DETERMINISTIC"),
                    risk_factors_json,
                    finding.get("ai_explanation", ""),
                    finding.get("recommended_action", ""),
                    now_str
                ))
                inserted_count += 1

        conn.commit()
        conn.close()

        return {
            "engagement_id": engagement_id,
            "total_collected": len(collected_findings),
            "new_findings_created": inserted_count,
            "existing_findings_updated": updated_count,
            "module_counts": module_counts,
            "severity_counts": severity_counts,
            "synced_at": now_str
        }

    # =========================================================================
    # Collector Methods for Each Audit Subsystem
    # =========================================================================

    @classmethod
    def _collect_statutory_and_statistical_findings(
        cls, conn, engagement_id: int, materiality_thresh: float
    ) -> List[Dict[str, Any]]:
        findings = []
        try:
            from backend.app.audit_engine.deterministic import DeterministicAuditEngine
            from backend.app.audit_engine.statistical import StatisticalAuditEngine

            eng_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
            fy = eng_row["financial_year"] if eng_row and "financial_year" in eng_row.keys() else "2024-25"
            tx_rows = conn.execute("SELECT * FROM transactions WHERE engagement_id = ?", (engagement_id,)).fetchall()
            transactions = [dict(t) for t in tx_rows]

            if not transactions:
                return findings

            det_engine = DeterministicAuditEngine(transactions, fy)
            det_results = det_engine.run_all_checks() or []

            stat_engine = StatisticalAuditEngine(transactions)
            stat_res_obj = stat_engine.run_all_checks() or {}
            stat_results = stat_res_obj.get("findings", []) if isinstance(stat_res_obj, dict) else []

            combined = det_results + stat_results
            for item in combined:
                code = item.get("finding_code") or f"FIND-TAX-{abs(hash(item.get('title', ''))) % 100000:05d}"
                sev = str(item.get("severity") or "HIGH").upper()
                amount_val = 0.0

                # Extract amount from evidence or actual_value
                ev = item.get("evidence") or {}
                if isinstance(ev, dict):
                    amount_val = float(ev.get("total_amount") or ev.get("amount") or ev.get("sum_amount") or 0.0)
                if not amount_val and item.get("actual_value"):
                    try:
                        amount_val = float(str(item["actual_value"]).replace(",", "").replace("₹", "").strip())
                    except Exception:
                        amount_val = 0.0

                aff_records = item.get("affected_records") or []
                aff_count = len(aff_records)

                data_quality = ("GSTIN" in code) or ("GST" in item.get("title", "").upper())
                hist_repeat = "Round" in item.get("title", "") or "Benford" in item.get("title", "")

                score, factors, explanation = cls.calculate_deterministic_risk_score(
                    severity=sev,
                    amount=amount_val,
                    materiality_threshold=materiality_thresh,
                    frequency=aff_count,
                    repetition_count=aff_count,
                    data_quality_issue=data_quality,
                    data_quality_details="Tax compliance format error" if data_quality else "",
                    difference_pct=0.0,
                    historical_repeat=hist_repeat,
                    historical_details="Recurring statistical distribution anomaly" if hist_repeat else "",
                    affected_records_count=aff_count
                )

                findings.append({
                    "finding_code": code,
                    "module": "Statutory & Tax Rules",
                    "category": item.get("category", "Statutory Compliance"),
                    "severity": sev,
                    "risk_score": score,
                    "title": item.get("title", "Statutory Exception"),
                    "description": item.get("description", ""),
                    "affected_records": aff_records,
                    "expected_value": item.get("expected_value", ""),
                    "actual_value": item.get("actual_value", ""),
                    "difference": item.get("difference", ""),
                    "reason": item.get("reason", ""),
                    "evidence": ev,
                    "rule_used": item.get("rule_used", "Statutory Rule Engine"),
                    "engine_type": item.get("engine_type", "DETERMINISTIC"),
                    "risk_factors": factors,
                    "ai_explanation": explanation + ("\n\n" + item.get("ai_explanation", "") if item.get("ai_explanation") else ""),
                    "recommended_action": item.get("recommended_action") or "Perform substantive testing and obtain management representation."
                })
        except Exception as e:
            logger.warning(f"Error collecting statutory findings: {e}")
        return findings

    @classmethod
    def _collect_duplicate_sequence_findings(
        cls, conn, engagement_id: int, materiality_thresh: float
    ) -> List[Dict[str, Any]]:
        findings = []
        try:
            from backend.app.services.duplicate_missing_detector import detect_duplicates_and_gaps
            dup_report = detect_duplicates_and_gaps(engagement_id)

            # Exact duplicates
            for grp in dup_report.get("duplicate_groups", []):
                grp_id = grp.get("group_code", "DUP-EXACT")
                code = f"FIND-{grp_id.replace('#', '').replace(' ', '-')}"
                amt = float(grp.get("amount") or 0.0)
                tx_list = grp.get("transactions", [])
                tx_ids = [t.get("id") for t in tx_list if t.get("id")]
                repetition = max(1, len(tx_list))

                score, factors, explanation = cls.calculate_deterministic_risk_score(
                    severity="HIGH",
                    amount=amt * max(1, repetition - 1),
                    materiality_threshold=materiality_thresh,
                    frequency=repetition,
                    repetition_count=repetition,
                    data_quality_issue=True,
                    data_quality_details="Identical transaction duplication",
                    difference_pct=100.0,
                    historical_repeat=False,
                    affected_records_count=len(tx_ids)
                )

                findings.append({
                    "finding_code": code,
                    "module": "Duplicate & Sequence Engine",
                    "category": "Duplicate Transactions",
                    "severity": "HIGH",
                    "risk_score": score,
                    "title": f"Duplicate Group {grp_id} ({grp.get('reason', 'Identical records')})",
                    "description": f"Multiple records share identical invoice/voucher/party details for ₹{amt:,.2f}.",
                    "affected_records": tx_ids,
                    "expected_value": "Single unique entry",
                    "actual_value": f"{len(tx_list)} duplicate occurrences",
                    "difference": f"₹{(amt * (len(tx_list) - 1)):,.2f} redundant exposure",
                    "reason": grp.get("reason", "Exact match across core transaction attributes"),
                    "evidence": grp,
                    "rule_used": "Exact Duplicate Verification Rule",
                    "engine_type": "DETERMINISTIC",
                    "risk_factors": factors,
                    "ai_explanation": explanation,
                    "recommended_action": "Verify supporting invoices, bank debit advice, and cancel redundant voucher entries if duplicate."
                })

            # Fuzzy duplicates
            for grp in dup_report.get("fuzzy_duplicate_groups", []):
                grp_id = grp.get("group_code", "DUP-FUZZY")
                code = f"FIND-FUZ-{grp_id.replace('#', '').replace(' ', '-')}"
                amt = float(grp.get("amount") or 0.0)
                sim_pct = float(grp.get("similarity_percentage") or 85.0)
                tx_list = grp.get("transactions", [])
                tx_ids = [t.get("id") for t in tx_list if t.get("id")]

                score, factors, explanation = cls.calculate_deterministic_risk_score(
                    severity="MEDIUM",
                    amount=amt,
                    materiality_threshold=materiality_thresh,
                    frequency=len(tx_list),
                    repetition_count=len(tx_list),
                    data_quality_issue=True,
                    data_quality_details=f"Fuzzy match similarity: {sim_pct}%",
                    difference_pct=sim_pct,
                    historical_repeat=False,
                    affected_records_count=len(tx_ids)
                )

                findings.append({
                    "finding_code": code,
                    "module": "Duplicate & Sequence Engine",
                    "category": "Fuzzy Duplicate Risk",
                    "severity": "MEDIUM",
                    "risk_score": score,
                    "title": f"Fuzzy Duplicate Group {grp_id} ({sim_pct}% Similarity)",
                    "description": grp.get("reason", "High textual and amount similarity detected"),
                    "affected_records": tx_ids,
                    "expected_value": "Distinct non-overlapping invoices",
                    "actual_value": f"{len(tx_list)} potential duplicate records",
                    "difference": f"₹{amt:,.2f}",
                    "reason": grp.get("reason", "Fuzzy party or invoice similarity"),
                    "evidence": grp,
                    "rule_used": "Levenshtein Fuzzy String & Amount Match Rule",
                    "engine_type": "STATISTICAL_ML",
                    "risk_factors": factors,
                    "ai_explanation": explanation,
                    "recommended_action": "Cross-check physical vendor invoice copies to verify if distinct service periods apply."
                })

            # Missing Sequence Gaps
            for gap in dup_report.get("missing_sequence_gaps", []):
                seq_type = gap.get("sequence_type", "INVOICE_GAP")
                prefix = gap.get("series_prefix", "DEFAULT")
                fr = gap.get("expected_from", "0")
                to = gap.get("expected_to", "0")
                gap_count = int(gap.get("missing_count") or 1)
                code = f"FIND-GAP-{seq_type[:3]}-{prefix}-{fr}-{to}".replace(" ", "_")

                score, factors, explanation = cls.calculate_deterministic_risk_score(
                    severity="MEDIUM" if gap_count <= 3 else "HIGH",
                    amount=0.0,
                    materiality_threshold=materiality_thresh,
                    frequency=gap_count,
                    repetition_count=gap_count,
                    data_quality_issue=True,
                    data_quality_details=f"Sequence discontinuity in {seq_type}",
                    difference_pct=0.0,
                    historical_repeat=False,
                    affected_records_count=gap_count
                )

                findings.append({
                    "finding_code": code,
                    "module": "Duplicate & Sequence Engine",
                    "category": "Sequence Discontinuity",
                    "severity": "MEDIUM" if gap_count <= 3 else "HIGH",
                    "risk_score": score,
                    "title": f"Missing Sequence Break in {seq_type.replace('_', ' ').title()} (Series {prefix}: {fr} to {to})",
                    "description": f"Audit identified {gap_count} missing continuous numbering sequence numbers.",
                    "affected_records": [],
                    "expected_value": f"Continuous numerical sequence {fr} - {to}",
                    "actual_value": f"{gap_count} missing sequence numbers ({', '.join(map(str, gap.get('missing_numbers', [])[:5]))})",
                    "difference": f"{gap_count} unrecorded sequence entries",
                    "reason": "Break in continuous sequential documentation numbering",
                    "evidence": gap,
                    "rule_used": "Sequential Document Numbering Continuity Check",
                    "engine_type": "DETERMINISTIC",
                    "risk_factors": factors,
                    "ai_explanation": explanation,
                    "recommended_action": "Inspect sequence cancellation register, spoilt vouchers, and verify unrecorded transactions under SA 500."
                })
        except Exception as e:
            logger.warning(f"Error collecting duplicate/sequence findings: {e}")
        return findings

    @classmethod
    def _collect_hybrid_anomaly_findings(
        cls, conn, engagement_id: int, materiality_thresh: float
    ) -> List[Dict[str, Any]]:
        findings = []
        try:
            from backend.app.services.anomaly_detection_engine import detect_all_anomalies
            anom_report = detect_all_anomalies(engagement_id)
            anomalies = anom_report.get("anomalies", [])

            for anom in anomalies:
                anom_id = anom.get("anomaly_id", "ANOM")
                code = f"FIND-{anom_id.replace('#', '')}"
                tx_id = anom.get("transaction_id")
                tx_ids = [tx_id] if tx_id else []
                sev = str(anom.get("severity") or "MEDIUM").upper()
                amt = float(anom.get("amount") or 0.0)
                level = anom.get("level", "Statistical")
                pattern = anom.get("detected_pattern", "Outlier")

                score, factors, explanation = cls.calculate_deterministic_risk_score(
                    severity=sev,
                    amount=amt,
                    materiality_threshold=materiality_thresh,
                    frequency=1,
                    repetition_count=1,
                    data_quality_issue=False,
                    difference_pct=float(anom.get("anomaly_score") or 0.0) * 10.0,
                    historical_repeat="Historical" in pattern or "Spike" in pattern,
                    historical_details=f"Pattern: {pattern}",
                    affected_records_count=1
                )

                findings.append({
                    "finding_code": code,
                    "module": "Hybrid Anomaly Detection",
                    "category": f"{level} Anomaly",
                    "severity": sev,
                    "risk_score": score,
                    "title": f"Anomaly: {pattern} ({anom.get('party_name') or anom.get('ledger') or 'Transaction'})",
                    "description": anom.get("explanation", f"Transaction flagged under {level} hybrid anomaly inspection."),
                    "affected_records": tx_ids,
                    "expected_value": "Normal transaction bounds",
                    "actual_value": f"₹{amt:,.2f} flagged (Score: {anom.get('anomaly_score', 0)})",
                    "difference": f"₹{amt:,.2f}",
                    "reason": pattern,
                    "evidence": anom.get("evidence", {}),
                    "rule_used": f"Hybrid Anomaly Engine ({level} - {pattern})",
                    "engine_type": "STATISTICAL_ML" if "ML" in level or "Statistical" in level else "DETERMINISTIC",
                    "risk_factors": factors,
                    "ai_explanation": explanation + f"\n\nContextual Review: {anom.get('explanation', '')}",
                    "recommended_action": anom.get("recommended_review") or "Verify underlying contract, delivery challan, and authorization signatory."
                })
        except Exception as e:
            logger.warning(f"Error collecting hybrid anomaly findings: {e}")
        return findings

    @classmethod
    def _collect_yoy_variance_findings(
        cls, conn, engagement_id: int, materiality_thresh: float
    ) -> List[Dict[str, Any]]:
        findings = []
        try:
            from backend.app.services.yoy_comparison_engine import run_yoy_comparison
            comp = run_yoy_comparison(engagement_id, threshold_pct=10.0)

            # Check significant movements in major ledgers & party balances
            for item in comp.get("major_ledger_movements", []) + comp.get("party_balance_movements", []):
                risk_tag = str(item.get("risk") or "LOW").upper()
                if risk_tag in ["HIGH", "CRITICAL", "MEDIUM"]:
                    acc_name = item.get("account_name") or item.get("party_name") or "Account"
                    diff_amt = abs(float(item.get("absolute_difference") or 0.0))
                    pct_change = abs(float(item.get("percentage_difference") or 0.0))

                    if diff_amt >= (materiality_thresh * 0.5) or pct_change >= 20.0:
                        code = f"FIND-YOY-{abs(hash(acc_name)) % 100000:05d}"
                        score, factors, explanation = cls.calculate_deterministic_risk_score(
                            severity=risk_tag,
                            amount=diff_amt,
                            materiality_threshold=materiality_thresh,
                            frequency=1,
                            repetition_count=1,
                            data_quality_issue=False,
                            difference_pct=pct_change,
                            historical_repeat=True,
                            historical_details=f"Year-on-Year variance of {pct_change:.1f}%",
                            affected_records_count=1
                        )

                        findings.append({
                            "finding_code": code,
                            "module": "Year-on-Year Variance",
                            "category": "Variance Analysis",
                            "severity": risk_tag,
                            "risk_score": score,
                            "title": f"Significant YoY Variance in {acc_name} ({pct_change:.1f}%)",
                            "description": f"Account {acc_name} exhibited an absolute variance of ₹{diff_amt:,.2f} ({pct_change:.1f}% change year-over-year).",
                            "affected_records": [],
                            "expected_value": f"Prior Year Balance ₹{float(item.get('previous_year', 0)):,.2f}",
                            "actual_value": f"Current Year Balance ₹{float(item.get('current_year', 0)):,.2f}",
                            "difference": f"₹{diff_amt:,.2f} ({item.get('movement_direction', 'Movement')})",
                            "reason": f"Variance exceeded audit threshold of 10.0% ({pct_change:.1f}% noted)",
                            "evidence": item,
                            "rule_used": "SA 520 Analytical Procedures Variance Threshold Rule",
                            "engine_type": "DETERMINISTIC",
                            "risk_factors": factors,
                            "ai_explanation": explanation + (f"\n\nAI Analysis: {item.get('ai_reason', '')}" if item.get('ai_reason') else ""),
                            "recommended_action": "Perform substantive analytical review, corroborate with sales/production records, and request management explanation."
                        })
        except Exception as e:
            logger.warning(f"Error collecting YoY variance findings: {e}")
        return findings

    @classmethod
    def _collect_trial_balance_findings(
        cls, conn, engagement_id: int, materiality_thresh: float
    ) -> List[Dict[str, Any]]:
        findings = []
        try:
            from backend.app.services.trial_balance_analyzer import analyze_trial_balance
            tb_report = analyze_trial_balance(engagement_id)

            # TB Balance check
            if not tb_report.get("is_balanced", True):
                diff = abs(float(tb_report.get("net_difference") or 0.0))
                code = "FIND-TB-MISMATCH-001"
                score, factors, explanation = cls.calculate_deterministic_risk_score(
                    severity="CRITICAL",
                    amount=diff,
                    materiality_threshold=materiality_thresh,
                    frequency=1,
                    repetition_count=1,
                    data_quality_issue=True,
                    data_quality_details="Debit and Credit totals in Trial Balance do not match",
                    difference_pct=100.0,
                    historical_repeat=False,
                    affected_records_count=1
                )
                findings.append({
                    "finding_code": code,
                    "module": "Trial Balance Analysis",
                    "category": "Accounting Standard",
                    "severity": "CRITICAL",
                    "risk_score": score,
                    "title": "Trial Balance Debit-Credit Mismatch",
                    "description": f"Trial balance out of balance by ₹{diff:,.2f} (Total Debits: ₹{tb_report.get('total_debits', 0):,.2f}, Total Credits: ₹{tb_report.get('total_credits', 0):,.2f}).",
                    "affected_records": [],
                    "expected_value": "Zero Difference (Total Debit == Total Credit)",
                    "actual_value": f"Difference of ₹{diff:,.2f}",
                    "difference": f"₹{diff:,.2f}",
                    "reason": "Double-entry imbalance in imported ledger balances",
                    "evidence": tb_report,
                    "rule_used": "Double-Entry Trial Balance Equivalence Rule",
                    "engine_type": "DETERMINISTIC",
                    "risk_factors": factors,
                    "ai_explanation": explanation,
                    "recommended_action": "Rectify posting errors, identify unposted single-sided entries, and re-import ledger balances."
                })

            # Suspense accounts check
            for susp in tb_report.get("suspense_accounts", []):
                bal = abs(float(susp.get("closing_balance") or 0.0))
                if bal > 0:
                    code = f"FIND-TB-SUSPENSE-{abs(hash(susp.get('ledger_name', ''))) % 100000:05d}"
                    score, factors, explanation = cls.calculate_deterministic_risk_score(
                        severity="HIGH",
                        amount=bal,
                        materiality_threshold=materiality_thresh,
                        frequency=1,
                        repetition_count=1,
                        data_quality_issue=True,
                        data_quality_details="Unresolved Suspense balance",
                        difference_pct=100.0,
                        historical_repeat=False,
                        affected_records_count=1
                    )
                    findings.append({
                        "finding_code": code,
                        "module": "Trial Balance Analysis",
                        "category": "Accounting Standard",
                        "severity": "HIGH",
                        "risk_score": score,
                        "title": f"Non-Zero Suspense Account Balance: {susp.get('ledger_name')}",
                        "description": f"Suspense account holds an uncleared balance of ₹{bal:,.2f}.",
                        "affected_records": [],
                        "expected_value": "₹0.00 (Cleared suspense)",
                        "actual_value": f"₹{bal:,.2f}",
                        "difference": f"₹{bal:,.2f}",
                        "reason": "Unclassified transaction postings placed into suspense",
                        "evidence": susp,
                        "rule_used": "Suspense Account Clearance Mandate",
                        "engine_type": "DETERMINISTIC",
                        "risk_factors": factors,
                        "ai_explanation": explanation,
                        "recommended_action": "Audit suspense ledger breakdown, reclassify to appropriate ledger heads, and resolve prior to finalizing statements."
                    })
        except Exception as e:
            logger.warning(f"Error collecting trial balance findings: {e}")
        return findings

    @classmethod
    def _collect_bank_recon_findings(
        cls, conn, engagement_id: int, materiality_thresh: float
    ) -> List[Dict[str, Any]]:
        findings = []
        try:
            # Query reconciliations table
            recons = conn.execute(
                "SELECT * FROM reconciliations WHERE engagement_id = ? AND recon_type LIKE '%Bank%'",
                (engagement_id,)
            ).fetchall()

            for recon in recons:
                recon_id = recon["id"]
                unrec_amt = abs(float(recon["net_unreconciled_difference"] or recon["unreconciled_amount"] or 0.0))
                if unrec_amt > 0:
                    code = f"FIND-BRS-UNREC-{recon_id}"
                    score, factors, explanation = cls.calculate_deterministic_risk_score(
                        severity="HIGH" if unrec_amt >= materiality_thresh else "MEDIUM",
                        amount=unrec_amt,
                        materiality_threshold=materiality_thresh,
                        frequency=1,
                        repetition_count=1,
                        data_quality_issue=False,
                        difference_pct=50.0,
                        historical_repeat=False,
                        affected_records_count=int(recon["unmatched_bank_count"] or 0) + int(recon["unmatched_book_count"] or 0)
                    )
                    findings.append({
                        "finding_code": code,
                        "module": "Bank Reconciliation",
                        "category": "Reconciliation Exception",
                        "severity": "HIGH" if unrec_amt >= materiality_thresh else "MEDIUM",
                        "risk_score": score,
                        "title": f"Unreconciled Bank Difference in {recon['title']}",
                        "description": f"Net unreconciled bank difference of ₹{unrec_amt:,.2f} between Book and Bank statement.",
                        "affected_records": [],
                        "expected_value": f"Adjusted Bank Balance ₹{float(recon['adjusted_bank_balance'] or 0):,.2f}",
                        "actual_value": f"Book Balance ₹{float(recon['book_balance'] or 0):,.2f}",
                        "difference": f"₹{unrec_amt:,.2f}",
                        "reason": "Unreconciled timing differences or unrecorded bank debits/credits",
                        "evidence": dict(recon),
                        "rule_used": "BRS Reconciliation Mandate",
                        "engine_type": "DETERMINISTIC",
                        "risk_factors": factors,
                        "ai_explanation": explanation,
                        "recommended_action": "Obtain bank confirmation under SA 505 and trace unpresented cheques/uncredited deposits."
                    })
        except Exception as e:
            logger.warning(f"Error collecting bank recon findings: {e}")
        return findings

    @classmethod
    def _collect_gst_recon_findings(
        cls, conn, engagement_id: int, materiality_thresh: float
    ) -> List[Dict[str, Any]]:
        findings = []
        try:
            # Query GST recon items with status Unmatched or Mismatched
            recon_rows = conn.execute(
                "SELECT * FROM reconciliations WHERE engagement_id = ? AND recon_type LIKE '%GST%'",
                (engagement_id,)
            ).fetchall()

            for recon in recon_rows:
                recon_id = recon["id"]
                unmatched_items = conn.execute(
                    "SELECT * FROM reconciliation_items WHERE recon_id = ? AND status IN ('Unmatched', 'Mismatched')",
                    (recon_id,)
                ).fetchall()

                if unmatched_items:
                    total_tax_diff = sum(abs(float(it["tax_difference"] or it["difference"] or 0.0)) for it in unmatched_items)
                    code = f"FIND-GST-ITC-UNREC-{recon_id}"
                    score, factors, explanation = cls.calculate_deterministic_risk_score(
                        severity="CRITICAL" if total_tax_diff >= materiality_thresh else "HIGH",
                        amount=total_tax_diff,
                        materiality_threshold=materiality_thresh,
                        frequency=len(unmatched_items),
                        repetition_count=len(unmatched_items),
                        data_quality_issue=True,
                        data_quality_details="GST ITC mismatch between Books and GSTR-2B",
                        difference_pct=100.0,
                        historical_repeat=False,
                        affected_records_count=len(unmatched_items)
                    )
                    findings.append({
                        "finding_code": code,
                        "module": "GST Reconciliation",
                        "category": "Statutory Compliance",
                        "severity": "CRITICAL" if total_tax_diff >= materiality_thresh else "HIGH",
                        "risk_score": score,
                        "title": f"GST 2B vs Books ITC Discrepancy ({len(unmatched_items)} Mismatched Invoices)",
                        "description": f"Cumulative Input Tax Credit discrepancy of ₹{total_tax_diff:,.2f} across {len(unmatched_items)} purchase invoices.",
                        "affected_records": [it["id"] for it in unmatched_items if it["id"]],
                        "expected_value": "Eligible ITC matched with GSTR-2B portal",
                        "actual_value": f"₹{total_tax_diff:,.2f} unreflected ITC claimed in Books",
                        "difference": f"₹{total_tax_diff:,.2f}",
                        "reason": "Section 16(2)(aa) CGST Act condition unfulfilled (supplier non-filing/mismatch)",
                        "evidence": {"unmatched_count": len(unmatched_items), "total_difference": total_tax_diff},
                        "rule_used": "GST Section 16(2)(aa) ITC Reconciliation Rule",
                        "engine_type": "DETERMINISTIC",
                        "risk_factors": factors,
                        "ai_explanation": explanation,
                        "recommended_action": "Disallow unmatched ITC under Sec 16(2)(aa) or issue vendor reminders to file GSTR-1."
                    })
        except Exception as e:
            logger.warning(f"Error collecting GST findings: {e}")
        return findings

    @classmethod
    def get_dashboard_summary(cls, engagement_id: int) -> Dict[str, Any]:
        """
        Calculates executive dashboard metrics for the Audit Risk & Findings module:
        - Total Findings
        - Open Findings
        - High Risk
        - Critical
        - Resolved
        - Under Review
        - Breakdown by Module, Severity, Category, and Average Risk Score
        """
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT * FROM audit_findings WHERE engagement_id = ?",
            (engagement_id,)
        ).fetchall()
        conn.close()

        total = len(rows)
        open_count = 0
        resolved_count = 0
        under_review_count = 0
        waived_count = 0

        high_risk_count = 0
        critical_count = 0

        by_severity = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        by_module: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        total_risk_score = 0.0

        for r in rows:
            status = (r["status"] or "Open").title()
            sev = (r["severity"] or "MEDIUM").upper()
            score = float(r["risk_score"] or 0.0)
            total_risk_score += score
            mod = r["module"] or "General"
            cat = r["category"] or "General Audit"

            if status == "Open":
                open_count += 1
            elif status in ["Under Review", "In Review"]:
                under_review_count += 1
            elif status == "Resolved":
                resolved_count += 1
            elif status == "Waived":
                waived_count += 1

            if sev in by_severity:
                by_severity[sev] += 1
            else:
                by_severity["MEDIUM"] += 1

            by_module[mod] = by_module.get(mod, 0) + 1
            by_category[cat] = by_category.get(cat, 0) + 1

            # High risk & critical metrics (excluding resolved/waived)
            if status not in ["Resolved", "Waived"]:
                if sev == "CRITICAL" or score >= 8.5:
                    critical_count += 1
                elif sev == "HIGH" or score >= 6.5:
                    high_risk_count += 1

        avg_score = round(total_risk_score / max(1, total), 2) if total > 0 else 0.0

        return {
            "engagement_id": engagement_id,
            "total_findings": total,
            "open_findings": open_count,
            "high_risk": high_risk_count,
            "critical": critical_count,
            "resolved": resolved_count,
            "under_review": under_review_count,
            "waived": waived_count,
            "average_risk_score": avg_score,
            "by_severity": by_severity,
            "by_module": by_module,
            "by_category": by_category
        }
