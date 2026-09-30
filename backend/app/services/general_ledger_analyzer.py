import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from backend.app.database import get_db_connection

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str or not str(date_str).strip():
        return None
    try:
        return datetime.strptime(str(date_str).strip()[:10], "%Y-%m-%d")
    except Exception:
        return None

def analyze_general_ledger(
    engagement_id: int,
    ledger: Optional[str] = None,
    party: Optional[str] = None,
    voucher_no: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    min_debit: Optional[float] = None,
    max_debit: Optional[float] = None,
    min_credit: Optional[float] = None,
    max_credit: Optional[float] = None,
    anomaly_rule: Optional[str] = None
) -> Dict[str, Any]:
    """
    Performs comprehensive 13-point deterministic General Ledger analysis and anomaly detection.
    Returns structured anomaly cards, summary metrics, and full transaction records.
    Never declares fraud; strictly labels as 'Requires review' / 'Potential anomaly'.
    """
    conn = get_db_connection()

    # 1. Fetch engagement metadata for period boundaries
    eng = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    period_start = eng["period_start"] if eng and eng["period_start"] else None
    period_end = eng["period_end"] if eng and eng["period_end"] else None
    fy = eng["financial_year"] if eng else "2024-25"

    dt_period_start = parse_date(period_start)
    dt_period_end = parse_date(period_end)

    # If period boundaries not set, default from financial year e.g. "2024-25" -> 2024-04-01 to 2025-03-31
    if not dt_period_start or not dt_period_end:
        try:
            start_yr = int(fy.split("-")[0])
            dt_period_start = datetime(start_yr, 4, 1)
            dt_period_end = datetime(start_yr + 1, 3, 31)
        except Exception:
            dt_period_start = datetime(2024, 4, 1)
            dt_period_end = datetime(2025, 3, 31)

    # 2. Fetch all transactions for this engagement with filters
    query = """
        SELECT * FROM transactions
        WHERE engagement_id = ?
    """
    params = [engagement_id]

    if ledger and ledger != "All" and ledger.strip():
        query += " AND ledger = ?"
        params.append(ledger.strip())
    if party and party.strip():
        query += " AND party_name LIKE ?"
        params.append(f"%{party.strip()}%")
    if voucher_no and voucher_no.strip():
        query += " AND voucher_no LIKE ?"
        params.append(f"%{voucher_no.strip()}%")
    if search and search.strip():
        term = f"%{search.strip()}%"
        query += " AND (description LIKE ? OR voucher_no LIKE ? OR invoice_no LIKE ? OR party_name LIKE ? OR ledger LIKE ?)"
        params.extend([term, term, term, term, term])
    if start_date and start_date.strip():
        query += " AND date >= ?"
        params.append(start_date.strip())
    if end_date and end_date.strip():
        query += " AND date <= ?"
        params.append(end_date.strip())
    if min_amount is not None:
        query += " AND (amount >= ? OR debit >= ? OR credit >= ?)"
        params.extend([min_amount, min_amount, min_amount])
    if max_amount is not None:
        query += " AND (amount <= ? AND (debit <= ? OR credit <= ?))"
        params.extend([max_amount, max_amount, max_amount])
    if min_debit is not None:
        query += " AND debit >= ?"
        params.append(min_debit)
    if max_debit is not None:
        query += " AND debit <= ?"
        params.append(max_debit)
    if min_credit is not None:
        query += " AND credit >= ?"
        params.append(min_credit)
    if max_credit is not None:
        query += " AND credit <= ?"
        params.append(max_credit)

    query += " ORDER BY date ASC, id ASC"
    rows = conn.execute(query, tuple(params)).fetchall()
    transactions = [dict(r) for r in rows]

    # Compute running balances per ledger
    running_balance_map: Dict[str, float] = {}
    for t in transactions:
        led = t.get("ledger") or "General"
        dr = float(t.get("debit") or 0.0)
        cr = float(t.get("credit") or 0.0)
        prev = running_balance_map.get(led, 0.0)
        cur = round(prev + (dr - cr), 2)
        running_balance_map[led] = cur
        t["running_balance"] = cur

    # Calculate overall materiality & statistics
    amounts = [float(t.get("amount") or max(t.get("debit", 0.0), t.get("credit", 0.0))) for t in transactions if float(t.get("amount") or 0.0) > 0]
    total_volume = len(transactions)
    total_debit = round(sum(float(t.get("debit") or 0.0) for t in transactions), 2)
    total_credit = round(sum(float(t.get("credit") or 0.0) for t in transactions), 2)
    
    # 95th percentile for large transactions
    sorted_amounts = sorted(amounts)
    large_threshold = 500000.0
    if len(sorted_amounts) >= 10:
        p95_idx = int(len(sorted_amounts) * 0.95)
        large_threshold = max(200000.0, sorted_amounts[p95_idx])

    # 3. Anomaly Detection Engine (13 Checks)
    anomalies: List[Dict[str, Any]] = []

    # Helper maps for group checks
    duplicate_map: Dict[str, List[Dict[str, Any]]] = {}
    repeated_amount_map: Dict[str, List[Dict[str, Any]]] = {}
    voucher_map: Dict[str, List[Dict[str, Any]]] = {}
    ledger_daily_count: Dict[str, Dict[str, int]] = {}
    ledger_party_amounts: Dict[str, List[Dict[str, Any]]] = {}

    prev_dt = None
    prev_vch_num = None

    for idx, t in enumerate(transactions):
        dt = parse_date(t.get("date"))
        dr = float(t.get("debit") or 0.0)
        cr = float(t.get("credit") or 0.0)
        amt = float(t.get("amount") or max(dr, cr))
        vch = (t.get("voucher_no") or "").strip()
        led = (t.get("ledger") or "").strip()
        pty = (t.get("party_name") or "").strip()
        desc = (t.get("description") or "").strip().lower()

        # Grouping for duplicates: (date, ledger, party, debit, credit)
        dup_key = f"{t.get('date')}|{led.lower()}|{pty.lower()}|{dr}|{cr}"
        duplicate_map.setdefault(dup_key, []).append(t)

        # Grouping for repeated amount in same ledger: (ledger, amount)
        if amt > 5000:
            rep_key = f"{led.lower()}|{amt}"
            repeated_amount_map.setdefault(rep_key, []).append(t)

        # Grouping for vouchers
        if vch:
            voucher_map.setdefault(vch, []).append(t)

        # Grouping for daily velocity
        if t.get("date") and led:
            ledger_daily_count.setdefault(led, {}).setdefault(t.get("date"), 0)
            ledger_daily_count[led][t.get("date")] += 1

        # Grouping for reversal detection: (ledger, abs(dr-cr))
        rev_key = f"{led.lower()}|{amt}"
        ledger_party_amounts.setdefault(rev_key, []).append(t)

        # -------------------------------------------------------------
        # CHECK 3: Backdated Transactions
        # -------------------------------------------------------------
        is_backdated_keyword = any(kw in desc for kw in ["backdated", "prior period", "omitted entry", "delayed entry", "late posting"])
        # Check if created_at exists and is significantly after transaction date (> 60 days)
        created_at_dt = parse_date(t.get("created_at"))
        is_backdated_entry = False
        if is_backdated_keyword:
            is_backdated_entry = True
        elif created_at_dt and dt and (created_at_dt - dt).days > 60:
            is_backdated_entry = True

        if is_backdated_entry:
            anomalies.append({
                "transaction": t,
                "transaction_id": t["id"],
                "rule": "GL_03_BACKDATED_ENTRY",
                "rule_name": "Potential Backdated Transaction",
                "severity": "HIGH",
                "risk_score": 80,
                "reason": f"Transaction appears backdated or contains delayed posting indicators for ₹{amt:,.2f}.",
                "evidence": f"Voucher: #{vch or 'N/A'}, Date: {t.get('date')}, Narration: '{t.get('description') or ''}'",
                "recommended_review": "Inspect ERP audit logs, original timestamp of creation, and documentary evidence of authorization."
            })

        # -------------------------------------------------------------
        # CHECK 4: Weekend / Sunday Posting
        # -------------------------------------------------------------
        if dt and dt.weekday() == 6:  # Sunday
            anomalies.append({
                "transaction": t,
                "transaction_id": t["id"],
                "rule": "GL_04_WEEKEND_POSTING",
                "rule_name": "Sunday / Weekend Entry",
                "severity": "LOW",
                "risk_score": 45,
                "reason": f"Transaction recorded on a Sunday ({dt.strftime('%A, %d-%b-%Y')}). Weekend entries are non-routine for corporate entities.",
                "evidence": f"Voucher #{vch or 'N/A'}, Date: {t.get('date')}, Ledger: {led}, Amount: ₹{amt:,.2f}",
                "recommended_review": "Verify if transaction represents emergency operational expenditure or manual post-facto backdated entry."
            })

        # -------------------------------------------------------------
        # CHECK 5: Out of Period
        # -------------------------------------------------------------
        if dt:
            if dt < dt_period_start or dt > dt_period_end:
                anomalies.append({
                    "transaction": t,
                    "transaction_id": t["id"],
                    "rule": "GL_05_OUT_OF_PERIOD",
                    "rule_name": "Transaction Outside Engagement Period",
                    "severity": "HIGH",
                    "risk_score": 90,
                    "reason": f"Transaction date ({t.get('date')}) falls outside the active audit period ({dt_period_start.strftime('%Y-%m-%d')} to {dt_period_end.strftime('%Y-%m-%d')}).",
                    "evidence": f"Date: {t.get('date')}, Engagement Period: FY {fy}, Voucher: #{vch or 'N/A'}",
                    "recommended_review": "Check for period cutoff misstatements (SA 500 / SA 520) and verify journal voucher posting date."
                })

        # -------------------------------------------------------------
        # CHECK 6: Manual Journal Entries
        # -------------------------------------------------------------
        is_manual_kw = any(kw in desc for kw in ["adjustment", "transfer", "rectification", "manual jv", "provision", "year end", "diff", "closing"])
        is_jv_vch = vch.upper().startswith("JV") or "JOURNAL" in vch.upper() or "JV" in led.upper()
        if (is_manual_kw or is_jv_vch) and amt > 25000:
            anomalies.append({
                "transaction": t,
                "transaction_id": t["id"],
                "rule": "GL_06_MANUAL_JOURNAL",
                "rule_name": "Non-Routine Manual Journal Entry",
                "severity": "MEDIUM",
                "risk_score": 65,
                "reason": f"Manual journal adjustment entry identified with narration keyword or JV designation for ₹{amt:,.2f}.",
                "evidence": f"Voucher: #{vch or 'JV'}, Narration: '{t.get('description') or ''}', Amount: ₹{amt:,.2f}",
                "recommended_review": "Inspect journal voucher authorization, supporting calculation sheets, and senior management approval (SA 240)."
            })

        # -------------------------------------------------------------
        # CHECK 7: Large Transactions (Outliers)
        # -------------------------------------------------------------
        if amt >= large_threshold and amt > 200000:
            anomalies.append({
                "transaction": t,
                "transaction_id": t["id"],
                "rule": "GL_07_LARGE_TRANSACTION",
                "rule_name": "High-Value Outlier Transaction",
                "severity": "MEDIUM",
                "risk_score": 75,
                "reason": f"Transaction amount of ₹{amt:,.2f} exceeds the 95th percentile materiality threshold (₹{large_threshold:,.2f}).",
                "evidence": f"Amount: ₹{amt:,.2f}, Ledger: {led}, Party: {pty or 'N/A'}, Voucher: #{vch or 'N/A'}",
                "recommended_review": "Perform 100% substantive voucher inspection, verify bank remittance / cheque clearance, and check purchase order/contract."
            })

        # -------------------------------------------------------------
        # CHECK 8: Round-Number Transactions
        # -------------------------------------------------------------
        if amt >= 50000 and amt % 50000 == 0 and dr % 1 == 0 and cr % 1 == 0:
            if not ("bank" in led.lower() and "cash" in led.lower() and amt < 100000):
                anomalies.append({
                    "transaction": t,
                    "transaction_id": t["id"],
                    "rule": "GL_08_ROUND_NUMBER",
                    "rule_name": "Exact Round-Number Transaction",
                    "severity": "LOW",
                    "risk_score": 50,
                    "reason": f"Transaction is an exact round sum of ₹{amt:,.2f} (multiples of ₹50,000 / ₹1,00,000 with zero paise).",
                    "evidence": f"Amount: ₹{amt:,.2f}, Ledger: {led}, Narration: '{t.get('description') or ''}'",
                    "recommended_review": "Review invoice breakdown to ensure round amount is supported by itemized billing rather than arbitrary estimate."
                })

        # -------------------------------------------------------------
        # CHECK 11: Missing References
        # -------------------------------------------------------------
        if not vch and not t.get("invoice_no") and not t.get("reference_no") and amt > 10000:
            anomalies.append({
                "transaction": t,
                "transaction_id": t["id"],
                "rule": "GL_11_MISSING_REFERENCE",
                "rule_name": "Missing Voucher / Invoice Reference",
                "severity": "MEDIUM",
                "risk_score": 65,
                "reason": f"Transaction of ₹{amt:,.2f} in '{led}' is recorded without a voucher number, invoice number, or documentary reference.",
                "evidence": f"Txn ID: #{t['id']}, Date: {t.get('date')}, Amount: ₹{amt:,.2f}",
                "recommended_review": "Request source documentation from client to establish unbroken audit trail (SA 500)."
            })

    # -------------------------------------------------------------
    # CHECK 1: Duplicate Entries (Group Check)
    # -------------------------------------------------------------
    for k, dup_list in duplicate_map.items():
        if len(dup_list) > 1:
            for t in dup_list:
                amt = float(t.get("amount") or max(t.get("debit", 0.0), t.get("credit", 0.0)))
                other_ids = [str(x["id"]) for x in dup_list if x["id"] != t["id"]]
                anomalies.append({
                    "transaction": t,
                    "transaction_id": t["id"],
                    "rule": "GL_01_DUPLICATE_ENTRY",
                    "rule_name": "Potential Duplicate Entry",
                    "severity": "HIGH",
                    "risk_score": 85,
                    "reason": f"Identical date ({t.get('date')}), ledger ('{t.get('ledger')}'), party ('{t.get('party_name')}'), and amount (₹{amt:,.2f}) posted {len(dup_list)} times.",
                    "evidence": f"Matching Transaction IDs: #{', #'.join(other_ids)}, Voucher: #{t.get('voucher_no') or 'N/A'}",
                    "recommended_review": "Inspect supplier tax invoices and delivery challans to verify if multiple shipments occurred or if entry was duplicated."
                })

    # -------------------------------------------------------------
    # CHECK 2: Same Amount Repeated Unusually
    # -------------------------------------------------------------
    for k, rep_list in repeated_amount_map.items():
        if len(rep_list) >= 3:
            dates = [parse_date(x.get("date")) for x in rep_list if parse_date(x.get("date"))]
            if dates:
                date_span = (max(dates) - min(dates)).days
                if date_span <= 30:
                    for t in rep_list:
                        amt = float(t.get("amount") or max(t.get("debit", 0.0), t.get("credit", 0.0)))
                        anomalies.append({
                            "transaction": t,
                            "transaction_id": t["id"],
                            "rule": "GL_02_REPEATED_AMOUNT",
                            "rule_name": "Unusually Repeated Identical Amount",
                            "severity": "MEDIUM",
                            "risk_score": 70,
                            "reason": f"Exact amount of ₹{amt:,.2f} posted {len(rep_list)} times in '{t.get('ledger')}' within a span of {date_span} days.",
                            "evidence": f"Count: {len(rep_list)} occurrences, Total Volume: ₹{(amt * len(rep_list)):,.2f}",
                            "recommended_review": "Check for structured payments designed to avoid single-transaction threshold limits (Section 40A(3) / 269ST compliance)."
                        })

    # -------------------------------------------------------------
    # CHECK 9: Unusual Frequency / Daily Velocity Clustering
    # -------------------------------------------------------------
    for led_name, date_counts in ledger_daily_count.items():
        daily_counts = list(date_counts.values())
        avg_daily = sum(daily_counts) / len(daily_counts) if daily_counts else 1.0
        for d_str, cnt in date_counts.items():
            if cnt >= 5 and cnt >= (4 * avg_daily):
                clustered_txs = [t for t in transactions if t.get("ledger") == led_name and t.get("date") == d_str]
                for t in clustered_txs:
                    anomalies.append({
                        "transaction": t,
                        "transaction_id": t["id"],
                        "rule": "GL_09_UNUSUAL_FREQUENCY",
                        "rule_name": "Unusual Transaction Clustering / Velocity Spike",
                        "severity": "LOW",
                        "risk_score": 55,
                        "reason": f"Unusual velocity spike: {cnt} vouchers recorded on {d_str} in '{led_name}' (average baseline: {avg_daily:.1f}/day).",
                        "evidence": f"Ledger: {led_name}, Date: {d_str}, Vouchers on Date: {cnt}",
                        "recommended_review": "Verify if year-end or month-end batch entries were dumped without contemporaneous documentation."
                    })

    # -------------------------------------------------------------
    # CHECK 10: Reversal Entries / Cancellation Pairs
    # -------------------------------------------------------------
    for k, pair_list in ledger_party_amounts.items():
        debits = [t for t in pair_list if float(t.get("debit") or 0.0) > 0 and float(t.get("credit") or 0.0) == 0]
        credits = [t for t in pair_list if float(t.get("credit") or 0.0) > 0 and float(t.get("debit") or 0.0) == 0]
        if debits and credits:
            for d_tx in debits:
                for c_tx in credits:
                    d_dt = parse_date(d_tx.get("date"))
                    c_dt = parse_date(c_tx.get("date"))
                    if d_dt and c_dt and abs((c_dt - d_dt).days) <= 30:
                        amt = float(d_tx.get("debit") or 0.0)
                        anomalies.append({
                            "transaction": d_tx,
                            "transaction_id": d_tx["id"],
                            "rule": "GL_10_REVERSAL_ENTRY",
                            "rule_name": "Potential Entry Reversal / Cancellation Pair",
                            "severity": "MEDIUM",
                            "risk_score": 60,
                            "reason": f"Debit of ₹{amt:,.2f} on {d_tx.get('date')} matches Credit of ₹{amt:,.2f} on {c_tx.get('date')} in '{d_tx.get('ledger')}'.",
                            "evidence": f"Matching Voucher pair: #{d_tx.get('voucher_no')} (Dr) and #{c_tx.get('voucher_no')} (Cr)",
                            "recommended_review": "Inspect credit note, reason for invoice cancellation, and confirm tax reversal under Section 34 of CGST Act."
                        })
                        break

    # -------------------------------------------------------------
    # CHECK 12 & 13: Debit/Credit Without Corresponding Offset (One-Sided)
    # -------------------------------------------------------------
    for vch_no, vch_txs in voucher_map.items():
        vch_dr = sum(float(x.get("debit") or 0.0) for x in vch_txs)
        vch_cr = sum(float(x.get("credit") or 0.0) for x in vch_txs)
        vch_diff = round(abs(vch_dr - vch_cr), 2)
        if vch_diff > 0.01:
            for t in vch_txs:
                dr = float(t.get("debit") or 0.0)
                cr = float(t.get("credit") or 0.0)
                if dr > 0 and cr == 0:
                    anomalies.append({
                        "transaction": t,
                        "transaction_id": t["id"],
                        "rule": "GL_12_DEBIT_WITHOUT_CREDIT",
                        "rule_name": "One-Sided Debit / Unbalanced Voucher",
                        "severity": "HIGH",
                        "risk_score": 85,
                        "reason": f"Voucher #{vch_no} has total Debit of ₹{vch_dr:,.2f} but total Credit of ₹{vch_cr:,.2f} (Variance: ₹{vch_diff:,.2f}).",
                        "evidence": f"Voucher: #{vch_no}, Debit: ₹{dr:,.2f}, Voucher Total Dr: ₹{vch_dr:,.2f}, Total Cr: ₹{vch_cr:,.2f}",
                        "recommended_review": "Review original journal entry to locate omitted credit leg or import mapping truncation."
                    })
                elif cr > 0 and dr == 0:
                    anomalies.append({
                        "transaction": t,
                        "transaction_id": t["id"],
                        "rule": "GL_13_CREDIT_WITHOUT_DEBIT",
                        "rule_name": "One-Sided Credit / Unbalanced Voucher",
                        "severity": "HIGH",
                        "risk_score": 85,
                        "reason": f"Voucher #{vch_no} has total Credit of ₹{vch_cr:,.2f} but total Debit of ₹{vch_dr:,.2f} (Variance: ₹{vch_diff:,.2f}).",
                        "evidence": f"Voucher: #{vch_no}, Credit: ₹{cr:,.2f}, Voucher Total Cr: ₹{vch_cr:,.2f}, Total Dr: ₹{vch_dr:,.2f}",
                        "recommended_review": "Review original journal entry to locate omitted debit leg or import mapping truncation."
                    })

    # Filter anomalies by specific rule if requested
    if anomaly_rule and anomaly_rule != "ALL":
        anomalies = [a for a in anomalies if a["rule"] == anomaly_rule]

    # Deduplicate anomalies per transaction and rule
    seen_anom_keys = set()
    unique_anomalies = []
    for a in anomalies:
        k = f"{a['transaction_id']}_{a['rule']}"
        if k not in seen_anom_keys:
            seen_anom_keys.add(k)
            unique_anomalies.append(a)

    # Attach anomaly flags directly to transaction items (avoiding circular references)
    anom_by_tx = {}
    for a in unique_anomalies:
        anom_copy = {k: v for k, v in a.items() if k != "transaction"}
        anom_by_tx.setdefault(a["transaction_id"], []).append(anom_copy)

    for t in transactions:
        t["anomalies"] = anom_by_tx.get(t["id"], [])
        t["has_anomaly"] = len(t["anomalies"]) > 0

    # Ensure transaction field in anomalies does not hold circular reference to anomalies list
    for a in unique_anomalies:
        if isinstance(a.get("transaction"), dict):
            a["transaction"] = {k: v for k, v in a["transaction"].items() if k != "anomalies"}


    # Risk metrics summary
    crit_count = sum(1 for a in unique_anomalies if a["severity"] == "CRITICAL")
    high_count = sum(1 for a in unique_anomalies if a["severity"] == "HIGH")
    med_count = sum(1 for a in unique_anomalies if a["severity"] == "MEDIUM")
    low_count = sum(1 for a in unique_anomalies if a["severity"] == "LOW")

    # Group anomalies by rule for summary breakdown
    rule_breakdown = {}
    for a in unique_anomalies:
        r = a["rule"]
        r_name = a["rule_name"]
        if r not in rule_breakdown:
            rule_breakdown[r] = {
                "rule_code": r,
                "rule_name": r_name,
                "severity": a["severity"],
                "count": 0
            }
        rule_breakdown[r]["count"] += 1

    conn.close()

    return {
        "engagement_id": engagement_id,
        "total_transactions": total_volume,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "flagged_transactions_count": len(anom_by_tx),
        "total_anomalies_count": len(unique_anomalies),
        "large_transaction_threshold": large_threshold,
        "summary": {
            "critical_count": crit_count,
            "high_count": high_count,
            "medium_count": med_count,
            "low_count": low_count,
            "rule_breakdown": list(rule_breakdown.values())
        },
        "anomalies": unique_anomalies,
        "transactions": transactions
    }

