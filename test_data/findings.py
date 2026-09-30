"""
Test Audit Findings Definitions
FinAuditPro - Test Data Architecture
"""

from typing import List, Dict, Any

def get_test_findings_for_company(company_code: str, engagement_id: int) -> List[Dict[str, Any]]:
    code = company_code.upper()
    return [
        {
            "engagement_id": engagement_id,
            "rule_id": "RULE_SEC_40A3",
            "title": f"[{code}] Contravention of Section 40A(3) - Cash Payment Exceeding Statutory Limit",
            "severity": "CRITICAL",
            "financial_impact": 55000.0,
            "risk": "HIGH",
            "description": f"Freight payment of ₹55,000 made in cash directly violates Section 40A(3) of the Income Tax Act 1961 and is liable to 100% disallowance.",
            "recommendation": "Obtain banking channel proof or disallow ₹55,000 under Clause 21(d) of Form 3CD.",
            "status": "Open",
            "created_by": "Senior Auditor"
        },
        {
            "engagement_id": engagement_id,
            "rule_id": "RULE_DUP_INVOICE",
            "title": f"[{code}] Potential Duplicate Vendor Invoice Entry Detected",
            "severity": "HIGH",
            "financial_impact": 125000.0,
            "risk": "HIGH",
            "description": f"Invoice INV-DUP-{code}-99 posted twice for ₹125,000 on the same date under IT Software & Cloud Services.",
            "recommendation": "Inspect vendor statement of account to confirm whether payment was processed twice.",
            "status": "Under Review",
            "created_by": "Audit Staff"
        },
        {
            "engagement_id": engagement_id,
            "rule_id": "RULE_GST_MISMATCH",
            "title": f"[{code}] GSTR-2B vs Purchase Register Tax Discrepancy",
            "severity": "MEDIUM",
            "financial_impact": 88500.0,
            "risk": "MEDIUM",
            "description": f"Unreflected vendor invoices identified in GSTR-2B reconciliation requiring supplier communication.",
            "recommendation": "Issue vendor reconciliation letters for unuploaded GSTR-1 returns.",
            "status": "In Progress",
            "created_by": "Audit Staff"
        }
    ]
