import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.app.database import get_db_connection

DEFAULT_GST_RULES: List[Dict[str, Any]] = [
    {
        "rule_key": "tolerance_limits",
        "category": "Matching Tolerances",
        "title": "Value & Tax Round-Off Tolerances",
        "description": "Configurable numeric variance thresholds for determining Exact vs Partial vs Mismatched invoice amounts.",
        "config_json": json.dumps({
            "taxable_value_tolerance": 5.00,       # ₹5.00 allowable rounding difference on taxable value
            "tax_heads_tolerance": 2.00,           # ₹2.00 allowable difference per tax head (CGST/SGST/IGST)
            "total_invoice_tolerance": 5.00,       # ₹5.00 allowable difference on gross invoice value
            "currency": "INR",
            "allow_fractional_paise_rounding": True
        }),
        "version": "v2024.1"
    },
    {
        "rule_key": "date_cutoff_disparity",
        "category": "Timing & Cutoff",
        "title": "Invoice Date Timing Disparity Threshold",
        "description": "Permitted transit lag and booking timing difference between supplier GSTR-1/2B date and buyer book entry date.",
        "config_json": json.dumps({
            "max_date_disparity_days": 30,         # Flag as date disparity if disparity > 30 days
            "warn_date_disparity_days": 15,        # Partial match warning if disparity > 15 days
            "financial_year_cutoff_strict": True   # Strict check if crossing March 31 financial year-end
        }),
        "version": "v2024.1"
    },
    {
        "rule_key": "fuzzy_matching_rules",
        "category": "String & Fuzzy Matching",
        "title": "Invoice Number & Party Fuzzy Matching",
        "description": "Rules for normalizing prefixes, slashes, zeros, and trade name variations.",
        "config_json": json.dumps({
            "strip_special_characters": True,      # Strips '/', '-', '.', spaces
            "strip_leading_zeros": True,           # Converts '00123' -> '123'
            "min_invoice_similarity": 0.85,        # 85% token similarity for fuzzy match
            "min_party_similarity": 0.70,          # 70% token similarity for party trade name
            "ignore_case": True,
            "strip_legal_suffixes": ["ltd", "pvt", "limited", "private", "llp", "inc", "corp", "co"]
        }),
        "version": "v2024.1"
    },
    {
        "rule_key": "gstin_structure_validation",
        "category": "Statutory Validation",
        "title": "15-Digit GSTIN Format & State Code Rules",
        "description": "Validation criteria for commercial Goods and Services Tax Identification Number.",
        "config_json": json.dumps({
            "regex_pattern": "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
            "enforce_15_char_length": True,
            "valid_state_codes": [
                "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
                "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
                "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
                "31", "32", "33", "34", "35", "36", "37", "38", "97", "99"
            ]
        }),
        "version": "v2024.1"
    },
    {
        "rule_key": "statutory_tax_slabs",
        "category": "Tax Computation",
        "title": "Recognized GST Slab Rates",
        "description": "Active statutory rate slabs for verifying calculated tax vs taxable value.",
        "config_json": json.dumps({
            "active_rates": [0.0, 0.25, 3.0, 5.0, 12.0, 18.0, 28.0],
            "default_rate": 18.0,
            "compensation_cess_supported": True
        }),
        "version": "v2024.1"
    },
    {
        "rule_key": "place_of_supply_logic",
        "category": "Tax Head Apportionment",
        "title": "Inter-State (IGST) vs Intra-State (CGST+SGST) Rules",
        "description": "Rules for checking proper tax head bifurcation between supplier and recipient state.",
        "config_json": json.dumps({
            "inter_state_requires_igst": True,
            "intra_state_requires_equal_cgst_sgst": True,
            "flag_wrong_tax_head_as_mismatch": True
        }),
        "version": "v2024.1"
    },
    {
        "rule_key": "itc_section_16_2_aa",
        "category": "ITC Compliance",
        "title": "Section 16(2)(aa) GSTR-2B Eligibility Filter",
        "description": "Mandatory auto-population check restricting Input Tax Credit to invoices communicated in GSTR-2B.",
        "config_json": json.dumps({
            "enforce_gstr2b_reflection": True,
            "itc_ineligible_if_missing_in_2b": True,
            "credit_debit_note_matching": True,
            "flag_unmatched_as_exception": True
        }),
        "version": "v2024.1"
    }
]

