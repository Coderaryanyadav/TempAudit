import re
import math
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from backend.app.database import get_db_connection

SUSPENSE_KEYWORDS = [
    "suspense", "diff in tb", "difference in tb", "unadjusted", "uncleared",
    "miscellaneous adjustment", "temp account", "temporary", "dummy", "unallocated",
    "reconciliation diff", "error account"
]

NORMAL_BALANCE_RULES = {
    # Expected normal balances
    "cash": "DEBIT",
    "bank": "DEBIT",
    "debtor": "DEBIT",
    "trade receivable": "DEBIT",
    "customer": "DEBIT",
    "asset": "DEBIT",
    "fixed asset": "DEBIT",
    "investment": "DEBIT",
    "expense": "DEBIT",
    "purchase": "DEBIT",
    "salary": "DEBIT",
    "rent": "DEBIT",
    "creditor": "CREDIT",
    "trade payable": "CREDIT",
    "vendor": "CREDIT",
    "supplier": "CREDIT",
    "liability": "CREDIT",
    "loan": "CREDIT",
    "borrowing": "CREDIT",
    "capital": "CREDIT",
    "equity": "CREDIT",
    "revenue": "CREDIT",
    "sales": "CREDIT",
    "income": "CREDIT"
}

def analyze_trial_balance(engagement_id: int) -> Dict[str, Any]:
    """
    Performs 12 deterministic audit checks on the Trial Balance of the specified engagement.
    Calculations are strictly deterministic (no AI for arithmetic).
    """
    conn = get_db_connection()

    # 1. Fetch all transactions grouped by ledger
    txn_rows = conn.execute("""
        SELECT 
            ledger,
            account_group,
            SUM(debit) as total_debit,
            SUM(credit) as total_credit,
            COUNT(*) as transaction_count,
            MIN(date) as first_txn_date,
            MAX(date) as last_txn_date,
            SUM(CASE WHEN opening_balance != 0 THEN opening_balance ELSE 0 END) as raw_opening,
            SUM(CASE WHEN closing_balance != 0 THEN closing_balance ELSE 0 END) as raw_closing,
            MIN(id) as sample_tx_id
        FROM transactions
        WHERE engagement_id = ?
        GROUP BY ledger, account_group
        ORDER BY account_group ASC, ledger ASC
    """, (engagement_id,)).fetchall()

    # 2. Check if explicit ledgers table has entries for this engagement
    ledger_master_rows = conn.execute("""
        SELECT * FROM ledgers WHERE engagement_id = ?
    """, (engagement_id,)).fetchall()
    master_dict = {r["ledger_name"].strip().lower(): dict(r) for r in ledger_master_rows}

    # Build comprehensive account list
    accounts = []
    grand_total_debit = 0.0
    grand_total_credit = 0.0
    grand_opening_debit = 0.0
    grand_opening_credit = 0.0
    group_summaries = {}

    for r in txn_rows:
        ledger_name = (r["ledger"] or "Untitled Account").strip()
        group = (r["account_group"] or "Unclassified").strip()
        
        dr = round(float(r["total_debit"] or 0.0), 2)
        cr = round(float(r["total_credit"] or 0.0), 2)
        tx_count = r["transaction_count"]
        
        master_info = master_dict.get(ledger_name.lower(), {})
        opening_bal = round(float(master_info.get("opening_balance") or r["raw_opening"] or 0.0), 2)
        
        # Calculate closing balance based on natural group
        # Net balance: positive for debit, negative for credit
        net_flow = dr - cr
        net_closing = round(opening_bal + net_flow, 2)
        
        closing_dr = net_closing if net_closing > 0 else 0.0
        closing_cr = abs(net_closing) if net_closing < 0 else 0.0

        grand_total_debit += dr
        grand_total_credit += cr

        if opening_bal >= 0:
            grand_opening_debit += opening_bal
        else:
            grand_opening_credit += abs(opening_bal)

        acct = {
            "ledger": ledger_name,
            "account_group": group,
            "opening_balance": opening_bal,
            "total_debit": dr,
            "total_credit": cr,
            "net_flow": net_flow,
            "closing_balance": net_closing,
            "closing_debit": closing_dr,
            "closing_credit": closing_cr,
            "transaction_count": tx_count,
            "first_txn_date": r["first_txn_date"],
            "last_txn_date": r["last_txn_date"],
            "sample_tx_id": r["sample_tx_id"]
        }
        accounts.append(acct)

        if group not in group_summaries:
            group_summaries[group] = {
                "total_debit": 0.0,
                "total_credit": 0.0,
                "opening_balance": 0.0,
                "closing_balance": 0.0,
                "ledger_count": 0
            }
        group_summaries[group]["total_debit"] += dr
        group_summaries[group]["total_credit"] += cr
        group_summaries[group]["opening_balance"] += opening_bal
        group_summaries[group]["closing_balance"] += net_closing
        group_summaries[group]["ledger_count"] += 1

    grand_total_debit = round(grand_total_debit, 2)
    grand_total_credit = round(grand_total_credit, 2)
    grand_opening_debit = round(grand_opening_debit, 2)
    grand_opening_credit = round(grand_opening_credit, 2)
    difference = round(abs(grand_total_debit - grand_total_credit), 2)
    is_balanced = difference <= 0.01

    # 3. Execute 12 Deterministic Audit Checks
    exceptions: List[Dict[str, Any]] = []
    
    # -------------------------------------------------------------
    # CHECK 1: Total Debit vs Total Credit (TB Tally)
    # -------------------------------------------------------------
    if not is_balanced:
        higher_side = "Debit" if grand_total_debit > grand_total_credit else "Credit"
        exceptions.append({
            "check_id": "CHK_01_TB_TALLY",
            "check_name": "Trial Balance Out of Balance",
            "severity": "CRITICAL",
            "category": "Accounting Equation",
            "description": f"Trial Balance does not tally. Total Debit (₹{grand_total_debit:,.2f}) differs from Total Credit (₹{grand_total_credit:,.2f}) by ₹{difference:,.2f} ({higher_side} side is higher).",
            "exact_difference": difference,
            "affected_accounts": [a["ledger"] for a in accounts],
            "affected_account_count": len(accounts),
            "recommendation": "Investigate unposted journal vouchers, one-sided import mappings, or omitted suspense ledger entries immediately before finalizing audit.",
            "sa_reference": "SA 500 (Audit Evidence) & SA 240 (Auditor's Responsibilities Relating to Fraud)"
        })

    # -------------------------------------------------------------
    # CHECK 2: Opening Balance Consistency Check
    # -------------------------------------------------------------
    opening_diff = round(abs(grand_opening_debit - grand_opening_credit), 2)
    if opening_diff > 0.01 and (grand_opening_debit > 0 or grand_opening_credit > 0):
        exceptions.append({
            "check_id": "CHK_02_OPENING_MISMATCH",
            "check_name": "Opening Trial Balance Mismatch",
            "severity": "HIGH",
            "category": "Opening Position",
            "description": f"Opening balances brought forward do not balance. Opening Debit (₹{grand_opening_debit:,.2f}) vs Opening Credit (₹{grand_opening_credit:,.2f}) has a variance of ₹{opening_diff:,.2f}.",
            "exact_difference": opening_diff,
            "affected_accounts": [a["ledger"] for a in accounts if a["opening_balance"] != 0],
            "affected_account_count": len([a for a in accounts if a["opening_balance"] != 0]),
            "recommendation": "Reconcile opening figures with the previous year's audited balance sheet (SA 510).",
            "sa_reference": "SA 510 (Initial Audit Engagements — Opening Balances)"
        })

    # -------------------------------------------------------------
    # CHECK 3: Closing Balance Consistency Check
    # -------------------------------------------------------------
    closing_inconsistent = []
    for a in accounts:
        expected = round(a["opening_balance"] + a["total_debit"] - a["total_credit"], 2)
        if abs(a["closing_balance"] - expected) > 0.01:
            closing_inconsistent.append(a["ledger"])
    
    if closing_inconsistent:
        exceptions.append({
            "check_id": "CHK_03_CLOSING_ROLL_FORWARD",
            "check_name": "Closing Balance Roll-Forward Inconsistency",
            "severity": "HIGH",
            "category": "Arithmetic Verification",
            "description": f"{len(closing_inconsistent)} account(s) have closing balances that deviate from the arithmetic roll-forward formula (Opening + Debit - Credit).",
            "affected_accounts": closing_inconsistent,
            "affected_account_count": len(closing_inconsistent),
            "recommendation": "Review automated journal adjustments or period-end closing vouchers.",
            "sa_reference": "SA 520 (Analytical Procedures)"
        })

    # -------------------------------------------------------------
    # CHECK 4: Accounts with Unusual / Abnormal Balances
    # -------------------------------------------------------------
    unusual_balance_accounts = []
    for a in accounts:
        lname = a["ledger"].lower()
        grp = a["account_group"].lower()
        net = a["closing_balance"]
        
        # Cash in hand should NEVER have credit balance
        if "cash" in lname and "cash credit" not in lname and "petty cash" in lname:
            if net < 0:
                unusual_balance_accounts.append({
                    "ledger": a["ledger"],
                    "reason": f"Cash account has negative/credit balance of ₹{abs(net):,.2f} (Physically impossible cash credit).",
                    "balance": net
                })
        elif "cash" in lname and "credit" not in lname and "bank" not in lname and "discount" not in lname:
            if net < 0:
                unusual_balance_accounts.append({
                    "ledger": a["ledger"],
                    "reason": f"Cash in Hand has credit balance of ₹{abs(net):,.2f}.",
                    "balance": net
                })
        # Bank accounts without OD designation
        elif "bank" in lname and "od" not in lname and "overdraft" not in lname and "cc" not in lname:
            if net < -50000:
                unusual_balance_accounts.append({
                    "ledger": a["ledger"],
                    "reason": f"Regular Bank account has substantial overdraft/credit balance of ₹{abs(net):,.2f} without documented CC/OD facility.",
                    "balance": net
                })
        # Sundry Debtors with net credit balance
        elif ("debtor" in lname or "receivable" in lname or grp == "current assets") and "prov" not in lname:
            if net < -10000:
                unusual_balance_accounts.append({
                    "ledger": a["ledger"],
                    "reason": f"Debtors / Trade Receivables head reflects credit balance of ₹{abs(net):,.2f} (Potential unadjusted customer advances).",
                    "balance": net
                })
        # Sundry Creditors with net debit balance
        elif ("creditor" in lname or "payable" in lname or grp == "current liabilities"):
            if net > 10000:
                unusual_balance_accounts.append({
                    "ledger": a["ledger"],
                    "reason": f"Creditors / Trade Payables head reflects debit balance of ₹{net:,.2f} (Potential unadjusted supplier advances).",
                    "balance": net
                })
        # Sales / Revenue with net debit balance
        elif grp in ["revenue", "sales", "income"] or "sales" in lname or "revenue" in lname:
            if a["total_debit"] > a["total_credit"] and (a["total_debit"] - a["total_credit"]) > 5000:
                unusual_balance_accounts.append({
                    "ledger": a["ledger"],
                    "reason": f"Revenue account has net debit balance of ₹{(a['total_debit'] - a['total_credit']):,.2f} (Abnormal sales returns or improper debit posting).",
                    "balance": net
                })
        # Capital with net debit balance
        elif grp in ["equity", "capital"] or "capital account" in lname or "share capital" in lname:
            if net > 0 and (a["total_debit"] > a["total_credit"]):
                unusual_balance_accounts.append({
                    "ledger": a["ledger"],
                    "reason": f"Capital/Equity account shows net debit balance of ₹{(a['total_debit'] - a['total_credit']):,.2f} (Capital erosion or excessive partner drawings).",
                    "balance": net
                })

    if unusual_balance_accounts:
        exceptions.append({
            "check_id": "CHK_04_UNUSUAL_BALANCES",
            "check_name": "Accounts with Abnormal / Inverted Balances",
            "severity": "HIGH",
            "category": "Classification & Grouping",
            "description": f"{len(unusual_balance_accounts)} account(s) show balances contrary to their accounting nature (e.g. negative cash, debtor credit balances, capital deficits).",
            "affected_accounts": [u["ledger"] for u in unusual_balance_accounts],
            "affected_account_count": len(unusual_balance_accounts),
            "details_list": unusual_balance_accounts,
            "recommendation": "Verify whether customer credit balances represent advances (Schedule III reclassification) and inspect physical cash book vouchers.",
            "sa_reference": "SA 505 (External Confirmations) & Schedule III of Companies Act 2013"
        })

    # -------------------------------------------------------------
    # CHECK 5: Missing Account Values / Blank Classification
    # -------------------------------------------------------------
    missing_accounts = []
    for a in accounts:
        if a["ledger"].lower() in ["", "untitled", "unknown", "null", "none"] or a["account_group"].lower() in ["unclassified", "other", ""]:
            missing_accounts.append(a["ledger"])
    
    if missing_accounts:
        exceptions.append({
            "check_id": "CHK_05_MISSING_ACCOUNT_INFO",
            "check_name": "Unclassified or Unnamed Account Heads",
            "severity": "MEDIUM",
            "category": "Data Quality",
            "description": f"{len(missing_accounts)} account head(s) lack proper accounting taxonomy or group classification (e.g. Assets, Liabilities, Revenue, Expense).",
            "affected_accounts": missing_accounts,
            "affected_account_count": len(missing_accounts),
            "recommendation": "Assign standard Schedule III account groupings to ensure accurate financial statement generation.",
            "sa_reference": "CARO 2020 & Schedule III Classification"
        })

    # -------------------------------------------------------------
    # CHECK 6: Duplicate or Redundant Account Heads
    # -------------------------------------------------------------
    seen_names = {}
    duplicate_accounts = []
    for a in accounts:
        # Simplify name: remove spaces, punctuation, lowercase
        simple_name = re.sub(r'[^a-z0-9]', '', a["ledger"].lower())
        # Remove common tokens like a/c, ac, account
        simple_name = re.sub(r'(ac|account|acc)$', '', simple_name)
        if simple_name in seen_names:
            duplicate_accounts.append(f"{a['ledger']} (conflicts with {seen_names[simple_name]})")
        else:
            seen_names[simple_name] = a["ledger"]
    
    if duplicate_accounts:
        exceptions.append({
            "check_id": "CHK_06_DUPLICATE_ACCOUNTS",
            "check_name": "Potential Duplicate / Redundant Account Heads",
            "severity": "MEDIUM",
            "category": "Master Data Integrity",
            "description": f"{len(duplicate_accounts)} account pair(s) have nearly identical names and may represent duplicate ledger creation in client accounting software.",
            "affected_accounts": duplicate_accounts,
            "affected_account_count": len(duplicate_accounts),
            "recommendation": "Recommend merging duplicate ledger accounts to avoid splitting vendor balances and TDS compliance records.",
            "sa_reference": "SA 315 (Identifying and Assessing the Risks of Material Misstatement)"
        })

    # -------------------------------------------------------------
    # CHECK 7: Negative Values in Debit/Credit Columns
    # -------------------------------------------------------------
    # Query raw transaction negative debits/credits
    neg_txns = conn.execute("""
        SELECT ledger, COUNT(*) as neg_cnt, SUM(CASE WHEN debit < 0 THEN 1 ELSE 0 END) as neg_dr,
               SUM(CASE WHEN credit < 0 THEN 1 ELSE 0 END) as neg_cr
        FROM transactions
        WHERE engagement_id = ? AND (debit < 0 OR credit < 0)
        GROUP BY ledger
    """, (engagement_id,)).fetchall()

    if neg_txns:
        neg_ledgers = [r["ledger"] for r in neg_txns]
        exceptions.append({
            "check_id": "CHK_07_NEGATIVE_POSTINGS",
            "check_name": "Negative Amounts in Debit/Credit Columns",
            "severity": "MEDIUM",
            "category": "Data Entry Integrity",
            "description": f"{len(neg_ledgers)} account(s) contain negative debit or credit amounts. Standard accounting requires posting positive values to the opposite column.",
            "affected_accounts": neg_ledgers,
            "affected_account_count": len(neg_ledgers),
            "recommendation": "Rectify negative entries by transferring to the appropriate opposite column to prevent turnover distortion.",
            "sa_reference": "SA 500 (Audit Evidence — Accuracy of Accounting Records)"
        })

    # -------------------------------------------------------------
    # CHECK 8: Suspense, Difference, and Clearing Accounts
    # -------------------------------------------------------------
    suspense_found = []
    for a in accounts:
        lname = a["ledger"].lower()
        if any(kw in lname for kw in SUSPENSE_KEYWORDS):
            suspense_found.append({
                "ledger": a["ledger"],
                "balance": a["closing_balance"],
                "total_debit": a["total_debit"],
                "total_credit": a["total_credit"]
            })

    if suspense_found:
        total_suspense_val = round(sum(abs(s["balance"]) for s in suspense_found), 2)
        exceptions.append({
            "check_id": "CHK_08_SUSPENSE_ACCOUNTS",
            "check_name": "Balances Parked in Suspense / Clearing Accounts",
            "severity": "CRITICAL" if total_suspense_val > 10000 else "HIGH",
            "category": "Audit Risk & Integrity",
            "description": f"{len(suspense_found)} suspense / unadjusted account(s) identified with cumulative uncleared balance of ₹{total_suspense_val:,.2f}.",
            "affected_accounts": [s["ledger"] for s in suspense_found],
            "affected_account_count": len(suspense_found),
            "details_list": suspense_found,
            "recommendation": "Suspense accounts must be completely analyzed, identified, and cleared before issuing audit report. Un-cleared suspense balance requires qualification.",
            "sa_reference": "SA 705 (Modifications to the Opinion in the Independent Auditor's Report)"
        })

    # -------------------------------------------------------------
    # CHECK 9: Round-Number Anomalies in Movement
    # -------------------------------------------------------------
    round_number_accounts = []
    for a in accounts:
        dr = a["total_debit"]
        cr = a["total_credit"]
        # Check if debit or credit is exact multiple of 1,00,000 or 50,000 and > 1,00,000 with zero decimals
        if (dr > 100000 and dr % 50000 == 0) or (cr > 100000 and cr % 50000 == 0):
            round_number_accounts.append({
                "ledger": a["ledger"],
                "total_debit": dr,
                "total_credit": cr
            })

    if len(round_number_accounts) >= 1:
        exceptions.append({
            "check_id": "CHK_09_ROUND_NUMBER_ANOMALY",
            "check_name": "Round-Number Journal Anomalies",
            "severity": "LOW",
            "category": "Fraud Risk & Journal Testing",
            "description": f"{len(round_number_accounts)} account(s) exhibit major transactions in exact round figures (multiples of ₹50,000 / ₹1,00,000), which frequently indicates non-system estimated journal entries.",
            "affected_accounts": [r["ledger"] for r in round_number_accounts[:10]],
            "affected_account_count": len(round_number_accounts),
            "recommendation": "Test sample journal entries for documentary support, authorized approvals, and business rationale (SA 240 journal testing).",
            "sa_reference": "SA 240 (The Auditor's Responsibilities Relating to Fraud in an Audit of Financial Statements)"
        })

    # -------------------------------------------------------------
    # CHECK 10: Accounts with Sudden Movement / Outlier Turnover
    # -------------------------------------------------------------
    sudden_movement_accounts = []
    all_turnovers = [a["total_debit"] + a["total_credit"] for a in accounts]
    avg_turnover = sum(all_turnovers) / len(all_turnovers) if all_turnovers else 0.0

    for a in accounts:
        turnover = a["total_debit"] + a["total_credit"]
        # If turnover is greater than 5x average turnover and has low opening balance
        if turnover > (5 * avg_turnover) and turnover > 500000 and abs(a["opening_balance"]) < (0.05 * turnover):
            sudden_movement_accounts.append({
                "ledger": a["ledger"],
                "turnover": turnover,
                "opening_balance": a["opening_balance"]
            })

    if sudden_movement_accounts:
        exceptions.append({
            "check_id": "CHK_10_SUDDEN_MOVEMENT",
            "check_name": "Accounts with Sudden High-Velocity Turnover",
            "severity": "MEDIUM",
            "category": "Analytical Procedures",
            "description": f"{len(sudden_movement_accounts)} account(s) show sudden disproportionate transaction volume (>5x average TB turnover) relative to minimal opening position.",
            "affected_accounts": [s["ledger"] for s in sudden_movement_accounts],
            "affected_account_count": len(sudden_movement_accounts),
            "recommendation": "Perform substantive analytical procedures and check for unusual business contracts or transactions with related parties.",
            "sa_reference": "SA 520 (Analytical Procedures) & SA 550 (Related Parties)"
        })

    # -------------------------------------------------------------
    # CHECK 11: Single-Transaction / One-Sided Accounts
    # -------------------------------------------------------------
    one_sided_accounts = []
    for a in accounts:
        if a["transaction_count"] == 1 and (a["total_debit"] > 100000 or a["total_credit"] > 100000):
            one_sided_accounts.append(a["ledger"])
    
    if one_sided_accounts:
        exceptions.append({
            "check_id": "CHK_11_SINGLE_ENTRY_HIGH_VALUE",
            "check_name": "High-Value Single-Transaction Accounts",
            "severity": "LOW",
            "category": "Substantive Testing",
            "description": f"{len(one_sided_accounts)} account(s) have only a single high-value posting (>₹1,00,000) during the entire financial year.",
            "affected_accounts": one_sided_accounts,
            "affected_account_count": len(one_sided_accounts),
            "recommendation": "Inspect underlying contract, invoice, and board approval for isolated lump-sum payments.",
            "sa_reference": "SA 500 (Audit Evidence)"
        })

    # -------------------------------------------------------------
    # CHECK 12: Material Concentration Accounts
    # -------------------------------------------------------------
    material_threshold = 0.20 * grand_total_debit if grand_total_debit > 0 else 500000
    material_accounts = [a["ledger"] for a in accounts if a["total_debit"] >= material_threshold or a["total_credit"] >= material_threshold]
    if material_accounts:
        exceptions.append({
            "check_id": "CHK_12_MATERIAL_CONCENTRATION",
            "check_name": "Materiality & High-Concentration Accounts",
            "severity": "LOW",
            "category": "Materiality Assessment",
            "description": f"{len(material_accounts)} account(s) each represent >20% of total financial turnover and constitute key audit matters (KAM).",
            "affected_accounts": material_accounts,
            "affected_account_count": len(material_accounts),
            "recommendation": "Determine specific performance materiality thresholds and sample sizes for these primary ledgers (SA 320).",
            "sa_reference": "SA 320 (Materiality in Planning and Performing an Audit)"
        })

    # 4. Aggregate Risk Summary
    critical_count = sum(1 for e in exceptions if e["severity"] == "CRITICAL")
    high_count = sum(1 for e in exceptions if e["severity"] == "HIGH")
    medium_count = sum(1 for e in exceptions if e["severity"] == "MEDIUM")
    low_count = sum(1 for e in exceptions if e["severity"] == "LOW")

    # Set overall risk rating
    overall_risk = "LOW"
    if critical_count > 0 or not is_balanced:
        overall_risk = "CRITICAL"
    elif high_count > 0:
        overall_risk = "HIGH"
    elif medium_count > 0:
        overall_risk = "MEDIUM"

    # Distinct accounts with exceptions
    all_affected_set = set()
    for e in exceptions:
        for acc in e.get("affected_accounts", []):
            if isinstance(acc, str) and not acc.startswith("Potential") and "(" not in acc:
                all_affected_set.add(acc)
            elif isinstance(acc, str) and "(" in acc:
                clean_name = acc.split("(")[0].strip()
                if clean_name:
                    all_affected_set.add(clean_name)

    conn.close()

    return {
        "engagement_id": engagement_id,
        "is_balanced": is_balanced,
        "grand_total_debit": grand_total_debit,
        "grand_total_credit": grand_total_credit,
        "difference": difference,
        "grand_opening_debit": grand_opening_debit,
        "grand_opening_credit": grand_opening_credit,
        "opening_difference": opening_diff,
        "total_accounts_count": len(accounts),
        "accounts_with_exceptions_count": len(all_affected_set),
        "overall_risk_rating": overall_risk,
        "risk_summary": {
            "critical_exceptions": critical_count,
            "high_exceptions": high_count,
            "medium_exceptions": medium_count,
            "low_exceptions": low_count,
            "total_exceptions": len(exceptions)
        },
        "exceptions": exceptions,
        "group_summaries": group_summaries,
        "provenance": {
            "source_type": "GENERAL_LEDGER_TRANSACTIONS",
            "calculation_method": "DETERMINISTIC_12_POINT_TB_ANALYSIS",
            "calculation_timestamp": datetime.now().isoformat(),
            "calculation_version": "2.0",
            "data_status": "ACTUAL" if len(txn_rows) > 0 else "MISSING"
        },
        "accounts": accounts
    }

