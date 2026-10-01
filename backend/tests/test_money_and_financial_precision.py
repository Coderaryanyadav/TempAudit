from decimal import Decimal
import pytest
from backend.app.utils.money import (
    to_decimal,
    quantize_money,
    to_paise,
    from_paise,
    safe_sum_decimals,
    calculate_gst_split,
    calculate_reconciliation_difference
)

def test_paise_and_decimal_conversions():
    """Verify precision across ₹0.01, ₹0.10, ₹999.99, and large figures."""
    assert to_paise("0.01") == 1
    assert to_paise(0.01) == 1
    assert to_paise(Decimal("0.01")) == 1

    assert from_paise(1) == Decimal("0.01")
    assert from_paise(10) == Decimal("0.10")
    assert from_paise(99999) == Decimal("999.99")
    assert from_paise(12345678901) == Decimal("123456789.01")

def test_no_floating_point_drift_in_sum():
    """Verify 0.1 + 0.2 equals 0.30 exactly with no binary float representation drift."""
    values = ["0.1", "0.2"]
    total = safe_sum_decimals(values)
    assert total == Decimal("0.30")
    assert str(total) == "0.30"

    # Sum 100 times 0.01
    hundred_cents = [Decimal("0.01") for _ in range(100)]
    assert safe_sum_decimals(hundred_cents) == Decimal("1.00")

def test_gst_precision_split():
    """Verify CGST, SGST, IGST calculations are deterministic."""
    # Intra-state 18% on ₹1,000.00
    split = calculate_gst_split("1000.00", "18.0", is_interstate=False)
    assert split["taxable"] == Decimal("1000.00")
    assert split["cgst"] == Decimal("90.00")
    assert split["sgst"] == Decimal("90.00")
    assert split["igst"] == Decimal("0.00")
    assert split["total_tax"] == Decimal("180.00")
    assert split["total_invoice"] == Decimal("1180.00")

    # Inter-state 18% on ₹999.99
    split_inter = calculate_gst_split("999.99", "18.0", is_interstate=True)
    assert split_inter["taxable"] == Decimal("999.99")
    assert split_inter["igst"] == Decimal("180.00")  # 999.99 * 0.18 = 179.9982 -> rounded 180.00
    assert split_inter["total_invoice"] == Decimal("1179.99")

def test_reconciliation_exact_difference():
    """Verify bank vs book variance calculation with exact Decimal precision."""
    diff = calculate_reconciliation_difference("12500.50", "12500.49")
    assert diff == Decimal("0.01")

    diff_neg = calculate_reconciliation_difference("1000.00", "1050.75")
    assert diff_neg == Decimal("-50.75")
