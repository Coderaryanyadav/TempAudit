"""
Test Scenarios Configuration
FinAuditPro - Test Data Architecture

Defines controlled anomaly flags and expected outcomes for:
1. CLEAN scenario (Zero violations, 100% tallies, balanced TB)
2. STRESS scenario (Controlled violations, anomalies, mismatches)
"""

from typing import Dict, Any

CLEAN_SCENARIO: Dict[str, bool] = {
    "duplicate_invoice": False,
    "missing_invoice": False,
    "round_number_transaction": False,
    "weekend_transaction": False,
    "high_value_transaction": False,
    "backdated_transaction": False,
    "duplicate_payment": False,
    "unusual_amount": False,
    "gst_mismatch": False,
    "gstin_mismatch": False,
    "bank_difference": False,
    "unpresented_cheque": False,
    "outstanding_deposit": False,
    "journal_entry_anomaly": False,
    "missing_voucher": False,
    "tb_unbalanced": False
}

STRESS_SCENARIO: Dict[str, bool] = {
    "duplicate_invoice": True,
    "missing_invoice": True,
    "round_number_transaction": True,
    "weekend_transaction": True,
    "high_value_transaction": True,
    "backdated_transaction": True,
    "duplicate_payment": True,
    "unusual_amount": True,
    "gst_mismatch": True,
    "gstin_mismatch": True,
    "bank_difference": True,
    "unpresented_cheque": True,
    "outstanding_deposit": True,
    "journal_entry_anomaly": True,
    "missing_voucher": True,
    "tb_unbalanced": False  # Handled as dedicated test
}

SCENARIOS = {
    "CLEAN": CLEAN_SCENARIO,
    "STRESS": STRESS_SCENARIO
}
