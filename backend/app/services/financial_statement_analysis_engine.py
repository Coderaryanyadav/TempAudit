import math
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.app.database import get_db_connection

def safe_div(n: Optional[float], d: Optional[float], default: Any = None) -> Optional[float]:
    """
    Safely computes n / d.
    Returns default (None by default) if d is 0, None, or undefined, avoiding false zero ratio values.
    """
    if n is None or d is None:
        return default
    if abs(d) < 1e-6:
        return default
    return round(n / d, 4)

def calculate_change(cy: Optional[float], py: Optional[float]) -> Dict[str, Any]:
    """
    Computes absolute and percentage change between Current Year (CY) and Previous Year (PY).
    Properly handles missing/undefined values without fabricating zeroes.
    """
    if cy is None or py is None:
        return {
            "current_value": cy,
            "previous_value": py,
            "absolute_difference": None,
            "percentage_difference": None,
            "change_type": "NO_PRIOR_YEAR_DATA" if py is None else "UNDEFINED_METRIC",
            "is_significant": False
        }

    abs_diff = round(cy - py, 2)
    if abs(py) < 1e-4:
        pct_diff = None
        change_type = "NO_CHANGE" if abs(cy) < 1e-4 else "NEW_BALANCE"
    else:
        pct_diff = round(((cy - py) / abs(py)) * 100.0, 2)
        change_type = "MOVEMENT"

    is_significant = (abs(pct_diff) >= 20.0 if pct_diff is not None else (change_type == "NEW_BALANCE" and abs(abs_diff) > 0)) or abs(abs_diff) >= 500000.0
    return {
        "current_value": round(cy, 2),
        "previous_value": round(py, 2),
        "absolute_difference": abs_diff,
        "percentage_difference": pct_diff,
        "change_type": change_type,
        "is_significant": is_significant
    }

def get_possible_explanations(metric_key: str, cy: Optional[float], py: Optional[float], pct_diff: Optional[float] = None) -> List[str]:
    """Provides plausible statutory and business hypothesis categories for significant financial movements (requires auditor corroboration)."""
    if cy is None or py is None:
        return []
    if pct_diff is None:
        is_increase = cy > py
    else:
        is_increase = pct_diff > 0
    k = metric_key.lower()

    if "revenue" in k or "sales" in k:
        raw = [
            "Expansion into new market territories / distributor addition" if is_increase else "Demand softening / key client contract non-renewal",
            "Price revision / inflation adjustments" if is_increase else "Competitive discounting / volume drop",
            "Introduction of new product lines" if is_increase else "Supply chain bottleneck impacting deliveries"
        ]
    elif "cogs" in k or "purchase" in k or "material" in k:
        raw = [
            "Raw material commodity price inflation" if is_increase else "Favorable procurement terms / bulk discounts",
            "Production volume escalation" if is_increase else "Shift toward higher margin traded goods",
            "Import tariff / freight rate fluctuations" if is_increase else "Inventory optimization / yield improvements"
        ]
    elif "gross_profit" in k or "gp_margin" in k:
        raw = [
            "Product mix shift toward higher margin value-added products" if is_increase else "Raw material input cost escalation not passed to customers",
            "Better manufacturing capacity utilization" if is_increase else "Pricing pressure from competitors",
            "Direct labor productivity gains" if is_increase else "Higher subcontracting / job work costs"
        ]
    elif "net_profit" in k or "np_margin" in k or "operating_margin" in k:
        raw = [
            "Operating leverage & fixed overhead cost containment" if is_increase else "Overhead cost escalation / administrative inflation",
            "Reduction in finance costs / debt retirement" if is_increase else "Higher interest rates on working capital facilities",
            "Lower depreciation or one-off exceptional gains" if is_increase else "Increased selling, marketing & logistics spend"
        ]
    elif "debtor" in k or "receivable" in k:
        raw = [
            "Relaxation of credit terms to major institutional clients" if is_increase else "Aggressive cash collections & tight credit policy",
            "High concentration of Q4 billing nearing year-end" if is_increase else "Factoring / bill discounting arrangements",
            "Delayed customer milestone sign-offs" if is_increase else "Write-off of long-overdue doubtful debts"
        ]
    elif "inventory" in k or "stock" in k:
        raw = [
            "Strategic bulk purchasing ahead of anticipated price rises" if is_increase else "Lean JIT inventory management implementation",
            "Slow-moving finished goods inventory build-up" if is_increase else "High order fulfillment during peak season",
            "Supply chain lead-time buffering" if is_increase else "Scrap / obsolete inventory write-downs"
        ]
    elif "creditor" in k or "payable" in k:
        raw = [
            "Negotiated extended payment terms with key suppliers" if is_increase else "Accelerated supplier payments to avail cash discounts",
            "Higher procurement volumes in year-end quarter" if is_increase else "Vendor advance settlement requirements",
            "Cash flow management pacing" if is_increase else "Stricter MSMEDA 45-day payment compliance (Sec 43B(h))"
        ]
    elif "debt" in k or "borrowing" in k:
        raw = [
            "Availment of new term loan for CAPEX expansion" if is_increase else "Scheduled term loan principal repayments",
            "Higher utilization of working capital cash credit limits" if is_increase else "De-leveraging funded by internal accruals",
            "Promoter unsecured loan infusion" if is_increase else "Refinancing with lower interest facilities"
        ]
    elif "current_ratio" in k or "quick_ratio" in k:
        raw = [
            "Enhanced liquidity buffer & retained cash reserves" if is_increase else "Working capital tightening / higher current maturities",
            "Inventory build-up or receivable growth" if is_increase else "Utilization of cash for fixed asset acquisitions",
            "Long-term funding of current assets" if is_increase else "Short-term borrowing for capital commitments"
        ]
    else:
        raw = [
            "Business scale change / operational expansion" if is_increase else "Operational curtailment / asset disposal",
            "Accounting reclassification or presentation change",
            "Market economic condition shift"
        ]

    return [f"[Hypothesis - requires auditor corroboration] {item}" for item in raw]

