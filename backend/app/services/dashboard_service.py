import math
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.app.database import get_db_connection
from backend.app.services.checklist_generator import ChecklistGenerator
from backend.app.services.yoy_comparison_engine import run_yoy_comparison

def parse_date_to_ym(date_str: str) -> Optional[str]:
    """Helper to parse a date string into YYYY-MM format."""
    if not date_str:
        return None
    d = str(date_str).strip()
    if len(d) >= 7 and d[4] == '-' and d[:4].isdigit() and d[5:7].isdigit():
        return d[:7] # YYYY-MM
    
    # Try common formats: DD/MM/YYYY, DD-MM-YYYY, YYYY/MM/DD
    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(d[:10], fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            pass
    return None

def get_month_name(ym_str: str) -> str:
    """Converts YYYY-MM to 'Mon YYYY' (e.g. 2024-04 -> Apr 2024)."""
    try:
        dt = datetime.strptime(ym_str, "%Y-%m")
        return dt.strftime("%b %Y")
    except Exception:
        return ym_str

class DashboardService:
    @classmethod
    def get_comprehensive_dashboard(cls, engagement_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieves real, 100% database-backed metrics for the main FinAuditPro dashboard:
        - 6 TOP CARDS: Active Clients, Active Engagements, Open Findings, High-Risk Findings, Unmatched Transactions, Pending Reviews
        - 7 MAIN SECTIONS:
          1. Engagement Overview
          2. Risk Overview (with severity & audit area distribution)
          3. Recent Findings
          4. Reconciliation Status
          5. Anomaly Summary (Benford conformity, ML & statistical outliers)
          6. Year-on-Year Changes
          7. Checklist Progress
        - CHARTS DATA:
          - Finding severity distribution
          - Monthly transaction volume
          - Monthly transaction value
          - Reconciliation status breakdown
          - Risk by audit area
          - Year-on-year movement
        """
        conn = get_db_connection()
        
        # 1. Resolve Active Engagement
        eng = None
        if engagement_id:
            eng_row = conn.execute("""
                SELECT e.*, c.name as client_name, c.pan as client_pan, c.gstin as client_gstin,
                       c.entity_type as client_entity_type, c.industry as client_industry,
                       u.full_name as lead_auditor_name, s.full_name as assigned_staff_name
                FROM engagements e
                JOIN clients c ON e.client_id = c.id
                LEFT JOIN users u ON e.lead_auditor_id = u.id
                LEFT JOIN users s ON e.assigned_staff_id = s.id
                WHERE e.id = ?
            """, (engagement_id,)).fetchone()
            if eng_row:
                eng = dict(eng_row)
        
        if not eng:
            # Pick the latest non-archived engagement or fallback to latest
            eng_row = conn.execute("""
                SELECT e.*, c.name as client_name, c.pan as client_pan, c.gstin as client_gstin,
                       c.entity_type as client_entity_type, c.industry as client_industry,
                       u.full_name as lead_auditor_name, s.full_name as assigned_staff_name
                FROM engagements e
                JOIN clients c ON e.client_id = c.id
                LEFT JOIN users u ON e.lead_auditor_id = u.id
                LEFT JOIN users s ON e.assigned_staff_id = s.id
                ORDER BY CASE WHEN e.status IN ('In Progress', 'Draft', 'Under Review') THEN 0 ELSE 1 END, e.id DESC
                LIMIT 1
            """).fetchone()
            if eng_row:
                eng = dict(eng_row)
                engagement_id = eng["id"]

        all_engagements_rows = conn.execute("""
            SELECT e.id, e.title, e.financial_year, e.status, e.audit_type, c.name as client_name
            FROM engagements e
            JOIN clients c ON e.client_id = c.id
            ORDER BY e.id DESC
        """).fetchall()
        all_engagements = [dict(r) for r in all_engagements_rows]

        # -------------------------------------------------------------
        # TOP METRIC CARDS (Using real DB values)
        # -------------------------------------------------------------
        active_clients_count = conn.execute("SELECT COUNT(*) as c FROM clients").fetchone()["c"]
        active_engagements_count = conn.execute(
            "SELECT COUNT(*) as c FROM engagements WHERE status IN ('Draft', 'In Progress', 'Under Review')"
        ).fetchone()["c"]
        completed_engagements_count = conn.execute(
            "SELECT COUNT(*) as c FROM engagements WHERE status = 'Completed'"
        ).fetchone()["c"]
        archived_engagements_count = conn.execute(
            "SELECT COUNT(*) as c FROM engagements WHERE status = 'Archived'"
        ).fetchone()["c"]

        # Open & High-Risk Findings
        if engagement_id:
            open_findings_count = conn.execute(
                "SELECT COUNT(*) as c FROM audit_findings WHERE engagement_id = ? AND status IN ('Open', 'In Review', 'Under Review')",
                (engagement_id,)
            ).fetchone()["c"]
            high_risk_findings_count = conn.execute(
                "SELECT COUNT(*) as c FROM audit_findings WHERE engagement_id = ? AND severity IN ('CRITICAL', 'HIGH') AND status NOT IN ('Resolved', 'Waived')",
                (engagement_id,)
            ).fetchone()["c"]
            critical_findings_count = conn.execute(
                "SELECT COUNT(*) as c FROM audit_findings WHERE engagement_id = ? AND severity = 'CRITICAL' AND status NOT IN ('Resolved', 'Waived')",
                (engagement_id,)
            ).fetchone()["c"]
        else:
            open_findings_count = conn.execute(
                "SELECT COUNT(*) as c FROM audit_findings WHERE status IN ('Open', 'In Review', 'Under Review')"
            ).fetchone()["c"]
            high_risk_findings_count = conn.execute(
                "SELECT COUNT(*) as c FROM audit_findings WHERE severity IN ('CRITICAL', 'HIGH') AND status NOT IN ('Resolved', 'Waived')"
            ).fetchone()["c"]
            critical_findings_count = conn.execute(
                "SELECT COUNT(*) as c FROM audit_findings WHERE severity = 'CRITICAL' AND status NOT IN ('Resolved', 'Waived')"
            ).fetchone()["c"]

        # Unmatched Transactions
        if engagement_id:
            # Count unmatched items from reconciliation_items if present
            unmatched_items_count = conn.execute("""
                SELECT COUNT(*) as c FROM reconciliation_items ri
                JOIN reconciliations r ON ri.recon_id = r.id
                WHERE r.engagement_id = ? AND (ri.status IN ('Unmatched', 'Suggested') OR ri.match_level = 'UNMATCHED')
            """, (engagement_id,)).fetchone()["c"]
            
            # If no detailed items, check summary columns from reconciliations
            if unmatched_items_count == 0:
                recon_summary = conn.execute("""
                    SELECT SUM(unmatched_bank_count + unmatched_book_count) as s
                    FROM reconciliations WHERE engagement_id = ?
                """, (engagement_id,)).fetchone()["s"]
                unmatched_items_count = int(recon_summary or 0)
        else:
            unmatched_items_count = conn.execute("""
                SELECT COUNT(*) as c FROM reconciliation_items WHERE status IN ('Unmatched', 'Suggested') OR match_level = 'UNMATCHED'
            """).fetchone()["c"]
            if unmatched_items_count == 0:
                recon_summary = conn.execute("SELECT SUM(unmatched_bank_count + unmatched_book_count) as s FROM reconciliations").fetchone()["s"]
                unmatched_items_count = int(recon_summary or 0)

        # Pending Reviews (Engagements Under Review + Working Papers Under Review/Needs Correction + Findings Under Review)
        if engagement_id:
            eng_under_review = 1 if (eng and eng.get("status") == "Under Review") else 0
            wp_under_review = conn.execute(
                "SELECT COUNT(*) as c FROM working_papers WHERE engagement_id = ? AND status IN ('Under Review', 'Needs Correction')",
                (engagement_id,)
            ).fetchone()["c"]
            findings_under_review = conn.execute(
                "SELECT COUNT(*) as c FROM audit_findings WHERE engagement_id = ? AND status IN ('Under Review', 'In Review')",
                (engagement_id,)
            ).fetchone()["c"]
            pending_reviews_count = eng_under_review + wp_under_review + findings_under_review
        else:
            eng_under_review = conn.execute("SELECT COUNT(*) as c FROM engagements WHERE status = 'Under Review'").fetchone()["c"]
            wp_under_review = conn.execute("SELECT COUNT(*) as c FROM working_papers WHERE status IN ('Under Review', 'Needs Correction')").fetchone()["c"]
            findings_under_review = conn.execute("SELECT COUNT(*) as c FROM audit_findings WHERE status IN ('Under Review', 'In Review')").fetchone()["c"]
            pending_reviews_count = eng_under_review + wp_under_review + findings_under_review

        # -------------------------------------------------------------
        # SECTION 1: ENGAGEMENT OVERVIEW & VOLUMETRICS
        # -------------------------------------------------------------
        eng_overview = {
            "engagement": eng,
            "all_engagements": all_engagements,
            "total_files": 0,
            "total_transactions": 0,
            "total_debit_turnover": 0.0,
            "total_credit_turnover": 0.0,
            "total_turnover_examined": 0.0,
        }

        if engagement_id:
            eng_overview["total_files"] = conn.execute(
                "SELECT COUNT(*) as c FROM uploaded_files WHERE engagement_id = ?", (engagement_id,)
            ).fetchone()["c"]
            
            tx_stats = conn.execute("""
                SELECT COUNT(*) as cnt, SUM(debit) as deb, SUM(credit) as cred
                FROM transactions WHERE engagement_id = ?
            """, (engagement_id,)).fetchone()
            
            eng_overview["total_transactions"] = tx_stats["cnt"] or 0
            eng_overview["total_debit_turnover"] = round(tx_stats["deb"] or 0.0, 2)
            eng_overview["total_credit_turnover"] = round(tx_stats["cred"] or 0.0, 2)
            eng_overview["total_turnover_examined"] = round(max(eng_overview["total_debit_turnover"], eng_overview["total_credit_turnover"]), 2)

        # -------------------------------------------------------------
        # SECTION 2: RISK OVERVIEW & SEVERITY / AREA DISTRIBUTION
        # -------------------------------------------------------------
        findings_query = "SELECT * FROM audit_findings" + (f" WHERE engagement_id = {engagement_id}" if engagement_id else "")
        finding_rows = conn.execute(findings_query).fetchall()
        
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        engine_counts = {"DETERMINISTIC": 0, "STATISTICAL_ML": 0, "LOCAL_AI": 0}
        area_counts: Dict[str, int] = {}
        total_risk_score = 0.0
        resolved_count = 0
        waived_count = 0
        under_review_findings_count = 0

        for r in finding_rows:
            sev = (r["severity"] or "MEDIUM").upper()
            if sev in severity_counts:
                severity_counts[sev] += 1
            else:
                severity_counts["MEDIUM"] += 1
                
            eng_type = (r["engine_type"] or "DETERMINISTIC").upper()
            if eng_type in engine_counts:
                engine_counts[eng_type] += 1
            else:
                engine_counts["DETERMINISTIC"] += 1

            # Categorize by audit area
            mod = r["module"] or "General"
            cat = r["category"] or "General Audit"
            area = cat
            if "tax" in mod.lower() or "40a" in str(r["rule_used"]).lower() or "269st" in str(r["rule_used"]).lower() or "tds" in mod.lower():
                area = "Tax & Statutory"
            elif "gst" in mod.lower() or "itc" in mod.lower() or "gstin" in str(r["rule_used"]).lower():
                area = "Direct & Indirect Tax (GST)"
            elif "bank" in mod.lower() or "cash" in mod.lower() or "cheque" in str(r["title"]).lower():
                area = "Cash & Banking"
            elif "duplicate" in mod.lower() or "gap" in mod.lower() or "duplicate" in cat.lower():
                area = "Duplicates & Number Gaps"
            elif "ml" in mod.lower() or "outlier" in cat.lower() or "benford" in str(r["rule_used"]).lower():
                area = "Statistical & ML Anomalies"
            elif "yoy" in mod.lower() or "variance" in cat.lower() or "statement" in mod.lower():
                area = "Financial Statement Analysis"
            elif "payroll" in mod.lower() or "salary" in str(r["title"]).lower() or "director" in str(r["title"]).lower():
                area = "Payroll & Remuneration"

            area_counts[area] = area_counts.get(area, 0) + 1
            total_risk_score += float(r["risk_score"] or 0.0)

            st = (r["status"] or "Open").title()
            if st == "Resolved":
                resolved_count += 1
            elif st == "Waived":
                waived_count += 1
            elif st in ["Under Review", "In Review"]:
                under_review_findings_count += 1

        total_findings = len(finding_rows)
        avg_risk_score = round(total_risk_score / max(1, total_findings), 1) if total_findings > 0 else 0.0

        if severity_counts["CRITICAL"] > 0 or avg_risk_score >= 8.0:
            risk_posture = "CRITICAL"
        elif severity_counts["HIGH"] > 1 or avg_risk_score >= 6.0:
            risk_posture = "HIGH"
        elif severity_counts["MEDIUM"] > 2 or avg_risk_score >= 4.0:
            risk_posture = "MODERATE"
        else:
            risk_posture = "LOW"

        risk_overview = {
            "total_findings": total_findings,
            "open_findings": open_findings_count,
            "high_risk_findings": high_risk_findings_count,
            "critical_findings": critical_findings_count,
            "resolved_findings": resolved_count,
            "waived_findings": waived_count,
            "under_review_findings": under_review_findings_count,
            "severity_counts": severity_counts,
            "engine_counts": engine_counts,
            "area_counts": area_counts,
            "average_risk_score": avg_risk_score,
            "risk_posture": risk_posture
        }

        # -------------------------------------------------------------
        # SECTION 3: RECENT FINDINGS TABLE
        # -------------------------------------------------------------
        recent_findings_query = """
            SELECT id, finding_code, title, severity, category, module,
                   expected_value, actual_value, difference, rule_used,
                   engine_type, status, auditor_comment, risk_score, created_at
            FROM audit_findings
        """ + (f" WHERE engagement_id = {engagement_id}" if engagement_id else "") + """
            ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END, id DESC
            LIMIT 10
        """
        recent_findings = [dict(r) for r in conn.execute(recent_findings_query).fetchall()]

        # -------------------------------------------------------------
        # SECTION 4: RECONCILIATION STATUS
        # -------------------------------------------------------------
        recon_query = "SELECT * FROM reconciliations" + (f" WHERE engagement_id = {engagement_id}" if engagement_id else "") + " ORDER BY id DESC"
        reconciliations_list = [dict(r) for r in conn.execute(recon_query).fetchall()]

        total_matched = sum(r.get("matched_count", 0) or 0 for r in reconciliations_list)
        total_unmatched_bank = sum(r.get("unmatched_bank_count", 0) or 0 for r in reconciliations_list)
        total_unmatched_book = sum(r.get("unmatched_book_count", 0) or 0 for r in reconciliations_list)
        total_amount_mismatches = sum(r.get("amount_diff_count", 0) or 0 for r in reconciliations_list)
        total_unreconciled_diff = sum(abs(float(r.get("net_unreconciled_difference", 0.0) or 0.0)) for r in reconciliations_list)

        reconciliation_status = {
            "reconciliations": reconciliations_list,
            "total_reconciliations": len(reconciliations_list),
            "matched_items": total_matched,
            "unmatched_bank_items": total_unmatched_bank,
            "unmatched_book_items": total_unmatched_book,
            "amount_mismatches": total_amount_mismatches,
            "total_unmatched": total_unmatched_bank + total_unmatched_book + total_amount_mismatches,
            "net_unreconciled_difference_sum": round(total_unreconciled_diff, 2)
        }

        # -------------------------------------------------------------
        # SECTION 5: ANOMALY SUMMARY (Benford, ML, Spikes)
        # -------------------------------------------------------------
        # Benford 1st digit calculation on real transactions
        tx_rows = conn.execute(
            "SELECT id, date, voucher_no, ledger, party_name, debit, credit, amount, description FROM transactions" +
            (f" WHERE engagement_id = {engagement_id}" if engagement_id else "")
        ).fetchall()

        digit_counts = {str(d): 0 for d in range(1, 10)}
        total_valid_digits = 0
        round_sum_count = 0
        weekend_count = 0
        surge_count = 0
        high_value_records = []

        for r in tx_rows:
            amt = float(r["amount"] or max(float(r["debit"] or 0), float(r["credit"] or 0)))
            if amt > 0:
                first_char = str(int(amt))[0]
                if first_char in digit_counts:
                    digit_counts[first_char] += 1
                    total_valid_digits += 1

            # Round sum check: >= 50,000 and round multiple of 10k/50k
            if amt >= 50000.0 and (amt % 10000.0 == 0 or amt % 50000.0 == 0):
                round_sum_count += 1

            # Weekend check
            d_str = r["date"]
            if d_str:
                ym = parse_date_to_ym(d_str)
                # Attempt weekday calculation
                try:
                    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
                        try:
                            dt_obj = datetime.strptime(d_str[:10], fmt)
                            if dt_obj.weekday() in [5, 6]: # Sat=5, Sun=6
                                weekend_count += 1
                            break
                        except ValueError:
                            pass
                except Exception:
                    pass

            if amt >= 100000.0:
                high_value_records.append({
                    "id": r["id"],
                    "date": r["date"],
                    "voucher_no": r["voucher_no"] or "N/A",
                    "ledger": r["ledger"] or "Unclassified",
                    "party_name": r["party_name"] or "N/A",
                    "amount": round(amt, 2),
                    "description": r["description"] or ""
                })

        # Calculate Benford MAD (Mean Absolute Deviation)
        benford_expected = {
            "1": 30.1, "2": 17.6, "3": 12.5, "4": 9.7,
            "5": 7.9, "6": 6.7, "7": 5.8, "8": 5.1, "9": 4.6
        }
        digit_comparison = []
        mad_sum = 0.0

        for d in range(1, 10):
            d_str = str(d)
            act_count = digit_counts[d_str]
            act_pct = round((act_count / max(1, total_valid_digits)) * 100, 1)
            exp_pct = benford_expected[d_str]
            diff = abs(act_pct - exp_pct)
            mad_sum += diff
            digit_comparison.append({
                "digit": d,
                "count": act_count,
                "actual_pct": act_pct,
                "expected_pct": exp_pct,
                "difference": round(diff, 1)
            })

        mad_score = round(mad_sum / 9.0, 2)
        if mad_score <= 3.0:
            benford_status = "Close Conformity"
        elif mad_score <= 6.0:
            benford_status = "Acceptable"
        else:
            benford_status = "Non-Conformity"

        ml_outliers_count = engine_counts.get("STATISTICAL_ML", 0)

        anomaly_summary = {
            "benford_status": benford_status,
            "benford_mad": mad_score,
            "benford_digits": digit_comparison,
            "ml_outliers_count": ml_outliers_count,
            "round_sum_count": round_sum_count,
            "weekend_count": weekend_count,
            "total_transactions_analyzed": len(tx_rows),
            "top_high_value_items": sorted(high_value_records, key=lambda x: x["amount"], reverse=True)[:6]
        }

        # -------------------------------------------------------------
        # SECTION 6: YEAR-ON-YEAR CHANGES
        # -------------------------------------------------------------
        yoy_summary_data = []
        try:
            if engagement_id:
                yoy_res = run_yoy_comparison(engagement_id=engagement_id, threshold_pct=10.0, materiality_threshold=50000.0)
                exec_items = yoy_res.get("executive_comparison", [])
                yoy_summary_data = exec_items[:8]
        except Exception:
            yoy_summary_data = []

        # -------------------------------------------------------------
        # SECTION 7: CHECKLIST PROGRESS
        # -------------------------------------------------------------
        checklist_summary = {
            "total_items": 0,
            "completed_count": 0,
            "in_progress_count": 0,
            "not_started_count": 0,
            "requires_review_count": 0,
            "not_applicable_count": 0,
            "completion_pct": 0.0,
            "category_progress": [],
            "requires_review_items": []
        }
        try:
            if engagement_id:
                chk_res = ChecklistGenerator.get_checklist_summary(engagement_id)
                checklist_summary = {
                    "total_items": chk_res.get("total_items", 0),
                    "completed_count": chk_res.get("completed_count", 0),
                    "in_progress_count": chk_res.get("in_progress_count", 0),
                    "not_started_count": chk_res.get("not_started_count", 0),
                    "requires_review_count": chk_res.get("requires_review_count", 0),
                    "not_applicable_count": chk_res.get("not_applicable_count", 0),
                    "completion_pct": chk_res.get("completion_percentage", 0.0),
                    "category_progress": chk_res.get("categories", []),
                    "requires_review_items": chk_res.get("requires_review_items", [])
                }
        except Exception:
            pass

        # -------------------------------------------------------------
        # CHARTS: MONTHLY TRANSACTION VOLUME & VALUE
        # -------------------------------------------------------------
        monthly_map: Dict[str, Dict[str, Any]] = {}
        for r in tx_rows:
            ym = parse_date_to_ym(r["date"]) or "Undated"
            if ym not in monthly_map:
                monthly_map[ym] = {
                    "month": ym,
                    "month_label": get_month_name(ym) if ym != "Undated" else "Undated",
                    "transaction_count": 0,
                    "debit_amount": 0.0,
                    "credit_amount": 0.0,
                    "total_value": 0.0
                }
            monthly_map[ym]["transaction_count"] += 1
            deb = float(r["debit"] or 0.0)
            cred = float(r["credit"] or 0.0)
            val = float(r["amount"] or max(deb, cred))
            monthly_map[ym]["debit_amount"] += deb
            monthly_map[ym]["credit_amount"] += cred
            monthly_map[ym]["total_value"] += val

        sorted_months = sorted(monthly_map.keys())
        monthly_trends = []
        for ym in sorted_months:
            m_data = monthly_map[ym]
            monthly_trends.append({
                "month": m_data["month"],
                "month_label": m_data["month_label"],
                "transaction_count": m_data["transaction_count"],
                "debit_amount": round(m_data["debit_amount"], 2),
                "credit_amount": round(m_data["credit_amount"], 2),
                "total_value": round(m_data["total_value"], 2)
            })

        conn.close()

        return {
            "top_cards": {
                "active_clients_count": active_clients_count,
                "active_engagements_count": active_engagements_count,
                "open_findings_count": open_findings_count,
                "high_risk_findings_count": high_risk_findings_count,
                "critical_findings_count": critical_findings_count,
                "unmatched_transactions_count": unmatched_items_count,
                "pending_reviews_count": pending_reviews_count,
                "completed_engagements_count": completed_engagements_count,
                "archived_engagements_count": archived_engagements_count
            },
            "engagement_overview": eng_overview,
            "risk_overview": risk_overview,
            "recent_findings": recent_findings,
            "reconciliation_status": reconciliation_status,
            "anomaly_summary": anomaly_summary,
            "yoy_summary": yoy_summary_data,
            "checklist_progress": checklist_summary,
            "monthly_trends": monthly_trends
        }
