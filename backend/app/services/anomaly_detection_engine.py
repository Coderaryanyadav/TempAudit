import re
import math
import json
import io
import csv
from datetime import datetime
import hashlib
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

from backend.app.database import get_db_connection

# Standard audit disclaimer constant
AUDIT_DISCLAIMER = "Potential anomaly detected. Auditor review recommended."

def extract_transaction_features(t: Dict[str, Any], all_txs: List[Dict[str, Any]], ledger_stats: Dict[str, Any], party_stats: Dict[str, Any], daily_counts: Dict[str, int]) -> Dict[str, Any]:
    """Extracts multidimensional numeric and categorical features for rule, statistical, and ML evaluation."""
    amt = float(t.get("amount") or t.get("debit") or t.get("credit") or 0.0)
    debit = float(t.get("debit") or 0.0)
    credit = float(t.get("credit") or 0.0)
    
    date_str = str(t.get("date") or "").strip().split("T")[0]
    day_of_week = 0
    day_of_month = 15
    is_month_end = 0
    is_quarter_end = 0
    is_weekend = 0
    month_val = 1
    
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            day_of_week = dt.weekday()
            day_of_month = dt.day
            month_val = dt.month
            is_weekend = 1 if day_of_week in [5, 6] else 0
            
            # Month-end: last 3 days of month or day >= 28
            next_day_month = (dt.replace(day=28) + (datetime.resolution * 86400 * 4)).month
            # Check if within last 3 days
            is_month_end = 1 if (day_of_month >= 28 or (month_val in [1, 3, 5, 7, 8, 10, 12] and day_of_month >= 29) or (month_val in [4, 6, 9, 11] and day_of_month >= 28)) else 0
            is_quarter_end = 1 if (is_month_end and month_val in [3, 6, 9, 12]) else 0
        except Exception:
            pass

    ledger = (t.get("ledger") or "General Ledger").strip()
    party = (t.get("party_name") or "Direct / Cash").strip()
    voucher = (t.get("voucher_no") or "").strip()
    desc = (t.get("description") or "").strip()

    l_stat = ledger_stats.get(ledger, {"mean": amt, "std": 1.0, "count": 1, "max": amt})
    p_stat = party_stats.get(party, {"count": 1, "total_amt": amt, "mean": amt})
    d_count = daily_counts.get(date_str, 1)

    return {
        "id": t.get("id"),
        "date_str": date_str,
        "amount": amt,
        "log_amount": float(np.log1p(amt)),
        "debit": debit,
        "credit": credit,
        "log_debit": float(np.log1p(debit)),
        "log_credit": float(np.log1p(credit)),
        "day_of_week": day_of_week,
        "day_of_month": day_of_month,
        "month": month_val,
        "is_weekend": is_weekend,
        "is_month_end": is_month_end,
        "is_quarter_end": is_quarter_end,
        "daily_velocity": d_count,
        "ledger": ledger,
        "party": party,
        "voucher": voucher,
        "description": desc,
        "reference": (t.get("reference_no") or "").strip(),
        "invoice": (t.get("invoice_no") or "").strip(),
        "ledger_mean": l_stat["mean"],
        "ledger_std": l_stat["std"],
        "ledger_count": l_stat["count"],
        "party_count": p_stat["count"],
        "party_total": p_stat["total_amt"],
        "party_mean": p_stat["mean"]
    }

def calculate_benford_mad(amounts: List[float]) -> Tuple[float, str, Dict[int, Dict[str, float]]]:
    """Calculates Benford's Law leading digit Mean Absolute Deviation (Nigrini Forensic Standard)."""
    first_digits = []
    for a in amounts:
        if a >= 10.0:
            s = f"{a:.2f}".lstrip("0.")
            if s and s[0].isdigit() and s[0] != "0":
                first_digits.append(int(s[0]))

    total = len(first_digits)
    if total < 15:
        return 0.0, "Insufficient Data", {}

    counts = {d: first_digits.count(d) for d in range(1, 10)}
    actual_dist = {d: counts[d] / total for d in range(1, 10)}
    expected_dist = {d: math.log10(1.0 + 1.0 / d) for d in range(1, 10)}

    mad = sum(abs(actual_dist[d] - expected_dist[d]) for d in range(1, 10)) / 9.0
    
    conformity = "Close Conformity"
    if mad > 0.015:
        conformity = "Non-Conformity (Suspicious Distribution)"
    elif mad > 0.012:
        conformity = "Marginally Acceptable"
    elif mad > 0.006:
        conformity = "Acceptable Conformity"

    details = {}
    for d in range(1, 10):
        details[d] = {
            "count": counts[d],
            "actual_pct": round(actual_dist[d] * 100, 2),
            "expected_pct": round(expected_dist[d] * 100, 2),
            "diff_pct": round((actual_dist[d] - expected_dist[d]) * 100, 2)
        }

    return mad, conformity, details

