import re
import difflib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from backend.app.database import get_db_connection
from backend.app.utils.audit_logger import log_audit_event

def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    t = str(text).lower().strip()
    # Remove common legal prefixes / suffixes and punctuation
    t = re.sub(r'^(m/s\.?|mr\.?|ms\.?|shri|smt\.?)\s+', '', t)
    t = re.sub(r'\b(pvt\.?|private|ltd\.?|limited|llp|corp|corporation|inc\.?)\b', '', t)
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    return " ".join(t.split())

def normalize_code(code: Optional[str]) -> str:
    if not code:
        return ""
    return re.sub(r'[^a-zA-Z0-9]', '', str(code)).upper()

def string_similarity(s1: str, s2: str) -> float:
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    s1_clean = normalize_text(s1)
    s2_clean = normalize_text(s2)
    if s1_clean == s2_clean:
        return 1.0
    return difflib.SequenceMatcher(None, s1_clean, s2_clean).ratio()

def code_similarity(c1: str, c2: str) -> float:
    if not c1 and not c2:
        return 1.0
    if not c1 or not c2:
        return 0.0
    n1 = normalize_code(c1)
    n2 = normalize_code(c2)
    if n1 == n2 and len(n1) > 0:
        return 1.0
    return difflib.SequenceMatcher(None, n1, n2).ratio()

def extract_cheque_numbers(text: Optional[str]) -> List[int]:
    """Extracts 6-digit Indian bank cheque numbers from narration or reference strings."""
    if not text:
        return []
    # Match patterns like Cheque 102450, Chq No. 102450, CHQ-102450, or standalone 6 digits
    matches = re.findall(r'(?:chq|cheque|instrument|cq)[\s\.:#\-_]*(\d{6})\b|\b(\d{6})\b', str(text), re.IGNORECASE)
    nums = []
    for m in matches:
        val = m[0] or m[1]
        if val and len(val) == 6:
            try:
                nums.append(int(val))
            except ValueError:
                pass
    return nums

def extract_sequence_parts(val: Optional[str]) -> Optional[Tuple[str, int, str, int]]:
    """
    Extracts prefix, numeric integer, suffix, and integer string length from a code.
    Example: 'INV-2024-0042A' -> prefix='INV-2024-', num=42, suffix='A', pad_len=4
    """
    if not val:
        return None
    s = str(val).strip()
    match = re.search(r'^(.*?)(\d+)([^\d]*)$', s)
    if not match:
        return None
    prefix = match.group(1)
    num_str = match.group(2)
    suffix = match.group(3)
    num = int(num_str)
    return (prefix, num, suffix, len(num_str))

