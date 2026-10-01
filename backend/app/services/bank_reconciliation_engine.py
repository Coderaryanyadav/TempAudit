import re
import math
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Set
from backend.app.database import get_db_connection

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str or not str(date_str).strip():
        return None
    try:
        return datetime.strptime(str(date_str).strip()[:10], "%Y-%m-%d")
    except Exception:
        return None

def normalize_ref(ref_str: Optional[str]) -> str:
    """Extract digits/alphanumerics from reference or cheque string."""
    if not ref_str:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(ref_str)).upper()
    return cleaned

def extract_cheque_no(text: Optional[str]) -> Optional[str]:
    """Look for standard 6-digit cheque numbers or 'CHQ 123456' patterns."""
    if not text:
        return None
    match = re.search(r"\b(\d{6})\b", str(text))
    if match:
        return match.group(1)
    chq_match = re.search(r"(?:chq|cheque|chk)[\s#:]*([A-Za-z0-9]+)", str(text), re.IGNORECASE)
    if chq_match:
        return chq_match.group(1).upper()
    return None

def compute_string_similarity(str1: Optional[str], str2: Optional[str]) -> float:
    """Computes token Jaccard similarity between two strings."""
    if not str1 or not str2:
        return 0.0
    tokens1 = set(re.findall(r"\w+", str(str1).lower()))
    tokens2 = set(re.findall(r"\w+", str(str2).lower()))
    # Remove generic stopwords
    stopwords = {"ltd", "pvt", "limited", "private", "co", "corp", "inc", "a", "an", "the", "to", "for", "by", "of", "and", "in", "payment", "received", "transfer", "neft", "rtgs", "upi", "imps"}
    tokens1 = tokens1 - stopwords
    tokens2 = tokens2 - stopwords
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)

