"""
Test Trial Balance Builder
FinAuditPro - Test Data Architecture
"""

from typing import Dict, Any, List

STANDARD_TRIAL_BALANCE_HEADS = [
    {"ledger": "Cash in Hand", "group": "Asset", "normal_balance": "DEBIT"},
    {"ledger": "Bank Current Account", "group": "Asset", "normal_balance": "DEBIT"},
    {"ledger": "Trade Debtors", "group": "Asset", "normal_balance": "DEBIT"},
    {"ledger": "Trade Creditors", "group": "Liability", "normal_balance": "CREDIT"},
    {"ledger": "Stock in Trade", "group": "Asset", "normal_balance": "DEBIT"},
    {"ledger": "Property, Plant & Equipment", "group": "Asset", "normal_balance": "DEBIT"},
    {"ledger": "Accumulated Depreciation", "group": "Asset", "normal_balance": "CREDIT"},
    {"ledger": "Long-Term Borrowings", "group": "Liability", "normal_balance": "CREDIT"},
    {"ledger": "Share Capital", "group": "Equity", "normal_balance": "CREDIT"},
    {"ledger": "Sales Revenue", "group": "Revenue", "normal_balance": "CREDIT"},
    {"ledger": "Cloud & Infrastructure Cost", "group": "Expense", "normal_balance": "DEBIT"},
    {"ledger": "Salaries & Wages", "group": "Expense", "normal_balance": "DEBIT"},
    {"ledger": "Office Rent", "group": "Expense", "normal_balance": "DEBIT"},
    {"ledger": "Electricity & Power", "group": "Expense", "normal_balance": "DEBIT"},
    {"ledger": "Professional & Legal Fees", "group": "Expense", "normal_balance": "DEBIT"},
    {"ledger": "GST Input Tax Credit", "group": "Asset", "normal_balance": "DEBIT"},
    {"ledger": "GST Output Liability", "group": "Liability", "normal_balance": "CREDIT"},
    {"ledger": "Bank Interest & Finance Charges", "group": "Expense", "normal_balance": "DEBIT"},
    {"ledger": "Depreciation Expense", "group": "Expense", "normal_balance": "DEBIT"},
    {"ledger": "Interest Income", "group": "Revenue", "normal_balance": "CREDIT"},
    {"ledger": "Office & Administrative Expenses", "group": "Expense", "normal_balance": "DEBIT"}
]

def get_standard_tb_heads() -> List[Dict[str, Any]]:
    return STANDARD_TRIAL_BALANCE_HEADS