def detect_duplicates_and_gaps(engagement_id: int) -> Dict[str, Any]:
    """
    Executes full duplicate detection (exact, invoice, voucher, date+amount+party, reference, fuzzy)
    and sequence gap detection (invoices, vouchers, cheques) for an engagement.
    """
    conn = get_db_connection()
    
    # 1. Fetch transactions
    tx_rows = conn.execute("""
        SELECT id, date, ledger, party_name, debit, credit, amount, voucher_no, invoice_no, description, reference_no, account_group
        FROM transactions
        WHERE engagement_id = ?
        ORDER BY date ASC, id ASC
    """, (engagement_id,)).fetchall()

    txs = [dict(r) for r in tx_rows]
    total_tx = len(txs)

    # 2. Fetch existing reviews
    dup_reviews_map = {}
    dup_review_rows = conn.execute("""
        SELECT * FROM duplicate_group_reviews WHERE engagement_id = ?
    """, (engagement_id,)).fetchall()
    for r in dup_review_rows:
        dup_reviews_map[(r["group_code"], r["duplicate_transaction_id"])] = dict(r)

    gap_reviews_map = {}
    gap_review_rows = conn.execute("""
        SELECT * FROM missing_sequence_reviews WHERE engagement_id = ?
    """, (engagement_id,)).fetchall()
    for r in gap_review_rows:
        k = (r["sequence_type"], r["series_prefix"] or "", r["expected_from"] or "", r["expected_to"] or "")
        gap_reviews_map[k] = dict(r)

    conn.close()

    # -------------------------------------------------------------
    # PART A: DUPLICATE DETECTION
    # -------------------------------------------------------------
    duplicate_pairs: List[Dict[str, Any]] = []
    seen_pair_keys: Set[Tuple[int, int]] = set()

    def add_dup_pair(t1: Dict[str, Any], t2: Dict[str, Any], group_type: str, similarity_pct: float, reason: str):
        id_a = min(t1["id"], t2["id"])
        id_b = max(t1["id"], t2["id"])
        if id_a == id_b:
            return
        if (id_a, id_b) in seen_pair_keys:
            return
        seen_pair_keys.add((id_a, id_b))
        
        t_first = t1 if t1["id"] == id_a else t2
        t_second = t2 if t2["id"] == id_b else t1

        duplicate_pairs.append({
            "group_type": group_type,
            "similarity_pct": round(similarity_pct, 1),
            "detection_reason": reason,
            "tx_a": t_first,
            "tx_b": t_second
        })

    # A1. Exact duplicate (Same date, amount, debit, credit, ledger, party, voucher, invoice)
    exact_map: Dict[str, List[Dict[str, Any]]] = {}
    for t in txs:
        amt = round(float(t["amount"] or t["debit"] or t["credit"] or 0.0), 2)
        key = f"{t['date']}|{amt}|{t['ledger']}|{t['party_name']}|{t['voucher_no']}|{t['invoice_no']}"
        exact_map.setdefault(key, []).append(t)

    for k, group in exact_map.items():
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    add_dup_pair(
                        group[i], group[j],
                        "Exact Duplicate", 100.0,
                        "Exact duplicate across all transaction fields (Date, Amount, Ledger, Party, Voucher, Invoice)"
                    )

    # A2. Same Invoice Number (Non-empty)
    inv_map: Dict[str, List[Dict[str, Any]]] = {}
    for t in txs:
        inv = (t["invoice_no"] or "").strip().upper()
        if inv and len(inv) >= 3:
            inv_map.setdefault(inv, []).append(t)

    for inv, group in inv_map.items():
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    t1, t2 = group[i], group[j]
                    amt1 = float(t1["amount"] or 0.0)
                    amt2 = float(t2["amount"] or 0.0)
                    is_same_amt = abs(amt1 - amt2) < 0.01
                    add_dup_pair(
                        t1, t2,
                        "Same Invoice Number", 98.0 if is_same_amt else 92.0,
                        f"Same invoice number '{inv}' recorded across multiple entries" + (f" with identical amount (₹{amt1:,.2f})" if is_same_amt else "")
                    )

    # A3. Same Voucher Number in same Ledger / Party
    vouch_map: Dict[str, List[Dict[str, Any]]] = {}
    for t in txs:
        v = (t["voucher_no"] or "").strip().upper()
        if v and len(v) >= 2:
            key = f"{v}|{t['ledger']}"
            vouch_map.setdefault(key, []).append(t)

    for k, group in vouch_map.items():
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    t1, t2 = group[i], group[j]
                    add_dup_pair(
                        t1, t2,
                        "Same Voucher Number", 95.0,
                        f"Same voucher number '{t1['voucher_no']}' in ledger '{t1['ledger']}'"
                    )

    # A4. Same Date + Amount + Party Name
    date_amt_party_map: Dict[str, List[Dict[str, Any]]] = {}
    for t in txs:
        party = normalize_text(t["party_name"])
        amt = round(float(t["amount"] or t["debit"] or t["credit"] or 0.0), 2)
        if party and amt > 0:
            key = f"{t['date']}|{amt}|{party}"
            date_amt_party_map.setdefault(key, []).append(t)

    for k, group in date_amt_party_map.items():
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    t1, t2 = group[i], group[j]
                    add_dup_pair(
                        t1, t2,
                        "Same Date + Amount + Party", 95.0,
                        f"Same date ({t1['date']}), same party '{t1['party_name']}', and identical amount (₹{float(t1['amount']):,.2f})"
                    )

    # A5. Same Reference Number / Transaction ID
    ref_map: Dict[str, List[Dict[str, Any]]] = {}
    for t in txs:
        ref = (t["reference_no"] or "").strip().upper()
        if ref and len(ref) >= 4:
            ref_map.setdefault(ref, []).append(t)

    for ref, group in ref_map.items():
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    t1, t2 = group[i], group[j]
                    add_dup_pair(
                        t1, t2,
                        "Same Reference Number", 96.0,
                        f"Same reference / UTR / transaction ID '{ref}' recorded in multiple transactions"
                    )

    # A6. Fuzzy Duplicate Detection (Similar Party, Similar Invoice, Similar Narration, Same/Near Amount)
    # Check within reasonable temporal / amount windows
    # Group transactions by approximate amount buckets to keep pairwise checks linear & fast
    amt_buckets: Dict[int, List[Dict[str, Any]]] = {}
    for t in txs:
        amt = float(t["amount"] or t["debit"] or t["credit"] or 0.0)
        if amt > 0:
            b_key = int(amt // 500) # 500 bucket
            amt_buckets.setdefault(b_key, []).append(t)
            amt_buckets.setdefault(b_key - 1, []) # check neighbor bucket
            amt_buckets.setdefault(b_key + 1, [])

    for b_key, candidates in amt_buckets.items():
        if len(candidates) > 1:
            for i in range(len(candidates)):
                for j in range(i + 1, len(candidates)):
                    t1, t2 = candidates[i], candidates[j]
                    if t1["id"] >= t2["id"]:
                        continue
                    if (t1["id"], t2["id"]) in seen_pair_keys:
                        continue

                    amt1 = float(t1["amount"] or t1["debit"] or t1["credit"] or 0.0)
                    amt2 = float(t2["amount"] or t2["debit"] or t2["credit"] or 0.0)
                    amt_diff = abs(amt1 - amt2)
                    max_amt = max(amt1, amt2, 1.0)
                    is_near_amt = (amt_diff == 0.0) or (amt_diff <= 1.0) or ((amt_diff / max_amt) <= 0.015)

                    if not is_near_amt:
                        continue

                    # Check Party similarity
                    p_sim = string_similarity(t1["party_name"], t2["party_name"]) if (t1["party_name"] and t2["party_name"]) else 0.0
                    # Check Invoice similarity
                    inv_sim = code_similarity(t1["invoice_no"], t2["invoice_no"]) if (t1["invoice_no"] and t2["invoice_no"]) else 0.0
                    # Check Narration similarity
                    desc_sim = string_similarity(t1["description"], t2["description"]) if (t1["description"] and t2["description"]) else 0.0

                    # Fuzzy match condition 1: Similar party (>= 85%) + exact/near amount
                    if p_sim >= 0.85 and amt1 > 0 and (amt_diff <= 1.0 or amt_diff / max_amt <= 0.01):
                        sim_score = round(p_sim * 95.0 + (5.0 if amt_diff == 0 else 0.0), 1)
                        add_dup_pair(
                            t1, t2,
                            "Fuzzy Duplicate (Party & Amount)", sim_score,
                            f"Similar party name ({int(p_sim*100)}% match: '{t1['party_name']}' vs '{t2['party_name']}') with identical/near amount (₹{amt1:,.2f})"
                        )
                    # Fuzzy match condition 2: Similar invoice number (>= 85%) + similar amount
                    elif inv_sim >= 0.85 and t1["invoice_no"] and t2["invoice_no"] and t1["invoice_no"] != t2["invoice_no"]:
                        sim_score = round(inv_sim * 94.0, 1)
                        add_dup_pair(
                            t1, t2,
                            "Fuzzy Duplicate (Invoice Pattern)", sim_score,
                            f"Similar invoice pattern ({int(inv_sim*100)}% match: '{t1['invoice_no']}' vs '{t2['invoice_no']}')"
                        )
                    # Fuzzy match condition 3: High description similarity (>= 85%) + exact amount
                    elif desc_sim >= 0.85 and amt_diff == 0.0 and len(t1["description"] or "") > 10:
                        sim_score = round(desc_sim * 92.0, 1)
                        add_dup_pair(
                            t1, t2,
                            "Fuzzy Duplicate (Narration & Amount)", sim_score,
                            f"Similar narration text ({int(desc_sim*100)}% match) and identical amount (₹{amt1:,.2f})"
                        )

    # Build Structured Duplicate Groups (Group #D001, Group #D002, ...)
    duplicate_groups: List[Dict[str, Any]] = []
    group_counter = 1

    # Sort pairs by similarity descending
    duplicate_pairs.sort(key=lambda p: (p["similarity_pct"], p["tx_a"]["amount"]), reverse=True)

    for p in duplicate_pairs:
        tx_a = p["tx_a"]
        tx_b = p["tx_b"]
        g_code = f"DUP-{min(tx_a['id'], tx_b['id'])}-{max(tx_a['id'], tx_b['id'])}"
        group_counter += 1

        # Check if reviewed by deterministic code or transaction IDs
        rev_a = dup_reviews_map.get((g_code, tx_b["id"])) or dup_reviews_map.get((f"D{group_counter:03d}", tx_b["id"]), {})
        status = rev_a.get("status", "Unreviewed")
        auditor_comment = rev_a.get("auditor_comment", "")
        reviewed_by = rev_a.get("reviewed_by")
        reviewed_at = rev_a.get("reviewed_at")

        duplicate_groups.append({
            "group_code": g_code,
            "group_type": p["group_type"],
            "similarity_pct": p["similarity_pct"],
            "detection_reason": p["detection_reason"],
            "status": status,
            "auditor_comment": auditor_comment,
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            "financial_exposure": max(float(tx_a["amount"] or 0), float(tx_b["amount"] or 0)),
            "transactions": [
                {
                    "label": "Transaction A (Reference)",
                    "id": tx_a["id"],
                    "date": tx_a["date"],
                    "ledger": tx_a["ledger"],
                    "party_name": tx_a["party_name"] or "—",
                    "debit": float(tx_a["debit"] or 0.0),
                    "credit": float(tx_a["credit"] or 0.0),
                    "amount": float(tx_a["amount"] or 0.0),
                    "voucher_no": tx_a["voucher_no"] or "—",
                    "invoice_no": tx_a["invoice_no"] or "—",
                    "reference_no": tx_a["reference_no"] or "—",
                    "description": tx_a["description"] or "—"
                },
                {
                    "label": "Transaction B (Potential Duplicate)",
                    "id": tx_b["id"],
                    "date": tx_b["date"],
                    "ledger": tx_b["ledger"],
                    "party_name": tx_b["party_name"] or "—",
                    "debit": float(tx_b["debit"] or 0.0),
                    "credit": float(tx_b["credit"] or 0.0),
                    "amount": float(tx_b["amount"] or 0.0),
                    "voucher_no": tx_b["voucher_no"] or "—",
                    "invoice_no": tx_b["invoice_no"] or "—",
                    "reference_no": tx_b["reference_no"] or "—",
                    "description": tx_b["description"] or "—"
                }
            ]
        })

    # -------------------------------------------------------------
    # PART B: MISSING TRANSACTION / SEQUENCE GAP DETECTION
    # -------------------------------------------------------------
    sequence_gaps: List[Dict[str, Any]] = []

    def check_sequence_series(items: List[str], seq_type: str, item_label: str):
        # Group by prefix and suffix
        series_buckets: Dict[Tuple[str, str, int], List[int]] = {}
        for itm in items:
            parts = extract_sequence_parts(itm)
            if parts:
                prefix, num, suffix, pad_len = parts
                series_buckets.setdefault((prefix, suffix, pad_len), []).append(num)

        for (prefix, suffix, pad_len), numbers in series_buckets.items():
            if len(numbers) < 2:
                continue
            
            sorted_nums = sorted(set(numbers))
            for i in range(len(sorted_nums) - 1):
                cur_n = sorted_nums[i]
                next_n = sorted_nums[i + 1]
                gap_size = next_n - cur_n - 1

                if 1 <= gap_size <= 200: # Practical gap range
                    missing_numbers = list(range(cur_n + 1, next_n))
                    # Format missing items
                    formatted_missing = [f"{prefix}{str(m).zfill(pad_len)}{suffix}" for m in missing_numbers]
                    exp_from = formatted_missing[0]
                    exp_to = formatted_missing[-1]

                    k = (seq_type, prefix, exp_from, exp_to)
                    rev = gap_reviews_map.get(k, {})

                    status = rev.get("status", "Open")
                    auditor_comment = rev.get("auditor_comment", "")
                    reviewed_by = rev.get("reviewed_by")
                    reviewed_at = rev.get("reviewed_at")

                    severity = "HIGH" if gap_size >= 10 else ("MEDIUM" if gap_size >= 3 else "LOW")

                    sequence_gaps.append({
                        "sequence_type": seq_type,
                        "item_label": item_label,
                        "series_prefix": prefix,
                        "series_suffix": suffix,
                        "expected_from": exp_from,
                        "expected_to": exp_to,
                        "missing_count": gap_size,
                        "missing_items": formatted_missing[:15], # top 15 samples
                        "total_missing_in_gap": gap_size,
                        "severity": severity,
                        "status": status,
                        "auditor_comment": auditor_comment,
                        "reviewed_by": reviewed_by,
                        "reviewed_at": reviewed_at,
                        "exception_reason": f"Sequence gap of {gap_size} {item_label.lower()}(s) between {prefix}{str(cur_n).zfill(pad_len)}{suffix} and {prefix}{str(next_n).zfill(pad_len)}{suffix}",
                        "audit_guidance": "Treat sequence gaps as exceptions for verification against cancelled documents, spoiled leaves, or multi-branch series rather than proof of unrecorded transactions."
                    })

    # B1. Invoice Number Gaps
    invoice_list = [t["invoice_no"] for t in txs if t.get("invoice_no")]
    check_sequence_series(invoice_list, "INVOICE_GAP", "Invoice")

    # B2. Voucher Number Gaps
    voucher_list = [t["voucher_no"] for t in txs if t.get("voucher_no")]
    check_sequence_series(voucher_list, "VOUCHER_GAP", "Voucher")

    # B3. Cheque Number Gaps
    cheque_nums_all: List[str] = []
    for t in txs:
        # Extract from description, reference, voucher
        extracted = extract_cheque_numbers(t.get("description")) + extract_cheque_numbers(t.get("reference_no")) + extract_cheque_numbers(t.get("voucher_no"))
        for num in extracted:
            cheque_nums_all.append(str(num).zfill(6))
    
    if cheque_nums_all:
        check_sequence_series(cheque_nums_all, "CHEQUE_GAP", "Cheque")

    # Sort gaps by missing count descending and severity
    sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    sequence_gaps.sort(key=lambda g: (sev_order.get(g["severity"], 3), -g["missing_count"]))

    # Summary Statistics
    total_exposure = sum(g["financial_exposure"] for g in duplicate_groups if g["status"] != "Marked Valid" and g["status"] != "Ignored")
    confirmed_count = sum(1 for g in duplicate_groups if g["status"] == "Confirmed Duplicate")
    unreviewed_dup_count = sum(1 for g in duplicate_groups if g["status"] == "Unreviewed")
    open_gaps_count = sum(1 for g in sequence_gaps if g["status"] == "Open")

    return {
        "engagement_id": engagement_id,
        "total_transactions_analyzed": total_tx,
        "summary": {
            "total_duplicate_groups": len(duplicate_groups),
            "unreviewed_duplicate_groups": unreviewed_dup_count,
            "confirmed_duplicate_count": confirmed_count,
            "potential_financial_exposure": round(total_exposure, 2),
            "total_sequence_gaps": len(sequence_gaps),
            "open_sequence_gaps_count": open_gaps_count
        },
        "duplicate_groups": duplicate_groups,
        "sequence_gaps": sequence_gaps
    }

def update_duplicate_group_review(engagement_id: int, group_code: str, status: str, comment: str, user_name: str) -> Dict[str, Any]:
    """Updates auditor review status and comments for all pairs in a duplicate group."""
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Fetch group from current analysis to get transaction IDs
    data = detect_duplicates_and_gaps(engagement_id)
    target_group = next((g for g in data["duplicate_groups"] if g["group_code"] == group_code), None)
    
    if not target_group:
        conn.close()
        raise ValueError(f"Duplicate Group '{group_code}' not found")

    tx_a_id = target_group["transactions"][0]["id"]
    tx_b_id = target_group["transactions"][1]["id"]
    g_type = target_group["group_type"]
    sim = target_group["similarity_pct"]
    reason = target_group["detection_reason"]

    # Insert or replace review record
    conn.execute("""
        INSERT INTO duplicate_group_reviews (
            engagement_id, group_code, group_type, primary_transaction_id, duplicate_transaction_id,
            similarity_pct, detection_reason, status, auditor_comment, reviewed_by, reviewed_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(engagement_id, group_code, duplicate_transaction_id) DO UPDATE SET
            status = excluded.status,
            auditor_comment = excluded.auditor_comment,
            reviewed_by = excluded.reviewed_by,
            reviewed_at = excluded.reviewed_at
    """, (
        engagement_id, group_code, g_type, tx_a_id, tx_b_id,
        sim, reason, status, comment, user_name, now_str, now_str
    ))

    # Also log to audit trail
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action=f"Duplicate Group #{group_code} marked as '{status}'",
        module="DUPLICATES",
        record_id=group_code,
        user=user_name,
        engagement_id=engagement_id,
        details=f"Auditor marked Group #{group_code} as '{status}'. Comment: {comment or 'None'}",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "group_code": group_code,
        "status": status,
        "auditor_comment": comment,
        "reviewed_by": user_name,
        "reviewed_at": now_str
    }