def run_bank_reconciliation(
    engagement_id: int,
    bank_ledger_name: Optional[str] = None,
    file_b_id: Optional[int] = None,
    title: Optional[str] = None,
    created_by: str = "admin"
) -> Dict[str, Any]:
    """
    Executes automated 4-tier Bank Reconciliation matching and anomaly detection.
    Never modifies source transactions.
    """
    conn = get_db_connection()

    # 1. Fetch Book Transactions (Cash Book / Bank Ledger)
    book_query = "SELECT * FROM transactions WHERE engagement_id = ?"
    book_params = [engagement_id]
    
    # If bank ledger specified, filter, else find any ledger containing bank or cash
    if bank_ledger_name and bank_ledger_name != "All":
        book_query += " AND ledger = ?"
        book_params.append(bank_ledger_name)
    else:
        # Default to bank ledger if exists, else all
        chk = conn.execute("SELECT DISTINCT ledger FROM transactions WHERE engagement_id = ? AND (LOWER(ledger) LIKE '%bank%' OR LOWER(ledger) LIKE '%hdfc%' OR LOWER(ledger) LIKE '%sbi%' OR LOWER(ledger) LIKE '%icici%')", (engagement_id,)).fetchone()
        if chk:
            bank_ledger_name = chk["ledger"]
            book_query += " AND ledger = ?"
            book_params.append(bank_ledger_name)
        else:
            bank_ledger_name = "Bank Account"

    book_rows = conn.execute(book_query + " ORDER BY date ASC, id ASC", tuple(book_params)).fetchall()
    book_txs = [dict(r) for r in book_rows]

    # 2. Fetch or Prepare Bank Statement Transactions
    bank_txs = []
    if file_b_id:
        # If transactions imported under this file_id exist
        stmt_rows = conn.execute("SELECT * FROM transactions WHERE file_id = ? ORDER BY date ASC, id ASC", (file_b_id,)).fetchall()
        if stmt_rows:
            bank_txs = [dict(r) for r in stmt_rows]
    else:
        stmt_rows = conn.execute("""
            SELECT t.* FROM transactions t
            WHERE t.engagement_id = ? AND (
                t.transaction_type = 'BANK_STATEMENT' OR
                t.file_id IN (SELECT id FROM uploaded_files WHERE engagement_id = ? AND (file_type = 'BANK_STATEMENT' OR LOWER(file_type) LIKE '%bank%'))
            )
            ORDER BY t.date ASC, t.id ASC
        """, (engagement_id, engagement_id)).fetchall()
        if stmt_rows:
            bank_txs = [dict(r) for r in stmt_rows]

    now_str = datetime.now().isoformat()
    if not title:
        title = f"{bank_ledger_name} Bank Reconciliation Statement (BRS)"

    # 3. Matching & Exception Engine
    matched_items = []
    matched_book_ids: Set[int] = set()
    matched_bank_ids: Set[int] = set()

    # Pre-index for faster matching
    # Map by exact amount
    bank_by_amt: Dict[float, List[Dict[str, Any]]] = {}
    for b in bank_txs:
        amt = float(b.get("amount") or max(float(b.get("debit") or 0.0), float(b.get("credit") or 0.0)))
        amt_key = round(amt, 2)
        bank_by_amt.setdefault(amt_key, []).append(b)

    # -------------------------------------------------------------
    # PASS 1: EXACT MATCH (100% Score - Strong Identifier Required)
    # -------------------------------------------------------------
    exact_candidates = []
    for bk in book_txs:
        bk_dr = float(bk.get("debit") or 0.0)
        bk_cr = float(bk.get("credit") or 0.0)
        bk_amt = round(float(bk.get("amount") or max(bk_dr, bk_cr)), 2)
        bk_dt = parse_date(bk.get("date"))
        bk_ref = normalize_ref(bk.get("voucher_no") or bk.get("reference_no") or bk.get("invoice_no"))
        bk_chq = extract_cheque_no(bk.get("description")) or extract_cheque_no(bk.get("voucher_no")) or extract_cheque_no(bk.get("reference_no"))
        bk_party = str(bk.get("party_name") or "").strip().lower()

        candidates = bank_by_amt.get(bk_amt, [])
        for bn in candidates:
            bn_dr = float(bn.get("debit") or 0.0)
            bn_cr = float(bn.get("credit") or 0.0)
            bn_dt = parse_date(bn.get("date"))
            bn_ref = normalize_ref(bn.get("voucher_no") or bn.get("reference_no") or bn.get("invoice_no"))
            bn_chq = extract_cheque_no(bn.get("description")) or extract_cheque_no(bn.get("voucher_no")) or extract_cheque_no(bn.get("reference_no"))
            bn_party = str(bn.get("party_name") or "").strip().lower()

            # Direction check: Book Dr (Deposit) == Bank Cr (Deposit) OR Book Cr (Payment) == Bank Dr (Withdrawal)
            is_direction_match = (bk_dr > 0 and bn_cr > 0) or (bk_cr > 0 and bn_dr > 0) or (bk_dr == 0 and bk_cr == 0)
            if not is_direction_match:
                continue

            date_diff = abs((bn_dt - bk_dt).days) if (bk_dt and bn_dt) else 0

            # Strict Exact condition: Requires strong identifier (cheque, voucher ref, or strong party match + 1 day window)
            is_exact_chq = bool(bk_chq and bn_chq and bk_chq == bn_chq)
            is_exact_ref = bool(bk_ref and bn_ref and bk_ref == bn_ref)
            is_exact_date_party = bool(date_diff <= 1 and bk_party and bn_party and (bk_party in bn_party or bn_party in bk_party))

            if is_exact_chq or is_exact_ref or is_exact_date_party:
                # Check for duplicate ambiguity if relying purely on date + party without distinct cheque/ref
                is_ambiguous = False
                if not is_exact_chq and not is_exact_ref:
                    bk_dupes = sum(1 for b in book_txs if round(float(b.get("amount") or 0), 2) == bk_amt and str(b.get("party_name") or "").strip().lower() == bk_party)
                    bn_dupes = sum(1 for b in bank_txs if round(float(b.get("amount") or 0), 2) == bk_amt and str(b.get("party_name") or "").strip().lower() == bn_party)
                    if bk_dupes > 1 or bn_dupes > 1:
                        is_ambiguous = True

                if is_exact_chq:
                    priority = 100
                elif is_exact_ref:
                    priority = 98
                elif not is_ambiguous:
                    priority = 95
                else:
                    priority = 85

                exact_candidates.append((priority, -date_diff, bk, bn, is_exact_chq, is_exact_ref, is_ambiguous, bk_chq, bk_ref, bk_amt, date_diff))

    ambiguous_items = []

    # Sort exact candidates by priority descending, date proximity ascending
    exact_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    for priority, _, bk, bn, is_exact_chq, is_exact_ref, is_ambiguous, bk_chq, bk_ref, bk_amt, date_diff in exact_candidates:
        if bk["id"] in matched_book_ids or bn["id"] in matched_bank_ids:
            continue

        reason_parts = [f"Exact Amount ₹{bk_amt:,.2f}"]
        if is_exact_chq:
            reason_parts.append(f"Matching Cheque #{bk_chq}")
        elif is_exact_ref:
            reason_parts.append(f"Matching Ref #{bk_ref}")

        if is_ambiguous:
            reason_parts.append("Ambiguous Duplicate Entry (Multiple Identical Amounts/Parties - Requires Auditor Verification)")
            ambiguous_items.append({
                "book_tx_id": bk["id"],
                "bank_tx_id": bn["id"],
                "date_a": bk.get("date"),
                "date_b": bn.get("date"),
                "ref_a": bk.get("voucher_no") or bk.get("reference_no") or "",
                "ref_b": bn.get("voucher_no") or bn.get("reference_no") or "",
                "party_a": bk.get("party_name") or "",
                "party_b": bn.get("party_name") or "",
                "description_a": bk.get("description") or "",
                "description_b": bn.get("description") or "",
                "amount_a": bk_amt,
                "amount_b": bk_amt,
                "difference": 0.0,
                "date_diff_days": date_diff,
                "match_level": "AMBIGUOUS EXACT CANDIDATE",
                "match_score": 85.0,
                "match_reason": " • ".join(reason_parts),
                "item_type": "AMBIGUOUS_CANDIDATE",
                "status": "Review Required",
                "notes": "Ambiguous duplicate candidates require manual auditor verification before reconciliation."
            })
            # Do NOT add to matched_book_ids or matched_bank_ids so they remain open for auditor verification
            continue

        matched_book_ids.add(bk["id"])
        matched_bank_ids.add(bn["id"])

        if date_diff == 0:
            reason_parts.append("Same Day Clearance")
        else:
            reason_parts.append(f"{date_diff}d timing clearance")

        matched_items.append({
            "book_tx_id": bk["id"],
            "bank_tx_id": bn["id"],
            "date_a": bk.get("date"),
            "date_b": bn.get("date"),
            "ref_a": bk.get("voucher_no") or bk.get("reference_no") or "",
            "ref_b": bn.get("voucher_no") or bn.get("reference_no") or "",
            "party_a": bk.get("party_name") or "",
            "party_b": bn.get("party_name") or "",
            "description_a": bk.get("description") or "",
            "description_b": bn.get("description") or "",
            "amount_a": bk_amt,
            "amount_b": bk_amt,
            "difference": 0.0,
            "date_diff_days": date_diff,
            "match_level": "EXACT MATCH",
            "match_score": 100.0,
            "match_reason": " • ".join(reason_parts),
            "item_type": "MATCHED",
            "status": "Confirmed",
            "notes": "System verified exact voucher and statement match with strong identifier."
        })

    # -------------------------------------------------------------
    # PASS 2: HIGH CONFIDENCE MATCH (80% - 95% Score - Global 1-to-1 Assignment)
    # -------------------------------------------------------------
    high_conf_candidates = []
    for bk in book_txs:
        if bk["id"] in matched_book_ids:
            continue
        bk_dr = float(bk.get("debit") or 0.0)
        bk_cr = float(bk.get("credit") or 0.0)
        bk_amt = round(float(bk.get("amount") or max(bk_dr, bk_cr)), 2)
        bk_dt = parse_date(bk.get("date"))
        bk_party = bk.get("party_name") or ""
        bk_desc = bk.get("description") or ""

        candidates = bank_by_amt.get(bk_amt, [])
        for bn in candidates:
            if bn["id"] in matched_bank_ids:
                continue
            bn_dr = float(bn.get("debit") or 0.0)
            bn_cr = float(bn.get("credit") or 0.0)
            bn_dt = parse_date(bn.get("date"))
            bn_party = bn.get("party_name") or ""
            bn_desc = bn.get("description") or ""

            is_direction_match = (bk_dr > 0 and bn_cr > 0) or (bk_cr > 0 and bn_dr > 0) or (bk_dr == 0 and bk_cr == 0)
            if not is_direction_match:
                continue

            date_diff = abs((bn_dt - bk_dt).days) if (bk_dt and bn_dt) else 0
            sim = compute_string_similarity(f"{bk_party} {bk_desc}", f"{bn_party} {bn_desc}")

            # High confidence: Exact amount within 7 days clearance delay
            if date_diff <= 7:
                score = 90.0 if date_diff <= 3 else 80.0
                if sim >= 0.3:
                    score += 5.0
                high_conf_candidates.append((score, -date_diff, bk, bn, bk_amt, bk_party, bn_party, bk_desc, bn_desc, date_diff, sim))

    # Sort high confidence candidates globally
    high_conf_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    for score, _, bk, bn, bk_amt, bk_party, bn_party, bk_desc, bn_desc, date_diff, sim in high_conf_candidates:
        if bk["id"] in matched_book_ids or bn["id"] in matched_bank_ids:
            continue
        matched_book_ids.add(bk["id"])
        matched_bank_ids.add(bn["id"])

        matched_items.append({
            "book_tx_id": bk["id"],
            "bank_tx_id": bn["id"],
            "date_a": bk.get("date"),
            "date_b": bn.get("date"),
            "ref_a": bk.get("voucher_no") or bk.get("reference_no") or "",
            "ref_b": bn.get("voucher_no") or bn.get("reference_no") or "",
            "party_a": bk_party,
            "party_b": bn_party,
            "description_a": bk_desc,
            "description_b": bn_desc,
            "amount_a": bk_amt,
            "amount_b": bk_amt,
            "difference": 0.0,
            "date_diff_days": date_diff,
            "match_level": "HIGH CONFIDENCE",
            "match_score": score,
            "match_reason": f"Exact Amount ₹{bk_amt:,.2f} with {date_diff} days clearance lag" + (f" (Party similarity {int(sim*100)}%)" if sim > 0 else ""),
            "item_type": "MATCHED",
            "status": "Suggested",
            "notes": "High probability match suggested based on amount and timing proximity."
        })

    # -------------------------------------------------------------
    # PASS 3: POSSIBLE MATCH (50% - 79% Score - Global Bipartite Pairing)
    # -------------------------------------------------------------
    possible_candidates = []
    for bk in book_txs:
        if bk["id"] in matched_book_ids:
            continue
        bk_dr = float(bk.get("debit") or 0.0)
        bk_cr = float(bk.get("credit") or 0.0)
        bk_amt = round(float(bk.get("amount") or max(bk_dr, bk_cr)), 2)
        bk_dt = parse_date(bk.get("date"))
        bk_party = bk.get("party_name") or ""
        bk_desc = bk.get("description") or ""

        # Check for matching candidates with date proximity or minor amount difference
        for bn in bank_txs:
            if bn["id"] in matched_bank_ids:
                continue
            bn_dr = float(bn.get("debit") or 0.0)
            bn_cr = float(bn.get("credit") or 0.0)
            bn_amt = round(float(bn.get("amount") or max(bn_dr, bn_cr)), 2)
            bn_dt = parse_date(bn.get("date"))
            bn_party = bn.get("party_name") or ""
            bn_desc = bn.get("description") or ""

            amt_diff = round(abs(bk_amt - bn_amt), 2)
            date_diff = abs((bn_dt - bk_dt).days) if (bk_dt and bn_dt) else 0
            sim = compute_string_similarity(f"{bk_party} {bk_desc}", f"{bn_party} {bn_desc}")

            # Case A: Exact amount with larger date lag (8-30 days)
            if amt_diff == 0.0 and date_diff <= 30:
                score = 65.0 - (date_diff * 0.3)
                possible_candidates.append((score, -date_diff, bk, bn, bk_amt, bn_amt, 0.0, date_diff, "MATCHED", "POSSIBLE MATCH", f"Exact Amount ₹{bk_amt:,.2f} with extended {date_diff} days transit lag"))
            
            # Case B: Minor amount difference (<= ₹100 e.g. bank fee deduction) with matching party
            elif amt_diff > 0 and amt_diff <= 100.0 and sim >= 0.4 and date_diff <= 10:
                score = 55.0 + (sim * 10.0) - (date_diff * 0.3)
                possible_candidates.append((score, -date_diff, bk, bn, bk_amt, bn_amt, amt_diff, date_diff, "AMOUNT_MISMATCH", "POSSIBLE MATCH", f"Party match '{bk_party}' with variance ₹{amt_diff:,.2f} (Potential bank service fee or deduction)"))

    possible_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    for score, _, bk, bn, bk_amt, bn_amt, amt_diff, date_diff, item_type, match_lvl, reason in possible_candidates:
        if bk["id"] in matched_book_ids or bn["id"] in matched_bank_ids:
            continue
        matched_book_ids.add(bk["id"])
        matched_bank_ids.add(bn["id"])
        matched_items.append({
            "book_tx_id": bk["id"],
            "bank_tx_id": bn["id"],
            "date_a": bk.get("date"),
            "date_b": bn.get("date"),
            "ref_a": bk.get("voucher_no") or bk.get("reference_no") or "",
            "ref_b": bn.get("voucher_no") or bn.get("reference_no") or "",
            "party_a": bk.get("party_name") or "",
            "party_b": bn.get("party_name") or "",
            "description_a": bk.get("description") or "",
            "description_b": bn.get("description") or "",
            "amount_a": bk_amt,
            "amount_b": bn_amt,
            "difference": amt_diff,
            "date_diff_days": date_diff,
            "match_level": match_lvl,
            "match_score": round(score, 1),
            "match_reason": reason,
            "item_type": item_type,
            "status": "Suggested",
            "notes": "Possible match requiring auditor verification of delayed clearance or amount adjustment."
        })

    # -------------------------------------------------------------
    # PASS 4: UNMATCHED ITEMS & TIMING EXCEPTIONS DETECTION
    # -------------------------------------------------------------
    unmatched_book_items = []
    unpresented_cheques_amt = 0.0
    outstanding_deposits_amt = 0.0

    for bk in book_txs:
        if bk["id"] not in matched_book_ids:
            dr = float(bk.get("debit") or 0.0)
            cr = float(bk.get("credit") or 0.0)
            amt = round(float(bk.get("amount") or max(dr, cr)), 2)
            desc = str(bk.get("description") or "").lower()
            vch = str(bk.get("voucher_no") or "").lower()
            pty = bk.get("party_name") or ""
            
            is_payment_type = cr > 0 or any(k in desc or k in vch for k in ["payment", "pymt", "chq", "cheque", "withdrawal", "paid", "vendor", "salary", "rent", "neft", "rtgs", "ach"])
            is_receipt_type = dr > 0 or any(k in desc or k in vch for k in ["receipt", "rcpt", "deposit", "collection", "customer", "received"])

            if cr > 0 or (is_payment_type and not is_receipt_type):
                item_type = "UNPRESENTED_CHEQUE"
                unpresented_cheques_amt += amt
                reason = "Cheque/Payment issued in books but not presented for payment in bank statement within period"
            elif dr > 0 or is_receipt_type:
                item_type = "OUTSTANDING_DEPOSIT"
                outstanding_deposits_amt += amt
                reason = "Cheque/Receipt deposited in books but not yet credited by bank"
            elif amt == 0.0:
                item_type = "ZERO_VALUE_ENTRY"
                reason = "Zero value entry in book ledger requiring auditor review"
            else:
                item_type = "UNRECONCILED_BOOK_ENTRY"
                outstanding_deposits_amt += amt
                reason = f"Unmatched book entry of ₹{amt:,.2f} requiring verification"

            unmatched_book_items.append({
                "book_tx_id": bk["id"],
                "bank_tx_id": None,
                "date_a": bk.get("date"),
                "date_b": None,
                "ref_a": bk.get("voucher_no") or bk.get("reference_no") or "",
                "ref_b": "",
                "party_a": pty,
                "party_b": "",
                "description_a": bk.get("description") or "",
                "description_b": "",
                "amount_a": amt,
                "amount_b": 0.0,
                "difference": amt,
                "date_diff_days": 0,
                "match_level": "UNMATCHED",
                "match_score": 0.0,
                "match_reason": reason,
                "item_type": item_type,
                "status": "Unmatched",
                "notes": f"Requires substantive verification of clearance in subsequent period."
            })

    unmatched_bank_items = []
    bank_charges_amt = 0.0
    interest_credited_amt = 0.0

    for bn in bank_txs:
        if bn["id"] not in matched_bank_ids:
            dr = float(bn.get("debit") or 0.0)
            cr = float(bn.get("credit") or 0.0)
            amt = round(float(bn.get("amount") or max(dr, cr)), 2)
            desc = str(bn.get("description") or "").lower()
            pty = str(bn.get("party_name") or "").lower()

            is_chg = any(k in desc or k in pty for k in ["chg", "charge", "fee", "commission", "penalty", "sms", "folio", "amc", "gst"])
            is_int = any(k in desc or k in pty for k in ["int", "interest", "credit int", "savings int", "fd int"])

            if is_chg and dr > 0:
                item_type = "BANK_CHARGES"
                bank_charges_amt += amt
                reason = f"Direct bank charge of ₹{amt:,.2f} debited in bank statement but not posted in Cash Book"
            elif is_int and cr > 0:
                item_type = "INTEREST_CREDIT"
                interest_credited_amt += amt
                reason = f"Direct interest of ₹{amt:,.2f} credited by bank but not recorded in Cash Book"
            elif not pty or "unknown" in pty or "unidentified" in desc:
                item_type = "UNKNOWN_ENTRY"
                reason = f"Unidentified bank entry of ₹{amt:,.2f} with missing client narration"
            else:
                item_type = "UNRECORDED_BANK_ENTRY"
                reason = f"Bank statement entry of ₹{amt:,.2f} ({'Credit' if cr > 0 else 'Debit'}) not found in Cash Book"

            unmatched_bank_items.append({
                "book_tx_id": None,
                "bank_tx_id": bn["id"],
                "date_a": None,
                "date_b": bn.get("date"),
                "ref_a": "",
                "ref_b": bn.get("voucher_no") or bn.get("reference_no") or "",
                "party_a": "",
                "party_b": bn.get("party_name") or "",
                "description_a": "",
                "description_b": bn.get("description") or "",
                "amount_a": 0.0,
                "amount_b": amt,
                "difference": amt,
                "date_diff_days": 0,
                "match_level": "UNMATCHED",
                "match_score": 0.0,
                "match_reason": reason,
                "item_type": item_type,
                "status": "Unmatched",
                "notes": f"Requires adjusting journal entry in Cash Book."
            })

    # Total counts and balances calculation
    all_recon_items = matched_items + ambiguous_items + unmatched_book_items + unmatched_bank_items

    # Compute BRS Roll-Forward Schedule
    # Book Balance = Sum of Book Debits - Sum of Book Credits
    book_dr_total = sum(float(b.get("debit") or 0.0) for b in book_txs)
    book_cr_total = sum(float(b.get("credit") or 0.0) for b in book_txs)
    book_balance = round(book_dr_total - book_cr_total, 2)

    # Bank Balance = Sum of Bank Credits - Sum of Bank Debits
    bank_cr_total = sum(float(b.get("credit") or 0.0) for b in bank_txs)
    bank_dr_total = sum(float(b.get("debit") or 0.0) for b in bank_txs)
    bank_balance = round(bank_cr_total - bank_dr_total, 2)

    # BRS Computation Formula:
    # Balance as per Bank Statement:
    # Less: Cheques issued but not presented
    # Add: Cheques deposited but not credited
    # Add: Bank charges not entered in books
    # Less: Interest credited not entered in books
    # = Adjusted Balance (should equal Balance as per Books)
    adjusted_bank_balance = round(
        bank_balance - unpresented_cheques_amt + outstanding_deposits_amt + bank_charges_amt - interest_credited_amt,
        2
    )
    net_diff = round(abs(book_balance - adjusted_bank_balance), 2)

    # 4. Persist to Database
    cursor = conn.execute("""
        INSERT INTO reconciliations (
            engagement_id, recon_type, title, bank_account_name, status,
            total_bank_tx, total_book_tx, matched_count, unmatched_bank_count, unmatched_book_count,
            amount_diff_count, manual_confirmed_count, unpresented_cheques_amount, outstanding_deposits_amount,
            bank_charges_amount, interest_credited_amount, book_balance, bank_balance,
            adjusted_bank_balance, net_unreconciled_difference, unreconciled_amount, created_at
        )
        VALUES (?, 'Bank BRS', ?, ?, 'Completed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        engagement_id, title, bank_ledger_name,
        len(bank_txs), len(book_txs), len(matched_items), len(unmatched_bank_items), len(unmatched_book_items),
        sum(1 for m in matched_items if m["difference"] > 0),
        sum(1 for m in matched_items if m["status"] == "Confirmed"),
        round(unpresented_cheques_amt, 2), round(outstanding_deposits_amt, 2),
        round(bank_charges_amt, 2), round(interest_credited_amt, 2),
        book_balance, bank_balance, adjusted_bank_balance, net_diff, net_diff, now_str
    ))
    recon_id = cursor.lastrowid

    # Insert items
    for itm in all_recon_items:
        conn.execute("""
            INSERT INTO reconciliation_items (
                recon_id, bank_tx_id, book_tx_id, date_a, date_b, ref_a, ref_b,
                party_a, party_b, description_a, description_b, amount_a, amount_b,
                difference, date_diff_days, match_level, match_score, match_reason,
                item_type, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            recon_id, itm["bank_tx_id"], itm["book_tx_id"], itm["date_a"], itm["date_b"],
            itm["ref_a"], itm["ref_b"], itm["party_a"], itm["party_b"],
            itm["description_a"], itm["description_b"], itm["amount_a"], itm["amount_b"],
            itm["difference"], itm["date_diff_days"], itm["match_level"], itm["match_score"],
            itm["match_reason"], itm["item_type"], itm["status"], itm["notes"]
        ))

    # Log in audit trail
    conn.execute("""
        INSERT INTO audit_logs (username, action, entity_type, entity_id, details, timestamp)
        VALUES (?, 'RUN_BANK_RECONCILIATION', 'reconciliation', ?, ?, ?)
    """, (created_by, recon_id, f"Executed BRS for '{bank_ledger_name}': {len(matched_items)} matched, {len(ambiguous_items)} ambiguous, {len(unmatched_book_items)} unpresented/outstanding, {len(unmatched_bank_items)} bank exceptions", now_str))

    conn.commit()
    conn.close()

    return {
        "recon_id": recon_id,
        "title": title,
        "bank_account_name": bank_ledger_name,
        "summary": {
            "total_bank_tx": len(bank_txs),
            "total_book_tx": len(book_txs),
            "matched_count": len(matched_items),
            "ambiguous_candidates_count": len(ambiguous_items),
            "unmatched_bank_count": len(unmatched_bank_items),
            "unmatched_book_count": len(unmatched_book_items),
            "amount_diff_count": sum(1 for m in matched_items if m["difference"] > 0),
            "manual_confirmed_count": sum(1 for m in matched_items if m["status"] == "Confirmed"),
            "unpresented_cheques_amount": round(unpresented_cheques_amt, 2),
            "outstanding_deposits_amount": round(outstanding_deposits_amt, 2),
            "bank_charges_amount": round(bank_charges_amt, 2),
            "interest_credited_amount": round(interest_credited_amt, 2),
            "book_balance": book_balance,
            "bank_balance": bank_balance,
            "adjusted_bank_balance": adjusted_bank_balance,
            "net_unreconciled_difference": net_diff
        },
        "provenance": {
            "source_type": "BANK_LEDGER_AND_STATEMENTS",
            "calculation_method": "DETERMINISTIC_4_TIER_BRS_RECONCILIATION",
            "calculation_timestamp": now_str,
            "calculation_version": "2.0",
            "data_status": "ACTUAL" if (len(book_txs) > 0 and len(bank_txs) > 0) else ("MISSING" if (len(book_txs) == 0 and len(bank_txs) == 0) else "INCOMPLETE_DATA")
        },
        "items": all_recon_items
    }