def get_ai_explanation_for_exception(check_id: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Provides deterministic ICAI-grounded audit guidance and analytical explanation
    for any selected trial balance exception without computing the numerical difference itself.
    """
    ex_name = context_data.get("check_name", "Trial Balance Discrepancy")
    diff = context_data.get("exact_difference", 0.0)
    affected = context_data.get("affected_accounts", [])
    sa_ref = context_data.get("sa_reference", "SA 500 (Audit Evidence)")

    guidance_map = {
        "CHK_01_TB_TALLY": (
            "An unbalanced Trial Balance represents an omission or corruption in the underlying double-entry postings. "
            "Under Indian Accounting Standards (Ind AS 1 / AS 1) and ICAI Guidance Notes, financial statements cannot be prepared "
            "from an unbalanced trial balance. The exact difference indicates either a single unposted leg of a journal entry, "
            "a translocated decimal, or a reversal posting error. The auditor must not adjust this through equity without full substantiation."
        ),
        "CHK_02_OPENING_MISMATCH": (
            "Pursuant to SA 510 'Initial Audit Engagements — Opening Balances', the auditor is required to obtain sufficient appropriate audit evidence "
            "that the opening balances do not contain misstatements that materially affect the current period's financial statements. "
            "A variance in opening balances indicates an unauthorized post-closing entry in the prior period's software data."
        ),
        "CHK_04_UNUSUAL_BALANCES": (
            "Normal balance conventions reflect the fundamental nature of accounts. A credit balance in Cash in Hand is legally and physically "
            "impossible and points to unrecorded cash receipts, suppression of sales, or wrong entry dates. Credit balances in Debtors must be evaluated "
            "for reclassification as Current Liabilities (Advances from Customers) under Schedule III of the Companies Act 2013."
        ),
        "CHK_08_SUSPENSE_ACCOUNTS": (
            "Suspense and difference accounts are transit heads used by bookkeepers to force a Trial Balance to tally. "
            "ICAI Standards on Auditing strictly require that all suspense balances be investigated and zeroed out before audit sign-off. "
            "Unresolved suspense balances exceeding materiality require a qualified or adverse audit opinion under SA 705."
        ),
        "CHK_09_ROUND_NUMBER_ANOMALY": (
            "Under SA 240, journal entries with round numbers or ending in multiple zeros in non-routine accounts are considered classic red flags "
            "for management override of controls. Auditors should inspect journal voucher authorization, narration, and supporting third-party invoices."
        )
    }

    explanation = guidance_map.get(
        check_id,
        f"This condition highlights an analytical discrepancy under {sa_ref}. The auditor should apply substantive testing and obtain management representation."
    )

    return {
        "check_id": check_id,
        "check_name": ex_name,
        "sa_reference": sa_ref,
        "explanation": explanation,
        "suggested_audit_procedures": [
            "Inspect primary journal vouchers and authorization logs.",
            "Verify third-party confirmations (SA 505) for trade parties.",
            "Review bank reconciliation statements (BRS) for unrecorded cheques.",
            "Cross-verify opening figures against previous year's signed Tax Audit Report (Form 3CD)."
        ],
        "compliance_note": "Deterministic explanation generated locally by FinAuditPro Core Audit Rule Engine."
    }