def detect_all_anomalies(engagement_id: int) -> Dict[str, Any]:
    """
    Executes 3-Tier Hybrid Anomaly Detection Engine:
    - Level 1: Deterministic Rules
    - Level 2: Statistical Analysis (Z-Scores, IQR, Benford, Frequency, Expense Surges)
    - Level 3: Local Machine Learning (Isolation Forest, Local Outlier Factor, DBSCAN)
    """
    conn = get_db_connection()
    
    # 1. Fetch Engagement
    eng_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    if not eng_row:
        conn.close()
        raise ValueError(f"Engagement #{engagement_id} not found")
    engagement = dict(eng_row)

    # 2. Fetch Transactions
    tx_rows = conn.execute("""
        SELECT * FROM transactions
        WHERE engagement_id = ?
        ORDER BY date ASC, id ASC
    """, (engagement_id,)).fetchall()
    raw_txs = [dict(r) for r in tx_rows]
    total_tx = len(raw_txs)

    # 3. Fetch Existing Anomaly Reviews
    rev_rows = conn.execute("SELECT * FROM anomaly_reviews WHERE engagement_id = ?", (engagement_id,)).fetchall()
    reviews_map = {r["anomaly_id"]: dict(r) for r in rev_rows}

    if total_tx == 0:
        conn.close()
        return {
            "engagement_id": engagement_id,
            "total_transactions": 0,
            "summary": {
                "total_anomalies": 0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "level_1_deterministic": 0,
                "level_2_statistical": 0,
                "level_3_ml": 0,
                "reviewed_count": 0,
                "open_count": 0
            },
            "anomalies": [],
            "benford_analysis": {"mad": 0.0, "conformity": "No Data"}
        }

    # 4. Compute Aggregate Stats for Feature Extraction
    ledger_amounts: Dict[str, List[float]] = {}
    party_amounts: Dict[str, List[float]] = {}
    daily_counts: Dict[str, int] = {}
    monthly_ledger_totals: Dict[Tuple[str, str], float] = {} # (ledger, YYYY-MM) -> total_amt
    all_amounts = []

    for t in raw_txs:
        amt = float(t.get("amount") or t.get("debit") or t.get("credit") or 0.0)
        ledger = (t.get("ledger") or "General Ledger").strip()
        party = (t.get("party_name") or "Direct / Cash").strip()
        date_str = str(t.get("date") or "").strip().split("T")[0]
        
        all_amounts.append(amt)
        ledger_amounts.setdefault(ledger, []).append(amt)
        party_amounts.setdefault(party, []).append(amt)
        if date_str:
            daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
            month_key = date_str[:7]
            monthly_ledger_totals[(ledger, month_key)] = monthly_ledger_totals.get((ledger, month_key), 0.0) + amt

    ledger_stats = {}
    for l_name, a_list in ledger_amounts.items():
        arr = np.array(a_list)
        ledger_stats[l_name] = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "count": len(a_list),
            "max": float(np.max(arr)),
            "q25": float(np.percentile(arr, 25)),
            "q75": float(np.percentile(arr, 75))
        }

    party_stats = {}
    for p_name, a_list in party_amounts.items():
        party_stats[p_name] = {
            "count": len(a_list),
            "total_amt": float(sum(a_list)),
            "mean": float(sum(a_list) / len(a_list))
        }

    # Global amount stats
    amt_arr = np.array([a for a in all_amounts if a > 0]) if all_amounts else np.array([0.0])
    global_q25 = float(np.percentile(amt_arr, 25)) if len(amt_arr) > 0 else 0.0
    global_q75 = float(np.percentile(amt_arr, 75)) if len(amt_arr) > 0 else 0.0
    global_iqr = max(0.01, global_q75 - global_q25)
    global_iqr_cutoff = global_q75 + 1.5 * global_iqr
    global_extreme_iqr_cutoff = global_q75 + 3.0 * global_iqr
    global_p95 = float(np.percentile(amt_arr, 95)) if len(amt_arr) > 0 else 0.0
    global_mean = float(np.mean(amt_arr)) if len(amt_arr) > 0 else 0.0
    global_std = max(0.01, float(np.std(amt_arr))) if len(amt_arr) > 0 else 1.0

    # Extract structured features for all transactions
    features_list = [
        extract_transaction_features(t, raw_txs, ledger_stats, party_stats, daily_counts)
        for t in raw_txs
    ]

    # Map raw_tx by ID
    tx_by_id = {t["id"]: t for t in raw_txs}

    # Anomaly accumulator list (candidate dictionary)
    anomaly_candidates: List[Dict[str, Any]] = []
    seen_tx_patterns = set() # (tx_id, pattern_type)

    def add_anomaly_candidate(
        tx_id: int,
        level: str,
        pattern_type: str,
        base_score: float,
        evidence: Dict[str, Any],
        explanation: str,
        recommended_review: str,
        severity_override: Optional[str] = None
    ):
        key = (tx_id, pattern_type)
        if key in seen_tx_patterns:
            return
        seen_tx_patterns.add(key)

        score = min(100.0, max(10.0, round(base_score, 1)))
        
        if severity_override:
            sev = severity_override
        else:
            if score >= 85.0:
                sev = "CRITICAL"
            elif score >= 70.0:
                sev = "HIGH"
            elif score >= 50.0:
                sev = "MEDIUM"
            else:
                sev = "LOW"

        anomaly_candidates.append({
            "transaction_id": tx_id,
            "level": level,
            "pattern_type": pattern_type,
            "anomaly_score": score,
            "severity": sev,
            "evidence": evidence,
            "explanation": f"{AUDIT_DISCLAIMER} {explanation}",
            "recommended_review": recommended_review
        })

    # =========================================================================
    # LEVEL 1: DETERMINISTIC RULES
    # =========================================================================
    for f in features_list:
        tx_id = f["id"]
        amt = f["amount"]
        ledger = f["ledger"]
        party = f["party"]
        date_str = f["date_str"]
        desc = f["description"]
        voucher = f["voucher"]
        is_we = f["is_weekend"]
        is_me = f["is_month_end"]
        is_qe = f["is_quarter_end"]

        # L1.1 Statutory Cash Limits: Section 40A(3) (> ₹10,000) & Section 269ST (>= ₹2,00,000)
        is_cash_head = any(k in ledger.lower() or k in desc.lower() for k in ["cash", "petty cash", "currency"])
        if is_cash_head and f["credit"] > 10000.0: # Cash payment
            add_anomaly_candidate(
                tx_id=tx_id,
                level="LEVEL 1: Deterministic",
                pattern_type="Statutory Cash Payment Limit Breach (Section 40A(3))",
                base_score=94.0,
                evidence={
                    "voucher_no": voucher,
                    "date": date_str,
                    "ledger": ledger,
                    "party_name": party,
                    "cash_payment_amount": f["credit"],
                    "statutory_threshold": 10000.0,
                    "excess_amount": f["credit"] - 10000.0,
                    "statutory_clause": "Section 40A(3) of Income Tax Act / Clause 21(d) Form 3CD"
                },
                explanation=f"Cash payment of ₹{f['credit']:,.2f} to '{party}' exceeds the statutory ₹10,000 threshold under Section 40A(3), disallowing 100% of the expenditure unless covered under Rule 6DD.",
                recommended_review="Inspect payment voucher, check payee identity, and verify whether the payment falls under any exceptions specified in Rule 6DD of Income Tax Rules 1962.",
                severity_override="CRITICAL"
            )
        elif is_cash_head and f["debit"] >= 200000.0: # Cash receipt
            add_anomaly_candidate(
                tx_id=tx_id,
                level="LEVEL 1: Deterministic",
                pattern_type="Statutory Cash Receipt Limit Breach (Section 269ST)",
                base_score=96.0,
                evidence={
                    "voucher_no": voucher,
                    "date": date_str,
                    "ledger": ledger,
                    "party_name": party,
                    "cash_receipt_amount": f["debit"],
                    "statutory_threshold": 200000.0,
                    "statutory_clause": "Section 269ST of Income Tax Act (100% penalty under Section 271DA)"
                },
                explanation=f"Cash receipt of ₹{f['debit']:,.2f} meets/exceeds the ₹2,00,000 limit under Section 269ST, attracting equal penalty under Section 271DA.",
                recommended_review="Review underlying sales/contract agreement and verify whether receipt relates to a single transaction or aggregate daily event from one person.",
                severity_override="CRITICAL"
            )

        # L1.2 Repeated Round-Number Transactions (multiples of ₹50,000, ₹1,00,000, ₹5,00,000)
        if amt >= 50000.0 and (amt % 50000.0 == 0):
            # Check if there are other round number transactions in this ledger
            round_count_in_ledger = sum(1 for a in ledger_amounts.get(ledger, []) if a >= 50000.0 and a % 50000.0 == 0)
            if round_count_in_ledger >= 2:
                add_anomaly_candidate(
                    tx_id=tx_id,
                    level="LEVEL 1: Deterministic",
                    pattern_type="Repeated Round-Number Transactions",
                    base_score=72.0 + min(15.0, round_count_in_ledger * 2),
                    evidence={
                        "voucher_no": voucher,
                        "date": date_str,
                        "ledger": ledger,
                        "party_name": party,
                        "exact_amount": amt,
                        "round_divisor": 50000,
                        "round_entries_in_ledger": round_count_in_ledger
                    },
                    explanation=f"Transaction of exact round figure ₹{amt:,.2f} recorded in '{ledger}'. The ledger contains {round_count_in_ledger} repetitive round-number postings, which deviate from typical itemized commercial billings.",
                    recommended_review="Inspect supporting tax invoices to verify if round figures represent lump-sum ad-hoc provisioning or unbilled supplier advances without milestone reconciliation.",
                    severity_override="MEDIUM"
                )

        # L1.3 Significant Month-End / Cutoff Activity
        if is_me and amt >= 75000.0:
            add_anomaly_candidate(
                tx_id=tx_id,
                level="LEVEL 1: Deterministic",
                pattern_type="Significant Month-End Activity / Cutoff Clustering",
                base_score=70.0 + (12.0 if is_qe else 0.0),
                evidence={
                    "voucher_no": voucher,
                    "date": date_str,
                    "day_of_month": f["day_of_month"],
                    "is_quarter_end": bool(is_qe),
                    "ledger": ledger,
                    "party_name": party,
                    "amount": amt
                },
                explanation=f"High-value entry of ₹{amt:,.2f} booked on {date_str} during month-end cutoff window ({'Quarter-End' if is_qe else 'Month-End'}). High concentration of entries at period closing poses cutoff timing risk under SA 500 / SA 240.",
                recommended_review="Verify delivery challans, goods receipt notes (GRN), and invoice dates around cutoff to ensure revenue/expense is recorded in the correct accounting period.",
                severity_override="HIGH" if is_qe else "MEDIUM"
            )

        # L1.4 Unusual Journal Entry (Manual JVs with round numbers, off-hours/weekends, or missing party)
        is_jv = voucher.upper().startswith("JV") or "journal" in (t.get("transaction_type") or "").lower() or voucher.upper().startswith("V-")
        if is_jv and is_we and amt >= 25000.0:
            add_anomaly_candidate(
                tx_id=tx_id,
                level="LEVEL 1: Deterministic",
                pattern_type="Unusual Journal Entry / Off-Hour Adjustments",
                base_score=78.0,
                evidence={
                    "voucher_no": voucher,
                    "date": date_str,
                    "day_name": "Sunday" if f["day_of_week"] == 6 else "Saturday",
                    "ledger": ledger,
                    "party_name": party,
                    "amount": amt,
                    "description": desc or "No description provided"
                },
                explanation=f"Manual journal adjustment of ₹{amt:,.2f} was posted on a weekend ({'Sunday' if f['day_of_week'] == 6 else 'Saturday'}). Manual JVs recorded outside standard operational hours require heightened scrutiny for management override of controls.",
                recommended_review="Verify approval matrix, authorizer signatures, and supporting justification memorandum for weekend journal entries.",
                severity_override="HIGH"
            )

        # L1.5 Unusual Vendor Activity: First-time high-value vendor (> ₹1,50,000) or high single-transaction concentration
        if f["party_count"] == 1 and amt >= 150000.0 and party not in ["Direct / Cash", "Direct", "Cash"]:
            add_anomaly_candidate(
                tx_id=tx_id,
                level="LEVEL 1: Deterministic",
                pattern_type="Unusual Vendor Activity / First-Time Outlier",
                base_score=76.0,
                evidence={
                    "party_name": party,
                    "voucher_no": voucher,
                    "date": date_str,
                    "transaction_amount": amt,
                    "total_party_transactions": 1,
                    "historical_volume": f"₹{amt:,.2f} (Single isolated transaction)"
                },
                explanation=f"Counterparty '{party}' has only 1 recorded transaction in the entire engagement, for a high value of ₹{amt:,.2f}. Isolated single-transaction high-value vendors warrant vendor onboarding verification.",
                recommended_review="Perform KYC and vendor master verification: inspect PAN/GSTIN registration, vendor onboarding approval, and physical proof of goods/services delivery.",
                severity_override="HIGH"
            )

    # =========================================================================
    # LEVEL 2: STATISTICAL ANALYSIS
    # =========================================================================
    # L2.1 Ledger Z-Score Spikes & Univariate Outliers
    for f in features_list:
        tx_id = f["id"]
        amt = f["amount"]
        ledger = f["ledger"]
        l_mean = f["ledger_mean"]
        l_std = f["ledger_std"]
        l_cnt = f["ledger_count"]

        if l_cnt >= 4 and l_std > 0 and amt > 0:
            z_score = (amt - l_mean) / l_std
            threshold = 1.8 if l_cnt < 8 else 2.5
            if z_score >= threshold and (amt >= 2.0 * l_mean or amt >= 50000.0):
                add_anomaly_candidate(
                    tx_id=tx_id,
                    level="LEVEL 2: Statistical",
                    pattern_type="Unusually Large Transaction (Z-Score Outlier)",
                    base_score=min(95.0, 70.0 + z_score * 8.0),
                    evidence={
                        "voucher_no": f["voucher"],
                        "date": f["date_str"],
                        "ledger": ledger,
                        "transaction_amount": amt,
                        "ledger_mean": round(l_mean, 2),
                        "ledger_std": round(l_std, 2),
                        "z_score": round(z_score, 2),
                        "variance_above_mean": round(amt - l_mean, 2),
                        "sample_size": l_cnt
                    },
                    explanation=f"Transaction amount ₹{amt:,.2f} in '{ledger}' is {z_score:.2f} standard deviations above the ledger baseline (Mean: ₹{l_mean:,.2f} ± ₹{l_std:,.2f}). Statistically, fewer than 0.5% of regular operational entries reach this variance.",
                    recommended_review="Inspect underlying contract or purchase order to verify whether this represents capital expenditure erroneously classified as revenue expense.",
                    severity_override="CRITICAL" if z_score >= 4.0 else "HIGH"
                )

        # L2.2 Global IQR Outlier Analysis
        if amt >= global_extreme_iqr_cutoff and amt >= 100000.0:
            add_anomaly_candidate(
                tx_id=tx_id,
                level="LEVEL 2: Statistical",
                pattern_type="Unusually Large Transaction (Extreme IQR Outlier)",
                base_score=84.0,
                evidence={
                    "voucher_no": f["voucher"],
                    "date": f["date_str"],
                    "ledger": ledger,
                    "amount": amt,
                    "global_q75": round(global_q75, 2),
                    "global_iqr": round(global_iqr, 2),
                    "iqr_upper_bound": round(global_extreme_iqr_cutoff, 2)
                },
                explanation=f"Transaction value ₹{amt:,.2f} exceeds the global engagement IQR extreme threshold (Q3 + 3.0*IQR = ₹{global_extreme_iqr_cutoff:,.2f}).",
                recommended_review="Perform full substantive substantive testing on this voucher including management authorization and physical asset/delivery verification.",
                severity_override="HIGH"
            )

    # L2.3 Sudden Monthly Expense Surges by Ledger Category
    # Check if a monthly total for a ledger surges by >= 100% or >= 3x compared to other months
    ledger_month_buckets: Dict[str, Dict[str, float]] = {}
    for (ledg, m_key), tot in monthly_ledger_totals.items():
        ledger_month_buckets.setdefault(ledg, {})[m_key] = tot

    for ledg, months_dict in ledger_month_buckets.items():
        if len(months_dict) >= 2:
            m_totals = list(months_dict.values())
            m_mean = float(np.mean(m_totals))
            for m_key, m_tot in months_dict.items():
                if m_tot >= 100000.0 and (m_tot >= 2.5 * m_mean or m_tot >= 300000.0) and len(m_totals) >= 3:
                    # Find highest transaction in that surge month
                    surge_txs = [f for f in features_list if f["ledger"] == ledg and f["date_str"].startswith(m_key)]
                    if surge_txs:
                        top_surge_f = max(surge_txs, key=lambda x: x["amount"])
                        add_anomaly_candidate(
                            tx_id=top_surge_f["id"],
                            level="LEVEL 2: Statistical",
                            pattern_type="Sudden Increase in Expense / Category Surge",
                            base_score=78.0,
                            evidence={
                                "ledger": ledg,
                                "surge_month": m_key,
                                "month_total": m_tot,
                                "average_monthly_total": round(m_mean, 2),
                                "surge_multiplier": round(m_tot / max(1.0, m_mean), 2),
                                "top_transaction_voucher": top_surge_f["voucher"],
                                "top_transaction_amount": top_surge_f["amount"]
                            },
                            explanation=f"Ledger '{ledg}' experienced a significant monthly surge in {m_key} totaling ₹{m_tot:,.2f} ({m_tot/max(1.0, m_mean):.1f}x of the monthly average ₹{m_mean:,.2f}).",
                            recommended_review="Perform month-over-month analytical review (SA 520) and examine leading drivers behind the category expense spike.",
                            severity_override="HIGH"
                        )

    # L2.4 Unusual Number of Transactions / Daily Velocity Spikes
    mean_daily_count = float(np.mean(list(daily_counts.values()))) if daily_counts else 1.0
    for d_str, count in daily_counts.items():
        if count >= 6 and count >= 3.0 * mean_daily_count:
            # Find transactions on this spike date
            day_txs = [f for f in features_list if f["date_str"] == d_str]
            for d_f in day_txs[:2]: # top 2 samples on that date
                add_anomaly_candidate(
                    tx_id=d_f["id"],
                    level="LEVEL 2: Statistical",
                    pattern_type="Unusual Number of Transactions / Velocity Spike",
                    base_score=70.0 + min(15.0, (count / max(1.0, mean_daily_count)) * 3),
                    evidence={
                        "date": d_str,
                        "transactions_on_date": count,
                        "average_daily_transactions": round(mean_daily_count, 1),
                        "velocity_spike_ratio": round(count / max(1.0, mean_daily_count), 2),
                        "sample_voucher": d_f["voucher"]
                    },
                    explanation=f"High transaction volume burst on {d_str} ({count} postings recorded vs daily baseline average of {mean_daily_count:.1f}). Batch posting bursts often represent manual backlog dumps.",
                    recommended_review="Verify whether the batch dumping represents delayed month-end recording or automated recurring payroll/vendor batch processing.",
                    severity_override="MEDIUM"
                )

    # =========================================================================
    # LEVEL 3: LOCAL MACHINE LEARNING (Isolation Forest, LOF, DBSCAN)
    # =========================================================================
    if len(features_list) >= 8:
        # Build multidimensional feature matrix X
        # Features: [log_amount, log_debit, log_credit, day_of_week, day_of_month, is_weekend, is_month_end, norm_ledger_freq, norm_party_freq]
        X_rows = []
        for f in features_list:
            X_rows.append([
                f["log_amount"],
                f["log_debit"],
                f["log_credit"],
                float(f["day_of_week"]),
                float(f["day_of_month"]),
                float(f["is_weekend"]),
                float(f["is_month_end"]),
                float(np.log1p(f["ledger_count"])),
                float(np.log1p(f["party_count"]))
            ])
        
        X = np.array(X_rows, dtype=np.float64)

        # Standardize features for distance-based models (LOF, DBSCAN)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # 1. Isolation Forest (Tree-based partition depth)
        try:
            iso = IsolationForest(contamination=0.08, random_state=42, n_estimators=100)
            iso_preds = iso.fit_predict(X)
            iso_scores = iso.decision_function(X) # lower score = more anomalous
            
            for i, pred in enumerate(iso_preds):
                if pred == -1: # Outlier
                    f = features_list[i]
                    # Score mapping: negative decision score to 70-98 range
                    dec_val = float(-iso_scores[i])
                    iso_anomaly_score = min(98.0, max(70.0, round(70.0 + dec_val * 85.0, 1)))
                    
                    add_anomaly_candidate(
                        tx_id=f["id"],
                        level="LEVEL 3: Machine Learning",
                        pattern_type="Behavior Significantly Different from Historical Pattern (Isolation Forest)",
                        base_score=iso_anomaly_score,
                        evidence={
                            "algorithm": "Isolation Forest (Scikit-Learn)",
                            "tree_decision_score": round(dec_val, 4),
                            "log_amount": round(f["log_amount"], 2),
                            "amount": f["amount"],
                            "ledger": f["ledger"],
                            "party": f["party"],
                            "date": f["date_str"],
                            "day_of_week": f["day_of_week"],
                            "is_month_end": bool(f["is_month_end"])
                        },
                        explanation=f"Multivariate Isolation Forest identified that this transaction of ₹{f['amount']:,.2f} in '{f['ledger']}' is isolated with very few tree partitions (Anomaly Score: {iso_anomaly_score}/100), exhibiting multidimensional divergence from normal ledger and temporal distributions.",
                        recommended_review="Inspect supporting documentation to evaluate why the combined attributes (amount, counterparty, and posting date) diverge from baseline clusters.",
                        severity_override="HIGH" if iso_anomaly_score >= 82.0 else "MEDIUM"
                    )
        except Exception:
            pass

        # 2. Local Outlier Factor (LOF Density Estimation)
        try:
            n_neighbors = min(15, max(3, len(X) - 1))
            lof = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=0.06)
            lof_preds = lof.fit_predict(X_scaled)
            lof_factors = -lof.negative_outlier_factor_ # factor > 1.5 indicates outlier
            
            for i, pred in enumerate(lof_preds):
                if pred == -1 and lof_factors[i] > 1.35:
                    f = features_list[i]
                    lof_score = min(96.0, max(72.0, round(65.0 + (lof_factors[i] - 1.0) * 35.0, 1)))
                    
                    add_anomaly_candidate(
                        tx_id=f["id"],
                        level="LEVEL 3: Machine Learning",
                        pattern_type="Local Density Outlier (Local Outlier Factor)",
                        base_score=lof_score,
                        evidence={
                            "algorithm": "Local Outlier Factor (LOF)",
                            "local_outlier_factor": round(float(lof_factors[i]), 3),
                            "k_neighbors": n_neighbors,
                            "amount": f["amount"],
                            "ledger": f["ledger"],
                            "party": f["party"],
                            "date": f["date_str"]
                        },
                        explanation=f"Local Outlier Factor analysis indicates this transaction is located in a significantly sparser density region (LOF = {lof_factors[i]:.2f}) relative to its {n_neighbors} nearest neighbor transactions.",
                        recommended_review="Verify whether the counterparty transaction terms, payment methods, or voucher classifications are unique in this ledger group.",
                        severity_override="HIGH" if lof_score >= 80.0 else "MEDIUM"
                    )
        except Exception:
            pass

        # 3. DBSCAN (Spatial Clustering Noise Detection)
        try:
            if len(X_scaled) >= 12:
                dbscan = DBSCAN(eps=1.8, min_samples=2)
                db_labels = dbscan.fit_predict(X_scaled)
                
                for i, label in enumerate(db_labels):
                    if label == -1: # Noise point
                        f = features_list[i]
                        add_anomaly_candidate(
                            tx_id=f["id"],
                            level="LEVEL 3: Machine Learning",
                            pattern_type="Spatial Cluster Noise Outlier (DBSCAN)",
                            base_score=75.0,
                            evidence={
                                "algorithm": "DBSCAN Density-Based Clustering",
                                "cluster_label": -1,
                                "amount": f["amount"],
                                "ledger": f["ledger"],
                                "party": f["party"],
                                "date": f["date_str"]
                            },
                            explanation=f"DBSCAN spatial clustering classified this record as a discrete noise point (Cluster -1), unable to be grouped into any standard operational cluster.",
                            recommended_review="Perform targeted substantive verification on the transaction's economic substance and commercial justification.",
                            severity_override="MEDIUM"
                        )
        except Exception:
            pass

    # =========================================================================
    # Benford's Law Summary
    # =========================================================================
    benford_mad, benford_conf, benford_dist = calculate_benford_mad(all_amounts)

    # Sort candidates by Anomaly Score descending
    anomaly_candidates.sort(key=lambda x: x["anomaly_score"], reverse=True)

    # Format structured output with unique, immutable Anomaly ID tied to transaction ID and pattern
    formatted_anomalies: List[Dict[str, Any]] = []

    for c in anomaly_candidates:
        pattern_hash = hashlib.sha256(c["pattern_type"].encode("utf-8")).hexdigest()[:6].upper()
        anom_id = f"ANOM-TX{c['transaction_id']}-{pattern_hash}"

        tx_obj = tx_by_id.get(c["transaction_id"], {})
        
        # Check review status
        rev_info = reviews_map.get(anom_id, {})
        status = rev_info.get("status", "Open")
        auditor_comment = rev_info.get("auditor_comment", "")
        ai_memo = rev_info.get("ai_memo", "")
        reviewed_by = rev_info.get("reviewed_by")
        reviewed_at = rev_info.get("reviewed_at")

        formatted_anomalies.append({
            "anomaly_id": anom_id,
            "transaction_id": c["transaction_id"],
            "level": c["level"],
            "pattern_type": c["pattern_type"],
            "anomaly_score": c["anomaly_score"],
            "severity": c["severity"],
            "status": status,
            "auditor_comment": auditor_comment,
            "ai_memo": ai_memo,
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            "evidence": c["evidence"],
            "explanation": c["explanation"],
            "recommended_review": c["recommended_review"],
            "transaction": {
                "id": tx_obj.get("id"),
                "date": tx_obj.get("date"),
                "voucher_no": tx_obj.get("voucher_no") or "—",
                "invoice_no": tx_obj.get("invoice_no") or "—",
                "reference_no": tx_obj.get("reference_no") or "—",
                "ledger": tx_obj.get("ledger") or "General",
                "party_name": tx_obj.get("party_name") or "—",
                "debit": float(tx_obj.get("debit") or 0.0),
                "credit": float(tx_obj.get("credit") or 0.0),
                "amount": float(tx_obj.get("amount") or 0.0),
                "description": tx_obj.get("description") or "—"
            }
        })

    # Summary Metrics
    crit_count = sum(1 for a in formatted_anomalies if a["severity"] == "CRITICAL")
    high_count = sum(1 for a in formatted_anomalies if a["severity"] == "HIGH")
    med_count = sum(1 for a in formatted_anomalies if a["severity"] == "MEDIUM")
    low_count = sum(1 for a in formatted_anomalies if a["severity"] == "LOW")

    l1_count = sum(1 for a in formatted_anomalies if "LEVEL 1" in a["level"])
    l2_count = sum(1 for a in formatted_anomalies if "LEVEL 2" in a["level"])
    l3_count = sum(1 for a in formatted_anomalies if "LEVEL 3" in a["level"])

    rev_count = sum(1 for a in formatted_anomalies if a["status"] != "Open")
    open_count = sum(1 for a in formatted_anomalies if a["status"] == "Open")

    conn.close()

    return {
        "engagement_id": engagement_id,
        "total_transactions": total_tx,
        "summary": {
            "total_anomalies": len(formatted_anomalies),
            "critical_count": crit_count,
            "high_count": high_count,
            "medium_count": med_count,
            "low_count": low_count,
            "level_1_deterministic": l1_count,
            "level_2_statistical": l2_count,
            "level_3_ml": l3_count,
            "reviewed_count": rev_count,
            "open_count": open_count
        },
        "benford_analysis": {
            "mad": round(benford_mad, 4),
            "conformity": benford_conf,
            "distribution": benford_dist
        },
        "anomalies": formatted_anomalies
    }

