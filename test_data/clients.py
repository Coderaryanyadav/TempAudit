"""
Test Clients Definitions
FinAuditPro - Test Data Architecture
"""

from typing import Dict, Any, List
from test_data.companies import ARYAN_COMPANY, HITANSH_COMPANY

def get_test_clients() -> List[Dict[str, Any]]:
    return [
        {
            "name": ARYAN_COMPANY["name"],
            "company_type": ARYAN_COMPANY["company_type"],
            "pan": ARYAN_COMPANY["pan"],
            "gstin": ARYAN_COMPANY["gstin"],
            "industry": ARYAN_COMPANY["industry"],
            "contact_person": ARYAN_COMPANY["primary_contact"],
            "email": ARYAN_COMPANY["email"],
            "phone": ARYAN_COMPANY["phone"],
            "address": ARYAN_COMPANY["address"]
        },
        {
            "name": HITANSH_COMPANY["name"],
            "company_type": HITANSH_COMPANY["company_type"],
            "pan": HITANSH_COMPANY["pan"],
            "gstin": HITANSH_COMPANY["gstin"],
            "industry": HITANSH_COMPANY["industry"],
            "contact_person": HITANSH_COMPANY["primary_contact"],
            "email": HITANSH_COMPANY["email"],
            "phone": HITANSH_COMPANY["phone"],
            "address": HITANSH_COMPANY["address"]
        }
    ]