def update_sequence_gap_review(
    engagement_id: int, sequence_type: str, series_prefix: Optional[str],
    expected_from: str, expected_to: str, status: str, comment: str, user_name: str
) -> Dict[str, Any]:
    """Updates auditor review status and explanation for a missing sequence gap."""
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    prefix = series_prefix or ""

    conn.execute("""
        INSERT INTO missing_sequence_reviews (
            engagement_id, sequence_type, series_prefix, expected_from, expected_to,
            missing_count, status, auditor_comment, reviewed_by, reviewed_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
        ON CONFLICT(engagement_id, sequence_type, series_prefix, expected_from, expected_to) DO UPDATE SET
            status = excluded.status,
            auditor_comment = excluded.auditor_comment,
            reviewed_by = excluded.reviewed_by,
            reviewed_at = excluded.reviewed_at
    """, (
        engagement_id, sequence_type, prefix, expected_from, expected_to,
        status, comment, user_name, now_str, now_str
    ))

    # Audit Trail
    log_audit_event(
        conn=conn,
        action=f"Sequence Gap {sequence_type} ({expected_from} to {expected_to}) updated",
        module="SEQUENCE_GAPS",
        record_id=f"{sequence_type}:{prefix}:{expected_from}-{expected_to}",
        user=user_name,
        engagement_id=engagement_id,
        details=f"Auditor status: '{status}'. Reason: {comment or 'None'}",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "sequence_type": sequence_type,
        "expected_from": expected_from,
        "expected_to": expected_to,
        "status": status,
        "auditor_comment": comment,
        "reviewed_by": user_name,
        "reviewed_at": now_str
    }