def update_anomaly_review(engagement_id: int, anomaly_id: str, status: str, comment: str, user_name: str) -> Dict[str, Any]:
    """Updates auditor review decision and comments for an anomaly."""
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Fetch current anomaly details
    data = detect_all_anomalies(engagement_id)
    target = next((a for a in data["anomalies"] if a["anomaly_id"] == anomaly_id), None)
    if not target:
        conn.close()
        raise ValueError(f"Anomaly '{anomaly_id}' not found")

    conn.execute("""
        INSERT INTO anomaly_reviews (
            engagement_id, anomaly_id, transaction_id, pattern_type, level,
            anomaly_score, severity, status, auditor_comment, reviewed_by, reviewed_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(engagement_id, anomaly_id) DO UPDATE SET
            status = excluded.status,
            auditor_comment = excluded.auditor_comment,
            reviewed_by = excluded.reviewed_by,
            reviewed_at = excluded.reviewed_at
    """, (
        engagement_id, anomaly_id, target["transaction_id"], target["pattern_type"], target["level"],
        target["anomaly_score"], target["severity"], status, comment, user_name, now_str, now_str
    ))

    # Audit log
    conn.execute("""
        INSERT INTO audit_logs (username, action, entity_type, entity_id, details, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_name, f"Anomaly {anomaly_id} review status updated to '{status}'", "anomaly", engagement_id,
        f"Auditor marked {anomaly_id} ({target['pattern_type']}) as '{status}'. Comment: {comment or 'None'}", now_str
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "anomaly_id": anomaly_id,
        "status": status,
        "auditor_comment": comment,
        "reviewed_by": user_name,
        "reviewed_at": now_str
    }

def generate_ai_anomaly_explanation(engagement_id: int, anomaly_id: str) -> Dict[str, Any]:
    """Generates an in-depth CA-oriented AI Working Paper Memorandum explaining why the anomaly occurred."""
    data = detect_all_anomalies(engagement_id)
    target = next((a for a in data["anomalies"] if a["anomaly_id"] == anomaly_id), None)
    if not target:
        raise ValueError(f"Anomaly '{anomaly_id}' not found")

    tx = target["transaction"]
    ev = target["evidence"]
    pat = target["pattern_type"]
    sev = target["severity"]
    score = target["anomaly_score"]
    level = target["level"]

    memo = f"""
================================================================================
FINAUDITPRO — AUDIT WORKING PAPER & AI ANOMALY MEMORANDUM
Reference ID: {anomaly_id} | Risk Score: {score}/100 | Severity: {sev}
Detection Level: {level}
Pattern Identified: {pat}
================================================================================

1. PROFESSIONAL AUDIT SAFEGUARD:
   {AUDIT_DISCLAIMER}
   This finding represents an empirical statistical/rule-based divergence requiring
   substantive auditor inquiry and does NOT constitute a conclusive determination of fraud.

2. TARGET TRANSACTION ATTRIBUTES:
   - Transaction ID: #{tx['id']}
   - Date of Posting: {tx['date']}
   - Voucher Number: {tx['voucher_no']}
   - Invoice Reference: {tx['invoice_no']}
   - Ledger Account: {tx['ledger']}
   - Counterparty / Payee: {tx['party_name']}
   - Financial Value: ₹{tx['amount']:,.2f} (Debit: ₹{tx['debit']:,.2f} | Credit: ₹{tx['credit']:,.2f})
   - Voucher Narration: {tx['description']}

3. STATISTICAL & RULE EVIDENCE ANALYSIS:
"""
    for k, v in ev.items():
        memo += f"   • {k.replace('_', ' ').title()}: {v}\n"

    memo += f"""
4. STATUTORY & ACCOUNTING STANDARD IMPLICATIONS:
   Under Standards on Auditing (SA 240 - The Auditor's Responsibilities Relating to Fraud,
   SA 315 - Identifying and Assessing Risks of Material Misstatement, and SA 520 - Analytical
   Procedures), unusual transactions displaying {pat.lower()} represent heightened inherent
   and control risks.

5. ACTIONABLE SUBSTANTIVE AUDIT PROCEDURES:
   {target['recommended_review']}

6. DOCUMENTATION & WORKING PAPER CITATION:
   - Audit WP Code: WP-ANOM-{anomaly_id.replace('-', '_')}
   - Prepared By: FinAuditPro Hybrid AI Engine
   - Reviewer Sign-Off: Pending Lead Auditor Sign-Off
================================================================================
"""
    memo_str = memo.strip()

    # Save to database
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
        INSERT INTO anomaly_reviews (
            engagement_id, anomaly_id, transaction_id, pattern_type, level,
            anomaly_score, severity, status, ai_memo, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?)
        ON CONFLICT(engagement_id, anomaly_id) DO UPDATE SET
            ai_memo = excluded.ai_memo
    """, (
        engagement_id, anomaly_id, target["transaction_id"], target["pattern_type"], target["level"],
        score, sev, memo_str, now_str
    ))
    conn.commit()
    conn.close()

    return {
        "anomaly_id": anomaly_id,
        "ai_memo": memo_str,
        "pattern_type": pat,
        "severity": sev,
        "anomaly_score": score
    }

