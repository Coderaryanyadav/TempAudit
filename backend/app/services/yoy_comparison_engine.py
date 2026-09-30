import math
import re
import io
import csv
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from backend.app.database import get_db_connection

INSUFFICIENT_DATA_MSG = "Insufficient data to determine the reason."

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    if not denominator or abs(denominator) < 1e-6:
        return default
    return round(numerator / denominator, 4)

def derive_prior_financial_year(fy_str: str) -> Optional[str]:
    """Derives exact preceding financial year string (e.g. '2025-26' -> '2024-25', '2024-2025' -> '2023-2024')."""
    if not fy_str:
        return None
    match = re.search(r'(\d{4})[-/](\d{2,4})', str(fy_str).strip())
    if match:
        start_year = int(match.group(1))
        end_part = match.group(2)
        if len(end_part) == 2:
            return f"{start_year - 1}-{(start_year)%100:02d}"
        else:
            return f"{start_year - 1}-{int(end_part) - 1}"
    return None

def calculate_variance(cy: float, py: float, threshold_pct: float = 10.0, materiality: float = 50000.0, is_executive: bool = False) -> Dict[str, Any]:
    """
    Computes absolute difference, percentage change, direction, and significance
    based on the auditor-configured threshold.
    """
    abs_diff = round(cy - py, 2)
    if abs(py) < 1e-4:
        if abs(cy) < 1e-4:
            pct_diff = 0.0
            direction = "No Change"
            change_type = "NO_CHANGE"
        else:
            pct_diff = None
            direction = "New Balance" if cy > 0 else "New Debit Balance"
            change_type = "NEW_BALANCE"
    else:
        pct_diff = round(((cy - py) / abs(py)) * 100.0, 2)
        change_type = "MOVEMENT"
        if abs_diff > 0:
            direction = "Increase"
        elif abs_diff < 0:
            direction = "Decrease"
        else:
            direction = "No Change"

    # Configurable threshold evaluation
    if pct_diff is not None:
        is_significant = (abs(pct_diff) >= threshold_pct) and (abs(abs_diff) >= materiality or is_executive)
    else:
        is_significant = (abs(abs_diff) >= materiality or is_executive)

    # Dynamic Risk Level
    if is_significant:
        if pct_diff is not None and ((abs(pct_diff) >= max(30.0, threshold_pct * 3.0)) or (py > 0 and cy < 0 and "profit" in str(is_executive).lower())):
            risk = "CRITICAL"
        elif pct_diff is not None and abs(pct_diff) >= max(20.0, threshold_pct * 2.0):
            risk = "HIGH"
        else:
            risk = "MEDIUM"
    else:
        risk = "NORMAL"

    return {
        "previous_year": round(py, 2),
        "current_year": round(cy, 2),
        "absolute_difference": abs_diff,
        "percentage_difference": pct_diff,
        "movement_direction": direction,
        "change_type": change_type,
        "is_significant": is_significant,
        "risk": risk
    }

