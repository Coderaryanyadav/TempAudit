"""
Financial Year Utilities & Normalization
FinAuditPro - Core Financial Invariants

Provides centralized parsing, validation, and historical period derivation
for standard Indian accounting financial years (e.g. 2024-25, 2025-26).
"""

import re
from typing import Optional, Tuple

FY_REGEX = r"^(?:FY\s*)?(\d{4})[-/](\d{2,4})$"

def validate_financial_year(fy_str: str) -> bool:
    """Validates if a string conforms to a valid Indian Financial Year format (e.g. '2025-26' or '2024-2025')."""
    if not fy_str or not isinstance(fy_str, str):
        return False
    match = re.match(FY_REGEX, fy_str.strip())
    if not match:
        return False
    start_year = int(match.group(1))
    end_str = match.group(2)
    if len(end_str) == 2:
        expected_end = (start_year + 1) % 100
        return int(end_str) == expected_end
    elif len(end_str) == 4:
        return int(end_str) == (start_year + 1)
    return False

def parse_financial_year(fy_str: str) -> Tuple[int, int, str, str]:
    """
    Parses financial year string into:
    (start_year, end_year, period_start_date, period_end_date)
    e.g. '2025-26' -> (2025, 2026, '2025-04-01', '2026-03-31')
    """
    match = re.search(r'(\d{4})[-/](\d{2,4})', str(fy_str).strip())
    if not match:
        return (2024, 2025, "2024-04-01", "2025-03-31")
    start_year = int(match.group(1))
    end_year = start_year + 1
    return (start_year, end_year, f"{start_year}-04-01", f"{end_year}-03-31")

def derive_prior_financial_year(fy_str: str) -> Optional[str]:
    """
    Derives exact preceding Indian Financial Year string.
    e.g. '2025-26' -> '2024-25', '2024-2025' -> '2023-2024'.
    """
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
