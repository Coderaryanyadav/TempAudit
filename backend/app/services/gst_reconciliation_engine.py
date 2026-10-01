import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple
from backend.app.database import get_db_connection
from backend.app.services.gst_rule_config import get_active_gst_rules_map

def parse_iso_date(d_str: Optional[str]) -> Optional[datetime]:
    if not d_str or not str(d_str).strip():
        return None
    cleaned = str(d_str).strip()[:10]
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]:
        try:
            return datetime.strptime(cleaned, fmt)
        except Exception:
            continue
    return None

def normalize_invoice_string(inv: Optional[str], strip_zeros: bool = True) -> str:
    """Normalizes invoice reference by stripping non-alphanumeric chars and optionally leading zeros."""
    if not inv:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(inv)).upper()
    if strip_zeros:
        cleaned = cleaned.lstrip("0")
    return cleaned

def clean_party_string(name: Optional[str], suffixes: List[str] = None) -> str:
    if not name:
        return ""
    words = re.findall(r"\w+", str(name).lower())
    if suffixes:
        s_set = set(s.lower() for s in suffixes)
        words = [w for w in words if w not in s_set]
    return " ".join(words).strip()

def compute_jaccard_similarity(str1: str, str2: str) -> float:
    if not str1 or not str2:
        return 0.0
    w1 = set(re.findall(r"\w+", str1.lower()))
    w2 = set(re.findall(r"\w+", str2.lower()))
    if not w1 or not w2:
        return 0.0
    inter = w1.intersection(w2)
    union = w1.union(w2)
    return len(inter) / len(union)

def is_valid_gstin_format(gstin: Optional[str], pattern: str) -> bool:
    if not gstin:
        return False
    clean_gst = str(gstin).strip().upper()
    return bool(re.match(pattern, clean_gst))

