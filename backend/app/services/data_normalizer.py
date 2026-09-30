import re
import json
from datetime import datetime, date
from typing import Dict, Any, List, Tuple, Optional

GSTIN_PATTERN = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"

MONTH_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "september": "09", "sept": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12"
}

def is_valid_calendar_date(y: int, m: int, d: int) -> bool:
    """Verifies that the year, month, and day form a legitimate calendar date."""
    try:
        if y < 1900 or y > 2100:
            return False
        date(y, m, d)
        return True
    except (ValueError, OverflowError):
        return False

def clean_whitespace(val: Any) -> str:
    """Removes non-breaking spaces, zero-width spaces, and collapses multiple spaces into single space."""
    if val is None:
        return ""
    s = str(val)
    # Replace unicode spaces and non-breaking spaces
    s = re.sub(r'[\u00a0\u200b\u200e\u200f\ufeff\t\r\n]+', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def normalize_date(raw_val: Any) -> Tuple[str, str, int, float]:
    """
    Normalizes varied client date representations into standard ISO YYYY-MM-DD.
    Returns (normalized_date_str, rule_applied, is_questionable, confidence).
    """
    if raw_val is None or str(raw_val).strip() == "":
        return "", "EMPTY_DATE", 0, 1.0

    raw = clean_whitespace(raw_val)

    # 1. Already ISO format: YYYY-MM-DD or YYYY/MM/DD or YYYY.MM.DD
    m_iso = re.match(r'^(\d{4})[-/. ](\d{1,2})[-/. ](\d{1,2})(?:[T ].*)?$', raw)
    if m_iso:
        y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        if is_valid_calendar_date(y, m, d):
            norm = f"{y:04d}-{m:02d}-{d:02d}"
            return norm, "ISO_STANDARD", 0, 1.0

    # 2. Text month format: e.g. "01-Apr-2026", "1 April 2026", "Apr 01, 2026", "01/Apr/26"
    m_text = re.match(r'^(\d{1,2})[-/ ]([A-Za-z]+)[-/ ,]+(\d{2,4})$', raw)
    if m_text:
        d = int(m_text.group(1))
        mon_str = m_text.group(2).lower()
        y_str = m_text.group(3)
        y = int(f"20{y_str}" if len(y_str) == 2 and int(y_str) < 50 else (f"19{y_str}" if len(y_str) == 2 else y_str))
        if mon_str in MONTH_MAP:
            m = int(MONTH_MAP[mon_str])
            if is_valid_calendar_date(y, m, d):
                norm = f"{y:04d}-{m:02d}-{d:02d}"
                return norm, "DATE_TEXT_MONTH", 0, 1.0

    # 2b. Month text first: "Apr 01, 2026", "April 1, 2026"
    m_text2 = re.match(r'^([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{2,4})$', raw)
    if m_text2:
        mon_str = m_text2.group(1).lower()
        d = int(m_text2.group(2))
        y_str = m_text2.group(3)
        y = int(f"20{y_str}" if len(y_str) == 2 and int(y_str) < 50 else (f"19{y_str}" if len(y_str) == 2 else y_str))
        if mon_str in MONTH_MAP:
            m = int(MONTH_MAP[mon_str])
            if is_valid_calendar_date(y, m, d):
                norm = f"{y:04d}-{m:02d}-{d:02d}"
                return norm, "DATE_MONTH_FIRST_TEXT", 0, 1.0

    # 3. Numeric Day-Month-Year: e.g. "01/04/2026", "01-04-2026", "1.4.26"
    m_dmy = re.match(r'^(\d{1,2})[-/. ](\d{1,2})[-/. ](\d{2,4})$', raw)
    if m_dmy:
        part1, part2, y_str = int(m_dmy.group(1)), int(m_dmy.group(2)), m_dmy.group(3)
        y = int(f"20{y_str}" if len(y_str) == 2 and int(y_str) < 50 else (f"19{y_str}" if len(y_str) == 2 else y_str))

        # Check for ambiguity: e.g. 03/04/2026 (3rd April vs 4th March)
        if part1 <= 12 and part2 <= 12:
            # Default Indian CA accounting standard: DD/MM/YYYY
            d, m = part1, part2
            if is_valid_calendar_date(y, m, d):
                norm = f"{y:04d}-{m:02d}-{d:02d}"
                # Flag as questionable if both day and month are ambiguous (different values)
                is_quest = 1 if part1 != part2 else 0
                conf = 0.85 if is_quest else 1.0
                return norm, "DATE_INDIAN_DMY_AMBIGUOUS" if is_quest else "DATE_INDIAN_DMY", is_quest, conf

        # If part1 > 12 -> Must be Day (DD/MM/YYYY)
        if part1 > 12 and part2 <= 12:
            d, m = part1, part2
            if is_valid_calendar_date(y, m, d):
                norm = f"{y:04d}-{m:02d}-{d:02d}"
                return norm, "DATE_DAY_FIRST_DMY", 0, 1.0

        # If part2 > 12 -> Must be Month-first (MM/DD/YYYY)
        if part1 <= 12 and part2 > 12:
            m, d = part1, part2
            if is_valid_calendar_date(y, m, d):
                norm = f"{y:04d}-{m:02d}-{d:02d}"
                return norm, "DATE_MONTH_FIRST_MDY", 0, 0.95

    # 4. Compact numeric: "20260401" or "01042026"
    if re.match(r'^\d{8}$', raw):
        if raw.startswith("20") or raw.startswith("19"):
            y, m, d = int(raw[:4]), int(raw[4:6]), int(raw[6:8])
            if is_valid_calendar_date(y, m, d):
                norm = f"{y:04d}-{m:02d}-{d:02d}"
                return norm, "DATE_COMPACT_ISO", 0, 1.0
        else:
            d, m, y = int(raw[:2]), int(raw[2:4]), int(raw[4:8])
            if is_valid_calendar_date(y, m, d):
                norm = f"{y:04d}-{m:02d}-{d:02d}"
                return norm, "DATE_COMPACT_DMY", 1, 0.85

    # Unparseable fallback
    return raw, "UNPARSEABLE_DATE_RAW", 1, 0.0

def normalize_monetary_amount(raw_val: Any) -> Tuple[float, str, str, int, float]:
    """
    Normalizes monetary values, stripping Indian & Western comma formatting,
    currency symbols (₹, Rs., $, INR), bracketed negatives, and trailing notations.
    Returns (float_value, formatted_inr_string, rule_applied, is_questionable, confidence).
    """
    if raw_val is None or str(raw_val).strip() == "":
        return 0.0, "0.00", "EMPTY_MONETARY", 0, 1.0

    raw = clean_whitespace(raw_val)
    orig_clean = raw
    rule = "DIRECT_NUMERIC"
    is_quest = 0
    conf = 1.0

    # 1. Remove trailing "/-", "/–", "/=", "--", "only" first
    if re.search(r'(/[-–=]|--|\bonly\b)$', raw, re.IGNORECASE):
        raw = re.sub(r'(/[-–=]|--|\bonly\b)$', '', raw, flags=re.IGNORECASE).strip()
        rule = "TRAILING_DENOMINATION_STRIPPED"

    # 2. Check and remove currency symbols (₹, Rs., $, €, £, INR)
    if any(sym in raw for sym in ["₹", "Rs.", "Rs", "INR", "$", "€", "£"]):
        raw = re.sub(r'[₹$€£]|Rs\.?|INR', '', raw, flags=re.IGNORECASE).strip()
        rule = "CURRENCY_SYMBOL_STRIPPED"

    # 3. Check for trailing Dr/Cr
    is_negative = False
    if re.search(r'\b(dr|cr)\b', raw, re.IGNORECASE):
        if re.search(r'\bcr\b', raw, re.IGNORECASE):
            is_negative = True
            rule = "CR_NOTATION_NORMALIZED"
        else:
            rule = "DR_NOTATION_NORMALIZED"
        raw = re.sub(r'\b(dr|cr)\.?', '', raw, flags=re.IGNORECASE).strip()

    # 4. Check for bracketed negative e.g. "(5,000.00)" or leading/trailing minus
    if re.match(r'^\(.*\)$', raw) or raw.endswith("-") or raw.startswith("-"):
        is_negative = True
        raw = raw.replace("(", "").replace(")", "").replace("-", "")
        if rule == "DIRECT_NUMERIC":
            rule = "BRACKETED_NEGATIVE_STANDARDIZED"

    # Strip all formatting commas and spaces
    clean_numeric = raw.replace(",", "").strip()

    try:
        val = float(clean_numeric)
        if is_negative and val > 0:
            val = -val
        formatted = f"{val:,.2f}"
        return val, formatted, rule, is_quest, conf
    except ValueError:
        return 0.0, orig_clean, "INVALID_NUMERIC_FORMAT", 1, 0.0

def normalize_entity_name(raw_val: Any) -> Tuple[str, str, int, float]:
    """
    Normalizes account heads, party names, customers, and vendors:
    - Collapses spaces and non-breaking spaces
    - Standardizes legal entity suffixes (Pvt Ltd, LLP, Ltd)
    - Normalizes case to title casing for words, preserving acronyms
    - Removes duplicate prefixes (M/s, M/S.)
    """
    if raw_val is None or str(raw_val).strip() == "":
        return "", "EMPTY_ENTITY", 0, 1.0

    raw = clean_whitespace(raw_val)
    orig = raw
    rule = "WHITESPACE_COLLAPSED"
    is_quest = 0
    conf = 1.0

    # Prefix normalization: M/S., M/s., M/S -> M/s
    if re.match(r'^(M/s\.?|M/S\.?|MS\.?)\s+', raw, re.IGNORECASE):
        raw = re.sub(r'^(M/s\.?|M/S\.?|MS\.?)\s+', 'M/s ', raw, flags=re.IGNORECASE)
        rule = "PREFIX_MS_STANDARDIZED"

    # Legal entity suffix normalizations
    if re.search(r'\b(pvt\.?\s*ltd\.?|private\s+limited|p\.?\s*ltd\.?)\b', raw, re.IGNORECASE):
        raw = re.sub(r'\b(pvt\.?\s*ltd\.?|private\s+limited|p\.?\s*ltd\.?)\b', 'Pvt Ltd', raw, flags=re.IGNORECASE)
        rule = "LEGAL_SUFFIX_PVT_LTD"
    elif re.search(r'\b(public\s+limited|ltd\.?|limited)\b', raw, re.IGNORECASE):
        raw = re.sub(r'\b(public\s+limited|ltd\.?|limited)\b', 'Ltd', raw, flags=re.IGNORECASE)
        rule = "LEGAL_SUFFIX_LTD"
    elif re.search(r'\b(l\.?l\.?p\.?|limited\s+liability\s+partnership)\b', raw, re.IGNORECASE):
        raw = re.sub(r'\b(l\.?l\.?p\.?|limited\s+liability\s+partnership)\b', 'LLP', raw, flags=re.IGNORECASE)
        rule = "LEGAL_SUFFIX_LLP"

    # Title Casing if original was all lowercase or all uppercase
    if orig.islower() or (orig.isupper() and len(orig) > 4):
        words = raw.split()
        capitalized = []
        for w in words:
            if w.upper() in ["PVT", "LTD", "LLP", "HDFC", "ICICI", "SBI", "GST", "TCS", "M/S", "CO.", "CORP", "INC"]:
                capitalized.append("Pvt" if w.upper() == "PVT" else ("Ltd" if w.upper() == "LTD" else w.upper()))
            else:
                capitalized.append(w.capitalize())
        raw = " ".join(capitalized)
        if rule == "WHITESPACE_COLLAPSED":
            rule = "TITLE_CASE_NORMALIZED"

    return clean_whitespace(raw), rule, is_quest, conf

def normalize_invoice_voucher(raw_val: Any) -> Tuple[str, str, int, float]:
    """
    Normalizes invoice numbers and voucher reference strings:
    - Removes internal extraneous spaces around delimiters
    - Normalizes case to uppercase
    - Strips invisible control characters
    """
    if raw_val is None or str(raw_val).strip() == "":
        return "", "EMPTY_REF", 0, 1.0

    raw = clean_whitespace(raw_val)
    orig = raw
    rule = "WHITESPACE_TRIMMED"
    is_quest = 0
    conf = 1.0

    # Remove internal spaces around slashes or hyphens e.g. "INV / 2024 / 001" -> "INV/2024/001"
    clean_val = re.sub(r'\s*([/\-_.:])\s*', r'\1', raw)
    # Uppercase
    clean_val = clean_val.upper()

    if clean_val != orig:
        rule = "INVOICE_DELIMITER_NORMALIZED"

    return clean_val, rule, is_quest, conf

def normalize_gstin(raw_val: Any) -> Tuple[str, str, int, float]:
    """
    Normalizes 15-character statutory GSTIN:
    - Uppercases and strips whitespace/hyphens
    - Validates against statutory regex
    """
    if raw_val is None or str(raw_val).strip() == "":
        return "", "EMPTY_GSTIN", 0, 1.0

    raw = clean_whitespace(raw_val)
    clean_val = re.sub(r'[^A-Za-z0-9]', '', raw).upper()

    if re.match(GSTIN_PATTERN, clean_val):
        return clean_val, "GSTIN_VALIDATED_NORMALIZED", 0, 1.0
    else:
        # Invalid GSTIN format
        return clean_val, "INVALID_GSTIN_FORMAT", 1, 0.4

def normalize_row_data(
    raw_dict: Dict[str, Any],
    mapping: Optional[Dict[str, str]] = None,
    row_num: int = 1
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Performs complete multi-attribute normalization on a single imported transaction record.
    Returns:
      (normalized_record, transformation_logs)
    where original values are strictly preserved in `original_row_json` and transformation logs.
    """
    if mapping is None:
        mapping = {k: k for k in raw_dict.keys()}

    tx: Dict[str, Any] = {}
    logs: List[Dict[str, Any]] = []

    # Preserve raw untouched input dictionary in original_row_json
    tx["original_row_json"] = json.dumps(raw_dict)

    # Copy raw mapped values
    for src_col, target in mapping.items():
        if src_col in raw_dict and target:
            val = raw_dict[src_col]
            tx[target] = val

    # 1. Date Normalization
    raw_date = tx.get("date")
    norm_date, d_rule, d_quest, d_conf = normalize_date(raw_date)
    tx["date"] = norm_date or (str(raw_date) if raw_date is not None else "")
    if str(raw_date or "").strip() != norm_date and str(raw_date or "").strip() != "":
        logs.append({
            "row_number": row_num,
            "field_name": "date",
            "original_value": str(raw_date),
            "normalized_value": norm_date,
            "transformation_rule": d_rule,
            "is_questionable": d_quest,
            "confidence_score": d_conf
        })

    # 2. Ledger Name Normalization
    raw_ledger = tx.get("ledger")
    norm_ledger, l_rule, l_quest, l_conf = normalize_entity_name(raw_ledger)
    tx["ledger"] = norm_ledger or (str(raw_ledger) if raw_ledger is not None else "General Ledger")
    if str(raw_ledger or "").strip() != norm_ledger and str(raw_ledger or "").strip() != "":
        logs.append({
            "row_number": row_num,
            "field_name": "ledger",
            "original_value": str(raw_ledger),
            "normalized_value": norm_ledger,
            "transformation_rule": l_rule,
            "is_questionable": l_quest,
            "confidence_score": l_conf
        })

    # 3. Party Name Normalization
    raw_party = tx.get("party_name")
    if raw_party:
        norm_party, p_rule, p_quest, p_conf = normalize_entity_name(raw_party)
        tx["party_name"] = norm_party
        if str(raw_party).strip() != norm_party:
            logs.append({
                "row_number": row_num,
                "field_name": "party_name",
                "original_value": str(raw_party),
                "normalized_value": norm_party,
                "transformation_rule": p_rule,
                "is_questionable": p_quest,
                "confidence_score": p_conf
            })

    # 4. Voucher & Invoice Number Normalization
    raw_vch = tx.get("voucher_no")
    if raw_vch:
        norm_vch, v_rule, v_quest, v_conf = normalize_invoice_voucher(raw_vch)
        tx["voucher_no"] = norm_vch
        if str(raw_vch).strip() != norm_vch:
            logs.append({
                "row_number": row_num,
                "field_name": "voucher_no",
                "original_value": str(raw_vch),
                "normalized_value": norm_vch,
                "transformation_rule": v_rule,
                "is_questionable": v_quest,
                "confidence_score": v_conf
            })

    raw_inv = tx.get("invoice_no")
    if raw_inv:
        norm_inv, inv_rule, inv_quest, inv_conf = normalize_invoice_voucher(raw_inv)
        tx["invoice_no"] = norm_inv
        if str(raw_inv).strip() != norm_inv:
            logs.append({
                "row_number": row_num,
                "field_name": "invoice_no",
                "original_value": str(raw_inv),
                "normalized_value": norm_inv,
                "transformation_rule": inv_rule,
                "is_questionable": inv_quest,
                "confidence_score": inv_conf
            })

    # 5. GSTIN Normalization
    raw_gstin = tx.get("gstin")
    if raw_gstin:
        norm_gstin, g_rule, g_quest, g_conf = normalize_gstin(raw_gstin)
        tx["gstin"] = norm_gstin
        if str(raw_gstin).strip() != norm_gstin:
            logs.append({
                "row_number": row_num,
                "field_name": "gstin",
                "original_value": str(raw_gstin),
                "normalized_value": norm_gstin,
                "transformation_rule": g_rule,
                "is_questionable": g_quest,
                "confidence_score": g_conf
            })

    # 6. Monetary Amounts Normalization (Debit, Credit, Amount, Tax)
    raw_debit = tx.get("debit")
    norm_debit, deb_fmt, deb_rule, deb_quest, deb_conf = normalize_monetary_amount(raw_debit)
    tx["debit"] = max(0.0, norm_debit)
    if raw_debit is not None and str(raw_debit).strip() != "" and str(raw_debit).strip() != str(tx["debit"]):
        logs.append({
            "row_number": row_num,
            "field_name": "debit",
            "original_value": str(raw_debit),
            "normalized_value": f"{tx['debit']:.2f}",
            "transformation_rule": deb_rule,
            "is_questionable": deb_quest,
            "confidence_score": deb_conf
        })

    raw_credit = tx.get("credit")
    norm_credit, cr_fmt, cr_rule, cr_quest, cr_conf = normalize_monetary_amount(raw_credit)
    tx["credit"] = max(0.0, norm_credit)
    if raw_credit is not None and str(raw_credit).strip() != "" and str(raw_credit).strip() != str(tx["credit"]):
        logs.append({
            "row_number": row_num,
            "field_name": "credit",
            "original_value": str(raw_credit),
            "normalized_value": f"{tx['credit']:.2f}",
            "transformation_rule": cr_rule,
            "is_questionable": cr_quest,
            "confidence_score": cr_conf
        })

    raw_amount = tx.get("amount")
    norm_amount, amt_fmt, amt_rule, amt_quest, amt_conf = normalize_monetary_amount(raw_amount)
    if raw_amount is not None and str(raw_amount).strip() != "":
        tx["amount"] = abs(norm_amount)
        if str(raw_amount).strip() != str(tx["amount"]):
            logs.append({
                "row_number": row_num,
                "field_name": "amount",
                "original_value": str(raw_amount),
                "normalized_value": f"{tx['amount']:.2f}",
                "transformation_rule": amt_rule,
                "is_questionable": amt_quest,
                "confidence_score": amt_conf
            })
    else:
        tx["amount"] = max(tx["debit"], tx["credit"])

    # 7. Description & Narration Whitespace Cleaning
    raw_desc = tx.get("description")
    if raw_desc:
        clean_desc = clean_whitespace(raw_desc)
        tx["description"] = clean_desc
        if str(raw_desc) != clean_desc:
            logs.append({
                "row_number": row_num,
                "field_name": "description",
                "original_value": str(raw_desc),
                "normalized_value": clean_desc,
                "transformation_rule": "DESCRIPTION_WHITESPACE_COLLAPSED",
                "is_questionable": 0,
                "confidence_score": 1.0
            })

    return tx, logs