def generate_anomaly_csv_report(engagement_id: int) -> str:
    """Generates a downloadable CSV report for all detected anomalies in an engagement."""
    data = detect_all_anomalies(engagement_id)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["FinAuditPro - AI-Assisted Anomaly Detection Audit Report"])
    writer.writerow(["Engagement ID", str(engagement_id)])
    writer.writerow(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow(["Total Transactions Analyzed", str(data["total_transactions"])])
    writer.writerow(["Total Anomalies Detected", str(data["summary"]["total_anomalies"])])
    writer.writerow(["Critical Severity", str(data["summary"]["critical_count"])])
    writer.writerow(["High Severity", str(data["summary"]["high_count"])])
    writer.writerow(["Medium Severity", str(data["summary"]["medium_count"])])
    writer.writerow(["Low Severity", str(data["summary"]["low_count"])])
    writer.writerow([])

    writer.writerow([
        "Anomaly ID", "Severity", "Anomaly Score", "Level", "Detected Pattern",
        "Date", "Voucher No", "Ledger", "Party Name", "Amount (INR)",
        "Evidence Details", "AI Explanation", "Recommended Review",
        "Review Status", "Auditor Comment", "Reviewed By", "Reviewed At"
    ])

    for a in data["anomalies"]:
        tx = a["transaction"]
        ev_str = json.dumps(a["evidence"])
        writer.writerow([
            a["anomaly_id"],
            a["severity"],
            f"{a['anomaly_score']:.1f}",
            a["level"],
            a["pattern_type"],
            tx["date"],
            tx["voucher_no"],
            tx["ledger"],
            tx["party_name"],
            f"{tx['amount']:.2f}",
            ev_str,
            a["explanation"],
            a["recommended_review"],
            a["status"],
            a["auditor_comment"],
            a["reviewed_by"] or "—",
            a["reviewed_at"] or "—"
        ])

    return output.getvalue()
