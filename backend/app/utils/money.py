from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Union, Optional, Dict, Any, List

PAISE_EXPONENT = Decimal("0.01")
FOUR_DECIMAL_EXPONENT = Decimal("0.0001")

def to_decimal(val: Any) -> Decimal:
    """
    Safely converts any input (int, float, str, Decimal, None) to canonical Decimal.
    Handles commas, currency symbols, and empty strings safely.
    """
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        # Convert float via str to prevent binary float representation noise
        return Decimal(str(val))
    if isinstance(val, str):
        cleaned = val.replace("₹", "").replace(",", "").replace("$", "").replace(" ", "").strip()
        if not cleaned or cleaned.lower() in ("nan", "none", "null", "-"):
            return Decimal("0.00")
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return Decimal("0.00")
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")

def quantize_money(val: Any, rounding=ROUND_HALF_UP) -> Decimal:
    """
    Quantizes any financial value to exactly 2 decimal places (paise precision)
    using Banker's or Standard Half-Up rounding.
    """
    d = to_decimal(val)
    return d.quantize(PAISE_EXPONENT, rounding=rounding)

def to_paise(val: Any) -> int:
    """
    Converts rupees (e.g. ₹1234.56 or 1234.567) to integer paise (123456 or 123457).
    """
    q = quantize_money(val)
    return int((q * Decimal("100")).to_integral_exact(rounding=ROUND_HALF_UP))

def from_paise(paise: int) -> Decimal:
    """
    Converts integer paise back to canonical Decimal rupees (e.g. 123456 -> Decimal('1234.56')).
    """
    return (Decimal(paise) / Decimal("100")).quantize(PAISE_EXPONENT)

def safe_sum_decimals(items: List[Any]) -> Decimal:
    """
    Deterministically sums a list of monetary items without floating point drift.
    """
    total = Decimal("0.00")
    for item in items:
        total += to_decimal(item)
    return total.quantize(PAISE_EXPONENT)

def calculate_gst_split(taxable_value: Any, rate_pct: Any, is_interstate: bool = False) -> Dict[str, Decimal]:
    """
    Computes CGST, SGST, IGST and total invoice value with deterministic Decimal precision.
    """
    taxable = quantize_money(taxable_value)
    rate = to_decimal(rate_pct)
    
    if is_interstate:
        igst = (taxable * (rate / Decimal("100"))).quantize(PAISE_EXPONENT)
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
    else:
        half_rate = rate / Decimal("2")
        cgst = (taxable * (half_rate / Decimal("100"))).quantize(PAISE_EXPONENT)
        sgst = (taxable * (half_rate / Decimal("100"))).quantize(PAISE_EXPONENT)
        igst = Decimal("0.00")
        
    total_tax = cgst + sgst + igst
    total_invoice = taxable + total_tax
    
    return {
        "taxable": taxable,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total_tax": total_tax,
        "total_invoice": total_invoice
    }

def calculate_reconciliation_difference(bank_amount: Any, book_amount: Any) -> Decimal:
    """
    Calculates exact reconciliation variance between bank and book records.
    """
    b_amt = quantize_money(bank_amount)
    k_amt = quantize_money(book_amount)
    return (b_amt - k_amt).quantize(PAISE_EXPONENT)