def run_financial_statement_analysis(engagement_id: int) -> Dict[str, Any]:
    """
    Executes full Schedule III Balance Sheet, P&L, Cash Flow, and deterministic ratio analysis.
    Performs Current Year (CY) vs Previous Year (PY) comparative analytics with significant movement detection.
    Enforces strict zero-fabrication: tax expense and balance sheet line items are derived strictly from source vouchers.
    """
    conn = get_db_connection()
    eng_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    if not eng_row:
        conn.close()
        raise ValueError(f"Engagement {engagement_id} not found")

    client_id = eng_row["client_id"]
    cy_year = eng_row["financial_year"] or "2024-25"

    # 1. Fetch Current Year (CY) Transactions
    cy_rows = conn.execute("""
        SELECT ledger, account_group, SUM(debit) as total_debit, SUM(credit) as total_credit
        FROM transactions
        WHERE engagement_id = ?
        GROUP BY ledger, account_group
    """, (engagement_id,)).fetchall()

    # 2. Check for exact Previous Year (PY) Engagement (e.g. 2025-26 -> 2024-25)
    from backend.app.utils.financial_year import derive_prior_financial_year
    target_py_fy = derive_prior_financial_year(cy_year)
    py_eng_row = None
    if target_py_fy:
        py_eng_row = conn.execute("""
            SELECT id, financial_year FROM engagements
            WHERE client_id = ? AND id != ? AND financial_year = ?
            ORDER BY id DESC LIMIT 1
        """, (client_id, engagement_id, target_py_fy)).fetchone()

    py_year = py_eng_row["financial_year"] if py_eng_row else (target_py_fy or "Prior FY")
    py_rows = []
    if py_eng_row:
        py_rows = conn.execute("""
            SELECT ledger, account_group, SUM(debit) as total_debit, SUM(credit) as total_credit
            FROM transactions
            WHERE engagement_id = ?
            GROUP BY ledger, account_group
        """, (py_eng_row["id"],)).fetchall()

    # 3. Aggregate Ledger Figures strictly according to Canonical Chart of Accounts rules
    def aggregate_statements(rows):
        rev = 0.0
        cogs = 0.0
        employee_exp = 0.0
        finance_costs = 0.0
        depreciation = 0.0
        other_exp = 0.0
        tax_expense = 0.0
        tax_entries_found = False

        cash_bank = 0.0
        debtors = 0.0
        inventory = 0.0
        other_ca = 0.0
        fixed_assets = 0.0
        investments = 0.0
        other_nca = 0.0

        creditors = 0.0
        st_borrowings = 0.0
        other_cl = 0.0
        lt_borrowings = 0.0
        other_ncl = 0.0
        share_capital = 0.0
        reserves = 0.0

        # Detailed item lists
        revenue_items = []
        expense_items = []
        asset_items = []
        liability_items = []
        equity_items = []

        for r in rows:
            ledger = r["ledger"] or ""
            l_lower = ledger.lower()
            group = (r["account_group"] or "").lower()
            dr = float(r["total_debit"] or 0.0)
            cr = float(r["total_credit"] or 0.0)

            # --- 1. Capital Purchases & Fixed Assets Overrides ---
            is_capital_purchase = ("purchase" in l_lower and any(k in l_lower for k in ["capital", "machinery", "equipment", "asset", "fixed", "furniture", "computer", "vehicle"]))
            if is_capital_purchase or "fixed asset" in group or "fixed asset" in l_lower or "property" in l_lower or "plant" in l_lower or "machinery" in l_lower or "ppe" in l_lower:
                amt = dr - cr
                if amt != 0:
                    asset_items.append({"ledger": ledger, "amount": amt})
                    fixed_assets += amt
                continue

            # --- 2. Contra Revenue (Sales Returns / Return Inward) ---
            if "return inward" in l_lower or "sales return" in l_lower or "sale return" in l_lower:
                amt = dr - cr  # Debits in sales return reduce net revenue
                if amt != 0:
                    revenue_items.append({"ledger": ledger, "amount": -amt})
                    rev -= amt
                continue

            # --- 3. Contra Expense (Purchase Returns / Return Outward) ---
            if "return outward" in l_lower or "purchase return" in l_lower:
                amt = cr - dr  # Credits in purchase return reduce COGS/expenses
                if amt != 0:
                    expense_items.append({"ledger": ledger, "amount": -amt})
                    cogs -= amt
                continue

            # --- 4. Tax Expense & Provisions vs Tax Assets / Liabilities ---
            is_tax_kw = any(k in l_lower for k in ["income tax", "tax expense", "provision for tax", "provision for income tax", "current tax", "deferred tax", "tax provision"])
            if is_tax_kw:
                is_tax_liability = "payable" in l_lower or "liabilit" in group or "provision" in group or ("provision for" in l_lower and "expense" not in group and "expense" not in l_lower)
                is_tax_asset = "advance" in l_lower or "tds" in l_lower or "tcs" in l_lower or "asset" in group or "receivable" in l_lower

                if is_tax_liability:
                    amt = cr - dr
                    if amt != 0:
                        liability_items.append({"ledger": ledger, "amount": amt})
                        other_cl += amt
                    continue
                elif is_tax_asset:
                    amt = dr - cr
                    if amt != 0:
                        asset_items.append({"ledger": ledger, "amount": amt})
                        other_ca += amt
                    continue
                else:
                    # True P&L Tax Expense Ledger
                    amt = dr - cr
                    if amt != 0:
                        expense_items.append({"ledger": ledger, "amount": amt})
                        tax_expense += amt
                        tax_entries_found = True
                    continue

            # --- 5. Revenue / Income ---
            if "revenue" in group or "income" in group or "sales" in group or (("sale" in l_lower or "revenue" in l_lower) and "asset" not in group and "receivable" not in l_lower and "creditor" not in l_lower):
                amt = cr - dr
                if amt != 0:
                    revenue_items.append({"ledger": ledger, "amount": amt})
                    rev += amt

            # --- 6. Expenses / Cost of Goods Sold ---
            elif "expense" in group or "cost" in group or ("purchase" in l_lower and "asset" not in group) or "salary" in l_lower or "wages" in l_lower or bool(re.search(r'\brent\b', l_lower)) or "freight" in l_lower or "depreciation" in l_lower or ("interest" in l_lower and "received" not in l_lower and "loan" not in l_lower):
                amt = dr - cr
                if amt != 0:
                    expense_items.append({"ledger": ledger, "amount": amt})
                    if "purchase" in l_lower or "raw material" in l_lower or "direct" in l_lower or "freight inward" in l_lower or "cogs" in l_lower:
                        cogs += amt
                    elif "salary" in l_lower or "wage" in l_lower or "employee" in l_lower or "bonus" in l_lower:
                        employee_exp += amt
                    elif "interest" in l_lower or "finance" in l_lower or "bank charge" in l_lower:
                        finance_costs += amt
                    elif "depreciation" in l_lower or "amortization" in l_lower:
                        depreciation += amt
                    else:
                        other_exp += amt

            # --- 7. Equity & Capital ---
            elif "equity" in group or "capital" in group or "reserve" in group or "surplus" in group or (("share capital" in l_lower or "proprietor capital" in l_lower or "partners capital" in l_lower) and "asset" not in group):
                amt = cr - dr
                if amt != 0:
                    equity_items.append({"ledger": ledger, "amount": amt})
                    if "share capital" in l_lower or "partner" in l_lower or "proprietor" in l_lower or "capital" in l_lower:
                        share_capital += amt
                    else:
                        reserves += amt

            # --- 8. Liabilities (Current & Non-Current) ---
            elif "liability" in group or "payable" in group or "borrowing" in group or "creditor" in l_lower or "payable" in l_lower or "term loan" in l_lower or "cash credit" in l_lower or "overdraft" in l_lower or "od/cc" in l_lower or "borrowing" in l_lower:
                amt = cr - dr
                if amt != 0:
                    liability_items.append({"ledger": ledger, "amount": amt})
                    if "creditor" in l_lower or "payable" in l_lower or "vendor" in l_lower or "supplier" in l_lower:
                        creditors += amt
                    elif "od" in l_lower or "overdraft" in l_lower or "cash credit" in l_lower or "short term" in l_lower:
                        st_borrowings += amt
                    elif "loan" in l_lower or "borrowing" in l_lower or "debenture" in l_lower or "non-current" in group:
                        lt_borrowings += amt
                    elif "tax payable" in l_lower or "gst payable" in l_lower or "tds" in l_lower or "provision" in l_lower:
                        other_cl += amt
                    else:
                        other_ncl += amt

            # --- 9. Assets (Current & Non-Current) ---
            else:
                amt = dr - cr
                if amt != 0:
                    asset_items.append({"ledger": ledger, "amount": amt})
                    if "cash" in l_lower or "bank" in l_lower:
                        cash_bank += amt
                    elif "debtor" in l_lower or "receivable" in l_lower or "customer" in l_lower:
                        debtors += amt
                    elif "stock" in l_lower or "inventory" in l_lower:
                        inventory += amt
                    elif "investment" in l_lower or "shares" in l_lower or "mutual" in l_lower:
                        investments += amt
                    elif "advance" in l_lower or "deposit" in l_lower or "prepaid" in l_lower:
                        other_ca += amt
                    else:
                        other_nca += amt

        # P&L Totals (Derived strictly from real ledger balances - no assumed percentages)
        total_income = rev
        gross_profit = rev - cogs
        total_operating_expenses = employee_exp + other_exp
        ebitda = gross_profit - total_operating_expenses
        ebit = ebitda - depreciation
        pbt = ebit - finance_costs
        
        # Real ledger-derived tax expense (Never assume 25% or any hardcoded rate)
        actual_tax = tax_expense if tax_entries_found else 0.0
        pat = pbt - actual_tax

        # Balance Sheet Totals
        current_assets = cash_bank + debtors + inventory + other_ca
        non_current_assets = fixed_assets + investments + other_nca
        total_assets = current_assets + non_current_assets

        current_liabilities = creditors + st_borrowings + other_cl
        non_current_liabilities = lt_borrowings + other_ncl
        total_liabilities = current_liabilities + non_current_liabilities
        
        # Equity accounting: Share capital + opening reserves + current year PAT
        total_equity = share_capital + reserves + pat
        total_equity_and_liabilities = total_equity + total_liabilities

        # Fundamental Accounting Equation Check
        diff = round(abs(total_assets - total_equity_and_liabilities), 2)
        is_balanced = diff < 0.01
        bs_status = "BALANCED" if is_balanced else "IMBALANCED"

        return {
            "pnl": {
                "revenue": round(rev, 2),
                "cogs": round(cogs, 2),
                "gross_profit": round(gross_profit, 2),
                "employee_expenses": round(employee_exp, 2),
                "finance_costs": round(finance_costs, 2),
                "depreciation": round(depreciation, 2),
                "other_operating_expenses": round(other_exp, 2),
                "total_operating_expenses": round(total_operating_expenses, 2),
                "ebitda": round(ebitda, 2),
                "ebit": round(ebit, 2),
                "pbt": round(pbt, 2),
                "tax_expense": round(actual_tax, 2),
                "tax_data_status": "ACTUAL_LEDGER" if tax_entries_found else "NOT_RECORDED_OR_ZERO",
                "pat": round(pat, 2),
                "revenue_items": revenue_items,
                "expense_items": expense_items
            },
            "balance_sheet": {
                "cash_bank": round(cash_bank, 2),
                "trade_debtors": round(debtors, 2),
                "inventory": round(inventory, 2),
                "other_current_assets": round(other_ca, 2),
                "current_assets": round(current_assets, 2),
                "total_current_assets": round(current_assets, 2),
                "fixed_assets_ppe": round(fixed_assets, 2),
                "investments": round(investments, 2),
                "other_non_current_assets": round(other_nca, 2),
                "non_current_assets": round(non_current_assets, 2),
                "total_non_current_assets": round(non_current_assets, 2),
                "total_assets": round(total_assets, 2),
                "trade_creditors": round(creditors, 2),
                "short_term_borrowings": round(st_borrowings, 2),
                "other_current_liabilities": round(other_cl, 2),
                "current_liabilities": round(current_liabilities, 2),
                "total_current_liabilities": round(current_liabilities, 2),
                "long_term_borrowings": round(lt_borrowings, 2),
                "other_non_current_liabilities": round(other_ncl, 2),
                "non_current_liabilities": round(non_current_liabilities, 2),
                "total_non_current_liabilities": round(non_current_liabilities, 2),
                "total_liabilities": round(total_liabilities, 2),
                "share_capital": round(share_capital, 2),
                "reserves_surplus": round(reserves, 2),
                "reserves_surplus_opening": round(reserves, 2),
                "current_year_pat": round(pat, 2),
                "pat_retained": round(pat, 2),
                "total_equity": round(total_equity, 2),
                "total_equity_and_liabilities": round(total_equity_and_liabilities, 2),
                "total_liabilities_and_equity": round(total_equity_and_liabilities, 2),
                "balance_sheet_status": bs_status,
                "balance_difference": diff,
                "difference": diff,
                "integrity_warning": None if is_balanced else f"Balance Sheet is IMBALANCED by ₹{diff:,.2f}. Assets: ₹{total_assets:,.2f}, Equity & Liabilities: ₹{total_equity_and_liabilities:,.2f}."
            }
        }

    # 4. Compute Deterministic Ratios (Return None / null for undefined zero-denominator ratios)
    def compute_ratios(pnl, bs):
        rev = pnl["revenue"]
        cogs = pnl["cogs"]
        gp = pnl["gross_profit"]
        ebit = pnl["ebit"]
        pat = pnl["pat"]

        ca = bs["current_assets"]
        cl = bs["current_liabilities"]
        inv = bs["inventory"]
        debtors = bs["trade_debtors"]
        creditors = bs["trade_creditors"]
        total_debt = bs["long_term_borrowings"] + bs["short_term_borrowings"]
        total_equity = bs["total_equity"]
        capital_employed = bs["total_assets"] - cl

        # Liquidity (Undefined / None when liabilities are zero)
        curr_ratio = safe_div(ca, cl, None)
        quick_ratio = safe_div(ca - inv, cl, None)

        # Solvency (Undefined / None when equity is zero or negative)
        debt_equity = safe_div(total_debt, total_equity, None) if total_equity > 0 else None

        # Profitability (Undefined / None when revenue is zero)
        gp_margin = safe_div(gp * 100.0, rev, None)
        np_margin = safe_div(pat * 100.0, rev, None)
        op_margin = safe_div(ebit * 100.0, rev, None)
        roce = safe_div(ebit * 100.0, capital_employed, None) if capital_employed > 0 else None
        roe = safe_div(pat * 100.0, total_equity, None) if total_equity > 0 else None

        # Activity / Turnover (Undefined / None when balances are zero)
        rec_turnover = safe_div(rev, debtors, None)
        dso_days = round(365.0 / rec_turnover, 1) if (rec_turnover is not None and rec_turnover > 0) else None

        inv_turnover = safe_div(cogs, inv, None)
        dsi_days = round(365.0 / inv_turnover, 1) if (inv_turnover is not None and inv_turnover > 0) else None

        pay_turnover = safe_div(cogs, creditors, None)
        dpo_days = round(365.0 / pay_turnover, 1) if (pay_turnover is not None and pay_turnover > 0) else None

        wc_diff = ca - cl
        wc_turnover = safe_div(rev, wc_diff, None) if abs(wc_diff) > 1e-6 else None

        return {
            "current_ratio": round(curr_ratio, 2) if curr_ratio is not None else None,
            "quick_ratio": round(quick_ratio, 2) if quick_ratio is not None else None,
            "debt_equity_ratio": round(debt_equity, 2) if debt_equity is not None else None,
            "gross_profit_margin_pct": round(gp_margin, 2) if gp_margin is not None else None,
            "net_profit_margin_pct": round(np_margin, 2) if np_margin is not None else None,
            "operating_margin_pct": round(op_margin, 2) if op_margin is not None else None,
            "receivable_turnover": round(rec_turnover, 2) if rec_turnover is not None else None,
            "dso_days": dso_days,
            "inventory_turnover": round(inv_turnover, 2) if inv_turnover is not None else None,
            "dsi_days": dsi_days,
            "payable_turnover": round(pay_turnover, 2) if pay_turnover is not None else None,
            "dpo_days": dpo_days,
            "return_on_capital_employed_pct": round(roce, 2) if roce is not None else None,
            "return_on_equity_pct": round(roe, 2) if roe is not None else None,
            "working_capital_turnover": round(wc_turnover, 2) if wc_turnover is not None else None
        }

    # Aggregate CY
    cy_data = aggregate_statements(cy_rows)
    cy_ratios = compute_ratios(cy_data["pnl"], cy_data["balance_sheet"])

    # Aggregate PY strictly from real PY data (no estimations or fake zeroes)
    py_available = bool(py_rows)
    if py_rows:
        py_data = aggregate_statements(py_rows)
        py_pnl = py_data["pnl"]
        py_bs = py_data["balance_sheet"]
        py_ratios = compute_ratios(py_pnl, py_bs)
    else:
        py_data = None
        py_pnl = None
        py_bs = None
        py_ratios = None

    # 5. Compute Cash Flow Statement (Consistent Indirect Method with Fundamental Equation Verification)
    def compute_cash_flow(cy_pnl, cy_bs, py_bs):
        if not py_bs:
            return {
                "status": "INSUFFICIENT_PRIOR_YEAR_DATA",
                "message": "Cash flow comparative statement requires prior-year balance sheet figures.",
                "cash_flow_operating": None,
                "cash_flow_investing": None,
                "cash_flow_financing": None,
                "net_cash_flow": None,
                "opening_cash_balance": None,
                "closing_cash_balance": cy_bs["cash_bank"],
                "cash_flow_reconciles": None,
                "reconciliation_difference": None
            }

        pbt = cy_pnl["pbt"]
        dep = cy_pnl["depreciation"]
        fin_cost = cy_pnl.get("finance_costs", 0.0)
        tax_paid = cy_pnl.get("tax_expense", 0.0)
        
        # Working capital movements
        delta_debtors = round(cy_bs["trade_debtors"] - py_bs["trade_debtors"], 2)
        delta_inv = round(cy_bs["inventory"] - py_bs["inventory"], 2)
        delta_other_ca = round(cy_bs["other_current_assets"] - py_bs["other_current_assets"], 2)
        delta_creditors = round(cy_bs["trade_creditors"] - py_bs["trade_creditors"], 2)
        delta_other_cl = round(cy_bs["other_current_liabilities"] - py_bs["other_current_liabilities"], 2)
        wc_adjustment = round(- delta_debtors - delta_inv - delta_other_ca + delta_creditors + delta_other_cl, 2)

        # Operating Activities:
        # PBT + Depreciation + Finance Costs + Working Capital Changes - Direct Taxes Paid
        op_profit_before_wc = round(pbt + dep + fin_cost, 2)
        cash_gen_ops = round(op_profit_before_wc + wc_adjustment, 2)
        cfo = round(cash_gen_ops - tax_paid, 2)

        # Investing Activities (Capex & Investments)
        delta_ppe = round(cy_bs["fixed_assets_ppe"] - py_bs["fixed_assets_ppe"] + dep, 2)
        delta_invst = round(cy_bs["investments"] - py_bs["investments"], 2)
        cfi = round(- (delta_ppe + delta_invst), 2)

        # Financing Activities (Borrowings, Equity, and Finance Costs Paid)
        delta_lt_debt = round(cy_bs["long_term_borrowings"] - py_bs["long_term_borrowings"], 2)
        delta_st_debt = round(cy_bs["short_term_borrowings"] - py_bs["short_term_borrowings"], 2)
        delta_equity = round(cy_bs["share_capital"] - py_bs["share_capital"], 2)
        cff = round(delta_lt_debt + delta_st_debt + delta_equity - fin_cost, 2)

        net_change = round(cfo + cfi + cff, 2)
        opening_cash = py_bs["cash_bank"]
        closing_cash = cy_bs["cash_bank"]

        # Fundamental Cash Flow Verification: Opening Cash + Net Change == Closing Cash
        recon_diff = round(opening_cash + net_change - closing_cash, 2)
        cash_flow_reconciles = abs(recon_diff) < 0.05

        return {
            "status": "COMPUTED",
            "cash_flow_reconciles": cash_flow_reconciles,
            "reconciliation_difference": recon_diff,
            "cash_flow_operating": cfo,
            "cash_flow_investing": cfi,
            "cash_flow_financing": cff,
            "net_cash_flow": {
                "net_increase_in_cash_and_equivalents": net_change,
                "cash_at_beginning_of_period": opening_cash,
                "cash_at_end_of_period": closing_cash,
                "cash_flow_reconciles": cash_flow_reconciles,
                "reconciliation_difference": recon_diff
            },
            "opening_cash_balance": opening_cash,
            "closing_cash_balance": closing_cash,
            "operating_activities": {
                "net_cash_from_operating_activities": cfo,
                "net_profit_before_tax": pbt,
                "adjustments_for_depreciation": dep,
                "adjustments_for_finance_costs": fin_cost,
                "operating_profit_before_working_capital_changes": op_profit_before_wc,
                "change_in_trade_receivables": -delta_debtors,
                "change_in_inventories": -delta_inv,
                "change_in_other_current_assets": -delta_other_ca,
                "change_in_trade_payables": delta_creditors,
                "change_in_other_current_liabilities": delta_other_cl,
                "working_capital_adjustments": wc_adjustment,
                "cash_generated_from_operations": cash_gen_ops,
                "direct_taxes_paid": tax_paid
            },
            "investing_activities": {
                "net_cash_from_investing_activities": cfi,
                "purchase_of_fixed_assets": -delta_ppe,
                "purchase_of_investments": -delta_invst
            },
            "financing_activities": {
                "net_cash_from_financing_activities": cff,
                "proceeds_from_borrowings": round(delta_lt_debt + delta_st_debt, 2),
                "proceeds_from_equity": delta_equity,
                "finance_costs_paid": -fin_cost
            },
            "details": {
                "net_profit_pbt": pbt,
                "net_profit_pat": cy_pnl["pat"],
                "depreciation_added_back": dep,
                "finance_costs_added_back": fin_cost,
                "working_capital_adjustments": wc_adjustment,
                "capex_outflow": round(- delta_ppe, 2),
                "net_borrowing_change": round(delta_lt_debt + delta_st_debt, 2),
                "cash_flow_reconciles": cash_flow_reconciles,
                "difference": recon_diff
            }
        }

    cash_flow_stmt = compute_cash_flow(cy_data["pnl"], cy_data["balance_sheet"], py_bs)

    # 6. Fetch Existing Auditor Explanations
    saved_expls = {}
    rows_expl = conn.execute("SELECT * FROM financial_statement_explanations WHERE engagement_id = ?", (engagement_id,)).fetchall()
    for e in rows_expl:
        saved_expls[e["item_key"]] = {
            "explanation": e["auditor_explanation"],
            "category": e["explanation_category"],
            "review_status": e["review_status"],
            "updated_by": e["updated_by"],
            "updated_at": e["updated_at"]
        }
    conn.close()

    # 7. Build Significant Movement Comparison Matrix
    metrics_to_compare = [
        # Ratios
        ("current_ratio", "Current Ratio", "Liquidity", cy_ratios["current_ratio"], py_ratios["current_ratio"] if py_ratios else None, "Ratio"),
        ("quick_ratio", "Quick Ratio (Acid Test)", "Liquidity", cy_ratios["quick_ratio"], py_ratios["quick_ratio"] if py_ratios else None, "Ratio"),
        ("debt_equity_ratio", "Debt-to-Equity Ratio", "Solvency / Leverage", cy_ratios["debt_equity_ratio"], py_ratios["debt_equity_ratio"] if py_ratios else None, "Ratio"),
        ("gross_profit_margin_pct", "Gross Profit Margin (%)", "Profitability", cy_ratios["gross_profit_margin_pct"], py_ratios["gross_profit_margin_pct"] if py_ratios else None, "%"),
        ("net_profit_margin_pct", "Net Profit Margin (%)", "Profitability", cy_ratios["net_profit_margin_pct"], py_ratios["net_profit_margin_pct"] if py_ratios else None, "%"),
        ("operating_margin_pct", "Operating Profit Margin (%)", "Profitability", cy_ratios["operating_margin_pct"], py_ratios["operating_margin_pct"] if py_ratios else None, "%"),
        ("receivable_turnover", "Debtors / Receivable Turnover", "Operating Efficiency", cy_ratios["receivable_turnover"], py_ratios["receivable_turnover"] if py_ratios else None, "Times"),
        ("inventory_turnover", "Inventory Turnover", "Operating Efficiency", cy_ratios["inventory_turnover"], py_ratios["inventory_turnover"] if py_ratios else None, "Times"),
        ("payable_turnover", "Creditors / Payable Turnover", "Operating Efficiency", cy_ratios["payable_turnover"], py_ratios["payable_turnover"] if py_ratios else None, "Times"),
        # P&L Line Items
        ("revenue", "Revenue from Operations", "P&L Summary", cy_data["pnl"]["revenue"], py_pnl["revenue"] if py_pnl else None, "INR"),
        ("cogs", "Cost of Goods Sold / Materials", "P&L Summary", cy_data["pnl"]["cogs"], py_pnl["cogs"] if py_pnl else None, "INR"),
        ("employee_expenses", "Employee Benefit Expenses", "P&L Summary", cy_data["pnl"]["employee_expenses"], py_pnl["employee_expenses"] if py_pnl else None, "INR"),
        ("finance_costs", "Finance Costs / Interest", "P&L Summary", cy_data["pnl"]["finance_costs"], py_pnl["finance_costs"] if py_pnl else None, "INR"),
        ("ebitda", "Operating EBITDA", "P&L Summary", cy_data["pnl"]["ebitda"], py_pnl["ebitda"] if py_pnl else None, "INR"),
        ("pat", "Net Profit After Tax (PAT)", "P&L Summary", cy_data["pnl"]["pat"], py_pnl["pat"] if py_pnl else None, "INR"),
        # Balance Sheet Line Items
        ("trade_debtors", "Trade Receivables (Debtors)", "Balance Sheet", cy_data["balance_sheet"]["trade_debtors"], py_bs["trade_debtors"] if py_bs else None, "INR"),
        ("inventory", "Inventories (Stock)", "Balance Sheet", cy_data["balance_sheet"]["inventory"], py_bs["inventory"] if py_bs else None, "INR"),
        ("cash_bank", "Cash & Bank Balances", "Balance Sheet", cy_data["balance_sheet"]["cash_bank"], py_bs["cash_bank"] if py_bs else None, "INR"),
        ("fixed_assets_ppe", "Property Plant & Equipment (PPE)", "Balance Sheet", cy_data["balance_sheet"]["fixed_assets_ppe"], py_bs["fixed_assets_ppe"] if py_bs else None, "INR"),
        ("trade_creditors", "Trade Payables (Creditors)", "Balance Sheet", cy_data["balance_sheet"]["trade_creditors"], py_bs["trade_creditors"] if py_bs else None, "INR"),
        ("long_term_borrowings", "Long-Term Borrowings (Debt)", "Balance Sheet", cy_data["balance_sheet"]["long_term_borrowings"], py_bs["long_term_borrowings"] if py_bs else None, "INR"),
        ("total_equity", "Shareholder Equity & Reserves", "Balance Sheet", cy_data["balance_sheet"]["total_equity"], py_bs["total_equity"] if py_bs else None, "INR")
    ]

    comparisons: List[Dict[str, Any]] = []
    significant_movements_count = 0

    for key, name, cat, cy_val, py_val, unit in metrics_to_compare:
        if py_val is not None and cy_val is not None:
            chg = calculate_change(cy_val, py_val)
            is_sig = chg["is_significant"]
            if is_sig:
                significant_movements_count += 1
                pct_d = chg["percentage_difference"]
                finding_status = "Significant movement" if (pct_d is None or abs(pct_d) >= 35.0) else "Unusual change"
            else:
                finding_status = "Stable trend"
            expl_categories = get_possible_explanations(key, cy_val, py_val, chg["percentage_difference"])
            abs_diff = chg["absolute_difference"]
            pct_diff = chg["percentage_difference"]
            change_type = chg["change_type"]
            prev_val = chg["previous_value"]
        else:
            is_sig = False
            finding_status = "No prior year data" if py_val is None else "Undefined metric"
            expl_categories = []
            abs_diff = None
            pct_diff = None
            change_type = "NO_PRIOR_YEAR_DATA" if py_val is None else "UNDEFINED"
            prev_val = None

        saved = saved_expls.get(key, {})

        comparisons.append({
            "item_key": key,
            "metric_name": name,
            "category": cat,
            "unit": unit,
            "current_year_value": cy_val,
            "previous_year_value": prev_val,
            "absolute_difference": abs_diff,
            "percentage_difference": pct_diff,
            "change_type": change_type,
            "is_significant": is_sig,
            "audit_verdict": finding_status if is_sig else ("No prior baseline" if py_val is None else "Normal variance"),
            "possible_explanation_categories": expl_categories,
            "auditor_explanation": saved.get("explanation", ""),
            "selected_category": saved.get("category", expl_categories[0] if expl_categories else "Normal Business Operations"),
            "review_status": saved.get("review_status", "Requires auditor review" if is_sig else ("No baseline" if py_val is None else "Reviewed"))
        })

    # 8. Management / Audit Analysis Summary Synthesis
    cr_str = f"{cy_ratios['current_ratio']}x" if cy_ratios['current_ratio'] is not None else "N/A"
    qr_str = f"{cy_ratios['quick_ratio']}x" if cy_ratios['quick_ratio'] is not None else "N/A"
    de_str = f"{cy_ratios['debt_equity_ratio']}x" if cy_ratios['debt_equity_ratio'] is not None else "N/A"
    npm_str = f"{cy_ratios['net_profit_margin_pct']}%" if cy_ratios['net_profit_margin_pct'] is not None else "N/A"
    dso_str = f"{cy_ratios['dso_days']} days" if cy_ratios['dso_days'] is not None else "N/A"
    dsi_str = f"{cy_ratios['dsi_days']} days" if cy_ratios['dsi_days'] is not None else "N/A"
    dpo_str = f"{cy_ratios['dpo_days']} days" if cy_ratios['dpo_days'] is not None else "N/A"

    if py_available and py_data:
        rev_cy = cy_data['pnl']['revenue']
        rev_py = py_data['pnl']['revenue']
        pct_rev = ((rev_cy - rev_py) / max(rev_py, 1.0) * 100.0) if rev_py > 0 else 0.0
        summary_text = (
            f"Financial Statement Analysis for FY {cy_year} (vs FY {py_year}) reveals a revenue trajectory of "
            f"₹{rev_cy:,.2f} ({'+' if rev_cy >= rev_py else ''}{pct_rev:.1f}%) with PAT of "
            f"₹{cy_data['pnl']['pat']:,.2f} (Net Margin: {npm_str}). "
            f"Liquidity reflects a Current Ratio of {cr_str} and Quick Ratio of {qr_str}. "
            f"Solvency profile reflects Debt-to-Equity of {de_str}. "
            f"Working capital cycle indicates DSO of {dso_str}, DSI of {dsi_str}, and DPO of {dpo_str}. "
            f"{significant_movements_count} significant movements detected requiring auditor review."
        )
    else:
        summary_text = (
            f"Financial Statement Analysis for FY {cy_year} (Standalone CY). Revenue is ₹{cy_data['pnl']['revenue']:,.2f} "
            f"with PAT of ₹{cy_data['pnl']['pat']:,.2f} (Net Margin: {npm_str}). "
            f"Liquidity reflects Current Ratio of {cr_str} and Quick Ratio of {qr_str}. "
            f"Prior year source dataset is NOT AVAILABLE; comparative cash flow and YoY baseline movements are omitted."
        )

    return {
        "engagement_id": engagement_id,
        "financial_year_current": cy_year,
        "financial_year_previous": py_year if py_available else None,
        "previous_year_data_status": "ACTUAL" if py_available else "NOT_AVAILABLE",
        "profit_and_loss": {
            "current_year": cy_data["pnl"],
            "previous_year": py_data["pnl"] if py_data else None
        },
        "balance_sheet": {
            "current_year": cy_data["balance_sheet"],
            "previous_year": py_data["balance_sheet"] if py_data else None
        },
        "cash_flow_statement": cash_flow_stmt,
        "ratios": {
            "current_year": cy_ratios,
            "previous_year": py_ratios
        },
        "comparisons": comparisons,
        "summary": {
            "significant_movements_count": significant_movements_count,
            "total_metrics_analyzed": len(comparisons),
            "management_commentary": summary_text
        },
        "provenance": {
            "source_type": "GENERAL_LEDGER_TRANSACTIONS",
            "calculation_method": "SCHEDULE_III_BALANCE_SHEET_PNL_CASHFLOW_AGGREGATION",
            "calculation_timestamp": datetime.now().isoformat(),
            "calculation_version": "2.0",
            "data_status": "ACTUAL" if bool(cy_rows) else "MISSING",
            "previous_year_data_status": "ACTUAL" if py_available else "NOT_AVAILABLE"
        }
    }