def run_yoy_comparison(
    engagement_id: int,
    py_engagement_id: Optional[int] = None,
    threshold_pct: float = 10.0,
    materiality_threshold: Optional[float] = None
) -> Dict[str, Any]:
    """
    Executes comprehensive Year-on-Year Financial Comparison across:
    1. Executive Financial Heads (Revenue, Expenses, Profit, Assets, Liabilities, Working Capital)
    2. Major Ledger Accounts
    3. Party Balances (Top Debtors and Creditors)
    4. Operational Transaction Volumes & Ticket Sizes
    """
    conn = get_db_connection()

    # 1. Fetch Current Year Engagement
    cy_eng_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    if not cy_eng_row:
        conn.close()
        raise ValueError(f"Engagement #{engagement_id} not found")

    cy_eng = dict(cy_eng_row)
    client_id = cy_eng["client_id"]
    cy_fy = cy_eng.get("financial_year", "2024-25")
    
    # Read materiality threshold from engagement if not explicitly provided
    if materiality_threshold is None:
        materiality_threshold = float(cy_eng.get("materiality_threshold") or 50000.0)

    # 2. Identify or Validate Previous Year Engagement
    py_eng = None
    if py_engagement_id:
        py_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (py_engagement_id,)).fetchone()
        if py_row:
            py_eng = dict(py_row)
    
    if not py_eng:
        # Look for exact prior financial year (e.g. FY 2025-26 -> FY 2024-25)
        target_py_fy = derive_prior_financial_year(cy_fy)
        if target_py_fy:
            py_row = conn.execute("""
                SELECT * FROM engagements
                WHERE client_id = ? AND id != ? AND financial_year = ?
                ORDER BY id DESC LIMIT 1
            """, (client_id, engagement_id, target_py_fy)).fetchone()
            if py_row:
                py_eng = dict(py_row)

    py_id = py_eng["id"] if py_eng else None
    target_py_fy = derive_prior_financial_year(cy_fy)
    py_fy = py_eng.get("financial_year") if py_eng else (target_py_fy or f"PY ({cy_fy} Baseline)")

    # 3. Fetch Existing Reviews & Comments
    rev_rows = conn.execute("SELECT * FROM yoy_comparison_reviews WHERE engagement_id = ?", (engagement_id,)).fetchall()
    reviews_map = {r["item_key"]: dict(r) for r in rev_rows}

    # 4. Fetch CY Transactions
    cy_tx_rows = conn.execute("SELECT * FROM transactions WHERE engagement_id = ?", (engagement_id,)).fetchall()
    cy_txs = [dict(r) for r in cy_tx_rows]

    # 5. Fetch CY Ledgers
    cy_ledger_rows = conn.execute("SELECT * FROM ledgers WHERE engagement_id = ?", (engagement_id,)).fetchall()
    cy_ledgers_db = {r["ledger_name"]: dict(r) for r in cy_ledger_rows}

    # 6. Fetch PY Transactions & Ledgers (or derive from baseline)
    py_txs = []
    py_ledgers_db = {}
    if py_id:
        py_tx_rows = conn.execute("SELECT * FROM transactions WHERE engagement_id = ?", (py_id,)).fetchall()
        py_txs = [dict(r) for r in py_tx_rows]
        py_l_rows = conn.execute("SELECT * FROM ledgers WHERE engagement_id = ?", (py_id,)).fetchall()
        py_ledgers_db = {r["ledger_name"]: dict(r) for r in py_l_rows}

    def infer_account_group(ledger_name: str, given_grp: str = "") -> str:
        grp_l = (given_grp or "").strip().lower()
        name_l = (ledger_name or "").strip().lower()
        if grp_l and grp_l not in ["general", "other", "default", "none", ""]:
            return grp_l
        if any(k in name_l for k in ["sale", "revenue", "turnover", "income"]) and not any(k in name_l for k in ["receivable", "debtor"]):
            return "revenue"
        if any(k in name_l for k in ["purchase", "cogs", "raw material", "freight", "expense", "salary", "wage", "rent", "depreciation", "interest", "cost", "staff", "payroll"]):
            return "expense"
        if any(k in name_l for k in ["debtor", "receivable", "customer", "cash", "bank", "inventory", "stock", "asset", "building", "machinery", "plant", "equipment", "deposit", "advances"]):
            return "asset"
        if any(k in name_l for k in ["creditor", "payable", "vendor", "supplier", "borrowing", "loan", "liability", "capital", "equity", "reserve", "surplus", "provision"]):
            return "liability"
        return "general"

    # Build CY & PY Ledger Balances
    cy_ledger_balances: Dict[str, Dict[str, Any]] = {}
    for t in cy_txs:
        l = (t.get("ledger") or "General").strip()
        grp = (t.get("account_group") or "").strip()
        dr = float(t.get("debit") or 0.0)
        cr = float(t.get("credit") or 0.0)
        if l not in cy_ledger_balances:
            cy_ledger_balances[l] = {"account_group": grp, "debit": 0.0, "credit": 0.0, "count": 0}
        cy_ledger_balances[l]["debit"] += dr
        cy_ledger_balances[l]["credit"] += cr
        cy_ledger_balances[l]["count"] += 1

    py_ledger_balances: Dict[str, Dict[str, Any]] = {}
    if py_txs:
        for t in py_txs:
            l = (t.get("ledger") or "General").strip()
            grp = (t.get("account_group") or "").strip()
            dr = float(t.get("debit") or 0.0)
            cr = float(t.get("credit") or 0.0)
            if l not in py_ledger_balances:
                py_ledger_balances[l] = {"account_group": grp, "debit": 0.0, "credit": 0.0, "count": 0}
            py_ledger_balances[l]["debit"] += dr
            py_ledger_balances[l]["credit"] += cr
            py_ledger_balances[l]["count"] += 1
    # Merge ledgers from ledgers table into balances
    for l_name, l_data in cy_ledgers_db.items():
        if l_name not in cy_ledger_balances:
            cl = float(l_data.get("closing_balance") or 0.0)
            grp = l_data.get("account_group", "General")
            cy_ledger_balances[l_name] = {
                "account_group": grp,
                "debit": cl if cl > 0 else 0.0,
                "credit": abs(cl) if cl < 0 else 0.0,
                "count": 0
            }

    for l_name, l_data in py_ledgers_db.items():
        if l_name not in py_ledger_balances:
            cl = float(l_data.get("closing_balance") or l_data.get("opening_balance") or 0.0)
            grp = l_data.get("account_group", "General")
            py_ledger_balances[l_name] = {
                "account_group": grp,
                "debit": cl if cl > 0 else 0.0,
                "credit": abs(cl) if cl < 0 else 0.0,
                "count": 0
            }

    # Party Balances CY vs PY
    cy_party_balances: Dict[str, Dict[str, float]] = {}
    for t in cy_txs:
        p = (t.get("party_name") or "").strip()
        if p and p not in ["Direct / Cash", "Direct", "Cash", "—"]:
            dr = float(t.get("debit") or 0.0)
            cr = float(t.get("credit") or 0.0)
            amt = float(t.get("amount") or dr or cr)
            if p not in cy_party_balances:
                cy_party_balances[p] = {"debit": 0.0, "credit": 0.0, "total_amt": 0.0, "count": 0}
            cy_party_balances[p]["debit"] += dr
            cy_party_balances[p]["credit"] += cr
            cy_party_balances[p]["total_amt"] += amt
            cy_party_balances[p]["count"] += 1

    py_party_balances: Dict[str, Dict[str, float]] = {}
    for t in py_txs:
        p = (t.get("party_name") or "").strip()
        if p and p not in ["Direct / Cash", "Direct", "Cash", "—"]:
            dr = float(t.get("debit") or 0.0)
            cr = float(t.get("credit") or 0.0)
            amt = float(t.get("amount") or dr or cr)
            if p not in py_party_balances:
                py_party_balances[p] = {"debit": 0.0, "credit": 0.0, "total_amt": 0.0, "count": 0}
            py_party_balances[p]["debit"] += dr
            py_party_balances[p]["credit"] += cr
            py_party_balances[p]["total_amt"] += amt
            py_party_balances[p]["count"] += 1

    # -------------------------------------------------------------
    # SECTION 1: EXECUTIVE TOTALS (P&L, Balance Sheet, Key Heads)
    # -------------------------------------------------------------
    def compute_statement_heads(l_balances: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        rev = 0.0
        other_inc = 0.0
        cogs = 0.0
        emp_exp = 0.0
        fin_cost = 0.0
        depr = 0.0
        other_exp = 0.0
        
        fixed_assets = 0.0
        receivables = 0.0
        cash = 0.0
        bank = 0.0
        inventory = 0.0
        other_ca = 0.0
        
        equity = 0.0
        long_term_debt = 0.0
        payables = 0.0
        other_cl = 0.0

        for l_name, data in l_balances.items():
            grp = infer_account_group(l_name, data.get("account_group", "")).lower()
            name_l = l_name.lower()
            dr = data["debit"]
            cr = data["credit"]
            net_dr = dr - cr
            net_cr = cr - dr

            # Revenue
            if "revenue" in grp or "sales" in grp or "income" in grp:
                val = max(0.0, net_cr if net_cr > 0 else (cr if cr > 0 else dr))
                if "other" in name_l or "interest" in name_l or "discount" in name_l:
                    other_inc += val
                else:
                    rev += val
            # Expenses
            elif "expense" in grp or "purchase" in grp or "direct" in grp:
                val = max(0.0, net_dr if net_dr > 0 else (dr if dr > 0 else cr))
                if any(k in name_l for k in ["purchase", "raw material", "cogs", "freight", "direct"]):
                    cogs += val
                elif any(k in name_l for k in ["salary", "wage", "employee", "bonus", "staff", "pf", "payroll"]):
                    emp_exp += val
                elif any(k in name_l for k in ["interest", "finance", "bank charge", "borrowing cost"]):
                    fin_cost += val
                elif any(k in name_l for k in ["depreciation", "amortisation", "amortization"]):
                    depr += val
                else:
                    other_exp += val
            # Assets
            elif "asset" in grp:
                val = max(0.0, net_dr if net_dr > 0 else (dr if dr > 0 else cr))
                if any(k in name_l for k in ["debtor", "receivable", "customer"]):
                    receivables += val
                elif any(k in name_l for k in ["cash in hand", "petty cash", "cash"]):
                    cash += val
                elif any(k in name_l for k in ["bank", "hdfc", "sbi", "icici", "axis", "current account"]):
                    bank += val
                elif any(k in name_l for k in ["inventory", "stock", "closing stock", "raw stock"]):
                    inventory += val
                elif any(k in name_l for k in ["plant", "machinery", "building", "furniture", "vehicle", "computer", "fixed"]):
                    fixed_assets += val
                else:
                    other_ca += val
            # Liabilities & Equity
            elif "liabilit" in grp or "equity" in grp or "capital" in grp:
                val = max(0.0, net_cr if net_cr > 0 else (cr if cr > 0 else dr))
                if any(k in name_l for k in ["creditor", "payable", "vendor", "supplier"]):
                    payables += val
                elif any(k in name_l for k in ["capital", "share", "reserve", "surplus", "retained"]):
                    equity += val
                elif any(k in name_l for k in ["loan", "term loan", "borrowing", "debenture", "mortgage"]):
                    long_term_debt += val
                else:
                    other_cl += val
            else:
                # Default heuristic based on name
                if "sales" in name_l or "revenue" in name_l:
                    rev += max(0.0, net_cr if net_cr > 0 else (cr if cr > 0 else dr))
                elif "purchase" in name_l or "expense" in name_l:
                    other_exp += max(0.0, net_dr if net_dr > 0 else (dr if dr > 0 else cr))

        total_rev = rev + other_inc
        total_exp = cogs + emp_exp + fin_cost + depr + other_exp
        gross_profit = total_rev - cogs
        operating_profit = gross_profit - emp_exp - other_exp
        pbt = total_rev - total_exp
        pat = pbt * 0.75 if pbt > 0 else pbt # Approximate standard 25% tax provision

        current_assets = receivables + cash + bank + inventory + other_ca
        total_assets = fixed_assets + current_assets
        current_liabilities = payables + other_cl
        total_liab_equity = equity + long_term_debt + current_liabilities

        return {
            "revenue_from_operations": rev,
            "other_income": other_inc,
            "total_revenue": total_rev,
            "cogs": cogs,
            "employee_benefit_expenses": emp_exp,
            "finance_costs": fin_cost,
            "depreciation_amortization": depr,
            "other_expenses": other_exp,
            "total_expenses": total_exp,
            "gross_profit": gross_profit,
            "operating_profit": operating_profit,
            "pbt": pbt,
            "net_profit": pat,
            "fixed_assets": fixed_assets,
            "inventories": inventory,
            "trade_receivables": receivables,
            "cash_in_hand": cash,
            "bank_balances": bank,
            "current_assets": current_assets,
            "total_assets": total_assets,
            "total_equity": equity,
            "long_term_borrowings": long_term_debt,
            "trade_payables": payables,
            "current_liabilities": current_liabilities,
            "total_liabilities": total_liab_equity
        }

    cy_heads = compute_statement_heads(cy_ledger_balances)
    py_heads = compute_statement_heads(py_ledger_balances)

    py_available = bool(py_txs or py_ledgers_db)

    # Executive line items display labels
    exec_definitions = [
        ("revenue_from_operations", "Revenue from Operations", "Revenue"),
        ("other_income", "Other Income", "Revenue"),
        ("total_revenue", "Total Revenue", "Revenue"),
        ("cogs", "Cost of Materials Consumed / COGS", "Expense"),
        ("employee_benefit_expenses", "Employee Benefit Expenses", "Expense"),
        ("finance_costs", "Finance Costs & Bank Charges", "Expense"),
        ("depreciation_amortization", "Depreciation & Amortization", "Expense"),
        ("other_expenses", "Other Operating Expenses", "Expense"),
        ("total_expenses", "Total Expenses", "Expense"),
        ("gross_profit", "Gross Profit", "Profit"),
        ("operating_profit", "Operating Profit (EBITDA / EBIT)", "Profit"),
        ("pbt", "Profit Before Tax (PBT)", "Profit"),
        ("net_profit", "Net Profit After Tax (PAT)", "Profit"),
        ("fixed_assets", "Property, Plant & Equipment (Fixed Assets)", "Asset"),
        ("inventories", "Inventories (Stock in Hand)", "Asset"),
        ("trade_receivables", "Trade Receivables (Debtors)", "Asset"),
        ("cash_in_hand", "Cash in Hand", "Asset"),
        ("bank_balances", "Bank Accounts & Balances", "Asset"),
        ("current_assets", "Total Current Assets", "Asset"),
        ("total_assets", "Total Assets", "Asset"),
        ("total_equity", "Total Equity & Net Worth", "Liability"),
        ("long_term_borrowings", "Long-Term Borrowings", "Liability"),
        ("trade_payables", "Trade Payables (Creditors)", "Liability"),
        ("current_liabilities", "Total Current Liabilities", "Liability"),
        ("total_liabilities", "Total Liabilities & Equity", "Liability")
    ]

    executive_comparison = []
    for key, label, grp in exec_definitions:
        cy_v = cy_heads.get(key, 0.0)
        rev_item = reviews_map.get(key, {})
        if py_available:
            py_v = py_heads.get(key, 0.0)
            var = calculate_variance(cy_v, py_v, threshold_pct, materiality_threshold, is_executive=True)
            prev_y = var["previous_year"]
            abs_diff = var["absolute_difference"]
            pct_diff = var["percentage_difference"]
            mov_dir = var["movement_direction"]
            is_sig = var["is_significant"]
            risk = var["risk"]
        else:
            prev_y = None
            abs_diff = None
            pct_diff = None
            mov_dir = "No Prior Year Data"
            is_sig = False
            risk = "NORMAL"

        executive_comparison.append({
            "item_key": key,
            "account_name": label,
            "category": "Executive Total",
            "group": grp,
            "previous_year": prev_y,
            "current_year": round(cy_v, 2),
            "absolute_difference": abs_diff,
            "percentage_difference": pct_diff,
            "movement_direction": mov_dir,
            "is_significant": is_sig,
            "risk": risk,
            "status": rev_item.get("status", "No Prior Baseline" if not py_available else "Unreviewed"),
            "auditor_comment": rev_item.get("auditor_comment", ""),
            "ai_reason": rev_item.get("ai_reason", "")
        })

    # -------------------------------------------------------------
    # SECTION 2: MAJOR LEDGER ACCOUNTS COMPARISON
    # -------------------------------------------------------------
    all_ledger_names = sorted(set(list(cy_ledger_balances.keys()) + list(py_ledger_balances.keys())))
    major_ledgers_comparison = []

    for l_name in all_ledger_names:
        cy_info = cy_ledger_balances.get(l_name, {"debit": 0.0, "credit": 0.0, "account_group": "General"})
        py_info = py_ledger_balances.get(l_name, {"debit": 0.0, "credit": 0.0, "account_group": "General"})
        raw_grp = cy_info.get("account_group") or py_info.get("account_group") or "General"
        grp = infer_account_group(l_name, raw_grp)

        grp_lower = grp.lower()
        if "asset" in grp_lower or "expense" in grp_lower:
            cy_net = cy_info["debit"] - cy_info["credit"]
            py_net = py_info["debit"] - py_info["credit"]
        else:
            cy_net = cy_info["credit"] - cy_info["debit"]
            py_net = py_info["credit"] - py_info["debit"]

        # Only include active ledgers
        if abs(cy_net) > 0 or abs(py_net) > 0:
            item_k = f"LEDGER_{l_name.upper().replace(' ', '_').replace('/', '_')}"
            rev_item = reviews_map.get(item_k, {})
            if py_available:
                var = calculate_variance(cy_net, py_net, threshold_pct, materiality_threshold, is_executive=False)
                prev_y = var["previous_year"]
                abs_diff = var["absolute_difference"]
                pct_diff = var["percentage_difference"]
                mov_dir = var["movement_direction"]
                is_sig = var["is_significant"]
                risk = var["risk"]
            else:
                prev_y = None
                abs_diff = None
                pct_diff = None
                mov_dir = "No Prior Year Data"
                is_sig = False
                risk = "NORMAL"

            major_ledgers_comparison.append({
                "item_key": item_k,
                "account_name": l_name,
                "category": "Major Ledger",
                "group": grp,
                "previous_year": prev_y,
                "current_year": round(cy_net, 2),
                "absolute_difference": abs_diff,
                "percentage_difference": pct_diff,
                "movement_direction": mov_dir,
                "is_significant": is_sig,
                "risk": risk,
                "status": rev_item.get("status", "No Prior Baseline" if not py_available else "Unreviewed"),
                "auditor_comment": rev_item.get("auditor_comment", ""),
                "ai_reason": rev_item.get("ai_reason", "")
            })

    # Sort major ledgers by absolute difference descending
    major_ledgers_comparison.sort(key=lambda x: abs(x["absolute_difference"]) if x["absolute_difference"] is not None else 0, reverse=True)

    # -------------------------------------------------------------
    # SECTION 3: PARTY BALANCES COMPARISON (Top Customers & Vendors)
    # -------------------------------------------------------------
    all_party_names = sorted(set(list(cy_party_balances.keys()) + list(py_party_balances.keys())))
    party_comparison = []

    for p_name in all_party_names:
        cy_p = cy_party_balances.get(p_name, {"total_amt": 0.0, "debit": 0.0, "credit": 0.0, "count": 0})
        py_p = py_party_balances.get(p_name, {"total_amt": 0.0, "debit": 0.0, "credit": 0.0, "count": 0})
        
        cy_amt = cy_p["total_amt"]
        py_amt = py_p["total_amt"]

        if cy_amt >= 25000.0 or py_amt >= 25000.0:
            item_k = f"PARTY_{p_name.upper().replace(' ', '_').replace('/', '_')}"
            rev_item = reviews_map.get(item_k, {})
            if py_available:
                var = calculate_variance(cy_amt, py_amt, threshold_pct, materiality_threshold, is_executive=False)
                prev_y = var["previous_year"]
                abs_diff = var["absolute_difference"]
                pct_diff = var["percentage_difference"]
                mov_dir = var["movement_direction"]
                is_sig = var["is_significant"]
                risk = var["risk"]
            else:
                prev_y = None
                abs_diff = None
                pct_diff = None
                mov_dir = "No Prior Year Data"
                is_sig = False
                risk = "NORMAL"

            party_comparison.append({
                "item_key": item_k,
                "account_name": p_name,
                "category": "Party Balance",
                "group": "Counterparty",
                "previous_year": prev_y,
                "current_year": round(cy_amt, 2),
                "absolute_difference": abs_diff,
                "percentage_difference": pct_diff,
                "movement_direction": mov_dir,
                "is_significant": is_sig,
                "risk": risk,
                "status": rev_item.get("status", "No Prior Baseline" if not py_available else "Unreviewed"),
                "auditor_comment": rev_item.get("auditor_comment", ""),
                "ai_reason": rev_item.get("ai_reason", "")
            })

    party_comparison.sort(key=lambda x: abs(x["absolute_difference"]) if x["absolute_difference"] is not None else 0, reverse=True)

    # -------------------------------------------------------------
    # SECTION 4: OPERATIONAL VOLUMES & TICKETS
    # -------------------------------------------------------------
    cy_count = len(cy_txs)
    py_count = len(py_txs) if py_txs else len(py_ledger_balances)
    
    cy_tot_dr = sum(float(t.get("debit") or 0.0) for t in cy_txs)
    py_tot_dr = sum(float(t.get("debit") or 0.0) for t in py_txs) if py_txs else sum(v["debit"] for v in py_ledger_balances.values())

    cy_tot_cr = sum(float(t.get("credit") or 0.0) for t in cy_txs)
    py_tot_cr = sum(float(t.get("credit") or 0.0) for t in py_txs) if py_txs else sum(v["credit"] for v in py_ledger_balances.values())

    cy_avg_size = safe_divide(cy_tot_dr + cy_tot_cr, cy_count * 2) if cy_count > 0 else 0.0
    py_avg_size = safe_divide(py_tot_dr + py_tot_cr, py_count * 2) if py_count > 0 else 0.0

    vol_definitions = [
        ("total_transaction_count", "Total Transactions Recorded", py_count, cy_count, "Volume", 1.0),
        ("total_debit_volume", "Total Debit Turnover (₹)", py_tot_dr, cy_tot_dr, "Turnover", materiality_threshold),
        ("total_credit_volume", "Total Credit Turnover (₹)", py_tot_cr, cy_tot_cr, "Turnover", materiality_threshold),
        ("average_transaction_size", "Average Transaction Ticket Size (₹)", py_avg_size, cy_avg_size, "Average", 5000.0),
        ("active_ledgers_count", "Active General Ledgers Count", len(py_ledger_balances), len(cy_ledger_balances), "Volume", 1.0),
        ("active_parties_count", "Active Counterparties Count", len(py_party_balances), len(cy_party_balances), "Volume", 1.0)
    ]

    volume_comparison = []
    for k, lbl, p_v, c_v, grp, mat in vol_definitions:
        rev_item = reviews_map.get(k, {})
        if py_available:
            var = calculate_variance(float(c_v), float(p_v), threshold_pct, mat, is_executive=True)
            prev_y = var["previous_year"]
            abs_diff = var["absolute_difference"]
            pct_diff = var["percentage_difference"]
            mov_dir = var["movement_direction"]
            is_sig = var["is_significant"]
            risk = var["risk"]
        else:
            prev_y = None
            abs_diff = None
            pct_diff = None
            mov_dir = "No Prior Year Data"
            is_sig = False
            risk = "NORMAL"

        volume_comparison.append({
            "item_key": k,
            "account_name": lbl,
            "category": "Operational Metric",
            "group": grp,
            "previous_year": prev_y,
            "current_year": round(float(c_v), 2),
            "absolute_difference": abs_diff,
            "percentage_difference": pct_diff,
            "movement_direction": mov_dir,
            "is_significant": is_sig,
            "risk": risk,
            "status": rev_item.get("status", "No Prior Baseline" if not py_available else "Unreviewed"),
            "auditor_comment": rev_item.get("auditor_comment", ""),
            "ai_reason": rev_item.get("ai_reason", "")
        })

    # Summary KPIs
    all_combined = executive_comparison + major_ledgers_comparison + party_comparison + volume_comparison
    total_items = len(all_combined)
    sig_count = sum(1 for i in all_combined if i["is_significant"])
    crit_count = sum(1 for i in all_combined if i["risk"] == "CRITICAL")
    high_count = sum(1 for i in all_combined if i["risk"] == "HIGH")
    reviewed_count = sum(1 for i in all_combined if i["status"] != "Unreviewed" and i["status"] != "No Prior Baseline")

    conn.close()

    rev_growth = next((i["percentage_difference"] for i in executive_comparison if i["item_key"] == "revenue_from_operations"), None)
    np_growth = next((i["percentage_difference"] for i in executive_comparison if i["item_key"] == "net_profit"), None)

    return {
        "engagement_id": engagement_id,
        "current_financial_year": cy_fy,
        "previous_engagement_id": py_id,
        "previous_financial_year": py_fy if py_available else None,
        "previous_year_data_status": "ACTUAL" if py_available else "NOT_AVAILABLE",
        "configured_threshold_pct": threshold_pct,
        "materiality_threshold": materiality_threshold,
        "summary": {
            "total_comparison_items": total_items,
            "significant_movements_count": sig_count,
            "critical_risk_count": crit_count,
            "high_risk_count": high_count,
            "reviewed_count": reviewed_count,
            "revenue_growth_pct": rev_growth,
            "net_profit_growth_pct": np_growth
        },
        "provenance": {
            "source_type": "GENERAL_LEDGER_TRANSACTIONS",
            "calculation_method": "DETERMINISTIC_YOY_VARIANCE_ANALYSIS",
            "calculation_timestamp": datetime.now().isoformat(),
            "calculation_version": "2.0",
            "data_status": "ACTUAL" if (bool(cy_txs) and bool(py_txs)) else ("MISSING_PY" if bool(cy_txs) else "MISSING"),
            "previous_year_data_status": "ACTUAL" if py_available else "NOT_AVAILABLE"
        },
        "executive_comparison": executive_comparison,
        "major_ledgers_comparison": major_ledgers_comparison,
        "party_comparison": party_comparison,
        "volume_comparison": volume_comparison
    }

def explain_yoy_movement_factually(
    engagement_id: int,
    item_key: str,
    threshold_pct: float = 10.0,
    py_engagement_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Generates a strictly factual AI explanation for large YoY movement.
    Rule: Base explanation ONLY on available transaction and ledger data.
    Never invent or assume unrecorded facts.
    If evidence is insufficient, returns: 'Insufficient data to determine the reason.'
    """
    data = run_yoy_comparison(engagement_id, py_engagement_id=py_engagement_id, threshold_pct=threshold_pct)
    all_items = (
        data["executive_comparison"] +
        data["major_ledgers_comparison"] +
        data["party_comparison"] +
        data["volume_comparison"]
    )
    target = next((i for i in all_items if i["item_key"] == item_key), None)
    if not target:
        reason = INSUFFICIENT_DATA_MSG
        acc_fallback = item_key.replace("LEDGER_", "").replace("_", " ").title()
        save_ai_reason_to_db(engagement_id, item_key, "Ledger", acc_fallback, reason)
        return {
            "item_key": item_key,
            "account_name": acc_fallback,
            "ai_reason": reason,
            "is_sufficient": False
        }

    conn = get_db_connection()
    cy_txs = [dict(r) for r in conn.execute("SELECT * FROM transactions WHERE engagement_id = ?", (engagement_id,)).fetchall()]
    py_id = data.get("previous_engagement_id")
    py_txs = []
    if py_id:
        py_txs = [dict(r) for r in conn.execute("SELECT * FROM transactions WHERE engagement_id = ?", (py_id,)).fetchall()]

    conn.close()

    acc = target["account_name"]
    abs_d = target["absolute_difference"]
    pct_d = target["percentage_difference"]
    dir_m = target["movement_direction"]
    cat = target["category"]

    # If prior year data is missing or change is 0
    if abs_d is None:
        reason = "Prior-year source dataset is not available for YoY variance explanation."
        save_ai_reason_to_db(engagement_id, item_key, cat, acc, reason)
        return {
            "item_key": item_key,
            "account_name": acc,
            "ai_reason": reason,
            "is_sufficient": False
        }

    if abs_d == 0.0:
        return {
            "item_key": item_key,
            "account_name": acc,
            "ai_reason": "No variance observed between current and previous financial year.",
            "is_sufficient": True
        }

    # Extract factual drivers from transactions
    factual_drivers: List[str] = []

    if cat == "Major Ledger":
        # Check specific transactions in CY vs PY for this ledger
        ledger_name = acc
        cy_l_txs = [t for t in cy_txs if (t.get("ledger") or "").strip().lower() == ledger_name.lower()]
        py_l_txs = [t for t in py_txs if (t.get("ledger") or "").strip().lower() == ledger_name.lower()]

        if not cy_l_txs and not py_l_txs:
            reason = INSUFFICIENT_DATA_MSG
            save_ai_reason_to_db(engagement_id, item_key, cat, acc, reason)
            return {"item_key": item_key, "account_name": acc, "ai_reason": reason, "is_sufficient": False}

        # 1. Volume and Average Ticket Driver
        c_cnt = len(cy_l_txs)
        p_cnt = len(py_l_txs)
        if c_cnt > 0 and p_cnt > 0 and c_cnt != p_cnt:
            factual_drivers.append(f"Transaction frequency changed from {p_cnt} entries in PY to {c_cnt} entries in CY ({((c_cnt - p_cnt)/p_cnt)*100:+.1f}%)")

        # 2. Check top party contributors
        cy_party_subtotals: Dict[str, float] = {}
        for t in cy_l_txs:
            p = (t.get("party_name") or "Direct").strip()
            cy_party_subtotals[p] = cy_party_subtotals.get(p, 0.0) + float(t.get("amount") or t.get("debit") or t.get("credit") or 0.0)

        py_party_subtotals: Dict[str, float] = {}
        for t in py_l_txs:
            p = (t.get("party_name") or "Direct").strip()
            py_party_subtotals[p] = py_party_subtotals.get(p, 0.0) + float(t.get("amount") or t.get("debit") or t.get("credit") or 0.0)

        # Identify new counterparties in CY
        new_parties = [p for p in cy_party_subtotals if p not in py_party_subtotals and cy_party_subtotals[p] >= 25000.0]
        if new_parties:
            top_new = sorted(new_parties, key=lambda p: cy_party_subtotals[p], reverse=True)[:2]
            p_desc = ", ".join([f"'{p}' (₹{cy_party_subtotals[p]:,.2f})" for p in top_new])
            factual_drivers.append(f"Addition of new counterparties in CY: {p_desc}")

        # 3. Check for single high-value outlier entry
        if cy_l_txs:
            max_cy_tx = max(cy_l_txs, key=lambda t: float(t.get("amount") or t.get("debit") or t.get("credit") or 0.0))
            max_amt = float(max_cy_tx.get("amount") or max_cy_tx.get("debit") or max_cy_tx.get("credit") or 0.0)
            if max_amt >= 0.4 * abs(target["current_year"]) and max_amt >= 50000.0:
                factual_drivers.append(f"Major individual posting of ₹{max_amt:,.2f} on {max_cy_tx.get('date')} (Voucher {max_cy_tx.get('voucher_no')}) representing {round(max_amt/max(1.0, target['current_year'])*100, 1)}% of total current year balance")

    elif cat == "Party Balance":
        party_name = acc
        cy_p_txs = [t for t in cy_txs if (t.get("party_name") or "").strip().lower() == party_name.lower()]
        py_p_txs = [t for t in py_txs if (t.get("party_name") or "").strip().lower() == party_name.lower()]

        if not cy_p_txs and not py_p_txs:
            reason = INSUFFICIENT_DATA_MSG
            save_ai_reason_to_db(engagement_id, item_key, cat, acc, reason)
            return {"item_key": item_key, "account_name": acc, "ai_reason": reason, "is_sufficient": False}

        if len(cy_p_txs) > 0 and len(py_p_txs) == 0:
            factual_drivers.append(f"New counterparty engaged in CY with {len(cy_p_txs)} transaction(s) totaling ₹{target['current_year']:,.2f}")
        elif len(cy_p_txs) == 0 and len(py_p_txs) > 0:
            factual_drivers.append(f"Zero transactions recorded with this counterparty in CY compared to {len(py_p_txs)} transactions in PY totaling ₹{target['previous_year']:,.2f}")
        else:
            factual_drivers.append(f"Booking volume changed from {len(py_p_txs)} entries (PY) to {len(cy_p_txs)} entries (CY)")
            # Check highest invoice
            if cy_p_txs:
                top_tx = max(cy_p_txs, key=lambda t: float(t.get("amount") or 0.0))
                factual_drivers.append(f"Highest CY invoice: ₹{float(top_tx.get('amount') or 0.0):,.2f} on {top_tx.get('date')} (Invoice {top_tx.get('invoice_no')})")

    elif cat == "Executive Total":
        # Check underlying ledger categories contributing to the executive movement
        if "revenue" in item_key:
            rev_ledgers = [l for l in data["major_ledgers_comparison"] if "sales" in l["account_name"].lower() or "revenue" in l["account_name"].lower()]
            if rev_ledgers:
                top_l = rev_ledgers[0]
                factual_drivers.append(f"Primary revenue driver: '{top_l['account_name']}' moved by ₹{top_l['absolute_difference']:,.2f} ({top_l['percentage_difference']:+.1f}%)")
        elif "expense" in item_key or "cogs" in item_key:
            exp_ledgers = [l for l in data["major_ledgers_comparison"] if "expense" in l["group"].lower() or "purchase" in l["group"].lower()]
            if exp_ledgers:
                top_e = max(exp_ledgers, key=lambda x: abs(x["absolute_difference"]))
                factual_drivers.append(f"Highest expense variance: '{top_e['account_name']}' with net shift of ₹{top_e['absolute_difference']:,.2f} ({top_e['percentage_difference']:+.1f}%)")
        elif "net_profit" in item_key or "gross_profit" in item_key:
            factual_drivers.append(f"Gross margin & operational leverage shift: Total Revenue changed by ₹{data['summary']['revenue_growth_pct']:+.1f}% vs Total Expense change")
        elif "receivable" in item_key:
            top_debtors = data["party_comparison"][:2]
            if top_debtors:
                d_str = ", ".join([f"{p['account_name']} (₹{p['current_year']:,.2f})" for p in top_debtors])
                factual_drivers.append(f"Receivable concentration across top counterparties: {d_str}")

    # Synthesize strict factual explanation
    if not factual_drivers:
        reason = INSUFFICIENT_DATA_MSG
        is_suff = False
    else:
        is_suff = True
        reason = f"Based strictly on available audit ledger data, the {dir_m.lower()} of ₹{abs(abs_d):,.2f} ({pct_d:+.1f}%) in '{acc}' is substantiated by the following empirical driver(s):\n" + "\n".join([f"• {d}" for d in factual_drivers])

    save_ai_reason_to_db(engagement_id, item_key, cat, acc, reason)

    return {
        "item_key": item_key,
        "account_name": acc,
        "ai_reason": reason,
        "is_sufficient": is_suff,
        "percentage_difference": pct_d,
        "absolute_difference": abs_d
    }

def save_ai_reason_to_db(engagement_id: int, item_key: str, category: str, account_name: str, ai_reason: str):
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
        INSERT INTO yoy_comparison_reviews (
            engagement_id, item_key, category, account_name, ai_reason, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(engagement_id, item_key) DO UPDATE SET
            ai_reason = excluded.ai_reason
    """, (engagement_id, item_key, category, account_name, ai_reason, now_str))
    conn.commit()
    conn.close()

def save_yoy_auditor_comment(
    engagement_id: int,
    item_key: str,
    category: str,
    account_name: str,
    status: str,
    comment: str,
    user_name: str
) -> Dict[str, Any]:
    """Updates auditor review status and working paper remarks for a comparative line item."""
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        INSERT INTO yoy_comparison_reviews (
            engagement_id, item_key, category, account_name, status, auditor_comment, reviewed_by, reviewed_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(engagement_id, item_key) DO UPDATE SET
            status = excluded.status,
            auditor_comment = excluded.auditor_comment,
            reviewed_by = excluded.reviewed_by,
            reviewed_at = excluded.reviewed_at
    """, (
        engagement_id, item_key, category, account_name, status, comment, user_name, now_str, now_str
    ))

    # Log to audit trail
    conn.execute("""
        INSERT INTO audit_logs (username, action, entity_type, entity_id, details, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_name, f"YoY Comparative item '{account_name}' updated to '{status}'", "yoy_comparison", engagement_id,
        f"Auditor marked '{account_name}' ({item_key}) as '{status}'. Comment: {comment or 'None'}", now_str
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "item_key": item_key,
        "account_name": account_name,
        "status": status,
        "auditor_comment": comment,
        "reviewed_by": user_name,
        "reviewed_at": now_str
    }

def generate_yoy_csv_report(
    engagement_id: int,
    py_engagement_id: Optional[int] = None,
    threshold_pct: float = 10.0,
    materiality_threshold: float = 50000.0
) -> str:
    """Generates a downloadable CSV report for Year-on-Year Financial Comparison."""
    data = run_yoy_comparison(engagement_id, py_engagement_id, threshold_pct, materiality_threshold)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["FinAuditPro - Year-on-Year Financial Comparison Audit Report"])
    writer.writerow(["Engagement ID", str(engagement_id)])
    writer.writerow(["Current Financial Year", data["current_financial_year"]])
    writer.writerow(["Previous Financial Year", data["previous_financial_year"]])
    writer.writerow(["Configured Threshold (%)", f"{data['configured_threshold_pct']}%"])
    writer.writerow(["Materiality Threshold (INR)", f"₹{data['materiality_threshold']:,.2f}"])
    writer.writerow(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])

    headers = [
        "Category", "Account / Metric Name", f"Previous Year ({data['previous_financial_year']})",
        f"Current Year ({data['current_financial_year']})", "Absolute Difference (INR)",
        "Percentage Change (%)", "Movement Direction", "Significant Movement?", "Risk Level",
        "Auditor Review Status", "Auditor Comment", "Factual AI Explanation"
    ]
    writer.writerow(headers)

    sections = [
        ("1. EXECUTIVE FINANCIAL TOTALS", data["executive_comparison"]),
        ("2. MAJOR LEDGER ACCOUNTS", data["major_ledgers_comparison"]),
        ("3. PARTY BALANCES (TOP DEBTORS & CREDITORS)", data["party_comparison"]),
        ("4. OPERATIONAL TRANSACTION VOLUMES & TICKETS", data["volume_comparison"])
    ]

    for sec_title, items in sections:
        writer.writerow([])
        writer.writerow([f"--- {sec_title} ---"])
        for itm in items:
            pct_s = f"{itm['percentage_difference']:.2f}%" if itm['percentage_difference'] is not None else "N/A (New Balance)"
            writer.writerow([
                itm["category"],
                itm["account_name"],
                f"{itm['previous_year']:.2f}",
                f"{itm['current_year']:.2f}",
                f"{itm['absolute_difference']:.2f}",
                pct_s,
                itm["movement_direction"],
                "YES" if itm["is_significant"] else "NO",
                itm["risk"],
                itm["status"],
                itm["auditor_comment"] or "—",
                itm["ai_reason"] or "—"
            ])

    return output.getvalue()
