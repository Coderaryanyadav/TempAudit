import re
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

def normalize_invoice_no(inv: Optional[str]) -> str:
    """Normalizes invoice string by stripping punctuation, spaces, and case."""
    if not inv:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", str(inv)).upper()

def is_valid_gstin(gstin: Optional[str]) -> bool:
    if not gstin:
        return False
    gstin_clean = str(gstin).strip().upper()
    return bool(re.match(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$", gstin_clean))

def compute_string_similarity(str1: Optional[str], str2: Optional[str]) -> float:
    if not str1 or not str2:
        return 0.0
    tokens1 = set(re.findall(r"\w+", str(str1).lower()))
    tokens2 = set(re.findall(r"\w+", str(str2).lower()))
    stopwords = {"ltd", "pvt", "limited", "private", "co", "corp", "inc", "a", "an", "the", "to", "for", "by", "of", "and"}
    tokens1 -= stopwords
    tokens2 -= stopwords
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)

def run_sales_purchase_reconciliation(
    engagement_id: int,
    recon_type: str = "Sales Reconciliation",  # 'Sales Reconciliation' or 'Purchase Reconciliation'
    register_file_id: Optional[int] = None,
    ledger_name: Optional[str] = None,
    title: Optional[str] = None,
    created_by: str = "admin"
) -> Dict[str, Any]:
    """
    Executes comprehensive 11-point Sales & Purchase Reconciliation comparing:
    - Register Data (Sales Register / Purchase Register)
    - General & Party Ledger Data
    - Available Tax / GST Data (GSTIN, Rates, Tax Amount)
    """
    conn = get_db_connection()
    is_sales = "sales" in recon_type.lower()
    now_str = datetime.now().isoformat()

    # 1. Fetch Register Transactions (Source A)
    # If a specific file is uploaded as Sales/Purchase Register
    register_txs = []
    if register_file_id:
        rows = conn.execute("SELECT * FROM transactions WHERE file_id = ? ORDER BY date ASC, id ASC", (register_file_id,)).fetchall()
        if rows:
            register_txs = [dict(r) for r in rows]

    if not register_txs:
        target_cat = "Sales Register" if is_sales else "Purchase Register"
        rows = conn.execute("""
            SELECT t.* FROM transactions t
            JOIN uploaded_files u ON t.file_id = u.id
            WHERE t.engagement_id = ? AND u.data_category = ?
            ORDER BY t.date ASC, t.id ASC
        """, (engagement_id, target_cat)).fetchall()
        if rows:
            register_txs = [dict(r) for r in rows]

    # 2. Fetch Ledger Transactions (Source B)
    ledger_query = "SELECT * FROM transactions WHERE engagement_id = ?"
    ledger_params = [engagement_id]

    if ledger_name and ledger_name != "All":
        ledger_query += " AND ledger = ?"
        ledger_params.append(ledger_name)
    else:
        # Default to Sales or Purchase related ledgers if no specific file
        if is_sales:
            ledger_query += " AND (LOWER(ledger) LIKE '%sale%' OR LOWER(ledger) LIKE '%revenue%' OR LOWER(ledger) LIKE '%debtor%' OR LOWER(account_group) = 'revenue')"
        else:
            ledger_query += " AND (LOWER(ledger) LIKE '%purchase%' OR LOWER(ledger) LIKE '%expense%' OR LOWER(ledger) LIKE '%creditor%' OR LOWER(account_group) = 'expense')"

    ledger_rows = conn.execute(ledger_query + " ORDER BY date ASC, id ASC", tuple(ledger_params)).fetchall()
    ledger_txs = [dict(r) for r in ledger_rows]

    if not title:
        eng_fy = conn.execute('SELECT financial_year FROM engagements WHERE id = ?', (engagement_id,)).fetchone()
        fy_val = eng_fy['financial_year'] if eng_fy and eng_fy['financial_year'] else '2024-25'
        title = f"{recon_type} FY {fy_val}"

    # 3. Comprehensive 11-Point Cross-Reconciliation Matching Engine
    exceptions_list: List[Dict[str, Any]] = []
    matched_reg_ids: Set[int] = set()
    matched_led_ids: Set[int] = set()

    # Pre-index ledger by normalized invoice number & party
    ledger_by_norm_inv: Dict[str, List[Dict[str, Any]]] = {}
    ledger_by_party_amt: Dict[str, List[Dict[str, Any]]] = {}
    
    for l_tx in ledger_txs:
        l_inv = normalize_invoice_no(l_tx.get("invoice_no") or l_tx.get("voucher_no") or l_tx.get("reference_no"))
        if l_inv:
            ledger_by_norm_inv.setdefault(l_inv, []).append(l_tx)
        
        l_amt = round(float(l_tx.get("amount") or max(float(l_tx.get("debit") or 0.0), float(l_tx.get("credit") or 0.0))), 2)
        l_pty = str(l_tx.get("party_name") or "").strip().lower()
        if l_pty:
            ledger_by_party_amt.setdefault(f"{l_pty}_{l_amt}", []).append(l_tx)

    # -------------------------------------------------------------
    # PASS 1: Check Register Invoices against Ledger & Tax Rules
    # -------------------------------------------------------------
    seen_reg_invs: Dict[str, int] = {}
    seen_gstin_inv: Set[str] = set()

    for r in register_txs:
        r_id = r["id"]
        r_inv_raw = str(r.get("invoice_no") or r.get("voucher_no") or "N/A").strip()
        r_inv_norm = normalize_invoice_no(r_inv_raw)
        r_dt = parse_date(r.get("date"))
        r_pty = str(r.get("party_name") or "").strip()
        r_amt = round(float(r.get("amount") or max(float(r.get("debit") or 0.0), float(r.get("credit") or 0.0))), 2)
        r_tax = round(float(r.get("tax_amount") or 0.0), 2)
        r_gstin = str(r.get("gstin") or "").strip().upper()
        r_desc = str(r.get("description") or "").lower()

        is_credit_note = "credit note" in r_desc or "cr note" in r_desc or "cn" in r_inv_norm or "sales return" in r_desc
        is_debit_note = "debit note" in r_desc or "dr note" in r_desc or "dn" in r_inv_norm or "purchase return" in r_desc

        # CHECK 2: Duplicate Invoices in Register
        if r_inv_norm:
            seen_reg_invs[r_inv_norm] = seen_reg_invs.get(r_inv_norm, 0) + 1
            if seen_reg_invs[r_inv_norm] > 1:
                exceptions_list.append({
                    "invoice_no": r_inv_raw,
                    "party": r_pty or "N/A",
                    "register_amount": r_amt,
                    "ledger_amount": 0.0,
                    "difference": r_amt,
                    "tax_a": r_tax,
                    "tax_b": 0.0,
                    "tax_difference": r_tax,
                    "date_a": r.get("date"),
                    "date_b": None,
                    "date_difference": 0,
                    "gstin_a": r_gstin,
                    "gstin_b": "",
                    "exception_type": "DUPLICATE_INVOICE",
                    "status": "Marked for review",
                    "match_reason": f"Duplicate invoice #{r_inv_raw} recorded {seen_reg_invs[r_inv_norm]} times in Register for ₹{r_amt:,.2f}",
                    "notes": "Verify supplier invoice series and delivery challan to rule out duplicate billing."
                })

        # CHECK 8: Missing GSTIN on B2B Invoices
        if not is_valid_gstin(r_gstin) and r_amt >= 20000:
            exceptions_list.append({
                "invoice_no": r_inv_raw,
                "party": r_pty or "N/A",
                "register_amount": r_amt,
                "ledger_amount": r_amt,
                "difference": 0.0,
                "tax_a": r_tax,
                "tax_b": r_tax,
                "tax_difference": 0.0,
                "date_a": r.get("date"),
                "date_b": r.get("date"),
                "date_difference": 0,
                "gstin_a": r_gstin or "MISSING",
                "gstin_b": "",
                "exception_type": "MISSING_GSTIN",
                "status": "Marked for review",
                "match_reason": f"Missing or invalid 15-char GSTIN for B2B transaction of ₹{r_amt:,.2f} with '{r_pty}'",
                "notes": "Request valid GSTIN certificate to ensure GSTR-1 / GSTR-3B B2B table compliance."
            })

        # CHECK 9: Duplicate GSTIN + Invoice Combination
        if r_gstin and r_inv_norm:
            gstin_inv_key = f"{r_gstin}_{r_inv_norm}"
            if gstin_inv_key in seen_gstin_inv:
                exceptions_list.append({
                    "invoice_no": r_inv_raw,
                    "party": r_pty or "N/A",
                    "register_amount": r_amt,
                    "ledger_amount": 0.0,
                    "difference": r_amt,
                    "tax_a": r_tax,
                    "tax_b": 0.0,
                    "tax_difference": r_tax,
                    "date_a": r.get("date"),
                    "date_b": None,
                    "date_difference": 0,
                    "gstin_a": r_gstin,
                    "gstin_b": r_gstin,
                    "exception_type": "DUPLICATE_GSTIN_INVOICE",
                    "status": "Marked for review",
                    "match_reason": f"Duplicate GSTIN ({r_gstin}) and Invoice #{r_inv_raw} combination booked multiple times",
                    "notes": "Violation of Section 16(2) CGST Act. Verify input tax credit eligibility."
                })
            else:
                seen_gstin_inv.add(gstin_inv_key)

        # Look for matching candidate in Ledger
        matched_l = None
        candidates = ledger_by_norm_inv.get(r_inv_norm, [])
        for l in candidates:
            if l["id"] not in matched_led_ids:
                matched_l = l
                break

        # Fallback to Party + Amount match if invoice formatting differs
        if not matched_l and r_pty:
            party_key = f"{r_pty.lower()}_{r_amt}"
            candidates = ledger_by_party_amt.get(party_key, [])
            for l in candidates:
                if l["id"] not in matched_led_ids:
                    matched_l = l
                    break

        if matched_l:
            matched_reg_ids.add(r_id)
            matched_led_ids.add(matched_l["id"])

            l_id = matched_l["id"]
            l_inv_raw = str(matched_l.get("invoice_no") or matched_l.get("voucher_no") or "N/A").strip()
            l_inv_norm = normalize_invoice_no(l_inv_raw)
            l_dt = parse_date(matched_l.get("date"))
            l_pty = str(matched_l.get("party_name") or "").strip()
            l_amt = round(float(matched_l.get("amount") or max(float(matched_l.get("debit") or 0.0), float(matched_l.get("credit") or 0.0))), 2)
            l_tax = round(float(matched_l.get("tax_amount") or 0.0), 2)
            l_gstin = str(matched_l.get("gstin") or "").strip().upper()

            amt_diff = round(abs(r_amt - l_amt), 2)
            tax_diff = round(abs(r_tax - l_tax), 2)
            date_diff = abs((r_dt - l_dt).days) if (r_dt and l_dt) else 0

            # CHECK 3: Invoice Amount Differences
            if amt_diff > 1.0:
                exceptions_list.append({
                    "invoice_no": r_inv_raw,
                    "party": r_pty or l_pty,
                    "register_amount": r_amt,
                    "ledger_amount": l_amt,
                    "difference": amt_diff,
                    "tax_a": r_tax,
                    "tax_b": l_tax,
                    "tax_difference": tax_diff,
                    "date_a": r.get("date"),
                    "date_b": matched_l.get("date"),
                    "date_difference": date_diff,
                    "gstin_a": r_gstin,
                    "gstin_b": l_gstin,
                    "exception_type": "AMOUNT_DIFFERENCE",
                    "status": "Marked for review",
                    "match_reason": f"Amount Discrepancy: Register ₹{r_amt:,.2f} != Ledger ₹{l_amt:,.2f} (Variance: ₹{amt_diff:,.2f})",
                    "notes": "Inspect underlying tax invoice and journal posting to resolve valuation variance."
                })

            # CHECK 4: Tax Amount Differences
            elif tax_diff > 1.0:
                exceptions_list.append({
                    "invoice_no": r_inv_raw,
                    "party": r_pty or l_pty,
                    "register_amount": r_amt,
                    "ledger_amount": l_amt,
                    "difference": amt_diff,
                    "tax_a": r_tax,
                    "tax_b": l_tax,
                    "tax_difference": tax_diff,
                    "date_a": r.get("date"),
                    "date_b": matched_l.get("date"),
                    "date_difference": date_diff,
                    "gstin_a": r_gstin,
                    "gstin_b": l_gstin,
                    "exception_type": "TAX_DIFFERENCE",
                    "status": "Marked for review",
                    "match_reason": f"GST Tax Discrepancy: Register Tax ₹{r_tax:,.2f} != Ledger Tax ₹{l_tax:,.2f} (Tax Variance: ₹{tax_diff:,.2f})",
                    "notes": "Verify HSN tax rate classification (18% vs 12% vs 5%) and GST return computation."
                })

            # CHECK 5: Date Differences (Timing / Cutoff Lag)
            elif date_diff > 15:
                exceptions_list.append({
                    "invoice_no": r_inv_raw,
                    "party": r_pty or l_pty,
                    "register_amount": r_amt,
                    "ledger_amount": l_amt,
                    "difference": amt_diff,
                    "tax_a": r_tax,
                    "tax_b": l_tax,
                    "tax_difference": tax_diff,
                    "date_a": r.get("date"),
                    "date_b": matched_l.get("date"),
                    "date_difference": date_diff,
                    "gstin_a": r_gstin,
                    "gstin_b": l_gstin,
                    "exception_type": "DATE_DIFFERENCE",
                    "status": "Suggested",
                    "match_reason": f"Cutoff Date Lag: Invoice date ({r.get('date')}) vs Ledger posting date ({matched_l.get('date')}) differs by {date_diff} days",
                    "notes": "Check for period cutoff compliance (SA 500 / SA 520)."
                })

            # CHECK 6: Party Mismatches
            elif compute_string_similarity(r_pty, l_pty) < 0.3 and r_pty and l_pty:
                exceptions_list.append({
                    "invoice_no": r_inv_raw,
                    "party": f"Reg: {r_pty} | Led: {l_pty}",
                    "register_amount": r_amt,
                    "ledger_amount": l_amt,
                    "difference": amt_diff,
                    "tax_a": r_tax,
                    "tax_b": l_tax,
                    "tax_difference": tax_diff,
                    "date_a": r.get("date"),
                    "date_b": matched_l.get("date"),
                    "date_difference": date_diff,
                    "gstin_a": r_gstin,
                    "gstin_b": l_gstin,
                    "exception_type": "PARTY_MISMATCH",
                    "status": "Marked for review",
                    "match_reason": f"Party Name Mismatch: Register '{r_pty}' != Ledger '{l_pty}'",
                    "notes": "Verify if trade name differs from legal entity registration."
                })

            # CHECK 7: Invoice Number Mismatch (Formatting differences)
            elif r_inv_raw != l_inv_raw and r_inv_norm == l_inv_norm:
                exceptions_list.append({
                    "invoice_no": f"{r_inv_raw} ~ {l_inv_raw}",
                    "party": r_pty or l_pty,
                    "register_amount": r_amt,
                    "ledger_amount": l_amt,
                    "difference": amt_diff,
                    "tax_a": r_tax,
                    "tax_b": l_tax,
                    "tax_difference": tax_diff,
                    "date_a": r.get("date"),
                    "date_b": matched_l.get("date"),
                    "date_difference": date_diff,
                    "gstin_a": r_gstin,
                    "gstin_b": l_gstin,
                    "exception_type": "INVOICE_NUMBER_MISMATCH",
                    "status": "Suggested",
                    "match_reason": f"Invoice Number Formatting Discrepancy: Register '{r_inv_raw}' vs Ledger '{l_inv_raw}'",
                    "notes": "Minor typographical formatting variance in prefix or slash characters."
                })

            # CHECK 10 & 11: Credit Note / Debit Note Mismatches
            elif is_credit_note:
                exceptions_list.append({
                    "invoice_no": r_inv_raw,
                    "party": r_pty or l_pty,
                    "register_amount": r_amt,
                    "ledger_amount": l_amt,
                    "difference": amt_diff,
                    "tax_a": r_tax,
                    "tax_b": l_tax,
                    "tax_difference": tax_diff,
                    "date_a": r.get("date"),
                    "date_b": matched_l.get("date"),
                    "date_difference": date_diff,
                    "gstin_a": r_gstin,
                    "gstin_b": l_gstin,
                    "exception_type": "CREDIT_NOTE_MISMATCH",
                    "status": "Suggested",
                    "match_reason": f"Credit Note #{r_inv_raw} for ₹{r_amt:,.2f} matched with ledger adjustment",
                    "notes": "Verify GST credit note tax reversal under Section 34(2) of CGST Act."
                })
            elif is_debit_note:
                exceptions_list.append({
                    "invoice_no": r_inv_raw,
                    "party": r_pty or l_pty,
                    "register_amount": r_amt,
                    "ledger_amount": l_amt,
                    "difference": amt_diff,
                    "tax_a": r_tax,
                    "tax_b": l_tax,
                    "tax_difference": tax_diff,
                    "date_a": r.get("date"),
                    "date_b": matched_l.get("date"),
                    "date_difference": date_diff,
                    "gstin_a": r_gstin,
                    "gstin_b": l_gstin,
                    "exception_type": "DEBIT_NOTE_MISMATCH",
                    "status": "Suggested",
                    "match_reason": f"Debit Note #{r_inv_raw} for ₹{r_amt:,.2f} matched with ledger adjustment",
                    "notes": "Verify supplementary tax invoice / debit note addition under Section 34(1) of CGST Act."
                })
            else:
                # Fully Reconciled Matching Item
                exceptions_list.append({
                    "invoice_no": r_inv_raw,
                    "party": r_pty or l_pty,
                    "register_amount": r_amt,
                    "ledger_amount": l_amt,
                    "difference": 0.0,
                    "tax_a": r_tax,
                    "tax_b": l_tax,
                    "tax_difference": 0.0,
                    "date_a": r.get("date"),
                    "date_b": matched_l.get("date"),
                    "date_difference": date_diff,
                    "gstin_a": r_gstin,
                    "gstin_b": l_gstin,
                    "exception_type": "MATCHED",
                    "status": "Accepted",
                    "match_reason": f"Perfect match: Invoice #{r_inv_raw}, Amount ₹{r_amt:,.2f}, Tax ₹{r_tax:,.2f}",
                    "notes": "Verified against source invoice and general ledger entry."
                })
        else:
            # CHECK 1: Missing Invoices in Ledger (In Register but not in Ledger)
            exceptions_list.append({
                "invoice_no": r_inv_raw,
                "party": r_pty or "N/A",
                "register_amount": r_amt,
                "ledger_amount": 0.0,
                "difference": r_amt,
                "tax_a": r_tax,
                "tax_b": 0.0,
                "tax_difference": r_tax,
                "date_a": r.get("date"),
                "date_b": None,
                "date_difference": 0,
                "gstin_a": r_gstin,
                "gstin_b": "",
                "exception_type": "MISSING_IN_LEDGER",
                "status": "Marked for review",
                "match_reason": f"Invoice #{r_inv_raw} of ₹{r_amt:,.2f} in {recon_type} is MISSING from General Ledger",
                "notes": "Omitted entry in books of accounts. Verify if transaction was booked in suspense or another financial year."
            })

    # -------------------------------------------------------------
    # PASS 2: Missing Invoices in Register (In Ledger but not in Register)
    # -------------------------------------------------------------
    for l in ledger_txs:
        if l["id"] not in matched_led_ids:
            l_inv_raw = str(l.get("invoice_no") or l.get("voucher_no") or f"VCH-{l['id']}").strip()
            l_pty = str(l.get("party_name") or "Ledger Party").strip()
            l_amt = round(float(l.get("amount") or max(float(l.get("debit") or 0.0), float(l.get("credit") or 0.0))), 2)
            l_tax = round(float(l.get("tax_amount") or 0.0), 2)
            l_gstin = str(l.get("gstin") or "").strip().upper()

            if l_amt > 0:
                exceptions_list.append({
                    "invoice_no": l_inv_raw,
                    "party": l_pty,
                    "register_amount": 0.0,
                    "ledger_amount": l_amt,
                    "difference": l_amt,
                    "tax_a": 0.0,
                    "tax_b": l_tax,
                    "tax_difference": l_tax,
                    "date_a": None,
                    "date_b": l.get("date"),
                    "date_difference": 0,
                    "gstin_a": "",
                    "gstin_b": l_gstin,
                    "exception_type": "MISSING_IN_REGISTER",
                    "status": "Marked for review",
                    "match_reason": f"Ledger entry #{l_inv_raw} of ₹{l_amt:,.2f} in '{l.get('ledger')}' is MISSING from {recon_type}",
                    "notes": "Voucher recorded in general ledger without corresponding entry in sales/purchase register."
                })

    # 4. Summary Metrics Computation
    total_reg_invoices = len(register_txs)
    total_led_invoices = len(ledger_txs)
    total_reg_amt = round(sum(float(r.get("amount") or 0.0) for r in register_txs), 2)
    total_led_amt = round(sum(float(l.get("amount") or max(float(l.get("debit") or 0.0), float(l.get("credit") or 0.0))) for l in ledger_txs), 2)
    net_amt_diff = round(abs(total_reg_amt - total_led_amt), 2)

    total_reg_tax = round(sum(float(r.get("tax_amount") or 0.0) for r in register_txs), 2)
    total_led_tax = round(sum(float(l.get("tax_amount") or 0.0) for l in ledger_txs), 2)
    net_tax_diff = round(abs(total_reg_tax - total_led_tax), 2)

    matched_count = sum(1 for e in exceptions_list if e["exception_type"] == "MATCHED")
    discrepancy_count = len(exceptions_list) - matched_count

    # 5. Persist Reconciliation Session to Database
    cursor = conn.execute("""
        INSERT INTO reconciliations (
            engagement_id, recon_type, title, bank_account_name, status,
            total_bank_tx, total_book_tx, matched_count, unmatched_bank_count, unmatched_book_count,
            amount_diff_count, manual_confirmed_count, book_balance, bank_balance,
            net_unreconciled_difference, unreconciled_amount, created_at
        )
        VALUES (?, ?, ?, ?, 'Completed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        engagement_id, recon_type, title, ledger_name or (recon_type + " Ledger"),
        total_reg_invoices, total_led_invoices, matched_count,
        sum(1 for e in exceptions_list if e["exception_type"] == "MISSING_IN_LEDGER"),
        sum(1 for e in exceptions_list if e["exception_type"] == "MISSING_IN_REGISTER"),
        discrepancy_count,
        matched_count,
        total_led_amt, total_reg_amt, net_amt_diff, net_tax_diff, now_str
    ))
    recon_id = cursor.lastrowid

    # Insert Items
    for e in exceptions_list:
        conn.execute("""
            INSERT INTO reconciliation_items (
                recon_id, date_a, date_b, ref_a, ref_b, party_a, party_b,
                amount_a, amount_b, difference, tax_a, tax_b, tax_difference,
                date_diff_days, gstin_a, gstin_b, match_level, match_score,
                match_reason, item_type, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            recon_id, e["date_a"], e["date_b"], e["invoice_no"], e["invoice_no"],
            e["party"], e["party"], e["register_amount"], e["ledger_amount"],
            e["difference"], e["tax_a"], e["tax_b"], e["tax_difference"],
            e["date_difference"], e["gstin_a"], e["gstin_b"],
            "EXACT MATCH" if e["exception_type"] == "MATCHED" else "UNMATCHED",
            100.0 if e["exception_type"] == "MATCHED" else 50.0,
            e["match_reason"], e["exception_type"], e["status"], e["notes"]
        ))

    # Log in audit trail
    conn.execute("""
        INSERT INTO audit_logs (username, action, entity_type, entity_id, details, timestamp)
        VALUES (?, 'EXECUTE_SALES_PURCHASE_RECON', 'reconciliation', ?, ?, ?)
    """, (created_by, recon_id, f"Executed {recon_type}: {matched_count} matched, {discrepancy_count} discrepancies (Net Diff: ₹{net_amt_diff:,.2f})", now_str))

    conn.commit()
    conn.close()

    return {
        "recon_id": recon_id,
        "title": title,
        "recon_type": recon_type,
        "summary": {
            "total_register_invoices": total_reg_invoices,
            "total_ledger_invoices": total_led_invoices,
            "total_register_amount": total_reg_amt,
            "total_ledger_amount": total_led_amt,
            "net_amount_difference": net_amt_diff,
            "total_register_tax": total_reg_tax,
            "total_ledger_tax": total_led_tax,
            "net_tax_difference": net_tax_diff,
            "matched_count": matched_count,
            "discrepancy_count": discrepancy_count
        },
        "provenance": {
            "source_type": "REGISTERS_AND_LEDGERS",
            "calculation_method": "DETERMINISTIC_11_POINT_REGISTER_RECONCILIATION",
            "calculation_timestamp": now_str,
            "calculation_version": "2.0",
            "data_status": "ACTUAL" if (total_reg_invoices > 0 or total_led_invoices > 0) else "MISSING"
        },
        "exceptions": exceptions_list
    }