def run_gst_reconciliation(
    engagement_id: int,
    source_a_file_id: Optional[int] = None,
    source_a_type: str = "GSTR-2B (Portal Download)",
    source_b_file_id: Optional[int] = None,
    source_b_type: str = "Purchase Register (Books)",
    ledger_name: Optional[str] = None,
    recon_title: Optional[str] = None,
    created_by: str = "admin"
) -> Dict[str, Any]:
    """
    Executes comprehensive Indian GST Reconciliation comparing Source A (e.g. GSTR-2B/GSTR-1)
    and Source B (e.g. Purchase/Sales Register or Books/Ledger).
    
    Dynamically adheres to configurable GST rule definitions and client state codes.
    """
    conn = get_db_connection()
    rules = get_active_gst_rules_map()
    now_str = datetime.now().isoformat()

    # 1. Configurable Parameters from Rule Engine
    tol_config = rules.get("tolerance_limits", {})
    taxable_tol = float(tol_config.get("taxable_value_tolerance", 5.00))
    tax_head_tol = float(tol_config.get("tax_heads_tolerance", 2.00))
    total_val_tol = float(tol_config.get("total_invoice_tolerance", 5.00))

    date_config = rules.get("date_cutoff_disparity", {})
    max_date_days = int(date_config.get("max_date_disparity_days", 30))
    warn_date_days = int(date_config.get("warn_date_disparity_days", 15))

    fuzzy_config = rules.get("fuzzy_matching_rules", {})
    strip_zeros = bool(fuzzy_config.get("strip_leading_zeros", True))
    min_inv_sim = float(fuzzy_config.get("min_invoice_similarity", 0.85))
    min_pty_sim = float(fuzzy_config.get("min_party_similarity", 0.70))
    legal_suffixes = fuzzy_config.get("strip_legal_suffixes", ["ltd", "pvt", "limited", "llp"])

    gstin_config = rules.get("gstin_structure_validation", {})
    gstin_pattern = gstin_config.get("regex_pattern", "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")

    # 2. Extract Source A (e.g. GST Portal / GSTR-2B / GSTR-1 Dataset)
    source_a_txs = []
    if source_a_file_id:
        rows = conn.execute("SELECT * FROM transactions WHERE file_id = ? ORDER BY date ASC, id ASC", (source_a_file_id,)).fetchall()
        if rows:
            source_a_txs = [dict(r) for r in rows]

    if not source_a_txs:
        is_sales = "sales" in source_b_type.lower() or "gstr-1" in source_a_type.lower()
        target_cat = "GST Data" if not is_sales else "GSTR-1"
        rows = conn.execute("""
            SELECT t.* FROM transactions t
            JOIN uploaded_files u ON t.file_id = u.id
            WHERE t.engagement_id = ? AND (u.data_category = ? OR u.data_category = 'GST Data')
            ORDER BY t.date ASC, t.id ASC
        """, (engagement_id, target_cat)).fetchall()
        if rows:
            source_a_txs = [dict(r) for r in rows]

    # 3. Extract Source B (e.g. Purchase/Sales Register or Books)
    source_b_txs = []
    if source_b_file_id:
        rows = conn.execute("SELECT * FROM transactions WHERE file_id = ? ORDER BY date ASC, id ASC", (source_b_file_id,)).fetchall()
        if rows:
            source_b_txs = [dict(r) for r in rows]

    if not source_b_txs:
        is_sales = "sales" in source_b_type.lower() or "gstr-1" in source_a_type.lower()
        target_cat = "Sales Register" if is_sales else "Purchase Register"
        rows = conn.execute("""
            SELECT t.* FROM transactions t
            JOIN uploaded_files u ON t.file_id = u.id
            WHERE t.engagement_id = ? AND u.data_category = ?
            ORDER BY t.date ASC, t.id ASC
        """, (engagement_id, target_cat)).fetchall()
        if rows:
            source_b_txs = [dict(r) for r in rows]

    if not source_b_txs:
        is_sales = "sales" in source_b_type.lower() or "gstr-1" in source_a_type.lower()
        gl_query = "SELECT * FROM transactions WHERE engagement_id = ?"
        gl_params = [engagement_id]
        if ledger_name and ledger_name != "All":
            gl_query += " AND ledger = ?"
            gl_params.append(ledger_name)
        else:
            if is_sales:
                gl_query += " AND (LOWER(ledger) LIKE '%sale%' OR LOWER(ledger) LIKE '%revenue%' OR LOWER(account_group) = 'revenue')"
            else:
                gl_query += " AND (LOWER(ledger) LIKE '%purchase%' OR LOWER(ledger) LIKE '%expense%' OR LOWER(account_group) = 'expense' OR LOWER(ledger) NOT LIKE '%gstr%')"
        if source_a_file_id:
            gl_query += " AND (file_id IS NULL OR file_id != ?)"
            gl_params.append(source_a_file_id)
        rows = conn.execute(gl_query + " ORDER BY date ASC, id ASC", tuple(gl_params)).fetchall()
        source_b_txs = [dict(r) for r in rows]

    # Fetch Client Home State from client GSTIN (Flaw 48)
    client_row = conn.execute("""
        SELECT c.gstin FROM clients c
        JOIN engagements e ON e.client_id = c.id
        WHERE e.id = ?
    """, (engagement_id,)).fetchone()
    client_home_state = client_row["gstin"][:2] if client_row and client_row["gstin"] and len(client_row["gstin"]) >= 2 else "27"

    # 4. Perform Multi-Parameter Deterministic Reconciliation
    recon_items: List[Dict[str, Any]] = []
    matched_b_ids: Set[int] = set()
    seen_a_invs: Dict[str, int] = {}

    for a in source_a_txs:
        a_id = a.get("id")
        a_inv_raw = str(a.get("invoice_no") or a.get("voucher_no") or "").strip()
        a_inv_norm = normalize_invoice_string(a_inv_raw, strip_zeros)
        a_date_str = str(a.get("date") or "")[:10]
        a_date = parse_iso_date(a_date_str)
        a_pty = str(a.get("party_name") or "GST Portal Counterparty").strip()
        a_gstin = str(a.get("gstin") or "").strip().upper()
        
        a_tax = round(float(a.get("tax_amount") or 0.0), 2)
        a_total = round(float(a.get("amount") or 0.0), 2)
        a_taxable = round(float(a.get("taxable_value") or a.get("taxable") or (a_total - a_tax if a_total > a_tax else a_total)), 2)
        if a_total == 0.0 and (a_taxable > 0 or a_tax > 0):
            a_total = round(a_taxable + a_tax, 2)

        is_intra_a = (not a_gstin or a_gstin[:2] == client_home_state)
        a_cgst = round(float(a.get("cgst") or (a_tax / 2 if a_tax > 0 and is_intra_a else 0.0)), 2)
        a_sgst = round(float(a.get("sgst") or (a_tax / 2 if a_tax > 0 and is_intra_a else 0.0)), 2)
        a_igst = round(float(a.get("igst") or (a_tax if a_tax > 0 and not is_intra_a else 0.0)), 2)
        if a_tax == 0.0 and (a_cgst > 0 or a_sgst > 0 or a_igst > 0):
            a_tax = round(a_cgst + a_sgst + a_igst, 2)
        a_doc_type = str(a.get("doc_type") or "INV").upper()

        # Check duplicate in Source A
        dup_key_a = f"{a_gstin}|{a_inv_norm}"
        seen_a_invs[dup_key_a] = seen_a_invs.get(dup_key_a, 0) + 1
        is_dup_a = seen_a_invs[dup_key_a] > 1

        # Search for best match in Source B
        best_b = None
        best_score = 0.0

        for b in source_b_txs:
            if b["id"] in matched_b_ids:
                continue

            b_inv_raw = str(b.get("invoice_no") or b.get("voucher_no") or "").strip()
            b_inv_norm = normalize_invoice_string(b_inv_raw, strip_zeros)
            b_gstin = str(b.get("gstin") or "").strip().upper()
            b_total = round(float(b.get("amount") or max(float(b.get("debit") or 0.0), float(b.get("credit") or 0.0))), 2)
            b_tax = round(float(b.get("tax_amount") or 0.0), 2)

            score = 0.0
            # Invoice number match
            if a_inv_norm and b_inv_norm and a_inv_norm == b_inv_norm:
                score += 40.0
            elif a_inv_raw and b_inv_raw and compute_jaccard_similarity(a_inv_raw, b_inv_raw) >= min_inv_sim:
                score += 30.0

            # GSTIN match
            if a_gstin and b_gstin and a_gstin == b_gstin:
                score += 30.0
            elif not b_gstin:
                score += 10.0

            # Amount proximity
            diff_amt = abs(a_total - b_total)
            if diff_amt <= total_val_tol:
                score += 30.0
            elif diff_amt <= 50.0:
                score += 15.0

            if score > best_score and score >= 40.0:
                best_score = score
                best_b = b

        if best_b:
            matched_b_ids.add(best_b["id"])
            b_inv_raw = str(best_b.get("invoice_no") or best_b.get("voucher_no") or "").strip()
            b_date_str = str(best_b.get("date") or "")[:10]
            b_date = parse_iso_date(b_date_str)
            b_pty = str(best_b.get("party_name") or "Book Party").strip()
            b_gstin = str(best_b.get("gstin") or "").strip().upper()
            b_total = round(float(best_b.get("amount") or max(float(best_b.get("debit") or 0.0), float(best_b.get("credit") or 0.0))), 2)
            b_tax = round(float(best_b.get("tax_amount") or 0.0), 2)
            b_taxable = round(b_total - b_tax if b_total > b_tax else b_total, 2)
            
            # Dynamic intra-state vs inter-state tax split
            is_intra = (not b_gstin or b_gstin[:2] == client_home_state)
            b_cgst = round(float(best_b.get("cgst") or (b_tax / 2 if b_tax > 0 and is_intra else 0.0)), 2)
            b_sgst = round(float(best_b.get("sgst") or (b_tax / 2 if b_tax > 0 and is_intra else 0.0)), 2)
            b_igst = round(float(best_b.get("igst") or (b_tax if b_tax > 0 and not is_intra else 0.0)), 2)

            # Compute differences
            diff_taxable = round(abs(a_taxable - b_taxable), 2)
            diff_cgst = round(abs(a_cgst - b_cgst), 2)
            diff_sgst = round(abs(a_sgst - b_sgst), 2)
            diff_igst = round(abs(a_igst - b_igst), 2)
            diff_tax = round(abs(a_tax - b_tax), 2)
            diff_total = round(abs(a_total - b_total), 2)

            date_diff = 0
            if a_date and b_date:
                date_diff = abs((a_date - b_date).days)

            # Determine Exceptions & Matching Level
            exceptions = []
            if is_dup_a:
                exceptions.append("Duplicate invoice in Source A")
            if a_gstin and b_gstin and a_gstin != b_gstin:
                exceptions.append(f"GSTIN mismatch ({a_gstin} vs {b_gstin})")
            elif not b_gstin and a_gstin:
                exceptions.append("Missing GSTIN in Books")
            elif a_gstin and not is_valid_gstin_format(a_gstin, gstin_pattern):
                exceptions.append("Invalid GSTIN structure")

            if a_inv_norm != normalize_invoice_string(b_inv_raw, strip_zeros):
                exceptions.append(f"Invoice number disparity ({a_inv_raw} vs {b_inv_raw})")

            if date_diff > max_date_days:
                exceptions.append(f"Invoice date timing disparity (> {max_date_days} days)")

            if diff_taxable > taxable_tol:
                exceptions.append(f"Taxable value difference of ₹{diff_taxable:,.2f}")

            if diff_cgst > tax_head_tol or diff_sgst > tax_head_tol or diff_igst > tax_head_tol:
                exceptions.append(f"Tax breakdown variance (CGST diff: ₹{diff_cgst:,.2f}, SGST diff: ₹{diff_sgst:,.2f}, IGST diff: ₹{diff_igst:,.2f})")

            if diff_total > total_val_tol:
                exceptions.append(f"Total invoice value difference of ₹{diff_total:,.2f}")

            if "CRN" in a_doc_type or "CN" in a_inv_raw or "CR" in a_inv_raw:
                exceptions.append("Credit note adjustment mismatch")

            # Classification
            if is_dup_a:
                match_category = "Mismatched"
                item_type = "DUPLICATE_INVOICE"
                status = "Marked for review"
                verdict = "GST reconciliation exception"
            elif len(exceptions) == 0:
                match_category = "Matched"
                item_type = "MATCHED"
                status = "Suggested"
                verdict = "Reconciled clean"
            elif diff_total <= total_val_tol and date_diff <= warn_date_days and (not a_gstin or a_gstin == b_gstin):
                match_category = "Partially matched"
                item_type = "AMOUNT_DIFFERENCE" if diff_taxable > 0 else "PARTIAL_MATCH"
                status = "Suggested"
                verdict = "Potential mismatch"
            else:
                match_category = "Mismatched"
                item_type = "GSTIN_MISMATCH" if (a_gstin != b_gstin and b_gstin) else ("TAX_DIFFERENCE" if diff_tax > 0 else "AMOUNT_DIFFERENCE")
                status = "Marked for review"
                verdict = "Requires auditor review"

            reason_str = " | ".join(exceptions) if exceptions else "Fully matched across GSTIN, Invoice #, Date, Taxable value, and Tax breakdown."

            recon_items.append({
                "ref_a": a_inv_raw,
                "ref_b": b_inv_raw,
                "date_a": a_date_str,
                "date_b": b_date_str,
                "party_a": a_pty,
                "party_b": b_pty,
                "gstin_a": a_gstin,
                "gstin_b": b_gstin,
                "taxable_a": a_taxable,
                "taxable_b": b_taxable,
                "taxable_difference": diff_taxable,
                "cgst_a": a_cgst,
                "cgst_b": b_cgst,
                "cgst_difference": diff_cgst,
                "sgst_a": a_sgst,
                "sgst_b": b_sgst,
                "sgst_difference": diff_sgst,
                "igst_a": a_igst,
                "igst_b": b_igst,
                "igst_difference": diff_igst,
                "tax_a": a_tax,
                "tax_b": b_tax,
                "tax_difference": diff_tax,
                "amount_a": a_total,
                "amount_b": b_total,
                "difference": diff_total,
                "date_diff_days": date_diff,
                "match_category": match_category,
                "item_type": item_type,
                "status": status,
                "match_score": best_score,
                "match_reason": f"[{verdict}] {reason_str}",
                "notes": f"{source_a_type} vs {source_b_type} comparison: {reason_str}"
            })
        else:
            # Missing in Source B (Present in GSTR-2B / Portal, Missing in Books)
            recon_items.append({
                "ref_a": a_inv_raw,
                "ref_b": "N/A",
                "date_a": a_date_str,
                "date_b": None,
                "party_a": a_pty,
                "party_b": "(Missing in Books)",
                "gstin_a": a_gstin,
                "gstin_b": "",
                "taxable_a": a_taxable,
                "taxable_b": 0.0,
                "taxable_difference": a_taxable,
                "cgst_a": a_cgst,
                "cgst_b": 0.0,
                "cgst_difference": a_cgst,
                "sgst_a": a_sgst,
                "sgst_b": 0.0,
                "sgst_difference": a_sgst,
                "igst_a": a_igst,
                "igst_b": 0.0,
                "igst_difference": a_igst,
                "tax_a": a_tax,
                "tax_b": 0.0,
                "tax_difference": a_tax,
                "amount_a": a_total,
                "amount_b": 0.0,
                "difference": a_total,
                "date_diff_days": 0,
                "match_category": "Missing in source B",
                "item_type": "MISSING_IN_BOOKS",
                "status": "Marked for review",
                "match_score": 0.0,
                "match_reason": f"[Requires auditor review] Invoice #{a_inv_raw} of ₹{a_total:,.2f} reflected in {source_a_type} is MISSING from {source_b_type}.",
                "notes": "ITC reflected on portal not availed in books or unrecorded supplier bill."
            })

    # 5. Check remaining unmatched items in Source B (Missing in Source A / GSTR-2B)
    for b in source_b_txs:
        if b["id"] not in matched_b_ids:
            b_inv_raw = str(b.get("invoice_no") or b.get("voucher_no") or f"VCH-{b['id']}").strip()
            b_date_str = str(b.get("date") or "")[:10]
            b_pty = str(b.get("party_name") or "Book Party").strip()
            b_gstin = str(b.get("gstin") or "").strip().upper()
            b_total = round(float(b.get("amount") or max(float(b.get("debit") or 0.0), float(b.get("credit") or 0.0))), 2)
            b_tax = round(float(b.get("tax_amount") or 0.0), 2)
            b_taxable = round(b_total - b_tax if b_total > b_tax else b_total, 2)
            is_intra = (not b_gstin or b_gstin[:2] == client_home_state)
            b_cgst = round(float(b.get("cgst") or (b_tax / 2 if b_tax > 0 and is_intra else 0.0)), 2)
            b_sgst = round(float(b.get("sgst") or (b_tax / 2 if b_tax > 0 and is_intra else 0.0)), 2)
            b_igst = round(float(b.get("igst") or (b_tax if b_tax > 0 and not is_intra else 0.0)), 2)

            recon_items.append({
                "ref_a": "N/A",
                "ref_b": b_inv_raw,
                "date_a": None,
                "date_b": b_date_str,
                "party_a": "(Missing on Portal)",
                "party_b": b_pty,
                "gstin_a": "",
                "gstin_b": b_gstin,
                "taxable_a": 0.0,
                "taxable_b": b_taxable,
                "taxable_difference": b_taxable,
                "cgst_a": 0.0,
                "cgst_b": b_cgst,
                "cgst_difference": b_cgst,
                "sgst_a": 0.0,
                "sgst_b": b_sgst,
                "sgst_difference": b_sgst,
                "igst_a": 0.0,
                "igst_b": b_igst,
                "igst_difference": b_igst,
                "tax_a": 0.0,
                "tax_b": b_tax,
                "tax_difference": b_tax,
                "amount_a": 0.0,
                "amount_b": b_total,
                "difference": b_total,
                "date_diff_days": 0,
                "match_category": "Missing in source A",
                "item_type": "MISSING_IN_PORTAL",
                "status": "Marked for review",
                "match_score": 0.0,
                "match_reason": f"[Requires auditor review] Invoice #{b_inv_raw} of ₹{b_total:,.2f} booked in {source_b_type} is MISSING from {source_a_type} (Section 16(2)(aa) ITC Risk).",
                "notes": "Supplier has not uploaded invoice in GSTR-1 or B2B sales return pending."
            })

    # 6. Compute Aggregated Summary Metrics
    total_a_invoices = len(source_a_txs)
    total_b_invoices = len(source_b_txs)
    total_a_val = round(sum(i["amount_a"] for i in recon_items if i["amount_a"] > 0), 2)
    total_b_val = round(sum(i["amount_b"] for i in recon_items if i["amount_b"] > 0), 2)
    net_val_diff = round(abs(total_a_val - total_b_val), 2)

    total_a_tax = round(sum(i["tax_a"] for i in recon_items if i["tax_a"] > 0), 2)
    total_b_tax = round(sum(i["tax_b"] for i in recon_items if i["tax_b"] > 0), 2)
    net_tax_diff = round(abs(total_a_tax - total_b_tax), 2)

    matched_count = sum(1 for i in recon_items if i["match_category"] == "Matched")
    partial_count = sum(1 for i in recon_items if i["match_category"] == "Partially matched")
    mismatched_count = sum(1 for i in recon_items if i["match_category"] == "Mismatched")
    missing_a_count = sum(1 for i in recon_items if i["match_category"] == "Missing in source A")
    missing_b_count = sum(1 for i in recon_items if i["match_category"] == "Missing in source B")
    discrepancy_count = len(recon_items) - matched_count

    title = recon_title or f"GST Reconciliation ({source_a_type} vs {source_b_type})"

    # 7. Persist to Database
    cursor = conn.execute("""
        INSERT INTO reconciliations (
            engagement_id, recon_type, title, bank_account_name, status,
            total_bank_tx, total_book_tx, matched_count, unmatched_bank_count, unmatched_book_count,
            amount_diff_count, manual_confirmed_count, book_balance, bank_balance,
            net_unreconciled_difference, unreconciled_amount, created_at
        )
        VALUES (?, 'GST Reconciliation', ?, ?, 'Completed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        engagement_id, title, f"{source_a_type} vs {source_b_type}",
        total_a_invoices, total_b_invoices, matched_count,
        missing_a_count, missing_b_count, discrepancy_count, matched_count,
        total_b_val, total_a_val, net_val_diff, net_tax_diff, now_str
    ))
    recon_id = cursor.lastrowid

    # Insert Items
    for i in recon_items:
        conn.execute("""
            INSERT INTO reconciliation_items (
                recon_id, date_a, date_b, ref_a, ref_b, party_a, party_b,
                taxable_a, taxable_b, taxable_difference,
                cgst_a, cgst_b, cgst_difference,
                sgst_a, sgst_b, sgst_difference,
                igst_a, igst_b, igst_difference,
                tax_a, tax_b, tax_difference,
                amount_a, amount_b, difference,
                date_diff_days, gstin_a, gstin_b,
                match_level, match_score, match_category,
                match_reason, item_type, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            recon_id, i["date_a"], i["date_b"], i["ref_a"], i["ref_b"], i["party_a"], i["party_b"],
            i["taxable_a"], i["taxable_b"], i["taxable_difference"],
            i["cgst_a"], i["cgst_b"], i["cgst_difference"],
            i["sgst_a"], i["sgst_b"], i["sgst_difference"],
            i["igst_a"], i["igst_b"], i["igst_difference"],
            i["tax_a"], i["tax_b"], i["tax_difference"],
            i["amount_a"], i["amount_b"], i["difference"],
            i["date_diff_days"], i["gstin_a"], i["gstin_b"],
            "EXACT MATCH" if i["match_category"] == "Matched" else ("HIGH CONFIDENCE" if i["match_category"] == "Partially matched" else "UNMATCHED"),
            i["match_score"], i["match_category"],
            i["match_reason"], i["item_type"], i["status"], i["notes"]
        ))

    # Log in audit trail
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action="EXECUTE_GST_RECONCILIATION",
        module="RECONCILIATION",
        record_id=recon_id,
        user=created_by,
        engagement_id=engagement_id,
        details=f"Executed GST Reconciliation: {matched_count} matched, {partial_count} partial, {mismatched_count} mismatched, {missing_a_count + missing_b_count} missing (Net Tax Diff: ₹{net_tax_diff:,.2f})",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {
        "recon_id": recon_id,
        "title": title,
        "recon_type": "GST Reconciliation",
        "source_a": source_a_type,
        "source_b": source_b_type,
        "summary": {
            "total_source_a_invoices": total_a_invoices,
            "total_source_b_invoices": total_b_invoices,
            "total_source_a_value": total_a_val,
            "total_source_b_value": total_b_val,
            "net_value_difference": net_val_diff,
            "total_source_a_tax": total_a_tax,
            "total_source_b_tax": total_b_tax,
            "net_tax_difference": net_tax_diff,
            "matched_count": matched_count,
            "partially_matched_count": partial_count,
            "mismatched_count": mismatched_count,
            "missing_in_source_a_count": missing_a_count,
            "missing_in_source_b_count": missing_b_count,
            "total_discrepancies": discrepancy_count
        },
        "provenance": {
            "source_type": "GST_PORTAL_AND_BOOKS",
            "calculation_method": "DETERMINISTIC_MULTI_PARAM_RECONCILIATION",
            "calculation_timestamp": now_str,
            "calculation_version": "2.0",
            "data_status": "ACTUAL" if (total_a_invoices > 0 and total_b_invoices > 0) else ("MISSING" if (total_a_invoices == 0 and total_b_invoices == 0) else "INCOMPLETE_DATA")
        },
        "items": recon_items
    }