def init_default_gst_rules(conn=None):
    """Ensures default configurable GST rule rows exist in the database."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    now_str = datetime.now().isoformat()
    for rule in DEFAULT_GST_RULES:
        existing = conn.execute("SELECT id FROM gst_rule_configurations WHERE rule_key = ?", (rule["rule_key"],)).fetchone()
        if not existing:
            conn.execute("""
                INSERT INTO gst_rule_configurations (rule_key, category, title, description, config_json, is_active, version, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, 'system', ?)
            """, (rule["rule_key"], rule["category"], rule["title"], rule["description"], rule["config_json"], rule["version"], now_str))

    conn.commit()
    if should_close:
        conn.close()

def get_all_gst_rules() -> List[Dict[str, Any]]:
    """Returns all configurable GST rules parsed with JSON configs."""
    conn = get_db_connection()
    init_default_gst_rules(conn)
    rows = conn.execute("SELECT * FROM gst_rule_configurations ORDER BY id ASC").fetchall()
    rules = []
    for r in rows:
        d = dict(r)
        try:
            d["config"] = json.loads(d["config_json"])
        except Exception:
            d["config"] = {}
        rules.append(d)
    conn.close()
    return rules

def get_gst_rule(rule_key: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single GST rule by key."""
    conn = get_db_connection()
    init_default_gst_rules(conn)
    row = conn.execute("SELECT * FROM gst_rule_configurations WHERE rule_key = ?", (rule_key,)).fetchone()
    if not row:
        conn.close()
        return None
    d = dict(row)
    try:
        d["config"] = json.loads(d["config_json"])
    except Exception:
        d["config"] = {}
    conn.close()
    return d

def get_active_gst_rules_map() -> Dict[str, Any]:
    """Returns a consolidated dictionary of all active GST rule configs for fast engine lookup."""
    rules = get_all_gst_rules()
    rule_map = {}
    for r in rules:
        if r.get("is_active", 1):
            rule_map[r["rule_key"]] = r.get("config", {})
    return rule_map

def update_gst_rule(rule_key: str, new_config: Dict[str, Any], updated_by: str = "admin") -> Dict[str, Any]:
    """Updates a GST rule's configuration parameters dynamically."""
    conn = get_db_connection()
    init_default_gst_rules(conn)
    row = conn.execute("SELECT * FROM gst_rule_configurations WHERE rule_key = ?", (rule_key,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Rule with key '{rule_key}' not found.")

    old_version = row["version"] or "v1.0"
    # Increment minor version
    try:
        ver_num = float(old_version.replace("v", "")) + 0.1
        new_version = f"v{ver_num:.1f}"
    except Exception:
        new_version = f"{old_version}.1"

    now_str = datetime.now().isoformat()
    config_str = json.dumps(new_config, indent=2)

    conn.execute("""
        UPDATE gst_rule_configurations 
        SET config_json = ?, version = ?, updated_by = ?, updated_at = ?
        WHERE rule_key = ?
    """, (config_str, new_version, updated_by, now_str, rule_key))

    # Log in audit trail
    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action="UPDATE_GST_RULE",
        module="GST_RULES",
        record_id=row["id"],
        user=updated_by,
        details=f"Updated configurable GST rule '{rule_key}' to version {new_version}",
        timestamp=now_str
    )

    conn.commit()
    conn.close()

    return {
        "rule_key": rule_key,
        "version": new_version,
        "config": new_config,
        "updated_at": now_str
    }

def reset_gst_rules_to_default(updated_by: str = "admin") -> bool:
    """Resets all configurable GST rules to factory standard parameters."""
    conn = get_db_connection()
    now_str = datetime.now().isoformat()
    conn.execute("DELETE FROM gst_rule_configurations")
    for rule in DEFAULT_GST_RULES:
        conn.execute("""
            INSERT INTO gst_rule_configurations (rule_key, category, title, description, config_json, is_active, version, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
        """, (rule["rule_key"], rule["category"], rule["title"], rule["description"], rule["config_json"], rule["version"], updated_by, now_str))

    from backend.app.utils.audit_logger import log_audit_event
    log_audit_event(
        conn=conn,
        action="RESET_GST_RULES",
        module="GST_RULES",
        record_id=0,
        user=updated_by,
        details="Reset all GST rules to default baseline",
        timestamp=now_str
    )

    conn.commit()
    conn.close()
    return True
