"""
Test Working Papers Definitions
FinAuditPro - Test Data Architecture
"""

from typing import List, Dict, Any

def get_test_working_papers_for_company(company_code: str, engagement_id: int) -> List[Dict[str, Any]]:
    code = company_code.upper()
    return [
        {
            "engagement_id": engagement_id,
            "wp_reference": f"WP-REV-{code}-01",
            "title": f"[{code}] Revenue Cut-off and Substantive Testing",
            "module": "Revenue",
            "objective": "Verify revenue recognition compliance with Ind AS 115 and year-end cut-off invoices.",
            "status": "In Progress",
            "prepared_by": "Audit Staff",
            "notes": "Sampled 50 sales transactions across Q1-Q4. Validated API invoicing logs and GST returns agreement."
        },
        {
            "engagement_id": engagement_id,
            "wp_reference": f"WP-BNK-{code}-01",
            "title": f"[{code}] Bank Reconciliation and Balance Confirmation",
            "module": "Cash & Bank",
            "objective": "Substantiate bank balances against direct bank confirmations (SA 505) and inspect stale items.",
            "status": "Prepared",
            "prepared_by": "Senior Auditor",
            "notes": "100+ transactions matched automatically. Investigating 10 unpresented cheques and bank charges."
        },
        {
            "engagement_id": engagement_id,
            "wp_reference": f"WP-GST-{code}-01",
            "title": f"[{code}] GST ITC Reconciliations & Rule 36(4) Compliance",
            "module": "GST",
            "objective": "Ensure all claimed Input Tax Credit appears in GSTR-2B and conforms to Section 16 eligibility criteria.",
            "status": "Draft",
            "prepared_by": "Audit Staff",
            "notes": "Reconciled purchase register against auto-drafted GSTR-2B data."
        }
    ]
